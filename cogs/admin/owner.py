import discord
from discord.ext import commands

class Owner(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.synced = False  # Синхрончлолын төлөв

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.synced:
            try:
                synced = await self.bot.tree.sync()
                self.synced = True
                print(f"✅ `{len(synced)}` команд глобал хэмжээнд амжилттай синхрончлогдлоо.")
            except Exception as e:
                print(f"❌ Slash командуудыг синхрончлох үед алдаа гарлаа: {e}")

    @commands.command(name="sync", help="Глобал slash командуудыг синхрончлох.")
    @commands.is_owner()
    async def sync(self, ctx: commands.Context):
        try:
            synced = await self.bot.tree.sync()
            await ctx.send(f"✅ `{len(synced)}` команд глобал хэмжээнд амжилттай синхрончлогдлоо.")
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: {e}")

    @commands.command(name="sync_guild", help="Зөвхөн энэ серверт slash командуудыг синхрончлох.")
    @commands.is_owner()
    async def sync_guild(self, ctx: commands.Context):
        try:
            synced = await self.bot.tree.sync(guild=ctx.guild)
            await ctx.send(f"✅ `{len(synced)}` команд зөвхөн энэ серверт амжилттай синхрончлогдлоо.")
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: {e}")

    @commands.command(name="sync_server", help="Тодорхой серверт slash командуудыг синхрончлох.")
    @commands.is_owner()
    async def sync_server(self, ctx: commands.Context, guild_id: int):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            await ctx.send("❌ Уг сервер олдсонгүй.")
            return
        try:
            synced = await self.bot.tree.sync(guild=guild)
            await ctx.send(f"✅ `{len(synced)}` команд сервер `{guild_id}`-д амжилттай синхрончлогдлоо.")
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: {e}")

    @commands.command(name='load', help='Шинэ нэмэлт (cog) ачаалах.')
    @commands.is_owner()
    async def load(self, ctx: commands.Context, cog: str):
        try:
            await self.bot.load_extension(f"{cog}")
            await ctx.send(f"✅ `{cog}` амжилттай ачаалагдлаа!")
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: `{e}`")

    @commands.command(name='unload', help='Нэмэлтийг (cog) ачаалалгүй болгох.')
    @commands.is_owner()
    async def unload(self, ctx: commands.Context, cog: str):
        try:
            await self.bot.unload_extension(f"{cog}")
            await ctx.send(f"✅ `{cog}` амжилттай ачаалалгүй боллоо!")
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: `{e}`")

    @commands.command(name='reload', help='Нэмэлтийг (cog) дахин ачаалах.')
    @commands.is_owner()
    async def reload(self, ctx: commands.Context, cog: str):
        try:
            await self.bot.unload_extension(f"{cog}")
            await self.bot.load_extension(f"{cog}")
            await ctx.send(f"✅ `{cog}` амжилттай дахин ачаалагдлаа!")
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: `{e}`")

async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))