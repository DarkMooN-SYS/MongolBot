from discord.ext import commands
import discord
import os
from typing import Optional
from .database import get_async_db_context

async def ensure_table():
    async with get_async_db_context('channel_permissions') as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channel_permissions (
                guild_id TEXT,
                channel_id TEXT,
                disabled INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, channel_id)
            )
        """)
        await db.commit()

async def is_channel_enabled(guild_id: int, channel_id: int) -> bool:
    """
    Channels are enabled by default. Only return False if explicitly disabled.
    """
    await ensure_table()
    async with get_async_db_context('channel_permissions') as db:
        async with db.execute("SELECT disabled FROM channel_permissions WHERE guild_id = ? AND channel_id = ?", (str(guild_id), str(channel_id))) as cursor:
            result = await cursor.fetchone()
            # If no record exists, channel is enabled by default
            # If record exists but disabled=0, channel is enabled
            # If record exists and disabled=1, channel is disabled
            return result is None or result[0] == 0

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
            async with get_async_db_context('channel_permissions') as db:
                if action == "enable":
                    # Бүх channel-уудыг идэвхжүүлэх (disabled records устгах)
                    await db.execute("DELETE FROM channel_permissions WHERE guild_id = ?", (str(ctx.guild.id),))
                    await db.commit()
                    await ctx.send("Бүх channel дээр командууд идэвхжлээ! (default)")
                else:                    # Бүх channel-уудыг идэвхгүй болгох
                    for channel in ctx.guild.text_channels:
                        await db.execute("INSERT OR REPLACE INTO channel_permissions (guild_id, channel_id, disabled) VALUES (?, ?, 1)", (str(ctx.guild.id), str(channel.id)))
                    await db.commit()
                    await ctx.send("Бүх channel дээр командууд идэвхгүй боллоо!")
        elif target and target.startswith("<#") and target.endswith(">"):
            # Channel mention хэлбэрээр ирсэн бол
            channel_id = int(target[2:-1])
            channel = ctx.guild.get_channel(channel_id)
            if not channel:
                await ctx.send("Channel олдсонгүй!")
                return
            async with get_async_db_context('channel_permissions') as db:
                if action == "enable":
                    # Enable channel (remove disabled record or set disabled=0)
                    await db.execute("DELETE FROM channel_permissions WHERE guild_id = ? AND channel_id = ?", (str(ctx.guild.id), str(channel.id)))
                    await db.commit()
                    await ctx.send(f"{channel.mention} дээр командууд идэвхжлээ! (default)")
                else:
                    # Disable channel (set disabled=1)
                    await db.execute("INSERT OR REPLACE INTO channel_permissions (guild_id, channel_id, disabled) VALUES (?, ?, 1)", (str(ctx.guild.id), str(channel.id)))
                    await db.commit()
                    await ctx.send(f"{channel.mention} дээр командууд идэвхгүй боллоо!")
        else:
            await ctx.send("Жишээ: !channel enable all | !channel disable all | !channel enable #channel | !channel disable #channel")

async def setup(bot: commands.Bot):
    await bot.add_cog(ChannelPermission(bot))
