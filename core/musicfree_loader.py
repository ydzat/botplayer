"""
MusicFree 插件加载器
支持加载和执行 JavaScript 格式的 MusicFree 插件
"""
import os
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any
import requests
import execjs
from pathlib import Path
from .models import Song

logger = logging.getLogger(__name__)


class MusicFreePluginLoader:
    """MusicFree 插件加载器"""
    
    def __init__(self, plugin_dir: str = "data/plugins"):
        self.plugin_dir = Path(plugin_dir)
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        self.loaded_plugins: Dict[str, dict] = {}
        self.js_runtime = None
        
        # 初始化 JavaScript 运行时
        self._init_js_runtime()
    
    def _init_js_runtime(self):
        """初始化 JavaScript 运行时环境"""
        try:
            # 尝试使用 Node.js
            self.js_runtime = execjs.get("Node")
            logger.info("使用 Node.js 作为 JavaScript 运行时")
        except:
            try:
                # 备选：使用 V8
                self.js_runtime = execjs.get("V8")
                logger.info("使用 V8 作为 JavaScript 运行时")
            except:
                # 最后备选：使用默认运行时
                self.js_runtime = execjs.get()
                logger.warning(f"使用默认 JavaScript 运行时: {self.js_runtime.name}")
    
    async def load_plugins_from_json(self, plugins_json_path: str):
        """从 plugins.json 文件加载插件"""
        try:
            with open(plugins_json_path, 'r', encoding='utf-8') as f:
                plugins_config = json.load(f)
            
            plugins_list = plugins_config.get('plugins', [])
            logger.info(f"开始加载 {len(plugins_list)} 个 MusicFree 插件")
            
            for plugin_config in plugins_list:
                try:
                    await self._load_single_plugin(plugin_config)
                except Exception as e:
                    logger.warning(f"加载插件失败 {plugin_config.get('name', 'Unknown')}: {e}")
            
            logger.info(f"成功加载 {len(self.loaded_plugins)} 个 MusicFree 插件")
            
        except Exception as e:
            logger.error(f"加载插件配置文件失败: {e}")
    
    async def _load_single_plugin(self, plugin_config: dict):
        """加载单个插件"""
        plugin_name = plugin_config.get('name', 'Unknown')
        plugin_url = plugin_config.get('url', '')
        plugin_version = plugin_config.get('version', '0.0.0')
        
        if not plugin_url:
            logger.warning(f"插件 {plugin_name} 没有 URL")
            return
        
        # 下载插件代码
        plugin_code = await self._download_plugin(plugin_url, plugin_name)
        if not plugin_code:
            return
        
        # 解析插件
        plugin_info = self._parse_plugin(plugin_code, plugin_name, plugin_version)
        if plugin_info:
            self.loaded_plugins[plugin_name] = plugin_info
            logger.info(f"成功加载插件: {plugin_name} v{plugin_version}")
    
    async def _download_plugin(self, url: str, name: str) -> Optional[str]:
        """下载插件代码"""
        try:
            # 检查本地缓存
            cache_file = self.plugin_dir / f"{name}.js"
            
            # 如果缓存存在且不超过24小时，使用缓存
            if cache_file.exists():
                file_age = cache_file.stat().st_mtime
                import time
                if time.time() - file_age < 86400:  # 24小时
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        logger.info(f"使用缓存的插件代码: {name}")
                        return f.read()
            
            # 下载新代码
            logger.info(f"下载插件代码: {url}")
            response = requests.get(url, timeout=30, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response.raise_for_status()
            
            plugin_code = response.text
            
            # 保存到缓存
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(plugin_code)
            
            return plugin_code
            
        except Exception as e:
            logger.error(f"下载插件失败 {name}: {e}")
            return None
    
    def _parse_plugin(self, plugin_code: str, name: str, version: str) -> Optional[dict]:
        """解析插件代码"""
        try:
            # 创建模拟的模块环境
            js_wrapper = f"""
            // 模拟 Node.js 环境
            var module = {{ exports: {{}} }};
            var exports = module.exports;
            var require = function(name) {{
                // 模拟常用模块
                if (name === 'axios') return axios_mock;
                if (name === 'dayjs') return dayjs_mock;
                if (name === 'he') return he_mock;
                if (name === 'crypto-js') return crypto_mock;
                if (name === 'cheerio') return cheerio_mock;
                return {{}};
            }};
            
            // 模拟对象
            var axios_mock = {{
                get: function() {{ return Promise.resolve({{data: {{}}}}); }},
                post: function() {{ return Promise.resolve({{data: {{}}}}); }}
            }};
            var dayjs_mock = {{
                unix: function(ts) {{ return {{ format: function() {{ return new Date(ts * 1000).toISOString().split('T')[0]; }} }}; }}
            }};
            var he_mock = {{
                decode: function(str) {{ return str; }}
            }};
            var crypto_mock = {{
                MD5: function(str) {{ return {{ toString: function() {{ return 'mock_md5'; }} }}; }},
                HmacSHA256: function(msg, key) {{ return {{ toString: function() {{ return 'mock_hmac'; }} }}; }},
                enc: {{ Hex: 'hex' }}
            }};
            var cheerio_mock = {{
                load: function() {{ return function() {{ return {{ text: function() {{ return '{{}}'; }} }}; }}; }}
            }};
            
            // 插件代码
            {plugin_code}
            
            // 返回插件对象
            module.exports;
            """
            
            # 执行 JavaScript 代码
            result = self.js_runtime.eval(js_wrapper)
            
            if result and isinstance(result, dict):
                # 提取插件信息
                plugin_info = {
                    'name': name,
                    'version': version,
                    'platform': result.get('platform', name),
                    'author': result.get('author', 'Unknown'),
                    'description': f"MusicFree 插件: {name}",
                    'type': 'musicfree',
                    'enabled': True,
                    'js_code': plugin_code,
                    'js_object': result,
                    'supported_search_types': result.get('supportedSearchType', ['music'])
                }
                return plugin_info
            
        except Exception as e:
            logger.error(f"解析插件代码失败 {name}: {e}")
        
        return None
    
    async def search_in_plugin(self, plugin_name: str, query: str, page: int = 1, search_type: str = 'music') -> List[Song]:
        """在指定插件中搜索"""
        plugin = self.loaded_plugins.get(plugin_name)
        if not plugin:
            logger.warning(f"插件未找到: {plugin_name}")
            return []
        
        try:
            # 由于 JavaScript 执行的复杂性，这里返回模拟结果
            # 在实际实现中，需要更复杂的 JS-Python 交互
            logger.info(f"在插件 {plugin_name} 中搜索: {query}")
            
            # 这里可以实现真实的 JavaScript 函数调用
            # 但需要处理异步函数和复杂的网络请求
            
            return []
            
        except Exception as e:
            logger.error(f"插件搜索失败 {plugin_name}: {e}")
            return []
    
    def get_loaded_plugins(self) -> List[dict]:
        """获取已加载的插件列表"""
        return [
            {
                'name': plugin['name'],
                'version': plugin['version'],
                'platform': plugin['platform'],
                'author': plugin['author'],
                'description': plugin['description'],
                'type': plugin['type'],
                'enabled': plugin['enabled'],
                'supported_types': plugin.get('supported_search_types', [])
            }
            for plugin in self.loaded_plugins.values()
        ]
