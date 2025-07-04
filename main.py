import os
import discord
from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *  # 导入事件类
from pkg.platform.sources.discord import VoiceConnectionError, VoicePermissionError, VoiceNetworkError


# 注册插件
@register(name="BotPlayer", description="Discord语音功能测试与音频播放", version="0.1", author="ydzat")
class BotPlayerPlugin(BasePlugin):

    # 插件加载时触发
    def __init__(self, host: APIHost):
        pass

    # 异步初始化
    async def initialize(self):
        pass

    # 当收到消息时触发
    @handler(PersonMessageReceived)
    @handler(GroupMessageReceived)
    async def message_received(self, ctx: EventContext):
        # 检查是否是 Discord 平台
        if ctx.event.query.adapter.__class__.__name__ != 'DiscordAdapter':
            return
        
        msg = str(ctx.event.message_chain).strip()
        if msg.startswith("!voice"):
            ctx.prevent_default()
            await self.handle_voice_command(ctx, msg)

    async def handle_voice_command(self, ctx: EventContext, command: str):
        """处理语音命令"""
        adapter = ctx.event.query.adapter
        
        # 获取 Discord 相关信息
        message_event = ctx.event.query.message_event
        if not hasattr(message_event, 'source_platform_object') or message_event.source_platform_object is None:
            await self.reply_message(ctx, "无法获取 Discord 消息对象")
            return
        
        discord_msg = message_event.source_platform_object
        guild_id = discord_msg.guild.id if discord_msg.guild else None
        user_id = discord_msg.author.id
        
        if not guild_id:
            await self.reply_message(ctx, "此命令只能在服务器中使用")
            return
        
        try:
            if command == '!voice join':
                await self.join_voice_command(ctx, adapter, guild_id, user_id)
            elif command == '!voice leave':
                await self.leave_voice_command(ctx, adapter, guild_id)
            elif command == '!voice status':
                await self.status_command(ctx, adapter, guild_id)
            elif command == '!voice list':
                await self.list_connections_command(ctx, adapter)
            elif command == '!voice play':
                await self.play_test_audio_command(ctx, adapter, guild_id)
            elif command == '!voice stop':
                await self.stop_audio_command(ctx, adapter, guild_id)
            elif command.startswith('!voice join '):
                # !voice join <channel_id>
                channel_id = command.split(' ')[-1]
                if channel_id.isdigit():
                    await self.join_specific_channel(ctx, adapter, guild_id, int(channel_id), user_id)
                else:
                    await self.reply_message(ctx, "请提供有效的频道ID")
            elif command == '!voice help':
                await self.help_command(ctx)
            else:
                await self.help_command(ctx)
                
        except Exception as e:
            await self.reply_message(ctx, f"命令执行出错: {str(e)}")
    
    async def join_voice_command(self, ctx, adapter, guild_id, user_id):
        """加入用户当前所在的语音频道并播放测试音频"""
        try:
            # 获取用户当前语音状态
            discord_msg = ctx.event.query.message_event.source_platform_object
            guild = discord_msg.guild
            member = guild.get_member(user_id)
            
            if not member or not member.voice or not member.voice.channel:
                await self.reply_message(ctx, "❌ 你需要先加入一个语音频道")
                return
            
            channel_id = member.voice.channel.id
            channel_name = member.voice.channel.name
            
            await self.reply_message(ctx, f"🔗 正在连接到语音频道: {channel_name}...")
            
            voice_client = await adapter.join_voice_channel(guild_id, channel_id, user_id)
            
            if voice_client:
                latency = voice_client.latency * 1000
                await self.reply_message(ctx, f"✅ 成功连接到 **{channel_name}**\n⏱️ 延迟: {latency:.2f}ms")
                
                # 自动播放测试音频
                await self.play_test_audio(ctx, voice_client)
            else:
                await self.reply_message(ctx, "❌ 连接失败")
                
        except VoicePermissionError as e:
            if "user_not_in_channel" in e.missing_permissions:
                await self.reply_message(ctx, "❌ 你不在语音频道中，请先加入频道")
            elif "connect" in e.missing_permissions:
                await self.reply_message(ctx, "❌ 机器人没有连接权限")
            elif "speak" in e.missing_permissions:
                await self.reply_message(ctx, "❌ 机器人没有说话权限")
            else:
                await self.reply_message(ctx, f"❌ 权限错误: {e}")
        except VoiceNetworkError as e:
            await self.reply_message(ctx, f"❌ 网络错误: {e}")
        except VoiceConnectionError as e:
            await self.reply_message(ctx, f"❌ 连接错误: {e}")
    
    async def join_specific_channel(self, ctx, adapter, guild_id, channel_id, user_id):
        """加入指定的语音频道并播放测试音频"""
        try:
            await self.reply_message(ctx, f"🔗 正在连接到频道 ID: {channel_id}...")
            
            voice_client = await adapter.join_voice_channel(guild_id, channel_id, user_id)
            
            if voice_client:
                # 获取频道信息
                channel_info = await adapter.get_voice_channel_info(guild_id, channel_id)
                channel_name = channel_info['channel_name'] if channel_info else f"Channel-{channel_id}"
                latency = voice_client.latency * 1000
                await self.reply_message(ctx, f"✅ 成功连接到 **{channel_name}**\n⏱️ 延迟: {latency:.2f}ms")
                
                # 自动播放测试音频
                await self.play_test_audio(ctx, voice_client)
            else:
                await self.reply_message(ctx, "❌ 连接失败")
                
        except Exception as e:
            await self.reply_message(ctx, f"❌ 连接失败: {e}")
    
    async def leave_voice_command(self, ctx, adapter, guild_id):
        """离开语音频道"""
        try:
            success = await adapter.leave_voice_channel(guild_id)
            if success:
                await self.reply_message(ctx, "👋 已断开语音连接")
            else:
                await self.reply_message(ctx, "❌ 断开失败或未连接")
        except Exception as e:
            await self.reply_message(ctx, f"❌ 断开连接时出错: {e}")
    
    async def status_command(self, ctx, adapter, guild_id):
        """显示语音连接状态"""
        try:
            is_connected = await adapter.is_connected_to_voice(guild_id)
            
            if not is_connected:
                await self.reply_message(ctx, "🔴 未连接到语音频道")
                return
            
            status = await adapter.get_voice_connection_status(guild_id)
            if status:
                status_text = f"""🔊 **语音连接状态**
📍 频道: **{status['channel_name']}**
⏰ 连接时间: {status['connection_time']}
⏱️ 延迟: {status['latency']:.2f}ms
👥 频道用户数: {status['user_count']}
💊 连接健康度: {status['connection_health']}
📊 状态: {status['status']}"""
                await self.reply_message(ctx, status_text)
            else:
                await self.reply_message(ctx, "❌ 无法获取状态信息")
                
        except Exception as e:
            await self.reply_message(ctx, f"❌ 获取状态时出错: {e}")
    
    async def list_connections_command(self, ctx, adapter):
        """列出所有活跃连接"""
        try:
            connections = await adapter.list_active_voice_connections()
            
            if not connections:
                await self.reply_message(ctx, "📝 当前没有活跃的语音连接")
                return
            
            connection_list = "🎵 **活跃的语音连接:**\n"
            for i, conn in enumerate(connections, 1):
                connection_list += f"{i}. **{conn['channel_name']}** (Guild: {conn['guild_id']})\n"
                connection_list += f"   ⏱️ 延迟: {conn['latency']:.2f}ms | 👥 用户: {conn['user_count']}\n"
            
            await self.reply_message(ctx, connection_list)
            
        except Exception as e:
            await self.reply_message(ctx, f"❌ 获取连接列表时出错: {e}")
    
    async def play_test_audio(self, ctx, voice_client):
        """播放测试音频文件"""
        import asyncio
        
        try:
            # 获取插件目录下的测试音频文件路径
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            audio_file = os.path.join(plugin_dir, "test_music.mp3")
            
            if not os.path.exists(audio_file):
                await self.reply_message(ctx, "❌ 测试音频文件 test_music.mp3 不存在")
                return
            
            # 检查语音客户端状态
            if not voice_client.is_connected():
                await self.reply_message(ctx, "❌ 语音客户端未连接")
                return
            
            if voice_client.is_playing():
                await self.reply_message(ctx, "⏸️ 正在停止当前播放...")
                voice_client.stop()
                await asyncio.sleep(1.0)
            
            await self.reply_message(ctx, "🎵 开始播放测试音频...")
            
            # 创建播放完成回调
            def after_playing(error):
                if error:
                    print(f'音频播放错误: {error}')
                else:
                    print('音频播放正常完成')
                # 注意：不在这里发送消息，因为这是在音频播放器线程中
                # 消息发送会在主播放逻辑中通过定时检查处理
            
            # 使用优化的 FFmpeg 配置，减少警告信息
            try:
                # 首先尝试带静默日志的配置，减少 MP3 警告
                ffmpeg_options = {
                    'before_options': '-loglevel quiet',
                    'options': '-vn -filter:a "volume=0.5"'
                }
                audio_source = discord.FFmpegPCMAudio(audio_file, **ffmpeg_options)
                voice_client.play(audio_source, after=after_playing)
                
                # 等待一下确认播放开始
                await asyncio.sleep(0.5)
                
                if voice_client.is_playing():
                    await self.reply_message(ctx, "✅ 音频播放已开始")
                    
                    # 可选：监控播放完成（后台任务）
                    asyncio.create_task(self._monitor_playback_completion(ctx, voice_client))
                else:
                    await self.reply_message(ctx, "⚠️ 音频可能没有正常开始播放")
                    
            except Exception as audio_error:
                await self.reply_message(ctx, f"❌ 创建音频源失败: {audio_error}")
                # 使用最简单的备用配置
                try:
                    audio_source = discord.FFmpegPCMAudio(audio_file)
                    voice_client.play(audio_source, after=after_playing)
                    await self.reply_message(ctx, "✅ 使用备用配置开始播放")
                except Exception as fallback_error:
                    await self.reply_message(ctx, f"❌ 备用配置也失败: {fallback_error}")
            
        except Exception as e:
            await self.reply_message(ctx, f"❌ 播放音频时出错: {e}")
            print(f"播放音频详细错误: {e}")
            import traceback
            traceback.print_exc()
    
    async def play_test_audio_command(self, ctx, adapter, guild_id):
        """手动播放测试音频命令"""
        try:
            voice_client = await adapter.get_voice_client(guild_id)
            if not voice_client:
                await self.reply_message(ctx, "❌ 未连接到语音频道，请先使用 !voice join")
                return
            
            await self.play_test_audio(ctx, voice_client)
            
        except Exception as e:
            await self.reply_message(ctx, f"❌ 播放命令执行出错: {e}")
    
    async def stop_audio_command(self, ctx, adapter, guild_id):
        """停止音频播放命令"""
        try:
            voice_client = await adapter.get_voice_client(guild_id)
            if not voice_client:
                await self.reply_message(ctx, "❌ 未连接到语音频道")
                return
            
            if voice_client.is_playing():
                voice_client.stop()
                await self.reply_message(ctx, "⏹️ 已停止音频播放")
            else:
                await self.reply_message(ctx, "ℹ️ 当前没有正在播放的音频")
                
        except Exception as e:
            await self.reply_message(ctx, f"❌ 停止播放时出错: {e}")
    
    async def help_command(self, ctx):
        """显示帮助信息"""
        help_text = """🎵 **Discord 语音功能测试命令**

**基本命令:**
• `!voice join` - 加入你当前所在的语音频道（自动播放测试音频）
• `!voice leave` - 离开语音频道
• `!voice status` - 查看当前连接状态
• `!voice list` - 列出所有活跃连接

**音频控制:**
• `!voice play` - 手动播放测试音频
• `!voice stop` - 停止当前播放

**高级命令:**
• `!voice join <channel_id>` - 加入指定ID的语音频道（自动播放测试音频）

**使用说明:**
1. 使用前请确保机器人有语音频道权限
2. 使用 `!voice join` 前请先加入一个语音频道
3. 机器人需要安装 PyNaCl 和 FFmpeg
4. 测试音频文件：test_music.mp3（需要放在插件目录中）

**权限要求:**
• Connect (连接语音频道)
• Speak (在语音频道说话)
• Use Voice Activity (使用语音激活)"""
        
        await self.reply_message(ctx, help_text)
    
    async def reply_message(self, ctx, text):
        """回复消息"""
        from pkg.platform.types.message import MessageChain, Plain
        
        try:
            await ctx.send_message(
                ctx.event.launcher_type,
                str(ctx.event.launcher_id),
                MessageChain([Plain(text=text)])
            )
        except Exception as e:
            # 如果发送失败，至少记录日志
            print(f"发送消息失败: {e}")

    async def _monitor_playback_completion(self, ctx, voice_client):
        """监控播放完成状态"""
        import asyncio
        
        try:
            # 等待播放完成
            while voice_client.is_playing():
                await asyncio.sleep(1.0)
            
            # 播放完成后发送消息
            await self.reply_message(ctx, "🎵 音频播放完成")
            
        except Exception as e:
            print(f"监控播放完成时出错: {e}")

    # 插件卸载时触发
    def __del__(self):
        pass
