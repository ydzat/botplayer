# BotPlayer 插件架构设计文档

## 整体架构概览

BotPlayer 是一个完整的音乐播放器插件，采用分层模块化架构设计，支持多音源、用户存档、播放队列等完整功能。系统设计遵循高内聚、低耦合的原则，确保可扩展性和可维护性。

### 系统层次架构

```mermaid
graph TB
    subgraph "用户交互层"
        A[Discord命令界面] --> B[消息反应界面]
        B --> C[状态显示界面]
    end
    
    subgraph "应用服务层"
        D[播放器服务] --> E[歌单管理服务]
        E --> F[搜索服务]
        F --> G[用户管理服务]
    end
    
    subgraph "业务逻辑层"
        H[播放引擎] --> I[队列管理器]
        I --> J[音源聚合器]
        J --> K[用户存档管理器]
    end
    
    subgraph "数据访问层"
        L[音源适配器] --> M[数据持久化]
        M --> N[缓存管理]
    end
    
    subgraph "基础设施层"
        O[LangBot框架] --> P[Discord.py]
        P --> Q[音频处理]
        Q --> R[网络客户端]
    end
    
    A --> D
    D --> H
    H --> L
    L --> O
```

## 核心模块设计

### 1. 播放器引擎 (PlayerEngine)

播放器引擎是系统的核心模块，负责音频播放控制和状态管理。

```mermaid
classDiagram
    class PlayerEngine {
        -current_song: Song
        -play_state: PlayState
        -volume: float
        -quality_preference: str
        +play(song: Song)
        +pause()
        +resume()
        +stop()
        +skip()
        +set_volume(volume: float)
        +get_status(): PlayStatus
    }
    
    class PlayState {
        <<enumeration>>
        STOPPED
        PLAYING
        PAUSED
        BUFFERING
    }
    
    class PlayStatus {
        +song: Song
        +position: int
        +duration: int
        +state: PlayState
        +volume: float
    }
    
    PlayerEngine --> PlayState
    PlayerEngine --> PlayStatus
```

**核心功能**:
- 音频播放控制（播放、暂停、停止、跳过）
- 播放状态管理和监控
- 音量控制和音质选择
- 播放进度跟踪
- 错误处理和自动恢复

### 2. 播放队列管理器 (QueueManager)

管理播放队列，支持多种播放模式和队列操作。

```mermaid
classDiagram
    class QueueManager {
        -queue: List[Song]
        -current_index: int
        -play_mode: PlayMode
        -shuffle_order: List[int]
        -history: List[Song]
        +add_song(song: Song)
        +remove_song(index: int)
        +next_song(): Song
        +previous_song(): Song
        +set_play_mode(mode: PlayMode)
        +shuffle()
        +clear()
        +get_queue(): List[Song]
    }
    
    class PlayMode {
        <<enumeration>>
        SEQUENCE
        SHUFFLE
        REPEAT_ONE
        REPEAT_ALL
    }
    
    QueueManager --> PlayMode
```

**核心功能**:
- 队列增删改查操作
- 多种播放模式支持（顺序、随机、单曲循环、列表循环）
- 播放历史记录
- 智能下一首推荐
- 队列持久化存储

### 3. 音源聚合器 (SourceAggregator)

统一管理多个音源平台，提供统一的音乐搜索和获取接口。

```mermaid
classDiagram
    class SourceAggregator {
        -sources: List[MusicSource]
        -source_priority: Dict[str, int]
        +search(query: str): List[Song]
        +get_play_url(song: Song): str
        +get_lyrics(song: Song): str
        +verify_availability(song: Song): bool
        +add_source(source: MusicSource)
        +set_priority(source: str, priority: int)
    }
    
    class MusicSource {
        <<interface>>
        +platform: str
        +search(query: str): List[Song]
        +get_play_url(song_id: str): str
        +get_lyrics(song_id: str): str
        +is_available(): bool
    }
    
    class BilibiliSource {
        +platform: "bilibili"
        +search(query: str): List[Song]
        +get_play_url(song_id: str): str
        +get_lyrics(song_id: str): str
        +is_available(): bool
    }
    
    class NeteaseSource {
        +platform: "netease"
        +search(query: str): List[Song]
        +get_play_url(song_id: str): str
        +get_lyrics(song_id: str): str
        +is_available(): bool
    }
    
    SourceAggregator --> MusicSource
    MusicSource <|-- BilibiliSource
    MusicSource <|-- NeteaseSource
```

