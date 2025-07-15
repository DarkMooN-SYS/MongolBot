# minijob.py

import discord
from discord.ext import commands
import random
from datetime import datetime, timedelta
from utils.database import get_async_db_context  # Ensure this imports a function/class, not a module

class Minijob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='work')
    async def work(self, ctx: commands.Context):
        user_id = ctx.author.id

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

        now = datetime.utcnow()

        async with get_async_db_context("economy") as db:  # Make sure get_async_db_context is a function/class, not a module
            await db.execute("""CREATE TABLE IF NOT EXISTS users (
                                user_id INTEGER PRIMARY KEY,
                                balance INTEGER DEFAULT 0,
                                last_work TIMESTAMP)""")
            await db.commit()

            # Хэрэглэгч байгаа эсэхийг шалгана
            cursor = await db.execute("SELECT balance, last_work FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()

            if row is None:
                # Хэрэглэгч байхгүй бол шинэчлэн бүртгэх
                last_work = now - timedelta(hours=1)
                await db.execute("INSERT INTO users (user_id, balance, last_work) VALUES (?, ?, ?)", (user_id, 0, last_work))
                await db.commit()
                balance = 0
            else:
                balance, last_work_str = row
                last_work = datetime.strptime(last_work_str, "%Y-%m-%d %H:%M:%S.%f") if last_work_str else now - timedelta(hours=1)

            # Cooldown шалгах
            if now - last_work < timedelta(hours=1):
                remaining = timedelta(hours=1) - (now - last_work)
                mins, secs = divmod(remaining.seconds, 60)
                return await ctx.send(f"⏳ Та дахин ажиллахын тулд {mins} минут {secs} секунд хүлээнэ үү.")

            # Санамсаргүй ажил, тогтмол цалин
            job, salary = random.choice(jobs)
            new_balance = balance + salary

            await db.execute("UPDATE users SET balance = ?, last_work = ? WHERE user_id = ?", (new_balance, now, user_id))
            await db.commit()

        # Embed хариу
        embed = discord.Embed(
            title="💼 Ажил амжилттай!",
            description=f"**Та \"{job}\" ажил хийж {salary:,}₮ цалин авлаа!**\n\n💰 Шинэ баланс: {new_balance:,}₮",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Minijob(bot))