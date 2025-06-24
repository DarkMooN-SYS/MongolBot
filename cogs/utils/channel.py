import aiosqlite
from discord.ext import commands
import discord
import os
from typing import Optional

CHANNEL_DB = os.path.join(os.path.dirname(__file__), '../data/channel_permissions.db')

async def ensure_table():
    async with aiosqlite.connect(CHANNEL_DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channel_permissions (
                guild_id TEXT,
                channel_id TEXT,
                PRIMARY KEY (guild_id, channel_id)
            )
        """)
        await db.commit()

async def is_channel_enabled(guild_id: int, channel_id: int) -> bool:
    await ensure_table()
    async with aiosqlite.connect(CHANNEL_DB) as db:
        async with db.execute("SELECT 1 FROM channel_permissions WHERE guild_id = ? AND channel_id = ?", (str(guild_id), str(channel_id))) as cursor:
            return await cursor.fetchone() is not None

class ChannelPermission(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="channel")
    async def channel(self, ctx: commands.Context, action: str, target: Optional[str] = None):
        if not ctx.guild:
            await ctx.send("Энэ команд зөвхөн сервер дээр ажиллана.")
            return
        await ensure_table()
        action = action.lower()
        if action not in ("enable", "disable"):
            await ctx.send("Зөвхөн 'enable' эсвэл 'disable' гэж бичнэ үү.")
            return
        # all эсвэл channel
        if target == "all":
            async with aiosqlite.connect(CHANNEL_DB) as db:
                if action == "enable":
                    # Бүх channel-уудыг идэвхжүүлэх
                    for channel in ctx.guild.text_channels:
                        await db.execute("INSERT OR IGNORE INTO channel_permissions (guild_id, channel_id) VALUES (?, ?)", (str(ctx.guild.id), str(channel.id)))
                    await db.commit()
                    await ctx.send("Бүх channel дээр командууд идэвхжлээ!")
                else:
                    # Бүх channel-уудыг идэвхгүй болгох
                    await db.execute("DELETE FROM channel_permissions WHERE guild_id = ?", (str(ctx.guild.id),))
                    await db.commit()
                    await ctx.send("Бүх channel дээр командууд идэвхгүй боллоо!")
        elif target and target.startswith("<#") and target.endswith(">"):
            # Channel mention хэлбэрээр ирсэн бол
            channel_id = int(target[2:-1])
            channel = ctx.guild.get_channel(channel_id)
            if not channel:
                await ctx.send("Channel олдсонгүй!")
                return
            async with aiosqlite.connect(CHANNEL_DB) as db:
                if action == "enable":
                    await db.execute("INSERT OR IGNORE INTO channel_permissions (guild_id, channel_id) VALUES (?, ?)", (str(ctx.guild.id), str(channel.id)))
                    await db.commit()
                    await ctx.send(f"{channel.mention} дээр командууд идэвхжлээ!")
                else:
                    await db.execute("DELETE FROM channel_permissions WHERE guild_id = ? AND channel_id = ?", (str(ctx.guild.id), str(channel.id)))
                    await db.commit()
                    await ctx.send(f"{channel.mention} дээр командууд идэвхгүй боллоо!")
        else:
            await ctx.send("Жишээ: !channel enable all | !channel disable all | !channel enable #channel | !channel disable #channel")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        # Зөвхөн зөвшөөрөгдсөн channel-д команд ажиллуулна
        if not await is_channel_enabled(message.guild.id, message.channel.id):
            return
        await self.bot.process_commands(message)

async def setup(bot: commands.Bot):
    await bot.add_cog(ChannelPermission(bot))
