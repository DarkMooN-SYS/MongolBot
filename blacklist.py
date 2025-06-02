import sqlite3
import discord
from discord.ext import commands

def get_db_connection():
    return sqlite3.connect("blacklist.db")

class Blacklist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.blacklist_users = set()
        self.blacklist_guilds = set()
        self.load_blacklist()

    def load_blacklist(self):
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS blacklist_users (
                user_id INTEGER PRIMARY KEY
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS blacklist_guilds (
                guild_id INTEGER PRIMARY KEY
            )''')
            c.execute("SELECT user_id FROM blacklist_users")
            self.blacklist_users = {row[0] for row in c.fetchall()}
            c.execute("SELECT guild_id FROM blacklist_guilds")
            self.blacklist_guilds = {row[0] for row in c.fetchall()}

    def is_blacklisted(self, ctx):
        return ctx.author.id in self.blacklist_users or ctx.guild.id in self.blacklist_guilds

    async def cog_check(self, ctx):
        if self.is_blacklisted(ctx):
            await ctx.send("🚫 📩 Хэрэв энэ талаар албан ёсоор лавлахыг хүсвэл доорх серверт нэгдэж, тусламж хүсээрэй.\n👉 [МонголBot албан ёсны сервер](https://discord.gg/GnVkB37xZS)")
            return False
        return True

    @commands.command(name="blockuser")
    @commands.is_owner()
    async def blacklistuser(self, ctx, user: discord.User = None, user_id: int = None):
        if not user and not user_id:
            return await ctx.send("⚠️ Хэрэглэгчийн mention эсвэл ID-г өгнө үү.")

        target_id = user.id if user else user_id

        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO blacklist_users (user_id) VALUES (?)", (target_id,))
            conn.commit()

        self.blacklist_users.add(target_id)
        await ctx.send(f"✅ <@{target_id}> хэрэглэгчийг blacklist-д амжилттай нэмлээ.")

    @commands.command(name="unblockuser")
    @commands.is_owner()
    async def unblacklistuser(self, ctx, user: discord.User = None, user_id: int = None):
        if not user and not user_id:
            return await ctx.send("⚠️ Хэрэглэгчийн mention эсвэл ID-г өгнө үү.")

        target_id = user.id if user else user_id

        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM blacklist_users WHERE user_id = ?", (target_id,))
            conn.commit()

        self.blacklist_users.discard(target_id)
        await ctx.send(f"✅ <@{target_id}> хэрэглэгчийг blacklist-ээс амжилттай хаслаа.")

    @commands.command(name="blockguild")
    @commands.is_owner()
    async def blacklistguild(self, ctx, guild_id: int):
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO blacklist_guilds (guild_id) VALUES (?)", (guild_id,))
            conn.commit()

        self.blacklist_guilds.add(guild_id)
        await ctx.send(f"✅ Сервер `{guild_id}`-ийг blacklist-д амжилттай нэмлээ.")

    @commands.command(name="unblockguild")
    @commands.is_owner()
    async def unblacklistguild(self, ctx, guild_id: int):
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM blacklist_guilds WHERE guild_id = ?", (guild_id,))
            conn.commit()

        self.blacklist_guilds.discard(guild_id)
        await ctx.send(f"✅ Сервер `{guild_id}`-ийг blacklist-ээс амжилттай хаслаа.")

async def setup(bot):
    await bot.add_cog(Blacklist(bot))