**核心功能**:
- 多音源平台统一接口
- 音源优先级管理
- 自动音源切换和备用方案
- 音源可用性监控
- 智能匹配和结果合并

### 4. 歌单管理器 (PlaylistManager)

负责歌单的创建、编辑、导入导出和同步功能。

```mermaid
classDiagram
    class PlaylistManager {
        -playlists: Dict[str, Playlist]
        -user_manager: UserManager
        +create_playlist(name: str, user_id: str): Playlist
        +import_playlist(file_path: str, user_id: str): Playlist
        +export_playlist(playlist_id: str, format: str): str
        +add_song_to_playlist(playlist_id: str, song: Song)
        +remove_song_from_playlist(playlist_id: str, song_index: int)
        +share_playlist(playlist_id: str): str
        +sync_with_webdav(user_id: str)
    }
    
    class Playlist {
        +id: str
        +name: str
        +owner_id: str
        +songs: List[Song]
        +created_at: datetime
        +updated_at: datetime
        +is_public: bool
        +description: str
        +tags: List[str]
    }
    
    class PlaylistFormat {
        <<enumeration>>
        MUSICFREE_BACKUP
        M3U
        JSON
        CSV
    }
    
    PlaylistManager --> Playlist
    PlaylistManager --> PlaylistFormat
```

**核心功能**:
- 歌单CRUD操作
- 安全的 URL 歌单导入（JSON 格式，HTTPS 协议）
- 歌单分享和协作
- webDAV云端同步
- 歌单标签和分类管理

### 5. 用户存档管理器 (UserManager)

管理用户个人数据、偏好设置和播放历史。

```mermaid
classDiagram
    class UserManager {
        -users: Dict[str, UserProfile]
        -storage: Storage
        +get_user(user_id: str): UserProfile
        +create_user(user_id: str): UserProfile
        +update_preferences(user_id: str, prefs: UserPreferences)
        +add_to_history(user_id: str, song: Song)
        +add_to_favorites(user_id: str, song: Song)
        +get_recommendations(user_id: str): List[Song]
        +backup_user_data(user_id: str): str
        +restore_user_data(user_id: str, backup_data: str)
    }
    
    class UserProfile {
        +user_id: str
        +display_name: str
        +preferences: UserPreferences
        +playlists: List[str]
        +play_history: List[PlayRecord]
        +favorites: List[Song]
        +created_at: datetime
        +last_active: datetime
    }
    
    class UserPreferences {
        +default_quality: str
        +default_volume: float
        +auto_play: bool
        +shuffle_mode: bool
        +notifications: bool
        +privacy_mode: bool
    }
    
    class PlayRecord {
        +song: Song
        +played_at: datetime
        +duration_played: int
        +completed: bool
    }
    
    UserManager --> UserProfile
    UserProfile --> UserPreferences
    UserProfile --> PlayRecord
```

**核心功能**:
- 用户档案管理
- 个人偏好设置
- 播放历史记录
- 收藏和喜欢管理
- 个性化推荐
- 数据备份和恢复

### 6. 搜索引擎 (SearchEngine)

提供智能音乐搜索和推荐功能。

```mermaid
classDiagram
    class SearchEngine {
        -source_aggregator: SourceAggregator
        -cache: SearchCache
        -recommender: RecommendationEngine
        +search(query: str, filters: SearchFilters): SearchResult
        +search_by_artist(artist: str): List[Song]
        +search_by_album(album: str): List[Song]
        +get_trending(): List[Song]
        +get_recommendations(user_id: str): List[Song]
    }
    
    class SearchFilters {
        +platform: str
        +duration_min: int
        +duration_max: int
        +quality: str
        +language: str
    }
    
    class SearchResult {
        +songs: List[Song]
        +total_count: int
        +query: str
        +search_time: float
        +sources: List[str]
    }
    
    SearchEngine --> SearchFilters
    SearchEngine --> SearchResult
```

