import sqlite3
import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import CooldownMapping, Cooldown, BucketType
import datetime
import random
import logging
import time
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Economy(commands.Cog):
    def __init__(self, bot, vip_cog):
        self.bot = bot
        self.vip_cog = vip_cog
        self.conn = sqlite3.connect('economy.db', check_same_thread=False, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL;")  # Enable WAL mode for better concurrency
        self.cursor = self.conn.cursor()
        self.setup_database()
        self.cooldowns = {}  # ← Энэ алга байсан!

    async def get_command_cooldown(self, user_id):
        return await self.vip_cog.get_cooldown_for_user(user_id)

    async def get_cooldown(self, command_name, user_id):
        base_cooldown = await self.get_command_cooldown(user_id)

        if command_name not in self.cooldowns:
            self.cooldowns[command_name] = CooldownMapping(Cooldown(1, base_cooldown), BucketType.user)
        else:
            self.cooldowns[command_name]._cooldown = Cooldown(1, base_cooldown)

        return self.cooldowns[command_name]

    async def check_cooldown(self, ctx, command_name):
        cooldown = await self.get_cooldown(command_name, ctx.author.id)
        bucket = cooldown.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()

        if retry_after:
            await ctx.send(f"⏳ Та **{retry_after:.1f}** секунд хүлээнэ үү!")
            return False
        return True

    def setup_database(self):
        try:
            with self.conn:
                self.cursor.execute("""
                    CREATE TABLE IF NOT EXISTS economy (
                        user_id INTEGER PRIMARY KEY,
                        balance INTEGER DEFAULT 5000,
                        last_reward INTEGER DEFAULT 0
                    )
                """)
                self.cursor.execute("""
                    CREATE TABLE IF NOT EXISTS bank (
                        user_id INTEGER PRIMARY KEY,
                        balance INTEGER DEFAULT 5000
                    )
                """)
                self.cursor.execute("""
                    CREATE TABLE IF NOT EXISTS rewards (
                        user_id INTEGER PRIMARY KEY,
                        streak INTEGER DEFAULT 0,
                        last_claim INTEGER DEFAULT 0
                    )
                """)
        except sqlite3.Error as e:
            logging.error(f"SQLite Error during database setup: {e}")

    def number(self, number_str):
        if number_str is None:  # `None` эсэхийг шалгах
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

    def ensure_connection(self):
        """🔹 SQLite холболтыг шалгах"""
        try:
            if self.conn is None:
                self.connect_db()  # 🔹 Хэрэв хаагдсан бол дахин холбох
            self.conn.execute("SELECT 1")  # 🔹 Мэдээллийн сан амьд эсэхийг шалгах
        except sqlite3.ProgrammingError:
            logger.error("⚠️ SQLite: Мэдээллийн сан хаагдсан байна! Шинэ холболт үүсгэж байна...")
            self.connect_db()

    def get_user_balance(self, user_id):
        try:
            self.cursor.execute("SELECT balance FROM economy WHERE user_id=?", (user_id,))
            result = self.cursor.fetchone()
            return int(result[0]) if result and result[0] is not None else 5000
        except sqlite3.Error as e:
            logging.error(f"SQLite Error in get_user_balance: {e}")
            return 5000

    def insert_user(self, user_id):
        try:
            with self.conn:
                self.cursor.execute("SELECT user_id FROM economy WHERE user_id = ?", (user_id,))
                if self.cursor.fetchone() is None:  # Хэрэв бүртгэгдээгүй бол
                    self.cursor.execute("INSERT INTO economy (user_id, balance, last_reward) VALUES (?, 5000, 0)", (user_id,))
        except sqlite3.Error as e:
            logging.error(f"SQLite Error in insert_user: {e}")

    def update_balance(self, table_name, user_id, amount):
        try:
            with self.conn:
                self.cursor.execute(f"SELECT balance FROM {table_name} WHERE user_id=?", (user_id,))
                balance_result = self.cursor.fetchone()
                balance = int(balance_result[0]) if balance_result and balance_result[0] is not None else 5000

                new_balance = balance + amount
                if new_balance < 0:
                    raise ValueError("Insufficient funds!")

                self.cursor.execute(f"""
                    INSERT INTO {table_name} (user_id, balance) 
                    VALUES (?, ?) 
                    ON CONFLICT(user_id) DO UPDATE SET balance=?""", 
                    (user_id, new_balance, new_balance))
        except sqlite3.Error as e:
            logging.error(f"SQLite Error in update_balance: {e}")
        except ValueError as e:
            logging.warning(f"{e}")

    async def check_account_and_send_message(self, ctx):
        if self.get_user_balance(ctx.author.id) == 5000:
            await ctx.send("Таны данс байхгүй байна. Эхлээд мөнгөний системийг ашиглана уу!")
            return False
        return True

    @commands.command(name='balance', aliases=['bal'])
    async def balance(self, ctx, user: discord.Member = None):
        if not await self.check_cooldown(ctx, 'balance'):
            return

        try:
            if user is None:
                user = ctx.author

            result = self.get_user_balance(user.id)
            if result is None:
                self.insert_user(user.id)
                await ctx.send(f"{user.mention}-ийн Халаасанд 0 төгрөг байна!")
            else:
                user_balance = result
                await ctx.send(f"{user.mention}-ийн Халаасанд {user_balance:,} төгрөг байна!")
        except Exception as e:
            await ctx.send("Алдаа гарлаа! Хүлээгээрэй.")
            logging.error(f"Error in balance command: {e}")

    @commands.command(name='give')
    async def give(self, ctx, user: discord.Member = None, amount: str = 1):
        if user is None or amount is None:
            await ctx.send("⚠️ Та мөнгө өгөх хэрэглэгч болон хэмжээг заавал оруулна уу! `mgive @User 1000`")
            return

        amount = self.number(amount)
        if isinstance(amount, str):  # Хэрэв хөрвүүлэлт амжилтгүй бол
            await ctx.send(amount)  # Алдааны мессежийг шууд харуулах
            return

        if amount <= 0:
            await ctx.send("⚠️ Та 0 буюу түүнээс бага мөнгө өгөх боломжгүй!")
            return

        self.ensure_connection()

        if user.id == ctx.author.id:
            await ctx.send("⚠️ Та өөртөө мөнгө өгөх боломжгүй!")
            return

        try:
            balances = self.cursor.execute(
                "SELECT user_id, balance FROM economy WHERE user_id IN (?, ?)", 
                (ctx.author.id, user.id)
            ).fetchall()

            balance_dict = {user_id: balance for user_id, balance in balances}

            if ctx.author.id not in balance_dict:
                self.update_balance("economy", ctx.author.id, 5000)
                balance_dict[ctx.author.id] = 5000

            if user.id not in balance_dict:
                self.update_balance("economy", user.id, 5000)
                balance_dict[user.id] = 5000

            author_balance = balance_dict[ctx.author.id]

            if amount > author_balance:
                await ctx.send("⚠️ Таны баланс хүрэлцэхгүй байна!")
                return

            # Шууд мөнгө шилжүүлэх (татваргүй)
            self.update_balance("economy", ctx.author.id, -amount)
            self.update_balance("economy", user.id, amount)

            await ctx.send(f"✅ Та **{amount:,}₮** {user.mention}-д амжилттай илгээлээ!")

        except sqlite3.ProgrammingError:
            logging.error("⚠️ SQLite: Мэдээллийн сан хаагдсан байна! Шинэ холболт үүсгэж байна...")
            self.connect_db()
            await ctx.send("⚠️ Алдаа гарлаа, дахин оролдоно уу.")

        except Exception as e:
            logging.error(f"Error in give command: {e}")
            await ctx.send("⚠️ Алдаа гарлаа, дахин оролдоно уу.")

    @commands.command(name='daily')
    async def daily_reward(self, ctx):
        try:
            current_time = int(datetime.datetime.now().timestamp())
            self.cursor.execute("SELECT streak, last_claim FROM rewards WHERE user_id = ?", (ctx.author.id,))
            reward_data = self.cursor.fetchone()

            if reward_data is None:
                self.insert_user(ctx.author.id)
                self.cursor.execute("INSERT INTO rewards (user_id, streak, last_claim) VALUES (?, 0, 0)", (ctx.author.id,))
                self.conn.commit()
                reward_data = (0, 0)

            if current_time - reward_data[1] >= 43200:
                streak = reward_data[0] + 1
                reward_amount = self.calculate_reward(streak)

                self.cursor.execute("UPDATE rewards SET last_claim = ?, streak = ? WHERE user_id = ?", (current_time, streak, ctx.author.id))
                self.cursor.execute("UPDATE economy SET balance = balance + ? WHERE user_id = ?", (reward_amount, ctx.author.id))
                self.conn.commit()

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

    @commands.command(name='add')
    @commands.is_owner()
    async def madd(self, ctx, account_type: str, user: discord.Member, amount: str):
        """Админ хэрэглэгчийн банк эсвэл балансад мөнгө нэмэх."""
        self.ensure_connection()

        amount = self.number(amount)
        if amount is None or amount <= 0:
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
            self.update_balance(table, user.id, amount)
            await ctx.send(f"✅ {amount:,} төгрөг {user.mention}-ийн **{table}** дансанд нэмэгдлээ!")
        except Exception as e:
            await ctx.send("⚠️ Алдаа гарлаа! Дахин оролдоно уу.")
            logging.error(f"Error in madd command: {e}")

    @commands.command(name='remove')
    @commands.is_owner()
    async def remove(self, ctx, account_type: str, user: discord.Member, amount: str):
        """Админ хэрэглэгчийн банк эсвэл баланснаас мөнгө хасах."""
        self.ensure_connection()

        amount = self.number(amount)
        if amount is None or amount <= 0:
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
            current_balance = self.get_user_balance(user.id) if table == "economy" else self.get_balance(user.id, "bank")

            if amount > current_balance:
                await ctx.send(f"⚠️ {user.mention}-ийн **{table}** данснаас **{amount:,}₮** хасах боломжгүй! (Одоогийн баланс: {current_balance:,}₮)")
                return

            self.update_balance(table, user.id, -amount)
            await ctx.send(f"✅ {amount:,} төгрөг {user.mention}-ийн **{table}** данснаас хасагдлаа!")
        except Exception as e:
            await ctx.send("⚠️ Алдаа гарлаа! Дахин оролдоно уу.")
            logging.error(f"Error in remove command: {e}")

    @commands.command(name='reset')
    @commands.is_owner()
    async def reset(self, ctx):
        try:
            self.cursor.execute("UPDATE economy SET balance = 5000")
            self.cursor.execute("UPDATE bank SET balance = 5000")
            self.cursor.execute("UPDATE rewards SET last_claim = 0")
            self.conn.commit()
            await ctx.send("Бүх баланс сэргээгдлээ! Дэлгэрэнгүй шагналын хүлээлт сэргээгдлээ!")
        except sqlite3.Error as e:
            await ctx.send("Алдаа гарлаа! Хүлээгээрэй.")
            logging.error(f"SQLite Error in reset command: {e}")
        except Exception as e:
            await ctx.send("Алдаа гарлаа! Хүлээгээрэй.")
            logging.error(f"General Error in reset command: {e}")

    @commands.command(name='top')
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def top(self, ctx, page: int = 1):
        try:
            self.cursor.execute("SELECT user_id, balance FROM economy ORDER BY balance DESC")
            results = self.cursor.fetchall()
            total_users = len(results)
            total_pages = (total_users + 4) // 5  # 5 хэрэглэгч нэг хуудсанд

            if page < 1 or page > total_pages:
                await ctx.send(f"Хуудас {page} байхгүй! Бүх хуудас: 1-{total_pages}.")
                return

            embed = discord.Embed(title="Лидерборд", description="Хамгийн баян хэрэглэгчүүд", color=0x00ff00)
            start_idx = (page - 1) * 5
            for i, (user_id, balance) in enumerate(results[start_idx:start_idx + 5], start=start_idx + 1):
                user = await self.bot.fetch_user(user_id)
                embed.add_field(name=f"{i}. {user.display_name if user else 'Нэргүй хэрэглэгч'}", value=f"{balance:,} төгрөг", inline=False)

            embed.set_footer(text=f"Хуудас {page}/{total_pages}")
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send("Алдаа гарлаа! Хүлээгээрэй.")
            logging.error(f"Error in top command: {e}")

    def calculate_reward(self, streak):
        reward_amounts = [
            (500, 0.35), (1000, 0.25), (2500, 0.15),
            (5000, 0.1), (10000, 0.05), (20000, 0.03),
            (50000, 0.02), (100000, 0.01)
        ]
        total_weight = sum(weight for _, weight in reward_amounts)
        r = random.random() * total_weight
        for amount, weight in reward_amounts:
            r -= weight
            if r <= 0:
                return int(amount * (1 + (streak - 1) * 0.01))
        return 500

    def cog_unload(self):
        self.conn.close()

async def setup(bot):
    vip_cog = bot.get_cog("VIP")
    await bot.add_cog(Economy(bot, vip_cog))