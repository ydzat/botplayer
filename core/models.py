"""
BotPlayer 数据模型定义
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import hashlib
import json


class PlayMode(Enum):
    """播放模式枚举"""
    SEQUENTIAL = "sequential"      # 顺序播放
    SHUFFLE = "shuffle"            # 随机播放
    REPEAT_ALL = "repeat_all"      # 循环播放全部
    REPEAT_ONE = "repeat_one"      # 单曲循环


class PlayerStatus(Enum):
    """播放器状态枚举"""
    IDLE = "idle"                  # 空闲
    PLAYING = "playing"            # 播放中
    PAUSED = "paused"              # 暂停
    BUFFERING = "buffering"        # 缓冲中
    ERROR = "error"                # 错误


@dataclass
class Song:
    """歌曲信息模型"""
    id: str                        # 歌曲唯一标识
    title: str                     # 歌曲标题
    artist: str                    # 艺术家
    album: str = ""                # 专辑名称
    duration: int = 0              # 时长（秒）
    platform: str = ""             # 来源平台
    artwork: str = ""              # 封面图片URL
    url: str = ""                  # 播放链接
    tags: List[str] = field(default_factory=list)  # 标签
    date: str = ""                 # 发布日期
    extra: Dict[str, Any] = field(default_factory=dict)  # 额外信息
    
    def __post_init__(self):
        """后处理：生成哈希ID"""
        if not self.id:
            # 基于标题+艺术家生成唯一ID
            content = f"{self.title}_{self.artist}_{self.platform}"
            self.id = hashlib.md5(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'title': self.title,
            'artist': self.artist,
            'album': self.album,
            'duration': self.duration,
            'platform': self.platform,
            'artwork': self.artwork,
            'url': self.url,
            'tags': self.tags,
            'date': self.date,
            'extra': self.extra
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Song':
        """从字典创建实例"""
        return cls(
            id=data.get('id', ''),
            title=data.get('title', ''),
            artist=data.get('artist', ''),
            album=data.get('album', ''),
            duration=data.get('duration', 0),
            platform=data.get('platform', ''),
            artwork=data.get('artwork', ''),
            url=data.get('url', ''),
            tags=data.get('tags', []),
            date=data.get('date', ''),
            extra=data.get('extra', {})
        )


@dataclass
class Playlist:
    """歌单模型"""
    id: str                        # 歌单唯一标识
    name: str                      # 歌单名称
    description: str = ""          # 歌单描述
    songs: List[Song] = field(default_factory=list)  # 歌曲列表
    creator: str = ""              # 创建者
    cover: str = ""                # 封面图片
    tags: List[str] = field(default_factory=list)  # 标签
    created_at: str = ""           # 创建时间
    updated_at: str = ""           # 更新时间
    extra: Dict[str, Any] = field(default_factory=dict)  # 额外信息
    
    def __post_init__(self):
        """后处理：生成哈希ID"""
        if not self.id:
            content = f"{self.name}_{self.creator}"
            self.id = hashlib.md5(content.encode()).hexdigest()[:16]
    
    def add_song(self, song: Song) -> None:
        """添加歌曲"""
        if song not in self.songs:
            self.songs.append(song)
    
    def remove_song(self, song_id: str) -> bool:
        """移除歌曲"""
        for i, song in enumerate(self.songs):
            if song.id == song_id:
                del self.songs[i]
                return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'songs': [song.to_dict() for song in self.songs],
            'creator': self.creator,
            'cover': self.cover,
            'tags': self.tags,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'extra': self.extra
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Playlist':
        """从字典创建实例"""
        songs = [Song.from_dict(song_data) for song_data in data.get('songs', [])]
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            description=data.get('description', ''),
            songs=songs,
            creator=data.get('creator', ''),
            cover=data.get('cover', ''),
            tags=data.get('tags', []),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            extra=data.get('extra', {})
        )


@dataclass
class PlayQueue:
    """播放队列模型"""
    current_index: int = 0         # 当前播放索引
    songs: List[Song] = field(default_factory=list)  # 歌曲列表
    play_mode: PlayMode = PlayMode.SEQUENTIAL  # 播放模式
    shuffle_history: List[int] = field(default_factory=list)  # 随机播放历史
    
    def add_song(self, song: Song, position: Optional[int] = None) -> None:
        """添加歌曲到队列"""
        if position is None:
            self.songs.append(song)
        else:
            self.songs.insert(position, song)
    
    def remove_song(self, index: int) -> bool:
        """从队列移除歌曲"""
        if 0 <= index < len(self.songs):
            del self.songs[index]
            if index < self.current_index:
                self.current_index -= 1
            elif index == self.current_index and self.current_index >= len(self.songs):
                self.current_index = 0
            return True
        return False
    
    def get_current_song(self) -> Optional[Song]:
        """获取当前歌曲"""
        if 0 <= self.current_index < len(self.songs):
            return self.songs[self.current_index]
        return None
    
    def next_song(self) -> Optional[Song]:
        """获取下一首歌曲"""
        if not self.songs:
            return None
        
        if self.play_mode == PlayMode.REPEAT_ONE:
            return self.get_current_song()
        elif self.play_mode == PlayMode.SHUFFLE:
            return self._next_shuffle()
        elif self.play_mode == PlayMode.SEQUENTIAL:
            # 顺序播放：只播放一次，到队列末尾就停止
            next_index = self.current_index + 1
            if next_index < len(self.songs):
                self.current_index = next_index
                return self.get_current_song()
            else:
                # 到达队列末尾，停止播放
                return None
        else:  # REPEAT_ALL
            # 列表循环：到队列末尾时回到开头
            self.current_index = (self.current_index + 1) % len(self.songs)
            return self.get_current_song()
    
    def has_next_song(self) -> bool:
        """检查是否有下一首歌曲可播放"""
        if not self.songs:
            return False
        
        if self.play_mode == PlayMode.REPEAT_ONE:
            return True  # 单曲循环总是有下一首（当前歌曲）
        elif self.play_mode == PlayMode.SHUFFLE:
            return len(self.songs) > 1  # 随机播放需要至少2首歌
        elif self.play_mode == PlayMode.SEQUENTIAL:
            return self.current_index + 1 < len(self.songs)  # 顺序播放检查是否到末尾
        else:  # REPEAT_ALL
            return True  # 列表循环总是有下一首
    
    def previous_song(self) -> Optional[Song]:
        """获取上一首歌曲"""
        if not self.songs:
            return None
        
        if self.play_mode == PlayMode.REPEAT_ONE:
            return self.get_current_song()
        elif self.play_mode == PlayMode.SHUFFLE:
            return self._previous_shuffle()
        elif self.play_mode == PlayMode.SEQUENTIAL:
            # 顺序播放：只能回到之前的歌曲
            prev_index = self.current_index - 1
            if prev_index >= 0:
                self.current_index = prev_index
                return self.get_current_song()
            else:
                # 到达队列开头，无法继续
                return None
        else:  # REPEAT_ALL
            # 列表循环：到队列开头时回到末尾
            self.current_index = (self.current_index - 1) % len(self.songs)
            return self.get_current_song()
    
    def _next_shuffle(self) -> Optional[Song]:
        """随机播放下一首"""
        if len(self.songs) <= 1:
            return self.get_current_song()
        
        import random
        available_indices = list(range(len(self.songs)))
        
        # 如果有历史记录，避免重复最近播放的歌曲
        if len(self.shuffle_history) >= len(self.songs) // 2:
            recent = self.shuffle_history[-len(self.songs)//3:]
            available_indices = [i for i in available_indices if i not in recent]
        
        if not available_indices:
            available_indices = list(range(len(self.songs)))
        
        if self.current_index in available_indices:
            available_indices.remove(self.current_index)
        
        if available_indices:
            self.current_index = random.choice(available_indices)
            self.shuffle_history.append(self.current_index)
            
            # 限制历史记录长度
            if len(self.shuffle_history) > len(self.songs):
                self.shuffle_history = self.shuffle_history[-len(self.songs):]
        
        return self.get_current_song()
    
    def _previous_shuffle(self) -> Optional[Song]:
        """随机播放上一首"""
        if len(self.shuffle_history) > 1:
            self.shuffle_history.pop()  # 移除当前
            self.current_index = self.shuffle_history[-1]
        return self.get_current_song()
    
    def clear(self) -> None:
        """清空队列"""
        self.songs.clear()
        self.current_index = 0
        self.shuffle_history.clear()
    
    def shuffle_all(self) -> None:
        """打乱整个队列"""
        import random
        if self.songs:
            current_song = self.get_current_song()
            random.shuffle(self.songs)
            # 重新定位当前歌曲
            if current_song:
                try:
                    self.current_index = self.songs.index(current_song)
                except ValueError:
                    self.current_index = 0


@dataclass
class AudioCache:
    """音频缓存项模型"""
    song_id: str                   # 歌曲ID
    file_path: str                 # 文件路径
    file_size: int                 # 文件大小（字节）
    audio_hash: str                # 音频内容哈希
    created_at: str                # 创建时间
    last_accessed: str             # 最后访问时间
    access_count: int = 0          # 访问次数
    reference_count: int = 1       # 引用计数
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'song_id': self.song_id,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'audio_hash': self.audio_hash,
            'created_at': self.created_at,
            'last_accessed': self.last_accessed,
            'access_count': self.access_count,
            'reference_count': self.reference_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AudioCache':
        """从字典创建实例"""
        return cls(
            song_id=data['song_id'],
            file_path=data['file_path'],
            file_size=data['file_size'],
            audio_hash=data['audio_hash'],
            created_at=data['created_at'],
            last_accessed=data['last_accessed'],
            access_count=data.get('access_count', 0),
            reference_count=data.get('reference_count', 1)
        )


@dataclass
class PlayerState:
    """播放器状态模型"""
    status: PlayerStatus = PlayerStatus.IDLE  # 播放状态
    current_song: Optional[Song] = None       # 当前歌曲
    position: int = 0                         # 播放位置（秒）
    volume: float = 0.5                       # 音量 (0.0 - 1.0)
    queue: PlayQueue = field(default_factory=PlayQueue)  # 播放队列
    last_error: str = ""                      # 最后错误信息
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'status': self.status.value,
            'current_song': self.current_song.to_dict() if self.current_song else None,
            'position': self.position,
            'volume': self.volume,
            'play_mode': self.queue.play_mode.value,
            'queue_length': len(self.queue.songs),
            'queue_index': self.queue.current_index,
            'last_error': self.last_error
        }
