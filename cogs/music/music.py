import discord
from discord.ext import commands
import wavelink
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from discord.ext.commands import Bot, Context

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.loop.create_task(self.start_lavalink())

    async def start_lavalink(self):
        await self.bot.wait_until_ready()
        node = wavelink.Node(uri='http://185.128.227.86:6029', password='Dragon95279853')
        await wavelink.Pool.connect(client=self.bot, nodes=[node])

    @commands.command(name='join')
    async def join(self, ctx: commands.Context):
        voice_state = getattr(ctx.author, 'voice', None)
        if voice_state and voice_state.channel:
            channel = voice_state.channel
            await channel.connect(cls=wavelink.Player)
            await ctx.send(f'Бот {channel.name} өрөөнд нэгдлээ!')
        else:
            await ctx.send('Та voice channel-д ороогүй байна.')

    @commands.command(name='play')
    async def play(self, ctx: commands.Context, *, search: str):
        voice_state = getattr(ctx.author, 'voice', None)
        if not ctx.voice_client:
            if voice_state and voice_state.channel:
                await voice_state.channel.connect(cls=wavelink.Player)
            else:
                await ctx.send('Та voice channel-д ороогүй байна.')
                return
        player: wavelink.Player = ctx.voice_client  # type: ignore
        tracks = await wavelink.Pool.fetch_tracks(f'ytsearch:{search}')
        if not tracks:
            await ctx.send('Дуу олдсонгүй.')
            return
        track = tracks[0]
        await player.play(track)
        await ctx.send(f'Одоо тоглож байна: {track.title}')

    @commands.command(name='pause')
    async def pause(self, ctx: commands.Context):
        player: wavelink.Player = ctx.voice_client  # type: ignore
        if player and player.playing:
            await player.pause(True)
            await ctx.send('⏸ Дуу түр зогслоо!')
        else:
            await ctx.send('Одоо ямар ч дуу тоглогдохгүй байна.')

    @commands.command(name='resume')
    async def resume(self, ctx: commands.Context):
        player: wavelink.Player = ctx.voice_client  # type: ignore
        if player and player.paused:
            await player.pause(False)
            await ctx.send('▶️ Дуу үргэлжиллээ!')
        else:
            await ctx.send('Дуу түр зогсоогдоогүй байна.')

    @commands.command(name='stop')
    async def stop(self, ctx: commands.Context):
        player: wavelink.Player = ctx.voice_client  # type: ignore
        if player and player.playing:
            await player.stop()
            await ctx.send('⏹ Дуу зогслоо!')
        else:
            await ctx.send('Одоо ямар ч дуу тоглогдохгүй байна.')

    @commands.command(name='leave')
    async def leave(self, ctx: commands.Context):
        if ctx.voice_client:
            await ctx.voice_client.disconnect(force=True)
            await ctx.send('Бот voice channel-оос гарлаа!')
        else:
            await ctx.send('Бот voice channel-д байхгүй байна.')

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
