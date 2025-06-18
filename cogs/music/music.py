import discord
from discord.ext import commands
import wavelink
import asyncio
import re
from typing import Optional, Dict, List, Union, cast
import logging

logger = logging.getLogger(__name__)

class Music(commands.Cog):
    """Lavalink ашиглан хөгжмийн команд"""
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.music_queue: Dict[int, List[wavelink.Playable]] = {}
        self.current_track: Dict[int, wavelink.Playable] = {}
          # Lavalink хостын тохиргоо (зөвхөн 1 хост)
        # Таны орон нутгийн Lavalink сервер (application.yml-ээс):
          # ТАНЫ LAVALINK СЕРВЕР (185.128.227.86):
        self.lavalink_host = {
            "uri": "ws://185.128.227.86:6029",      # Websocket холболт
            "password": "Dragon95279853",           # Таны application.yml-д password
            "identifier": "remote_server"           # Remote сервер
        }
        
        self.connected_node: Optional[wavelink.Node] = None

    async def cog_load(self) -> None:
        """Lavalink хостод холбогдох"""
        logger.info("🔍 Lavalink хостод холбогдож байна...")
        
        try:
            # Найдвартай хостод холбогдох
            node = wavelink.Node(
                uri=self.lavalink_host['uri'],
                password=self.lavalink_host['password'],
                identifier=self.lavalink_host['identifier']
            )
            
            # FIXED: Use nodes parameter (plural) instead of node (singular)
            await wavelink.Pool.connect(nodes=[node], client=self.bot)
            self.connected_node = node
            logger.info(f"✅ {self.lavalink_host['identifier']} хостод амжилттай холбогдлоо!")
                    
        except Exception as e:
            logger.error(f"❌ Lavalink холболтод алдаа: {e}")
            logger.info("💡 Дараах зүйлсийг шалгана уу:")
            logger.info("   1. Интернет холболт")
            logger.info("   2. Firewall тохиргоо")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload) -> None:
        """Node бэлэн болоход ажиллана"""
        node = payload.node
        logger.info(f"🎵 Node {node.identifier} бэлэн боллоо!")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload) -> None:
        """Дуу дууссан үед дараагийн дууг тоглуулна"""
        player = cast(wavelink.Player, payload.player)
        
        if not player.guild:
            return
            
        guild_id = player.guild.id
        
        if guild_id in self.music_queue and self.music_queue[guild_id]:
            next_track = self.music_queue[guild_id].pop(0)
            self.current_track[guild_id] = next_track
            await player.play(next_track)
            
            # Дараагийн дууны мэдээллийг илгээх embed
            embed = discord.Embed(
                title="🎵 Одоо тоглож байна",
                description=f"**{next_track.title}**",
                color=0x00ff00
            )
            embed.add_field(name="Зохиолч", value=next_track.author, inline=True)
            embed.add_field(name="Үргэлжлэх хугацаа", value=self.format_time(next_track.length), inline=True)
            
            # Try to send message to system channel if available
            if player.guild.system_channel:
                try:
                    await player.guild.system_channel.send(embed=embed)
                except Exception:
                    pass  # Ignore if can't send
        else:
            # Жагсаалт хоосон бол дуу тоглуулахыг зогсоох
            self.current_track.pop(guild_id, None)

    def format_time(self, milliseconds: int) -> str:
        """Миллисекундийг цаг:минут:секунд болгон хөрвүүлэх"""
        seconds = milliseconds // 1000
        minutes = seconds // 60
        hours = minutes // 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes%60:02d}:{seconds%60:02d}"
        else:
            return f"{minutes:02d}:{seconds%60:02d}"

    def get_queue_embed(self, guild_id: int) -> discord.Embed:
        """Жагсаалтын embed үүсгэх"""
        if guild_id not in self.music_queue or not self.music_queue[guild_id]:
            embed = discord.Embed(
                title="📜 Дууны жагсаалт",
                description="Жагсаалт хоосон байна",
                color=0xff0000
            )
            return embed
            
        embed = discord.Embed(
            title="📜 Дууны жагсаалт",
            color=0x00ff00
        )
        
        for i, track in enumerate(self.music_queue[guild_id][:10], 1):  # Эхний 10 дуу
            embed.add_field(
                name=f"{i}. {track.title}",
                value=f"Зохиолч: {track.author} | Үргэлжлэх хугацаа: {self.format_time(track.length)}",
                inline=False
            )
            
        if len(self.music_queue[guild_id]) > 10:
            embed.add_field(
                name="...",
                value=f"Ба өөр {len(self.music_queue[guild_id]) - 10} дуу",
                inline=False
            )
            
        return embed

    async def ensure_voice_connection(self, ctx: commands.Context) -> Optional[wavelink.Player]:
        """Voice channel-д холбогдож, player-ийг буцаах"""
        # Type guard to ensure ctx.author is a Member
        if not isinstance(ctx.author, discord.Member) or not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ Та эхлээд voice channel-д орно уу!")
            return None
            
        voice_channel = ctx.author.voice.channel
        
        # Get or create player
        player: Optional[wavelink.Player] = cast(Optional[wavelink.Player], ctx.voice_client)
        if not player:
            try:
                player = await voice_channel.connect(cls=wavelink.Player)  # type: ignore
            except Exception as e:
                await ctx.send(f"❌ Voice channel-д холбогдохад алдаа гарлаа: {e}")
                return None
                
        return player

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, search: str) -> None:
        """Дуу тоглуулах команд"""
        player = await self.ensure_voice_connection(ctx)
        if not player:
            return
            
        # YouTube-ээс дуу хайх
        try:
            tracks: wavelink.Search = await wavelink.Playable.search(search)
            if not tracks:
                tracks = await wavelink.Playable.search(f"ytsearch:{search}")
                
            if not tracks:
                await ctx.send("❌ Дуу олдсонгүй!")
                return
                
        except Exception as e:
            await ctx.send(f"❌ Дуу хайхад алдаа гарлаа: {e}")
            return

        track = tracks[0]
        
        if not ctx.guild:
            await ctx.send("❌ Энэ команд зөвхөн серверт ашиглана!")
            return
            
        guild_id = ctx.guild.id
        
        # Check if player is currently playing
        if not player.playing:
            # Play immediately if nothing is playing
            self.current_track[guild_id] = track
            await player.play(track)
            
            embed = discord.Embed(
                title="🎵 Одоо тоглож байна",
                description=f"**{track.title}**",
                color=0x00ff00
            )
            embed.add_field(name="Зохиолч", value=track.author, inline=True)
            embed.add_field(name="Үргэлжлэх хугацаа", value=self.format_time(track.length), inline=True)
            embed.add_field(name="Хүссэн", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
        else:
            # Add to queue if already playing
            if guild_id not in self.music_queue:
                self.music_queue[guild_id] = []
            self.music_queue[guild_id].append(track)
            
            embed = discord.Embed(
                title="📜 Жагсаалтад нэмэгдлээ",
                description=f"**{track.title}**",
                color=0xffff00
            )
            embed.add_field(name="Зохиолч", value=track.author, inline=True)
            embed.add_field(name="Үргэлжлэх хугацаа", value=self.format_time(track.length), inline=True)
            embed.add_field(name="Жагсаалтын байрлал", value=f"#{len(self.music_queue[guild_id])}", inline=True)
            
            await ctx.send(embed=embed)

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context) -> None:
        """Дуу тоглуулахыг зогсоох"""
        player: Optional[wavelink.Player] = cast(Optional[wavelink.Player], ctx.voice_client)
        if not player:
            await ctx.send("❌ Дуу тоглуулж байхгүй байна!")
            return
            
        if not player.playing:
            await ctx.send("❌ Дуу тоглуулж байхгүй байна!")
            return
            
        await player.stop()
        await ctx.send("⏹️ Дуу тоглуулахыг зогсоолоо!")

    @commands.command(name="skip", aliases=["next"])
    async def skip(self, ctx: commands.Context) -> None:
        """Дараагийн дуу руу шилжих"""
        player: Optional[wavelink.Player] = cast(Optional[wavelink.Player], ctx.voice_client)
        if not player:
            await ctx.send("❌ Дуу тоглуулж байхгүй байна!")
            return
            
        if not ctx.guild:
            await ctx.send("❌ Энэ команд зөвхөн серверт ашиглана!")
            return
            
        guild_id = ctx.guild.id
        
        # Stop current track to trigger next one
        await player.stop()
        self.current_track.pop(guild_id, None)
        
        await ctx.send("⏭️ Дууг алгасаж дараагийн дуу руу шилжлээ!")

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context) -> None:
        """Дууг түр зогсоох"""
        player: Optional[wavelink.Player] = cast(Optional[wavelink.Player], ctx.voice_client)
        if not player:
            await ctx.send("❌ Дуу тоглуулж байхгүй байна!")
            return
            
        if not player.playing:
            await ctx.send("❌ Дуу тоглуулж байхгүй байна!")
            return
            
        await player.pause(True)
        await ctx.send("⏸️ Дууг түр зогсоолоо!")

    @commands.command(name="resume")
    async def resume(self, ctx: commands.Context) -> None:
        """Дууг үргэлжлүүлэх"""
        player: Optional[wavelink.Player] = cast(Optional[wavelink.Player], ctx.voice_client)
        if not player:
            await ctx.send("❌ Дуу тоглуулж байхгүй байна!")
            return
            
        if player.playing:
            await ctx.send("❌ Дуу аль хэдийн тоглож байна!")
            return
            
        await player.pause(False)
        await ctx.send("▶️ Дууг үргэлжлүүллээ!")

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx: commands.Context) -> None:
        """Дууны жагсаалтыг харах"""
        if not ctx.guild:
            await ctx.send("❌ Энэ команд зөвхөн серверт ашиглана!")
            return
            
        guild_id = ctx.guild.id
        embed = self.get_queue_embed(guild_id)
        
        # Add currently playing track
        if guild_id in self.current_track:
            current = self.current_track[guild_id]
            embed.insert_field_at(
                0,
                name="🎵 Одоо тоглож байна",
                value=f"**{current.title}** - {current.author}",
                inline=False
            )
            
        await ctx.send(embed=embed)

    @commands.command(name="clear")
    async def clear_queue(self, ctx: commands.Context) -> None:
        """Дууны жагсаалтыг цэвэрлэх"""
        if not ctx.guild:
            await ctx.send("❌ Энэ команд зөвхөн серверт ашиглана!")
            return
            
        guild_id = ctx.guild.id
        
        if guild_id not in self.music_queue or not self.music_queue[guild_id]:
            await ctx.send("❌ Жагсаалт аль хэдийн хоосон байна!")
            return
            
        cleared_count = len(self.music_queue[guild_id])
        self.music_queue[guild_id].clear()
        
        await ctx.send(f"🗑️ Жагсаалтаас {cleared_count} дуу хаслаа!")

    @commands.command(name="disconnect", aliases=["dc", "leave"])
    async def disconnect(self, ctx: commands.Context) -> None:
        """Voice channel-ээс гарах"""
        player: Optional[wavelink.Player] = cast(Optional[wavelink.Player], ctx.voice_client)
        if not player:
            await ctx.send("❌ Voice channel-д холбогдоогүй байна!")
            return
            
        await player.disconnect()
        
        # Clean up guild queues and current tracks
        if ctx.guild:
            guild_id = ctx.guild.id
            self.music_queue.pop(guild_id, None)
            self.current_track.pop(guild_id, None)
            
        await ctx.send("👋 Voice channel-ээс гарлаа!")

    @commands.command(name="nowplaying", aliases=["np"])
    async def now_playing(self, ctx: commands.Context) -> None:
        """Одоо тоглож байгаа дууны мэдээлэл"""
        if not ctx.guild:
            await ctx.send("❌ Энэ команд зөвхөн серверт ашиглана!")
            return
            
        guild_id = ctx.guild.id
        
        if guild_id not in self.current_track:
            await ctx.send("❌ Одоо дуу тоглуулж байхгүй байна!")
            return
            
        track = self.current_track[guild_id]
        player: Optional[wavelink.Player] = cast(Optional[wavelink.Player], ctx.voice_client)
        
        embed = discord.Embed(
            title="🎵 Одоо тоглож байна",
            description=f"**{track.title}**",
            color=0x00ff00
        )
        embed.add_field(name="Зохиолч", value=track.author, inline=True)
        embed.add_field(name="Үргэлжлэх хугацаа", value=self.format_time(track.length), inline=True)
        
        if player and hasattr(player, 'position') and player.position:
            embed.add_field(name="Одоогийн байрлал", value=self.format_time(player.position), inline=True)
            
        await ctx.send(embed=embed)

    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx: commands.Context, volume: Optional[int] = None) -> None:
        """Дууны хэмжээг тохируулах (0-100)"""
        player: Optional[wavelink.Player] = cast(Optional[wavelink.Player], ctx.voice_client)
        if not player:
            await ctx.send("❌ Дуу тоглуулж байхгүй байна!")
            return
            
        if volume is None:
            current_volume = getattr(player, 'volume', 100)
            await ctx.send(f"🔊 Одоогийн дууны хэмжээ: {current_volume}%")
            return
            
        if volume < 0 or volume > 100:
            await ctx.send("❌ Дууны хэмжээ 0-100 хооронд байх ёстой!")
            return
            
        await player.set_volume(volume)
        await ctx.send(f"🔊 Дууны хэмжээг {volume}% болгов!")

async def setup(bot: commands.Bot) -> None:
    """Cog-ийг bot-д нэмэх"""
    await bot.add_cog(Music(bot))
