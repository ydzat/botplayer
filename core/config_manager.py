"""
配置管理器
负责加载、验证和管理插件配置
"""
import os
import yaml
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.default_config = self._get_default_config()
        
        # 加载配置
        self.load_config()
        
        # 验证配置
        self.validate_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'botplayer': {
                'plugins': {
                    'enabled': ['bilibili', 'netease', 'local'],
                    'plugin_dir': './data/plugins',
                    'update_interval': 86400
                },
                'cache': {
                    'max_size': 10737418240,  # 10GB
                    'cache_dir': './data/audio_cache',
                    'cleanup_threshold': 0.9,
                    'min_access_interval': 3600,
                    'max_concurrent_downloads': 3,
                    'download_timeout': 300
                },
                'playback': {
                    'default_volume': 0.5,
                    'auto_play': True,
                    'timeout': 30,
                    'buffer_size': 1024,
                    'audio_format': 'opus',
                    'audio_bitrate': '128k'
                },
                'discord': {
                    'max_queue_size': 100,
                    'idle_timeout': 300,
                    'reconnect_attempts': 3,
                    'command_prefix': '!'
                },
                'storage': {
                    'database_path': 'data/botplayer.db',
                    'audio_cache_path': 'data/audio_cache',
                    'plugins_path': 'data/plugins',
                    'playlists_path': 'data/playlists'
                },
                'playlist_import': {
                    'allowed_domains': [
                        'github.com',
                        'gist.githubusercontent.com',
                        'gitee.com',
                        'music.163.com',
                        'y.qq.com'
                    ],
                    'max_file_size': 5242880,
                    'timeout': 30,
                    'max_songs_per_playlist': 1000
                },
                'plugin_execution': {
                    'js_timeout': 10,
                    'max_retries': 3,
                    'node_path': 'node'
                },
                'ffmpeg': {
                    'path': 'ffmpeg',
                    'audio_codec': 'libopus',
                    'video_codec': 'none',
                    'extra_args': ['-loglevel', 'error']
                },
                'logging': {
                    'level': 'INFO',
                    'file': 'data/botplayer.log',
                    'max_size': 10485760,
                    'backup_count': 5
                },
                'search': {
                    'max_results': 20,
                    'timeout': 10,
                    'result_ranking': {
                        'title_exact_match': 100,
                        'title_contains': 50,
                        'artist_match': 30,
                        'platform_priority': {
                            'bilibili': 20,
                            'netease': 15,
                            'local': 10,
                            'default': 5
                        }
                    }
                }
            }
        }
    
    def load_config(self) -> None:
        """加载配置文件"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_config = yaml.safe_load(f)
                    if loaded_config:
                        self.config = self._merge_config(self.default_config, loaded_config)
                    else:
                        self.config = self.default_config.copy()
                        logger.warning("配置文件为空，使用默认配置")
            else:
                self.config = self.default_config.copy()
                logger.info("配置文件不存在，使用默认配置")
                # 创建默认配置文件
                self.save_config()
                
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            self.config = self.default_config.copy()
    
    def _merge_config(self, default: Dict[str, Any], loaded: Dict[str, Any]) -> Dict[str, Any]:
        """合并配置，loaded覆盖default"""
        result = default.copy()
        
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def validate_config(self) -> None:
        """验证配置"""
        try:
            botplayer_config = self.config.get('botplayer', {})
            
            # 验证缓存大小
            cache_config = botplayer_config.get('cache', {})
            max_size = cache_config.get('max_size', 0)
            if max_size <= 0:
                logger.warning("缓存大小配置无效，使用默认值")
                cache_config['max_size'] = self.default_config['botplayer']['cache']['max_size']
            
            # 验证音频格式
            playback_config = botplayer_config.get('playback', {})
            audio_format = playback_config.get('audio_format', '')
            if audio_format not in ['opus', 'mp3', 'aac', 'ogg']:
                logger.warning(f"不支持的音频格式: {audio_format}，使用默认格式")
                playback_config['audio_format'] = 'opus'
            
            # 验证音量设置
            volume = playback_config.get('default_volume', 0.5)
            if not 0 <= volume <= 1:
                logger.warning("音量设置超出范围，使用默认值")
                playback_config['default_volume'] = 0.5
            
            # 验证允许的域名
            playlist_config = botplayer_config.get('playlist_import', {})
            allowed_domains = playlist_config.get('allowed_domains', [])
            if not isinstance(allowed_domains, list):
                logger.warning("允许域名配置格式错误，使用默认值")
                playlist_config['allowed_domains'] = self.default_config['botplayer']['playlist_import']['allowed_domains']
            
            logger.info("配置验证完成")
            
        except Exception as e:
            logger.error(f"配置验证失败: {e}")
    
    def save_config(self) -> None:
        """保存配置到文件"""
        try:
            # 确保配置目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            logger.info(f"配置已保存到: {self.config_path}")
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """获取配置值，支持点号分隔的路径"""
        try:
            keys = key_path.split('.')
            value = self.config
            
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default
            
            return value
            
        except Exception as e:
            logger.warning(f"获取配置 {key_path} 失败: {e}")
            return default
    
    def set(self, key_path: str, value: Any) -> None:
        """设置配置值"""
        try:
            keys = key_path.split('.')
            config = self.config
            
            # 导航到最后一级的父配置
            for key in keys[:-1]:
                if key not in config:
                    config[key] = {}
                config = config[key]
            
            # 设置值
            config[keys[-1]] = value
            
            logger.debug(f"配置 {key_path} 已设置为: {value}")
            
        except Exception as e:
            logger.error(f"设置配置 {key_path} 失败: {e}")
    
    def get_botplayer_config(self) -> Dict[str, Any]:
        """获取 botplayer 相关的所有配置"""
        return self.config.get('botplayer', {})
    
    def get_cache_config(self) -> Dict[str, Any]:
        """获取缓存配置"""
        return self.get('botplayer.cache', {})
    
    def get_plugin_config(self) -> Dict[str, Any]:
        """获取插件配置"""
        return self.get('botplayer.plugins', {})
    
    def get_playback_config(self) -> Dict[str, Any]:
        """获取播放配置"""
        return self.get('botplayer.playback', {})
    
    def get_discord_config(self) -> Dict[str, Any]:
        """获取Discord配置"""
        return self.get('botplayer.discord', {})
    
    def get_storage_config(self) -> Dict[str, Any]:
        """获取存储配置"""
        return self.get('botplayer.storage', {})
    
    def get_enabled_plugins(self) -> List[str]:
        """获取启用的插件列表"""
        return self.get('botplayer.plugins.enabled', [])
    
    def is_plugin_enabled(self, plugin_name: str) -> bool:
        """检查插件是否启用"""
        enabled_plugins = self.get_enabled_plugins()
        return plugin_name in enabled_plugins
    
    def get_cache_max_size(self) -> int:
        """获取缓存最大大小"""
        return self.get('botplayer.cache.max_size', 10737418240)
    
    def get_max_queue_size(self) -> int:
        """获取队列最大大小"""
        return self.get('botplayer.discord.max_queue_size', 100)
    
    def get_audio_format(self) -> str:
        """获取音频格式"""
        return self.get('botplayer.playback.audio_format', 'opus')
    
    def get_audio_bitrate(self) -> str:
        """获取音频比特率"""
        return self.get('botplayer.playback.audio_bitrate', '128k')
    
    def reload_config(self) -> None:
        """重新加载配置"""
        logger.info("重新加载配置...")
        self.load_config()
        self.validate_config()
    
    def reset_to_default(self) -> None:
        """重置为默认配置"""
        logger.info("重置为默认配置")
        self.config = self.default_config.copy()
        self.save_config()
