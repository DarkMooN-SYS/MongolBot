import discord
from discord.ext import commands
import wavelink
from typing import TYPE_CHECKING, List, Optional
from datetime import timedelta
import asyncio
import random
import math
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

class VolumeView(discord.ui.View):
    """🔊 Volume удирдлагын button-ууд"""
    def __init__(self, music_cog: 'Music', guild_id: int, current_volume: int):
        super().__init__(timeout=120)
        self.music_cog = music_cog
        self.guild_id = guild_id
        self.current_volume = current_volume
    
    @discord.ui.button(emoji='🔇', style=discord.ButtonStyle.secondary, label='Mute')
    async def mute_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mute button"""
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        if not player:
            await interaction.response.send_message("❌ Бот холбогдоогүй байна!", ephemeral=True)
            return
        
        await player.set_volume(0)
        self.music_cog.guild_volumes[self.guild_id] = 0
        
        embed = discord.Embed(
            title="🔇 Дуу хаагдлаа",
            description="Volume: **0%**",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)
    
    @discord.ui.button(emoji='🔈', style=discord.ButtonStyle.secondary, label='25%')
    async def low_volume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """25% volume button"""
        await self._set_volume(interaction, 25)
    
    @discord.ui.button(emoji='🔉', style=discord.ButtonStyle.secondary, label='50%')
    async def medium_volume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """50% volume button"""
        await self._set_volume(interaction, 50)
    
    @discord.ui.button(emoji='🔊', style=discord.ButtonStyle.secondary, label='75%')
    async def high_volume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """75% volume button"""
        await self._set_volume(interaction, 75)
    
    @discord.ui.button(emoji='🔥', style=discord.ButtonStyle.danger, label='100%')
    async def max_volume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """100% volume button"""
        await self._set_volume(interaction, 100)
    
    async def _set_volume(self, interaction: discord.Interaction, volume: int):
        """Volume тохируулах helper функц"""
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        if not player:
            await interaction.response.send_message("❌ Бот холбогдоогүй байна!", ephemeral=True)
            return
        
        await player.set_volume(volume)
        self.music_cog.guild_volumes[self.guild_id] = volume
        
        # Volume emoji авах
        if volume == 0:
            volume_emoji = "🔇"
        elif volume <= 25:
            volume_emoji = "🔈"
        elif volume <= 75:
            volume_emoji = "🔉"
        else:
            volume_emoji = "🔊"
        
        embed = discord.Embed(
            title=f"{volume_emoji} Дууны чанга өөрчлөгдлөө",
            description=f"Шинэ чанга: **{volume}%**",
            color=0x00ff00
        )
        
        if volume > 85:
            embed.add_field(
                name="⚠️ Анхааруулга",
                value="Маш чанга тохиргоо! Чихэндээ анхаарна уу.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

class LoopView(discord.ui.View):
    """🔄 Loop удирдлагын button-ууд"""
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
    
    @discord.ui.button(emoji='🔁', style=discord.ButtonStyle.success, label='Loop Queue')
    async def loop_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Loop queue button"""
        await self._set_loop_mode(interaction, 'queue')
    
    async def _set_loop_mode(self, interaction: discord.Interaction, mode: str):
        """Loop mode тохируулах helper функц"""
        queue = self.music_cog.get_queue(self.guild_id)
        queue.loop_mode = mode
        
        if mode == 'off':
            title = "❌ Loop унтраагдлаа"
            description = "Дуу давтахгүй болно"
            color = 0xff0000
        elif mode == 'on':
            title = "🔂 Дуу давтах горим идэвхжлээ"
            description = "Одоогийн дуу дуусах бүрд дахин тоглох болно"
            color = 0x00ff00
        else:  # queue
            title = "🔁 Queue давтах горим идэвхжлээ"
            description = "Queue дуусах бүрд эхнээс нь эхэлнэ"
            color = 0x0099ff
        
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
        self.loop_mode: str = 'off'  # 'off', 'track', 'queue'
    
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
    
    def shuffle_tracks(self):
        """🔀 Queue-г холих"""
        random.shuffle(self.tracks)
    
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

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """Дуу дуусах үед автомат дараагийн дуу тоглуулах"""
        player = payload.player
        if not player or not getattr(player, "guild", None):
            return
            
        if not getattr(player, "guild", None):
            return

        if not player.guild:
            return
        queue = self.get_queue(player.guild.id)
        
        # Loop mode шалгах
        loop_mode = getattr(queue, 'loop_mode', 'off')
        
        if loop_mode == 'track' and queue.current_track:
            # Одоогийн дууг дахин тоглуулах
            try:
                await player.play(queue.current_track)
                
                # Enhanced UI for track loop
                if hasattr(player, 'channel') and player.channel:
                    embed = discord.Embed(
                        title="🔁 Track Loop | Дуу давтагдаж байна",
                        description=f"**{queue.current_track.title}**",
                        color=0x9B59B6
                    )
                    embed.add_field(name="🎤 Зохиогч", value=queue.current_track.author, inline=True)
                    embed.add_field(name="⏱️ Үргэлжлэх хугацаа", value=f"`{self.format_duration(queue.current_track.length)}`", inline=True)
                    embed.add_field(name="🔄 Loop Mode", value="Track", inline=True)
                    
                    # Add thumbnail if available
                    if hasattr(queue.current_track, 'artwork') and queue.current_track.artwork:
                        embed.set_thumbnail(url=queue.current_track.artwork)
                    elif hasattr(queue.current_track, 'uri') and 'youtube' in str(queue.current_track.uri):
                        try:
                            video_id = str(queue.current_track.uri).split('v=')[1].split('&')[0] if 'v=' in str(queue.current_track.uri) else None
                            if video_id:
                                embed.set_thumbnail(url=f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg")
                        except:
                            pass
                    
                    embed.set_footer(text="🎶 Музыкийн бот | Track loop режим")
                    
                    # Create control view
                    view = MusicControlView(self, player.guild.id)
                    await player.channel.send(embed=embed, view=view)
                
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
                            title="🎵 Auto-Next | Дараагийн дуу эхэллээ",
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
        elif loop_mode == 'queue' and queue.history:
            # Queue loop: Түүхээс дуунуудыг буцааж queue-д оруулах
            queue.tracks.extend(queue.history.copy())
            queue.history.clear()
            if queue.tracks:
                next_track = queue.next()
                if next_track:
                    try:
                        await player.play(next_track)
                        queue.current_track = next_track
                        
                        # Enhanced UI for queue loop
                        if hasattr(player, 'channel') and player.channel:
                            embed = discord.Embed(
                                title="🔄 Queue Loop | Дахин эхэллээ",
                                description=f"**{next_track.title}**",
                                color=0xFF6B35
                            )
                            embed.add_field(name="🎤 Зохиогч", value=next_track.author, inline=True)
                            embed.add_field(name="⏱️ Үргэлжлэх хугацаа", value=f"`{self.format_duration(next_track.length)}`", inline=True)
                            embed.add_field(name="🔄 Loop Mode", value="Queue", inline=True)
                            
                            # Add thumbnail if available
                            if hasattr(next_track, 'artwork') and next_track.artwork:
                                embed.set_thumbnail(url=next_track.artwork)
                            elif hasattr(next_track, 'uri') and 'youtube' in str(next_track.uri):
                                try:
                                    video_id = str(next_track.uri).split('v=')[1].split('&')[0] if 'v=' in str(next_track.uri) else None
                                    if video_id:
                                        embed.set_thumbnail(url=f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg")
                                except:
                                    pass
                            
                            total_tracks = len(queue.tracks)
                            embed.add_field(name="📜 Queue үлдэрч байна", value=f"{total_tracks} дуу", inline=True)
                            embed.set_footer(text="🎶 Музыкийн бот | Queue loop режим")
                            
                            # Create control view
                            view = MusicControlView(self, player.guild.id)
                            await player.channel.send(embed=embed, view=view)
                    except Exception as e:
                        print(f"❌ Queue loop тоглуулахад алдаа: {e}")
        else:
            # Queue хоосон байна, музык дууссан тул мэдэгдэл илгээх
            if hasattr(player, 'channel') and player.channel:
                embed = discord.Embed(
                    title="🎵 Музык дууслаа",
                    description="Queue хоосон байна. Шинэ дуу нэмэх бол `!play` ашиглана уу.",
                    color=0x95A5A6
                )
                embed.add_field(name="💡 Зөвлөгөө", value="• `!play <дуу>` - Шинэ дуу нэмэх\n• `!playlist <нэр>` - Playlist тоглуулах", inline=False)
                embed.set_footer(text="🎶 Музыкийн бот | Playback ended")
                await player.channel.send(embed=embed)

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
                    value="`!play Ariunaa - Mongol heleer`\n`!play https://youtube.com/watch?v=...`",
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
                
                # Progress bar нэмэх
                if track.length > 0:
                    progress = self.create_progress_bar(0, track.length)
                    embed.add_field(
                        name=f"{self.emojis['loading']} Явц",
                        value=f"`{progress}`",
                        inline=False
                    )
                
                embed.add_field(
                    name=f"{self.emojis['info']} Мэдээлэл",
                    value=f"💡 Дараагийн дуу queue-д нэмэгдэх болно\n"
                          f"🎧 `{ctx.prefix}queue` - Queue харах\n"
                          f"⏭️ `{ctx.prefix}skip` - Дараагийн дуу",
                    inline=False
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

    @commands.command(name='skip', aliases=['next'])
    async def skip(self, ctx: commands.Context):
        """⏭️ Одоогийн дууг алгасаж дараагийн дуу руу шилжих"""
        if not ctx.guild:
            return
            
        player: wavelink.Player = ctx.voice_client  # type: ignore
        if not player or not player.playing:
            embed = self.create_music_embed(
                f"{self.emojis['error']} Дуу тоглогдохгүй байна",
                f"Одоо ямар ч дуу тоглогдохгүй байна.\n\n"
                f"💡 **Дуу тоглуулахын тулд:**\n"
                f"`{ctx.prefix}play <дууны нэр>`",
                'error'
            )
            await ctx.send(embed=embed)
            return
        
        queue = self.get_queue(ctx.guild.id)
        current_track = player.current
        
        # Одоогийн дууг түүхэнд хадгалах
        if current_track:
            queue.add_to_history(current_track)
            
        await player.stop()
        
        embed = self.create_music_embed(
            f"{self.emojis['skip']} Skip хийлээ!",
            f"**{current_track.title if current_track else 'Дуу'}** skip хийгдлээ",
            'success'
        )
        
        # Дараагийн дуу мэдээлэл
        if not queue.is_empty():
            next_track = queue.tracks[0]
            embed.add_field(
                name=f"{self.emojis['notes']} Дараагийн дуу",
                value=f"`{next_track.title}`",
                inline=False
            )
        else:
            embed.add_field(
                name=f"{self.emojis['info']} Мэдээлэл",
                value="Queue хоосон байна. Дуу дуусах болно.",
                inline=False
            )
            
        embed.add_field(
            name=f"{self.emojis['queue']} Queue",
            value=f"`{queue.size()} дуу үлдлээ`",
            inline=True
        )
        
        msg = await ctx.send(embed=embed)
        
        # Reactions нэмэх
        if not queue.is_empty():
            await msg.add_reaction(self.emojis['skip'])
        await msg.add_reaction(self.emojis['queue'])

    @commands.command(name='pause')
    async def pause(self, ctx: commands.Context):
        """⏸️ Дууг түр зогсоох"""
        if not ctx.guild:
            return
            
        player: wavelink.Player = ctx.voice_client  # type: ignore
        if not player or not player.playing:
            embed = self.create_music_embed(
                f"{self.emojis['error']} Дуу тоглогдохгүй байна",
                f"Одоо ямар ч дуу тоглогдохгүй байна эсвэл аль хэдийн түр зогссон байна.\n\n"
                f"💡 **Дуу тоглуулахын тулд:** `{ctx.prefix}play <дууны нэр>`",
                'error'
            )
            await ctx.send(embed=embed)
            return
            
        current_track = player.current
        await player.pause(True)
        
        embed = self.create_music_embed(
            f"{self.emojis['pause']} Дуу түр зогслоо",
            f"**{current_track.title if current_track else 'Дуу'}** түр зогслоо",
            'warning'
        )
        
        if current_track:
            embed.add_field(
                name=f"{self.emojis['clock']} Одоогийн байрлал",
                value=f"`{self.format_duration(player.position)}`",
                inline=True
            )
            embed.add_field(
                name=f"{self.emojis['microphone']} Зохиогч",
                value=f"`{current_track.author}`",
                inline=True
            )
        
        embed.add_field(
            name=f"{self.emojis['info']} Үргэлжлүүлэх",
            value=f"`{ctx.prefix}resume` эсвэл `{ctx.prefix}unpause`",
            inline=False
        )
        
        msg = await ctx.send(embed=embed)
        await msg.add_reaction(self.emojis['play'])
        await msg.add_reaction(self.emojis['stop'])

    @commands.command(name='resume', aliases=['unpause'])
    async def resume(self, ctx: commands.Context):
        """▶️ Түр зогссон дууг үргэлжлүүлэх"""
        if not ctx.guild:
            return
            
        player: wavelink.Player = ctx.voice_client  # type: ignore
        if not player or not player.paused:
            embed = self.create_music_embed(
                f"{self.emojis['error']} Дуу түр зогсоогдоогүй байна",
                f"Дуу түр зогсоогдоогүй байна эсвэл тоглохгүй байна.\n\n"
                f"💡 **Дуу тоглуулахын тулд:** `{ctx.prefix}play <дууны нэр>`",
                'error'
            )
            await ctx.send(embed=embed)
            return
            
        current_track = player.current
        await player.pause(False)
        
        embed = self.create_music_embed(
            f"{self.emojis['play']} Дуу үргэлжиллээ!",
            f"**{current_track.title if current_track else 'Дуу'}** дахин тоглож эхэллээ!",
            'success'
        )
        
        if current_track:
            # Progress bar харуулах
            if current_track.length > 0:
                progress = self.create_progress_bar(player.position, current_track.length)
                embed.add_field(
                    name=f"{self.emojis['loading']} Явц",
                    value=f"`{progress}`",
                    inline=False
                )
            
            embed.add_field(
                name=f"{self.emojis['clock']} Хугацаа",
                value=f"`{self.format_duration(player.position)} / {self.format_duration(current_track.length)}`",
                inline=True
            )
        
        queue = self.get_queue(ctx.guild.id)
        embed.add_field(
            name=f"{self.emojis['queue']} Queue",
            value=f"`{queue.size()} дуу хүлээж байна`",
            inline=True
        )
        
        msg = await ctx.send(embed=embed)
        await msg.add_reaction(self.emojis['pause'])
        await msg.add_reaction(self.emojis['skip'])

    @commands.command(name='stop')
    async def stop(self, ctx: commands.Context):
        """Дууг зогсоож queue цэвэрлэх"""
        if not ctx.guild:
            return
            
        player: wavelink.Player = ctx.voice_client  # type: ignore
        queue = self.get_queue(ctx.guild.id)
        
        if player and player.playing:
            await player.stop()
            
        queue.clear()
        embed = discord.Embed(
            title="⏹️ Музык зогслоо",
            description="Дуу зогсч, queue цэвэрлэгдлээ!",
            color=0xff0000
        )
        await ctx.send(embed=embed)

    @commands.command(name='leave', aliases=['disconnect'])
    async def leave(self, ctx: commands.Context):
        """Voice channel-оос гарах"""
        if not ctx.guild:
            return
            
        if ctx.voice_client:
            await ctx.voice_client.disconnect(force=True)
            
            # Player connection-г арилгах
            if ctx.guild.id in self.players_connected:
                self.players_connected.remove(ctx.guild.id)
                
            # Queue цэвэрлэх
            queue = self.get_queue(ctx.guild.id)
            queue.clear()
            
            embed = discord.Embed(
                title="👋 Гарлаа",
                description="Бот voice channel-оос гарч, queue цэвэрлэгдлээ!",
                color=0xff0000
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Алдаа",
                description="Бот voice channel-д байхгүй байна.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @commands.command(name='queue', aliases=['q'])
    async def show_queue(self, ctx: commands.Context):
        """📋 Одоогийн queue-г харуулах"""
        if not ctx.guild:
            return
            
        queue = self.get_queue(ctx.guild.id)
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        embed = self.create_music_embed(
            f"{self.emojis['queue']} Музыкийн дараалал",
            f"🎵 **{ctx.guild.name}** серверийн дууны жагсаалт",
            'queue'
        )
        
        # Одоо тоглож байгаа дуу
        if player and player.current:
            current_track = player.current
            status_emoji = self.emojis['play'] if player.playing else self.emojis['pause']
            
            # Progress bar
            progress_text = ""
            if current_track.length > 0:
                progress = self.create_progress_bar(player.position, current_track.length, 15)
                progress_text = f"\n`{progress}`"
                time_text = f"`{self.format_duration(player.position)} / {self.format_duration(current_track.length)}`"
            else:
                time_text = "`🔴 Live Stream`"
                
            embed.add_field(
                name=f"{status_emoji} **Одоо тоглож байна**",
                value=f"**{current_track.title}**\n"
                      f"👤 `{current_track.author}`\n"
                      f"⏰ {time_text}"
                      f"{progress_text}",
                inline=False
            )
            
            # Thumbnail нэмэх
            if hasattr(current_track, 'artwork') and current_track.artwork:
                embed.set_thumbnail(url=current_track.artwork)
        else:
            embed.add_field(
                name=f"{self.emojis['error']} Одоо тоглож байна",
                value="Одоо ямар ч дуу тоглохгүй байна",
                inline=False
            )
        
        # Queue-ын дуунууд
        if queue.is_empty():
            embed.add_field(
                name=f"{self.emojis['info']} Queue хоосон",
                value=f"Queue-д дуу алга байна.\n\n"
                      f"💡 **Дуу нэмэхийн тулд:**\n"
                      f"`{ctx.prefix}play <дууны нэр>`\n"
                      f"`{ctx.prefix}playlist <playlist нэр>`",
                inline=False
            )
        else:
            queue_text = ""
            total_duration = 0
            
            for i, track in enumerate(queue.tracks[:10], 1):  # Эхний 10 дууг харуулах
                duration_text = self.format_duration(track.length) if track.length > 0 else "Live"
                queue_text += f"`{i}.` **{track.title[:40]}{'...' if len(track.title) > 40 else ''}**\n"
                queue_text += f"     👤 {track.author[:30]}{'...' if len(track.author) > 30 else ''} • ⏰ {duration_text}\n\n"
                
                if track.length > 0:
                    total_duration += track.length
            
            if queue.size() > 10:
                queue_text += f"**... болон өөр {queue.size() - 10} дуу**\n"
                remaining_duration = sum(t.length for t in queue.tracks[10:] if t.length > 0)
                total_duration += remaining_duration
            
            embed.add_field(
                name=f"{self.emojis['queue']} **Queue ({queue.size()} дуу)**",
                value=queue_text,
                inline=False
            )
            
            # Нийт хугацаа
            if total_duration > 0:
                embed.add_field(
                    name=f"⏱️ Нийт хугацаа",
                    value=f"`~{self.format_duration(total_duration)}`",
                    inline=True
                )
            
            # Queue удирдлагын командууд
            embed.add_field(
                name=f"{self.emojis['info']} Удирдлага",
                value="Button-ууд ашиглан queue удирдана уу эсвэл команд ашиглана уу:\n"
                      f"`{ctx.prefix}skip` - Дараагийн дуу\n"
                      f"`{ctx.prefix}shuffle` - Холих\n"
                      f"`{ctx.prefix}clear` - Цэвэрлэх",
                inline=True
            )
        
        # Volume мэдээлэл
        current_volume = self.guild_volumes.get(ctx.guild.id, self.default_volume)
        volume_emoji = self.get_volume_emoji(current_volume)
        embed.add_field(
            name=f"{volume_emoji} Дууны чанга",
            value=f"`{current_volume}%`",
            inline=True
        )
        
        msg = await ctx.send(embed=embed)
        
        # Music control buttons нэмэх (хэрэв дуу тоглож байвал)
        if player and player.current:
            view = MusicControlView(self, ctx.guild.id)
            await msg.edit(embed=embed, view=view)
        
        # Queue удирдлагын button-ууд нэмэх (хэрэв queue-д дуу байвал)
        elif not queue.is_empty():
            # QueueControlView-г энд тодорхойлох
            class QueueControlView(discord.ui.View):
                def __init__(self, music_cog: 'Music', guild_id: int):
                    super().__init__(timeout=180)
                    self.music_cog = music_cog
                    self.guild_id = guild_id
                
                @discord.ui.button(emoji='🔀', style=discord.ButtonStyle.primary, label='Shuffle')
                async def shuffle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    queue = self.music_cog.get_queue(self.guild_id)
                    if queue.size() >= 2:
                        queue.shuffle_tracks()
                        embed = discord.Embed(title="🔀 Queue холигдлоо!", color=0x00ff00)
                        await interaction.response.send_message(embed=embed, ephemeral=False)
                    else:
                        await interaction.response.send_message("❌ Хангалтгүй дуу!", ephemeral=True)
                
                @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.danger, label='Clear')
                async def clear_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    queue = self.music_cog.get_queue(self.guild_id)
                    queue_size = queue.size()
                    queue.clear()
                    embed = discord.Embed(title="🗑️ Queue цэвэрлэгдлээ!", description=f"{queue_size} дуу хасагдлаа", color=0xff0000)
                    await interaction.response.send_message(embed=embed, ephemeral=False)
            
            queue_view = QueueControlView(self, ctx.guild.id)
            await msg.edit(embed=embed, view=queue_view)

    @commands.command(name='volume', aliases=['vol'])
    async def volume(self, ctx: commands.Context, volume: Optional[int] = None):
        """Дууны чангыг тохируулах"""
        if not ctx.guild:
            return
            
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        if not player:
            embed = discord.Embed(
                title="❌ Алдаа",
                description="Бот voice channel-д байхгүй байна.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        if volume is None:
            # Одоогийн чангыг харуулах
            current_volume = self.guild_volumes.get(ctx.guild.id, self.default_volume)
            embed = discord.Embed(
                title="🔊 Дууны чанга",
                description=f"Одоогийн чанга: **{current_volume}%**\n"
                           f"Default чанга: **{self.default_volume}%**",
                color=0x7289DA
            )
            embed.add_field(
                name="💡 Заавар",
                value="Button-ууд ашиглан чанга тохируулна уу эсвэл\n"
                      f"`{ctx.prefix}volume <0-100>` - Тоо оруулах",
                inline=False
            )
            
            # Volume control buttons
            view = VolumeView(self, ctx.guild.id, current_volume)
            await ctx.send(embed=embed, view=view)
            return
        
        if volume < 0 or volume > 100:
            embed = discord.Embed(
                title="❌ Алдаа",
                description="Дууны чанга 0-100 хооронд байх ёстой!",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        # Volume тохируулах болон хадгалах
        await player.set_volume(volume)
        self.guild_volumes[ctx.guild.id] = volume
        
        # Volume түвшинээс хамаарч өөр өөр emoji ашиглах
        if volume == 0:
            volume_emoji = "🔇"
        elif volume <= 25:
            volume_emoji = "🔈"
        elif volume <= 75:
            volume_emoji = "🔉"
        else:
            volume_emoji = "🔊"
        
        embed = discord.Embed(
            title=f"{volume_emoji} Дууны чанга өөрчлөгдлөө",
            description=f"Шинэ чанга: **{volume}%**",
            color=0x00ff00
        )
        
        # Анхаарлын мэдэгдэл
        if volume > 85:
            embed.add_field(
                name="⚠️ Анхааруулга",
                value="Маш чанга тохиргоо! Чихэндээ анхаарна уу.",
                inline=False
            )
        elif volume < 10:
            embed.add_field(
                name="🔇 Анхааруулга", 
                value="Маш намуу тохиргоо! Дуу сайн сонсогдохгүй байж болно.",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @commands.command(name='musicinfo', aliases=['minfo'])
    async def music_info(self, ctx: commands.Context):
        """Музыкийн ботын мэдээлэл"""
        if not ctx.guild:
            return
            
        queue = self.get_queue(ctx.guild.id)
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        embed = discord.Embed(
            title="🎵 MongolBot Музык Систем",
            description="Монголын хамгийн шилдэг музык бот!",
            color=0x7289DA
        )
        
        # Холболтын статус
        connection_status = "✅ Холбогдсон" if player else "❌ Холбогдоогүй"
        embed.add_field(name="📡 Холболт", value=connection_status, inline=True)
        
        # Player статус
        if player:
            if player.playing:
                player_status = "🎵 Тоглож байна"
            elif player.paused:
                player_status = "⏸️ Түр зогссон"
            else:
                player_status = "⏹️ Зогссон"
        else:
            player_status = "❌ Идэвхгүй"
        
        embed.add_field(name="🎮 Статус", value=player_status, inline=True)
        embed.add_field(name="📋 Queue", value=f"{queue.size()} дуу", inline=True)
        
        # Volume мэдээлэл
        current_volume = self.guild_volumes.get(ctx.guild.id, self.default_volume)
        volume_emoji = "🔇" if current_volume == 0 else "🔈" if current_volume <= 25 else "🔉" if current_volume <= 75 else "🔊"
        embed.add_field(name=f"{volume_emoji} Дууны чанга", value=f"{current_volume}%", inline=True)
        embed.add_field(name="🎛️ Default Volume", value=f"{self.default_volume}%", inline=True)
        embed.add_field(name="🔗 Холбогдсон сервер", value=f"{len(self.players_connected)}", inline=True)
        
        # Команд жагсаалт
        commands_text = """
        `play` - Дуу тоглуулах (эхний дуу шууд, дараагийнх queue-д)
        `playlist` - Playlist эсвэл олон дуу queue-д нэмэх
        `pause/resume` - Түр зогсоох/үргэлжлүүлэх
        `skip` - Дараагийн дуу руу
        `stop` - Зогсоох
        `queue` - Queue харах
        `volume` - Дууны чанга (default: 50%)
        `leave` - Voice channel-оос гарах
        """
        
        embed.add_field(name="📝 Командууд", value=commands_text, inline=False)
        embed.set_footer(text="🎵 MongolBot - Mongolian Music Experience | Default Volume: 50%")
        
        await ctx.send(embed=embed)

    @commands.command(name='playlist', aliases=['pl'])
    @rate_limit_command()
    async def add_playlist(self, ctx: commands.Context, *, search: str):
        """Playlist эсвэл олон дуу queue-д нэмэх"""
        if not ctx.guild:
            return
            
        player = await self.ensure_voice_connection(ctx)
        if not player:
            return
            
        # Playlist эсвэл дуунуудыг хайх
        try:
            # YouTube playlist, Spotify playlist, эсвэл олон дуу хайх
            tracks = await wavelink.Pool.fetch_tracks(search)
            if not tracks:
                # YouTube search хийх
                tracks = await wavelink.Pool.fetch_tracks(f'ytsearch:{search}')
                if not tracks:
                    embed = discord.Embed(
                        title="❌ Playlist эсвэл дуу олдсонгүй",
                        description=f"'{search}' гэсэн хайлтаар дуу олдсонгүй.",
                        color=0xff0000
                    )
                    await ctx.send(embed=embed)
                    return
        except Exception as e:
            await ctx.send(f'❌ Playlist хайхад алдаа гарлаа: {e}')
            return
        
        queue = self.get_queue(ctx.guild.id)
        added_count = 0
        
        # Loading message
        loading_embed = discord.Embed(
            title="⏳ Playlist ачаалж байна...",
            description=f"Нийт {len(tracks)} дуу олдлоо",
            color=0xffaa00
        )
        loading_msg = await ctx.send(embed=loading_embed)
        
        # Эхний дууг шууд тоглуулах (хэрэв дуу тоглохгүй байвал)
        if not player.playing and not player.paused and queue.is_empty() and tracks:
            first_track = tracks[0]
            try:
                await player.play(first_track)
                queue.current_track = first_track
                added_count += 1
                tracks = tracks[1:]  # Эхний дууг list-ээс хас
            except Exception as e:
                print(f"❌ Эхний дуу тоглуулахад алдаа: {e}")
        
        # Бусад дуунуудыг queue-д нэмэх
        for track in tracks:
            queue.add(track)
            added_count += 1
            
            # 50 дуу тутамд progress харуулах
            if added_count % 50 == 0:
                try:
                    progress_embed = discord.Embed(
                        title="⏳ Playlist ачаалж байна...",
                        description=f"{added_count}/{len(tracks) + (1 if queue.current_track else 0)} дуу нэмэгдлээ",
                        color=0xffaa00
                    )
                    await loading_msg.edit(embed=progress_embed)
                except:
                    pass
        
        # Дуусгах мэдэгдэл
        try:
            await loading_msg.delete()
        except:
            pass
            
        embed = discord.Embed(
            title="✅ Playlist амжилттай нэмэгдлээ!",
            description=f"**{added_count}** дуу queue-д нэмэгдлээ",
            color=0x00ff00
        )
        
        if queue.current_track:
            embed.add_field(name="🎵 Одоо тоглож байна", value=f"**{queue.current_track.title}**", inline=False)
        
        embed.add_field(name="📋 Queue", value=f"{queue.size()} дуу", inline=True)
        embed.add_field(name="⏱️ Нийт хугацаа", value=f"~{sum(track.length for track in queue.tracks) // 60000} минут", inline=True)
        
        await ctx.send(embed=embed)

    @commands.command(name='loop', aliases=['repeat'])
    async def toggle_loop(self, ctx: commands.Context, mode: Optional[str] = None):
        """🔄 Loop горим солих (off/on/queue)"""
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
        
        # Loop mode тодорхойлох
        if mode is None:
            # Одоогийн статусыг харуулах
            current_mode = "❌ Идэвхгүй"
            if hasattr(queue, 'loop_mode'):
                if queue.loop_mode == 'on':
                    current_mode = "🔂 Нэг дуу давтах"
                elif queue.loop_mode == 'queue':
                    current_mode = "🔁 Queue давтах"
            
            embed = self.create_music_embed(
                f"{self.emojis['loop']} Loop горим",
                f"**Одоогийн горим:** {current_mode}",
                'info'
            )
            embed.add_field(
                name="🎛️ Боломжит горимууд",
                value="Button-ууд ашиглан loop горим сонгоно уу эсвэл\n"
                      f"`{ctx.prefix}loop off/on/queue` - Команд ашиглах",
                inline=False
            )
            
            # Loop control buttons
            view = LoopView(self, ctx.guild.id)
            await ctx.send(embed=embed, view=view)
            return
        
        mode = mode.lower()
        if mode not in ['off', 'on', 'queue']:
            embed = self.create_music_embed(
                f"{self.emojis['error']} Буруу горим",
                f"**Боломжит горимууд:** `off`, `on`, `queue`",
                'error'
            )
            await ctx.send(embed=embed)
            return
        
        # Loop mode тохируулах
        queue.loop_mode = mode
        
        # Мэдэгдэл үүсгэх
        if mode == 'off':
            title = f"{self.emojis['stop']} Loop унтраагдлаа"
            description = "Дуу давтахгүй болно"
            color = 'error'
        elif mode == 'on':
            title = f"🔂 Дуу давтах горим идэвхжлээ"
            description = "Одоогийн дуу дуусах бүрд дахин тоглох болно"
            color = 'success'
        else:  # queue
            title = f"🔁 Queue давтах горим идэвхжлээ"
            description = "Queue дуусах бүрд эхнээс нь эхэлнэ"
            color = 'success'
        
        embed = self.create_music_embed(title, description, color)
        
        if player.current:
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

    @commands.command(name='shuffle')
    async def shuffle_queue(self, ctx: commands.Context):
        """🔀 Queue-г холих"""
        if not ctx.guild:
            return
            
        queue = self.get_queue(ctx.guild.id)
        
        if queue.is_empty():
            embed = self.create_music_embed(
                f"{self.emojis['error']} Queue хоосон байна",
                f"Queue-д дуу алга байна.",
                'error'
            )
            await ctx.send(embed=embed)
            return
        
        if queue.size() < 2:
            embed = self.create_music_embed(
                f"{self.emojis['warning']} Хангалтгүй дуу",
                f"Shuffle хийхийн тулд дор хаяж 2 дуу байх ёстой.\n"
                f"Одоо queue-д {queue.size()} дуу байна.",
                'warning'
            )
            await ctx.send(embed=embed)
            return
        
        queue.shuffle_tracks()
        
        embed = self.create_music_embed(
            f"{self.emojis['shuffle']} Queue холигдлоо!",
            f"**{queue.size()}** дуу санамсаргүй дарааллаар солигдлоо",
            'success'
        )
        
        # Дараагийн 3 дууг харуулах
        next_tracks = []
        for i, track in enumerate(queue.tracks[:3], 1):
            title = track.title[:40] + "..." if len(track.title) > 40 else track.title
            next_tracks.append(f"`{i}.` **{title}**")
        
        embed.add_field(
            name=f"{self.emojis['notes']} Дараагийн дуунууд",
            value="\n".join(next_tracks) if next_tracks else "Дуу алга",
            inline=False
        )
        
        # Queue control buttons нэмэх
        msg = await ctx.send(embed=embed)

    @commands.command(name='clear')
    async def clear_queue(self, ctx: commands.Context):
        """🗑️ Queue цэвэрлэх"""
        if not ctx.guild:
            return
            
        queue = self.get_queue(ctx.guild.id)
        
        if queue.is_empty():
            embed = self.create_music_embed(
                f"{self.emojis['info']} Queue аль хэдийн хоосон байна",
                f"Цэвэрлэх зүйл алга байна.",
                'info'
            )
            await ctx.send(embed=embed)
            return
        
        queue_size = queue.size()
        queue.clear()
        
        embed = self.create_music_embed(
            f"{self.emojis['success']} Queue цэвэрлэгдлээ!",
            f"**{queue_size}** дуу queue-оос хасагдлаа",
            'success'
        )
        
        player: wavelink.Player = ctx.voice_client  # type: ignore
        if player and player.current:
            embed.add_field(
                name=f"{self.emojis['notes']} Одоо тоглож байна",
                value=f"**{player.current.title}**\n"
                      f"Энэ дуу дуусмагц музык зогсох болно.",
                inline=False
            )
        
        embed.add_field(
            name=f"{self.emojis['info']} Мэдээлэл",
            value=f"`{ctx.prefix}play <дуу>` - Шинэ дуу нэмэх\n"
                  f"`{ctx.prefix}stop` - Одоогийн дууг зогсоох",
            inline=False
        )
        
        await ctx.send(embed=embed)

    # ...existing code...
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))