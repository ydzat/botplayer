# Discord 适配器基础语音功能扩展架构设计

## 整体架构设计

### 分层架构中适配器的位置

```
┌─────────────────────────────────────────────────────────────┐
│                     LangBot 核心系统                        │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │   应用上下文     │  │   插件管理器     │                  │
│  │ (Application)   │  │  (PluginManager) │                  │
│  └─────────────────┘  └─────────────────┘                  │
├─────────────────────────────────────────────────────────────┤
│                    平台适配器层                              │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │        扩展的 Discord 适配器                            │ │
│  │     (pkg/platform/sources/discord.py)                  │ │
│  │                                                         │ │
│  │  [现有功能]              [基础语音功能]                  │ │
│  │  ┌─────────────┐        ┌─────────────┐                │ │
│  │  │ 消息转换器   │        │ 语音连接管理 │                │ │
│  │  │ 事件转换器   │        │   (仅连接)   │                │ │
│  │  │ 消息发送     │        │             │                │ │
│  │  └─────────────┘        └─────────────┘                │ │
│  └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                     Discord API                            │
│           (消息API + 语音API + WebSocket Gateway)           │
└─────────────────────────────────────────────────────────────┘
```

## Discord 适配器基础语音扩展

### 扩展范围和职责

#### 职责范围
- **仅提供基础语音连接功能**
- **不包含任何业务逻辑**
- **为插件提供标准化的语音 API**

#### 扩展内容
```python
class DiscordAdapter(adapter.MessagePlatformAdapter):
    # 保持现有属性不变
    # ...existing attributes...
    
    # 新增：基础语音连接管理
    voice_clients: Dict[int, discord.VoiceClient] = {}
    
    # 新增方法（仅基础功能）
    async def join_voice_channel(self, channel_id: int) -> Optional[discord.VoiceClient]
    async def leave_voice_channel(self, guild_id: int) -> bool
    def get_voice_client(self, guild_id: int) -> Optional[discord.VoiceClient]
    def is_connected_to_voice(self, guild_id: int) -> bool
```

### 适配器的职责边界

#### ✅ 应该包含的功能
- **基础语音连接**: `join_voice_channel()`, `leave_voice_channel()`
- **连接状态查询**: `get_voice_client()`, `is_connected_to_voice()`
- **基础事件处理**: `on_voice_state_update()` 等

#### ❌ 不应该包含的功能
- ~~音频队列管理~~
- ~~音频源处理~~
- ~~播放控制逻辑~~
- ~~搜索功能~~
- ~~用户权限检查~~
- ~~业务流程控制~~

## 配置和集成策略

### Discord 适配器配置扩展
```yaml
discord:
  token: "bot_token"
  client_id: "client_id"
  
  # 基础语音功能配置
  voice:
    enabled: true  # 是否启用语音连接功能
```

### 依赖关系
- **Discord 适配器**: 仅需要 `discord.py[voice]` 和 `PyNaCl`

### 部署灵活性
- **可选部署**: 可以单独启用/禁用语音功能
- **向后兼容**: 适配器扩展不影响现有功能

## 错误处理策略

### 适配器层错误处理
- **网络连接**: Discord API 调用错误
- **权限错误**: 语音频道权限不足
- **连接错误**: 语音连接建立失败

### 容错机制
- 连接重试机制
- 错误状态清理
- 异常日志记录

## 性能考虑

### 资源管理
- 语音客户端生命周期管理
- 连接状态监控
- 内存泄漏防护
