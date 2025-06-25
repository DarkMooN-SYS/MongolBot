# -*- coding: utf-8 -*-
import discord
from discord.ext import commands, tasks
import random
from datetime import datetime, timedelta
import pytz
from .vip_utils import get_vip_level
from typing import Any
import aiosqlite
import os
from pathlib import Path
from ..utils.channel import is_channel_enabled

TICKET_PRICE = 300_000
MAX_TICKETS_PER_USER = 2 # Суурь тасалбарын тоо
LOTTERY_INTERVAL_DAYS = 30  # 1 сар
MONGOLIA_TZ = pytz.timezone('Asia/Ulaanbaatar')

def get_mongolia_time():
    """Монгол цагийн бүсээр одоогийн цагийг буцаах"""
    return datetime.now(MONGOLIA_TZ)

class Lottery(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tickets = {}  # {user_id: ticket_count}
        self.jackpot = 0
        self.last_draw = None
        self.winners = []  # [(user_id, amount, date)]
        
        # Database path-ийг илүү найдвартай болгох
        self.data_dir = Path(__file__).parent.parent.parent / 'data'
        self.data_dir.mkdir(exist_ok=True)
        self.db_path = self.data_dir / 'lottery.db'
        
        self.lottery_task.start()

    async def cog_load(self):
        """Cog ачаалагдахад database болон өгөгдлүүдийг сэргээх"""
        await self.init_database()
        await self.load_lottery_data()

    async def init_database(self):
        """Lottery database үүсгэх"""
        try:
            # Folder үүсгэх
            self.data_dir.mkdir(exist_ok=True)
            
            async with aiosqlite.connect(str(self.db_path)) as db:
                # Database файл зөв үүсч байгаа эсэхийг шалгах
                await db.execute('SELECT 1')
                
                # Тасалбарууд хадгалах хүснэгт
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS tickets (
                        user_id INTEGER PRIMARY KEY,
                        ticket_count INTEGER DEFAULT 0
                    )
                ''')
                # Сугалааны мэдээлэл хадгалах хүснэгт
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS lottery_info (
                        id INTEGER PRIMARY KEY,
                        jackpot INTEGER DEFAULT 0,
                        last_draw TEXT
                    )
                ''')
                # Ялагчдын түүх хадгалах хүснэгт
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS winners (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        amount INTEGER,
                        date TEXT
                    )                ''')
                await db.commit()
                print(f"✅ Lottery database амжилттай үүслээ: {self.db_path}")
                
        except Exception as e:
            print(f"❌ Lottery database үүсгэхэд алдаа: {e}")
            raise

    async def load_lottery_data(self):
        """Database-ээс өгөгдөл уншиж memory-д ачаалах"""
        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                # Тасалбарууд ачаалах
                async with db.execute('SELECT user_id, ticket_count FROM tickets') as cursor:
                    async for row in cursor:
                        self.tickets[row[0]] = row[1]
                
                # Jackpot болон сүүлийн сугалааны мэдээлэл ачаалах
                async with db.execute('SELECT jackpot, last_draw FROM lottery_info WHERE id = 1') as cursor:
                    row = await cursor.fetchone()
                    if row:
                        self.jackpot = row[0] if row[0] is not None else 0
                        if row[1]:
                            self.last_draw = datetime.fromisoformat(row[1])
                    else:
                        # Анхны мэдээлэл үүсгэх
                        self.jackpot = 0
                        self.last_draw = None
                
                # Ялагчдын түүх ачаалах
                async with db.execute('SELECT user_id, amount, date FROM winners ORDER BY id DESC LIMIT 10') as cursor:
                    async for row in cursor:
                        self.winners.append((row[0], row[1], datetime.fromisoformat(row[2])))
                        
                print(f"✅ Lottery data амжилттай ачаалагдлаа: {len(self.tickets)} тасалбар, jackpot: {self.jackpot:,}₮")
                
        except Exception as e:
            print(f"❌ Lottery data ачаалахад алдаа: {e}")

    async def save_lottery_data(self):
        """Одоогийн мэдээллийг database-д хадгалах"""
        try:
            # Database болон table-г эхлээд шалгаж байна
            await self.init_database()
            
            async with aiosqlite.connect(str(self.db_path)) as db:
                # Transaction ашиглах
                await db.execute('BEGIN TRANSACTION')
                
                try:
                    # Тасалбарууд хадгалах
                    await db.execute('DELETE FROM tickets')
                    for user_id, count in self.tickets.items():
                        await db.execute('INSERT INTO tickets (user_id, ticket_count) VALUES (?, ?)', 
                                       (user_id, count))
                    
                    # Jackpot болон сүүлийн сугалааны мэдээлэл хадгалах
                    last_draw_str = self.last_draw.isoformat() if self.last_draw else None
                    await db.execute('''
                        INSERT OR REPLACE INTO lottery_info (id, jackpot, last_draw) 
                        VALUES (1, ?, ?)
                    ''', (self.jackpot, last_draw_str))
                    
                    await db.execute('COMMIT')
                    print(f"✅ Lottery data амжилттай хадгалагдлаа - Jackpot: {self.jackpot:,}₮, Tickets: {len(self.tickets)}")
                    
                except Exception as e:
                    await db.execute('ROLLBACK')
                    print(f"❌ Transaction rollback: {e}")
                    raise
                    
        except Exception as e:
            print(f"❌ Lottery data хадгалахад алдаа: {e}")
            # Database алдаа гарвал дахин үүсгэж оролдох
            try:
                await self.init_database()
            except Exception as init_error:
                print(f"❌ Database дахин эхлүүлэхэд алдаа: {init_error}")

    async def add_winner(self, user_id: int, amount: int, date: datetime):
        """Ялагчийг database-д хадгалах"""
        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                await db.execute('INSERT INTO winners (user_id, amount, date) VALUES (?, ?, ?)', 
                               (user_id, amount, date.isoformat()))
                await db.commit()
            self.winners.insert(0, (user_id, amount, date))
            # Зөвхөн сүүлийн 10 ялагчийг memory-д хадгалах
            if len(self.winners) > 10:
                self.winners = self.winners[:10]
        except Exception as e:
            print(f"❌ Winner хадгалахад алдаа: {e}")

    async def cog_unload(self):
        """Cog унтрахад өгөгдлийг хадгалах"""
        await self.save_lottery_data()
        self.lottery_task.cancel()

    @property
    def bank(self) -> Any:
        """
        Bank cog-г буцаана. Хэрвээ ачаалагдаагүй бол None буцаана.
        Pylance-д зориулж төрөл тодорхойлсон.
        """
        bank_cog = self.bot.get_cog('Bank')
        if bank_cog and hasattr(bank_cog, "get_balance") and hasattr(bank_cog, "update_balance"):
            return bank_cog
        return None

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

    @commands.command(name='buylottery')
    async def lottery_buy(self, ctx: commands.Context, count: int = 1):
        user_id = ctx.author.id
        base_max_tickets = 2
        vip_level = await get_vip_level(self.bot, user_id)
        vip_bonus = 0
        if vip_level:
            vip_bonus = 1
        max_tickets = base_max_tickets + vip_bonus
        if count < 1 or count > max_tickets:
            await ctx.send(f'1-ээс {max_tickets} хүртэл тасалбар авч болно.' + (f' (VIP: +{vip_bonus} тасалбар)' if vip_bonus else ''))
            return
        prev = self.tickets.get(user_id, 0)
        if prev + count > max_tickets:
            await ctx.send(f'Нийтдээ {max_tickets} тасалбар л авч болно.' + (f' (VIP: +{vip_bonus} тасалбар)' if vip_bonus else ''))
            return
        # --- Баланс шалгах, мөнгө хасах ---
        bank = self.bank
        if not bank:
            await ctx.send('💸 Санхүүгийн систем ачаалагдаагүй байна. Та дахин оролдоно уу.')
            return
        # Pylance-д зориулж төрөл тодорхойлж, type: ignore ашиглаж байна
        get_balance = getattr(bank, "get_balance", None)  # type: ignore[attr-defined]
        if not callable(get_balance):
            await ctx.send('💸 Санхүүгийн системийн get_balance функц олдсонгүй.')
            return
        balance = await get_balance(user_id, 'bank')  # type: ignore
        total_price = TICKET_PRICE * count
        if balance < total_price:
            await ctx.send(f'💸 Таны үлдэгдэл хүрэлцэхгүй байна! (Таны үлдэгдэл: {balance:,}₮, нийт үнэ: {total_price:,}₮)')
            return
        update_balance = getattr(bank, "update_balance", None)  # type: ignore[attr-defined]
        if not callable(update_balance):
            await ctx.send('💸 Санхүүгийн системийн update_balance функц олдсонгүй.')
            return
        await update_balance('bank', user_id, -total_price)  # type: ignore
        self.tickets[user_id] = prev + count
        self.jackpot += total_price
        
        # Database-д хадгалах
        await self.save_lottery_data()
        
        embed = discord.Embed(
            title='🎟️ Сугалааны тасалбар амжилттай авлаа!',
            description=(
                f'Таны нийт тасалбар: **{self.tickets[user_id]}**\n'
                f'Jackpot: **{self.jackpot:,}₮**\n'
                f'Үлдэгдэл: **{balance-total_price:,}₮**'
            ),
            color=discord.Color.green()
        )
        if vip_bonus:
            embed.set_footer(text=f'VIP эрхтэй тул +{vip_bonus} тасалбар авах боломжтой!')
        await ctx.send(embed=embed)

    @commands.command(name='lottery')
    async def lottery_info(self, ctx: commands.Context):
        try:
            next_draw = None
            if self.last_draw is None:
                next_draw = get_mongolia_time() + timedelta(days=LOTTERY_INTERVAL_DAYS)
            else:
                # Convert UTC last_draw to Mongolia time for calculation
                last_draw_mg = self.last_draw.replace(tzinfo=pytz.UTC).astimezone(MONGOLIA_TZ)
                next_draw = last_draw_mg + timedelta(days=LOTTERY_INTERVAL_DAYS)
            
            # Unicode алдаанаас сэргийлэхийн тулд энгийн форматаар
            next_draw_str = next_draw.strftime('%Y-%m-%d %H:%M') + ' (MN)' if next_draw else 'Тодорхойгүй'
            channel_mention = '<#1297446170003767383>'
            
            embed = discord.Embed(
                title='🎟️ Сугалааны мэдээлэл',
                color=discord.Color.gold()
            )
            embed.add_field(
                name='💰 Одоогийн jackpot',
                value=f'**{self.jackpot:,}₮**',
                inline=True
            )
            embed.add_field(
                name='👥 Оролцогчид',
                value=f'**{len(self.tickets)}** хүн',
                inline=True
            )
            embed.add_field(
                name='⏰ Дараагийн сугалаа',
                value=f'**{next_draw_str}**',
                inline=True
            )
            embed.add_field(
                name='📺 Зарлагдах суваг',
                value=channel_mention,
                inline=True
            )
            embed.add_field(
                name='🎟️ Тасалбарын лимит',
                value=f'Хэрэглэгч бүр **{MAX_TICKETS_PER_USER}** (VIP бол **+1**) тасалбар',
                inline=True
            )
            embed.add_field(
                name='💵 Үнэ',
                value=f'1 тасалбар = **{TICKET_PRICE:,}₮**',
                inline=True
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            # Fallback санал болгосон text мэдээлэл
            await ctx.send(
                f'🎟️ **Сугалааны мэдээлэл**\n'
                f'- Jackpot: **{self.jackpot:,}₮**\n'
                f'- Оролцогчид: **{len(self.tickets)}**\n'
                f'- 1 тасалбар = **{TICKET_PRICE:,}₮**\n'
                f'- Лимит: {MAX_TICKETS_PER_USER} (VIP +1)'
            )

    @tasks.loop(hours=24)
    async def lottery_task(self):
        try:
            now = datetime.utcnow()
            if self.last_draw is None:
                self.last_draw = now
                await self.save_lottery_data()  # Анхны огноог хадгалах
            elif (now - self.last_draw).days >= LOTTERY_INTERVAL_DAYS:
                guild = self.bot.get_guild(1297446169995251712)
                channel = guild.get_channel(1297446170003767383) if guild else None
                if self.tickets and isinstance(channel, discord.TextChannel):
                    pool = []
                    for user_id, count in self.tickets.items():
                        pool.extend([user_id] * count)
                    winner_id = random.choice(pool)
                    winner = guild.get_member(winner_id) if guild else None
                    amount = self.jackpot  # Winner gets the full jackpot
                    # Ялагчийг database-д хадгалах
                    await self.add_winner(winner_id, amount, now)
                    # --- Jackpot-ыг ялагчийн дансанд бүрэн шилжүүлэх ---
                    bank = self.bank
                    jackpot_added = False
                    if bank and winner:
                        update_balance = getattr(bank, "update_balance", None)  # type: ignore[attr-defined]
                        if callable(update_balance):
                            try:
                                await update_balance('bank', winner_id, amount)  # type: ignore[misc]
                                jackpot_added = True
                            except Exception:
                                pass  # Алдаа гарсан ч үргэлжлүүлнэ
                    
                    embed = discord.Embed(
                        title='🎉🏆 СУГАЛААНЫ ЯЛАГЧ ТОДОРЛОО! 🏆🎉',
                        description=(
                            f'🎊 **Баяр хүргэе!** Сугалааны азтан тодорлоо!\n\n'
                            f'💰 **Jackpot:** {amount:,}₮\n'
                            f'🏆 **Ялагч:** {winner.mention if winner else f"ID: {winner_id}"}\n'
                            f'🎟️ **Оролцогчдын тоо:** {len(self.tickets)}\n\n'
                            + ('✅ **Jackpot амжилттай дансанд шилжлээ!**' if jackpot_added else '⚠️ **Jackpot дансанд нэмэхэд алдаа гарлаа!**')
                        ),
                        color=discord.Color.gold(),
                        timestamp=get_mongolia_time()
                    )
                    embed.set_thumbnail(url='https://cdn.discordapp.com/emojis/1234567890.gif' if winner and winner.avatar else None)
                    embed.add_field(
                        name='🎯 Дараагийн сугалаа',
                        value=f'30 хоногийн дараа!\nТасалбар авахыг мартуузай! (`/buylottery`)',
                        inline=False
                    )
                    embed.set_footer(
                        text='МонголБот • Сугалааны систем',
                        icon_url=self.bot.user.avatar.url if self.bot.user and self.bot.user.avatar else None
                    )
                    
                    await channel.send(content='@everyone 🎉 **СУГАЛААНЫ ҮНДЭСНИЙ ЯЛАГЧ ТОДОРЛОО!** 🎉', embed=embed)
                    self.tickets.clear()
                    self.jackpot = 0
                    self.last_draw = now
                    # Database-д өөрчлөлт хадгалах
                    await self.save_lottery_data()
        except Exception as e:
            print(f"Lottery task алдаа: {e}")
            # Database алдаа гарвал дахин эхлүүлэх оролдлого
            try:
                await self.init_database()
            except Exception as init_error:
                print(f"Database дахин эхлүүлэхэд алдаа: {init_error}")

    @lottery_task.before_loop
    async def before_lottery_task(self):
        await self.bot.wait_until_ready()

    @commands.command(name='lotterytest', hidden=True)
    @commands.has_permissions(administrator=True)
    async def lottery_test(self, ctx: commands.Context):
        """Админд зориулсан тест команд: шууд ялагч тодруулж, мэдэгдэл илгээнэ."""
        if not self.tickets:
            await ctx.send('Оролцогч байхгүй байна.')
            return
        guild = ctx.guild or self.bot.get_guild(1297446169995251712)
        channel = guild.get_channel(1297446170003767383) if guild else ctx.channel
        if not isinstance(channel, discord.TextChannel):
            await ctx.send('Тохирох текст суваг олдсонгүй.')
            return
        pool = []
        for user_id, count in self.tickets.items():
            pool.extend([user_id] * count)
        winner_id = random.choice(pool)
        winner = guild.get_member(winner_id) if guild else None
        amount = self.jackpot  # Winner gets the full jackpot
        # Ялагчийг database-д хадгалах
        await self.add_winner(winner_id, amount, datetime.utcnow())
        # --- Jackpot-ыг ялагчийн дансанд бүрэн шилжүүлэх ---
        bank = self.bank
        jackpot_added = False
        if bank:
            update_balance = getattr(bank, "update_balance", None)  # type: ignore[attr-defined]
            if callable(update_balance):
                try:
                    await update_balance('bank', winner_id, amount)  # type: ignore[misc]
                    jackpot_added = True
                except Exception:                    pass  # Алдаа гарсан ч үргэлжлүүлнэ
        
        embed = discord.Embed(
            title='[ТЕСТ] 🎉🏆 СУГАЛААНЫ ЯЛАГЧ ТОДОРЛОО! 🏆🎉',
            description=(
                f'🎊 **[ТЕСТ ГОРИМ]** Сугалааны азтан тодорлоо!\n\n'
                f'💰 **Jackpot:** {amount:,}₮\n'
                f'🏆 **Ялагч:** {winner.mention if winner else f"ID: {winner_id}"}\n'
                f'🎟️ **Оролцогчдын тоо:** {len(self.tickets)}\n\n'
                + ('✅ **Jackpot амжилттай дансанд шилжлээ!**' if jackpot_added else '⚠️ **Jackpot дансанд нэмэхэд алдаа гарлаа!**')
            ),
            color=discord.Color.purple(),
            timestamp=get_mongolia_time()
        )
        embed.add_field(
            name='⚠️ Анхааруулга',
            value='Энэ бол тест горимын сугалаа юм!',
            inline=False
        )
        embed.set_footer(
            text='МонголБот • Тест Горим',
            icon_url=self.bot.user.avatar.url if self.bot.user and self.bot.user.avatar else None
        )        
        await channel.send(content='@everyone [ТЕСТ] 🎉 **СУГАЛААНЫ ТЕСТ ЯЛАГЧ ТОДОРЛОО!** 🎉', embed=embed)
        self.tickets.clear()
        self.jackpot = 0
        self.last_draw = datetime.utcnow()  # Store as UTC in database
        # Database-д өөрчлөлт хадгалах
        await self.save_lottery_data()
        await ctx.send('Тест сугалаа амжилттай гүйцэтгэлээ.')

    async def test_database_connection(self):
        """Database холболт шалгах"""
        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                # Simple query ажиллуулах
                cursor = await db.execute('SELECT COUNT(*) FROM tickets')
                count = await cursor.fetchone()
                print(f"✅ Database холболт амжилттай. Tickets тоо: {count[0] if count else 0}")
                return True
        except Exception as e:
            print(f"❌ Database холболтын алдаа: {e}")
            return False

    @commands.command(name='lotterydb', hidden=True)
    @commands.has_permissions(administrator=True)
    async def lottery_db_test(self, ctx: commands.Context):
        """Database холболт шалгах"""
        
        embed = discord.Embed(title="🗄️ Lottery Database шалгалт", color=discord.Color.blue())
        
        # Database файл байгаа эсэх
        if self.db_path.exists():
            embed.add_field(name="📁 Database файл", value="✅ Байна", inline=True)
            embed.add_field(name="📍 Байршил", value=f"`{self.db_path}`", inline=False)
        else:
            embed.add_field(name="📁 Database файл", value="❌ Байхгүй", inline=True)
        
        # Холболт шалгах
        connection_ok = await self.test_database_connection()
        embed.add_field(name="🔗 Холболт", value="✅ Амжилттай" if connection_ok else "❌ Алдаатай", inline=True)
        
        # Memory дэх өгөгдөл
        embed.add_field(name="🎟️ Tickets (memory)", value=str(len(self.tickets)), inline=True)
        embed.add_field(name="💰 Jackpot", value=f"{self.jackpot:,}₮", inline=True)
        embed.add_field(name="🏆 Winners", value=str(len(self.winners)), inline=True)
        
        # Last draw
        if self.last_draw:
            embed.add_field(name="📅 Сүүлийн сугалаа", value=self.last_draw.strftime('%Y-%m-%d %H:%M'), inline=True)
        else:
            embed.add_field(name="📅 Сүүлийн сугалаа", value="Байхгүй", inline=True)
        
        await ctx.send(embed=embed)

    @commands.command(name='lotteryreload', hidden=True)
    @commands.has_permissions(administrator=True)
    async def lottery_reload(self, ctx: commands.Context):
        """Database-ээс lottery өгөгдлийг дахин ачаалах"""
        old_jackpot = self.jackpot
        old_tickets = len(self.tickets)
        
        # Өгөгдлийг дахин ачаалах
        self.tickets = {}
        self.jackpot = 0
        self.last_draw = None
        self.winners = []
        
        await self.load_lottery_data()
        
        embed = discord.Embed(
            title="🔄 Lottery өгөгдөл дахин ачаалагдлаа",
            color=discord.Color.blue()
        )
        embed.add_field(name="💰 Jackpot", value=f"Өмнө: {old_jackpot:,}₮\nОдоо: {self.jackpot:,}₮", inline=True)
        embed.add_field(name="🎟️ Tickets", value=f"Өмнө: {old_tickets}\nОдоо: {len(self.tickets)}", inline=True)
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    lottery_cog = Lottery(bot)
    await lottery_cog.cog_load()  # Database init хийх
    await bot.add_cog(lottery_cog)
