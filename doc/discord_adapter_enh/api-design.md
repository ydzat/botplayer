# Discord 适配器基础语音功能扩展 API 设计

## 概述

本文档描述了对现有 `pkg/platform/sources/discord.py` 中 `DiscordAdapter` 类的**基础语音功能**扩展。扩展仅添加 Discord 语音频道连接和基础音频播放的底层 API 支持，不包含任何特定于 BotPlayer 插件的业务逻辑。

## 设计原则

- **职责分离**: Discord 适配器仅提供 Discord API 的基础封装
- **业务无关**: 不包含音乐播放、队列管理等业务逻辑
- **插件友好**: 为上层插件提供标准化的语音操作接口

## Discord 适配器基础语音扩展

### 现有 DiscordAdapter 类扩展

基于现有的 `DiscordAdapter` 类，仅添加**必要的语音连接管理**功能：

#### 新增类属性
```python
class DiscordAdapter(adapter.MessagePlatformAdapter):
    # ...existing attributes...
    
    # 新增基础语音功能属性
    voice_clients: typing.Dict[int, discord.VoiceClient] = {}
```

### 基础语音连接方法

#### join_voice_channel()
**功能**: 连接到指定的语音频道
**方法签名**: `async def join_voice_channel(self, channel_id: int, user_id: int) -> typing.Optional[discord.VoiceClient]`
**参数**:
- `channel_id: int`: 语音频道ID
- `user_id: int`: 请求用户ID（用于验证用户是否在语音频道中）
**返回值**: `Optional[discord.VoiceClient]` - 成功时返回语音客户端，失败时返回 None
**职责**: 仅负责建立语音连接，不处理任何业务逻辑

#### leave_voice_channel()
**功能**: 断开指定服务器的语音连接
**方法签名**: `async def leave_voice_channel(self, guild_id: int) -> bool`
**参数**:
- `guild_id: int`: 服务器ID
**返回值**: `bool` - 是否成功断开连接
**职责**: 仅负责断开语音连接，不处理任何业务逻辑

#### get_voice_client()
**功能**: 获取指定服务器的语音客户端
**方法签名**: `def get_voice_client(self, guild_id: int) -> typing.Optional[discord.VoiceClient]`
**参数**:
- `guild_id: int`: 服务器ID
**返回值**: `Optional[discord.VoiceClient]` - 语音客户端实例或 None
**职责**: 仅提供语音客户端的访问接口

#### is_connected_to_voice()
**功能**: 检查是否连接到语音频道
**方法签名**: `def is_connected_to_voice(self, guild_id: int) -> bool`
**参数**:
- `guild_id: int`: 服务器ID
**返回值**: `bool` - 是否已连接到语音频道
**职责**: 提供连接状态查询

#### get_connection_status()
**功能**: 获取指定服务器的详细连接状态
**方法签名**: `def get_connection_status(self, guild_id: int) -> dict`
**参数**:
- `guild_id: int`: 服务器ID
**返回值**: `dict` - 包含连接状态详细信息的字典
**职责**: 提供连接状态的详细信息查询

#### list_active_connections()
**功能**: 列出所有活跃的语音连接
**方法签名**: `def list_active_connections(self) -> typing.List[dict]`
**返回值**: `List[dict]` - 活跃连接信息列表
**职责**: 提供所有连接的概览信息

#### get_voice_channel_info()
**功能**: 获取当前连接的语音频道信息
**方法签名**: `def get_voice_channel_info(self, guild_id: int) -> typing.Optional[dict]`
**参数**:
- `guild_id: int`: 服务器ID
**返回值**: `Optional[dict]` - 频道信息字典或 None
**职责**: 提供当前连接频道的详细信息

### Discord 客户端扩展

#### 扩展现有的 MyClient 类
在现有的 `MyClient` 内部类中添加基础语音事件处理：

```python
class MyClient(discord.Client):
    # ...existing methods...
    
    async def on_voice_state_update(self, member, before, after):
        # 基础语音状态变更事件处理
        # 仅处理连接状态，不包含业务逻辑
        pass
```

## 配置扩展

在现有 Discord 适配器配置中添加语音功能开关：

```yaml
discord:
  token: "bot_token"
  client_id: "client_id"
  
  # 新增语音功能配置
  voice:
    enabled: true  # 是否启用语音功能
```

## 权限和依赖

### Discord 权限要求
- Connect (连接语音频道)
- Speak (在语音频道中说话)
- Use Voice Activity (使用语音活动)

### 依赖要求
- `discord.py[voice] >= 2.0.0`: Discord API 客户端库，包含语音功能支持
- `PyNaCl >= 1.4.0`: Discord 语音功能必需的加密库

## 错误处理

### 异常定义
```python
class VoiceConnectionError(Exception):
    """语音连接相关错误基类"""
    pass

class PermissionDeniedError(VoiceConnectionError):
    """权限不足错误"""
    pass

class ChannelNotFoundError(VoiceConnectionError):
    """频道不存在错误"""
    pass

class NetworkError(VoiceConnectionError):
    """网络连接错误"""
    pass

class UserNotInVoiceError(VoiceConnectionError):
    """用户不在语音频道错误"""
    pass

class AlreadyConnectedError(VoiceConnectionError):
    """已连接到语音频道错误"""
    pass
```

### 错误场景
- 权限不足
- 频道不存在
- 网络连接问题
- 语音依赖缺失




