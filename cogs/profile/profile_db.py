import aiosqlite
from pathlib import Path
import asyncio
from typing import Optional, Any

class ProfileDB:
    def __init__(self, bot: Any):
        self.bot = bot
        # Өгөгдлийн санг хадгалах data хавтсыг зааж өгнө
        self.data_dir: Path = Path(__file__).parent.parent.parent / 'data'
        self.data_dir.mkdir(exist_ok=True)
        self.db_path: Path = self.data_dir / 'profile.db'
        self.conn: Optional[aiosqlite.Connection] = None
        self.bot.loop.create_task(self.setup_database())

    async def setup_database(self) -> None:
        self.conn = await aiosqlite.connect(str(self.db_path))
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                about TEXT DEFAULT ''
            )
        ''')
        await self.conn.commit()

    async def get_profile(self, user_id: int) -> dict[str, Any]:
        if self.conn is None:
            raise RuntimeError("Database connection is not initialized.")
        async with self.conn.execute('SELECT xp, level, about FROM profiles WHERE user_id=?', (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                return {'xp': row[0], 'level': row[1], 'about': row[2]}
            else:
                return {'xp': 0, 'level': 1, 'about': ''}

    async def update_profile(self, user_id: int, xp: Optional[int] = None, level: Optional[int] = None, about: Optional[str] = None) -> None:
        if self.conn is None:
            raise RuntimeError("Database connection is not initialized.")
        profile = await self.get_profile(user_id)
        xp = xp if xp is not None else profile['xp']
        level = level if level is not None else profile['level']
        about = about if about is not None else profile['about']
        await self.conn.execute('''
            INSERT INTO profiles (user_id, xp, level, about) VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET xp=?, level=?, about=?
        ''', (user_id, xp, level, about, xp, level, about))
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()
