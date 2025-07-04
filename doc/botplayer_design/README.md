# BotPlayer 插件设计文档

## 概述

BotPlayer 是一个为 LangBot 框架设计的简洁音乐播放器插件，参考 MusicFree 的核心理念。该插件提供多音源支持、歌单导入、播放队列等基本播放器功能，旨在为 Discord 服务器提供实用的音乐播放体验。

## 核心功能

### 主要特性
- **多音源支持**: 支持 bilibili、网易云、酷狗、QQ音乐、YouTube等多个音源平台
- **歌单导入**: 通过 URL 导入 JSON 格式歌单（如 MusicFreeBackup.json）
- **播放队列**: 基本的播放队列功能
- **播放模式**: 顺序播放、随机播放、循环播放
- **音乐搜索**: 跨平台音乐搜索
- **插件化音源**: 基于 MusicFree 插件生态系统

### 核心目标
- 简单易用的音乐播放功能
- 支持个人歌单管理
- 多音源整合
- 稳定的音频播放

## 功能架构

### 系统组件
```
Discord 命令层
    ↓
播放器核心
    ↓
音源适配器
    ↓
本地存储
```

### 核心模块
- **播放器引擎**: 音频播放和基本控制
- **音源适配器**: 多平台音源接入
- **歌单管理**: 简单的歌单导入和存储
- **搜索功能**: 跨平台音乐搜索

## 技术特色

### 多音源支持
- 基于 MusicFree 插件生态系统
- 支持 JavaScript 插件加载
- 统一的音频格式处理
- 自动音源管理和更新

### 支持的音源平台
**主流音乐平台**:
- bilibili (版本 0.2.3)
- 网易云音乐 (版本 0.2.3)
- 酷狗音乐 (版本 0.1.4)
- QQ音乐 (版本 0.1.0)
- 酷我音乐 (版本 0.1.0)

**国际平台**:
- YouTube (版本 0.0.1)
- Audiomack (版本 0.0.2)

**特色平台**:
- 猫耳FM (版本 0.1.4)
- 5sing (版本 0.0.3)
- 快手 (版本 0.0.2)
- 音悦台 (版本 0.0.1)

### 基本用户体验
- 实时播放状态显示
- 简单的播放控制
- 基本的歌单管理

## 项目结构

```
plugins/botplayer/
├── __init__.py                      # 插件包初始化
├── main.py                          # 插件主文件
├── manifest.yaml                    # 插件清单文件
├── requirements.txt                 # 依赖声明
├── config.yaml                      # 配置文件
├── plugins.json                     # 音源插件列表
├── data/                            # 数据存储目录
│   ├── playlists/                   # 歌单存储
│   ├── audio_cache/                 # 统一音频缓存目录
│   │   ├── index.db                 # 音频文件索引数据库
│   │   └── files/                   # 音频文件存储
│   │       ├── 001.opus             # 音频文件(按ID命名)
│   │       ├── 002.opus
│   │       └── ...
│   └── plugins/                     # 下载的音源插件
├── sources/                         # 音源管理模块
│   ├── __init__.py
│   ├── loader.py                    # 插件加载器
│   ├── manager.py                   # 音源管理器
│   └── adapter.py                   # 插件适配器
├── audio/                           # 音频处理模块
│   ├── __init__.py
│   ├── downloader.py                # 音频下载器
│   ├── cache_manager.py             # 缓存管理器
│   └── converter.py                 # 音频格式转换
└── doc/                             # 设计文档
    └── README.md                    # 项目说明
```

## 主要功能

### 音乐播放功能
- **播放控制**: 播放、暂停、停止、上一首、下一首
- **播放模式**: 顺序播放、随机播放、循环播放
- **实时状态**: 显示当前播放歌曲和队列

### 歌单管理功能
- **歌单导入**: 通过 URL 导入 JSON 格式歌单
- **歌单播放**: 播放导入的歌单
- **简单编辑**: 添加、删除歌曲

### 音乐搜索功能
- **跨平台搜索**: 搜索多个音源平台
- **搜索过滤**: 按歌手、专辑等筛选

## 命令系统

