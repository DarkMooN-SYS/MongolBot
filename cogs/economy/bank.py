import re
import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime, timedelta
from typing import Optional, Union, Any, List, Tuple, NoReturn
from ..utils.database import get_async_connection
from ..utils.rate_limit_decorators import rate_limit_command  # Rate limiting import
import aiosqlite
import os
import asyncio
from ..utils.channel import is_channel_enabled

# Set up logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s", 
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

def parse_datetime(date_str: str):
    """Бутархай секундтэй болон секундгүй datetime-г зөв хөрвүүлэх"""
    if date_str is None:
        return None  # `None` бол `None` буцаана.

    if "." in date_str:
        date_str = date_str.split(".")[0]  # ✅ Бутархай секундийг арилгах

    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")  # ✅ Бүхэл секунд болгон хөрвүүлэх
    except ValueError:
        return None  # 🔹 Хэрэв ямар нэгэн асуудал гарвал `None` буцаана.

class Bank(commands.Cog):
    from typing import Any

    def __init__(self, bot: commands.Bot, vip_cog: Any):
        self.bot = bot
        self.vip_cog = vip_cog
        self.conn: Optional[aiosqlite.Connection] = None
        self.bot.loop.create_task(self.setup_database())
        self.savings_interest_rate = 0.02  # 14 хоног тутмын хадгаламжийн хүү (2%)
        self.loan_interest_rate = 0.05  # 7 хоног тутмын зээлийн хүү (5%)
    async def setup_database(self) -> None:
        print("🏦 Bank систем setup эхлэж байна...")  # Print шууд console-д гарах
        logger.info("🏦 Bank систем setup эхлэж байна...")
        self.conn = await get_async_connection('economy')
        await self.conn.execute("PRAGMA journal_mode=WAL;")
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bank (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS economy (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS savings (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                hadgalamj_date TEXT,
                due_date TEXT
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS loans (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                zeel_date TEXT,
                due_date TEXT,
                perma_block INTEGER DEFAULT 0 -- Зээлийн эрхийг бүр мөсөн хаах тэмдэглэгээ
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS last_interest (
                type TEXT PRIMARY KEY,
                last_date TEXT  -- ✅ Бутархайгүй `YYYY-MM-DD HH:MM:SS` форматаар хадгалах
            )
        """)
        await self.ensure_connection()
        await self.conn.commit()

        # --- loans хүснэгтэд perma_block багана байхгүй бол автоматаар нэмэх (минимал код) ---
        try:
            print("🔍 loans хүснэгтийн perma_block баганыг шалгаж байна...")  # Print шууд console-д гарах
            logger.info("🔍 loans хүснэгтийн perma_block баганыг шалгаж байна...")
            # Хүснэгтийн бүтцийг шалгаж perma_block багана байхгүй бол нэмэх
            async with self.conn.execute("PRAGMA table_info(loans)") as cursor:
                rows = await cursor.fetchall()
                columns = [row[1] for row in rows]
                print(f"📋 loans хүснэгтийн бүх багануud: {columns}")  # Print шууд console-д гарах
                logger.info(f"📋 loans хүснэгтийн бүх багануud: {columns}")
                
            if "perma_block" not in columns:
                print("➕ perma_block багана байхгүй тул нэмэж байна...")  # Print шууд console-д гарах
                logger.info("➕ perma_block багана байхгүй тул нэмэж байна...")
                await self.conn.execute("ALTER TABLE loans ADD COLUMN perma_block INTEGER DEFAULT 0")
                await self.conn.commit()
                print("✅ perma_block багана амжилттай нэмэгдлээ")  # Print шууд console-д гарах
                logger.info("✅ perma_block багана амжилттай нэмэгдлээ")
            else:
                print("ℹ️ perma_block багана аль хэдийн байна")  # Print шууд console-д гарах
                logger.info("ℹ️ perma_block багана аль хэдийн байна")
                
        except Exception as e:
            print(f"❌ perma_block багана нэмэхэд алдаа: {e}")  # Print шууд console-д гарах
            logger.error(f"❌ perma_block багана нэмэхэд алдаа: {e}")
        
        print("✅ Bank database setup бүрэн дууслаа")  # Print шууд console-д гарах
        logger.info("✅ Bank database setup бүрэн дууслаа")

    async def ensure_connection(self) -> None:
        if self.conn is None:
            await self.setup_database()
        if self.conn is None:
            raise RuntimeError("Database connection is not established!")

    async def get_balance(self, user_id: int, table_name: str) -> int:
        async with aiosqlite.connect('data/economy.db') as conn:
            async with conn.execute(f"SELECT balance FROM {table_name} WHERE user_id=?", (user_id,)) as cursor:
                result = await cursor.fetchone()
                return int(result[0]) if result and result[0] is not None else 0

    async def update_balance(self, table_name: str, user_id: int, amount: int, date_column: Optional[str] = None, due_date: Optional[str] = None):
        async with aiosqlite.connect('data/economy.db') as conn:
            # Get current balance within the same connection
            async with conn.execute(f"SELECT balance FROM {table_name} WHERE user_id=?", (user_id,)) as cursor:
                result = await cursor.fetchone()
                current_balance = int(result[0]) if result and result[0] is not None else 0
            
            new_balance = current_balance + amount
            if new_balance < 0:
                return current_balance
            
            if date_column:
                await conn.execute(f'''
                    INSERT INTO {table_name} (user_id, balance, {date_column}, due_date)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET balance = ?, {date_column} = ?, due_date = COALESCE(?, due_date)
                ''', (user_id, new_balance, datetime.now().strftime("%Y-%m-%d"), due_date, new_balance, datetime.now().strftime("%Y-%m-%d"), due_date))
            else:
                await conn.execute(f'''
                    INSERT INTO {table_name} (user_id, balance)
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET balance = ?
                ''', (user_id, new_balance, new_balance))
            await conn.commit()
            return new_balance

    async def get_max_loan_for_user(self, user_id: int) -> int:
        """VIP хэрэглэгчийн зээлийн дээд хэмжээг авах"""
        if self.vip_cog and hasattr(self.vip_cog, "get_max_loan_for_user"):
            return await self.vip_cog.get_max_loan_for_user(user_id)
        return 1_000_000  # Default max loan

    async def get_loan_interest_rate_for_user(self, user_id: int) -> float:
        """VIP хэрэглэгчийн зээлийн хүүгийн хувийг авах"""
        if self.vip_cog and hasattr(self.vip_cog, "get_loan_interest_rate_for_user"):
            return await self.vip_cog.get_loan_interest_rate_for_user(user_id)
        return 0.05  # Default interest rate 5%



    def number(self, number_str: str) -> Union[int, str]:
        if not isinstance(number_str, str):
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

    async def check_account_and_send_message(self, ctx: commands.Context):
        await self.ensure_connection()
        if not self.conn:
            raise RuntimeError("Database connection is not established!")
        async with self.conn.execute("SELECT 1 FROM bank WHERE user_id=?", (ctx.author.id,)) as cursor:
            result = await cursor.fetchone()
            if result is None:
                await ctx.send("⚠️ Таны данс байхгүй байна. mbank командаар үүсгэнэ үү!")
                return False
        return True

    def cog_check(self, ctx: commands.Context) -> bool:
        # Synchronous check: only check if in a guild, async checks must be done in before_invoke
        if not ctx.guild:
            return False
        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        # Async channel check and message sending
        if not ctx.guild or not await is_channel_enabled(ctx.guild.id, ctx.channel.id):
            await ctx.send("Энэ channel-д команд ашиглах боломжгүй!")
            raise commands.CheckFailure("Channel not enabled for commands.")

    # Bank Commands
    @commands.command(name="bank")
    @commands.cooldown(1, 10, commands.BucketType.user)
    @rate_limit_command()  # Global rate limiting нэмэх
    async def bank(self, ctx: commands.Context, user: Optional[discord.Member] = None) -> None:
        """Хэрэглэгчийн банкны мэдээллийг харуулах
        
        Args:
            ctx (commands.Context): Команд контекст
            user (Optional[discord.Member]): Мэдээлэл харах хэрэглэгч
        """

        # Хэрэглэгчийг тодорхойлох
        target_user = user if user else ctx.author
        if not isinstance(target_user, discord.Member) and ctx.guild:
            target_user = ctx.guild.get_member(target_user.id) or ctx.author

        # Үндсэн үлдэгдлүүдийг авах
        bank_balance = await self.get_balance(target_user.id, "bank")
        savings_balance = await self.get_balance(target_user.id, "savings")
        loan_balance = await self.get_balance(target_user.id, "loans")

        # Өнгөний код 
        colors = {
            "positive": 0x2ecc71,  # Ногоон өнгө
            "negative": 0xe74c3c,  # Улаан өнгө
            "neutral": 0x3498db    # Цэнхэр өнгө
        }

        embed = discord.Embed(
            title=f"🏦 {target_user.display_name}-ийн Банкны Мэдээлэл",
            description="Таны санхүүгийн бүх мэдээлэл энд байна",
            color=colors["neutral"]
        )

        # Үндсэн балансын хэсэг
        embed.add_field(
            name="💎 Дансны үлдэгдэл",
            value=f"```py\n{bank_balance:,} ₮```",
            inline=False
        )        # Хадгаламж ба зээлийн мэдээлэл
        # VIP түвшин шалгах (хүчинтэй VIP эрх байгаа эсэхийг)
        vip_status = ""
        if self.vip_cog and hasattr(self.vip_cog, "check_vip"):
            is_vip_active = await self.vip_cog.check_vip(target_user.id)
            if is_vip_active:
                vip_level = await self.vip_cog.get_vip_level(target_user.id)
                if vip_level:
                    vip_status = f"\n🎭 VIP {vip_level} эрх"
        
        financial_status = (
            f"📈 Хадгаламж: {savings_balance:,} ₮\n"
            f"📉 Зээл: -{loan_balance:,} ₮\n"
            f"📊 Нийт: {bank_balance + savings_balance - loan_balance:,} ₮{vip_status}"
        )
        embed.add_field(
            name="💰 Санхүүгийн тойм",
            value=f"```py\n{financial_status}```",
            inline=False
        )

        # Үндсэн үйлдлүүд
        basic_commands = (
            "🟢 **Орлого**: `mdeposit <дүн>` эсвэл `mdep <дүн>`\n"
            "🔴 **Зарлага**: `mwithdraw <дүн>` эсвэл `mwit <дүн>`\n"
            "💰 **Үлдэгдэл**: `mbalance` эсвэл `mbal`"
        )
        embed.add_field(
            name="📱 Үндсэн үйлдлүүд",
            value=basic_commands,
            inline=False
        )

        # Хадгаламжийн үйлчилгээ
        savings_info = (
            "💾 **Хадгалах**: `msave <дүн>`\n"
            "📤 **Авах**: `mwitsave <дүн>`\n"
            "💹 Хүү: 14 хоног тутамд 2%"
        )
        embed.add_field(
            name="🏦 Хадгаламжийн үйлчилгээ",
            value=savings_info,
            inline=True
        )        # Зээлийн үйлчилгээ (VIP мэдээлэл оруулах)
        max_loan = await self.get_max_loan_for_user(target_user.id)
        interest_rate = await self.get_loan_interest_rate_for_user(target_user.id)
        
        # VIP түвшин шалгах (хүчинтэй VIP эрх байгаа эсэхийг)
        vip_info = ""
        if self.vip_cog and hasattr(self.vip_cog, "check_vip"):
            is_vip_active = await self.vip_cog.check_vip(target_user.id)
            if is_vip_active:
                vip_level = await self.vip_cog.get_vip_level(target_user.id)
                if vip_level:
                    vip_info = f" (VIP {vip_level})"

        # --- NEW: Check overdue loan for current user ---
        overdue_loan_block = False
        overdue_loan_msg = ""
        if target_user.id == ctx.author.id:
            await self.ensure_connection()
            if self.conn is not None:
                async with self.conn.execute("SELECT due_date, balance, perma_block FROM loans WHERE user_id=?", (target_user.id,)) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0]:
                        try:
                            due_date = datetime.strptime(row[0], "%Y-%m-%d")
                            loan_balance = row[1] if row[1] is not None else 0
                            perma_block = row[2] if len(row) > 2 else 0
                            if perma_block == 1:
                                overdue_loan_block = True
                                overdue_loan_msg = "\n❌ Та өмнө нь зээлийн хугацаа хэтрүүлсэн тул дахин зээл авах боломжгүй! Админтай холбогдоно уу."
                            elif due_date < datetime.now() and loan_balance > 0:
                                overdue_loan_block = True
                                overdue_loan_msg = "\n❌ Та өмнөх зээлийн хугацаандаа төлөөгүй тул дахин зээл авах боломжгүй! Эхлээд зээлээ бүрэн төлнө үү."
                        except Exception:
                            pass
        # --- END NEW ---

        loan_info = (
            f"💸 **Зээл авах**: `mloan <дүн>`\n"
            f"💳 **Төлөх**: `mpayloan <дүн>`\n"
            f"💰 **Дээд хэмжээ**: {max_loan:,}₮{vip_info}\n"
            f"📊 **Хүү**: 7 хоног тутамд {interest_rate*100:.1f}%"
        )
        if overdue_loan_block:
            loan_info += overdue_loan_msg
        embed.add_field(
            name="💳 Зээлийн үйлчилгээ",
            value=loan_info,
            inline=True
        )

        embed.set_footer(text="💡 Нарийвчилсан мэдээлэл авахын тулд mhelp bank гэж бичнэ үү!")
        # Avatar зургийг аюулгүй байдлаар оруулах
        avatar_url = None
        if hasattr(target_user, "avatar") and target_user.avatar:
            avatar_url = target_user.avatar.url
        elif hasattr(target_user, "default_avatar"):
            avatar_url = target_user.default_avatar.url

        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        await ctx.send(embed=embed)

    @commands.command(name='deposit', aliases=['dep'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def deposit(self, ctx: commands.Context, amount: str) -> None:
        """Дансанд мөнгө хийх
        
        Args:
            ctx (commands.Context): Команд контекст
            amount (str): Хийх мөнгөний хэмжээ
        """

        converted_amount = self.number(amount)
        if isinstance(converted_amount, str):
            await ctx.send(converted_amount)
            return
            
        if converted_amount <= 0:
            await ctx.send("⚠️ Таны оруулсан хэмжээ хүчинтэй тоо биш байна!")
            return

        try:
            author_balance = await self.get_balance(ctx.author.id, "economy")

            if converted_amount > author_balance:
                await ctx.send("⚠️ Таны мөнгө хүрэхгүй байна!")
                return

            # Шууд татваргүй шилжүүлнэ
            await self.update_balance("economy", ctx.author.id, -converted_amount)
            await self.update_balance("bank", ctx.author.id, converted_amount)

            await ctx.send(f"✅ {converted_amount:,} төгрөг таны банкны дансанд орлоо!")

        except Exception as e:
            logging.error(f"Error during deposit: {e}")
            await ctx.send("⚠️ Банкны системд алдаа гарлаа.")

    @commands.command(name='withdraw', aliases=['wit'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def withdraw(self, ctx: commands.Context, amount: str) -> None:
        """Данснаас мөнгө авах
        
        Args:
            ctx (commands.Context): Команд контекст
            amount (str): Авах мөнгөний хэмжээ
        """

        converted_amount = self.number(amount)
        if isinstance(converted_amount, str):
            await ctx.send(converted_amount)
            return
            
        if converted_amount <= 0:
            await ctx.send("⚠️ Таны оруулсан хэмжээ хүчинтэй тоо биш байна!")
            return

        try:
            bank_balance = await self.get_balance(ctx.author.id, "bank")

            if converted_amount > bank_balance:
                await ctx.send("⚠️ Таны дансны үлдэгдэл хүрэлцэхгүй байна!")
                return

            # Шууд татваргүйгээр
            await self.update_balance("bank", ctx.author.id, -converted_amount)
            await self.update_balance("economy", ctx.author.id, converted_amount)

            await ctx.send(f"✅ {converted_amount:,} төгрөг таны халаасанд орлоо!")

        except Exception as e:
            logging.error(f"Error during withdrawal: {e}")
            await ctx.send("⚠️ Системд алдаа гарлаа.")

    @commands.command(name="save")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def save(self, ctx: commands.Context, amount: str) -> Optional[NoReturn]:
        """Хадгаламжинд мөнгө хийх
        
        Args:
            ctx (commands.Context): Команд контекст
            amount (str): Хийх мөнгөний хэмжээ
        """

        converted_amount = self.number(amount)
        if isinstance(converted_amount, str):
            await ctx.send(converted_amount)
            return None
            
        if converted_amount <= 0:
            await ctx.send("⚠️ Хадгаламжинд хийх мөнгө 0-с их байх ёстой!")
            return None
        try:
            bank_balance = await self.get_balance(ctx.author.id, "bank")
            if bank_balance < converted_amount:
                await ctx.send("⚠️ Таны банкны үлдэгдэл хүрэлцэхгүй байна!")
                return None

            await self.update_balance("bank", ctx.author.id, -converted_amount)
            await self.update_balance("savings", ctx.author.id, converted_amount, "hadgalamj_date")
            await ctx.send(f"✅ **{converted_amount:,}₮** хадгаламжинд нэмэгдлээ!")
            return None

        except Exception as e:
            logging.error(f"Error during save: {e}")
            await ctx.send("⚠️ Хадгаламжийн системд алдаа гарлаа.")
            return None

    @commands.command(name='witsave', aliases=['ws'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def withdrawsave(self, ctx: commands.Context, amount: str) -> None:
        """Хадгаламжаас мөнгө авах
        
        Args:
            ctx (commands.Context): Команд контекст
            amount (str): Авах мөнгөний хэмжээ
        """

        converted_amount = self.number(amount)
        if isinstance(converted_amount, str):
            await ctx.send(converted_amount)
            return
            
        if converted_amount <= 0:
            await ctx.send("⚠️ Хадгаламжаас авах мөнгө 0-с их байх ёстой!")
            return None

        savings_balance = await self.get_balance(ctx.author.id, "savings")
        if savings_balance < converted_amount:
            await ctx.send("⚠️ Таны хадгаламжинд хангалттай мөнгө байхгүй байна!")
            return None

        await self.update_balance("savings", ctx.author.id, -converted_amount)
        await self.update_balance("bank", ctx.author.id, converted_amount)
        await ctx.send(f"✅ **{converted_amount:,}₮** хадгаламжаас татлаа!")

    @commands.command(name="loan")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def loan(self, ctx: commands.Context, amount: str) -> None:
        """Зээл авах
        
        Args:
            ctx (commands.Context): Команд контекст
            amount (str): Зээлийн хэмжээ
        """

        converted_amount = self.number(amount)
        if isinstance(converted_amount, str):
            await ctx.send(converted_amount)
            return
            
        if converted_amount < 10000:
            await ctx.send("⚠️ Зээлийн хамгийн бага хэмжээ 10,000₮ байна!")
            return

        current_loan = await self.get_balance(ctx.author.id, "loans")
        max_loan = await self.get_max_loan_for_user(ctx.author.id)  # Get max loan for user

        # --- STRICT: Check if user has overdue loan or perma_block ---
        await self.ensure_connection()
        if self.conn is None:
            await ctx.send("⚠️ Мэдээллийн сантай холбогдож чадсангүй. Дахин оролдоно уу.")
            return
        async with self.conn.execute("SELECT due_date, balance, perma_block FROM loans WHERE user_id=?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                try:
                    # --- Тайлбар: due_date-г datetime болгож хөрвүүлнэ ---
                    due_date = datetime.strptime(row[0], "%Y-%m-%d")
                    loan_balance = row[1] if row[1] is not None else 0
                    perma_block = row[2] if len(row) > 2 else 0
                    # --- Тайлбар: Хэрвээ өмнө нь perma_block тавигдсан бол шууд хориглоно ---
                    if perma_block == 1:
                        await ctx.send("❌ Та өмнө нь зээлийн хугацаа хэтрүүлсэн тул дахин зээл авах боломжгүй! Админтай холбогдоно уу.")
                        return
                    # --- Тайлбар: Хэрвээ due_date өнөөдрөөс өмнө бол зээл авах боломжгүй ---
                    if due_date < datetime.now() and loan_balance > 0:
                        await ctx.send("❌ Таны өмнөх зээлийн хугацаа хэтэрсэн тул дахин зээл авах боломжгүй! Эхлээд өмнөх зээлээ төлнө үү эсвэл админтай холбогдоно уу.")
                        return
                except Exception:
                    pass
        # --- END STRICT ---

        if current_loan + converted_amount > max_loan:
            # VIP түвшинг харуулах (хүчинтэй VIP эрх байгаа эсэхийг)
            vip_info = ""
            if self.vip_cog and hasattr(self.vip_cog, "check_vip"):
                is_vip_active = await self.vip_cog.check_vip(ctx.author.id)
                if is_vip_active:
                    vip_level = await self.vip_cog.get_vip_level(ctx.author.id)
                    if vip_level:
                        vip_info = f" (VIP {vip_level} эрх)"
            await ctx.send(f"⚠️ Хамгийн ихдээ {max_loan:,}₮ зээл авах боломжтой{vip_info}!")
            return

        # --- Хадгаламжийн шалгуур: Зээл авахын тулд зээлийн 10%-тай тэнцэх хадгаламжтай байх ---
        savings_balance = await self.get_balance(ctx.author.id, "savings")
        required_savings = int(converted_amount * 0.10)
        if savings_balance < required_savings:
            await ctx.send(f"❌ Та {converted_amount:,}₮ зээл авахын тулд дор хаяж {required_savings:,}₮ хадгаламжид байршуулах шаардлагатай!")
            return

        due_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        interest_rate = await self.get_loan_interest_rate_for_user(ctx.author.id)  # Get interest rate for user
        await self.update_balance("bank", ctx.author.id, converted_amount)
        await self.update_balance("loans", ctx.author.id, converted_amount, "zeel_date", due_date)
        
        # VIP түвшин болон тусгай хүүгийн мэдээлэл харуулах (хүчинтэй VIP эрх байгаа эсэхийг)
        vip_message = ""
        if self.vip_cog and hasattr(self.vip_cog, "check_vip"):
            is_vip_active = await self.vip_cog.check_vip(ctx.author.id)
            if is_vip_active:
                vip_level = await self.vip_cog.get_vip_level(ctx.author.id)
                if vip_level:
                    vip_message = f"\n🎭 VIP {vip_level} эрхээр {interest_rate*100:.1f}% хүүтэй!"
        
        await ctx.send(f"✅ **{converted_amount:,}₮** зээл авлаа! Төлөх хугацаа: {due_date}{vip_message}")

    @commands.command(name="payloan")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def payloan(self, ctx: commands.Context, amount: str) -> None:
        """Зээл төлөх
        
        Args:
            ctx (commands.Context): Команд контекст
            amount (str): Төлөх мөнгөний хэмжээ
        """

        converted_amount = self.number(amount)
        if isinstance(converted_amount, str):
            await ctx.send(converted_amount)
            return
            
        if converted_amount <= 0:
            await ctx.send("⚠️ Төлөх зээлийн хэмжээ 0-с их байх ёстой!")
            return

        bank_balance = await self.get_balance(ctx.author.id, "bank")
        if bank_balance < converted_amount:
            await ctx.send("⚠️ Таны банкны үлдэгдэл хүрэлцэхгүй байна!")
            return None

        current_loan = await self.get_balance(ctx.author.id, "loans")
        if current_loan == 0:
            await ctx.send("⚠️ Танд төлөх зээл байхгүй байна!")
            return
            
        final_amount = min(converted_amount, current_loan)

        await self.update_balance("bank", ctx.author.id, -final_amount)
        await self.update_balance("loans", ctx.author.id, -final_amount)
        await ctx.send(f"✅ **{final_amount:,}₮** зээлийн төлбөр хийлээ!")
        
    async def cog_unload(self) -> None:
        # Эхлээд interest loop-уудыг зогсооно
        try:
            self.process_loan_interest.cancel()
        except Exception:
            pass
        try:
            self.process_savings_interest.cancel()
        except Exception:
            pass
        try:
            self.process_overdue_loans.cancel()
        except Exception:
            pass
        # Дараа нь холболтыг хаана
        if self.conn:
            await self.conn.close()
            self.conn = None
            logger.info("✅ Мэдээллийн сан амжилттай хаагдлаа.")

    async def get_last_interest_date(self, interest_type: str) -> Optional[datetime]:
        await self.ensure_connection()
        if not self.conn:
            raise RuntimeError("Database connection is not established!")
        async with self.conn.execute("SELECT last_date FROM last_interest WHERE type = ?", (interest_type,)) as cursor:
            result = await cursor.fetchone()
            if result and result[0]:
                return parse_datetime(result[0])
        return None

    async def set_last_interest_date(self, interest_type: str) -> None:
        await self.ensure_connection()
        if not self.conn:
            raise RuntimeError("Database connection is not established!")
        today = datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        await self.conn.execute("""
            INSERT INTO last_interest (type, last_date)
            VALUES (?, ?)
            ON CONFLICT(type) DO UPDATE SET last_date = excluded.last_date
        """, (interest_type, today))
        await self.conn.commit()

    @tasks.loop(hours=168)
    async def process_loan_interest(self) -> None:
        await self.bot.wait_until_ready()
        await self.ensure_connection()
        if not self.conn:
            raise RuntimeError("Database connection is not established!")
        
        last_date = await self.get_last_interest_date("loan")
        today = datetime.now()
        if last_date and (today - last_date).days < 7:
            logger.info("⚠️ Зээлийн хүү тооцох хугацаа болоогүй байна!")
            return
        
        async with self.conn.execute("SELECT user_id, balance FROM loans") as cursor:
            rows = await cursor.fetchall()
            for user_id, balance in rows:
                # VIP хэрэглэгчийн тусгай хүүгийн хувийг ашиглах
                user_interest_rate = await self.get_loan_interest_rate_for_user(user_id)
                interest = int(balance * user_interest_rate)
                await self.conn.execute(
                    "UPDATE loans SET balance = balance + ? WHERE user_id = ?",
                    (interest, user_id)
                )
        await self.set_last_interest_date("loan")
        await self.conn.commit()
        logger.info("✅ Зээлийн хүү тооцооллоо!")

    @tasks.loop(hours=336)
    async def process_savings_interest(self) -> None:
        await self.bot.wait_until_ready()
        await self.ensure_connection()
        if not self.conn:
            raise RuntimeError("Database connection is not established!")
        last_date = await self.get_last_interest_date("savings")
        today = datetime.now()
        if last_date and (today - last_date).days < 14:
            logger.info("⚠️ Хадгаламжийн хүү тооцох хугацаа болоогүй байна!")
            return
        async with self.conn.execute("SELECT user_id, balance FROM savings") as cursor:
            rows = await cursor.fetchall()
            for user_id, balance in rows:
                interest = int(balance * self.savings_interest_rate)
                await self.conn.execute(
                    "UPDATE savings SET balance = balance + ? WHERE user_id = ?",
                    (interest, user_id)
                )
        await self.set_last_interest_date("savings")
        await self.conn.commit()
        logger.info("✅ Хадгаламжийн хүү тооцооллоо!")

    @tasks.loop(hours=1)
    async def process_overdue_loans(self) -> None:
        """Зээлийн хугацаа хэтэрсэн хэрэглэгчдийг 1 цаг тутамд автоматаар шалгаж, мөнгийг суутгана."""
        try:
            async with aiosqlite.connect('data/economy.db') as conn:
                async with conn.execute("SELECT user_id, due_date, balance, perma_block FROM loans WHERE balance > 0 AND due_date IS NOT NULL") as cursor:
                    rows = await cursor.fetchall()
                for row in rows:
                    user_id, due_date_str, loan_balance, perma_block = row
                    if perma_block == 1:
                        continue
                    try:
                        due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
                    except Exception:
                        continue
                    if due_date < datetime.now():
                        # --- Банк, халаас, хадгаламжийн одоогийн үлдэгдлийг авах ---
                        bank_balance = 0
                        economy_balance = 0
                        savings_balance = 0
                        async with conn.execute("SELECT balance FROM bank WHERE user_id=?", (user_id,)) as c:
                            r = await c.fetchone()
                            if r and r[0] is not None:
                                bank_balance = int(r[0])
                        async with conn.execute("SELECT balance FROM economy WHERE user_id=?", (user_id,)) as c:
                            r = await c.fetchone()
                            if r and r[0] is not None:
                                economy_balance = int(r[0])
                        async with conn.execute("SELECT balance FROM savings WHERE user_id=?", (user_id,)) as c:
                            r = await c.fetchone()
                            if r and r[0] is not None:
                                savings_balance = int(r[0])
                        
                        # --- Зөвхөн эерэг үлдэгдэлтэй данснаас суутгах ---
                        remaining_loan = loan_balance
                        deduct_from_bank = 0
                        deduct_from_economy = 0
                        deduct_from_savings = 0
                        
                        # Эхлээд банкнаас суутгах
                        if bank_balance > 0 and remaining_loan > 0:
                            deduct_from_bank = min(bank_balance, remaining_loan)
                            remaining_loan -= deduct_from_bank
                        
                        # Дараа нь халааснаас суутгах
                        if economy_balance > 0 and remaining_loan > 0:
                            deduct_from_economy = min(economy_balance, remaining_loan)
                            remaining_loan -= deduct_from_economy
                        
                        # Эцэст хадгаламжаас суутгах
                        if savings_balance > 0 and remaining_loan > 0:
                            deduct_from_savings = min(savings_balance, remaining_loan)
                            remaining_loan -= deduct_from_savings
                        
                        # Нийт суутгасан дүн
                        deducted = deduct_from_bank + deduct_from_economy + deduct_from_savings
                        # update_balance-ийг дуудахын оронд шууд UPDATE хийнэ
                        if deduct_from_bank > 0:
                            await conn.execute("UPDATE bank SET balance = balance - ? WHERE user_id = ?", (deduct_from_bank, user_id))
                        if deduct_from_economy > 0:
                            await conn.execute("UPDATE economy SET balance = balance - ? WHERE user_id = ?", (deduct_from_economy, user_id))
                        if deduct_from_savings > 0:
                            await conn.execute("UPDATE savings SET balance = balance - ? WHERE user_id = ?", (deduct_from_savings, user_id))
                        if deducted > 0:
                            await conn.execute("UPDATE loans SET balance = balance - ? WHERE user_id = ?", (deducted, user_id))
                        # --- Одоо perma_block-г 1 болгож тэмдэглэнэ ---
                        await conn.execute("UPDATE loans SET perma_block=1 WHERE user_id=?", (user_id,))
                        await conn.commit()
                        
                        # --- Хэрэглэгчдэд DM мэдэгдэл илгээх ---
                        try:
                            user = self.bot.get_user(user_id)
                            if user:
                                embed = discord.Embed(
                                    title="🚨 Зээлийн төлбөр автоматаар суутгалаа",
                                    description="Таны зээлийн хугацаа хэтрсэн тул автоматаар мөнгө суутгалаа.",
                                    color=0xe74c3c  # Улаан өнгө
                                )
                                embed.add_field(
                                    name="💰 Суутгасан дүн",
                                    value=f"{deducted:,}₮",
                                    inline=True
                                )
                                embed.add_field(
                                    name="📅 Огноо",
                                    value=datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    inline=True
                                )
                                embed.add_field(
                                    name="📊 Суутгасан эх үүсвэр",
                                    value=(
                                        f"🏦 Банк: {deduct_from_bank:,}₮\n"
                                        f"💰 Халаас: {deduct_from_economy:,}₮\n"
                                        f"💎 Хадгаламж: {deduct_from_savings:,}₮"
                                    ),
                                    inline=False
                                )
                                embed.add_field(
                                    name="⚠️ Анхааруулга",
                                    value="Та дахин зээл авах боломжгүй болсон. Админтай холбогдоно уу.",
                                    inline=False
                                )
                                embed.set_footer(text="MongolBot Banking System")
                                await user.send(embed=embed)
                                logger.info(f"✅ User {user_id}-д зээлийн суутгалын мэдэгдэл илгээлээ")
                        except Exception as dm_error:
                            logger.warning(f"⚠️ User {user_id}-д DM илгээж чадсангүй: {dm_error}")
        except Exception as e:
            logger.error(f"process_overdue_loans алдаа: {e}")

    # --- END: process_overdue_loans ---

    async def start_interest_loops(self) -> None:
        await self.ensure_connection()
        if not self.conn:
            raise RuntimeError("Database connection is not established!")
        today = datetime.now()
        last_loan_interest = await self.get_last_interest_date("loan")
        if last_loan_interest and (today - last_loan_interest).days >= 7:
            await self.process_loan_interest()
        self.process_loan_interest.start()
        last_savings_interest = await self.get_last_interest_date("savings")
        if last_savings_interest and (today - last_savings_interest).days >= 14:
            await self.process_savings_interest()
        self.process_savings_interest.start()
        # --- Шинэ: хугацаа хэтэрсэн зээлийг автоматаар шалгах loop ---
        self.process_overdue_loans.start()

    @commands.command(name="unloan", aliases=['unblock_loan'])
    @commands.is_owner()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def unblock_loan(self, ctx: commands.Context, user: discord.Member) -> None:
        """Owner команд: Хэрэглэгчийн зээлийн perma_block-г арилгах

        Args:
            ctx (commands.Context): Команд контекст
            user (discord.Member): Блок арилгах хэрэглэгч
        """

        await self.ensure_connection()
        if self.conn is None:
            await ctx.send("⚠️ Мэдээллийн сантай холбогдож чадсангүй. Дахин оролдоно уу.")
            return

        try:
            # Хэрэглэгчийн одоогийн зээлийн мэдээллийг шалгах
            async with self.conn.execute("SELECT balance, perma_block FROM loans WHERE user_id=?", (user.id,)) as cursor:
                row = await cursor.fetchone()
                
                if not row:
                    await ctx.send(f"❌ {user.display_name}-д зээлийн бичлэг байхгүй байна.")
                    return
                
                loan_balance, perma_block = row
                
                if perma_block != 1:
                    await ctx.send(f"ℹ️ {user.display_name}-д perma_block байхгүй байна.")
                    return
                
                # Perma_block-г арилгах
                await self.conn.execute("UPDATE loans SET perma_block=0 WHERE user_id=?", (user.id,))
                await self.conn.commit()
                
                # Амжилттай мэдээлэл
                embed = discord.Embed(
                    title="✅ Зээлийн эрх сэргээгдлээ",
                    description=f"{user.display_name}-ийн зээлийн эрх амжилттай сэргээгдлээ.",
                    color=0x2ecc71
                )
                embed.add_field(
                    name="👤 Хэрэглэгч",
                    value=user.mention,
                    inline=True
                )
                embed.add_field(
                    name="💰 Одоогийн зээлийн үлдэгдэл",
                    value=f"{loan_balance:,}₮",
                    inline=True
                )
                embed.add_field(
                    name="🔓 Статус",
                    value="Зээл авах боломжтой",
                    inline=True
                )
                embed.add_field(
                    name="👑 Owner",
                    value=ctx.author.mention,
                    inline=True
                )
                embed.add_field(
                    name="📅 Огноо",
                    value=datetime.now().strftime("%Y-%m-%d %H:%M"),
                    inline=True
                )
                embed.set_footer(text="MongolBot Banking System")
                await ctx.send(embed=embed)
                
                # Хэрэглэгчдэд DM мэдэгдэл илгээх
                try:
                    user_dm_embed = discord.Embed(
                        title="🎉 Зээлийн эрх сэргээгдлээ!",
                        description="Таны зээлийн эрх owner-оор сэргээгдлээ.",
                        color=0x2ecc71
                    )
                    user_dm_embed.add_field(
                        name="✅ Мэдээлэл",
                        value="Та одоо дахин зээл авах боломжтой боллоо!",
                        inline=False
                    )
                    if loan_balance > 0:
                        user_dm_embed.add_field(
                            name="💰 Анхааруулга",
                            value=f"Таны одоогийн зээлийн үлдэгдэл: {loan_balance:,}₮\nШинэ зээл авахын өмнө өмнөх зээлээ төлнө үү.",
                            inline=False
                        )
                    user_dm_embed.set_footer(text="MongolBot Banking System")
                    await user.send(embed=user_dm_embed)
                    logger.info(f"✅ User {user.id}-д зээлийн эрх сэргээгдсэний мэдэгдэл илгээлээ")
                except Exception as dm_error:
                    logger.warning(f"⚠️ User {user.id}-д DM илгээж чадсангүй: {dm_error}")
                    await ctx.send("⚠️ Хэрэглэгчдэд DM илгээж чадсангүй, гэхдээ блок амжилттай арилгагдлаа.")

        except Exception as e:
            logger.error(f"unblock_loan алдаа: {e}")
            await ctx.send("⚠️ Зээлийн эрх сэргээхэд алдаа гарлаа.")

    @unblock_loan.error
    async def unblock_loan_error(self, ctx: commands.Context, error: commands.CommandError):
        """Unloan командын алдаа боловсруулах"""
        if isinstance(error, commands.NotOwner):
            await ctx.send("❌ Энэ командыг зөвхөн bot owner ашиглаж болно!")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Хэрэглэгчийг дурдана уу! Жишээ: `munloan @user`")
        else:
            await ctx.send("⚠️ Командыг ажиллуулахад алдаа гарлаа.")
            logger.error(f"unblock_loan команд алдаа: {error}")

async def setup(bot: commands.Bot) -> None:
    """Setup function to add the bank cog
    
    Args:
        bot (commands.Bot): The bot instance
    """
    vip_cog = bot.get_cog("VIP")
    bank = Bank(bot, vip_cog)
    await bot.add_cog(bank)  # ⬅️ Эхлээд когийг бүрэн нэмэх
    await bank.start_interest_loops()  # ✅ Дараа нь loop-уудыг эхлүүлэх