from typing import Union, List, Optional
from discord.ext import commands
import discord
import aiosqlite
import logging

logger = logging.getLogger(__name__)
default_prefix = ["m", "M"]
prefixes = {}

async def init_db():
    """Префикс хадгалах хүснэгт үүсгэх"""
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS prefixes (
                guild_id INTEGER PRIMARY KEY,
                prefix TEXT NOT NULL
            )
        """)
        await db.commit()

async def load_prefixes():
    """Бүх префиксүүдийг датабаазаас ачаалах"""
    try:
        async with aiosqlite.connect("bot.db") as db:
            async with db.execute("SELECT guild_id, prefix FROM prefixes") as cursor:
                async for row in cursor:
                    prefixes[row[0]] = row[1]
        logger.info("✅ Префиксүүд амжилттай ачаалагдлаа")
    except Exception as e:
        logger.error(f"❌ Префикс ачаалахад алдаа гарлаа: {e}")

def get_prefix(bot: commands.Bot, message: discord.Message) -> Union[List[str], str]:
    """Тухайн серверийн command prefix-ийг авах"""
    guild_id = message.guild.id if message.guild else None
    return prefixes.get(guild_id, default_prefix)

async def set_prefix(guild_id: int, new_prefix: str) -> str:
    """Серверийн шинэ prefix тохируулах"""
    if len(new_prefix) > 15:
        return "⚠️ Префикс 15 тэмдэгтээс богино байх ёстой!"
    
    try:
        async with aiosqlite.connect("bot.db") as db:
            await db.execute(
                "INSERT OR REPLACE INTO prefixes (guild_id, prefix) VALUES (?, ?)",
                (guild_id, new_prefix)
            )
            await db.commit()
            
        prefixes[guild_id] = new_prefix
        return f"✅ Команд префикс `{new_prefix}` болж өөрчлөгдлөө!"
    
    except Exception as e:
        logger.error(f"❌ Префикс хадгалахад алдаа гарлаа: {e}")
        return "⚠️ Префикс өөрчлөхөд алдаа гарлаа. Дахин оролдоно уу!"