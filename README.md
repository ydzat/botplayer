# BotPlayer

简单的 Discord 音乐播放器插件，支持多音源搜索和播放。

## 功能特性

- 🎵 多音源支持（Bilibili、网易云音乐、本地文件）
- 🎧 Discord 语音频道播放
- 📋 播放队列管理
- 💾 智能音频缓存
- 🎶 歌单导入和管理

## 安装

配置完成 [LangBot](https://github.com/RockChinQ/LangBot) 主程序后即可到插件管理页面安装  
或查看详细的[插件安装说明](https://docs.langbot.app/plugin/plugin-intro.html#%E6%8F%92%E4%BB%B6%E7%94%A8%E6%B3%95)

## 使用

### 基本播放
- `!play <歌曲名>` - 播放歌曲
- `!pause` - 暂停播放
- `!resume` - 恢复播放
- `!stop` - 停止播放
- `!skip` - 跳过当前歌曲

### 队列管理
- `!queue` - 查看播放队列
- `!shuffle` - 随机播放
- `!repeat <模式>` - 循环模式 (off/all/one)

### 其他功能
- `!search <关键词>` - 搜索歌曲
- `!playlist list` - 查看歌单
- `!cache` - 查看缓存状态
- `!help` - 显示帮助信息

## 注意事项

- 仅支持 Discord 平台使用
- 需要机器人有语音频道权限
- 首次使用时会自动下载音频文件