### 基本命令
```
!play <歌曲名> - 搜索并播放音乐
!queue - 查看播放队列
!skip - 跳过当前歌曲
!pause - 暂停播放
!resume - 恢复播放
!stop - 停止播放
!shuffle - 随机播放模式
!repeat - 循环播放模式
```

### 歌单命令
```
!playlist import <JSON_URL> - 导入歌单
!playlist list - 查看歌单
!playlist play <歌单名> - 播放歌单
```

### 搜索命令
```
!search <关键词> - 搜索音乐
!search bilibili <关键词> - 在指定平台搜索
!sources - 查看可用音源
!sources update - 更新音源插件
```

## 使用场景

### 基本应用
- **个人音乐**: 导入个人歌单并播放
- **多平台搜索**: 在不同音源平台搜索音乐
- **群组音乐**: 为 Discord 频道播放背景音乐
- **插件化扩展**: 通过更新 plugins.json 添加新音源

### 歌单导入示例
```
!playlist import https://github.com/user/playlist.json
!playlist import https://gist.githubusercontent.com/user/id/raw/playlist.json
```

### 音源使用示例
```
!search 春日影                    # 搜索所有平台
!search bilibili 春日影           # 指定 bilibili 平台搜索
!sources                          # 查看可用音源
!sources update                   # 更新音源插件
!play 春日影                      # 播放音乐(自动缓存管理)
!cache status                     # 查看缓存状态
!cache clean                      # 手动清理缓存
```

## 简单工作流程

### 导入歌单
1. 用户提供 JSON 格式的歌单 URL
2. 系统下载并解析歌单
3. 保存到本地数据库

### 播放音乐
1. 用户搜索或选择歌曲
2. 系统检查音频缓存
   - 如果已缓存: 直接播放，更新访问时间
   - 如果未缓存: 后台下载音频，先播放在线流
3. 开始播放并更新状态

### 缓存管理
1. 系统自动监控缓存大小
2. 超过限制时自动清理最久未用的音频
3. 删除歌曲时智能管理引用计数

这就是一个简单实用且高效的音乐播放器插件设计，专注于核心功能，同时优化了存储和缓存管理。

## 数据结构

### 歌曲信息
```json
{
  "id": "unique_song_id",
  "title": "歌曲标题",
  "artist": "艺术家",
  "album": "专辑名称",
  "platform": "bilibili",
  "url": "播放链接",
  "duration": 240,
  "artwork": "封面图片URL",
  "audio_hash": "sha256_hash",          # 音频内容哈希
  "cached_file": "001.opus",            # 缓存文件名
  "file_size": 5242880                  # 文件大小(字节)
}
```

### 音频缓存索引
```json
{
  "audio_hash": "sha256_hash_value",
  "file_path": "files/001.opus",
  "file_size": 5242880,
  "format": "opus",
  "bitrate": "128k",
  "duration": 240,
  "reference_count": 3,                 # 引用计数
  "last_accessed": "2025-07-04T10:30:00Z",
  "created_at": "2025-07-04T09:00:00Z",
  "songs": [                            # 引用此音频的歌曲ID列表
    "song_id_1",
    "song_id_2", 
    "song_id_3"
  ]
}
```

### 音源插件信息
```json
{
  "name": "bilibili",
  "url": "https://gitee.com/maotoumao/MusicFreePlugins/raw/v0.1/dist/bilibili/index.js",
  "version": "0.2.3",
  "enabled": true,
  "last_update": "2025-07-04"
}
```

### 播放队列
```json
{
  "current": 0,
  "mode": "sequence",
  "songs": ["song1", "song2"]
}
```

## 技术实现

### 音源插件系统
基于现有的 MusicFree 插件生态系统，直接使用 JavaScript 插件：

```python
class PluginLoader:
    def load_from_url(self, plugin_url: str) -> Plugin:
        """从 URL 加载 JavaScript 插件"""
        pass
    
    def execute_plugin_function(self, plugin: Plugin, function: str, args: dict):
        """执行插件的特定功能"""
        pass

class MusicSourceManager:
    def __init__(self):
        self.plugins = {}
        self.loader = PluginLoader()
    
    async def search(self, query: str, platform: str = None) -> List[Song]:
        """搜索音乐，可指定平台"""
        pass
    
    async def get_play_url(self, song_id: str, platform: str) -> str:
        """获取播放链接"""
        pass
```

