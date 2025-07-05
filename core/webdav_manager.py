#!/usr/bin/env python3
"""
WebDAV 用户配置管理器
支持每个用户配置自己的 WebDAV 服务器来同步个人歌单
"""

import os
import json
import asyncio
import aiohttp
import aiofiles
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging
from urllib.parse import urljoin
import base64

logger = logging.getLogger(__name__)

class UserWebDAVConfig:
    """用户 WebDAV 配置类"""
    
    def __init__(self, user_id: str, config_data: Dict[str, Any]):
        self.user_id = user_id
        self.name = config_data.get('name', 'My WebDAV')
        self.url = config_data.get('url', '')
        self.username = config_data.get('username', '')
        self.password = config_data.get('password', '')
        self.playlists_path = config_data.get('playlists_path', '/playlists/')
        self.auto_sync = config_data.get('auto_sync', True)
        self.sync_interval = config_data.get('sync_interval', 3600)
        self.enabled = config_data.get('enabled', True)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'name': self.name,
            'url': self.url,
            'username': self.username,
            'password': self.password,
            'playlists_path': self.playlists_path,
            'auto_sync': self.auto_sync,
            'sync_interval': self.sync_interval,
            'enabled': self.enabled
        }
    
    def get_auth_header(self) -> Dict[str, str]:
        """获取认证头"""
        if self.username and self.password:
            credentials = f"{self.username}:{self.password}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            return {'Authorization': f'Basic {encoded_credentials}'}
        return {}

class WebDAVManager:
    """WebDAV 管理器"""
    
    def __init__(self, data_dir: str, config: Dict[str, Any]):
        self.data_dir = data_dir
        self.config = config
        self.user_configs_dir = os.path.join(data_dir, config.get('user_config_path', 'user_configs'))
        self.user_configs: Dict[str, UserWebDAVConfig] = {}
        
        # 确保用户配置目录存在
        Path(self.user_configs_dir).mkdir(parents=True, exist_ok=True)
        
        # 加载已有的用户配置
        self._load_user_configs()
    
    def _load_user_configs(self):
        """加载所有用户的 WebDAV 配置"""
        try:
            config_files = Path(self.user_configs_dir).glob("*.json")
            for config_file in config_files:
                user_id = config_file.stem
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    self.user_configs[user_id] = UserWebDAVConfig(user_id, config_data)
                    logger.info(f"Loaded WebDAV config for user {user_id}")
                except Exception as e:
                    logger.error(f"Failed to load WebDAV config for user {user_id}: {e}")
        except Exception as e:
            logger.error(f"Failed to load user WebDAV configs: {e}")
    
    def _save_user_config(self, user_id: str, config: UserWebDAVConfig):
        """保存用户的 WebDAV 配置"""
        try:
            config_file = os.path.join(self.user_configs_dir, f"{user_id}.json")
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Saved WebDAV config for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to save WebDAV config for user {user_id}: {e}")
            raise
    
    def set_user_webdav_config(self, user_id: str, url: str, username: str, password: str, 
                              playlists_path: str = '/playlists/', name: str = 'My WebDAV') -> bool:
        """设置用户的 WebDAV 配置"""
        try:
            config_data = {
                'name': name,
                'url': url.rstrip('/') + '/',
                'username': username,
                'password': password,
                'playlists_path': playlists_path,
                'auto_sync': True,
                'sync_interval': 3600,
                'enabled': True
            }
            
            config = UserWebDAVConfig(user_id, config_data)
            self.user_configs[user_id] = config
            self._save_user_config(user_id, config)
            
            logger.info(f"WebDAV config set for user {user_id}: {url}")
            return True
        except Exception as e:
            logger.error(f"Failed to set WebDAV config for user {user_id}: {e}")
            return False
    
    def get_user_webdav_config(self, user_id: str) -> Optional[UserWebDAVConfig]:
        """获取用户的 WebDAV 配置"""
        return self.user_configs.get(user_id)
    
    def remove_user_webdav_config(self, user_id: str) -> bool:
        """删除用户的 WebDAV 配置"""
        try:
            if user_id in self.user_configs:
                del self.user_configs[user_id]
            
            config_file = os.path.join(self.user_configs_dir, f"{user_id}.json")
            if os.path.exists(config_file):
                os.remove(config_file)
                
            logger.info(f"Removed WebDAV config for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove WebDAV config for user {user_id}: {e}")
            return False
    
    async def list_user_playlists(self, user_id: str) -> List[Dict[str, Any]]:
        """列出用户 WebDAV 上的歌单文件"""
        config = self.get_user_webdav_config(user_id)
        if not config or not config.enabled:
            return []
        
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.get('connection_timeout', 30))
            ) as session:
                url = urljoin(config.url, config.playlists_path)
                headers = config.get_auth_header()
                
                async with session.request('PROPFIND', url, headers=headers) as response:
                    if response.status == 200:
                        # 简单的文件列表解析 (需要根据实际 WebDAV 服务器响应格式调整)
                        content = await response.text()
                        # 这里需要解析 WebDAV PROPFIND 响应
                        # 为简化起见，假设返回的是包含文件信息的 XML
                        return await self._parse_webdav_listing(content, config)
                    else:
                        logger.error(f"WebDAV listing failed for user {user_id}: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Failed to list WebDAV playlists for user {user_id}: {e}")
            return []
    
    async def _parse_webdav_listing(self, content: str, config: UserWebDAVConfig) -> List[Dict[str, Any]]:
        """解析 WebDAV 目录列表响应"""
        # 这里需要实现 WebDAV XML 响应的解析
        # 为简化起见，返回空列表
        # 实际实现需要使用 xml.etree.ElementTree 或其他 XML 解析库
        return []
    
    async def download_user_playlist(self, user_id: str, playlist_path: str) -> Optional[str]:
        """从用户的 WebDAV 下载歌单文件"""
        config = self.get_user_webdav_config(user_id)
        if not config or not config.enabled:
            return None
        
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.get('read_timeout', 60))
            ) as session:
                url = urljoin(config.url, playlist_path)
                headers = config.get_auth_header()
                
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"Downloaded playlist {playlist_path} for user {user_id}")
                        return content
                    else:
                        logger.error(f"Failed to download playlist {playlist_path} for user {user_id}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Failed to download playlist {playlist_path} for user {user_id}: {e}")
            return None
    
    async def test_user_connection(self, user_id: str) -> bool:
        """测试用户的 WebDAV 连接"""
        config = self.get_user_webdav_config(user_id)
        if not config:
            return False
        
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.get('connection_timeout', 30))
            ) as session:
                headers = config.get_auth_header()
                
                async with session.request('PROPFIND', config.url, headers=headers) as response:
                    success = response.status in [200, 207]  # 200 OK or 207 Multi-Status
                    if success:
                        logger.info(f"WebDAV connection test successful for user {user_id}")
                    else:
                        logger.warning(f"WebDAV connection test failed for user {user_id}: {response.status}")
                    return success
        except Exception as e:
            logger.error(f"WebDAV connection test failed for user {user_id}: {e}")
            return False
    
    def get_user_config_status(self, user_id: str) -> Dict[str, Any]:
        """获取用户 WebDAV 配置状态"""
        config = self.get_user_webdav_config(user_id)
        if not config:
            return {
                'configured': False,
                'enabled': False,
                'name': None,
                'url': None
            }
        
        return {
            'configured': True,
            'enabled': config.enabled,
            'name': config.name,
            'url': config.url,
            'playlists_path': config.playlists_path,
            'auto_sync': config.auto_sync,
            'sync_interval': config.sync_interval
        }
