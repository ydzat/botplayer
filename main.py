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


# 注册插件
@register(name="BotPlayer", description="多音源Discord音乐播放器，支持歌单导入和智能缓存", version="1.0", author="ydzat")
class BotPlayerPlugin(BasePlugin):

    def __init__(self, host: APIHost):
        super().__init__(host)
        self.player_core = None
        self.guild_players = {}  # 每个服务器的播放器实例
        
    async def initialize(self):
        """异步初始化"""
        try:
            # 获取插件目录
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(plugin_dir, "data")
            
            # 初始化播放器核心
            self.player_core = BotPlayerCore(data_dir=data_dir)
            
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
                "!sources", "!volume", "!now", "!help"
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
            
            # 歌单命令
            elif cmd == "!playlist":
                await self.playlist_command(ctx, args)
            
            # 缓存命令
            elif cmd == "!cache":
                await self.cache_command(ctx, args)
            
            # 音源命令
            elif cmd == "!sources":
                await self.sources_command(ctx)
            
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
        self.player_core.pause()
        await self.reply_message(ctx, "⏸️ 播放已暂停")

    async def resume_command(self, ctx: EventContext):
        """恢复播放命令"""
        self.player_core.resume()
        await self.reply_message(ctx, "▶️ 播放已恢复")

    async def stop_command(self, ctx: EventContext, adapter, guild_id: int):
        """停止命令"""
        try:
            # 停止Discord语音播放
            voice_client = await adapter.get_voice_client(guild_id)
            if voice_client and voice_client.is_playing():
                voice_client.stop()
            
            # 停止播放器
            self.player_core.stop()
            await self.reply_message(ctx, "⏹️ 播放已停止")
            
        except Exception as e:
            await self.reply_message(ctx, f"❌ 停止失败: {str(e)}")

    async def skip_command(self, ctx: EventContext, adapter, guild_id: int, user_id: int):
        """跳过命令"""
        try:
            next_song = await self.player_core.play_next()
            if next_song:
                # 播放下一首
                audio_file = await self.player_core.cache_manager.get_audio_file(next_song)
                if audio_file:
                    success = await self.play_audio_file(ctx, adapter, guild_id, audio_file)
                    if success:
                        await self.reply_message(ctx, 
                            f"⏭️ 已跳到下一首:\n"
                            f"**{next_song.title}** - {next_song.artist}"
                        )
                    else:
                        await self.reply_message(ctx, "❌ 播放下一首失败")
                else:
                    await self.reply_message(ctx, "❌ 无法获取下一首音频文件")
            else:
                await self.reply_message(ctx, "❌ 队列中没有下一首歌曲")
                
        except Exception as e:
            await self.reply_message(ctx, f"❌ 跳过失败: {str(e)}")

    async def queue_command(self, ctx: EventContext):
        """队列命令"""
        try:
            queue_info = self.player_core.get_queue_info()
            current_song = self.player_core.player_state.current_song
            
            if queue_info['total_songs'] == 0:
                await self.reply_message(ctx, "📝 播放队列为空")
                return
            
            response = f"🎵 **播放队列** ({queue_info['total_songs']} 首)\n"
            response += f"🔄 模式: {queue_info['play_mode']}\n\n"
            
            if current_song:
                response += f"🎧 **正在播放:**\n"
                response += f"　　{current_song.title} - {current_song.artist}\n\n"
            
            response += "📋 **队列:**\n"
            for i, song_data in enumerate(queue_info['songs'][:10], 1):  # 只显示前10首
                marker = "🔸" if i == queue_info['current_index'] + 1 else "　"
                response += f"{marker} **{i}.** {song_data['title']} - {song_data['artist']}\n"
            
            if queue_info['total_songs'] > 10:
                response += f"　... 还有 {queue_info['total_songs'] - 10} 首歌曲"
            
            await self.reply_message(ctx, response)
            
        except Exception as e:
            await self.reply_message(ctx, f"❌ 获取队列信息失败: {str(e)}")

    async def shuffle_command(self, ctx: EventContext):
        """随机播放命令"""
        self.player_core.shuffle_queue()
        await self.reply_message(ctx, "🔀 队列已打乱")

    async def repeat_command(self, ctx: EventContext, args: List[str]):
        """循环模式命令"""
        if not args:
            current_mode = self.player_core.player_state.queue.play_mode
            await self.reply_message(ctx, f"🔄 当前播放模式: {current_mode.value}")
            return
        
        mode_arg = args[0].lower()
        if mode_arg in ['off', 'none', '关闭']:
            self.player_core.set_play_mode(PlayMode.SEQUENTIAL)
            await self.reply_message(ctx, "🔄 循环模式: 关闭")
        elif mode_arg in ['all', 'playlist', '列表']:
            self.player_core.set_play_mode(PlayMode.REPEAT_ALL)
            await self.reply_message(ctx, "🔄 循环模式: 列表循环")
        elif mode_arg in ['one', 'single', '单曲']:
            self.player_core.set_play_mode(PlayMode.REPEAT_ONE)
            await self.reply_message(ctx, "🔄 循环模式: 单曲循环")
        elif mode_arg in ['shuffle', 'random', '随机']:
            self.player_core.set_play_mode(PlayMode.SHUFFLE)
            await self.reply_message(ctx, "🔄 循环模式: 随机播放")
        else:
            await self.reply_message(ctx, "❌ 无效的循环模式\n可用模式: off, all, one, shuffle")

    async def volume_command(self, ctx: EventContext, args: List[str]):
        """音量命令"""
        if not args:
            volume = self.player_core.player_state.volume
            await self.reply_message(ctx, f"🔊 当前音量: {int(volume * 100)}%")
            return
        
        try:
            volume = int(args[0])
            if volume < 0 or volume > 100:
                await self.reply_message(ctx, "❌ 音量必须在 0-100 之间")
                return
            
            self.player_core.set_volume(volume / 100.0)
            await self.reply_message(ctx, f"🔊 音量已设置为: {volume}%")
            
        except ValueError:
            await self.reply_message(ctx, "❌ 请提供有效的音量值 (0-100)")

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
                    response += f"**{i}.** {playlist.name}\n"
                    response += f"　　👤 {playlist.creator} | 🎵 {len(playlist.songs)} 首歌曲\n\n"
                
                response += "使用 `!playlist play <歌单名>` 播放歌单"
                await self.reply_message(ctx, response)
            else:
                await self.reply_message(ctx, "📝 暂无歌单")
                
        except Exception as e:
            await self.reply_message(ctx, f"❌ 获取歌单列表失败: {str(e)}")

    async def playlist_import_command(self, ctx: EventContext, url: str):
        """导入歌单"""
        await self.reply_message(ctx, f"📥 正在导入歌单: {url}")
        
        try:
            playlist = await self.player_core.import_playlist_from_url(url)
            if playlist:
                await self.reply_message(ctx, 
                    f"✅ 成功导入歌单:\n"
                    f"**{playlist.name}**\n"
                    f"👤 {playlist.creator}\n"
                    f"🎵 {len(playlist.songs)} 首歌曲"
                )
            else:
                await self.reply_message(ctx, "❌ 歌单导入失败，请检查URL是否正确")
                
        except Exception as e:
            await self.reply_message(ctx, f"❌ 导入失败: {str(e)}")

    async def playlist_play_command(self, ctx: EventContext, playlist_name: str):
        """播放歌单"""
        try:
            playlists = await self.player_core.get_playlists()
            playlist = next((p for p in playlists if playlist_name.lower() in p.name.lower()), None)
            
            if not playlist:
                await self.reply_message(ctx, f"❌ 未找到歌单: {playlist_name}")
                return
            
            success = await self.player_core.load_playlist_to_queue(playlist.id)
            if success:
                await self.reply_message(ctx, 
                    f"✅ 已加载歌单到队列:\n"
                    f"**{playlist.name}**\n"
                    f"🎵 {len(playlist.songs)} 首歌曲"
                )
            else:
                await self.reply_message(ctx, "❌ 加载歌单失败")
                
        except Exception as e:
            await self.reply_message(ctx, f"❌ 播放歌单失败: {str(e)}")

    async def cache_command(self, ctx: EventContext, args: List[str]):
        """缓存管理命令"""
        if not args:
            # 显示缓存状态
            stats = self.player_core.get_cache_status()
            response = f"💾 **缓存状态:**\n"
            response += f"📁 文件数量: {stats['total_files']}\n"
            response += f"💽 使用空间: {stats['total_size_mb']} MB / {stats['max_size_mb']} MB\n"
            response += f"📊 使用率: {stats['usage_percent']}%\n"
            response += f"📈 平均访问次数: {stats['avg_access_count']}\n"
            
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

    async def reply_message(self, ctx: EventContext, text: str):
        """回复消息"""
        from pkg.platform.types.message import MessageChain, Plain
        
        try:
            await ctx.send_message(
                ctx.event.launcher_type,
                str(ctx.event.launcher_id),
                MessageChain([Plain(text=text)])
            )
        except Exception as e:
            print(f"发送消息失败: {e}")

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
