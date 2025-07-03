# BotPlayer 插件架构设计文档

## BotPlayer 插件架构

### 插件层架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                BotPlayer 插件                               │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   命令处理   │  │  音频管理器  │  │  播放控制器  │         │
│  │    器       │  │ AudioManager │  │PlaybackCtrl │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐                          │
│  │  队列管理器  │  │  插件控制器  │                          │
│  │QueueManager │  │ Controller  │                          │
│  └─────────────┘  └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    (使用基础语音API)
┌─────────────────────────────────────────────────────────────┐
│        Discord 适配器基础语音功能                            │
│     (join_voice_channel, get_voice_client...)               │
└─────────────────────────────────────────────────────────────┘
```

## 核心组件设计

### 1. 插件控制器 (plugin.py)
**职责**:
- 插件生命周期管理
- 与 LangBot 核心系统集成
- 获取和使用 Discord 适配器

**关键功能**:
```python
class BotPlayerController:
    def get_discord_adapter(self) -> Optional[DiscordAdapter]:
        """从应用上下文获取 Discord 适配器"""
        
    async def initialize_plugin(self):
        """初始化插件组件"""
        
    def register_commands(self):
        """注册插件命令"""
```

### 2. 音频管理器 (audio_manager.py)
**职责**:
- 音频源处理（YouTube、Spotify、本地文件）
- 音频信息提取和验证
- 搜索功能实现

**独立性**: 完全独立于 Discord 适配器，仅处理音频数据

### 3. 播放控制器 (playback_controller.py)
**职责**:
- 使用 Discord 适配器的语音客户端进行播放
- 播放状态管理
- 音量控制

**与适配器交互**:
```python
class PlaybackController:
    async def play_audio(self, guild_id: int, audio_info: AudioInfo):
        # 1. 获取语音客户端
        voice_client = self.discord_adapter.get_voice_client(guild_id)
        # 2. 使用 discord.py 的播放功能
        voice_client.play(audio_source)
```

### 4. 队列管理器 (queue_manager.py)
**职责**:
- 播放队列维护
- 播放逻辑控制
- 循环模式实现

**独立性**: 纯业务逻辑，不依赖任何适配器

### 5. 命令处理器 (command_handler.py)
**职责**:
- 用户命令解析
- 命令执行协调
- 用户反馈

## 交互流程设计

### 音乐播放请求流程
```
用户命令 → LangBot核心 → BotPlayer插件 → 音频管理器处理 → 播放控制器 → Discord适配器基础API → Discord语音客户端
```

**详细步骤**:
1. 用户在Discord发送音乐命令
2. Discord适配器接收消息并转换为LangBot事件
3. LangBot核心将命令路由到BotPlayer插件
4. 插件的命令处理器解析命令
5. 音频管理器处理音频源（URL解析、信息提取等）
6. 播放控制器通过适配器获取语音客户端
7. 使用 discord.py 的原生播放功能进行播放

### 语音连接管理流程
```
连接请求 → BotPlayer插件 → Discord适配器基础API → Discord API → 连接建立
```

**插件职责**: 处理连接逻辑、权限检查、用户反馈等业务逻辑

### 队列管理流程
```
队列操作 → BotPlayer队列管理器 → 纯内存操作 → 状态更新通知
```

**完全独立**: 队列管理完全在插件内部，不涉及适配器

## 插件职责范围

### ✅ 插件负责的功能
- **所有业务逻辑**: 音乐播放、队列管理、搜索等
- **用户交互**: 命令处理、反馈信息、权限检查
- **音频处理**: 源解析、格式转换、信息提取
- **状态管理**: 播放状态、队列状态、用户偏好

### 🔗 插件与适配器的交互
- **获取语音客户端**: 通过适配器的基础API
- **使用discord.py功能**: 直接调用语音客户端的播放方法
- **监听基础事件**: 订阅适配器提供的语音连接事件

## 配置和集成策略

### BotPlayer 插件独立配置
```yaml
botplayer:
  enabled: true
  max_queue_length: 50
  default_volume: 50
  auto_leave_timeout: 300
  
  # 音频处理配置
  audio:
    allowed_formats: ["mp3", "mp4", "webm", "ogg"]
    max_duration: 3600
    search_platform: "youtube"
    
  # 权限配置
  permissions:
    admin_commands: ["volume", "clear"]
    max_requests_per_user: 10
```

### 依赖关系
- **BotPlayer 插件**: 需要 `yt-dlp`, `ffmpeg` 等音频处理库

### 部署灵活性
- **可选部署**: 可以单独启用/禁用插件
- **独立更新**: 插件可以独立更新

## 错误处理策略

### 插件层错误处理
- **业务逻辑错误**: 参数验证、权限检查
- **音频处理错误**: 源解析失败、格式不支持
- **用户交互错误**: 友好错误提示、操作建议

### 容错机制
- 自动重试机制
- 备用音频源
- 降级播放模式
- 错误日志记录

## 性能优化

### 缓存策略
- 音频元数据缓存
- 播放历史缓存
- 搜索结果缓存

### 异步处理
- 音频预加载
- 队列预处理
- 并发播放控制

### 资源管理
- 内存使用监控
- 网络带宽控制
- 存储空间管理
