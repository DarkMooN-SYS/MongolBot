import re
import discord
from discord.ext import commands, tasks
import sqlite3
import logging
from discord.ext.commands.cooldowns import CooldownMapping, Cooldown, BucketType
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s", 
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

def parse_datetime(date_str):
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
    def __init__(self, bot, vip_cog):
        self.bot = bot
        self.vip_cog = vip_cog  # VIP когийг энд дамжуулна
        self.conn = sqlite3.connect("economy.db", check_same_thread=False, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.c = self.conn.cursor()
        self.setup_database()
        self.cooldowns = {}
        self.savings_interest_rate = 0.02  # 14 хоног тутмын хадгаламжийн хүү (2%)
        self.loan_interest_rate = 0.05  # 7 хоног тутмын зээлийн хүү (5%)

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

    def connect_db(self):
        """SQLite мэдээллийн санг үргэлж нээлттэй байхыг баталгаажуулах"""
        try:
            self.conn.execute("SELECT 1")  # 🔹 Холболт амьд эсэхийг шалгах
        except (sqlite3.ProgrammingError, sqlite3.OperationalError):
            logger.warning("⚠️ Мэдээллийн сан дахин холбогдож байна...")
            self.conn = sqlite3.connect("economy.db", check_same_thread=False, isolation_level=None)
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.c = self.conn.cursor()

    def ensure_connection(self):
        """🔹 SQL-г ачааллах үед үргэлж нээлттэй байхыг баталгаажуулах"""
        try:
            self.conn.execute("SELECT 1")
        except (sqlite3.ProgrammingError, sqlite3.OperationalError):
            self.conn = sqlite3.connect("economy.db", check_same_thread=False, isolation_level=None)
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.c = self.conn.cursor()

    def setup_database(self):
        """Хүснэгтүүдийг зөв тохируулах."""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS bank (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS economy (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS savings (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0,
                    hadgalamj_date TEXT,
                    due_date TEXT
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS loans (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0,
                    zeel_date TEXT,
                    due_date TEXT
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS last_interest (
                    type TEXT PRIMARY KEY,
                    last_date TEXT  -- ✅ Бутархайгүй `YYYY-MM-DD HH:MM:SS` форматаар хадгалах
                )
            """)

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

    def get_last_interest_date(self, interest_type: str):
        """Сүүлийн хүү бодсон огноог авах (бутархайгүй формат)"""
        self.ensure_connection()
        self.c.execute("SELECT last_date FROM last_interest WHERE type=?", (interest_type,))
        result = self.c.fetchone()
        return parse_datetime(result[0]) if result and result[0] else None

    def set_last_interest_date(self, interest_type: str):
        """Сүүлийн хүү бодсон хугацааг хадгалах (бутархайгүй)"""
        today = datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        self.ensure_connection()
        with self.conn:
            self.conn.execute("""
                INSERT INTO last_interest (type, last_date)
                VALUES (?, ?)
                ON CONFLICT(type) DO UPDATE SET last_date = excluded.last_date
            """, (interest_type, today))

    async def check_account_and_send_message(self, ctx):
        """Check if the user has an account in the bank."""
        self.c.execute("SELECT 1 FROM bank WHERE user_id=?", (ctx.author.id,))
        if self.c.fetchone() is None:
            await ctx.send("⚠️ Таны данс байхгүй байна. mbank командаар үүсгэнэ үү!")
            return False
        return True

    def get_balance(self, user_id: int, table_name: str):
        """Хэрэглэгчийн дансны үлдэгдлийг авах"""
        self.ensure_connection()
        self.c.execute(f"SELECT balance FROM {table_name} WHERE user_id=?", (user_id,))
        result = self.c.fetchone()
        return int(result[0]) if result else 0

    def update_balance(self, table_name: str, user_id: int, amount: int, date_column: str = None, due_date: str = None):
        """Дансны үлдэгдэл шинэчлэх"""
        self.ensure_connection()
        with self.conn:
            current_balance = self.get_balance(user_id, table_name)
            new_balance = current_balance + amount
            if new_balance < 0:
                return current_balance

            if date_column:
                self.conn.execute(f"""
                    INSERT INTO {table_name} (user_id, balance, {date_column}, due_date) 
                    VALUES (?, ?, ?, ?) 
                    ON CONFLICT(user_id) DO UPDATE SET balance = ?, {date_column} = ?, due_date = COALESCE(?, due_date)
                """, (user_id, new_balance, datetime.now().strftime("%Y-%m-%d"), due_date, 
                      new_balance, datetime.now().strftime("%Y-%m-%d"), due_date))

            else:
                self.conn.execute(f"""
                    INSERT INTO {table_name} (user_id, balance) 
                    VALUES (?, ?) 
                    ON CONFLICT(user_id) DO UPDATE SET balance = ?
                """, (user_id, new_balance, new_balance))
            return new_balance

    # Bank Commands
    @commands.command(name="bank")
    async def bank(self, ctx, user: discord.Member = None):
        if not await self.check_cooldown(ctx, 'bank'):
            return
        """Хэрэглэгчийн банкны мэдээллийг харуулах."""
        user = user or ctx.author
        bank_balance = self.get_balance(user.id, "bank")
        savings_balance = self.get_balance(user.id, "savings")
        loan_balance = self.get_balance(user.id, "loans")

        embed = discord.Embed(
            title=f"💰 {user.display_name}-ийн Дансны Мэдээлэл 💰",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="💵 **Дансны дүн**",
            value=f"```🪙 {bank_balance:,} төгрөг```",
            inline=True
        )

        embed.add_field(
            name="📈 **Хадгаламжийн үлдэгдэл**",
            value=f"```💰 {savings_balance:,} ₮```",
            inline=True
        )

        embed.add_field(
            name="💳 **Зээлийн үлдэгдэл**",
            value=f"```📉 -{loan_balance:,} ₮```",
            inline=True
        )

        embed.add_field(
            name="⬇️ **Дансанд Цэнэглэлт хийх**",
            value="```mdeposit <төгрөг> болон mdep <төгрөг>```",
            inline=True
        )

        embed.add_field(
            name="💸 **Хадгаламжаас мөнгө авах**",
            value=(
                "```"
                "💳 Хадгаламжаас татах: `mwitsave <мөнгө>`\n"
                "⚠️ 30 хоног хадгалж байж хүү тооцно\n"
                "```"
            ),
            inline=True
        )

        embed.add_field(
            name="💳 **Зээл авах**",
            value=(
                "```"
                "🏦 Зээл авах: `mloan <мөнгө>`\n"
                "🕒 30 хоногийн хугацаатай, Хүү 7 хоног тутам бодогдоно (:%)\n"
                "```"
            ),
            inline=True
        )

        embed.add_field(
            name="⬆️ **Данснаас мөнгө Татах**",
            value="```mwithdraw <төгрөг> болон mwit <төгрөг>```",
            inline=True
        )

        embed.add_field(
            name="💰 **Хадгаламжинд мөнгө хийх**",
            value=(
                "```"
                "💾 Хадгаламж хийх: `msave <мөнгө>`\n"
                "🕒 Хүү 30 хоног тутам бодогдоно (2%)\n"
                "```"
            ),
            inline=True
        )

        embed.add_field(
            name="💲 **Зээл төлөх**",
            value=(
                "```"
                "💰 Зээл төлөх: `mpayloan <мөнгө>`\n"
                "⚠️ Хугацаандаа төлөхгүй бол торгуультай\n"
                "```"
            ),
            inline=True
        )

        embed.add_field(
            name="👜 **Халаасандах мөнгө шалгах**",
            value="```mbalance болон mbal```",
            inline=False
        )

        embed.set_footer(text="💡 Тушаал ашиглахын тулд зөв нэр томьёог хэрэглээрэй!")

        await ctx.send(embed=embed)

    @commands.command(name='deposit', aliases=['dep'])
    async def deposit(self, ctx, amount: str):
        if not await self.check_cooldown(ctx, 'deposit'):
            return

        amount = self.number(amount)
        if amount is None or amount <= 0:
            await ctx.send("⚠️ Таны оруулсан хэмжээ хүчинтэй тоо биш байна!")
            return

        try:
            author_balance = self.get_balance(ctx.author.id, "economy")

            if amount > author_balance:
                await ctx.send("⚠️ Таны мөнгө хүрэхгүй байна!")
                return

            # Шууд татваргүй шилжүүлнэ
            self.update_balance("economy", ctx.author.id, -amount)
            self.update_balance("bank", ctx.author.id, amount)

            await ctx.send(f"✅ {amount:,} төгрөг таны банкны дансанд орлоо!")

        except sqlite3.Error as e:
            logging.error(f"Error during deposit: {e}")
            await ctx.send("⚠️ Банкны системд алдаа гарлаа.")

    @commands.command(name='withdraw', aliases=['wit'])
    async def withdraw(self, ctx, amount: str):
        if not await self.check_cooldown(ctx, 'withdraw'):
            return

        amount = self.number(amount)
        if amount is None or amount <= 0:
            await ctx.send("⚠️ Таны оруулсан хэмжээ хүчинтэй тоо биш байна!")
            return

        try:
            bank_balance = self.get_balance(ctx.author.id, "bank")

            if amount > bank_balance:
                await ctx.send("⚠️ Таны дансны үлдэгдэл хүрэлцэхгүй байна!")
                return

            # Шууд татваргүйгээр
            self.update_balance("bank", ctx.author.id, -amount)
            self.update_balance("economy", ctx.author.id, amount)

            await ctx.send(f"✅ {amount:,} төгрөг таны халаасанд орлоо!")

        except sqlite3.Error as e:
            logging.error(f"Error during withdrawal: {e}")
            await ctx.send("⚠️ Системд алдаа гарлаа.")

    @commands.command(name="save")
    async def save(self, ctx, amount: str):
        if not await self.check_cooldown(ctx, 'save'):
            return

        amount = self.number(amount)
        if amount is None or amount <= 0:
            return await ctx.send("⚠️ Хадгаламжинд хийх мөнгө 0-с их байх ёстой!")
        if self.get_balance(ctx.author.id, "bank") < amount:
            return await ctx.send("⚠️ Таны банкны үлдэгдэл хүрэлцэхгүй байна!")

        self.update_balance("bank", ctx.author.id, -amount)
        self.update_balance("savings", ctx.author.id, amount, "hadgalamj_date")
        await ctx.send(f"✅ **{amount:,}₮** хадгаламжинд нэмэгдлээ!")

    @commands.command(name='witsave', aliases=['ws'])
    async def withdrawsave(self, ctx, amount: str):
        if not await self.check_cooldown(ctx, 'withdrawsave'):
            return
        """Хадгаламжаас мөнгө авах"""
        amount = self.number(amount)
        if amount is None or amount <= 0:
            return await ctx.send("⚠️ Хадгаламжаас авах мөнгө 0-с их байх ёстой!")
        if self.get_balance(ctx.author.id, "savings") < amount:
            return await ctx.send("⚠️ Таны хадгаламжинд хангалттай мөнгө байхгүй байна!")

        self.update_balance("savings", ctx.author.id, -amount)
        self.update_balance("bank", ctx.author.id, amount)
        await ctx.send(f"✅ **{amount:,}₮** хадгаламжаас татлаа!")

    @commands.command(name="loan")
    async def loan(self, ctx, amount: str):
        if not await self.check_cooldown(ctx, 'loan'):
            return

        amount = self.number(amount)
        if amount is None or amount < 10000:
            return await ctx.send("⚠️ Зээлийн хамгийн бага хэмжээ 10,000₮ байна!")

        current_loan = self.get_balance(ctx.author.id, "loans")
        if current_loan + amount > 1_000_000:
            return await ctx.send("⚠️ Хамгийн ихдээ 1,000,000₮ зээл авах боломжтой!")

        due_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        self.update_balance("bank", ctx.author.id, amount)
        self.update_balance("loans", ctx.author.id, amount, "zeel_date", due_date)
        await ctx.send(f"✅ **{amount:,}₮** зээл авлаа! Төлөх хугацаа: {due_date}")

    @commands.command(name="payloan")
    async def payloan(self, ctx, amount: str):
        if not await self.check_cooldown(ctx, 'payloan'):
            return
        """Зээл төлөх"""
        amount = self.number(amount)
        if amount is None or amount <= 0:
            return await ctx.send("⚠️ Төлөх зээлийн хэмжээ 0-с их байх ёстой!")
        if self.get_balance(ctx.author.id, "bank") < amount:
            return await ctx.send("⚠️ Таны банкны үлдэгдэл хүрэлцэхгүй байна!")

        current_loan = self.get_balance(ctx.author.id, "loans")
        if current_loan == 0:
            return await ctx.send("⚠️ Танд төлөх зээл байхгүй байна!")
        if amount > current_loan:
            amount = current_loan

        self.update_balance("bank", ctx.author.id, -amount)
        self.update_balance("loans", ctx.author.id, -amount)
        await ctx.send(f"✅ **{amount:,}₮** зээлийн төлбөр хийлээ!")
        
    @tasks.loop(hours=168)  
    async def process_loan_interest(self):
        """Зээлийн хүү бодох"""
        await self.bot.wait_until_ready()
        self.ensure_connection()
        last_date = self.get_last_interest_date("loan")
        today = datetime.now()

        if last_date and (today - last_date).days < 7:
            logger.info("⚠️ Зээлийн хүү тооцох хугацаа болоогүй байна!")
            return  

        self.c.execute("SELECT user_id, balance FROM loans")
        for user_id, balance in self.c.fetchall():
            interest = int(balance * self.loan_interest_rate)
            self.conn.execute("UPDATE loans SET balance = balance + ? WHERE user_id = ?", (interest, user_id))

        self.set_last_interest_date("loan")
        logger.info("✅ Зээлийн хүү тооцооллоо!")

    @tasks.loop(hours=336)  
    async def process_savings_interest(self):
        """Хадгаламжийн хүү бодох"""
        await self.bot.wait_until_ready()
        self.ensure_connection()
        last_date = self.get_last_interest_date("savings")
        today = datetime.now()

        if last_date and (today - last_date).days < 3:
            logger.info("⚠️ Хадгаламжийн хүү тооцох хугацаа болоогүй байна!")
            return  

        self.c.execute("SELECT user_id, balance FROM savings")
        for user_id, balance in self.c.fetchall():
            interest = int(balance * self.savings_interest_rate)
            self.conn.execute("UPDATE savings SET balance = balance + ? WHERE user_id = ?", (interest, user_id))

        self.set_last_interest_date("savings")
        logger.info("✅ Хадгаламжийн хүү тооцооллоо!")

    async def start_interest_loops(self):
        """Бот асаах үед хүү тооцох процессыг зөв эхлүүлэх"""
        self.ensure_connection()
        today = datetime.now()

        last_loan_interest = self.get_last_interest_date("loan")
        if last_loan_interest and (today - last_loan_interest).days >= 7:
            await self.process_loan_interest()
        self.process_loan_interest.start()  

        last_savings_interest = self.get_last_interest_date("savings")
        if last_savings_interest and (today - last_savings_interest).days >= 30:
            await self.process_savings_interest()
        self.process_savings_interest.start()  

    def cog_unload(self):
        """Бот унтрах үед мэдээллийн санг зөв хаах"""
        if self.conn:
            try:
                self.conn.execute("SELECT 1")
            except sqlite3.ProgrammingError:
                return
            self.conn.close()
            self.conn = None
            logger.info("✅ Мэдээллийн сан амжилттай хаагдлаа.")

async def setup(bot):
    vip_cog = bot.get_cog("VIP")
    bank = Bank(bot, vip_cog)
    await bot.add_cog(bank)  # ⬅️ Эхлээд когийг бүрэн нэмэх
    await bank.start_interest_loops()  # ✅ Дараа нь loop-уудыг эхлүүлэх