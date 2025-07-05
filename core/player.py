"""
BotPlayer 核心播放器
整合音源管理、缓存管理、队列管理等功能
"""
import asyncio
import logging
import json
from typing import Optional, List, Dict, Any
from .models import Song, Playlist, PlayQueue, PlayerState, PlayerStatus, PlayMode
from .plugin_manager import PluginManager
from .cache_manager import AudioCacheManager
from .playlist_importer import PlaylistImporter
from .config_manager import ConfigManager
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class BotPlayerCore:
    """BotPlayer 核心类"""
    
    def __init__(self, data_dir: str = "data", config: Dict[str, Any] = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # 配置管理
        config_path = self.data_dir.parent / "config.yaml"
        self.config_manager = ConfigManager(str(config_path))
        self.config = config or self.config_manager.get_botplayer_config()
        
        # 初始化组件
        self.plugin_manager = PluginManager(
            str(self.data_dir / "plugins"),
            self.config_manager.get_plugin_config()
        )
        self.cache_manager = AudioCacheManager(
            cache_dir=str(self.data_dir / "audio_cache"),
            config=self.config_manager.get_cache_config()
        )
        self.playlist_importer = PlaylistImporter(self.config_manager)
        
        # 播放器状态
        self.player_state = PlayerState()
        
        # 数据库
        self.db_path = self.data_dir / "botplayer.db"
        self._init_database()
        
        # 加载保存的状态
        self._load_state()
    
    async def initialize_async(self):
        """异步初始化，需要在异步环境中调用"""
        try:
            # 初始化 MusicFree 插件
            await self.plugin_manager.initialize_async_plugins()
            logger.info("异步插件初始化完成")
        except Exception as e:
            logger.error(f"异步初始化失败: {e}")
    
    def _init_database(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            # 播放列表表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS playlists (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    creator TEXT,
                    cover TEXT,
                    tags TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    extra TEXT
                )
            ''')
            
            # 歌曲表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS songs (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    artist TEXT,
                    album TEXT,
                    duration INTEGER,
                    platform TEXT,
                    artwork TEXT,
                    url TEXT,
                    tags TEXT,
                    date TEXT,
                    extra TEXT
                )
            ''')
            
            # 播放列表歌曲关系表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS playlist_songs (
                    playlist_id TEXT,
                    song_id TEXT,
                    position INTEGER,
                    PRIMARY KEY (playlist_id, song_id),
                    FOREIGN KEY (playlist_id) REFERENCES playlists (id),
                    FOREIGN KEY (song_id) REFERENCES songs (id)
                )
            ''')
            
            # 播放历史表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS play_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    song_id TEXT,
                    played_at TEXT,
                    duration_played INTEGER,
                    FOREIGN KEY (song_id) REFERENCES songs (id)
                )
            ''')
            
            conn.commit()
    
    def _load_state(self):
        """加载保存的状态"""
        try:
            # 这里可以从数据库或配置文件加载上次的播放状态
            # 暂时使用默认状态
            pass
        except Exception as e:
            logger.warning(f"Error loading state: {e}")
    
    def _save_state(self):
        """保存当前状态"""
        try:
            # 这里可以保存当前播放状态到数据库或配置文件
            pass
        except Exception as e:
            logger.warning(f"Error saving state: {e}")
    
    # 搜索相关方法
    async def search_songs(self, query: str, platform: str = None, limit: int = 10) -> List[Song]:
        """搜索歌曲"""
        try:
            results = await self.plugin_manager.search_song(query, platform, limit)
            
            # 保存搜索到的歌曲到数据库
            for song in results:
                await self._save_song(song)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching songs: {e}")
            return []
    
    async def _save_song(self, song: Song):
        """保存歌曲到数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO songs 
                    (id, title, artist, album, duration, platform, artwork, url, tags, date, extra)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    song.id, song.title, song.artist, song.album, song.duration,
                    song.platform, song.artwork, song.url,
                    ','.join(song.tags), song.date, str(song.extra)
                ))
                conn.commit()
        except Exception as e:
            logger.warning(f"Error saving song {song.id}: {e}")
    
    # 播放控制方法
    async def play_song(self, song: Song) -> bool:
        """播放指定歌曲"""
        try:
            # 获取播放URL
            play_url = await self.plugin_manager.get_play_url(song)
            if not play_url:
                logger.error(f"No play URL for song {song.id}")
                return False
            
            # 更新歌曲URL
            song.url = play_url
            
            # 获取缓存的音频文件
            audio_file = await self.cache_manager.get_audio_file(song)
            if not audio_file:
                logger.error(f"Failed to get audio file for song {song.id}")
                return False
            
            # 更新播放器状态
            self.player_state.current_song = song
            self.player_state.status = PlayerStatus.PLAYING
            self.player_state.position = 0
            
            # 记录播放历史
            await self._record_play_history(song)
            
            logger.info(f"Playing song: {song.title} by {song.artist}")
            return True
            
        except Exception as e:
            logger.error(f"Error playing song {song.id}: {e}")
            self.player_state.status = PlayerStatus.ERROR
            self.player_state.last_error = str(e)
            return False
    
    async def play_next(self) -> Optional[Song]:
        """播放下一首"""
        try:
            next_song = self.player_state.queue.next_song()
            if next_song:
                success = await self.play_song(next_song)
                return next_song if success else None
            return None
        except Exception as e:
            logger.error(f"Error playing next song: {e}")
            return None
    
    async def play_previous(self) -> Optional[Song]:
        """播放上一首"""
        try:
            prev_song = self.player_state.queue.previous_song()
            if prev_song:
                success = await self.play_song(prev_song)
                return prev_song if success else None
            return None
        except Exception as e:
            logger.error(f"Error playing previous song: {e}")
            return None
    
    def pause(self):
        """暂停播放"""
        if self.player_state.status == PlayerStatus.PLAYING:
            self.player_state.status = PlayerStatus.PAUSED
            logger.info("Playback paused")
    
    def resume(self):
        """恢复播放"""
        if self.player_state.status == PlayerStatus.PAUSED:
            self.player_state.status = PlayerStatus.PLAYING
            logger.info("Playback resumed")
    
    def stop(self):
        """停止播放"""
        self.player_state.status = PlayerStatus.IDLE
        self.player_state.current_song = None
        self.player_state.position = 0
        logger.info("Playback stopped")
    
    def set_volume(self, volume: float):
        """设置音量"""
        self.player_state.volume = max(0.0, min(1.0, volume))
        logger.info(f"Volume set to {self.player_state.volume:.2f}")
    
    # 队列管理方法
    def add_to_queue(self, song: Song, position: Optional[int] = None):
        """添加歌曲到队列"""
        self.player_state.queue.add_song(song, position)
        logger.info(f"Added to queue: {song.title} by {song.artist}")
    
    def remove_from_queue(self, index: int) -> bool:
        """从队列移除歌曲"""
        success = self.player_state.queue.remove_song(index)
        if success:
            logger.info(f"Removed song at index {index} from queue")
        return success
    
    def clear_queue(self):
        """清空队列"""
        self.player_state.queue.clear()
        logger.info("Queue cleared")
    
    def shuffle_queue(self):
        """打乱队列"""
        self.player_state.queue.shuffle_all()
        logger.info("Queue shuffled")
    
    def set_play_mode(self, mode):
        """设置播放模式"""
        if isinstance(mode, str):
            # 将字符串转换为 PlayMode 枚举
            mode_map = {
                'sequential': PlayMode.SEQUENTIAL,
                'random': PlayMode.SHUFFLE,
                'shuffle': PlayMode.SHUFFLE,
                'loop': PlayMode.REPEAT_ALL,
                'repeat_all': PlayMode.REPEAT_ALL,
                'repeat_one': PlayMode.REPEAT_ONE
            }
            mode = mode_map.get(mode.lower(), PlayMode.SEQUENTIAL)
        
        self.player_state.queue.play_mode = mode
        logger.info(f"Play mode set to {mode.value}")
    
    def get_queue_info(self) -> Dict[str, Any]:
        """获取队列信息"""
        return {
            'current_index': self.player_state.queue.current_index,
            'total_songs': len(self.player_state.queue.songs),
            'play_mode': self.player_state.queue.play_mode.value,
            'songs': [song.to_dict() for song in self.player_state.queue.songs]
        }
    
    # 歌单管理方法
    async def save_playlist(self, playlist: Playlist) -> Optional[str]:
        """保存歌单到数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 保存歌单信息
                conn.execute('''
                    INSERT OR REPLACE INTO playlists 
                    (id, name, description, creator, cover, tags, created_at, updated_at, extra)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    playlist.id,
                    playlist.name,
                    playlist.description,
                    playlist.creator,
                    playlist.cover,
                    ','.join(playlist.tags) if playlist.tags else '',
                    playlist.created_at.isoformat() if playlist.created_at else datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    json.dumps(playlist.extra) if playlist.extra else '{}'
                ))
                
                # 删除旧的歌曲关系
                conn.execute('DELETE FROM playlist_songs WHERE playlist_id = ?', (playlist.id,))
                
                # 保存歌曲和关系
                for position, song in enumerate(playlist.songs):
                    # 保存歌曲信息
                    conn.execute('''
                        INSERT OR REPLACE INTO songs 
                        (id, title, artist, album, duration, platform, artwork, url, tags, date, extra)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        song.id,
                        song.title,
                        song.artist,
                        song.album,
                        song.duration,
                        song.platform,
                        song.artwork,
                        song.url,
                        ','.join(song.tags) if song.tags else '',
                        song.date,
                        json.dumps(song.extra) if song.extra else '{}'
                    ))
                    
                    # 保存歌单-歌曲关系
                    conn.execute('''
                        INSERT INTO playlist_songs (playlist_id, song_id, position)
                        VALUES (?, ?, ?)
                    ''', (playlist.id, song.id, position))
                
                conn.commit()
                logger.info(f"Saved playlist {playlist.name} with {len(playlist.songs)} songs")
                return playlist.id
                
        except Exception as e:
            logger.error(f"Error saving playlist: {e}")
            return None
    
    async def get_playlists(self) -> List[Dict[str, Any]]:
        """获取所有歌单"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT p.id, p.name, p.description, p.creator, p.cover, p.tags, 
                           p.created_at, p.updated_at, COUNT(ps.song_id) as song_count
                    FROM playlists p
                    LEFT JOIN playlist_songs ps ON p.id = ps.playlist_id
                    GROUP BY p.id
                    ORDER BY p.updated_at DESC
                ''')
                
                playlists = []
                for row in cursor.fetchall():
                    playlists.append({
                        'id': row[0],
                        'name': row[1],
                        'description': row[2],
                        'creator': row[3],
                        'cover': row[4],
                        'tags': row[5].split(',') if row[5] else [],
                        'created_at': row[6],
                        'updated_at': row[7],
                        'song_count': row[8]
                    })
                
                return playlists
                
        except Exception as e:
            logger.error(f"Error getting playlists: {e}")
            return []
    
    async def get_playlist_by_id(self, playlist_id: str) -> Optional[Playlist]:
        """根据ID获取歌单"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 获取歌单信息
                cursor = conn.execute('''
                    SELECT id, name, description, creator, cover, tags, created_at, updated_at, extra
                    FROM playlists WHERE id = ?
                ''', (playlist_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                # 创建歌单对象
                from datetime import datetime
                import json
                
                playlist = Playlist(
                    id=row[0],
                    name=row[1],
                    description=row[2],
                    creator=row[3],
                    cover=row[4],
                    tags=row[5].split(',') if row[5] else [],
                    created_at=datetime.fromisoformat(row[6]) if row[6] else None,
                    extra=json.loads(row[8]) if row[8] else {}
                )
                
                # 获取歌曲列表
                cursor = conn.execute('''
                    SELECT s.id, s.title, s.artist, s.album, s.duration, s.platform, 
                           s.artwork, s.url, s.tags, s.date, s.extra
                    FROM songs s
                    JOIN playlist_songs ps ON s.id = ps.song_id
                    WHERE ps.playlist_id = ?
                    ORDER BY ps.position
                ''', (playlist_id,))
                
                for song_row in cursor.fetchall():
                    song = Song(
                        id=song_row[0],
                        title=song_row[1],
                        artist=song_row[2],
                        album=song_row[3],
                        duration=song_row[4],
                        platform=song_row[5],
                        artwork=song_row[6],
                        url=song_row[7],
                        tags=song_row[8].split(',') if song_row[8] else [],
                        date=song_row[9],
                        extra=json.loads(song_row[10]) if song_row[10] else {}
                    )
                    playlist.add_song(song)
                
                return playlist
                
        except Exception as e:
            logger.error(f"Error getting playlist {playlist_id}: {e}")
            return None
    
    async def delete_playlist(self, playlist_id: str) -> bool:
        """删除歌单"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 删除歌单-歌曲关系
                conn.execute('DELETE FROM playlist_songs WHERE playlist_id = ?', (playlist_id,))
                
                # 删除歌单
                cursor = conn.execute('DELETE FROM playlists WHERE id = ?', (playlist_id,))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"Deleted playlist {playlist_id}")
                    return True
                else:
                    logger.warning(f"Playlist {playlist_id} not found")
                    return False
                    
        except Exception as e:
            logger.error(f"Error deleting playlist {playlist_id}: {e}")
            return False
    
    async def load_playlist_to_queue(self, playlist_id: str, clear_queue: bool = True) -> bool:
        """将歌单加载到播放队列"""
        try:
            playlist = await self.get_playlist_by_id(playlist_id)
            if not playlist:
                logger.error(f"Playlist {playlist_id} not found")
                return False
            
            if clear_queue:
                self.clear_queue()
            
            for song in playlist.songs:
                self.add_to_queue(song)
            
            logger.info(f"Loaded playlist {playlist.name} with {len(playlist.songs)} songs to queue")
            return True
            
        except Exception as e:
            logger.error(f"Error loading playlist to queue: {e}")
            return False
    
    # 历史记录方法
    async def _record_play_history(self, song: Song):
        """记录播放历史"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO play_history (song_id, played_at, duration_played)
                    VALUES (?, ?, ?)
                ''', (song.id, datetime.now().isoformat(), 0))
                conn.commit()
        except Exception as e:
            logger.warning(f"Error recording play history for {song.id}: {e}")
    
    async def get_play_history(self, limit: int = 50) -> List[Song]:
        """获取播放历史"""
        try:
            songs = []
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT DISTINCT s.id, s.title, s.artist, s.album, s.duration, 
                           s.platform, s.artwork, s.url, s.tags, s.date, s.extra,
                           MAX(h.played_at) as last_played
                    FROM songs s
                    JOIN play_history h ON s.id = h.song_id
                    GROUP BY s.id
                    ORDER BY last_played DESC
                    LIMIT ?
                ''', (limit,))
                
                for row in cursor:
                    song = Song(
                        id=row[0],
                        title=row[1],
                        artist=row[2] or '',
                        album=row[3] or '',
                        duration=row[4] or 0,
                        platform=row[5] or '',
                        artwork=row[6] or '',
                        url=row[7] or '',
                        tags=row[8].split(',') if row[8] else [],
                        date=row[9] or '',
                        extra=eval(row[10]) if row[10] else {}
                    )
                    songs.append(song)
            
            return songs
        except Exception as e:
            logger.error(f"Error getting play history: {e}")
            return []
    
    # 状态获取方法
    def get_current_song(self) -> Optional[Song]:
        """获取当前播放的歌曲"""
        return self.player_state.current_song
    
    def get_queue_info(self) -> Dict[str, Any]:
        """获取队列信息"""
        queue = self.player_state.queue
        return {
            'current_index': queue.current_index,
            'total_songs': len(queue.songs),
            'play_mode': queue.play_mode.value,
            'songs': [song.to_dict() for song in queue.songs]
        }
    
    def get_player_status(self) -> Dict[str, Any]:
        """获取播放器状态"""
        return self.player_state.to_dict()
    
    def is_playing(self) -> bool:
        """检查是否正在播放"""
        return self.player_state.status == PlayerStatus.PLAYING
    
    def is_paused(self) -> bool:
        """检查是否暂停"""
        return self.player_state.status == PlayerStatus.PAUSED
    
    # 缓存管理方法
    def get_cache_status(self) -> Dict[str, Any]:
        """获取缓存状态"""
        try:
            return self.cache_manager.get_cache_stats()
        except Exception as e:
            logger.error(f"Error getting cache status: {e}")
            return {
                'total_files': 0,
                'total_size_mb': 0,
                'max_size_mb': self.config_manager.get_cache_max_size() / (1024**2),
                'usage_percent': 0,
                'avg_access_count': 0
            }
    
    def clear_cache(self) -> bool:
        """清理缓存"""
        try:
            return self.cache_manager.clear_cache()
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    def reload_config(self):
        """重新加载配置"""
        try:
            self.config_manager.reload_config()
            self.config = self.config_manager.get_botplayer_config()
            logger.info("Configuration reloaded")
        except Exception as e:
            logger.error(f"Error reloading configuration: {e}")
    
    def get_config_value(self, key: str, default=None):
        """获取配置值"""
        return self.config_manager.get(key, default)
    
    # 清理方法
    async def cleanup(self):
        """清理资源"""
        try:
            self.stop()
            self._save_state()
            logger.info("BotPlayer cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    # 智能播放方法
    async def smart_play(self, query: str, platform: str = None) -> Optional[Song]:
        """智能搜索并播放歌曲"""
        try:
            # 搜索歌曲
            results = await self.search_songs(query, platform, limit=5)
            if not results:
                logger.warning(f"No songs found for query: {query}")
                return None
            
            # 选择最佳匹配（第一个结果）
            best_match = results[0]
            
            # 添加到队列
            self.add_to_queue(best_match)
            
            # 如果当前没有播放，开始播放
            if self.player_state.status == PlayerStatus.IDLE:
                success = await self.play_song(best_match)
                return best_match if success else None
            
            return best_match
            
        except Exception as e:
            logger.error(f"Error in smart_play for query '{query}': {e}")
            return None
    
    async def play_song_by_id(self, song_id: str) -> bool:
        """根据歌曲ID播放歌曲"""
        try:
            # 从数据库获取歌曲信息
            song = await self._get_song_by_id(song_id)
            if not song:
                logger.error(f"Song not found: {song_id}")
                return False
            
            return await self.play_song(song)
            
        except Exception as e:
            logger.error(f"Error playing song by ID {song_id}: {e}")
            return False
    
    async def _get_song_by_id(self, song_id: str) -> Optional[Song]:
        """根据ID获取歌曲"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT id, title, artist, album, duration, platform, artwork, url, tags, date, extra
                    FROM songs WHERE id = ?
                ''', (song_id,))
                
                row = cursor.fetchone()
                if row:
                    return Song(
                        id=row[0], title=row[1], artist=row[2], album=row[3],
                        duration=row[4], platform=row[5], artwork=row[6], url=row[7],
                        tags=row[8].split(',') if row[8] else [],
                        date=row[9], extra=eval(row[10]) if row[10] else {}
                    )
                return None
        except Exception as e:
            logger.error(f"Error getting song by ID {song_id}: {e}")
            return None
    
    # 错误处理和恢复
    async def handle_playback_error(self, error: Exception):
        """处理播放错误"""
        logger.error(f"Playback error: {error}")
        self.player_state.status = PlayerStatus.ERROR
        self.player_state.last_error = str(error)
        
        # 尝试播放下一首
        try:
            await asyncio.sleep(1)  # 短暂延迟
            next_song = await self.play_next()
            if next_song:
                logger.info(f"Recovered by playing next song: {next_song.title}")
            else:
                self.stop()
                logger.warning("No next song available, stopped playback")
        except Exception as e:
            logger.error(f"Error in playback recovery: {e}")
            self.stop()
    
    def get_plugin_status(self) -> Dict[str, Any]:
        """获取插件状态信息"""
        try:
            plugin_info = self.plugin_manager.get_available_plugins()
            enabled_plugins = [p for p in plugin_info if p.get('enabled', True)]
            
            return {
                'total_plugins': len(plugin_info),
                'enabled_plugins': len(enabled_plugins),
                'disabled_plugins': len(plugin_info) - len(enabled_plugins),
                'plugins': plugin_info
            }
        except Exception as e:
            self.logger.error(f"获取插件状态失败: {e}")
            return {
                'total_plugins': 0,
                'enabled_plugins': 0,
                'disabled_plugins': 0,
                'plugins': [],
                'error': str(e)
            }
    
    async def import_playlist_from_url(self, url: str) -> Optional[Playlist]:
        """从URL导入歌单并保存"""
        try:
            # 使用歌单导入器导入
            playlist = await self.playlist_importer.import_from_url(url)
            if not playlist:
                logger.error(f"Failed to import playlist from URL: {url}")
                return None
            
            # 保存到数据库
            saved_id = await self.save_playlist(playlist)
            if saved_id:
                logger.info(f"Successfully imported and saved playlist: {playlist.name}")
                return playlist
            else:
                logger.error(f"Failed to save imported playlist: {playlist.name}")
                return None
                
        except Exception as e:
            logger.error(f"Error importing playlist from URL {url}: {e}")
            return None
    
    async def import_playlist_from_file(self, file_path: str) -> Optional[Playlist]:
        """从文件导入歌单并保存"""
        try:
            # 使用歌单导入器导入
            playlist = await self.playlist_importer.import_from_file(file_path)
            if not playlist:
                logger.error(f"Failed to import playlist from file: {file_path}")
                return None
            
            # 保存到数据库
            saved_id = await self.save_playlist(playlist)
            if saved_id:
                logger.info(f"Successfully imported and saved playlist: {playlist.name}")
                return playlist
            else:
                logger.error(f"Failed to save imported playlist: {playlist.name}")
                return None
                
        except Exception as e:
            logger.error(f"Error importing playlist from file {file_path}: {e}")
            return None
