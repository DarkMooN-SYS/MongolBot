from typing import Union, List, Optional
from discord.ext import commands
import discord
import aiosqlite
import logging
from .database import get_db_path

logger = logging.getLogger(__name__)
# Default prefix-г array биш string болгох
default_prefix = ">"
prefixes = {}

async def init_db():
    """Префикс болон серверийн хүснэгтүүд үүсгэх"""
    async with aiosqlite.connect(get_db_path('bot_config')) as db:
        # Префикс хүснэгт
        await db.execute("""
            CREATE TABLE IF NOT EXISTS prefixes (
                guild_id INTEGER PRIMARY KEY,
                prefix TEXT NOT NULL
            )
        """)
        # Серверийн хүснэгт
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id TEXT PRIMARY KEY,
                prefix TEXT DEFAULT '>'
            )
        """)
        await db.commit()

async def load_prefixes():
    """Бүх префиксүүдийг датабаазаас ачаалах"""
    try:
        async with aiosqlite.connect(get_db_path('bot_config')) as db:
            # Хуучин префиксүүдийг ачаалах
            async with db.execute("SELECT guild_id, prefix FROM prefixes") as cursor:
                async for row in cursor:
                    prefixes[row[0]] = row[1]
                    
            # guilds хүснэгтээс префиксүүдийг нэмж ачаалах
            async with db.execute("SELECT guild_id, prefix FROM guilds") as cursor:
                async for row in cursor:
                    guild_id = int(row[0])
                    if guild_id not in prefixes:  # Хуучин prefix байхгүй бол л нэмнэ
                        prefixes[guild_id] = row[1]
                        
        logger.info("✅ Префиксүүд амжилттай ачаалагдлаа")
    except Exception as e:
        logger.error(f"❌ Префикс ачаалахад алдаа гарлаа: {e}")

def get_prefix(bot: commands.Bot, message: discord.Message) -> list[str]:
    """Тухайн серверийн command prefix-ийг авах"""
    if not message.guild:
        return [default_prefix.lower(), default_prefix.upper()]
        
    guild_id = message.guild.id
    prefix = prefixes.get(guild_id, default_prefix)
    # Том жижиг үсгийн хувилбарыг буцаах
    return [prefix.lower(), prefix.upper()]

async def set_prefix(guild_id: int, new_prefix: str) -> str:
    """Серверийн шинэ prefix тохируулах"""
    if len(new_prefix) > 15:
        return "⚠️ Префикс 15 тэмдэгтээс богино байх ёстой!"
    
    try:
        async with aiosqlite.connect(get_db_path('bot_config')) as db:
            # prefixes хүснэгтэд хадгалах
            await db.execute(
                "INSERT OR REPLACE INTO prefixes (guild_id, prefix) VALUES (?, ?)",
                (guild_id, new_prefix)
            )
            # guilds хүснэгтэд хадгалах
            await db.execute(
                "INSERT OR REPLACE INTO guilds (guild_id, prefix) VALUES (?, ?)",
                (str(guild_id), new_prefix)
            )
            await db.commit()
            
        prefixes[guild_id] = new_prefix
        return f"✅ Команд префикс `{new_prefix}` болж өөрчлөгдлөө!"
    
    except Exception as e:
        logger.error(f"❌ Префикс хадгалахад алдаа гарлаа: {e}")
        return "⚠️ Префикс өөрчлөхөд алдаа гарлаа. Дахин оролдоно уу!"
