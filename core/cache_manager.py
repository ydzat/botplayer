"""
音频缓存管理器
智能缓存管理，支持LRU清理、哈希去重和引用计数
"""
import os
import hashlib
import asyncio
import aiohttp
import sqlite3
import time
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime
import shutil
import logging
from .models import Song, AudioCache
import yt_dlp
from pathlib import Path

logger = logging.getLogger(__name__)


class AudioCacheManager:
    """音频缓存管理器"""
    
    def __init__(self, cache_dir: str = "data/audio_cache", config: Dict = None):
        self.cache_dir = Path(cache_dir)
        self.config = config or {}
        self.max_size = self.config.get('max_size', 10 * 1024**3)  # 10GB
        self.db_path = self.cache_dir / "cache.db"
        self.temp_dir = self.cache_dir / "temp"
        
        # 创建目录
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库
        self._init_database()
        
        # 下载限制
        max_downloads = self.config.get('max_concurrent_downloads', 3)
        self._download_semaphore = asyncio.Semaphore(max_downloads)
        
        # yt-dlp 配置
        audio_format = self.config.get('audio_format', 'mp3')
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': audio_format,
            'outtmpl': str(self.temp_dir / '%(id)s.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': self.config.get('download_timeout', 30),
            'retries': 3,
        }
    
    def _init_database(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS audio_cache (
                    song_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    audio_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    reference_count INTEGER DEFAULT 1
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_audio_hash ON audio_cache(audio_hash)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_last_accessed ON audio_cache(last_accessed)
            ''')
            conn.commit()
    
    def _calculate_hash(self, file_path: str) -> str:
        """计算文件哈希"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            # 读取文件头部和尾部用于快速哈希
            chunk_size = 8192
            # 读取开头
            chunk = f.read(chunk_size)
            hash_md5.update(chunk)
            
            # 如果文件足够大，跳到中间和结尾
            file_size = os.path.getsize(file_path)
            if file_size > chunk_size * 3:
                # 中间
                f.seek(file_size // 2)
                chunk = f.read(chunk_size)
                hash_md5.update(chunk)
                
                # 结尾
                f.seek(-chunk_size, 2)
                chunk = f.read(chunk_size)
                hash_md5.update(chunk)
        
        return hash_md5.hexdigest()
    
    def _get_cache_info(self, song_id: str) -> Optional[AudioCache]:
        """获取缓存信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT song_id, file_path, file_size, audio_hash, created_at, 
                       last_accessed, access_count, reference_count
                FROM audio_cache WHERE song_id = ?
            ''', (song_id,))
            row = cursor.fetchone()
            
            if row:
                return AudioCache(
                    song_id=row[0],
                    file_path=row[1],
                    file_size=row[2],
                    audio_hash=row[3],
                    created_at=row[4],
                    last_accessed=row[5],
                    access_count=row[6],
                    reference_count=row[7]
                )
        return None
    
    def _update_access_info(self, song_id: str):
        """更新访问信息"""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE audio_cache 
                SET last_accessed = ?, access_count = access_count + 1
                WHERE song_id = ?
            ''', (now, song_id))
            conn.commit()
    
    def _save_cache_info(self, cache: AudioCache):
        """保存缓存信息"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO audio_cache 
                (song_id, file_path, file_size, audio_hash, created_at, 
                 last_accessed, access_count, reference_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                cache.song_id, cache.file_path, cache.file_size,
                cache.audio_hash, cache.created_at, cache.last_accessed,
                cache.access_count, cache.reference_count
            ))
            conn.commit()

    async def get_audio_file(self, song: Song) -> Optional[str]:
        """获取音频文件路径，如果不存在则下载并缓存"""
        try:
            # 检查缓存
            cache_info = self._get_cache_info(song.id)
            if cache_info and os.path.exists(cache_info.file_path):
                # 更新访问信息
                self._update_access_info(song.id)
                logger.debug(f"Cache hit for song: {song.title}")
                return cache_info.file_path
            
            # 缓存未命中，下载音频
            logger.info(f"Cache miss for song: {song.title}, downloading...")
            return await self._download_and_cache(song)
            
        except Exception as e:
            logger.error(f"Error getting audio file for {song.id}: {e}")
            return None

    async def _download_and_cache(self, song: Song) -> Optional[str]:
        """下载并缓存音频"""
        async with self._download_semaphore:
            try:
                if not song.url:
                    logger.error(f"No URL provided for song: {song.id}")
                    return None
                
                # 检查是否是模拟数据
                if 'mock' in song.id:
                    # 为测试创建一个简单的音频文件
                    return await self._create_test_audio_file(song)
                
                # 使用 yt-dlp 下载
                temp_file = await self._download_with_ytdlp(song.url)
                if not temp_file:
                    logger.error(f"Failed to download audio for: {song.title}")
                    return None
                
                # 计算哈希并检查重复
                audio_hash = self._calculate_hash(temp_file)
                existing_file = await self._find_by_hash(audio_hash)
                
                if existing_file:
                    # 找到相同的文件，创建引用
                    os.remove(temp_file)  # 删除临时文件
                    await self._create_cache_reference(song.id, existing_file, audio_hash)
                    logger.info(f"Found duplicate audio for {song.title}, created reference")
                    return existing_file
                
                # 移动到缓存目录
                file_extension = os.path.splitext(temp_file)[1]
                cache_file = self.cache_dir / f"{song.id}{file_extension}"
                shutil.move(temp_file, cache_file)
                
                # 检查缓存空间
                await self._check_cache_space()
                
                # 保存缓存信息
                cache_info = AudioCache(
                    song_id=song.id,
                    file_path=str(cache_file),
                    file_size=os.path.getsize(cache_file),
                    audio_hash=audio_hash,
                    created_at=datetime.now().isoformat(),
                    last_accessed=datetime.now().isoformat(),
                    access_count=1,
                    reference_count=1
                )
                self._save_cache_info(cache_info)
                
                logger.info(f"Successfully cached audio for: {song.title}")
                return str(cache_file)
                
            except Exception as e:
                logger.error(f"Error downloading and caching {song.id}: {e}")
                return None

    async def _create_test_audio_file(self, song: Song) -> Optional[str]:
        """为测试创建一个简单的音频文件"""
        try:
            # 检查是否已经有测试音频文件
            test_audio_path = self.cache_dir / "test_music.mp3"
            
            if test_audio_path.exists():
                # 如果已经有测试音频，创建符号链接或复制
                cache_file = self.cache_dir / f"{song.id}.mp3"
                if not cache_file.exists():
                    shutil.copy2(test_audio_path, cache_file)
                
                # 保存缓存信息
                cache_info = AudioCache(
                    song_id=song.id,
                    file_path=str(cache_file),
                    file_size=os.path.getsize(cache_file),
                    audio_hash=self._calculate_hash(str(cache_file)),
                    created_at=datetime.now().isoformat(),
                    last_accessed=datetime.now().isoformat(),
                    access_count=1,
                    reference_count=1
                )
                self._save_cache_info(cache_info)
                
                logger.info(f"Created test audio file for: {song.title}")
                return str(cache_file)
            else:
                # 如果没有测试音频文件，检查项目中是否有
                project_test_file = Path(__file__).parent.parent / "test_music.mp3"
                if project_test_file.exists():
                    # 复制到缓存目录
                    shutil.copy2(project_test_file, test_audio_path)
                    return await self._create_test_audio_file(song)  # 递归调用
                else:
                    # 创建一个简单的测试音频文件（静音）
                    return await self._create_silent_audio_file(song)
                    
        except Exception as e:
            logger.error(f"Error creating test audio file: {e}")
            return None

    async def _create_silent_audio_file(self, song: Song) -> Optional[str]:
        """创建一个简单的静音音频文件用于测试"""
        try:
            # 尝试使用 ffmpeg 创建一个短的静音音频文件
            cache_file = self.cache_dir / f"{song.id}.mp3"
            
            # 创建一个小的示例音频文件
            # 这里我们创建一个简单的文本文件作为占位符
            # 在实际应用中，应该使用适当的音频库
            with open(cache_file, 'wb') as f:
                # 写入一个简单的MP3头部（非常基础的实现）
                # 这只是为了测试，实际应用中需要真正的音频数据
                f.write(b'\xff\xfb\x90\x00' + b'\x00' * 1000)  # 基本的MP3头部 + 数据
            
            # 保存缓存信息
            cache_info = AudioCache(
                song_id=song.id,
                file_path=str(cache_file),
                file_size=os.path.getsize(cache_file),
                audio_hash=self._calculate_hash(str(cache_file)),
                created_at=datetime.now().isoformat(),
                last_accessed=datetime.now().isoformat(),
                access_count=1,
                reference_count=1
            )
            self._save_cache_info(cache_info)
            
            logger.info(f"Created silent test audio file for: {song.title}")
            return str(cache_file)
            
        except Exception as e:
            logger.error(f"Error creating silent audio file: {e}")
            return None

    async def _download_with_ytdlp(self, url: str) -> Optional[str]:
        """使用 yt-dlp 下载音频"""
        try:
            # 创建临时文件名
            temp_id = hashlib.md5(url.encode()).hexdigest()[:16]
            
            # 更新输出模板
            opts = self.ydl_opts.copy()
            opts['outtmpl'] = str(self.temp_dir / f"{temp_id}.%(ext)s")
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                # 提取信息
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None
                
                # 下载
                ydl.download([url])
                
                # 查找下载的文件
                for file in self.temp_dir.glob(f"{temp_id}.*"):
                    if file.suffix in ['.mp3', '.m4a', '.opus', '.ogg', '.wav']:
                        return str(file)
                
                logger.warning(f"Downloaded file not found for URL: {url}")
                return None
                
        except Exception as e:
            logger.error(f"yt-dlp download failed for {url}: {e}")
            return None

    async def _find_by_hash(self, audio_hash: str) -> Optional[str]:
        """根据哈希查找已存在的文件"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT file_path FROM audio_cache 
                WHERE audio_hash = ? AND reference_count > 0
                LIMIT 1
            ''', (audio_hash,))
            row = cursor.fetchone()
            
            if row and os.path.exists(row[0]):
                return row[0]
        return None

    async def _create_cache_reference(self, song_id: str, file_path: str, audio_hash: str):
        """为已存在的文件创建引用"""
        cache_info = AudioCache(
            song_id=song_id,
            file_path=file_path,
            file_size=os.path.getsize(file_path),
            audio_hash=audio_hash,
            created_at=datetime.now().isoformat(),
            last_accessed=datetime.now().isoformat(),
            access_count=1,
            reference_count=1
        )
        self._save_cache_info(cache_info)
        
        # 增加原文件的引用计数
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE audio_cache 
                SET reference_count = reference_count + 1
                WHERE file_path = ? AND song_id != ?
            ''', (file_path, song_id))
            conn.commit()

    async def _check_cache_space(self):
        """检查缓存空间，必要时清理"""
        total_size = self._get_total_cache_size()
        
        if total_size > self.max_size:
            logger.info(f"Cache size ({total_size / 1024**2:.1f}MB) exceeds limit, cleaning up...")
            await self._cleanup_lru()

    def _get_total_cache_size(self) -> int:
        """获取总缓存大小"""
        total_size = 0
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT DISTINCT file_path, file_size FROM audio_cache')
            for row in cursor:
                if os.path.exists(row[0]):
                    total_size += row[1]
        return total_size

    async def _cleanup_lru(self):
        """LRU缓存清理算法"""
        try:
            # 获取按访问时间排序的缓存条目
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT DISTINCT file_path, last_accessed, file_size, 
                           COUNT(*) as ref_count
                    FROM audio_cache 
                    WHERE reference_count > 0
                    GROUP BY file_path
                    ORDER BY last_accessed ASC
                ''')
                
                files_to_remove = []
                total_size = self._get_total_cache_size()
                target_size = int(self.max_size * 0.8)  # 清理到80%
                
                for row in cursor:
                    file_path, last_accessed, file_size, ref_count = row
                    
                    if not os.path.exists(file_path):
                        # 文件不存在，清理数据库记录
                        files_to_remove.append(file_path)
                        continue
                    
                    # 检查是否可以删除（考虑最小访问间隔）
                    last_access_time = datetime.fromisoformat(last_accessed)
                    time_since_access = (datetime.now() - last_access_time).total_seconds()
                    min_interval = self.config.get('min_access_interval', 3600)
                    
                    if time_since_access > min_interval:
                        files_to_remove.append(file_path)
                        total_size -= file_size
                        
                        if total_size <= target_size:
                            break
                
                # 删除文件和数据库记录
                removed_count = 0
                for file_path in files_to_remove:
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        
                        # 删除数据库记录
                        conn.execute('DELETE FROM audio_cache WHERE file_path = ?', (file_path,))
                        removed_count += 1
                        
                    except Exception as e:
                        logger.warning(f"Failed to remove cache file {file_path}: {e}")
                
                conn.commit()
                logger.info(f"LRU cleanup completed, removed {removed_count} files")
                
        except Exception as e:
            logger.error(f"Error in LRU cleanup: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT 
                        COUNT(*) as total_files,
                        SUM(file_size) as total_size,
                        AVG(access_count) as avg_access_count,
                        MIN(created_at) as oldest_file,
                        MAX(created_at) as newest_file
                    FROM audio_cache
                ''')
                stats = cursor.fetchone()
                
                return {
                    'total_files': stats[0] if stats[0] else 0,
                    'total_size': stats[1] if stats[1] else 0,
                    'total_size_mb': round((stats[1] if stats[1] else 0) / (1024 * 1024), 2),
                    'max_size_mb': round(self.max_size / (1024 * 1024), 2),
                    'usage_percent': round(((stats[1] if stats[1] else 0) / self.max_size) * 100, 2),
                    'avg_access_count': round(stats[2] if stats[2] else 0, 2),
                    'oldest_file': stats[3],
                    'newest_file': stats[4]
                }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                'total_files': 0,
                'total_size': 0,
                'total_size_mb': 0.0,
                'max_size_mb': round(self.max_size / (1024 * 1024), 2),
                'usage_percent': 0.0,
                'avg_access_count': 0.0,
                'oldest_file': None,
                'newest_file': None
            }

    def clear_cache(self) -> bool:
        """清空所有缓存"""
        try:
            # 删除所有缓存文件
            removed_count = 0
            for file_path in self.cache_dir.glob("*"):
                if file_path.is_file() and file_path.name != "cache.db":
                    try:
                        file_path.unlink()
                        removed_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to remove {file_path}: {e}")
            
            # 清空数据库
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('DELETE FROM audio_cache')
                conn.commit()
            
            logger.info(f"Cache cleared, removed {removed_count} files")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
