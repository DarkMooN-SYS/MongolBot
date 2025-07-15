# minijob.py

import discord
from discord.ext import commands
import random
from datetime import datetime, timedelta
import aiosqlite
from pathlib import Path
from typing import Optional

class Minijob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data_dir: Path = Path(__file__).parent.parent.parent / 'data'
        self.data_dir.mkdir(exist_ok=True)
        self.db_path: Path = self.data_dir / 'economy.db'
        self.conn: Optional[aiosqlite.Connection] = None

    async def get_conn(self):
        """Database connection үүсгэх (нэг л удаа холбогдоно)"""
        if not self.conn:
            self.conn = await aiosqlite.connect(self.db_path)
            await self.conn.execute("PRAGMA journal_mode=WAL;")
            await self.conn.execute("PRAGMA synchronous=NORMAL;")
            await self.conn.execute("PRAGMA cache_size=1000;")
            # Ensure 'last_work' column exists
            cursor = await self.conn.execute("PRAGMA table_info(economy);")
            columns = [row[1] async for row in cursor]
            if 'last_work' not in columns:
                await self.conn.execute("ALTER TABLE economy ADD COLUMN last_work TIMESTAMP;")
                await self.conn.commit()
        return self.conn

    @commands.command(name='work')
    async def work(self, ctx: commands.Context):
        user_id = ctx.author.id
        now = datetime.utcnow()

        jobs = [
            ('Цэвэрлэгч', 60000),
            ('Туслах тогооч', 70000),
            ('Жолооч', 90000),
            ('Хүргэлтийн ажилтан', 80000),
            ('Бичээч', 75000),
            ('Барилгын туслах', 70000),
            ('Номын санч', 65000),
            ('Цахилгаанчин', 95000),
            ('Сантехникч', 92000),
            ('Дугуй засварчин', 68000)
        ]

        db = await self.get_conn()

        await db.execute("""
            CREATE TABLE IF NOT EXISTS economy (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                last_work TIMESTAMP
            )
        """)
        await db.commit()

        # Хэрэглэгчийн мэдээлэл авах
        cursor = await db.execute("SELECT balance, last_work FROM economy WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()

        if row is None:
            balance = 0
            last_work = now - timedelta(hours=1)
            await db.execute("INSERT INTO economy (user_id, balance, last_work) VALUES (?, ?, ?)", (user_id, balance, last_work))
            await db.commit()
        else:
            balance, last_work_str = row
            last_work = datetime.strptime(last_work_str, "%Y-%m-%d %H:%M:%S.%f") if last_work_str else now - timedelta(hours=1)

        # Cooldown шалгах
        if now - last_work < timedelta(hours=1):
            remaining = timedelta(hours=1) - (now - last_work)
            mins, secs = divmod(remaining.seconds, 60)
            return await ctx.send(f"⏳ Та дахин ажиллахын тулд {mins} минут {secs} секунд хүлээнэ үү.")

        # Ажил болон цалин
        job, salary = random.choice(jobs)
        new_balance = balance + salary

        await db.execute("UPDATE economy SET balance = ?, last_work = ? WHERE user_id = ?", (new_balance, now, user_id))
        await db.commit()

        embed = discord.Embed(
            title="💼 Ажил амжилттай!",
            description=f"**Та \"{job}\" ажил хийж {salary:,}₮ цалин авлаа!**\n\n💰 Шинэ баланс: {new_balance:,}₮",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Minijob(bot))
