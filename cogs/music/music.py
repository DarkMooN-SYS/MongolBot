import discord
from discord.ext import commands
import wavelink
from typing import TYPE_CHECKING, List, Optional
from datetime import timedelta
import asyncio
import time  # Add time import for idle tracking
from ..utils.channel import is_channel_enabled
from ..utils.rate_limit_decorators import rate_limit_command  # Rate limiting import

if TYPE_CHECKING:
    from discord.ext.commands import Bot, Context

class MusicControlView(discord.ui.View):
    """🎵 Музыкийн удирдлагын button-ууд"""
    def __init__(self, music_cog: 'Music', guild_id: int):
        super().__init__(timeout=300)  # 5 минутын timeout
        self.music_cog = music_cog
        self.guild_id = guild_id
    
    @discord.ui.button(emoji='⏸️', style=discord.ButtonStyle.secondary, label='Pause')
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Pause button"""
        if not interaction.guild or interaction.guild.id != self.guild_id:
            return
            
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        if not player or not player.playing:
            await interaction.response.send_message("❌ Дуу тоглогдохгүй байна!", ephemeral=True)
            return
        
        await player.pause(True)
        button.emoji = '▶️'
        button.label = 'Resume'
        await interaction.response.edit_message(view=self)
        
        # Channel-д мэдэгдэх
        embed = discord.Embed(
            title="⏸️ Дуу түр зогслоо",
            description=f"**{player.current.title if player.current else 'Дуу'}** түр зогслоо",
            color=0xffaa00
        )
        await interaction.followup.send(embed=embed, ephemeral=False)
    
    @discord.ui.button(emoji='▶️', style=discord.ButtonStyle.success, label='Resume')
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Resume button"""
        if not interaction.guild or interaction.guild.id != self.guild_id:
            return
            
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        if not player or not player.paused:
            await interaction.response.send_message("❌ Дуу түр зогсоогдоогүй байна!", ephemeral=True)
            return
        
        await player.pause(False)
        button.emoji = '⏸️'
        button.label = 'Pause'
        await interaction.response.edit_message(view=self)
        
        # Channel-д мэдэгдэх
        embed = discord.Embed(
            title="▶️ Дуу үргэлжиллээ!",
            description=f"**{player.current.title if player.current else 'Дуу'}** дахин тоглож эхэллээ!",
            color=0x00ff00
        )
        await interaction.followup.send(embed=embed, ephemeral=False)
    
    @discord.ui.button(emoji='⏭️', style=discord.ButtonStyle.primary, label='Skip')
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Skip button"""
        if not interaction.guild or interaction.guild.id != self.guild_id:
            return
            
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        if not player or not player.playing:
            await interaction.response.send_message("❌ Дуу тоглогдохгүй байна!", ephemeral=True)
            return
        
        queue = self.music_cog.get_queue(self.guild_id)
        current_track = player.current
        
        # Түүхэнд хадгалах
        if current_track:
            queue.add_to_history(current_track)
        
        await player.stop()
        await interaction.response.send_message("⏭️ Skip хийлээ!", ephemeral=False)
    
    @discord.ui.button(emoji='⏹️', style=discord.ButtonStyle.danger, label='Stop')
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Stop button"""
        if not interaction.guild or interaction.guild.id != self.guild_id:
            return
            
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        queue = self.music_cog.get_queue(self.guild_id)
        
        if player and player.playing:
            await player.stop()
        
        queue.clear()
        
        embed = discord.Embed(
            title="⏹️ Музык зогслоо",
            description="Дуу зогсч, queue цэвэрлэгдлээ!",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)
        
        # View-г идэвхгүй болгох
        for item in self.children:
            try:
                item.disabled = True  # type: ignore
            except:
                pass
        try:
            await interaction.edit_original_response(view=self)
        except:
            pass
    
    @discord.ui.button(emoji='🔄', style=discord.ButtonStyle.secondary, label='Loop')
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Loop mode солих button"""
        if not interaction.guild or interaction.guild.id != self.guild_id:
            return
            
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        if not player or not player.current:
            await interaction.response.send_message("❌ Дуу тоглогдохгүй байна!", ephemeral=True)
            return
            
        queue = self.music_cog.get_queue(self.guild_id)
        current_mode = getattr(queue, 'loop_mode', 'off')
        
        # Loop mode toggle: off -> on -> off
        if current_mode == 'off':
            queue.loop_mode = 'on'
            title = "🔂 Track Loop идэвхжлээ"
            description = f"**{player.current.title}** дуусах бүрд дахин тоглох болно"
            color = 0x9B59B6
            button.emoji = '🔂'
            button.style = discord.ButtonStyle.primary
        else:  # on
            queue.loop_mode = 'off'
            title = "❌ Loop унтраагдлаа"
            description = "Дуу давтахгүй болно"
            color = 0x95A5A6
            button.emoji = '🔄'
            button.style = discord.ButtonStyle.secondary
            
        embed = discord.Embed(title=title, description=description, color=color)
        embed.add_field(
            name="🎵 Одоогийн дуу",
            value=f"**{player.current.title}**",
            inline=False
        )
        
        # View-г шинэчлэх
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(embed=embed, ephemeral=False)
    
    @discord.ui.button(emoji='📋', style=discord.ButtonStyle.secondary, label='Queue')
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Queue button"""
        if not interaction.guild or interaction.guild.id != self.guild_id:
            return
        
        queue = self.music_cog.get_queue(self.guild_id)
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        
        embed = discord.Embed(
            title="📋 Музыкийн дараалал",
            description=f"🎵 **{interaction.guild.name}** серверийн дууны жагсаалт",
            color=0x3498db
        )
        
        # Одоо тоглож байгаа дуу
        if player and player.current:
            current_track = player.current
            status_emoji = '▶️' if player.playing else '⏸️'
            embed.add_field(
                name=f"{status_emoji} **Одоо тоглож байна**",
                value=f"**{current_track.title}**\n👤 `{current_track.author}`",
                inline=False
            )
        
        # Queue мэдээлэл
        if queue.is_empty():
            embed.add_field(
                name="ℹ️ Queue хоосон",
                value="Queue-д дуу алга байна.",
                inline=False
            )
        else:
            queue_text = ""
            for i, track in enumerate(queue.tracks[:5], 1):
                title = track.title[:30] + "..." if len(track.title) > 30 else track.title
                queue_text += f"`{i}.` **{title}**\n"
            
            if queue.size() > 5:
                queue_text += f"**... болон өөр {queue.size() - 5} дуу**"
            
            embed.add_field(
                name=f"📋 **Queue ({queue.size()} дуу)**",
                value=queue_text,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class LoopView(discord.ui.View):
    """🔄 Loop удирдлагын button-ууд (зөвхөн track loop)"""
    def __init__(self, music_cog: 'Music', guild_id: int):
        super().__init__(timeout=120)
        self.music_cog = music_cog
        self.guild_id = guild_id
    
    @discord.ui.button(emoji='❌', style=discord.ButtonStyle.secondary, label='Loop Off')
    async def loop_off_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Loop off button"""
        await self._set_loop_mode(interaction, 'off')
    
    @discord.ui.button(emoji='🔂', style=discord.ButtonStyle.primary, label='Loop Track')
    async def loop_track_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Loop track button"""
        await self._set_loop_mode(interaction, 'on')
    
    async def _set_loop_mode(self, interaction: discord.Interaction, mode: str):
        """Loop mode тохируулах helper функц"""
        queue = self.music_cog.get_queue(self.guild_id)
        queue.loop_mode = mode
        
        if mode == 'off':
            title = "❌ Loop унтраагдлаа"
            description = "Дуу давтахгүй болно"
            color = 0xff0000
        else:  # on
            title = "🔂 Дуу давтах горим идэвхжлээ"
            description = "Одоогийн дуу дуусах бүрд дахин тоглох болно"
            color = 0x00ff00
        
        embed = discord.Embed(title=title, description=description, color=color)
        await interaction.response.send_message(embed=embed, ephemeral=False)

class MusicQueue:
    """🎵 Дуунуудын дараалал удирдах класс"""
    def __init__(self):
        self.tracks: List[wavelink.Playable] = []
        self.current_track: Optional[wavelink.Playable] = None
        self.loop = False
        self.shuffle = False
        self.history: List[wavelink.Playable] = []  # Өмнө тоглосон дуунууд
        self.loop_mode: str = 'off'  # 'off', 'on', 'queue'
    
    def add(self, track: wavelink.Playable):
        """🎵 Дуу нэмэх"""
        self.tracks.append(track)
    
    def next(self) -> Optional[wavelink.Playable]:
        """⏭️ Дараагийн дуу авах"""
        if not self.tracks:
            return None
        return self.tracks.pop(0)
    
    def clear(self):
        """🗑️ Queue цэвэрлэх"""
        self.tracks.clear()
        self.current_track = None
    
    def is_empty(self) -> bool:
        """❓ Queue хоосон эсэхийг шалгах"""
        return len(self.tracks) == 0
    
    def size(self) -> int:
        """📊 Queue-ын хэмжээ"""
        return len(self.tracks)
    
    def add_to_history(self, track: wavelink.Playable):
        """📚 Түүхэнд нэмэх"""
        self.history.append(track)
        if len(self.history) > 50:  # Хамгийн ихдээ 50 дуу хадгалах
            self.history.pop(0)

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.loop.create_task(self.start_lavalink())
        self.queues = {}  # Guild бүрт тусдаа queue
        self.players_connected = set()  # Холбогдсон player-уудыг хадгалах
        self.guild_volumes = {}  # Guild тус бүрийн volume хадгалах
        self.default_volume = 50  # Default volume 50%
        
        # Auto-disconnect tracking
        self.last_activity = {}  # Guild-ийн сүүлийн идэвхжил
        self.idle_check_task = self.bot.loop.create_task(self.check_idle_players())
        
        # 🎨 UI Colors
        self.colors = {
            'success': 0x00ff88,     # Ногоон
            'error': 0xff3366,       # Улаан
            'warning': 0xffaa00,     # Шар
            'info': 0x5865f2,        # Цэнхэр
            'music': 0x9c59b6,       # Ягаан
            'queue': 0x3498db        # Гэрэл цэнхэр
        }
        
        # 🎵 Music Status Emojis
        self.emojis = {
            'play': '▶️',
            'pause': '⏸️',
            'stop': '⏹️',
            'skip': '⏭️',
            'back': '⏮️',
            'loop': '🔄',
            'shuffle': '🔀',
            'volume_mute': '🔇',
            'volume_low': '🔈',
            'volume_med': '🔉',
            'volume_high': '🔊',
            'note': '🎵',
            'notes': '🎶',
            'headphones': '🎧',
            'microphone': '🎤',
            'radio': '📻',
            'musical_note': '♪',
            'double_note': '♫',
            'loading': '⏳',
            'success': '✅',
            'error': '❌',
            'warning': '⚠️',
            'info': 'ℹ️',
            'queue': '📋',
            'history': '📚',
            'fire': '🔥',
            'star': '⭐',
            'heart': '💖',
            'clock': '⏰'
        }

    def format_duration(self, milliseconds: int) -> str:
        """⏱️ Хугацааг форматлах"""
        if milliseconds == 0:
            return "🔴 Live"
        
        seconds = milliseconds // 1000
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    
    def create_progress_bar(self, current: int, total: int, length: int = 20) -> str:
        """📊 Progress bar үүсгэх"""
        if total == 0:
            return "🔴 Live Stream"
        
        filled = int(length * current / total)
        bar = "▰" * filled + "▱" * (length - filled)
        percentage = int(100 * current / total)
        return f"{bar} {percentage}%"
    
    def get_volume_emoji(self, volume: int) -> str:
        """🔊 Volume emoji авах"""
        if volume == 0:
            return self.emojis['volume_mute']
        elif volume <= 25:
            return self.emojis['volume_low']
        elif volume <= 75:
            return self.emojis['volume_med']
        else:
            return self.emojis['volume_high']
    
    def create_music_embed(self, title: str, description: str = "", color: str = 'music') -> discord.Embed:
        """🎨 Музыкийн embed үүсгэх"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=self.colors.get(color, self.colors['music'])
        )
        embed.set_footer(
            text="🎵 MongolBot Music System | Mongolian Music Experience",
            icon_url="https://cdn.discordapp.com/emojis/741605543046807626.png"
        )
        return embed

    async def start_lavalink(self):
        """Lavalink серверт холбогдох"""
        await self.bot.wait_until_ready()
        try:
            node = wavelink.Node(uri='http://67.220.85.182:6576', password='Dragon95279853')
            await wavelink.Pool.connect(client=self.bot, nodes=[node])
            print("✅ Lavalink серверт амжилттай холбогдлоо")
        except Exception as e:
            print(f"❌ Lavalink серверт холбогдоход алдаа: {e}")

    def get_queue(self, guild_id: int) -> MusicQueue:
        """Guild-ийн queue авах эсвэл үүсгэх"""
        if guild_id not in self.queues:
            self.queues[guild_id] = MusicQueue()
        return self.queues[guild_id]

    async def ensure_voice_connection(self, ctx: commands.Context) -> Optional[wavelink.Player]:
        """Voice холболтыг шалгах болон үүсгэх"""
        if not ctx.voice_client:
            voice_state = getattr(ctx.author, 'voice', None)
            if not voice_state or not voice_state.channel:
                await ctx.send('❌ Та voice channel-д ороогүй байна!')
                return None
            
            try:
                player = await voice_state.channel.connect(cls=wavelink.Player)
                # Guild-ийн сонгосон volume эсвэл default volume ашиглах
                guild_volume = self.guild_volumes.get(ctx.guild.id if ctx.guild else 0, self.default_volume)
                await player.set_volume(guild_volume)
                
                if ctx.guild:
                    self.players_connected.add(ctx.guild.id)
                await ctx.send(f'✅ {voice_state.channel.name} channel-д холбогдлоо!')
            except Exception as e:
                await ctx.send(f'❌ Voice channel-д холбогдоход алдаа: {e}')
                return None
        
        return ctx.voice_client  # type: ignore

    async def check_idle_players(self):
        """5 минут идэвхгүй байвал auto disconnect"""
        while not self.bot.is_closed():
            await asyncio.sleep(60)  # 1 минут тутамд шалгах
            
            current_time = time.time()
            disconnected_guilds = []
            
            for guild_id in list(self.last_activity.keys()):
                last_time = self.last_activity.get(guild_id, current_time)
                idle_time = current_time - last_time
                
                if idle_time >= 300:  # 5 минут = 300 секунд
                    guild = self.bot.get_guild(guild_id)
                    if guild and guild.voice_client:
                        player = guild.voice_client
                        
                        # Check if actually idle (not playing) - ensure it's a wavelink.Player
                        if isinstance(player, wavelink.Player) and not player.playing and not player.paused:
                            try:
                                # Send notification
                                if hasattr(player, 'channel') and player.channel:
                                    embed = discord.Embed(
                                        title="😴 Auto Disconnect",
                                        description="5 минут идэвхгүй байсан тул voice channel-оос гарлаа.",
                                        color=0x95A5A6
                                    )
                                    embed.add_field(
                                        name="💡 Дахин холбогдох",
                                        value="`mplay <дуу>` ашиглан дахин холбогдоно уу",
                                        inline=False
                                    )
                                    await player.channel.send(embed=embed)
                                
                                # Disconnect
                                await player.disconnect(force=True)
                                
                                # Clean up
                                if guild_id in self.players_connected:
                                    self.players_connected.remove(guild_id)
                                
                                queue = self.get_queue(guild_id)
                                queue.clear()
                                
                                disconnected_guilds.append(guild_id)
                                
                            except Exception as e:
                                print(f"❌ Auto disconnect алдаа: {e}")
            
            # Clean up disconnected guilds
            for guild_id in disconnected_guilds:
                if guild_id in self.last_activity:
                    del self.last_activity[guild_id]

    def update_activity(self, guild_id: int):
        """Guild-ийн идэвхжилийг шинэчлэх"""
        self.last_activity[guild_id] = time.time()

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """Дуу дуусах үед автомат дараагийн дуу тоглуулах"""
        player = payload.player
        if not player or not getattr(player, "guild", None):
            return
            
        if not player.guild:
            return

        guild_id = player.guild.id
        queue = self.get_queue(guild_id)
        
        # Update activity
        self.update_activity(guild_id)
        
        # Loop mode шалгах
        loop_mode = getattr(queue, 'loop_mode', 'off')
        
        if loop_mode == 'on' and queue.current_track:
            # Одоогийн дууг дахин тоглуулах (embed мэдэгдэлгүйгээр)
            try:
                await player.play(queue.current_track)
                return
            except Exception as e:
                print(f"❌ Loop track тоглуулахад алдаа: {e}")
        
        if not queue.is_empty():
            next_track = queue.next()
            if next_track:
                try:
                    await player.play(next_track)
                    queue.current_track = next_track
                    # Channel-д мэдэгдэх (хэрэв боломжтой бол)
                    if hasattr(player, 'channel') and player.channel:
                        # Modern embed with enhanced UI/UX
                        embed = discord.Embed(
                            title="🎵 Дараагийн дуу эхэллээ",
                            description=f"**{next_track.title}**",
                            color=0x1DB954
                        )
                        embed.add_field(name="🎤 Зохиогч", value=next_track.author, inline=True)
                        embed.add_field(name="⏱️ Үргэлжлэх хугацаа", value=f"`{self.format_duration(next_track.length)}`", inline=True)
                        embed.add_field(name="🔄 Loop Mode", value=loop_mode.title(), inline=True)
                        
                        # Add thumbnail if available (check for uri and artwork)
                        if hasattr(next_track, 'artwork') and next_track.artwork:
                            embed.set_thumbnail(url=next_track.artwork)
                        elif hasattr(next_track, 'uri') and 'youtube' in str(next_track.uri):
                            # Generate YouTube thumbnail from video ID if possible
                            try:
                                video_id = str(next_track.uri).split('v=')[1].split('&')[0] if 'v=' in str(next_track.uri) else None
                                if video_id:
                                    embed.set_thumbnail(url=f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg")
                            except:
                                pass
                        
                        # Queue info
                        remaining = len(queue.tracks)
                        embed.add_field(name="📜 Queue", value=f"{remaining} дуу үлдсэн", inline=True)
                        
                        # Add extras info if available
                        if hasattr(next_track, 'extras') and next_track.extras:
                            try:
                                requester = getattr(next_track.extras, 'requester', None)
                                if requester:
                                    embed.add_field(name="👤 Хүсэлт тавьсан", value=requester.mention, inline=True)
                            except:
                                pass
                        
                        embed.set_footer(text="🎶 Музыкийн бот | Auto-playing next track")
                        
                        # Create control view for auto-next notification
                        view = MusicControlView(self, player.guild.id)
                        await player.channel.send(embed=embed, view=view)
                except Exception as e:
                    print(f"❌ Дараагийн дуу тоглуулахад алдаа: {e}")

    def cog_check(self, ctx: commands.Context) -> bool:
        # Only allow commands in guilds; channel enable check must be async elsewhere
        if not ctx.guild:
            return False
        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        # Async channel check here
        if ctx.guild is None or not await is_channel_enabled(ctx.guild.id, ctx.channel.id):
            await ctx.send("Энэ channel-д команд ашиглах боломжгүй!")
            raise commands.CheckFailure("Channel not enabled for commands.")

    @commands.command(name='play', aliases=['p'])
    @rate_limit_command()  # Rate limiting нэмэх
    async def play(self, ctx: commands.Context, *, search: str):
        """🎵 Дуу тоглуулах эсвэл queue-д нэмэх"""
        if not ctx.guild:
            return
        
        # Update activity
        self.update_activity(ctx.guild.id)
            
        player = await self.ensure_voice_connection(ctx)
        if not player:
            return
        
        # Loading message
        loading_embed = self.create_music_embed(
            f"{self.emojis['loading']} Дуу хайж байна...",
            f"**Хайлт:** `{search}`",
            'warning'
        )
        loading_msg = await ctx.send(embed=loading_embed)
            
        # Дуу хайх
        try:
            tracks = await wavelink.Pool.fetch_tracks(f'ytsearch:{search}')
            if not tracks:
                embed = self.create_music_embed(
                    f"{self.emojis['error']} Дуу олдсонгүй",
                    f"**'{search}'** гэсэн хайлтаар дуу олдсонгүй.\n\n"
                    f"💡 **Зөвлөмж:**\n"
                    f"• Дууны нэр, зохиогчийн нэрийг бүрэн бичнэ үү\n"
                    f"• YouTube URL ашиглана уу\n"
                    f"• Өөр түлхүүр үг ашиглана уу",
                    'error'
                )
                embed.add_field(
                    name=f"{self.emojis['info']} Жишээ",
                    value="`mplay Ariunaa - Mongol heleер`\n`mplay https://youtube.com/watch?v=...`",
                    inline=False
                )
                await loading_msg.edit(embed=embed)
                return
        except Exception as e:
            embed = self.create_music_embed(
                f"{self.emojis['error']} Хайлтад алдаа гарлаа",
                f"**Алдаа:** `{str(e)[:100]}...`\n\n"
                f"💡 Дахин оролдоно уу эсвэл админтай холбогдоно уу.",
                'error'
            )
            await loading_msg.edit(embed=embed)
            return
            
        track = tracks[0]
        queue = self.get_queue(ctx.guild.id)
        
        # Хэрэв одоо дуу тоглохгүй байвал шууд тоглуулах (queue-д нэмэхгүй)
        if not player.playing and not player.paused and queue.is_empty():
            try:
                await player.play(track)
                queue.current_track = track
                
                # Одоо тоглож байна embed
                embed = self.create_music_embed(
                    f"{self.emojis['notes']} Одоо тоглож байна",
                    f"**{track.title}**",
                    'success'
                )
                
                # Thumbnail нэмэх (хэрэв боломжтой бол)
                if hasattr(track, 'artwork') and track.artwork:
                    embed.set_thumbnail(url=track.artwork)
                
                embed.add_field(
                    name=f"{self.emojis['microphone']} Зохиогч",
                    value=f"`{track.author}`",
                    inline=True
                )
                embed.add_field(
                    name=f"{self.emojis['clock']} Үргэлжлэх хугацаа",
                    value=f"`{self.format_duration(track.length)}`",
                    inline=True
                )
                embed.add_field(
                    name=f"{self.emojis['queue']} Queue",
                    value=f"`{self.emojis['heart']} Хоосон`",
                    inline=True
                )
                
                await loading_msg.edit(embed=embed)
                
                # Music control buttons нэмэх
                view = MusicControlView(self, ctx.guild.id)
                await loading_msg.edit(embed=embed, view=view)
                
            except Exception as e:
                embed = self.create_music_embed(
                    f"{self.emojis['error']} Дуу тоглуулахад алдаа гарлаа",
                    f"**Алдаа:** `{str(e)[:100]}...`",
                    'error'
                )
                await loading_msg.edit(embed=embed)
        else:
            # Дуу тоглож байвал эсвэл queue-д дуу байвал queue-д нэмэх
            queue.add(track)
            
            embed = self.create_music_embed(
                f"{self.emojis['success']} Дуу queue-д нэмэгдлээ",
                f"**{track.title}**",
                'success'
            )
            
            # Thumbnail нэмэх
            if hasattr(track, 'artwork') and track.artwork:
                embed.set_thumbnail(url=track.artwork)
            
            embed.add_field(
                name=f"{self.emojis['microphone']} Зохиогч",
                value=f"`{track.author}`",
                inline=True
            )
            embed.add_field(
                name=f"⏰ Үргэлжлэх хугацаа",
                value=f"`{self.format_duration(track.length)}`",
                inline=True
            )
            embed.add_field(
                name=f"{self.emojis['queue']} Queue байрлал",
                value=f"`#{queue.size()} | {self.emojis['fire']} {queue.size()} дуу`",
                inline=True
            )
            
            # Queue-ын нийт хугацаа тооцоолох
            total_duration = sum(t.length for t in queue.tracks if t.length > 0)
            if total_duration > 0:
                embed.add_field(
                    name=f"⏱️ Хүлээх хугацаа",
                    value=f"`~{self.format_duration(total_duration)}`",
                    inline=True
                )
            
            # Одоо тоглож байгаа дуу харуулах
            if queue.current_track:
                embed.add_field(
                    name=f"{self.emojis['notes']} Одоо тоглож байна",
                    value=f"`{queue.current_track.title[:50]}...`" if len(queue.current_track.title) > 50 else f"`{queue.current_track.title}`",
                    inline=False
                )
            
            await loading_msg.edit(embed=embed)
            
            # Music control buttons нэмэх
            view = MusicControlView(self, ctx.guild.id)
            await loading_msg.edit(embed=embed, view=view)

    @commands.command(name='loop', aliases=['repeat'])
    async def toggle_loop(self, ctx: commands.Context, mode: Optional[str] = None):
        """🔄 Loop горим солих - Button ашиглан илүү хялбар!"""
        if not ctx.guild:
            return
            
        queue = self.get_queue(ctx.guild.id)
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        if not player:
            embed = self.create_music_embed(
                f"{self.emojis['error']} Бот холбогдоогүй байна",
                f"Loop тохируулахын тулд бот voice channel-д байх ёстой.",
                'error'
            )
            await ctx.send(embed=embed)
            return
        
        if not player.current:
            embed = self.create_music_embed(
                f"{self.emojis['error']} Дуу тоглохгүй байна",
                f"Loop тохируулахын тулд дуу тоглож байх ёстой.\n\n"
                f"💡 **Дуу тоглуулахын тулд:** `{ctx.prefix}play <дууны нэр>`",
                'error'
            )
            await ctx.send(embed=embed)
            return
        
        # Хэрэв mode заагаагүй бол button-тай мэдэгдэл илгээх
        if mode is None:
            current_mode = getattr(queue, 'loop_mode', 'off')
            
            embed = self.create_music_embed(
                f"{self.emojis['loop']} Loop удирдлага",
                f"Button-ууд ашиглан loop горим солино уу!",
                'info'
            )
            
            embed.add_field(
                name=f"{self.emojis['notes']} Одоогийн дуу",
                value=f"**{player.current.title}**",
                inline=False
            )
            
            embed.add_field(
                name=f"{self.emojis['info']} Одоогийн горим",
                value=f"`{current_mode.title()}`",
                inline=True
            )
            
            embed.add_field(
                name=f"{self.emojis['info']} Горимууд",
                value="🔄 Off - Давтахгүй\n🔂 Track - Дуу давтах",
                inline=True
            )
            
            # Loop control buttons нэмэх
            view = MusicControlView(self, ctx.guild.id)
            msg = await ctx.send(embed=embed, view=view)
            return
        
        # Хэрэв mode заасан бол (off/on гэх мэт)
        mode = mode.lower()
        if mode not in ['off', 'on']:
            embed = self.create_music_embed(
                f"{self.emojis['error']} Буруу горим",
                f"**Боломжит горимууд:** `off`, `on`\n\n"
                f"💡 **Button ашиглах:** `{ctx.prefix}loop` (mode заахгүйгээр)",
                'error'
            )
            await ctx.send(embed=embed)
            return
        
        # Loop mode тохируулах
        queue.loop_mode = mode
        
        # Мэдэгдэл үүсгэх
        if mode == 'off':
            title = f"❌ Loop унтраагдлаа"
            description = f"**{player.current.title}** давтахгүй болно"
            color = 'error'
        else:  # on
            title = f"🔂 Дуу давтах горим идэвхжлээ"
            description = f"**{player.current.title}** дуусах бүрд дахин тоглох болно"
            color = 'success'
        
        embed = self.create_music_embed(title, description, color)
        
        embed.add_field(
            name=f"{self.emojis['notes']} Одоогийн дуу",
            value=f"**{player.current.title}**",
            inline=False
        )
        
        embed.add_field(
            name=f"{self.emojis['queue']} Queue",
            value=f"{queue.size()} дуу хүлээж байна",
            inline=True
        )
        
        msg = await ctx.send(embed=embed)
        await msg.add_reaction(self.emojis['loop'])
        
        # Music control buttons нэмэх (хэрэв дуу тоглож байвал)
        if player and player.current:
            view = MusicControlView(self, ctx.guild.id)
            await msg.edit(embed=embed, view=view)

    @commands.command(name='volume', aliases=['vol', 'v'])
    async def set_volume(self, ctx: commands.Context, volume: Optional[int] = None):
        """🔊 Volume тохируулах (0-100%)"""
        if not ctx.guild:
            return
            
        player: wavelink.Player = ctx.voice_client  # type: ignore
        if not player:
            embed = self.create_music_embed(
                f"{self.emojis['error']} Бот холбогдоогүй байна",
                f"Volume тохируулахын тулд бот voice channel-д байх ёстой.",
                'error'
            )
            await ctx.send(embed=embed)
            return
        
        # Хэрэв volume заагаагүй бол одоогийн volume харуулах
        if volume is None:
            current_volume = self.guild_volumes.get(ctx.guild.id, self.default_volume)
            
            embed = self.create_music_embed(
                f"{self.get_volume_emoji(current_volume)} Одоогийн Volume",
                f"Volume: **{current_volume}%**",
                'info'
            )
            
            embed.add_field(
                name=f"{self.emojis['info']} Команд ашиглах",
                value=f"`{ctx.prefix}volume <0-100>`\n\n**Жишээ:**\n`{ctx.prefix}volume 50` - 50%\n`{ctx.prefix}volume 0` - Mute\n`{ctx.prefix}volume 100` - Max",
                inline=False
            )
            
            # Одоо тоглож байгаа дуу харуулах
            if player.current:
                embed.add_field(
                    name=f"{self.emojis['notes']} Одоо тоглож байна",
                    value=f"**{player.current.title}**",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            return
        
        # Volume тоо шалгах
        if not (0 <= volume <= 100):
            embed = self.create_music_embed(
                f"{self.emojis['error']} Буруу volume",
                f"Volume 0-100 хооронд байх ёстой.\n\n"
                f"💡 **Жишээ:** `{ctx.prefix}volume 50`",
                'error'
            )
            await ctx.send(embed=embed)
            return
        
        # Volume тохируулах
        try:
            await player.set_volume(volume)
            self.guild_volumes[ctx.guild.id] = volume
            
            # Volume emoji авах
            volume_emoji = self.get_volume_emoji(volume)
            
            if volume == 0:
                title = f"{volume_emoji} Дуу хаагдлаа"
                description = f"Volume: **{volume}%** (Muted)"
                color = 'error'
            elif volume <= 25:
                title = f"{volume_emoji} Бага volume"
                description = f"Volume: **{volume}%**"
                color = 'warning'
            elif volume <= 75:
                title = f"{volume_emoji} Дунд volume"
                description = f"Volume: **{volume}%**"
                color = 'info'
            else:
                title = f"{volume_emoji} Их volume"
                description = f"Volume: **{volume}%**"
                color = 'success'
            
            embed = self.create_music_embed(title, description, color)
            
            if volume > 85:
                embed.add_field(
                    name="⚠️ Анхааруулга",
                    value="Маш чанга тохиргоо! Чихэндээ анхаарна уу.",
                    inline=False
                )
            
            # Одоо тоглож байгаа дуу харуулах
            if player.current:
                embed.add_field(
                    name=f"{self.emojis['notes']} Одоо тоглож байна",
                    value=f"**{player.current.title}**",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = self.create_music_embed(
                f"{self.emojis['error']} Volume тохируулахад алдаа гарлаа",
                f"**Алдаа:** `{str(e)[:100]}...`",
                'error'
            )
            await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))