"""
用户 WebDAV 配置管理模块
负责用户注册和 WebDAV 配置管理
"""

import os
import json
import yaml
import asyncio
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
import requests
from requests.auth import HTTPBasicAuth
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, quote


@dataclass
class UserInfo:
    """用户信息"""
    user_id: str          # Discord 用户 ID
    username: str         # 用户自定义名称
    discord_name: str     # Discord 显示名称
    registered_at: str    # 注册时间
    last_active: str      # 最后活跃时间
    webdav_enabled: bool = False  # WebDAV 是否启用（由管理员设置）


@dataclass
class WebDAVConfig:
    """WebDAV 配置"""
    enabled: bool = False
    server_url: str = ""
    username: str = ""
    password: str = ""
    playlist_path: str = ""  # 歌单文件在 WebDAV 中的路径
    auto_sync: bool = False
    last_sync: str = ""


class UserWebDAVManager:
    """用户 WebDAV 配置管理器"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.user_configs_dir = os.path.join(data_dir, "user_configs")
        self.users_file = os.path.join(self.user_configs_dir, "users.json")
        self.webdav_configs_file = os.path.join(self.user_configs_dir, "webdav_configs.yaml")
        
        # 确保目录存在
        os.makedirs(self.user_configs_dir, exist_ok=True)
        
        # 初始化配置文件
        self._init_config_files()
    
    def _init_config_files(self):
        """初始化配置文件"""
        # 初始化用户文件
        if not os.path.exists(self.users_file):
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2, ensure_ascii=False)
        
        # 初始化 WebDAV 配置文件
        if not os.path.exists(self.webdav_configs_file):
            with open(self.webdav_configs_file, 'w', encoding='utf-8') as f:
                yaml.dump({
                    # 示例配置
                    "_example_user": {
                        "enabled": False,
                        "server_url": "https://your-webdav-server.com/remote.php/dav/files/username/",
                        "username": "webdav_username",
                        "password": "webdav_password",
                        "playlist_path": "Music/Playlists/",
                        "auto_sync": True,
                        "last_sync": ""
                    },
                    "_注意": "这是示例配置，实际使用时请删除此条目。用户名应该使用注册时的自定义名称"
                }, f, default_flow_style=False, allow_unicode=True)
    
    def register_user(self, user_id: str, username: str, discord_name: str) -> Dict:
        """注册用户"""
        try:
            # 加载现有用户
            users = self._load_users()
            
            # 检查用户名是否已存在
            for uid, user_info in users.items():
                if user_info['username'] == username:
                    return {
                        'success': False,
                        'message': f'用户名 "{username}" 已被使用，请选择其他名称'
                    }
            
            # 检查用户是否已注册
            if user_id in users:
                return {
                    'success': False,
                    'message': f'您已经注册过了，当前用户名: {users[user_id]["username"]}'
                }
            
            # 创建新用户
            now = datetime.now().isoformat()
            user_info = UserInfo(
                user_id=user_id,
                username=username,
                discord_name=discord_name,
                registered_at=now,
                last_active=now
            )
            
            # 保存用户信息
            users[user_id] = asdict(user_info)
            self._save_users(users)
            
            # 在 WebDAV 配置文件中创建占位符
            self._create_webdav_placeholder(username)
            
            return {
                'success': True,
                'message': f'注册成功！用户名: {username}\n'
                          f'管理员可以在配置文件中为您设置 WebDAV 访问权限。',
                'user_info': user_info
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'注册失败: {str(e)}'
            }
    
    def _create_webdav_placeholder(self, username: str):
        """为新用户在 WebDAV 配置中创建占位符"""
        try:
            with open(self.webdav_configs_file, 'r', encoding='utf-8') as f:
                configs = yaml.safe_load(f) or {}
            
            if username not in configs:
                configs[username] = {
                    "enabled": False,
                    "server_url": "",
                    "username": "",
                    "password": "",
                    "playlist_path": "",
                    "auto_sync": False,
                    "last_sync": "",
                    "_note": f"管理员请为用户 {username} 配置 WebDAV 信息"
                }
                
                with open(self.webdav_configs_file, 'w', encoding='utf-8') as f:
                    yaml.dump(configs, f, default_flow_style=False, allow_unicode=True)
        
        except Exception as e:
            print(f"创建 WebDAV 占位符失败: {e}")
    
    def get_user_info(self, user_id: str) -> Optional[UserInfo]:
        """获取用户信息"""
        users = self._load_users()
        if user_id in users:
            user_data = users[user_id]
            return UserInfo(**user_data)
        return None
    
    def get_user_by_username(self, username: str) -> Optional[UserInfo]:
        """通过用户名获取用户信息"""
        users = self._load_users()
        for user_data in users.values():
            if user_data['username'] == username:
                return UserInfo(**user_data)
        return None
    
    def get_webdav_config(self, user_id: str) -> Optional[WebDAVConfig]:
        """获取用户的 WebDAV 配置"""
        user_info = self.get_user_info(user_id)
        if not user_info:
            return None
        
        try:
            with open(self.webdav_configs_file, 'r', encoding='utf-8') as f:
                configs = yaml.safe_load(f) or {}
            
            username = user_info.username
            if username in configs:
                config_data = configs[username]
                
                # 过滤掉不属于 WebDAVConfig 的字段
                valid_fields = {
                    'enabled', 'server_url', 'username', 'password', 
                    'playlist_path', 'auto_sync', 'last_sync'
                }
                filtered_config = {k: v for k, v in config_data.items() if k in valid_fields}
                
                return WebDAVConfig(**filtered_config)
            
        except Exception as e:
            print(f"读取 WebDAV 配置失败: {e}")
        
        return None
    
    def update_last_active(self, user_id: str):
        """更新用户最后活跃时间"""
        try:
            users = self._load_users()
            if user_id in users:
                users[user_id]['last_active'] = datetime.now().isoformat()
                self._save_users(users)
        except Exception as e:
            print(f"更新用户活跃时间失败: {e}")
    
    def list_all_users(self) -> List[UserInfo]:
        """列出所有用户（管理员功能）"""
        users = self._load_users()
        return [UserInfo(**user_data) for user_data in users.values()]
    
    def get_webdav_status(self, user_id: str) -> Dict:
        """获取用户 WebDAV 状态"""
        user_info = self.get_user_info(user_id)
        if not user_info:
            return {
                'registered': False,
                'message': '您尚未注册，请使用 !reg name <用户名> 进行注册'
            }
        
        webdav_config = self.get_webdav_config(user_id)
        if not webdav_config or not webdav_config.enabled:
            return {
                'registered': True,
                'webdav_enabled': False,
                'username': user_info.username,
                'message': f'用户名: {user_info.username}\nWebDAV 未启用，请联系管理员配置'
            }
        
        return {
            'registered': True,
            'webdav_enabled': True,
            'username': user_info.username,
            'auto_sync': webdav_config.auto_sync,
            'last_sync': webdav_config.last_sync,
            'message': f'用户名: {user_info.username}\nWebDAV 已启用'
        }
    
    def _load_users(self) -> Dict:
        """加载用户数据"""
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def _save_users(self, users: Dict):
        """保存用户数据"""
        with open(self.users_file, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
    
    def _load_webdav_configs(self) -> Dict:
        """加载 WebDAV 配置"""
        try:
            with open(self.webdav_configs_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except:
            return {}
    
    def _save_webdav_configs(self, configs: Dict):
        """保存 WebDAV 配置"""
        with open(self.webdav_configs_file, 'w', encoding='utf-8') as f:
            yaml.dump(configs, f, default_flow_style=False, allow_unicode=True, indent=2)

    def sync_webdav_playlists(self, user_id: str) -> Dict:
        """同步用户的 WebDAV 歌单"""
        try:
            user_info = self.get_user_info(user_id)
            if not user_info:
                return {"success": False, "error": "用户未注册"}
            
            webdav_config = self.get_webdav_config(user_id)
            if not webdav_config or not webdav_config.enabled:
                return {"success": False, "error": "WebDAV 未启用"}
            
            # 连接到 WebDAV 服务器
            session = requests.Session()
            session.auth = HTTPBasicAuth(webdav_config.username, webdav_config.password)
            session.headers.update({
                'User-Agent': 'BotPlayer/1.0',
                'Content-Type': 'application/xml; charset=utf-8'
            })
            
            # 获取歌单目录列表
            playlist_files = self._list_webdav_files(session, webdav_config)
            if not playlist_files:
                return {"success": False, "error": "未找到歌单文件"}
            
            # 下载并处理歌单
            downloaded_count = 0
            errors = []
            
            for file_info in playlist_files:
                try:
                    content = self._download_webdav_file(session, webdav_config, file_info['path'])
                    if content:
                        # 保存歌单文件到本地
                        local_path = self._save_playlist_file(user_info.username, file_info['name'], content)
                        if local_path:
                            downloaded_count += 1
                except Exception as e:
                    errors.append(f"下载 {file_info['name']} 失败: {str(e)}")
            
            # 更新同步时间
            self._update_sync_time(user_id)
            
            result = {
                "success": True,
                "downloaded_count": downloaded_count,
                "total_files": len(playlist_files),
                "message": f"成功同步 {downloaded_count}/{len(playlist_files)} 个歌单文件"
            }
            
            if errors:
                result["errors"] = errors
                result["message"] += f"，{len(errors)} 个文件出错"
            
            return result
            
        except Exception as e:
            return {"success": False, "error": f"同步失败: {str(e)}"}
    
    def _list_webdav_files(self, session: requests.Session, config: 'WebDAVConfig') -> List[Dict]:
        """列出 WebDAV 目录中的歌单文件"""
        try:
            url = urljoin(config.server_url, config.playlist_path)
            
            # PROPFIND 请求获取目录列表
            propfind_xml = '''<?xml version="1.0" encoding="utf-8" ?>
            <d:propfind xmlns:d="DAV:">
                <d:prop>
                    <d:displayname/>
                    <d:getcontentlength/>
                    <d:getlastmodified/>
                    <d:resourcetype/>
                </d:prop>
            </d:propfind>'''
            
            response = session.request(
                'PROPFIND', 
                url,
                data=propfind_xml,
                headers={'Depth': '1'},
                timeout=30
            )
            
            if response.status_code != 207:  # Multi-Status
                return []
            
            # 解析 WebDAV 响应
            files = []
            root = ET.fromstring(response.content)
            
            for response_elem in root.findall('.//{DAV:}response'):
                href_elem = response_elem.find('.//{DAV:}href')
                displayname_elem = response_elem.find('.//{DAV:}displayname')
                resourcetype_elem = response_elem.find('.//{DAV:}resourcetype')
                
                if href_elem is not None and displayname_elem is not None:
                    # 跳过目录
                    if resourcetype_elem is not None and resourcetype_elem.find('.//{DAV:}collection') is not None:
                        continue
                    
                    filename = displayname_elem.text
                    if filename and self._is_supported_playlist_file(filename):
                        files.append({
                            'name': filename,
                            'path': href_elem.text
                        })
            
            return files
            
        except Exception as e:
            print(f"列出 WebDAV 文件失败: {e}")
            return []
    
    def _download_webdav_file(self, session: requests.Session, config: 'WebDAVConfig', file_path: str) -> Optional[bytes]:
        """下载 WebDAV 文件"""
        try:
            # 构建完整的文件 URL - 修复 URL 重复问题
            if file_path.startswith('http'):
                url = file_path
            else:
                # 确保正确拼接 URL，避免重复路径
                base_url = config.server_url.rstrip('/')
                clean_path = file_path.lstrip('/')
                
                # 如果 file_path 已经包含完整路径，直接使用 base domain
                if clean_path.startswith('remote.php/dav/files/'):
                    # 提取域名部分
                    from urllib.parse import urlparse
                    parsed = urlparse(base_url)
                    url = f"{parsed.scheme}://{parsed.netloc}/{clean_path}"
                else:
                    # 正常拼接
                    url = f"{base_url}/{clean_path}"
            
            print(f"正在下载: {url}")
            response = session.get(url, timeout=60)
            response.raise_for_status()
            
            # 检查文件大小限制（10MB）
            if len(response.content) > 10 * 1024 * 1024:
                print(f"文件 {file_path} 太大，跳过下载")
                return None
            
            return response.content
            
        except Exception as e:
            print(f"下载文件 {file_path} 失败: {e}")
            return None
    
    def _save_playlist_file(self, username: str, filename: str, content: bytes) -> Optional[str]:
        """保存歌单文件到本地"""
        try:
            # 创建用户歌单目录
            playlist_dir = os.path.join(self.data_dir, 'user_playlists', username)
            os.makedirs(playlist_dir, exist_ok=True)
            
            # 保存文件
            file_path = os.path.join(playlist_dir, filename)
            with open(file_path, 'wb') as f:
                f.write(content)
            
            return file_path
            
        except Exception as e:
            print(f"保存文件 {filename} 失败: {e}")
            return None
    
    def _is_supported_playlist_file(self, filename: str) -> bool:
        """检查是否是支持的歌单文件格式"""
        supported_extensions = ['.json', '.m3u', '.m3u8', '.pls']
        return any(filename.lower().endswith(ext) for ext in supported_extensions)
    
    def _update_sync_time(self, user_id: str):
        """更新用户的同步时间"""
        try:
            user_info = self.get_user_info(user_id)
            if user_info:
                # 更新用户活跃时间
                users = self._load_users()
                if user_id in users:
                    users[user_id]['last_active'] = datetime.now().isoformat()
                    self._save_users(users)
                
                # 更新 WebDAV 同步时间
                configs = self._load_webdav_configs()
                if user_info.username in configs:
                    configs[user_info.username]['last_sync'] = datetime.now().isoformat()
                    self._save_webdav_configs(configs)
                    
        except Exception as e:
            print(f"更新同步时间失败: {e}")

    def list_user_playlists(self, user_id: str) -> List[Dict]:
        """列出用户的本地歌单文件"""
        try:
            user_info = self.get_user_info(user_id)
            if not user_info:
                return []
            
            playlist_dir = os.path.join(self.data_dir, 'user_playlists', user_info.username)
            if not os.path.exists(playlist_dir):
                return []
            
            playlists = []
            for filename in os.listdir(playlist_dir):
                if self._is_supported_playlist_file(filename):
                    file_path = os.path.join(playlist_dir, filename)
                    file_stats = os.stat(file_path)
                    
                    playlists.append({
                        'name': filename,
                        'path': file_path,
                        'size': file_stats.st_size,
                        'modified': datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    })
            
            return sorted(playlists, key=lambda x: x['modified'], reverse=True)
            
        except Exception as e:
            print(f"列出用户歌单失败: {e}")
            return []
