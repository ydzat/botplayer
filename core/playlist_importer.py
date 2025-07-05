"""
歌单导入器
支持从URL导入JSON格式歌单，包括MusicFreeBackup.json等格式
"""
import asyncio
import aiohttp
import json
import logging
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse
from .models import Song, Playlist
import urllib.parse
from pathlib import Path

logger = logging.getLogger(__name__)


class PlaylistImporter:
    """歌单导入器"""
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        
        # 安全域名白名单
        if config_manager:
            self.allowed_domains = set(config_manager.get('botplayer.playlist_import.allowed_domains', [
                'github.com',
                'raw.githubusercontent.com',
                'gist.github.com',
                'gist.githubusercontent.com',
                'gitlab.com',
                'cdn.jsdelivr.net',
                'unpkg.com'
            ]))
            self.max_file_size = config_manager.get('botplayer.playlist_import.max_file_size', 5242880)
            self.timeout = config_manager.get('botplayer.playlist_import.timeout', 30)
        else:
            self.allowed_domains = {
                'github.com',
                'raw.githubusercontent.com',
                'gist.github.com',
                'gist.githubusercontent.com',
                'gitlab.com',
                'cdn.jsdelivr.net',
                'unpkg.com'
            }
            self.max_file_size = 5242880  # 5MB
            self.timeout = 30
        
        # 支持的文件格式
        self.supported_formats = {
            'musicfree_backup',  # MusicFreeBackup.json
            'simple_playlist',   # 简单歌单格式
            'netease_playlist',  # 网易云歌单
            'spotify_playlist'   # Spotify 歌单（简化）
        }
    
    async def import_from_url(self, url: str) -> Optional[Playlist]:
        """从URL导入歌单"""
        try:
            # 验证URL安全性
            if not self._is_safe_url(url):
                logger.warning(f"Unsafe URL rejected: {url}")
                return None
            
            # 下载JSON数据
            json_data = await self._download_json(url)
            if not json_data:
                return None
            
            # 解析歌单
            return self._parse_playlist(json_data, url)
            
        except Exception as e:
            logger.error(f"Error importing playlist from URL {url}: {e}")
            return None
    
    async def import_from_file(self, file_path: str) -> Optional[Playlist]:
        """从本地文件导入歌单"""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            return self._parse_playlist(json_data, str(file_path))
            
        except Exception as e:
            logger.error(f"Error importing playlist from file {file_path}: {e}")
            return None
    
    async def import_from_musicfree_backup(self, backup_file: str) -> List[Song]:
        """从MusicFree备份文件导入歌单"""
        try:
            if backup_file.startswith(('http://', 'https://')):
                json_data = await self._download_json(backup_file)
            else:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
            if not json_data:
                return []
            playlist = self._parse_musicfree_backup(json_data, backup_file)
            return playlist.songs if playlist else []
        except Exception as e:
            logger.error(f"MusicFree备份导入失败: {e}")
            return []
    
    def _is_safe_url(self, url: str) -> bool:
        """检查URL是否安全"""
        try:
            parsed = urlparse(url)
            
            # 必须是HTTPS
            if parsed.scheme != 'https':
                return False
            
            # 检查域名白名单
            hostname = parsed.hostname
            if not hostname:
                return False
            
            # 检查是否在白名单中
            for allowed_domain in self.allowed_domains:
                if hostname == allowed_domain or hostname.endswith('.' + allowed_domain):
                    return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking URL safety: {e}")
            return False
    
    async def _download_json(self, url: str) -> Optional[Dict[str, Any]]:
        """下载JSON数据"""
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {
                    'User-Agent': 'BotPlayer/1.0',
                    'Accept': 'application/json, text/plain, */*'
                }
                
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"HTTP {response.status} when downloading {url}")
                        return None
                    
                    # 检查内容大小（最大5MB）
                    content_length = response.headers.get('content-length')
                    if content_length and int(content_length) > 5 * 1024 * 1024:
                        logger.error(f"File too large: {content_length} bytes")
                        return None
                    
                    # 读取内容
                    content = await response.text()
                    
                    # 解析JSON
                    return json.loads(content)
                    
        except asyncio.TimeoutError:
            logger.error(f"Timeout downloading {url}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from {url}: {e}")
        except Exception as e:
            logger.error(f"Error downloading JSON from {url}: {e}")
        
        return None
    
    def _parse_playlist(self, json_data: Dict[str, Any], source: str) -> Optional[Playlist]:
        """解析歌单数据"""
        try:
            # 检测歌单格式
            playlist_format = self._detect_format(json_data)
            
            if playlist_format == 'musicfree_backup':
                return self._parse_musicfree_backup(json_data, source)
            elif playlist_format == 'simple_playlist':
                return self._parse_simple_playlist(json_data, source)
            elif playlist_format == 'netease_playlist':
                return self._parse_netease_playlist(json_data, source)
            elif playlist_format == 'spotify_playlist':
                return self._parse_spotify_playlist(json_data, source)
            else:
                logger.error(f"Unknown playlist format from {source}")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing playlist from {source}: {e}")
            return None
    
    def _detect_format(self, json_data: Dict[str, Any]) -> Optional[str]:
        """检测歌单格式"""
        try:
            # MusicFree Backup 格式
            if 'musicSheets' in json_data:
                return 'musicfree_backup'
            
            # 网易云歌单格式
            if 'playlist' in json_data and 'tracks' in json_data.get('playlist', {}):
                return 'netease_playlist'
            
            # Spotify 歌单格式
            if 'tracks' in json_data and 'items' in json_data.get('tracks', {}):
                return 'spotify_playlist'
            
            # 简单歌单格式
            if 'name' in json_data and 'songs' in json_data:
                return 'simple_playlist'
            
            # 默认尝试简单格式
            return 'simple_playlist'
            
        except Exception as e:
            logger.warning(f"Error detecting playlist format: {e}")
            return None
    
    def _parse_musicfree_backup(self, json_data: Dict[str, Any], source: str) -> Optional[Playlist]:
        """解析 MusicFree Backup 格式"""
        try:
            music_sheets = json_data.get('musicSheets', [])
            
            if not music_sheets:
                logger.warning(f"No musicSheets found in {source}")
                return None
            
            # 取第一个歌单（或可以让用户选择）
            sheet = music_sheets[0]
            
            playlist = Playlist(
                id=sheet.get('id', ''),
                name=sheet.get('platform', 'Imported Playlist'),
                description=f"Imported from {source}",
                creator="BotPlayer"
            )
            
            # 解析歌曲列表
            music_list = sheet.get('musicList', [])
            for item in music_list:
                song = self._parse_musicfree_song(item)
                if song:
                    playlist.add_song(song)
            
            logger.info(f"Imported MusicFree playlist with {len(playlist.songs)} songs")
            return playlist
            
        except Exception as e:
            logger.error(f"Error parsing MusicFree backup: {e}")
            return None
    
    def _parse_musicfree_song(self, item: Dict[str, Any]) -> Optional[Song]:
        """解析 MusicFree 歌曲格式"""
        try:
            # 构建播放URL
            url = ""
            if item.get('platform') == 'bilibili' and item.get('bvid'):
                url = f"https://www.bilibili.com/video/{item['bvid']}"
            elif item.get('url'):
                url = item['url']
            
            song = Song(
                id=item.get('id', ''),
                title=item.get('title', ''),
                artist=item.get('artist', ''),
                album=item.get('album', ''),
                duration=item.get('duration', 0),
                platform=item.get('platform', ''),
                artwork=item.get('artwork', ''),
                url=url,
                tags=item.get('tags', []),
                date=item.get('date', ''),
                extra={
                    'aid': item.get('aid'),
                    'bvid': item.get('bvid'),
                    'original_item': item
                }
            )
            
            return song
            
        except Exception as e:
            logger.warning(f"Error parsing MusicFree song: {e}")
            return None
    
    def _parse_simple_playlist(self, json_data: Dict[str, Any], source: str) -> Optional[Playlist]:
        """解析简单歌单格式"""
        try:
            playlist = Playlist(
                id=json_data.get('id', ''),
                name=json_data.get('name', 'Imported Playlist'),
                description=json_data.get('description', f"Imported from {source}"),
                creator=json_data.get('creator', 'BotPlayer'),
                cover=json_data.get('cover', ''),
                tags=json_data.get('tags', [])
            )
            
            # 解析歌曲列表
            songs = json_data.get('songs', [])
            for song_data in songs:
                song = Song.from_dict(song_data)
                playlist.add_song(song)
            
            logger.info(f"Imported simple playlist with {len(playlist.songs)} songs")
            return playlist
            
        except Exception as e:
            logger.error(f"Error parsing simple playlist: {e}")
            return None
    
    def _parse_netease_playlist(self, json_data: Dict[str, Any], source: str) -> Optional[Playlist]:
        """解析网易云歌单格式"""
        try:
            playlist_data = json_data.get('playlist', {})
            
            playlist = Playlist(
                id=str(playlist_data.get('id', '')),
                name=playlist_data.get('name', 'Netease Playlist'),
                description=playlist_data.get('description', f"Imported from {source}"),
                creator=playlist_data.get('creator', {}).get('nickname', 'Unknown'),
                cover=playlist_data.get('coverImgUrl', ''),
                tags=playlist_data.get('tags', [])
            )
            
            # 解析歌曲列表
            tracks = playlist_data.get('tracks', [])
            for track in tracks:
                song = self._parse_netease_track(track)
                if song:
                    playlist.add_song(song)
            
            logger.info(f"Imported Netease playlist with {len(playlist.songs)} songs")
            return playlist
            
        except Exception as e:
            logger.error(f"Error parsing Netease playlist: {e}")
            return None
    
    def _parse_netease_track(self, track: Dict[str, Any]) -> Optional[Song]:
        """解析网易云歌曲格式"""
        try:
            # 获取艺术家名称
            artists = track.get('artists', [])
            artist_names = [artist.get('name', '') for artist in artists]
            artist = ', '.join(artist_names) if artist_names else 'Unknown'
            
            # 获取专辑信息
            album_data = track.get('album', {})
            album = album_data.get('name', '')
            
            song = Song(
                id=str(track.get('id', '')),
                title=track.get('name', ''),
                artist=artist,
                album=album,
                duration=track.get('duration', 0) // 1000,  # 毫秒转秒
                platform='netease',
                artwork=album_data.get('picUrl', ''),
                url=f"http://music.163.com/song/{track.get('id', '')}",
                extra={
                    'netease_id': track.get('id'),
                    'original_track': track
                }
            )
            
            return song
            
        except Exception as e:
            logger.warning(f"Error parsing Netease track: {e}")
            return None
    
    def _parse_spotify_playlist(self, json_data: Dict[str, Any], source: str) -> Optional[Playlist]:
        """解析 Spotify 歌单格式（简化）"""
        try:
            playlist = Playlist(
                id=json_data.get('id', ''),
                name=json_data.get('name', 'Spotify Playlist'),
                description=json_data.get('description', f"Imported from {source}"),
                creator=json_data.get('owner', {}).get('display_name', 'Unknown'),
                cover='',
                tags=[]
            )
            
            # 获取封面图片
            images = json_data.get('images', [])
            if images:
                playlist.cover = images[0].get('url', '')
            
            # 解析歌曲列表
            tracks = json_data.get('tracks', {}).get('items', [])
            for item in tracks:
                track = item.get('track', {})
                song = self._parse_spotify_track(track)
                if song:
                    playlist.add_song(song)
            
            logger.info(f"Imported Spotify playlist with {len(playlist.songs)} songs")
            return playlist
            
        except Exception as e:
            logger.error(f"Error parsing Spotify playlist: {e}")
            return None
    
    def _parse_spotify_track(self, track: Dict[str, Any]) -> Optional[Song]:
        """解析 Spotify 歌曲格式"""
        try:
            # 获取艺术家名称
            artists = track.get('artists', [])
            artist_names = [artist.get('name', '') for artist in artists]
            artist = ', '.join(artist_names) if artist_names else 'Unknown'
            
            # 获取专辑信息
            album_data = track.get('album', {})
            album = album_data.get('name', '')
            
            # 获取封面图片
            artwork = ''
            images = album_data.get('images', [])
            if images:
                artwork = images[0].get('url', '')
            
            song = Song(
                id=track.get('id', ''),
                title=track.get('name', ''),
                artist=artist,
                album=album,
                duration=track.get('duration_ms', 0) // 1000,  # 毫秒转秒
                platform='spotify',
                artwork=artwork,
                url=track.get('external_urls', {}).get('spotify', ''),
                extra={
                    'spotify_id': track.get('id'),
                    'preview_url': track.get('preview_url'),
                    'original_track': track
                }
            )
            
            return song
            
        except Exception as e:
            logger.warning(f"Error parsing Spotify track: {e}")
            return None
    
    def export_to_file(self, playlist: Playlist, file_path: str, format_type: str = 'simple_playlist') -> bool:
        """导出歌单到文件"""
        try:
            if format_type == 'simple_playlist':
                data = playlist.to_dict()
            elif format_type == 'musicfree_backup':
                data = self._convert_to_musicfree_format(playlist)
            else:
                logger.error(f"Unsupported export format: {format_type}")
                return False
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Exported playlist to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting playlist to {file_path}: {e}")
            return False
    
    def _convert_to_musicfree_format(self, playlist: Playlist) -> Dict[str, Any]:
        """转换为 MusicFree 格式"""
        music_list = []
        
        for song in playlist.songs:
            item = {
                'id': song.id,
                'title': song.title,
                'artist': song.artist,
                'album': song.album,
                'duration': song.duration,
                'platform': song.platform,
                'artwork': song.artwork,
                'tags': song.tags,
                'date': song.date,
                'url': song.url
            }
            
            # 添加额外信息
            if song.extra:
                item.update(song.extra)
            
            music_list.append(item)
        
        return {
            'musicSheets': [{
                'id': playlist.id,
                'platform': playlist.name,
                'musicList': music_list
            }]
        }