**核心功能**:
- 跨平台智能搜索
- 搜索结果缓存和优化
- 个性化推荐算法
- 热门音乐发现
- 搜索历史和建议

## 数据模型设计

### 核心实体模型

```mermaid
erDiagram
    Song {
        string id PK
        string title
        string artist
        string album
        int duration
        string artwork_url
        datetime created_at
        datetime updated_at
    }
    
    SongSource {
        string song_id PK
        string platform PK
        string source_url
        string quality
        boolean available
        datetime verified_at
    }
    
    Playlist {
        string id PK
        string name
        string owner_id FK
        boolean is_public
        string description
        datetime created_at
        datetime updated_at
    }
    
    PlaylistSong {
        string playlist_id PK, FK
        string song_id PK, FK
        int order_index
        datetime added_at
    }
    
    UserProfile {
        string user_id PK
        string display_name
        json preferences
        datetime created_at
        datetime last_active
    }
    
    PlayHistory {
        string id PK
        string user_id FK
        string song_id FK
        datetime played_at
        int duration_played
        boolean completed
    }
    
    UserFavorites {
        string user_id PK, FK
        string song_id PK, FK
        datetime added_at
    }
    
    Song ||--o{ SongSource : has
    Playlist ||--o{ PlaylistSong : contains
    Song ||--o{ PlaylistSong : included_in
    UserProfile ||--o{ Playlist : owns
    UserProfile ||--o{ PlayHistory : has
    UserProfile ||--o{ UserFavorites : likes
    Song ||--o{ UserFavorites : liked_by
    Song ||--o{ PlayHistory : played_in
```

### 配置数据结构

```yaml
# 系统配置结构
botplayer:
  music_sources:
    bilibili:
      enabled: true
      api_key: "bilibili_api_key"
      rate_limit: 100
      priority: 1
    netease:
      enabled: true
      api_endpoint: "netease_api_endpoint"
      rate_limit: 50
      priority: 2
  
  storage:
    type: "sqlite"  # sqlite, postgresql, mysql
    connection_string: "sqlite:///data/botplayer.db"
    
  cache:
    enabled: true
    type: "redis"  # redis, memory
    size_limit: "1GB"
    expire_time: 7200
    
  audio:
    default_quality: "high"
    supported_formats: ["mp3", "flac", "ogg", "m4a"]
    max_file_size: "100MB"
    
  webdav:
    enabled: true
    server_url: "https://webdav.example.com"
    username: "user"
    password: "pass"
    sync_interval: 3600
```

## 服务层架构

### 应用服务层

```mermaid
classDiagram
    class PlayerService {
        -player_engine: PlayerEngine
        -queue_manager: QueueManager
        +play_song(song_id: str)
        +control_playback(action: str)
        +manage_queue(operation: str, data: any)
        +get_player_status(): PlayerStatus
    }
    
    class PlaylistService {
        -playlist_manager: PlaylistManager
        -user_manager: UserManager
        +create_playlist(user_id: str, name: str)
        +import_playlist(user_id: str, file_data: bytes)
        +manage_playlist_songs(playlist_id: str, operation: str)
        +share_playlist(playlist_id: str): str
    }
    
    class SearchService {
        -search_engine: SearchEngine
        -source_aggregator: SourceAggregator
        +search_music(query: str, filters: SearchFilters)
        +get_recommendations(user_id: str)
        +discover_trending(): List[Song]
    }
    
    class UserService {
        -user_manager: UserManager
        +get_user_profile(user_id: str)
        +update_user_preferences(user_id: str, prefs: dict)
        +manage_user_data(user_id: str, operation: str)
        +sync_user_data(user_id: str)
    }
```

### 命令处理架构

```mermaid
graph TD
    A[Discord消息] --> B{命令类型判断}
    B -->|!music| C[音乐命令处理器]
    B -->|!playlist| D[歌单命令处理器]
    B -->|!search| E[搜索命令处理器]
    B -->|!user| F[用户命令处理器]
    
    C --> G[PlayerService]
    D --> H[PlaylistService]
    E --> I[SearchService]
    F --> J[UserService]
    
    G --> K[响应生成器]
    H --> K
    I --> K
    J --> K
    
    K --> L[Discord消息回复]
```

