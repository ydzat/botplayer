# BotPlayer

功能强大的 Discord 音乐播放器插件，支持多音源搜索播放、歌单管理和 WebDAV 云同步。

## 功能特性

- 🎵 **音源支持**：当前支持 Bilibili 音源（更多音源正在开发中）
- 🎧 **Discord 语音播放**：自动加入语音频道，智能播放控制
- 📋 **播放队列管理**：支持队列、随机播放、循环模式
- 💾 **智能音频缓存**：自动缓存音频文件，提升播放体验
- 🎶 **歌单导入管理**：支持 MusicFree、M3U、PLS 格式歌单导入
- ☁️ **WebDAV 云同步**：支持多用户歌单云端同步管理
- 🚀 **自动播放**：导入歌单后可直接播放，无需手动操作

## 安装

配置完成 [LangBot](https://github.com/RockChinQ/LangBot) 主程序后即可到插件管理页面安装  
或查看详细的[插件安装说明](https://docs.langbot.app/plugin/plugin-intro.html#%E6%8F%92%E4%BB%B6%E7%94%A8%E6%B3%95)

## 使用指南

### 🎵 基本播放命令
- `!play <歌曲名>` - 搜索并播放歌曲（自动加入语音频道）
- `!pause` - 暂停播放
- `!resume` - 恢复播放
- `!stop` - 停止播放并清空队列
- `!skip` - 跳过当前歌曲
- `!volume <1-100>` - 调整播放音量

### 📋 播放队列管理
- `!queue` - 查看当前播放队列
- `!queue add <歌曲名>` - 添加歌曲到队列
- `!queue clear` - 清空播放队列
- `!shuffle` - 开启/关闭随机播放
- `!repeat <模式>` - 设置循环模式 (off/all/one)

### 🎶 歌单功能
- `!playlist list` - 查看所有歌单
- `!playlist create <歌单名>` - 创建新歌单
- `!playlist import <文件名>` - 导入歌单文件 (MusicFree/M3U/PLS)
- `!playlist play <歌单名>` - 播放指定歌单（自动加入语音频道并开始播放）
- `!playlist add <歌单名> <歌曲名>` - 添加歌曲到歌单
- `!playlist remove <歌单名>` - 删除歌单

### 🔍 搜索和信息
- `!search <关键词>` - 搜索歌曲
- `!nowplaying` - 查看当前播放信息
- `!cache` - 查看缓存状态
- `!status` - 查看播放器状态

### 👤 用户管理
- `!reg name <用户名>` - 注册用户（用于 WebDAV 功能）

### ☁️ WebDAV 云同步
- `!webdav status` - 查看 WebDAV 同步状态
- `!webdav sync` - 手动同步歌单
- `!webdav list` - 查看云端可用歌单

### ❓ 帮助
- `!help` - 显示完整帮助信息

## WebDAV 用户配置管理

### 工作流程

#### 1. 用户注册
用户在 Discord 中使用以下命令注册：
```
!reg name 张三
```

系统会自动：
- 记录用户的 Discord ID 和自定义用户名
- 在 `data/user_configs/users.json` 中保存用户信息
- 在 `data/user_configs/webdav_configs.yaml` 中创建配置占位符

#### 2. 管理员配置 WebDAV
注册成功后，管理员需要在 `data/user_configs/webdav_configs.yaml` 中为用户配置 WebDAV 信息：

```yaml
张三:  # 用户注册时的用户名
  enabled: true
  server_url: "https://nextcloud.example.com/remote.php/dav/files/zhangsan/"
  username: "zhangsan"
  password: "your_webdav_password"
  playlist_path: "Music/Playlists/"
  auto_sync: true
  last_sync: ""
```

#### 3. 用户使用
配置完成后，用户可以使用：
- `!webdav status` - 查看 WebDAV 状态
- `!webdav sync` - 同步歌单
- `!webdav list` - 查看可用歌单

### 安全特性

1. **分离敏感信息**: 用户无法直接设置 WebDAV 凭据
2. **管理员控制**: 只有管理员能在服务器文件中配置 WebDAV
3. **用户隔离**: 每个用户的配置独立，互不影响
4. **审计跟踪**: 所有操作都有日志记录

### 文件结构

```
data/user_configs/
├── users.json                 # 用户注册信息
├── webdav_configs.yaml        # WebDAV 配置（管理员编辑）
└── logs/                      # 操作日志
    └── webdav_sync.log
```

### 支持的歌单格式

- **MusicFree 备份文件** (.json) - 支持完整的歌单信息导入
- **M3U 播放列表** (.m3u, .m3u8) - 标准音频播放列表格式
- **PLS 播放列表** (.pls) - Winamp 播放列表格式

### WebDAV 服务器建议

推荐使用以下 WebDAV 服务：
- **Nextcloud** - 开源私有云解决方案（✅ 已测试兼容）
- **ownCloud** - 企业级文件同步服务（理论兼容）
- **坚果云** - 国内稳定的云存储服务（理论兼容）
- **阿里云盘** - 支持 WebDAV 接口（理论兼容）

> 💡 目前仅在 Nextcloud 上进行了完整测试，其他 WebDAV 服务理论上兼容，如遇问题请提 Issue。

## 注意事项

- ✅ 仅支持 Discord 平台使用
- ✅ 需要机器人有语音频道权限
- ✅ 首次使用时会自动下载音频文件
- ✅ 支持自动加入语音频道和自动播放
- ✅ 歌单导入后可直接使用 `!playlist play` 命令播放
- ⚠️ WebDAV 配置需要管理员手动设置
- ⚠️ 大文件下载可能需要较长时间，请耐心等待

## 已知限制

- 🎵 **音源限制**：目前仅支持 Bilibili 音源，如需其他音源请提 [Issue](https://github.com/your-repo/issues)
- ☁️ **WebDAV 兼容性**：目前仅在 Nextcloud 上完整测试，其他云盘理论兼容，如遇问题请提 [Issue](https://github.com/your-repo/issues)
- 👥 **并发支持**：未进行多人并发测试，可能存在不可预料的错误，如遇问题请提 [Issue](https://github.com/your-repo/issues)
- 🧪 **功能完整性**：部分播放指令未进行全面测试，如遇问题请提 [Issue](https://github.com/your-repo/issues)

## 问题反馈

如果你在使用过程中遇到任何问题，请：

1. 📋 **提交 Issue** - 详细描述问题和重现步骤
2. 🔧 **贡献代码** - 欢迎提交 Pull Request 来改进项目
3. 📚 **查看日志** - 控制台输出通常包含有用的错误信息

> 💡 **开发者说明**：由于时间有限，暂时无法进行更深入的修复和优化。如果你遇到任何问题，请提 Issue，我会在有空的时候处理。当然，也非常欢迎你直接贡献代码，提交 PR！