### 音频缓存管理系统
```python
class AudioCacheManager:
    def __init__(self, cache_dir: str, max_size: int = 10737418240):  # 10GB
        self.cache_dir = cache_dir
        self.max_size = max_size
        self.index_db = f"{cache_dir}/index.db"
    
    async def get_audio_file(self, song: Song) -> str:
        """获取音频文件路径，如果不存在则下载"""
        audio_hash = await self.calculate_audio_hash(song)
        
        # 检查是否已缓存
        cached_file = await self.find_cached_audio(audio_hash)
        if cached_file:
            await self.update_access_time(audio_hash)
            return cached_file
        
        # 下载并缓存音频
        return await self.download_and_cache(song, audio_hash)
    
    async def calculate_audio_hash(self, song: Song) -> str:
        """计算音频内容哈希值"""
        # 基于歌曲标题、艺术家、时长等信息生成哈希
        content = f"{song.title}|{song.artist}|{song.duration}|{song.platform}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    async def download_and_cache(self, song: Song, audio_hash: str) -> str:
        """下载音频并缓存"""
        # 1. 获取音频流URL
        audio_url = await self.get_audio_stream_url(song)
        
        # 2. 使用yt-dlp下载仅音频
        output_file = f"{self.cache_dir}/files/{audio_hash}.opus"
        await self.download_audio_only(audio_url, output_file)
        
        # 3. 更新索引
        await self.update_cache_index(audio_hash, song, output_file)
        
        # 4. 检查存储限制
        await self.cleanup_if_needed()
        
        return output_file
    
    async def download_audio_only(self, url: str, output_file: str):
        """仅下载音频，支持视频URL"""
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_file,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'opus',
                'preferredquality': '128',
            }],
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await ydl.download([url])
    
    async def cleanup_if_needed(self):
        """检查存储限制，必要时清理旧文件"""
        total_size = await self.get_total_cache_size()
        
        if total_size > self.max_size:
            # 按最后访问时间排序，删除最久未使用的文件
            old_files = await self.get_files_by_last_access()
            
            for file_info in old_files:
                if await self.can_delete_file(file_info['audio_hash']):
                    await self.delete_cached_file(file_info['audio_hash'])
                    total_size -= file_info['file_size']
                    
                    if total_size <= self.max_size * 0.8:  # 清理到80%
                        break
    
    async def can_delete_file(self, audio_hash: str) -> bool:
        """检查文件是否可以删除（不在任何歌单中）"""
        # 查询所有歌单，检查是否还有引用
        return await self.get_reference_count(audio_hash) == 0
    
    async def remove_song_reference(self, song_id: str):
        """移除歌曲引用，如果无引用则删除缓存文件"""
        audio_hash = await self.get_audio_hash_by_song_id(song_id)
        if audio_hash:
            await self.decrease_reference_count(audio_hash, song_id)
            
            # 如果没有其他引用，删除缓存文件
            if await self.get_reference_count(audio_hash) == 0:
                await self.delete_cached_file(audio_hash)
```

### 插件管理
```python
class PluginManager:
    def update_plugins(self):
        """从 plugins.json 更新插件"""
        pass
    
    def get_available_sources(self) -> List[str]:
        """获取可用音源列表"""
        pass
```

### 核心依赖
- **LangBot**: 插件框架
- **Discord.py[voice]**: Discord 语音支持
- **aiohttp**: HTTP 客户端
- **sqlite3**: 数据存储
- **PyExecJS**: JavaScript 执行环境（用于运行音源插件）
- **yt-dlp**: 音频下载（支持视频网站音频提取）
- **FFmpeg**: 音频格式转换
- **requests**: 插件下载

## 配置文件