## 异步处理架构

### 事件驱动模型

```mermaid
sequenceDiagram
    participant U as 用户
    participant C as 命令处理器
    participant S as 服务层
    participant E as 事件系统
    participant W as 工作队列
    
    U->>C: 发送命令
    C->>S: 调用服务方法
    S->>E: 发布事件
    E->>W: 添加异步任务
    W-->>S: 执行后台任务
    S-->>C: 返回初步结果
    C-->>U: 发送响应
    
    Note over W: 异步处理音频下载、缓存等
    W->>E: 任务完成事件
    E->>C: 通知更新
    C->>U: 发送状态更新
```

### 音频流处理

```mermaid
graph LR
    A[音频源URL] --> B[HTTP客户端]
    B --> C[流式下载]
    C --> D[格式检测]
    D --> E[音频解码]
    E --> F[缓存管理]
    F --> G[Discord音频流]
    G --> H[语音频道播放]
    
    C --> I[进度监控]
    E --> J[质量检测]
    F --> K[磁盘管理]
```

## 错误处理架构

### 异常处理层次

```mermaid
graph TD
    A[业务异常] --> B[服务层异常处理]
    C[网络异常] --> D[适配器层异常处理]
    E[系统异常] --> F[框架层异常处理]
    
    B --> G[错误记录]
    D --> G
    F --> G
    
    G --> H[用户友好消息]
    G --> I[错误恢复策略]
    G --> J[监控告警]
```

### 容错机制

- **音源切换**: 当主音源不可用时自动切换到备用音源
- **自动重试**: 网络错误时自动重试，采用指数退避策略
- **降级处理**: 在系统负载过高时提供降级服务
- **缓存回退**: 利用缓存数据提供离线播放能力

## 性能优化架构

### 缓存策略

```mermaid
graph TD
    A[请求] --> B{缓存检查}
    B -->|命中| C[返回缓存数据]
    B -->|未命中| D[数据源查询]
    D --> E[更新缓存]
    E --> F[返回数据]
    
    G[缓存层次]
    H[内存缓存 - 热点数据]
    I[Redis缓存 - 会话数据]
    J[文件缓存 - 音频文件]
    K[数据库 - 持久化数据]
    
    G --> H
    G --> I
    G --> J
    G --> K
```

### 并发控制

- **连接池管理**: HTTP客户端连接池优化
- **异步IO**: 使用asyncio实现高并发处理
- **队列限流**: 防止过多并发请求导致系统过载
- **资源监控**: 实时监控内存、网络、磁盘使用情况

## 扩展性架构

### 插件化设计

```mermaid
graph TD
    A[核心系统] --> B[插件接口]
    B --> C[音源插件]
    B --> D[格式插件]
    B --> E[存储插件]
    B --> F[UI插件]
    
    C --> G[Bilibili插件]
    C --> H[Netease插件]
    C --> I[第三方插件]
    
    D --> J[MP3插件]
    D --> K[FLAC插件]
    
    E --> L[SQLite插件]
    E --> M[PostgreSQL插件]
```

### API扩展能力

- **RESTful API**: 提供标准HTTP API接口
- **WebSocket API**: 实时状态推送和双向通信
- **Webhook**: 事件通知和第三方集成
- **SDK**: 提供多语言SDK支持

## 安全架构

### 数据安全

```mermaid
graph TD
    A[用户数据] --> B[加密存储]
    C[API密钥] --> D[安全管理]
    E[网络传输] --> F[TLS加密]
    G[访问控制] --> H[权限验证]
    
    B --> I[数据库加密]
    D --> J[密钥轮换]
    F --> K[证书管理]
    H --> L[角色控制]
```

### 安全策略

- **数据加密**: 敏感数据使用AES加密存储
- **访问控制**: 基于角色的权限控制系统
- **API安全**: API密钥管理和速率限制
- **内容过滤**: 违规内容检测和过滤机制
- **审计日志**: 完整的操作审计和日志记录

这个架构设计确保了 BotPlayer 插件能够提供完整、可靠、可扩展的音乐播放器功能，同时保持良好的性能和用户体验。
