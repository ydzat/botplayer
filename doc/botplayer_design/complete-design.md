# BotPlayer 插件完整设计文档

## 概述

BotPlayer 是一个基于 LangBot 插件系统的 Discord 音乐播放器插件。该插件使用 Discord 适配器提供的基础语音连接功能，实现完整的音乐播放、队列管理和用户交互功能。

## 设计原则

- **职责分离**: 插件负责业务逻辑，适配器负责底层 API
- **模块化**: 各功能组件独立，便于维护和扩展
- **用户友好**: 提供直观的命令接口和友好的反馈信息

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                 BotPlayer 插件架构                          │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │   插件控制器     │  │   命令处理器     │                  │
│  │  (Controller)   │  │  (CommandHandler)│                  │
│  └─────────────────┘  └─────────────────┘                  │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   音频管理器     │  │   播放控制器     │  │  队列管理器  │ │
│  │ (AudioManager)  │  │(PlaybackControl)│  │(QueueManager)│ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Discord 适配器基础语音 API                 │ │
│  │        (join_voice_channel, get_voice_client...)       │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 核心组件设计

### 1. 插件控制器 (Controller)

**职责**: 插件生命周期管理和组件协调

#### 关键方法
```python
class BotPlayerController:
    async def initialize(self):
        """初始化插件"""
        
    async def shutdown(self):
        """关闭插件"""
        
    def get_discord_adapter(self) -> Optional[DiscordAdapter]:
        """获取 Discord 适配器实例"""
        
    async def handle_voice_event(self, event):
        """处理语音相关事件"""
```

### 2. 音频管理器 (AudioManager)

**职责**: 音频源处理、搜索、信息提取

#### 核心功能
```python
class AudioManager:
    async def process_source(self, source: str, options: dict = None) -> AudioInfo:
        """处理音频源，支持 URL、文件路径、搜索关键词"""
        
    async def search_music(self, query: str, platform: str = "youtube", limit: int = 10) -> List[SearchResult]:
        """搜索音乐"""
        
    async def validate_source(self, source: str) -> ValidationResult:
        """验证音频源有效性"""
        
    async def get_audio_stream(self, url: str) -> AudioStream:
        """获取音频流对象"""
```

#### 支持的音频源
- **YouTube**: 通过 yt-dlp 支持
- **本地文件**: MP3, FLAC, OGG, WAV 等格式
- **HTTP 流**: 直接的音频 URL
- **Spotify**: 获取信息，通过 YouTube 播放

### 3. 播放控制器 (PlaybackController)

**职责**: 音频播放控制，与 Discord 适配器交互

#### 核心功能
```python
class PlaybackController:
    async def play_audio(self, guild_id: int, audio_info: AudioInfo) -> bool:
        """播放音频"""
        
    def pause_playback(self, guild_id: int) -> bool:
        """暂停播放"""
        
    def resume_playback(self, guild_id: int) -> bool:
        """恢复播放"""
        
    def stop_playback(self, guild_id: int) -> bool:
        """停止播放"""
        
    def get_playback_status(self, guild_id: int) -> PlaybackStatus:
        """获取播放状态"""
        
    def set_volume(self, guild_id: int, volume: int) -> bool:
        """设置音量 (0-100)"""
```

### 4. 队列管理器 (QueueManager)

**职责**: 播放队列管理、播放逻辑

#### 核心功能
```python
class QueueManager:
    async def add_to_queue(self, guild_id: int, audio_info: AudioInfo, requester: UserInfo, position: int = -1) -> int:
        """添加到队列"""
        
    def remove_from_queue(self, guild_id: int, position: int) -> bool:
        """从队列移除"""
        
    def get_queue(self, guild_id: int) -> List[QueueItem]:
        """获取队列"""
        
    def clear_queue(self, guild_id: int) -> bool:
        """清空队列"""
        
    def shuffle_queue(self, guild_id: int) -> bool:
        """随机排列队列"""
        
    async def play_next(self, guild_id: int) -> Optional[AudioInfo]:
        """播放下一首"""
        
    def set_loop_mode(self, guild_id: int, mode: LoopMode) -> bool:
        """设置循环模式"""
```

### 5. 命令处理器 (CommandHandler)

**职责**: 用户命令解析和执行

#### 命令系统
```python
class CommandHandler:
    @command("play")
    async def handle_play_command(self, event, args: str):
        """处理播放命令"""
        
    @command("pause")
    async def handle_pause_command(self, event):
        """处理暂停命令"""
        
    @command("queue")
    async def handle_queue_command(self, event, subcommand: str = None):
        """处理队列相关命令"""
        
    @command("search")
    async def handle_search_command(self, event, query: str):
        """处理搜索命令"""
```

## 数据结构定义

