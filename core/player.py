"""
BotPlayer 核心播放器
整合音源管理、缓存管理、队列管理等功能
"""
import asyncio
import logging
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
    
    def set_play_mode(self, mode: PlayMode):
        """设置播放模式"""
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
    async def import_playlist_from_url(self, url: str) -> Optional[Playlist]:
        """从URL导入歌单"""
        try:
            playlist = await self.playlist_importer.import_from_url(url)
            if playlist:
                await self._save_playlist(playlist)
                logger.info(f"Imported playlist: {playlist.name} with {len(playlist.songs)} songs")
            return playlist
        except Exception as e:
            logger.error(f"Error importing playlist from URL: {e}")
            return None
    
    async def import_playlist_from_file(self, file_path: str) -> Optional[Playlist]:
        """从文件导入歌单"""
        try:
            playlist = await self.playlist_importer.import_from_file(file_path)
            if playlist:
                await self._save_playlist(playlist)
                logger.info(f"Imported playlist: {playlist.name} with {len(playlist.songs)} songs")
            return playlist
        except Exception as e:
            logger.error(f"Error importing playlist from file: {e}")
            return None
    
    async def _save_playlist(self, playlist: Playlist):
        """保存歌单到数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 保存歌单信息
                now = datetime.now().isoformat()
                conn.execute('''
                    INSERT OR REPLACE INTO playlists 
                    (id, name, description, creator, cover, tags, created_at, updated_at, extra)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    playlist.id, playlist.name, playlist.description, playlist.creator,
                    playlist.cover, ','.join(playlist.tags), 
                    playlist.created_at or now, now, str(playlist.extra)
                ))
                
                # 保存歌曲
                for song in playlist.songs:
                    await self._save_song(song)
                
                # 保存歌单歌曲关系
                conn.execute('DELETE FROM playlist_songs WHERE playlist_id = ?', (playlist.id,))
                for i, song in enumerate(playlist.songs):
                    conn.execute('''
                        INSERT INTO playlist_songs (playlist_id, song_id, position)
                        VALUES (?, ?, ?)
                    ''', (playlist.id, song.id, i))
                
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving playlist {playlist.id}: {e}")
    
    async def get_playlists(self) -> List[Playlist]:
        """获取所有歌单"""
        try:
            playlists = []
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT id, name, description, creator, cover, tags, created_at, updated_at, extra
                    FROM playlists
                ''')
                
                for row in cursor:
                    playlist = Playlist(
                        id=row[0],
                        name=row[1],
                        description=row[2] or '',
                        creator=row[3] or '',
                        cover=row[4] or '',
                        tags=row[5].split(',') if row[5] else [],
                        created_at=row[6] or '',
                        updated_at=row[7] or '',
                        extra=eval(row[8]) if row[8] else {}
                    )
                    
                    # 加载歌曲
                    await self._load_playlist_songs(playlist)
                    playlists.append(playlist)
            
            return playlists
        except Exception as e:
            logger.error(f"Error getting playlists: {e}")
            return []
    
    async def _load_playlist_songs(self, playlist: Playlist):
        """加载歌单的歌曲"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT s.id, s.title, s.artist, s.album, s.duration, s.platform, 
                           s.artwork, s.url, s.tags, s.date, s.extra
                    FROM songs s
                    JOIN playlist_songs ps ON s.id = ps.song_id
                    WHERE ps.playlist_id = ?
                    ORDER BY ps.position
                ''', (playlist.id,))
                
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
                    playlist.songs.append(song)
        except Exception as e:
            logger.error(f"Error loading songs for playlist {playlist.id}: {e}")
    
    async def load_playlist_to_queue(self, playlist_id: str, clear_queue: bool = True) -> bool:
        """加载歌单到播放队列"""
        try:
            playlists = await self.get_playlists()
            playlist = next((p for p in playlists if p.id == playlist_id), None)
            
            if not playlist:
                logger.error(f"Playlist not found: {playlist_id}")
                return False
            
            if clear_queue:
                self.clear_queue()
            
            for song in playlist.songs:
                self.add_to_queue(song)
            
            logger.info(f"Loaded playlist '{playlist.name}' to queue ({len(playlist.songs)} songs)")
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
