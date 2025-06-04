import discord
from discord.ext import commands
import hashlib

class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.synced = False
        self.command_hashes = {}  # Командын hash хадгалах

    def get_command_hash(self, commands):
        """Командуудын hash утга бодох"""
        command_data = []
        for cmd in commands:
            data = {
                'name': cmd.name,
                'description': str(getattr(cmd, 'description', '')),
                'options': [(o.name, str(o.description)) for o in getattr(cmd, 'options', [])]
            }
            command_data.append(str(data))
        return hashlib.md5(''.join(sorted(command_data)).encode()).hexdigest()

    @commands.Cog.listener()
    async def on_ready(self):
        await self.sync_all_commands()

    async def sync_all_commands(self):
        try:
            print("\n🔄 Slash командуудыг бүртгэж байна...")

            # Шинэ командуудыг бүртгэх
            print("\n📥 Командуудыг бүртгэж байна:")
            registered = 0
            for cog in self.bot.cogs.values():
                for cmd in getattr(cog, '__cog_app_commands__', []):
                    try:
                        self.bot.tree.add_command(cmd)
                        registered += 1
                        print(f"  ➕ /{cmd.name} нэмэгдлээ")
                    except Exception as e:
                        print(f"  ❌ /{cmd.name} - Алдаа: {e}")

            # Force sync хийх (глобал)
            print("\n🌐 Глобал sync хийж байна...")
            synced = await self.bot.tree.sync()
            print(f"  ✅ {len(synced)} команд sync хийгдлээ")

            # Guild бүрт sync хийх
            print("\n🏰 Серверүүдэд sync хийж байна...")
            for guild in self.bot.guilds:
                try:
                    guild_synced = await self.bot.tree.sync(guild=guild)
                    print(f"  ✅ {guild.name}: {len(guild_synced)} команд")
                except Exception as e:
                    print(f"  ❌ {guild.name} - Алдаа: {e}")

            self.synced = True
            print(f"\n✨ Амжилттай! Нийт {registered} команд бүртгэгдлээ")

        except Exception as e:
            print(f"❌ Sync хийх үед алдаа гарлаа: {str(e)}")

    @commands.command(name="sync", help="Бүх slash командуудыг дахин синхрончлох")
    @commands.is_owner()
    async def sync(self, ctx):
        await ctx.send("⏳ Синхрончилж байна...")
        self.synced = False
        await self.sync_all_commands()
        
        # Команд бүртгэгдсэн эсэхийг шалгах
        commands = self.bot.tree.get_commands()
        command_list = "\n".join([f"/{cmd.name}" for cmd in commands])
        
        await ctx.send(f"✅ Синхрончлол дууслаа!\nБүртгэгдсэн командууд:\n```{command_list}```")

    @commands.command(name="sync_guild", help="Зөвхөн энэ серверт slash командуудыг синхрончлох.")
    @commands.is_owner()
    async def sync_guild(self, ctx):
        try:
            synced = await self.bot.tree.sync(guild=ctx.guild)
            await ctx.send(f"✅ `{len(synced)}` команд зөвхөн энэ серверт амжилттай синхрончлогдлоо.")
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: {e}")

    @commands.command(name="sync_server", help="Тодорхой серверт slash командуудыг синхрончлох.")
    @commands.is_owner()
    async def sync_server(self, ctx, guild_id: int):
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
    async def load(self, ctx, cog: str):
        try:
            await self.bot.load_extension(f"{cog}")
            await ctx.send(f"✅ `{cog}` амжилттай ачаалагдлаа!")
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: `{e}`")

    @commands.command(name='unload', help='Нэмэлтийг (cog) ачаалалгүй болгох.')
    @commands.is_owner()
    async def unload(self, ctx, cog: str):
        try:
            await self.bot.unload_extension(f"{cog}")
            await ctx.send(f"✅ `{cog}` амжилттай ачаалалгүй боллоо!")
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: `{e}`")

    @commands.command(name='reload', help='Нэмэлтийг (cog) дахин ачаалах.')
    @commands.is_owner()
    async def reload(self, ctx, cog: str):
        try:
            await self.bot.unload_extension(f"{cog}")
            await self.bot.load_extension(f"{cog}")
            await ctx.send(f"✅ `{cog}` амжилттай дахин ачаалагдлаа!")
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: `{e}`")

async def setup(bot):
    await bot.add_cog(Owner(bot))