### AudioInfo
```python
@dataclass
class AudioInfo:
    id: str
    title: str
    duration: int  # 秒
    url: str
    original_url: str
    thumbnail: Optional[str]
    uploader: str
    platform: str
    file_size: Optional[int]  # 字节
    bitrate: Optional[int]   # kbps
    format: str
```

### QueueItem
```python
@dataclass
class QueueItem:
    id: str
    audio_info: AudioInfo
    requester: UserInfo
    added_time: int  # Unix 时间戳
    status: QueueItemStatus  # waiting/playing/failed
    position: int
```

### PlaybackStatus
```python
@dataclass
class PlaybackStatus:
    guild_id: int
    is_connected: bool
    is_playing: bool
    is_paused: bool
    current_time: float
    total_time: float
    volume: int
    loop_mode: LoopMode
    current_audio: Optional[AudioInfo]
    queue_length: int
```

### UserInfo
```python
@dataclass
class UserInfo:
    user_id: int
    username: str
    discriminator: Optional[str]
    display_name: str
```

## 枚举定义

```python
class LoopMode(Enum):
    OFF = "off"
    SINGLE = "single"
    QUEUE = "queue"

class QueueItemStatus(Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    FAILED = "failed"

class AudioPlatform(Enum):
    YOUTUBE = "youtube"
    LOCAL = "local"
    HTTP = "http"
    SPOTIFY = "spotify"
```

## 命令接口设计

### 基础播放命令
- `!play <音频源>` - 播放音频
- `!pause` - 暂停播放
- `!resume` - 恢复播放
- `!stop` - 停止播放并清空队列
- `!skip` - 跳过当前音频
- `!join [频道名]` - 加入语音频道
- `!leave` - 离开语音频道

### 队列管理命令
- `!queue` - 显示当前队列
- `!queue add <音频源>` - 添加到队列
- `!queue remove <位置>` - 移除队列项目
- `!queue clear` - 清空队列
- `!queue shuffle` - 随机排列队列

### 控制命令
- `!volume <0-100>` - 设置音量
- `!loop <off/single/queue>` - 设置循环模式
- `!nowplaying` - 显示当前播放信息

### 搜索命令
- `!search <关键词>` - 搜索音乐
- `!search youtube <关键词>` - 在 YouTube 搜索

## 配置设计

```yaml
botplayer:
  enabled: true
  
  # 队列设置
  max_queue_length: 50
  max_duration_per_track: 3600  # 秒
  
  # 音量设置
  default_volume: 50
  max_volume: 100
  
  # 搜索设置
  search_results_limit: 10
  default_search_platform: "youtube"
  
  # 权限设置
  admin_only_commands: ["volume", "loop", "clear"]
  max_requests_per_user: 10
  
  # 自动化设置
  auto_leave_when_empty: true
  auto_leave_timeout: 300  # 秒
  auto_pause_when_alone: false
  
  # 支持的格式
  allowed_formats: ["mp3", "mp4", "webm", "ogg", "flac", "wav"]
```

## 事件系统

### 内部事件
```python
class AudioEvent:
    PLAYBACK_STARTED = "playback_started"
    PLAYBACK_PAUSED = "playback_paused"
    PLAYBACK_RESUMED = "playback_resumed"
    PLAYBACK_STOPPED = "playback_stopped"
    PLAYBACK_ENDED = "playback_ended"
    PLAYBACK_ERROR = "playback_error"
    
    QUEUE_ADDED = "queue_added"
    QUEUE_REMOVED = "queue_removed"
    QUEUE_CLEARED = "queue_cleared"
    QUEUE_NEXT = "queue_next"
    
    VOICE_CONNECTED = "voice_connected"
    VOICE_DISCONNECTED = "voice_disconnected"
```

### 事件处理
```python
class EventHandler:
    async def on_playback_ended(self, guild_id: int, audio_info: AudioInfo):
        """音频播放结束后自动播放下一首"""
        next_audio = await self.queue_manager.play_next(guild_id)
        if next_audio:
            await self.playback_controller.play_audio(guild_id, next_audio)
```

## 错误处理

### 异常定义
```python
class BotPlayerException(Exception):
    """插件基础异常"""

class AudioSourceError(BotPlayerException):
    """音频源错误"""

class PlaybackError(BotPlayerException):
    """播放错误"""

class QueueError(BotPlayerException):
    """队列操作错误"""

class PermissionError(BotPlayerException):
    """权限错误"""
```

### 错误处理策略
- **网络错误**: 自动重试，提供降级选项
- **格式错误**: 友好提示，建议支持的格式
- **权限错误**: 清晰的权限要求说明
- **播放错误**: 自动跳过，记录错误日志

## 测试策略

### 单元测试
- 各组件独立功能测试
- 模拟 Discord 适配器进行测试
- 音频源处理测试

### 集成测试
- 完整播放流程测试
- 队列管理测试
- 命令处理测试

### 性能测试
- 大队列处理性能
- 并发播放测试
- 内存使用监控