```yaml
# config.yaml
# 音源配置
sources:
  auto_update: true              # 自动更新插件
  update_interval: 86400         # 更新间隔(秒)
  enabled_sources:               # 启用的音源
    - "bilibili"
    - "网易"
    - "酷狗"
    - "QQ"
  
  # 插件优先级 (搜索时的优先顺序)
  priority:
    - "bilibili"
    - "网易"
    - "酷狗"

# 音频缓存配置
audio_cache:
  max_size: 10737418240          # 最大缓存大小 (10GB)
  cleanup_threshold: 0.8         # 清理阈值 (80%)
  audio_format: "opus"           # 统一音频格式
  audio_bitrate: "128k"          # 音频比特率
  download_timeout: 300          # 下载超时时间(秒)

# 数据存储
storage:
  path: "data/botplayer.db"
  audio_cache_path: "data/audio_cache"

# 歌单导入安全设置
playlist_import:
  allowed_domains:
    - "github.com"
    - "gist.githubusercontent.com"
    - "gitee.com"
  max_size: "5MB"
  timeout: 30

# 插件配置
plugins:
  source_file: "plugins.json"     # 插件列表文件
  cache_dir: "data/plugins"       # 插件缓存目录
  js_timeout: 10                  # JavaScript 执行超时

# FFmpeg 配置
ffmpeg:
  path: "/usr/bin/ffmpeg"         # FFmpeg 可执行文件路径
  audio_codec: "libopus"          # 音频编码器
  audio_bitrate: "128k"           # 比特率
```

## 音频缓存管理

### 智能缓存策略
- **统一存储**: 所有用户共享同一个音频缓存池
- **去重机制**: 相同音频只存储一份，通过哈希值识别
- **引用计数**: 跟踪每个音频文件的使用情况
- **LRU清理**: 基于最后访问时间的自动清理机制

### 缓存工作流程

#### 播放请求处理
```python
# 播放音频的完整流程
1. 用户请求播放歌曲
2. 计算歌曲音频哈希值
3. 检查缓存中是否存在
   - 存在: 直接返回文件路径，更新访问时间
   - 不存在: 执行下载流程
4. 下载流程:
   - 获取音源插件提供的URL
   - 使用yt-dlp提取音频流
   - 转换为统一格式(opus, 128k)
   - 保存到缓存目录
   - 更新索引数据库
5. 检查存储限制，必要时清理
```

#### 音频下载优化
- **仅音频下载**: 对于视频网站，仅提取音频流
- **格式统一**: 转换为 opus 格式，节省空间
- **比特率控制**: 统一 128k 比特率，平衡质量和大小
- **并发控制**: 限制同时下载数量，避免资源竞争

#### 存储空间管理
```python
# 自动清理策略
def cleanup_strategy():
    if total_size > max_size:
        # 1. 获取所有缓存文件，按最后访问时间排序
        files = get_files_sorted_by_last_access()
        
        # 2. 依次检查是否可删除
        for file in files:
            if reference_count == 0:  # 无任何歌单引用
                delete_file(file)
                if total_size <= max_size * 0.8:
                    break
```

### 引用计数管理

#### 添加歌曲时
1. 计算音频哈希值
2. 检查缓存中是否存在
3. 增加引用计数
4. 如果不存在，下载并初始化引用计数为1

#### 删除歌曲时
1. 减少对应音频文件的引用计数
2. 如果引用计数为0，标记为可删除
3. 在下次清理时删除无引用的文件

#### 数据一致性
- **事务处理**: 引用计数的修改使用数据库事务
- **定期校验**: 定期检查引用计数与实际使用情况的一致性
- **容错机制**: 处理异常情况下的数据不一致

### 缓存索引结构
```sql
CREATE TABLE audio_cache (
    audio_hash TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    format TEXT NOT NULL,
    bitrate TEXT NOT NULL,
    duration INTEGER,
    reference_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE song_audio_refs (
    song_id TEXT,
    audio_hash TEXT,
    PRIMARY KEY (song_id, audio_hash),
    FOREIGN KEY (audio_hash) REFERENCES audio_cache(audio_hash)
);

CREATE INDEX idx_audio_last_accessed ON audio_cache(last_accessed);
CREATE INDEX idx_audio_ref_count ON audio_cache(reference_count);
```

### 性能优化
- **异步下载**: 音频下载不阻塞用户操作
- **预缓存**: 对于歌单，可以后台预下载
- **压缩存储**: 使用高效的音频编码格式
- **快速查找**: 基于哈希值的O(1)查找效率
