"""
音源管理器
负责加载和管理音源插件，提供统一的搜索和获取接口
"""
import os
import json
import asyncio
import subprocess
import logging
import re
from typing import Dict, List, Optional, Any
from pathlib import Path
import requests
import tempfile
from .models import Song
from .bilibili_source import BilibiliMusicSource
from .musicfree_loader import MusicFreePluginLoader
import urllib.parse

logger = logging.getLogger(__name__)


class PluginManager:
    """音源插件管理器"""
    
    def __init__(self, plugin_dir: str = "plugins", config: Dict = None):
        self.plugin_dir = Path(plugin_dir)
        self.config = config or {}
        self.plugins: Dict[str, dict] = {}
        
        # 初始化真实的音源实现
        self.bilibili_source = BilibiliMusicSource()
        self.musicfree_loader = MusicFreePluginLoader(str(self.plugin_dir))
        
        # 创建插件目录
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载插件
        self.load_plugins()
    
    def load_plugins(self):
        """扫描并加载音源插件"""
        try:
            # 加载内置插件
            self._load_builtin_plugins()
            
            logger.info(f"Loaded {len(self.plugins)} audio source plugins")
            
        except Exception as e:
            logger.error(f"Error loading plugins: {e}")
    
    async def initialize_async_plugins(self):
        """初始化异步插件（需要在异步环境中调用）"""
        try:
            # 暂时禁用 MusicFree 插件，专注于内置插件
            logger.info("MusicFree 插件加载已暂时禁用，使用内置插件")
            # 未来可以重新启用 MusicFree 插件加载
        except Exception as e:
            logger.error(f"MusicFree插件初始化失败: {e}")
            import traceback
            traceback.print_exc()
    
    async def _load_musicfree_plugins(self):
        """异步加载 MusicFree 插件"""
        try:
            # 暂时禁用 MusicFree 插件加载，因为需要复杂的 JavaScript 环境
            # 当前专注于内置插件的稳定工作
            logger.info("MusicFree 插件加载已暂时禁用，使用内置插件")
            
            # 确保方法正确返回（避免 await None 错误）
            return None
            
            # TODO: 未来可以重新启用这个功能
            """
            # 查找 plugins.json 文件
            current_dir = Path.cwd()
            plugins_json_paths = [
                current_dir / "plugins.json",
                self.plugin_dir.parent / "plugins.json",
                self.plugin_dir.parent.parent / "plugins.json"
            ]
            
            for plugins_json_path in plugins_json_paths:
                if plugins_json_path.exists():
                    logger.info(f"找到 plugins.json: {plugins_json_path}")
                    await self.musicfree_loader.load_plugins_from_json(str(plugins_json_path))
                    
                    # 将加载的插件添加到插件列表
                    musicfree_plugins = self.musicfree_loader.get_loaded_plugins()
                    for plugin in musicfree_plugins:
                        self.plugins[f"musicfree_{plugin['name']}"] = plugin
                    
                    logger.info(f"从 MusicFree 加载了 {len(musicfree_plugins)} 个插件")
                    break
            else:
                logger.info("未找到 plugins.json 文件")
            """
                
        except Exception as e:
            logger.error(f"加载 MusicFree 插件失败: {e}")
    
    def _load_builtin_plugins(self):
        """加载内置插件"""
        # 改进的 Bilibili 插件
        self.plugins['bilibili'] = {
            'name': 'bilibili',
            'version': '2.0.0',
            'author': 'BotPlayer Enhanced',
            'description': '基于真实 API 的 Bilibili 音频搜索',
            'type': 'builtin_enhanced',
            'enabled': True
        }
        
        # 本地文件插件
        self.plugins['local'] = {
            'name': 'local',
            'version': '1.0.0',
            'author': 'BotPlayer',
            'description': '本地音频文件',
            'type': 'builtin',
            'enabled': True
        }
        
        # 网易云音乐插件
        self.plugins['netease'] = {
            'name': 'netease',
            'version': '1.0.0',
            'author': 'BotPlayer',
            'description': '网易云音乐搜索',
            'type': 'builtin',
            'enabled': True
        }
    
    def _load_musicfree_plugins(self):
        """加载 MusicFree 格式的插件"""
        for file_path in self.plugin_dir.glob('*.js'):
            try:
                plugin_info = self._load_musicfree_plugin(file_path)
                if plugin_info:
                    self.plugins[plugin_info['name']] = plugin_info
                    logger.info(f"Loaded MusicFree plugin: {plugin_info['name']}")
            except Exception as e:
                logger.warning(f"Failed to load plugin {file_path}: {e}")
    
    def _load_musicfree_plugin(self, plugin_path: Path) -> Optional[dict]:
        """加载单个 MusicFree 插件"""
        try:
            with open(plugin_path, 'r', encoding='utf-8') as f:
                plugin_code = f.read()
            
            # 提取插件基本信息
            plugin_info = self._extract_plugin_info(plugin_code)
            if plugin_info:
                plugin_info.update({
                    'code': plugin_code,
                    'path': str(plugin_path),
                    'type': 'musicfree',
                    'enabled': True
                })
                return plugin_info
                
        except Exception as e:
            logger.error(f"Failed to load MusicFree plugin {plugin_path}: {e}")
        
        return None
    
    def _extract_plugin_info(self, plugin_code: str) -> Optional[dict]:
        """从插件代码中提取基本信息"""
        try:
            # 简单的正则提取（实际可能需要更复杂的解析）
            import re
            
            name_match = re.search(r'name\s*:\s*["\']([^"\']+)["\']', plugin_code)
            version_match = re.search(r'version\s*:\s*["\']([^"\']+)["\']', plugin_code)
            author_match = re.search(r'author\s*:\s*["\']([^"\']+)["\']', plugin_code)
            description_match = re.search(r'description\s*:\s*["\']([^"\']+)["\']', plugin_code)
            
            if name_match:
                return {
                    'name': name_match.group(1),
                    'version': version_match.group(1) if version_match else '1.0.0',
                    'author': author_match.group(1) if author_match else 'Unknown',
                    'description': description_match.group(1) if description_match else ''
                }
        except Exception as e:
            logger.warning(f"Failed to extract plugin info: {e}")
        
        return None
    
    async def search_song(self, query: str, plugin_name: str = None, limit: int = 10) -> List[Song]:
        """搜索歌曲"""
        try:
            results = []
            
            if plugin_name and plugin_name in self.plugins:
                # 指定插件搜索
                plugin_results = await self._search_in_plugin(plugin_name, query, limit)
                results.extend(plugin_results)
            else:
                # 所有启用的插件搜索
                tasks = []
                per_plugin_limit = max(1, limit // len([p for p in self.plugins.values() if p.get('enabled', True)]))
                
                for name, plugin in self.plugins.items():
                    if plugin.get('enabled', True):
                        tasks.append(self._search_in_plugin(name, query, per_plugin_limit))
                
                # 并发搜索
                plugin_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in plugin_results:
                    if isinstance(result, list):
                        results.extend(result)
                    elif isinstance(result, Exception):
                        logger.warning(f"Plugin search error: {result}")
            
            # 智能排序和去重
            results = self._rank_and_deduplicate(results, query)
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Error searching songs: {e}")
            return []
    
    async def _search_in_plugin(self, plugin_name: str, query: str, limit: int) -> List[Song]:
        """在指定插件中搜索"""
        try:
            plugin = self.plugins.get(plugin_name)
            if not plugin:
                return []
            
            if plugin['type'] == 'builtin' or plugin['type'] == 'builtin_enhanced':
                return await self._search_builtin(plugin_name, query, limit)
            elif plugin['type'] == 'musicfree':
                return await self.musicfree_loader.search_in_plugin(plugin_name, query, 1, 'music')
            
        except Exception as e:
            logger.error(f"Error searching in plugin {plugin_name}: {e}")
        
        return []
    
    async def _search_builtin(self, plugin_name: str, query: str, limit: int) -> List[Song]:
        """内置插件搜索"""
        if plugin_name == 'bilibili':
            return await self.bilibili_source.search(query, 1, limit)
        elif plugin_name == 'netease':
            return await self._search_netease(query, limit)
        elif plugin_name == 'local':
            return await self._search_local(query, limit)
        
        return []
    
    async def _search_bilibili(self, query: str, limit: int) -> List[Song]:
        """使用 MusicFree Bilibili 插件搜索"""
        try:
            # 使用新的 MusicFree 插件搜索
            if hasattr(self, 'musicfree_bilibili') and self.musicfree_bilibili:
                return await self.musicfree_bilibili.search(query, 1, limit)
            else:
                logger.warning("MusicFree Bilibili 插件未加载")
                return []
        except Exception as e:
            logger.error(f"Bilibili search error: {e}")
            return []
    
    def _parse_duration(self, duration_str: str) -> int:
        """解析时长字符串为秒数"""
        try:
            parts = duration_str.split(':')
            if len(parts) == 2:
                minutes, seconds = int(parts[0]), int(parts[1])
                return minutes * 60 + seconds
            elif len(parts) == 3:
                hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
                return hours * 3600 + minutes * 60 + seconds
            else:
                return 0
        except:
            return 0
    
    def _clean_title(self, title: str) -> str:
        """清理标题中的HTML标签"""
        import re
        # 移除HTML标签
        clean_title = re.sub(r'<[^>]+>', '', title)
        # 移除多余的空格
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        return clean_title
    
    async def _search_netease(self, query: str, limit: int) -> List[Song]:
        """网易云音乐搜索"""
        try:
            # 真实的网易云音乐搜索实现
            import aiohttp
            
            # 网易云音乐 API (需要使用第三方API或自建服务)
            # 这里暂时返回空结果，用户可以自行实现真实的API调用
            logger.warning("网易云音乐搜索功能需要配置真实的API，当前返回空结果")
            return []
            
        except Exception as e:
            logger.error(f"Netease search error: {e}")
            return []
    
    async def _search_local(self, query: str, limit: int) -> List[Song]:
        """本地文件搜索"""
        try:
            results = []
            
            # 搜索本地音频文件
            audio_extensions = ['.mp3', '.m4a', '.opus', '.ogg', '.wav', '.flac', '.aac']
            
            # 扩展搜索目录
            music_dirs = [
                './music', './audio', './downloads', './Music', './Audio',
                os.path.expanduser('~/Music'), os.path.expanduser('~/Downloads'),
                './data/audio', './data/music'
            ]
            
            # 添加当前目录和插件目录
            current_dir = os.getcwd()
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            music_dirs.extend([
                os.path.join(current_dir, 'music'),
                os.path.join(plugin_dir, '..', 'data'),
                os.path.join(plugin_dir, '..', 'data', 'music')
            ])
            
            for music_dir in music_dirs:
                if os.path.exists(music_dir):
                    logger.info(f"搜索本地音乐目录: {music_dir}")
                    
                    for root, dirs, files in os.walk(music_dir):
                        for file in files:
                            if any(file.lower().endswith(ext) for ext in audio_extensions):
                                if query.lower() in file.lower():
                                    file_path = os.path.join(root, file)
                                    file_name = os.path.splitext(file)[0]
                                    
                                    # 尝试从文件名解析艺术家和标题
                                    artist, title = self._parse_filename(file_name)
                                    
                                    # 获取文件大小
                                    file_size = os.path.getsize(file_path)
                                    
                                    song = Song(
                                        id=f'local_{hash(file_path)}',
                                        title=title,
                                        artist=artist,
                                        album='本地音乐',
                                        duration=0,  # 可以用mutagen库解析音频文件获取时长
                                        platform='local',
                                        url=f'file://{os.path.abspath(file_path)}',
                                        extra={
                                            'file_path': os.path.abspath(file_path),
                                            'file_size': file_size,
                                            'file_ext': os.path.splitext(file)[1]
                                        }
                                    )
                                    results.append(song)
                                    
                                    logger.info(f"找到本地音乐: {title} - {artist}")
                                    
                                    if len(results) >= limit:
                                        return results
            
            if not results:
                logger.warning(f"未找到包含'{query}'的本地音乐文件")
                # 列出所有可用的音乐文件（调试用）
                self._list_available_music()
            
            return results
            
        except Exception as e:
            logger.error(f"Local search error: {e}")
            return []
    
    def _parse_filename(self, filename: str) -> tuple:
        """从文件名解析艺术家和标题"""
        # 尝试多种格式
        patterns = [
            r'(.+?)\s*-\s*(.+)',  # 艺术家 - 标题
            r'(.+?)\s*_\s*(.+)',  # 艺术家_标题
            r'(.+?)\s*\|\s*(.+)', # 艺术家|标题
        ]
        
        for pattern in patterns:
            match = re.match(pattern, filename)
            if match:
                return match.group(1).strip(), match.group(2).strip()
        
        # 如果没有匹配到，整个文件名作为标题
        return '未知艺术家', filename
    
    def _list_available_music(self):
        """列出所有可用的音乐文件（调试用）"""
        try:
            audio_extensions = ['.mp3', '.m4a', '.opus', '.ogg', '.wav', '.flac', '.aac']
            music_dirs = [
                './music', './audio', './downloads', './Music', './Audio',
                os.path.expanduser('~/Music'), os.path.expanduser('~/Downloads'),
                './data/audio', './data/music'
            ]
            
            logger.info("=== 可用音乐文件列表 ===")
            total_files = 0
            
            for music_dir in music_dirs:
                if os.path.exists(music_dir):
                    logger.info(f"目录: {music_dir}")
                    files_in_dir = []
                    
                    for root, dirs, files in os.walk(music_dir):
                        for file in files:
                            if any(file.lower().endswith(ext) for ext in audio_extensions):
                                files_in_dir.append(file)
                                total_files += 1
                    
                    if files_in_dir:
                        for file in files_in_dir[:10]:  # 只显示前10个
                            logger.info(f"  - {file}")
                        if len(files_in_dir) > 10:
                            logger.info(f"  ... 还有 {len(files_in_dir) - 10} 个文件")
                    else:
                        logger.info("  (空目录)")
            
            logger.info(f"总共找到 {total_files} 个音乐文件")
            logger.info("=== 列表结束 ===")
            
        except Exception as e:
            logger.error(f"列出音乐文件时出错: {e}")
    
    async def _search_musicfree(self, plugin: dict, query: str, limit: int) -> List[Song]:
        """MusicFree 插件搜索"""
        try:
            # 这里需要实现 JavaScript 执行环境
            # 暂时返回空结果
            logger.warning(f"MusicFree plugin search not implemented yet: {plugin['name']}")
            return []
            
        except Exception as e:
            logger.error(f"MusicFree plugin search error: {e}")
            return []
    
    def _rank_and_deduplicate(self, results: List[Song], query: str) -> List[Song]:
        """对搜索结果进行智能排序和去重"""
        if not results:
            return []
        
        # 去重：基于标题+艺术家
        unique_results = []
        seen = set()
        
        for song in results:
            key = f"{song.title.lower()}_{song.artist.lower()}"
            if key not in seen:
                seen.add(key)
                unique_results.append(song)
        
        # 智能排序
        def score_song(song: Song) -> int:
            score = 0
            title_lower = song.title.lower()
            artist_lower = song.artist.lower()
            query_lower = query.lower()
            
            # 标题完全匹配
            if title_lower == query_lower:
                score += 100
            # 标题包含查询词
            elif query_lower in title_lower:
                score += 50
            # 艺术家匹配
            if query_lower in artist_lower:
                score += 30
            
            # 音源优先级
            platform_scores = self.config.get('platform_priority', {
                'bilibili': 20,
                'netease': 15,
                'local': 10,
                'default': 5
            })
            score += platform_scores.get(song.platform, platform_scores.get('default', 5))
            
            return score
        
        return sorted(unique_results, key=score_song, reverse=True)
    
    async def get_play_url(self, song: Song) -> Optional[str]:
        """获取播放链接"""
        try:
            if song.platform == 'local':
                # 本地文件直接返回文件路径
                file_path = song.extra.get('file_path', '')
                if file_path and os.path.exists(file_path):
                    return f'file://{os.path.abspath(file_path)}'
            
            elif song.platform == 'bilibili':
                # Bilibili 需要解析视频链接获取音频流
                return await self._get_bilibili_audio_url(song)
            
            elif song.platform == 'netease':
                # 网易云音乐需要解析音频链接
                return await self._get_netease_audio_url(song)
            
            # 对于其他情况，返回原始URL
            return song.url
            
        except Exception as e:
            logger.error(f"Error getting play URL for {song.id}: {e}")
            return None
    
    async def _get_bilibili_audio_url(self, song: Song) -> Optional[str]:
        """获取 Bilibili 音频流链接"""
        try:
            # 这里应该使用 Bilibili API 或解析视频页面
            # 暂时返回原始链接，让 yt-dlp 处理
            return song.url
            
        except Exception as e:
            logger.error(f"Error getting Bilibili audio URL: {e}")
            return None
    
    async def _get_netease_audio_url(self, song: Song) -> Optional[str]:
        """获取网易云音乐音频流链接"""
        try:
            # 这里应该调用网易云音乐 API
            # 暂时返回原始链接
            return song.url
            
        except Exception as e:
            logger.error(f"Error getting Netease audio URL: {e}")
            return None
    
    def get_enabled_plugins(self) -> List[Dict[str, Any]]:
        """获取启用的插件列表"""
        enabled = []
        for name, plugin in self.plugins.items():
            if plugin.get('enabled', True):
                enabled.append({
                    'name': name,
                    'version': plugin.get('version', '1.0.0'),
                    'author': plugin.get('author', 'Unknown'),
                    'description': plugin.get('description', ''),
                    'type': plugin.get('type', 'unknown'),
                    'enabled': True
                })
        return enabled
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """启用插件"""
        if plugin_name in self.plugins:
            self.plugins[plugin_name]['enabled'] = True
            logger.info(f"Plugin enabled: {plugin_name}")
            return True
        return False
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """禁用插件"""
        if plugin_name in self.plugins:
            self.plugins[plugin_name]['enabled'] = False
            logger.info(f"Plugin disabled: {plugin_name}")
            return True
        return False
    
    def get_plugin_info(self, plugin_name: str) -> Optional[dict]:
        """获取插件信息"""
        return self.plugins.get(plugin_name)
    
    def get_available_plugins(self) -> List[Dict[str, Any]]:
        """获取可用插件列表"""
        plugin_list = []
        for plugin_id, plugin_info in self.plugins.items():
            plugin_list.append({
                'id': plugin_id,
                'name': plugin_info.get('name', plugin_id),
                'description': plugin_info.get('description', ''),
                'version': plugin_info.get('version', '1.0.0'),
                'author': plugin_info.get('author', 'Unknown'),
                'type': plugin_info.get('type', 'unknown'),
                'enabled': plugin_info.get('enabled', True)
            })
        return plugin_list
