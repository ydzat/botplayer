import os
import asyncio
import traceback
from typing import Optional, List
from pkg.plugin.context import register, handler, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *
from pkg.platform.sources.discord import VoiceConnectionError, VoicePermissionError, VoiceNetworkError

# 导入核心模块
from .core.player import BotPlayerCore
from .core.models import Song, PlayMode
from .core.user_webdav_manager import UserWebDAVManager


# 注册插件
@register(name="BotPlayer", description="多音源Discord音乐播放器，支持歌单导入和智能缓存", version="1.0.0", author="ydzat")
class BotPlayerPlugin(BasePlugin):

    def __init__(self, host: APIHost):
        super().__init__(host)
        self.player_core = None
        self.guild_players = {}  # 每个服务器的播放器实例
        self.webdav_manager = None
        self._playing_lock = asyncio.Lock()  # 防止并发播放的锁
        self._is_processing_next = False     # 标记是否正在处理下一首
        self._main_loop = None               # 主事件循环引用
        
    async def initialize(self):
        """异步初始化"""
        try:
            # 保存主事件循环引用
            self._main_loop = asyncio.get_event_loop()
            
            # 获取插件目录
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(plugin_dir, "data")
            
            # 初始化播放器核心
            self.player_core = BotPlayerCore(data_dir=data_dir)
            
            # 初始化用户 WebDAV 管理器
            import yaml
            config_file = os.path.join(plugin_dir, "config.yaml")
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    webdav_config = config.get('botplayer', {}).get('webdav', {})
                    if webdav_config.get('enabled', False):
                        self.webdav_manager = UserWebDAVManager(data_dir)
            
            print("BotPlayer initialized successfully")
            
        except Exception as e:
            print(f"Error initializing BotPlayer: {e}")
            traceback.print_exc()

    def get_config(self, key: str, default=None):
        """获取配置值"""
        try:
            # 从host获取配置，如果没有则使用默认值
            return getattr(self.host, 'config', {}).get(key, default)
        except:
            return default

    # 当收到消息时触发
    @handler(PersonMessageReceived)
    @handler(GroupMessageReceived)
    async def message_received(self, ctx: EventContext):
        # 检查是否是 Discord 平台
        if ctx.event.query.adapter.__class__.__name__ != 'DiscordAdapter':
            return
        
        msg = str(ctx.event.message_chain).strip()
        
        # 检查是否是音乐相关命令
        if msg.startswith("!"):
            if any(msg.startswith(cmd) for cmd in [
                "!play", "!search", "!queue", "!skip", "!pause", "!resume", 
                "!stop", "!shuffle", "!repeat", "!playlist", "!cache", 
                "!sources", "!volume", "!now", "!leave", "!help", "!webdav", "!reg"
            ]):
                ctx.prevent_default()
                await self.handle_music_command(ctx, msg)

    async def handle_music_command(self, ctx: EventContext, command: str):
        """处理音乐命令"""
        try:
            if not self.player_core:
                await self.reply_message(ctx, "❌ 播放器未初始化")
                return
                
            adapter = ctx.event.query.adapter
            message_event = ctx.event.query.message_event
            
            if not hasattr(message_event, 'source_platform_object') or message_event.source_platform_object is None:
                await self.reply_message(ctx, "❌ 无法获取 Discord 消息对象")
                return
            
            discord_msg = message_event.source_platform_object
            guild_id = discord_msg.guild.id if discord_msg.guild else None
            user_id = discord_msg.author.id
            
            if not guild_id:
                await self.reply_message(ctx, "❌ 此命令只能在服务器中使用")
                return

            # 解析命令
            parts = command.split()
            cmd = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []

            # 基本播放命令
            if cmd == "!play":
                await self.play_command(ctx, adapter, guild_id, user_id, args)
            elif cmd == "!search":
                await self.search_command(ctx, args)
            elif cmd == "!pause":
                await self.pause_command(ctx)
            elif cmd == "!resume":
                await self.resume_command(ctx)
            elif cmd == "!stop":
                await self.stop_command(ctx, adapter, guild_id)
            elif cmd == "!skip":
                await self.skip_command(ctx, adapter, guild_id, user_id)
            elif cmd == "!queue":
                await self.queue_command(ctx)
            elif cmd == "!shuffle":
                await self.shuffle_command(ctx)
            elif cmd == "!repeat":
                await self.repeat_command(ctx, args)
            elif cmd == "!volume":
                await self.volume_command(ctx, args)
            elif cmd == "!now":
                await self.now_playing_command(ctx)
            elif cmd == "!leave":
                await self.leave_command(ctx, adapter, guild_id)
            
            # 歌单命令
            elif cmd == "!playlist":
                await self.playlist_command(ctx, args)
            
            # 缓存命令
            elif cmd == "!cache":
                await self.cache_command(ctx, args)
            
            # 音源命令
            elif cmd == "!sources":
                await self.sources_command(ctx)
            
            # WebDAV 个人配置命令
            # WebDAV 命令
            elif cmd == "!webdav":
                await self.webdav_command(ctx, args)
            
            # 用户注册命令
            elif cmd == "!reg":
                await self.register_command(ctx, args)
            
            # 帮助命令
            elif cmd == "!help":
                await self.help_command(ctx)
            
            else:
                await self.help_command(ctx)
                
        except Exception as e:
            await self.reply_message(ctx, f"❌ 命令执行出错: {str(e)}")
            print(f"Error in music command: {e}")
            traceback.print_exc()

    async def play_command(self, ctx: EventContext, adapter, guild_id: int, user_id: int, args: List[str]):
        """播放命令"""
        if not args:
            await self.reply_message(ctx, "❌ 请提供歌曲名称\n用法: `!play <歌曲名>` 或 `!play <歌曲名> <音源>`")
            return
        
        # 确保连接到语音频道
        voice_connected = await self.ensure_voice_connection(ctx, adapter, guild_id, user_id)
        if not voice_connected:
            return
        
        query = " ".join(args[:-1]) if len(args) > 1 and args[-1] in ['bilibili', 'netease', 'local'] else " ".join(args)
        platform = args[-1] if len(args) > 1 and args[-1] in ['bilibili', 'netease', 'local'] else None
        
        await self.reply_message(ctx, f"🔍 正在搜索: {query}...")
        
        try:
            # 智能播放
            song = await self.player_core.smart_play(query)
            if song:
                # 获取音频文件并播放
                audio_file = await self.player_core.cache_manager.get_audio_file(song)
                if audio_file:
                    success = await self.play_audio_file(ctx, adapter, guild_id, audio_file)
                    if success:
                        await self.reply_message(ctx, 
                            f"🎵 正在播放:\n"
                            f"**{song.title}**\n"
                            f"👤 {song.artist}\n"
                            f"📀 {song.album}\n"
                            f"🎧 {song.platform}"
                        )
                    else:
                        await self.reply_message(ctx, "❌ 音频播放失败")
                else:
                    await self.reply_message(ctx, "❌ 无法获取音频文件")
            else:
                await self.reply_message(ctx, f"❌ 未找到歌曲: {query}")
                
        except Exception as e:
            await self.reply_message(ctx, f"❌ 播放失败: {str(e)}")

    async def search_command(self, ctx: EventContext, args: List[str]):
        """搜索命令"""
        if not args:
            await self.reply_message(ctx, "❌ 请提供搜索关键词\n用法: `!search <关键词>`")
            return
        
        query = " ".join(args)
        await self.reply_message(ctx, f"🔍 正在搜索: {query}...")
        
        try:
            results = await self.player_core.search_songs(query, limit=5)
            if results:
                response = f"🎵 搜索结果 ({len(results)}):\n\n"
                for i, song in enumerate(results, 1):
                    duration_str = f"{song.duration // 60}:{song.duration % 60:02d}" if song.duration > 0 else "未知"
                    response += f"**{i}.** {song.title}\n"
                    response += f"　　👤 {song.artist} | 📀 {song.album}\n"
                    response += f"　　⏱️ {duration_str} | 🎧 {song.platform}\n\n"
                
                response += "使用 `!play <歌曲名>` 播放歌曲"
                await self.reply_message(ctx, response)
            else:
                await self.reply_message(ctx, f"❌ 未找到相关歌曲: {query}")
                
        except Exception as e:
            await self.reply_message(ctx, f"❌ 搜索失败: {str(e)}")

    async def pause_command(self, ctx: EventContext):
        """暂停命令"""
        try:
            self.player_core.pause()
            await self.reply_message(ctx, "⏸️ 播放已暂停")
        except Exception as e:
            await self.reply_message(ctx, f"❌ 暂停失败: {str(e)}")

    async def resume_command(self, ctx: EventContext):
        """恢复播放命令"""
        try:
            self.player_core.resume()
            await self.reply_message(ctx, "▶️ 播放已恢复")
        except Exception as e:
            await self.reply_message(ctx, f"❌ 恢复播放失败: {str(e)}")

    async def stop_command(self, ctx: EventContext, adapter, guild_id: int):
        """停止命令"""
        try:
            # 停止Discord语音播放
            voice_client = await adapter.get_voice_client(guild_id)
            if voice_client and voice_client.is_playing():
                voice_client.stop()
            
            # 停止播放器
            self.player_core.stop()
            self.player_core.clear_queue()
            await self.reply_message(ctx, "⏹️ 播放已停止，队列已清空")
            
        except Exception as e:
            await self.reply_message(ctx, f"❌ 停止失败: {str(e)}")

    async def skip_command(self, ctx: EventContext, adapter, guild_id: int, user_id: int):
        """跳过命令"""
        try:
            # 防止重复跳过
            if self._is_processing_next:
                await self.reply_message(ctx, "⚠️ 正在处理播放队列，请稍等...")
                return
            
            voice_client = await adapter.get_voice_client(guild_id)
            if voice_client and voice_client.is_playing():
                print(f"🎵 用户请求跳过当前歌曲")
                voice_client.stop()  # 这会触发 after_playing 回调，自动播放下一首
                await self.reply_message(ctx, "⏭️ 已跳过当前歌曲")
            else:
                await self.reply_message(ctx, "❌ 当前没有正在播放的歌曲")
        except Exception as e:
            await self.reply_message(ctx, f"❌ 跳过失败: {str(e)}")
            print(f"Error in skip command: {e}")
            import traceback
            traceback.print_exc()

    async def queue_command(self, ctx: EventContext):
        """队列命令"""
        try:
            queue_info = self.player_core.get_queue_info()
            current_song = self.player_core.player_state.current_song
            
            if not current_song and queue_info['total_songs'] == 0:
                await self.reply_message(ctx, "📋 播放队列为空")
                return
            
            response = "📋 播放队列:\n\n"
            
            if current_song:
                response += f"🎵 正在播放:\n**{current_song.title}** - {current_song.artist}\n\n"
            
            if queue_info['total_songs'] > 0:
                response += f"⏭️ 队列中的歌曲 ({queue_info['total_songs']}):\n"
                for i, song_dict in enumerate(queue_info['songs'][:10], 1):  # 只显示前10首
                    response += f"{i}. {song_dict['title']} - {song_dict['artist']}\n"
                
                if queue_info['total_songs'] > 10:
                    response += f"... 还有 {queue_info['total_songs'] - 10} 首歌曲\n"
                
                response += f"\n🔀 播放模式: {queue_info['play_mode']}"
            else:
                response += "⏭️ 队列为空"
            
            await self.reply_message(ctx, response)
            
        except Exception as e:
            await self.reply_message(ctx, f"❌ 获取队列信息失败: {str(e)}")

    async def shuffle_command(self, ctx: EventContext):
        """随机播放命令"""
        try:
            self.player_core.shuffle_queue()
            await self.reply_message(ctx, "🔀 队列已打乱")
        except Exception as e:
            await self.reply_message(ctx, f"❌ 打乱队列失败: {str(e)}")

    async def repeat_command(self, ctx: EventContext, args: List[str]):
        """循环模式命令"""
        try:
            if not args:
                # 显示当前循环模式
                current_mode = self.player_core.player_state.queue.play_mode
                await self.reply_message(ctx, f"🔁 当前播放模式: {current_mode.value}")
                return
            
            mode = args[0].lower()
            if mode in ['off', 'none', '关闭']:
                self.player_core.set_play_mode(PlayMode.SEQUENTIAL)
                await self.reply_message(ctx, "🔁 循环模式: 关闭")
            elif mode in ['all', 'list', '列表', '全部']:
                self.player_core.set_play_mode(PlayMode.REPEAT_ALL)
                await self.reply_message(ctx, "🔁 循环模式: 列表循环")
            elif mode in ['one', 'single', '单曲']:
                self.player_core.set_play_mode(PlayMode.REPEAT_ONE)
                await self.reply_message(ctx, "🔁 循环模式: 单曲循环")
            elif mode in ['shuffle', 'random', '随机']:
                self.player_core.set_play_mode(PlayMode.SHUFFLE)
                await self.reply_message(ctx, "🔁 循环模式: 随机播放")
            else:
                await self.reply_message(ctx, "❌ 无效的循环模式\n可用模式: off/all/one/shuffle")
                
        except Exception as e:
            await self.reply_message(ctx, f"❌ 设置循环模式失败: {str(e)}")

    async def volume_command(self, ctx: EventContext, args: List[str]):
        """音量命令"""
        try:
            if not args:
                volume = self.player_core.player_state.volume
                await self.reply_message(ctx, f"🔊 当前音量: {int(volume * 100)}%")
                return
            
            try:
                volume = float(args[0])
                if volume < 0 or volume > 100:
                    await self.reply_message(ctx, "❌ 音量范围: 0-100")
                    return
                
                self.player_core.set_volume(volume / 100.0)
                await self.reply_message(ctx, f"🔊 音量设置为: {int(volume)}%")
                
            except ValueError:
                await self.reply_message(ctx, "❌ 无效的音量值\n用法: `!volume <0-100>`")
                
        except Exception as e:
            await self.reply_message(ctx, f"❌ 设置音量失败: {str(e)}")

    async def now_playing_command(self, ctx: EventContext):
        """当前播放命令"""
        current_song = self.player_core.player_state.current_song
        if current_song:
            status = self.player_core.player_state.status.value
            duration_str = f"{current_song.duration // 60}:{current_song.duration % 60:02d}" if current_song.duration > 0 else "未知"
            
            response = f"🎵 **正在播放:**\n"
            response += f"**{current_song.title}**\n"
            response += f"👤 {current_song.artist}\n"
            response += f"📀 {current_song.album}\n"
            response += f"⏱️ {duration_str}\n"
            response += f"🎧 {current_song.platform}\n"
            response += f"▶️ 状态: {status}"
            
            await self.reply_message(ctx, response)
        else:
            await self.reply_message(ctx, "❌ 当前没有播放歌曲")

    async def playlist_command(self, ctx: EventContext, args: List[str]):
        """歌单命令"""
        if not args:
            await self.reply_message(ctx, 
                "📝 **歌单命令:**\n"
                "• `!playlist list` - 查看所有歌单\n"
                "• `!playlist import <URL>` - 从URL导入歌单\n"
                "• `!playlist play <歌单名>` - 播放歌单"
            )
            return
        
        subcommand = args[0].lower()
        
        if subcommand == "list":
            await self.playlist_list_command(ctx)
        elif subcommand == "import" and len(args) > 1:
            await self.playlist_import_command(ctx, args[1])
        elif subcommand == "play" and len(args) > 1:
            await self.playlist_play_command(ctx, " ".join(args[1:]))
        else:
            await self.reply_message(ctx, "❌ 无效的歌单命令")

    async def playlist_list_command(self, ctx: EventContext):
        """列出歌单"""
        try:
            playlists = await self.player_core.get_playlists()
            if playlists:
                response = f"📝 **歌单列表** ({len(playlists)}):\n\n"
                for i, playlist in enumerate(playlists, 1):
                    response += f"**{i}.** {playlist['name']}\n"
                    response += f"　　👤 {playlist['creator']} | 🎵 {playlist['song_count']} 首歌曲\n\n"
                
                response += "使用 `!playlist play <歌单名>` 播放歌单"
                await self.reply_message(ctx, response)
            else:
                await self.reply_message(ctx, "📝 暂无歌单")
                
        except Exception as e:
            await self.reply_message(ctx, f"❌ 获取歌单列表失败: {str(e)}")

    async def playlist_import_command(self, ctx: EventContext, source: str):
        """导入歌单"""
        user_id = str(ctx.event.query.message_event.source_platform_object.author.id)
        
        await self.reply_message(ctx, f"📥 正在导入歌单: {source}")
        
        try:
            # 检查是否是 URL 还是本地文件名
            if source.startswith(('http://', 'https://')):
                # 从 URL 导入
                playlist = await self.player_core.import_playlist_from_url(source)
            else:
                # 从本地文件导入（WebDAV 同步的文件）
                playlist = await self.import_local_playlist_file(user_id, source)
            
            if playlist:
                await self.reply_message(ctx, 
                    f"✅ 成功导入歌单:\n"
                    f"**{playlist.name}**\n"
                    f"👤 {playlist.creator}\n"
                    f"🎵 {len(playlist.songs)} 首歌曲"
                )
            else:
                if source.startswith(('http://', 'https://')):
                    await self.reply_message(ctx, "❌ 歌单导入失败，请检查URL是否正确")
                else:
                    await self.reply_message(ctx, 
                        f"❌ 未找到本地歌单文件: {source}\n"
                        f"💡 使用 `!webdav list` 查看可用的歌单文件\n"
                        f"💡 使用 `!webdav sync` 同步您的 WebDAV 歌单"
                    )
                
        except Exception as e:
            await self.reply_message(ctx, f"❌ 导入失败: {str(e)}")

    async def playlist_play_command(self, ctx: EventContext, playlist_name: str):
        """播放歌单"""
        try:
            # 获取 Discord 相关信息
            adapter = ctx.event.query.adapter
            message_event = ctx.event.query.message_event
            discord_msg = message_event.source_platform_object
            guild_id = discord_msg.guild.id if discord_msg.guild else None
            user_id = discord_msg.author.id
            
            if not guild_id:
                await self.reply_message(ctx, "❌ 此命令只能在服务器中使用")
                return
            
            # 查找歌单
            playlists = await self.player_core.get_playlists()
            playlist = next((p for p in playlists if playlist_name.lower() in p['name'].lower()), None)
            
            if not playlist:
                await self.reply_message(ctx, f"❌ 未找到歌单: {playlist_name}")
                return
            
            # 确保连接到语音频道
            voice_connected = await self.ensure_voice_connection(ctx, adapter, guild_id, user_id)
            if not voice_connected:
                return
            
            # 加载歌单到队列
            success = await self.player_core.load_playlist_to_queue(playlist['id'])
            if success:
                await self.reply_message(ctx, 
                    f"✅ 已加载歌单到队列:\n"
                    f"**{playlist['name']}**\n"
                    f"🎵 {playlist['song_count']} 首歌曲\n"
                    f"🎧 正在开始播放..."
                )
                
                # 开始播放第一首歌曲
                first_song = self.player_core.player_state.queue.get_current_song()
                if first_song:
                    # 设置当前播放歌曲
                    self.player_core.player_state.current_song = first_song
                    
                    # 获取音频文件并播放
                    audio_file = await self.player_core.cache_manager.get_audio_file(first_song)
                    if audio_file:
                        play_success = await self.play_audio_file(ctx, adapter, guild_id, audio_file)
                        if play_success:
                            await self.reply_message(ctx, 
                                f"🎵 正在播放:\n"
                                f"**{first_song.title}**\n"
                                f"👤 {first_song.artist}\n"
                                f"📀 {first_song.album}\n"
                                f"🎧 {first_song.platform}"
                            )
                        else:
                            await self.reply_message(ctx, "❌ 音频播放失败")
                    else:
                        await self.reply_message(ctx, "❌ 无法获取音频文件")
                else:
                    await self.reply_message(ctx, "❌ 歌单为空或无法播放")
            else:
                await self.reply_message(ctx, "❌ 加载歌单失败")
                
        except Exception as e:
            await self.reply_message(ctx, f"❌ 播放歌单失败: {str(e)}")
            import traceback
            traceback.print_exc()

    async def cache_command(self, ctx: EventContext, args: List[str]):
        """缓存管理命令"""
        try:
            if not args:
                # 显示缓存状态
                stats = self.player_core.cache_manager.get_cache_stats()
                response = f"💾 **缓存状态:**\n"
                response += f"📁 文件数量: {stats['total_files']}\n"
                response += f"💽 使用空间: {stats.get('total_size_mb', 0):.1f} MB / {stats.get('max_size_mb', 0):.1f} MB\n"
                response += f"📊 使用率: {stats.get('usage_percent', 0):.1f}%\n"
                response += f"📈 平均访问次数: {stats.get('avg_access_count', 0):.1f}\n"
                
                await self.reply_message(ctx, response)
                return
            
            subcommand = args[0].lower()
            
            if subcommand == "clear":
                success = self.player_core.cache_manager.clear_cache()
                if success:
                    await self.reply_message(ctx, "✅ 缓存已清空")
                else:
                    await self.reply_message(ctx, "❌ 清空缓存失败")
            elif subcommand == "cleanup":
                removed_count = self.player_core.cache_manager.cleanup_orphaned_files()
                await self.reply_message(ctx, f"✅ 已清理 {removed_count} 个孤立文件")
            else:
                await self.reply_message(ctx, "❌ 无效的缓存命令\n可用命令: clear, cleanup")
                
        except Exception as e:
            await self.reply_message(ctx, f"❌ 缓存操作失败: {str(e)}")

    async def sources_command(self, ctx: EventContext):
        """音源命令"""
        plugins = self.player_core.get_plugin_status()
        if plugins:
            response = f"🎧 **可用音源** ({len(plugins)}):\n\n"
            for plugin in plugins:
                status = "✅ 启用" if plugin.get('enabled', True) else "❌ 禁用"
                response += f"**{plugin['name']}** {status}\n"
                response += f"　　📝 {plugin.get('description', '')}\n"
                response += f"　　👤 {plugin.get('author', 'Unknown')}\n\n"
            
            await self.reply_message(ctx, response)
        else:
            await self.reply_message(ctx, "❌ 没有可用的音源插件")

    async def register_command(self, ctx: EventContext, args: List[str]):
        """用户注册命令"""
        if not self.webdav_manager:
            await self.reply_message(ctx, "❌ WebDAV 功能未启用")
            return
        
        if not args or len(args) < 2 or args[0].lower() != "name":
            await self.reply_message(ctx, 
                "❌ 用法错误\n"
                "正确用法: `!reg name <您的用户名>`\n"
                "例如: `!reg name 张三`"
            )
            return
        
        # 获取用户信息
        discord_msg = ctx.event.query.message_event.source_platform_object
        user_id = str(discord_msg.author.id)
        discord_name = discord_msg.author.display_name
        username = " ".join(args[1:])  # 支持带空格的用户名
        
        # 注册用户
        result = self.webdav_manager.register_user(user_id, username, discord_name)
        
        if result['success']:
            await self.reply_message(ctx, f"✅ {result['message']}")
        else:
            await self.reply_message(ctx, f"❌ {result['message']}")

    async def webdav_command(self, ctx: EventContext, args: List[str]):
        """WebDAV 管理命令"""
        if not self.webdav_manager:
            await self.reply_message(ctx, "❌ WebDAV 功能未启用")
            return
        
        if not args:
            await self.reply_message(ctx, 
                "📁 **WebDAV 命令:**\n"
                "• `!webdav status` - 查看您的 WebDAV 状态\n"
                "• `!webdav sync` - 同步歌单\n"
                "• `!webdav list` - 查看可用歌单\n\n"
                "💡 首次使用请先注册: `!reg name <您的用户名>`"
            )
            return
        
        subcommand = args[0].lower()
        discord_msg = ctx.event.query.message_event.source_platform_object
        user_id = str(discord_msg.author.id)
        
        if subcommand == "status":
            await self.webdav_status_command(ctx, user_id)
        elif subcommand == "sync":
            await self.webdav_sync_command(ctx, user_id)
        elif subcommand == "list":
            await self.webdav_list_command(ctx, user_id)
        else:
            await self.reply_message(ctx, "❌ 无效的 WebDAV 命令")

    async def webdav_status_command(self, ctx: EventContext, user_id: str):
        """查看 WebDAV 状态"""
        status = self.webdav_manager.get_webdav_status(user_id)
        
        if not status['registered']:
            await self.reply_message(ctx, f"❌ {status['message']}")
            return
        
        response = f"📁 **WebDAV 状态**\n\n"
        response += f"👤 用户名: {status['username']}\n"
        
        if status['webdav_enabled']:
            response += f"✅ WebDAV 已启用\n"
            response += f"🔄 自动同步: {'是' if status['auto_sync'] else '否'}\n"
            if status['last_sync']:
                response += f"📅 上次同步: {status['last_sync']}\n"
            response += f"\n💡 配置详情请联系管理员"
        else:
            response += f"❌ WebDAV 未启用\n"
            response += f"💡 请联系管理员配置您的 WebDAV 访问权限"
        
        await self.reply_message(ctx, response)

    async def webdav_sync_command(self, ctx: EventContext, user_id: str):
        """同步 WebDAV 歌单"""
        try:
            await self.reply_message(ctx, "🔄 正在同步 WebDAV 歌单...")
            
            result = self.webdav_manager.sync_webdav_playlists(user_id)
            
            if result['success']:
                response = f"✅ {result['message']}"
                if 'errors' in result and result['errors']:
                    response += f"\n\n⚠️ 错误详情:\n"
                    for error in result['errors'][:3]:  # 只显示前3个错误
                        response += f"• {error}\n"
                    if len(result['errors']) > 3:
                        response += f"• ... 还有 {len(result['errors']) - 3} 个错误"
            else:
                response = f"❌ 同步失败: {result['error']}"
            
            await self.reply_message(ctx, response)
            
        except Exception as e:
            await self.reply_message(ctx, f"❌ 同步过程中出错: {str(e)}")

    async def webdav_list_command(self, ctx: EventContext, user_id: str):
        """列出用户的歌单"""
        try:
            playlists = self.webdav_manager.list_user_playlists(user_id)
            
            if not playlists:
                await self.reply_message(ctx, 
                    "📋 您还没有任何歌单文件\n\n"
                    "💡 使用 `!webdav sync` 从 WebDAV 同步歌单"
                )
                return
            
            response = f"📋 **您的歌单** ({len(playlists)}):\n\n"
            
            for i, playlist in enumerate(playlists[:10], 1):  # 只显示前10个
                size_kb = playlist['size'] / 1024
                response += f"**{i}.** {playlist['name']}\n"
                response += f"　　📅 {playlist['modified']} | 💾 {size_kb:.1f}KB\n\n"
            
            if len(playlists) > 10:
                response += f"... 还有 {len(playlists) - 10} 个歌单\n\n"
            
            response += "💡 使用 `!playlist import <文件名>` 导入歌单到播放队列"
            
            await self.reply_message(ctx, response)
            
        except Exception as e:
            await self.reply_message(ctx, f"❌ 获取歌单列表失败: {str(e)}")

    async def help_command(self, ctx: EventContext):
        """帮助命令"""
        help_text = """🎵 **BotPlayer 音乐机器人**

**基本播放:**
• `!play <歌曲名>` - 搜索并播放歌曲
• `!search <关键词>` - 搜索歌曲
• `!pause` - 暂停播放
• `!resume` - 恢复播放
• `!stop` - 停止播放
• `!skip` - 跳到下一首
• `!now` - 显示当前播放

**队列管理:**
• `!queue` - 查看播放队列
• `!shuffle` - 打乱队列
• `!repeat <模式>` - 设置循环模式 (off/all/one/shuffle)
• `!volume <0-100>` - 设置音量

**歌单管理:**
• `!playlist list` - 查看所有歌单
• `!playlist import <URL>` - 从URL导入歌单
• `!playlist play <歌单名>` - 播放歌单

**个人 WebDAV:**
• `!reg name <用户名>` - 注册账户
• `!webdav status` - 查看 WebDAV 状态
• `!webdav sync` - 同步个人歌单
• `!webdav list` - 查看个人歌单

**系统管理:**
• `!cache` - 查看缓存状态
• `!cache clear` - 清空缓存
• `!sources` - 查看音源状态
• `!help` - 显示此帮助

**支持的音源:** Bilibili, 网易云音乐, 本地文件
**支持格式:** MusicFreeBackup.json, 网易云歌单等"""
        
        await self.reply_message(ctx, help_text)

    async def ensure_voice_connection(self, ctx: EventContext, adapter, guild_id: int, user_id: int) -> bool:
        """确保语音连接"""
        try:
            # 检查是否已连接
            is_connected = await adapter.is_connected_to_voice(guild_id)
            if is_connected:
                return True
            
            # 获取用户语音状态
            discord_msg = ctx.event.query.message_event.source_platform_object
            guild = discord_msg.guild
            member = guild.get_member(user_id)
            
            if not member or not member.voice or not member.voice.channel:
                await self.reply_message(ctx, "❌ 请先加入一个语音频道")
                return False
            
            channel_id = member.voice.channel.id
            
            # 连接到语音频道
            voice_client = await adapter.join_voice_channel(guild_id, channel_id, user_id)
            return voice_client is not None
            
        except Exception as e:
            await self.reply_message(ctx, f"❌ 语音连接失败: {str(e)}")
            return False

    async def play_audio_file(self, ctx: EventContext, adapter, guild_id: int, audio_file: str) -> bool:
        """播放音频文件"""
        try:
            voice_client = await adapter.get_voice_client(guild_id)
            if not voice_client:
                await self.reply_message(ctx, "❌ 未连接到语音频道")
                return False
            
            if voice_client.is_playing():
                voice_client.stop()
                await asyncio.sleep(0.5)
            
            # 使用 Discord.py 播放音频
            import discord
            
            def after_playing(error):
                if error:
                    print(f'音频播放错误: {error}')
                else:
                    print('音频播放完成')
                    # 播放完成后尝试播放下一首
                    # 使用同步方式处理，避免异步上下文问题
                    try:
                        self.handle_song_finished_sync(ctx, adapter, guild_id)
                    except Exception as e:
                        print(f"处理歌曲完成事件时出错: {e}")
            
            # 播放音频文件
            ffmpeg_options = {
                'before_options': '-loglevel quiet',
                'options': '-vn -filter:a "volume=0.5"'
            }
            
            audio_source = discord.FFmpegPCMAudio(audio_file, **ffmpeg_options)
            voice_client.play(audio_source, after=after_playing)
            
            return True
            
        except Exception as e:
            print(f"Error playing audio file: {e}")
            return False

    def handle_song_finished_sync(self, ctx: EventContext, adapter, guild_id: int):
        """同步处理歌曲播放完成"""
        try:
            print("音频播放完成")
            
            # 防止重复处理
            if self._is_processing_next:
                print("⚠️ 已在处理下一首歌曲，跳过重复处理")
                return
            
            self._is_processing_next = True
            
            # 检查播放模式和队列状态
            current_mode = self.player_core.player_state.queue.play_mode
            has_next = self.player_core.player_state.queue.has_next_song()
            
            print(f"播放模式: {current_mode}, 有下一首: {has_next}")
            
            # 根据播放模式决定是否播放下一首
            should_play_next = False
            
            if current_mode == PlayMode.REPEAT_ONE:
                # 单曲循环：重播当前歌曲
                should_play_next = True
                print("🔁 单曲循环模式")
            elif current_mode == PlayMode.SEQUENTIAL:
                # 顺序播放：检查是否有下一首
                should_play_next = has_next
                print(f"🎵 顺序播放模式，有下一首: {has_next}")
            elif current_mode in [PlayMode.REPEAT_ALL, PlayMode.SHUFFLE]:
                # 列表循环或随机播放：总是继续播放
                should_play_next = True
                print(f"🔄 循环/随机播放模式")
            
            if should_play_next:
                # 使用线程池来运行异步任务
                import threading
                
                def run_async_task_with_lock(coro):
                    """在新的事件循环中安全运行异步任务"""
                    import asyncio
                    try:
                        # 创建新的事件循环
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(coro)
                        finally:
                            # 重置处理标志
                            self._is_processing_next = False
                            loop.close()
                    except Exception as e:
                        print(f"运行异步任务时出错: {e}")
                        import traceback
                        traceback.print_exc()
                        # 重置处理标志
                        self._is_processing_next = False
                
                # 在后台线程中运行异步任务
                if current_mode == PlayMode.REPEAT_ONE:
                    # 重播当前歌曲
                    threading.Thread(
                        target=run_async_task_with_lock,
                        args=(self.replay_current_song_safe(ctx, adapter, guild_id),),
                        daemon=True
                    ).start()
                else:
                    # 播放下一首
                    threading.Thread(
                        target=run_async_task_with_lock,
                        args=(self.play_next_song_safe(ctx, adapter, guild_id),),
                        daemon=True
                    ).start()
            else:
                # 不应该继续播放
                self.player_core.stop()
                self._is_processing_next = False
                print("🎵 播放完成，已停止")
                
        except Exception as e:
            print(f"Error handling song finished sync: {e}")
            import traceback
            traceback.print_exc()
            # 重置处理标志
            self._is_processing_next = False

    async def replay_current_song_safe(self, ctx: EventContext, adapter, guild_id: int):
        """安全地重播当前歌曲（带锁保护）"""
        async with self._playing_lock:
            try:
                print("🔁 开始重播当前歌曲...")
                current_song = self.player_core.player_state.current_song
                if current_song:
                    audio_file = await self.player_core.cache_manager.get_audio_file(current_song)
                    if audio_file:
                        success = await self.play_audio_file(ctx, adapter, guild_id, audio_file)
                        if success:
                            print(f"🔁 成功重播: {current_song.title}")
                            await self.safe_send_message(ctx, 
                                f"🔁 单曲循环:\n"
                                f"**{current_song.title}**\n"
                                f"👤 {current_song.artist}"
                            )
                        else:
                            print("❌ 重播失败")
                    else:
                        print("❌ 无法获取当前歌曲的音频文件")
                else:
                    print("❌ 没有当前歌曲可重播")
            except Exception as e:
                print(f"Error replaying current song: {e}")
                import traceback
                traceback.print_exc()

    async def play_next_song_safe(self, ctx: EventContext, adapter, guild_id: int):
        """安全地播放下一首歌曲（带锁保护）"""
        async with self._playing_lock:
            try:
                print("🎵 开始播放下一首歌曲...")
                
                # 检查是否已有音频在播放
                try:
                    voice_client = await adapter.get_voice_client(guild_id)
                    if voice_client and voice_client.is_playing():
                        print("⚠️ 检测到音频仍在播放，停止当前播放")
                        voice_client.stop()
                        await asyncio.sleep(0.5)  # 等待停止完成
                except Exception as e:
                    print(f"检查语音客户端状态时出错: {e}")
                
                # 直接从队列获取下一首歌，而不是通过 play_next()
                next_song = self.player_core.player_state.queue.next_song()
                if next_song:
                    print(f"🎵 获取到下一首歌曲: {next_song.title}")
                    
                    # 更新当前播放歌曲状态
                    self.player_core.player_state.current_song = next_song
                    
                    # 获取音频文件
                    audio_file = await self.player_core.cache_manager.get_audio_file(next_song)
                    if audio_file:
                        print(f"🎵 获取到音频文件: {audio_file}")
                        
                        # 播放音频
                        success = await self.play_audio_file(ctx, adapter, guild_id, audio_file)
                        if success:
                            print(f"🎵 成功播放下一首: {next_song.title}")
                            # 使用安全的消息发送方法
                            await self.send_message_to_main_loop(ctx,
                                f"🎵 自动播放下一首:\n"
                                f"**{next_song.title}**\n"
                                f"👤 {next_song.artist}\n"
                                f"📀 {next_song.album}\n"
                                f"🎧 {next_song.platform}"
                            )
                        else:
                            print("❌ 音频播放失败")
                            await self.send_message_to_main_loop(ctx, "❌ 下一首歌曲播放失败")
                    else:
                        print("❌ 无法获取音频文件")
                        await self.send_message_to_main_loop(ctx, "❌ 无法获取下一首歌曲的音频文件")
                else:
                    # 没有下一首了
                    print("🎵 没有下一首歌曲了")
                    self.player_core.stop()
                    await self.send_message_to_main_loop(ctx, "🎵 播放队列已结束")
            except Exception as e:
                print(f"Error playing next song: {e}")
                import traceback
                traceback.print_exc()
                await self.send_message_to_main_loop(ctx, f"❌ 播放下一首时出错: {str(e)}")

    async def send_message_to_main_loop(self, ctx: EventContext, text: str):
        """安全地将消息发送到主事件循环"""
        try:
            if self._main_loop and not self._main_loop.is_closed():
                # 在主事件循环中调度消息发送任务
                future = asyncio.run_coroutine_threadsafe(
                    self._send_message_direct(ctx, text),
                    self._main_loop
                )
                # 等待最多3秒钟
                try:
                    future.result(timeout=3.0)
                    print(f"[BotPlayer] 成功发送消息到Discord")
                except Exception as e:
                    print(f"[BotPlayer] 发送消息超时或失败: {e}")
                    print(f"[BotPlayer消息] {text}")
            else:
                # 主事件循环不可用，只打印到控制台
                print(f"[BotPlayer消息] {text}")
        except Exception as e:
            print(f"发送消息到主循环失败: {e}")
            print(f"[BotPlayer消息] {text}")

    async def replay_current_song(self, ctx: EventContext, adapter, guild_id: int):
        """重播当前歌曲（已弃用，使用 replay_current_song_safe）"""
        await self.replay_current_song_safe(ctx, adapter, guild_id)

    async def play_next_song_async(self, ctx: EventContext, adapter, guild_id: int):
        """异步播放下一首歌曲（已弃用，使用 play_next_song_safe）"""
        await self.play_next_song_safe(ctx, adapter, guild_id)

    async def safe_send_message(self, ctx: EventContext, text: str):
        """安全发送消息，避免异步上下文管理器错误"""
        try:
            # 检查是否在主线程中
            import threading
            import asyncio
            from pkg.platform.types.message import MessageChain, Plain
            
            current_thread = threading.current_thread()
            is_main_thread = isinstance(current_thread, threading._MainThread)
            
            print(f"[BotPlayer] 发送消息请求 - 当前线程: {current_thread.name}, 是否主线程: {is_main_thread}")
            
            if is_main_thread:
                # 在主线程中，直接发送
                await self._send_message_direct(ctx, text)
            else:
                # 在子线程中，只打印到控制台，不发送Discord消息
                # 因为跨线程的Discord消息发送容易出现异步上下文错误
                print(f"[BotPlayer消息] {text}")
                
                # 如果确实需要发送到Discord，可以考虑使用回调机制
                # 但为了避免复杂性和潜在的异步问题，这里仅打印日志
                
        except Exception as e:
            print(f"发送消息失败: {e}")
            # 备用方案：打印到控制台
            print(f"[BotPlayer消息] {text}")

    async def _send_message_direct(self, ctx: EventContext, text: str):
        """直接发送消息到Discord"""
        from pkg.platform.types.message import MessageChain, Plain
        
        try:
            # 创建消息链
            message_chain = MessageChain([Plain(text=text)])
            
            # 发送消息到Discord平台
            await ctx.send_message(
                ctx.event.launcher_type,
                str(ctx.event.launcher_id),
                message_chain
            )
            print(f"[BotPlayer] Discord消息发送成功: {text[:50]}...")
        except Exception as e:
            print(f"Discord消息发送失败: {e}")
            print(f"[BotPlayer控制台消息] {text}")
            print(f"[BotPlayer消息] {text}")

    async def reply_message(self, ctx: EventContext, text: str):
        """回复消息"""
        from pkg.platform.types.message import MessageChain, Plain
        
        try:
            # 创建消息链
            message_chain = MessageChain([Plain(text=text)])
            
            # 正常发送消息
            await ctx.send_message(
                ctx.event.launcher_type,
                str(ctx.event.launcher_id),
                message_chain
            )
                
        except Exception as e:
            print(f"发送消息失败: {e}")
            # 备用方案：打印到控制台
            print(f"[BotPlayer消息] {text}")

    def __del__(self):
        """清理资源"""
        if self.player_core:
            try:
                # 运行清理任务
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.player_core.cleanup())
                else:
                    asyncio.run(self.player_core.cleanup())
            except Exception as e:
                print(f"Cleanup error: {e}")
    
    async def import_local_playlist_file(self, user_id: str, filename: str):
        """从本地文件导入歌单（WebDAV 同步的文件）"""
        try:
            print(f"[DEBUG] 开始导入本地歌单文件: {filename}, 用户ID: {user_id}")
            
            if not self.webdav_manager:
                print(f"[DEBUG] WebDAV 管理器未初始化")
                return None
            
            # 获取用户信息
            user_info = self.webdav_manager.get_user_info(user_id)
            if not user_info:
                print(f"[DEBUG] 未找到用户信息: {user_id}")
                return None
            
            print(f"[DEBUG] 用户信息: {user_info.username}")
            
            # 查找用户的歌单文件
            user_playlists = self.webdav_manager.list_user_playlists(user_id)
            print(f"[DEBUG] 用户歌单列表: {[p['name'] for p in user_playlists]}")
            
            target_file = None
            
            for playlist in user_playlists:
                print(f"[DEBUG] 检查文件: {playlist['name']} == {filename}")
                if playlist['name'] == filename:
                    target_file = playlist['path']
                    break
            
            if not target_file:
                print(f"[DEBUG] 未找到目标文件: {filename}")
                return None
            
            print(f"[DEBUG] 找到目标文件: {target_file}")
            
            # 读取文件内容
            with open(target_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            print(f"[DEBUG] 文件内容长度: {len(content)} 字符")
            
            # 根据文件扩展名选择导入方法
            if filename.lower().endswith('.json'):
                print(f"[DEBUG] 识别为 JSON 文件，调用 import_musicfree_backup_from_content")
                # 尝试作为 MusicFree 备份文件导入
                result = await self.player_core.import_musicfree_backup_from_content(content)
                print(f"[DEBUG] 导入结果: {result.name if result else 'None'}")
                return result
            elif filename.lower().endswith(('.m3u', '.m3u8')):
                print(f"[DEBUG] 识别为 M3U 文件")
                # 导入 M3U 格式
                return await self.player_core.import_m3u_from_content(content)
            elif filename.lower().endswith('.pls'):
                print(f"[DEBUG] 识别为 PLS 文件")
                # 导入 PLS 格式
                return await self.player_core.import_pls_from_content(content)
            else:
                print(f"不支持的文件格式: {filename}")
                return None
                
        except Exception as e:
            print(f"导入本地歌单文件失败: {e}")
            import traceback
            traceback.print_exc()
            return None
