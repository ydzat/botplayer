# BotPlayer 插件 API 设计文档

## 概述

BotPlayer 是一个基于 LangBot 插件系统的 Discord 音乐播放器插件。该插件使用 Discord 适配器提供的基础语音连接功能，实现完整的音乐播放、队列管理和用户交互功能。

## 插件架构设计

### 与 Discord 适配器的交互

BotPlayer 插件通过 LangBot 应用上下文获取 Discord 适配器实例，并使用其基础语音 API：

```python
# 插件获取适配器实例
def get_discord_adapter() -> typing.Optional[DiscordAdapter]:
    """从 LangBot 应用上下文中获取 Discord 适配器实例"""
    pass

# 使用适配器的基础语音功能
voice_client = await discord_adapter.join_voice_channel(channel_id)
if voice_client:
    # 插件自己处理音频播放逻辑
    voice_client.play(audio_source)
```

## 插件组件设计

### 音频管理器 (AudioManager)

负责音频源处理，不依赖 Discord 适配器：

#### process_source()
**功能**: 处理和验证音频源
**方法签名**: `async def process_source(self, source: str, options: dict = None) -> dict`

#### search_music()
**功能**: 搜索音乐
**方法签名**: `async def search_music(self, query: str, platform: str = "youtube", limit: int = 10) -> list`

### 播放控制器 (PlaybackController)

管理音频播放逻辑，与 Discord 适配器交互：

#### play_audio()
**功能**: 播放音频（使用适配器的语音客户端）
**方法签名**: `async def play_audio(self, guild_id: int, audio_source: str) -> bool`

#### pause_playback()
**功能**: 暂停播放
**方法签名**: `def pause_playback(self, guild_id: int) -> bool`

#### stop_playback()
**功能**: 停止播放
**方法签名**: `def stop_playback(self, guild_id: int) -> bool`

### 队列管理器 (QueueManager)

管理播放队列，独立于适配器：

#### add_to_queue()
**功能**: 添加音频到播放队列
**方法签名**: `async def add_to_queue(self, guild_id: int, audio_item: dict, position: int = -1) -> int`

#### get_queue()
**功能**: 获取当前播放队列
**方法签名**: `def get_queue(self, guild_id: int) -> list`

#### clear_queue()
**功能**: 清空播放队列
**方法签名**: `def clear_queue(self, guild_id: int) -> bool`

## 插件命令系统

基于 LangBot 命令系统实现：

### 基础播放命令
- `!play <音频源>`: 播放音频
- `!pause`: 暂停播放
- `!stop`: 停止播放
- `!join`: 加入用户所在语音频道
- `!leave`: 离开语音频道

### 队列管理命令
- `!queue`: 显示播放队列
- `!queue add <音频源>`: 添加到队列
- `!queue clear`: 清空队列

## 数据结构定义

### 音频信息结构 (AudioInfo)
```python
{
    "id": "唯一标识符",
    "title": "音频标题",
    "duration": 180,  # 时长（秒）
    "url": "实际播放URL",
    "thumbnail": "缩略图URL",
    "uploader": "上传者/艺术家",
    "platform": "来源平台"
}
```

### 队列项目结构 (QueueItem)
```python
{
    "id": "unique_id_123",
    "audio_info": {},      # AudioInfo 对象
    "requester": {
        "user_id": 987654321,
        "username": "user123"
    },
    "added_time": 1625097600,  # Unix 时间戳
    "status": "waiting"        # waiting/playing/failed
}
```

## 插件配置

```yaml
botplayer:
  enabled: true
  max_queue_length: 50
  max_duration: 3600  # 最大播放时长（秒）
  allowed_formats: ["mp3", "mp4", "webm", "ogg"]
  volume_default: 50
```
