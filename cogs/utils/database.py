# MongolBot Database Manager
# Бүх database холболтыг энэ файлаар дамжуулна

import sqlite3
import aiosqlite
import logging
import os
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Database холболт хариуцах ерөнхий класс"""
    
    def __init__(self):
        # Database файлуудын зам тогтоох
        self.base_path = Path(__file__).parent.parent.parent / "data"
        self.base_path.mkdir(exist_ok=True)  # data фолдерыг үүсгэх
          # Database файлуудын бүрэн зам
        self.databases = {
            'bot_config': self.base_path / "bot.db",  # Bot configuration, prefixes, guilds
            'economy': self.base_path / "economy.db", 
            'birthdays': self.base_path / "birthdays.db",              
            'giveaways': self.base_path / "giveaways.db",
            'counting': self.base_path / "counting.db",
            'suggestions': self.base_path / "suggestions.db",
            'serverbank': self.base_path / "serverbank.db",
            'disabled_channels': self.base_path / "disabled_channels.db",
            'staff_channels': self.base_path / "staff_channels.db",
            'channel_permissions': self.base_path / "channel_permissions.db"
        }
    
    def get_db_path(self, db_name: str) -> str:
        """Database файлын зам авах
        
        Args:
            db_name: Database нэр ('bot_config', 'economy', гэх мэт)
            
        Returns:
            str: Database файлын бүрэн зам
        """
        if db_name in self.databases:
            return str(self.databases[db_name])
        else:
            logger.warning(f"⚠️ Тодорхойгүй database: {db_name}")
            return str(self.base_path / f"{db_name}.db")
    
    def get_sync_connection(self, db_name: str) -> sqlite3.Connection:
        """Синхрон database холболт авах
        
        Args:
            db_name: Database нэр
            
        Returns:
            sqlite3.Connection: Database холболт
        """
        try:
            db_path = self.get_db_path(db_name)
            conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA cache_size=1000;")
            logger.debug(f"✅ {db_name} database-д амжилттай холбогдлоо: {db_path}")
            return conn
        except Exception as e:
            logger.error(f"❌ {db_name} database холболтод алдаа: {e}")
            raise
    
    async def get_async_connection(self, db_name: str) -> aiosqlite.Connection:
        """Асинхрон database холболт авах
        
        Args:
            db_name: Database нэр
            
        Returns:
            aiosqlite.Connection: Асинхрон database холболт
        """
        try:
            db_path = self.get_db_path(db_name)
            conn = await aiosqlite.connect(db_path)
            await conn.execute("PRAGMA journal_mode=WAL;")
            await conn.execute("PRAGMA synchronous=NORMAL;")
            await conn.execute("PRAGMA cache_size=1000;")
            logger.debug(f"✅ {db_name} async database-д амжилттай холбогдлоо: {db_path}")
            return conn
        except Exception as e:
            logger.error(f"❌ {db_name} async database холболтод алдаа: {e}")
            raise

class AsyncDBConnection:
    """Асинхрон database холболтын context manager"""
    
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.db_path = db_manager.get_db_path(db_name)
        self.conn = None
        
    async def __aenter__(self):
        try:
            self.conn = await aiosqlite.connect(self.db_path)
            await self.conn.execute("PRAGMA journal_mode=WAL;")
            await self.conn.execute("PRAGMA synchronous=NORMAL;")
            await self.conn.execute("PRAGMA cache_size=1000;")
            logger.debug(f"✅ {self.db_name} async database-д амжилттай холбогдлоо: {self.db_path}")
            return self.conn
        except Exception as e:
            logger.error(f"❌ {self.db_name} async database холболтод алдаа: {e}")
            raise
            
    async def __aexit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]):
        if self.conn:
            try:
                await self.conn.close()
                logger.debug(f"🔗 {self.db_name} database холболт хаагдлаа")
            except Exception as e:
                logger.error(f"❌ {self.db_name} database хаахад алдаа: {e}")

# Global database manager instance
db_manager = DatabaseManager()

# Хялбар хэрэглээний функцууд
def get_db_path(db_name: str) -> str:
    """Database файлын зам авах хялбар функц"""
    return db_manager.get_db_path(db_name)

def get_sync_connection(db_name: str) -> sqlite3.Connection:
    """Синхрон database холболт авах хялбар функц"""
    return db_manager.get_sync_connection(db_name)

async def get_async_connection(db_name: str) -> aiosqlite.Connection:
    """Асинхрон database холболт авах хялбар функц"""
    return await db_manager.get_async_connection(db_name)

def get_async_db_context(db_name: str) -> AsyncDBConnection:
    """Асинхрон database context manager авах"""
    return AsyncDBConnection(db_name)