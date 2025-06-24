# MongolBot Database Connection Helper
# Бүх cogs-д ашиглах database холболтын туслах функцууд

import sqlite3
import aiosqlite
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Database файлуудын үндсэн зам
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Database файлуудын жагсаалт
DATABASES = {
    'bot_config': 'bot.db',  # Bot configuration, prefixes, guilds
    'economy': 'economy.db',    
    'birthdays': 'birthdays.db',
    'giveaways': 'giveaways.db',
    'counting': 'counting.db',
    'suggestions': 'suggestions.db',
    'serverbank': 'serverbank.db',
    'disabled_channels': 'disabled_channels.db',
    'blacklist': 'blacklist.db',
    'prefixes': 'prefixes.db',
    'staff_channels': 'staff_channels.db'
}

def get_db_path(db_name: str) -> str:
    """Database файлын бүрэн зам авах"""
    if db_name in DATABASES:
        return str(DATA_DIR / DATABASES[db_name])
    else:
        # Хэрэв жагсаалтад байхгүй бол data фолдерт .db өргөтгөлтэй файл үүсгэх
        return str(DATA_DIR / f"{db_name}.db")

def get_sync_connection(db_name: str) -> sqlite3.Connection:
    """Синхрон SQLite холболт авах"""
    db_path = get_db_path(db_name)
    conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

async def get_async_connection(db_name: str) -> aiosqlite.Connection:
    """Асинхрон SQLite холболт авах"""
    db_path = get_db_path(db_name)
    conn = await aiosqlite.connect(db_path)
    await conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def get_db_connection(db_name: str = 'bot_config') -> sqlite3.Connection:
    """Ерөнхий database холболт авах функц (backwards compatibility)"""
    return get_sync_connection(db_name)

# Backwards compatibility aliases
def get_economy_db() -> sqlite3.Connection:
    """Economy database холболт"""
    return get_sync_connection('economy')

def get_main_db() -> sqlite3.Connection:
    """Main bot database холболт"""
    return get_sync_connection('bot_config')

def get_suggestions_db() -> sqlite3.Connection:
    """Suggestions database холболт"""
    return get_sync_connection('suggestions')

def get_blacklist_db() -> sqlite3.Connection:
    """Blacklist database холболт"""
    return get_sync_connection('blacklist')

def get_birthdays_db() -> sqlite3.Connection:
    """Birthdays database холболт"""
    return get_sync_connection('birthdays')

def get_giveaways_db() -> sqlite3.Connection:
    """Giveaways database холболт"""
    return get_sync_connection('giveaways')

def get_counting_db() -> sqlite3.Connection:
    """Counting game database холболт"""
    return get_sync_connection('counting')

def get_serverbank_db() -> sqlite3.Connection:
    """Serverbank database холболт"""
    return get_sync_connection('serverbank')

def get_disabled_channels_db() -> sqlite3.Connection:
    """Disabled channels database холболт"""
    return get_sync_connection('disabled_channels')

# Context manager үүсгэх
class DatabaseConnection:
    """Database холболтын context manager"""
    
    def __init__(self, db_name: str = 'bot_config'):
        self.db_name = db_name
        self.conn = None
    
    def __enter__(self) -> sqlite3.Connection:
        self.conn = get_sync_connection(self.db_name)
        return self.conn
    
    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any]
    ):
        if self.conn:
            self.conn.close()

# Async context manager
class AsyncDatabaseConnection:
    """Асинхрон database холболтын context manager"""
    
    def __init__(self, db_name: str = 'bot_config'):
        self.db_name = db_name
        self.conn = None
    
    async def __aenter__(self) -> aiosqlite.Connection:
        self.conn = await get_async_connection(self.db_name)
        return self.conn
    
    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any]
    ):
        if self.conn:
            await self.conn.close()

# Log мэдээлэл
logger.info(f"📁 Database файлууд: {DATA_DIR}")
for name, filename in DATABASES.items():
    full_path = DATA_DIR / filename
    if full_path.exists():
        logger.debug(f"✅ {name}: {filename}")
    else:
        logger.debug(f"⚠️ {name}: {filename} (файл байхгүй)")
