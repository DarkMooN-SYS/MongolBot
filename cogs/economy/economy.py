import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import CooldownMapping, Cooldown, BucketType
import datetime
from typing import Optional
import random
import logging
import time
import re
import os
from ..utils.database import get_async_connection
import aiosqlite

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        """Economy когийг эхлүүлэх

        Args:
            bot: Discord бот
        """
        self.bot = bot
        self.conn: Optional[aiosqlite.Connection] = None
        self.cursor: Optional[aiosqlite.Cursor] = None
        self.cooldowns = {}
        self.bot.loop.create_task(self.setup_database())

    async def setup_database(self) -> None:
        self.conn = await get_async_connection('economy')
        await self.conn.execute("PRAGMA journal_mode=WAL;")
        self.cursor = await self.conn.cursor()
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS economy (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 5000,
                last_reward INTEGER DEFAULT 0
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bank (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 5000
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS rewards (
                user_id INTEGER PRIMARY KEY,
                streak INTEGER DEFAULT 0,
                last_claim INTEGER DEFAULT 0
            )
        """)
        await self.conn.commit()

    async def ensure_connection(self) -> None:
        if self.conn is None:
            await self.setup_database()
        if self.conn is None:
            raise RuntimeError("Database connection is not established!")

    async def insert_user(self, user_id: int) -> None:
        await self.ensure_connection()
        if self.conn is None:
            raise RuntimeError("Database connection is not established!")
        async with self.conn.execute("SELECT user_id FROM economy WHERE user_id = ?", (user_id,)) as cursor:
            if await cursor.fetchone() is None:
                await self.ensure_connection()
                if self.conn is None:
                    raise RuntimeError("Database connection is not established!")
                await self.conn.execute("INSERT INTO economy (user_id, balance, last_reward) VALUES (?, 5000, 0)", (user_id,))
                await self.ensure_connection()
                if self.conn is None:
                    raise RuntimeError("Database connection is not established!")
                await self.conn.commit()

    async def update_balance(self, table_name: str, user_id: int, amount: int) -> None:
        await self.ensure_connection()
        if self.conn is None:
            raise RuntimeError("Database connection is not established!")
        async with self.conn.execute(f"SELECT balance FROM {table_name} WHERE user_id=?", (user_id,)) as cursor:
            balance_result = await cursor.fetchone()
            balance = int(balance_result[0]) if balance_result and balance_result[0] is not None else 5000
            new_balance = balance + amount
            if new_balance < 0:
                raise ValueError("Insufficient funds!")
            await self.ensure_connection()
            if self.conn is None:
                raise RuntimeError("Database connection is not established!")
            await self.conn.execute(f"""
                INSERT INTO {table_name} (user_id, balance)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET balance=?""",
                (user_id, new_balance, new_balance))
            await self.ensure_connection()
            if self.conn is None:
                raise RuntimeError("Database connection is not established!")
            await self.conn.commit()

    async def get_user_balance(self, user_id: int) -> int:
        await self.ensure_connection()
        if self.conn is None:
            raise RuntimeError("Database connection is not established!")
        async with self.conn.execute("SELECT balance FROM economy WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 5000

    async def check_account_and_send_message(self, ctx: commands.Context) -> bool:
        """Хэрэглэгчийн данс байгаа эсэхийг шалгах"""
        if await self.get_user_balance(ctx.author.id) == 5000:
            await ctx.send("Таны данс байхгүй байна. Эхлээд мөнгөний системийг ашиглана уу!")
            return False
        return True

    async def check_cooldown(self, ctx: commands.Context, command_name: str) -> bool:
        now = int(time.time())
        user_id = ctx.author.id
        if not hasattr(self, "_cooldown_map"):
            self._cooldown_map = {}
        key = (user_id, command_name)
        cooldown = self._cooldown_map.get(key, 0)
        if now < cooldown:
            await ctx.send(f"⏳ Та түр хүлээнэ үү! ({cooldown - now} секунд)")
            return False
        # 10 секунд cooldown (хүсвэл customize хийж болно)
        self._cooldown_map[key] = now + 10
        return True

    @commands.command(name='balance', aliases=['bal'])
    async def balance(self, ctx: commands.Context, user: discord.Member | None = None) -> None:
        """Хэрэглэгчийн балансыг харах"""
        if not await self.check_cooldown(ctx, 'balance'):
            return
        try:
            if user is None:
                if isinstance(ctx.author, discord.Member):
                    user = ctx.author
                else:
                    if ctx.guild is not None:
                        user = ctx.guild.get_member(ctx.author.id)
                    else:
                        user = None
                    if user is None:
                        await ctx.send("Хэрэглэгч олдсонгүй.")
                        return
            result = await self.get_user_balance(user.id)
            if result is None:
                await self.insert_user(user.id)
                await ctx.send(f"{user.mention}-ийн Халаасанд 0 төгрөг байна!")
            else:
                user_balance = result
                await ctx.send(f"{user.mention}-ийн Халаасанд {user_balance:,} төгрөг байна!")
        except Exception as e:
            await ctx.send("Алдаа гарлаа! Хүлээгээрэй.")
            logging.error(f"Error in balance command: {e}")

    @commands.command(name='give')
    async def give(self, ctx: commands.Context, user: discord.Member | None = None, amount: str = "1") -> None:
        if user is None or amount is None:
            await ctx.send("⚠️ Та мөнгө өгөх хэрэглэгч болон хэмжээг заавал оруулна уу! `mgive @User 1000`")
            return
        amt = self.number(amount)
        if isinstance(amt, str):
            await ctx.send(amt)
            return
        if isinstance(amt, int) and amt <= 0:
            await ctx.send("⚠️ Та 0 буюу түүнээс бага мөнгө өгөх боломжгүй!")
            return
        await self.ensure_connection()
        if user.id == ctx.author.id:
            await ctx.send("⚠️ Та өөртөө мөнгө өгөх боломжгүй!")
            return
        try:
            await self.ensure_connection()
            if self.conn is None:
                raise RuntimeError("Database connection is not established!")
            async with self.conn.execute(
                "SELECT user_id, balance FROM economy WHERE user_id IN (?, ?)",
                (ctx.author.id, user.id)
            ) as cursor:
                balances = await cursor.fetchall()
            balance_dict = {user_id: balance for user_id, balance in balances}
            if ctx.author.id not in balance_dict:
                await self.update_balance("economy", ctx.author.id, 5000)
                balance_dict[ctx.author.id] = 5000
            if user.id not in balance_dict:
                await self.update_balance("economy", user.id, 5000)
                balance_dict[user.id] = 5000
            author_balance = balance_dict[ctx.author.id]
            if amt > author_balance:
                await ctx.send("⚠️ Таны баланс хүрэлцэхгүй байна!")
                return
            await self.update_balance("economy", ctx.author.id, -amt)
            await self.update_balance("economy", user.id, amt)
            await ctx.send(f"✅ Та **{amt:,}₮** {user.mention}-д амжилттай илгээлээ!")
        except Exception as e:
            logging.error(f"Error in give command: {e}")
            await ctx.send("⚠️ Алдаа гарлаа, дахин оролдоно уу.")

    @commands.command(name='daily')
    async def daily_reward(self, ctx: commands.Context) -> None:
        try:
            current_time = int(datetime.datetime.now().timestamp())
            await self.ensure_connection()
            if self.conn is None:
                raise RuntimeError("Database connection is not established!")
            async with self.conn.execute("SELECT streak, last_claim FROM rewards WHERE user_id = ?", (ctx.author.id,)) as cursor:
                reward_data = await cursor.fetchone()
            if reward_data is None:
                await self.insert_user(ctx.author.id)
                await self.ensure_connection()
                if self.conn is None:
                    raise RuntimeError("Database connection is not established!")
                await self.conn.execute("INSERT INTO rewards (user_id, streak, last_claim) VALUES (?, 0, 0)", (ctx.author.id,))
                await self.ensure_connection()
                if self.conn is None:
                    raise RuntimeError("Database connection is not established!")
                await self.conn.commit()
                reward_data = (0, 0)
            if current_time - reward_data[1] >= 43200:
                streak = reward_data[0] + 1
                reward_amount = self.calculate_reward(streak)
                await self.ensure_connection()
                if self.conn is None:
                    raise RuntimeError("Database connection is not established!")
                await self.conn.execute("UPDATE rewards SET last_claim = ?, streak = ? WHERE user_id = ?", (current_time, streak, ctx.author.id))
                await self.ensure_connection()
                if self.conn is None:
                    raise RuntimeError("Database connection is not established!")
                await self.conn.execute("UPDATE economy SET balance = balance + ? WHERE user_id = ?", (reward_amount, ctx.author.id))
                await self.ensure_connection()
                if self.conn is None:
                    raise RuntimeError("Database connection is not established!")
                await self.conn.commit()
                await ctx.send(f"💸 | {ctx.author.display_name}, энэ таны шагнал байна 🤑 {reward_amount:,} төгрөг!")
            else:
                next_claim_time = reward_data[1] + 43200
                remaining_time = next_claim_time - current_time
                hours, remainder = divmod(remaining_time, 3600)
                minutes, seconds = divmod(remainder, 60)
                await ctx.send(f"⏱ | Уучлаарай! {ctx.author.mention}! Та хүлээх хэрэгтэй {hours:02d}H {minutes:02d}M {seconds:02d}S")
        except Exception as e:
            await ctx.send("Алдаа гарлаа! Хүлээгээрэй.")
            logging.error(f"Error in daily_reward command: {e}")

    def calculate_reward(self, streak: int) -> int:
        """Calculate the daily reward amount based on the user's streak."""
        base_reward = 1000
        bonus = min(streak * 100, 500000)  # Example: 100 per streak, max 500000 bonus
        return base_reward + bonus

    @commands.command(name='add')
    @commands.is_owner()
    async def madd(self, ctx: commands.Context, account_type: str, user: discord.Member, amount: str) -> None:
        await self.ensure_connection()
        amt = self.number(amount)
        if isinstance(amt, str) or amt <= 0:
            await ctx.send("⚠️ Оруулсан хэмжээ хүчинтэй тоо биш байна!")
            return
        if account_type.lower() == "bank":
            table = "bank"
        elif account_type.lower() == "bal":
            table = "economy"
        else:
            await ctx.send("⚠️ Буруу аккаунтын төрөл! `madd bank @user 1k` эсвэл `madd bal @user 1m` гэж ашиглана уу.")
            return
        try:
            await self.ensure_connection()
            if self.conn is None:
                raise RuntimeError("Database connection is not established!")
            await self.update_balance(table, user.id, amt)
            await ctx.send(f"✅ {amt:,} төгрөг {user.mention}-ийн **{table}** дансанд нэмэгдлээ!")
        except Exception as e:
            await ctx.send("⚠️ Алдаа гарлаа! Дахин оролдоно уу.")
            logging.error(f"Error in madd command: {e}")

    @commands.command(name='remove')
    @commands.is_owner()
    async def remove(self, ctx: commands.Context, account_type: str, user: discord.Member, amount: str) -> None:
        """Админ хэрэглэгчийн банк эсвэл баланснаас мөнгө хасах."""
        await self.ensure_connection()

        amt = self.number(amount)
        if isinstance(amt, str) or amt <= 0:
            await ctx.send("⚠️ Оруулсан хэмжээ хүчинтэй тоо биш байна!")
            return

        if account_type.lower() == "bank":
            table = "bank"
        elif account_type.lower() == "bal":
            table = "economy"
        else:
            await ctx.send("⚠️ Буруу аккаунтын төрөл! `remove bank @user 1k` эсвэл `remove bal @user 1m` гэж ашиглана уу.")
            return

        try:
            if table == "economy":
                current_balance = await self.get_user_balance(user.id)
            else:
                current_balance = await self.get_balance(user.id, "bank")

            if amt > current_balance:
                await ctx.send(f"⚠️ {user.mention}-ийн **{table}** данснаас **{amt:,}₮** хасах боломжгүй! (Одоогийн баланс: {current_balance:,}₮)")
                return

            await self.update_balance(table, user.id, -amt)
            await ctx.send(f"✅ {amt:,} төгрөг {user.mention}-ийн **{table}** данснаас хасагдлаа!")
        except Exception as e:
            await ctx.send("⚠️ Алдаа гарлаа! Дахин оролдоно уу.")
            logging.error(f"Error in remove command: {e}")

    @commands.command(name='top')
    async def top(self, ctx: commands.Context) -> None:
        """Эдийн засгийн хамгийн баян 10 хэрэглэгчийн жагсаалт"""
        await self.ensure_connection()
        if self.conn is None:
            await ctx.send("⚠️ Өгөгдлийн сантай холбогдож чадсангүй!")
            logging.error("Database connection is not established in top command.")
            return
        try:
            async with self.conn.execute("SELECT user_id, balance FROM economy ORDER BY balance DESC LIMIT 10") as cursor:
                top_users = await cursor.fetchall()
            if not top_users:
                await ctx.send("📊 Одоогоор жагсаалт хоосон байна!")
                return
            desc = ""
            for i, (user_id, balance) in enumerate(top_users, 1):
                user = ctx.guild.get_member(user_id) if ctx.guild else None
                name = user.mention if user else f"<@{user_id}>"
                desc += f"**{i}.** {name} — `{balance:,}₮`\n"
            embed = discord.Embed(title="📊 Топ 10 баян хэрэглэгч", description=desc, color=0xFFD700)
            await ctx.send(embed=embed)
        except Exception as e:
            logging.error(f"Error in top command: {e}")
            await ctx.send("⚠️ Алдаа гарлаа! Дахин оролдоно уу.")

    async def cog_unload(self) -> None:
        if self.conn:
            await self.conn.close()

    def number(self, number_str: str | None) -> int | str:
        if number_str is None:
            return "❌ Буруу формат! Тоон утга оруулна уу."
        number_str = number_str.lower().strip().replace(",", ".")
        multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000, "t": 1_000_000_000_000}
        match = re.fullmatch(r"(\d+(\.\d+)?)([kmbt]?)", number_str)
        if not match:
            return "❌ Буруу формат! Зөвшөөрөгдсөн хэлбэр: 1.5k, 10m, 2.3b, 5.55k"
        num, _, suffix = match.groups()
        try:
            return int(float(num) * multipliers.get(suffix, 1))
        except ValueError:
            return "❌ Алдаа гарлаа! Тоог хөрвүүлэх боломжгүй байна."

    async def get_balance(self, user_id: int, table: str = "bank") -> int:
        await self.ensure_connection()
        if self.conn is None:
            raise RuntimeError("Database connection is not established!")
        try:
            async with self.conn.execute(f"SELECT balance FROM {table} WHERE user_id=?", (user_id,)) as cursor:
                result = await cursor.fetchone()
                return int(result[0]) if result and result[0] is not None else 5000
        except Exception as e:
            logging.error(f"SQLite Error in get_balance: {e}")
            return 5000

def setup(bot: commands.Bot):
    return bot.loop.create_task(bot.add_cog(Economy(bot)))