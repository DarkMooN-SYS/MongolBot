import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import CooldownMapping, Cooldown, BucketType
import datetime
from typing import Optional, List, Tuple, Any
import random
import logging
import time
import re
import os
from ..utils.database import get_async_connection
import aiosqlite
from ..utils.channel import is_channel_enabled

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
                current_balance = await self.get_bank_balance(user.id)

            if amt > current_balance:
                await ctx.send(f"⚠️ {user.mention}-ийн **{table}** данснаас **{amt:,}₮** хасах боломжгүй! (Одоогийн баланс: {current_balance:,}₮)")
                return

            await self.update_balance(table, user.id, -amt)
            await ctx.send(f"✅ {amt:,} төгрөг {user.mention}-ийн **{table}** данснаас хасагдлаа!")
        except Exception as e:
            await ctx.send("⚠️ Алдаа гарлаа! Дахин оролдоно уу.")
            logging.error(f"Error in remove command: {e}")

    async def get_bank_balance(self, user_id: int) -> int:
        """Get the user's bank balance."""
        await self.ensure_connection()
        if self.conn is None:
            raise RuntimeError("Database connection is not established!")
        async with self.conn.execute("SELECT balance FROM bank WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 5000

    async def get_top_users(self, guild: discord.Guild, table: str, page: int = 1, per_page: int = 10) -> Tuple[List[Tuple[int, int]], int]:
        """Серверийн топ хэрэглэгчдийг авах"""
        await self.ensure_connection()
        member_ids = [member.id for member in guild.members if not member.bot]
        
        if not member_ids:
            return [], 0
            
        placeholders = ','.join('?' * len(member_ids))
        offset = (page - 1) * per_page
        
        # Нийт тоо авах
        count_query = f"SELECT COUNT(*) FROM {table} WHERE user_id IN ({placeholders}) AND balance > 0"
        await self.ensure_connection()
        if self.conn is None:
            return [], 0
        async with self.conn.execute(count_query, member_ids) as cursor:
            count_row = await cursor.fetchone()
            total_count = count_row[0] if count_row is not None else 0
            
        # Хуудаслалттай өгөгдөл авах
        query = f"SELECT user_id, balance FROM {table} WHERE user_id IN ({placeholders}) AND balance > 0 ORDER BY balance DESC LIMIT {per_page} OFFSET {offset}"
        await self.ensure_connection()
        if self.conn is None:
            return [], total_count
        async with self.conn.execute(query, member_ids) as cursor:
            rows = await cursor.fetchall()
            users = [(int(row[0]), int(row[1])) for row in rows]
            
        return users, total_count

    def create_top_embed(self, guild: discord.Guild, users: List[Tuple[int, int]], page: int, total_pages: int, table: str) -> discord.Embed:
        """Топ хэрэглэгчдийн embed үүсгэх"""
        table_name = "💰 Мөнгө" if table == "economy" else "🏦 Банк"
        
        if not users:
            embed = discord.Embed(
                title=f"📊 {guild.name} - {table_name} Топ",
                description="Мэдээлэл олдсонгүй!",
                color=0xFFD700
            )
            return embed
            
        desc = ""
        start_rank = (page - 1) * 10 + 1
        
        for i, (user_id, balance) in enumerate(users):
            rank = start_rank + i
            user = guild.get_member(user_id)
            name = user.mention if user else f"<@{user_id}>"
            desc += f"**{rank}.** {name} — `{balance:,}₮`\n"
            
        embed = discord.Embed(
            title=f"📊 {guild.name} - {table_name} Топ",
            description=desc,
            color=0xFFD700
        )
        embed.set_footer(text=f"Хуудас {page}/{total_pages}")
        return embed

    @commands.command(name='top')
    async def top(self, ctx: commands.Context) -> None:
        """Тухайн серверийн хамгийн баян хэрэглэгчдийн жагсаалт (button-тай)"""
        await self.ensure_connection()
        if self.conn is None:
            await ctx.send("⚠️ Өгөгдлийн сантай холбогдож чадсангүй!")
            return
        
        if ctx.guild is None:
            await ctx.send("⚠️ Энэ команд зөвхөн сервер дээр ажиллана!")
            return
            
        try:
            # Анхны мэдээлэл авах (economy table, 1-р хуудас)
            users, total_count = await self.get_top_users(ctx.guild, "economy", 1)
            total_pages = max(1, (total_count + 9) // 10)  # 10-аар хуваах
            
            embed = self.create_top_embed(ctx.guild, users, 1, total_pages, "economy")
            
            # Button-ууд үүсгэх
            view = TopLeaderboardView(self, ctx.guild, "economy", 1, total_pages)
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            logging.error(f"Error in top command: {e}")
            await ctx.send("⚠️ Алдаа гарлаа! Дахин оролдоно уу.")


class TopLeaderboardView(discord.ui.View):
    def __init__(self, economy_cog: 'Economy', guild: discord.Guild, table: str, page: int, total_pages: int):
        super().__init__(timeout=300)
        self.economy_cog = economy_cog
        self.guild = guild
        self.table = table
        self.page = page
        self.total_pages = total_pages
        
        # Button-уудийг динамикаар нэмэх
        self._setup_buttons()
    
    def _setup_buttons(self) -> None:
        """Одоогийн table-д тохирсон button-уудыг динамикаар үүсгэх"""
        # Бүх button-уудыг арилгах
        self.clear_items()
        
        # Navigation button-ууд үргэлж байна
        # Эхний хуудас
        first_btn = discord.ui.Button(
            label='⏮️', 
            style=discord.ButtonStyle.secondary,
            disabled=(self.page == 1)
        )
        first_btn.callback = self.first_page_callback
        self.add_item(first_btn)
        
        # Өмнөх хуудас  
        prev_btn = discord.ui.Button(
            label='◀️', 
            style=discord.ButtonStyle.secondary,
            disabled=(self.page == 1)
        )
        prev_btn.callback = self.prev_page_callback
        self.add_item(prev_btn)
        
        # Toggle button - зөвхөн холбогдох нэг л button харагдана
        if self.table == "economy":
            # Balance leaderboard үзэж байгаа бол зөвхөн Bank button харагдана
            toggle_btn = discord.ui.Button(
                label='Bank', 
                emoji='🏦', 
                style=discord.ButtonStyle.primary
            )
            toggle_btn.callback = self.toggle_bank_callback
        else:  # bank
            # Bank leaderboard үзэж байгаа бол зөвхөн Balance button харагдана
            toggle_btn = discord.ui.Button(
                label='Balance', 
                emoji='💰', 
                style=discord.ButtonStyle.primary
            )
            toggle_btn.callback = self.toggle_economy_callback
        
        self.add_item(toggle_btn)
        
        # Дараагийн хуудас
        next_btn = discord.ui.Button(
            label='▶️', 
            style=discord.ButtonStyle.secondary,
            disabled=(self.page == self.total_pages)
        )
        next_btn.callback = self.next_page_callback
        self.add_item(next_btn)
        
        # Сүүлийн хуудас
        last_btn = discord.ui.Button(
            label='⏭️', 
            style=discord.ButtonStyle.secondary,
            disabled=(self.page == self.total_pages)
        )
        last_btn.callback = self.last_page_callback
        self.add_item(last_btn)
    
    async def first_page_callback(self, interaction: discord.Interaction) -> None:
        self.page = 1
        await self.update_embed(interaction)
    
    async def prev_page_callback(self, interaction: discord.Interaction) -> None:
        if self.page > 1:
            self.page -= 1
        await self.update_embed(interaction)
    
    async def toggle_economy_callback(self, interaction: discord.Interaction) -> None:
        self.table = "economy"
        self.page = 1
        await self.recalculate_and_update(interaction)
    
    async def toggle_bank_callback(self, interaction: discord.Interaction) -> None:
        self.table = "bank"
        self.page = 1
        await self.recalculate_and_update(interaction)
    
    async def next_page_callback(self, interaction: discord.Interaction) -> None:
        if self.page < self.total_pages:
            self.page += 1
        await self.update_embed(interaction)
    
    async def last_page_callback(self, interaction: discord.Interaction) -> None:
        self.page = self.total_pages
        await self.update_embed(interaction)
    
    
    async def recalculate_and_update(self, interaction: discord.Interaction) -> None:
        """Table сольж, нийт хуудасны тоог дахин тооцоолох"""
        try:
            users, total_count = await self.economy_cog.get_top_users(self.guild, self.table, self.page)
            self.total_pages = max(1, (total_count + 9) // 10)
            embed = self.economy_cog.create_top_embed(self.guild, users, self.page, self.total_pages, self.table)
            self._setup_buttons()  # Button-уудыг дахин тохируулах
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            await interaction.response.send_message("⚠️ Алдаа гарлаа!", ephemeral=True)
    
    async def update_embed(self, interaction: discord.Interaction) -> None:
        """Embed-ийг шинэчлэх"""
        try:
            users, _ = await self.economy_cog.get_top_users(self.guild, self.table, self.page)
            embed = self.economy_cog.create_top_embed(self.guild, users, self.page, self.total_pages, self.table)
            self._setup_buttons()  # Button-уудыг дахин тохируулах
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            await interaction.response.send_message("⚠️ Алдаа гарлаа!", ephemeral=True)
    
    async def on_timeout(self) -> None:
        """Timeout болоход button-уудыг идэвхгүй болгох"""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    def cog_check(self, ctx: commands.Context) -> bool:
        # Only allow commands in guilds; channel enable check must be async elsewhere
        if not ctx.guild:
            return False
        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        # Async channel check here
        if ctx.guild is None or not await is_channel_enabled(ctx.guild.id, ctx.channel.id):
            await ctx.send("Энэ channel-д команд ашиглах боломжгүй!")
            raise commands.CheckFailure("Channel not enabled for commands.")

def setup(bot: commands.Bot):
    return bot.loop.create_task(bot.add_cog(Economy(bot)))