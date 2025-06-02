import discord
from discord.ext import commands
import aiosqlite
import random
import asyncio
import time

class Job(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.setup_database())

    async def setup_database(self):
        """Өгөгдлийн сангийн хүснэгтүүдийг үүсгэнэ."""
        self.conn = await aiosqlite.connect('economy.db')
        await self.conn.execute("PRAGMA journal_mode=WAL;")
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS economy (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bank (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS job_cooldowns (
                user_id INTEGER PRIMARY KEY,
                hack_cooldown INTEGER DEFAULT 0,
                rob_cooldown INTEGER DEFAULT 0,
                block_cooldown INTEGER DEFAULT 0
            )
        """)
        await self.conn.commit()

    async def check_vip(self, user_id):
        async with self.conn.execute("SELECT vip_expiry FROM users1 WHERE user_id=?", (user_id,)) as cursor:
            vip_status = await cursor.fetchone()
        return bool(vip_status and vip_status[0])

    async def get_balance(self, user_id):
        async with self.conn.execute("SELECT balance FROM economy WHERE user_id=?", (user_id,)) as cursor:
            result = await cursor.fetchone()
        return result[0] if result else 0

    async def update_balance(self, user_id, amount):
        current_balance = await self.get_balance(user_id)
        new_balance = max(current_balance + amount, 0)
        await self.conn.execute("""
            INSERT INTO economy (user_id, balance) VALUES (?, ?) 
            ON CONFLICT(user_id) DO UPDATE SET balance = ?
        """, (user_id, new_balance, new_balance))
        await self.conn.commit()
        return new_balance

    async def get_cooldown(self, user_id, cooldown_type):
        async with self.conn.execute(f"SELECT {cooldown_type}_cooldown FROM job_cooldowns WHERE user_id=?", (user_id,)) as cursor:
            result = await cursor.fetchone()
        return result[0] if result else 0

    async def hack_with_delay(self, ctx, hacker_id, target_id):
        await asyncio.sleep(60)  # 1 минут хүлээнэ
        target_bank_balance = await self.get_bank_balance(target_id)
        if target_bank_balance <= 0:
            return await ctx.send(f"⚠️ **{ctx.bot.get_user(target_id).display_name}** хакдах боломжгүй, банканд ямар ч мөнгөгүй байна!")
        
        stolen_amount = int(target_bank_balance * 0.05)
        await self.update_bank_balance(hacker_id, stolen_amount)
        await self.update_bank_balance(target_id, -stolen_amount)
        await ctx.send(f"💻 **{ctx.bot.get_user(hacker_id).display_name}** **{ctx.bot.get_user(target_id).display_name}**-ын банкнаас {stolen_amount:,}₮ хакдлаа!")

    async def update_cooldown(self, user_id, cooldown_type, duration):
        block_until = int(time.time()) + duration
        await self.conn.execute(f"""
            INSERT INTO job_cooldowns (user_id, {cooldown_type}_cooldown) 
            VALUES (?, ?) 
            ON CONFLICT(user_id) DO UPDATE SET {cooldown_type}_cooldown = excluded.{cooldown_type}_cooldown
        """, (user_id, block_until))
        await self.conn.commit()

    async def get_bank_balance(self, user_id):
        async with self.conn.execute("SELECT balance FROM bank WHERE user_id=?", (user_id,)) as cursor:
            result = await cursor.fetchone()
        return result[0] if result else 0

    async def update_bank_balance(self, user_id, amount):
        current_balance = await self.get_bank_balance(user_id)
        new_balance = max(current_balance + amount, 0)
        await self.conn.execute("""
            INSERT INTO bank (user_id, balance) VALUES (?, ?) 
            ON CONFLICT(user_id) DO UPDATE SET balance = excluded.balance
        """, (user_id, new_balance))
        await self.conn.commit()
        return new_balance

    async def format_remaining_time(self, remaining_time):
        hours, remainder = divmod(remaining_time, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours} цаг, {minutes} мин, {seconds} сек"

    # ----------------- Роб хийх команд -----------------
    @commands.command(name='rob')
    async def rob(self, ctx, target: discord.Member):
        robber_id, target_id = ctx.author.id, target.id

        if target.bot or target_id == ctx.bot.user.id:
            return await ctx.send("❌ Бот болон хэн ч байхгүй хэрэглэгчийг дээрэмдэх боломжгүй!")

        if robber_id == target_id:
            return await ctx.send("❌ Өөрийгөө дээрэмдэх боломжгүй!")

        is_vip = await self.check_vip(robber_id)
        cooldown_time = 1800 if is_vip else 3600
        cooldown = await self.get_cooldown(robber_id, "rob")

        if int(time.time()) < cooldown:
            return await ctx.send(f"⏳ Дахин дээрэмдэхийн тулд хүлээнэ үү: {await self.format_remaining_time(cooldown - int(time.time()))}")

        target_balance = await self.get_balance(target_id)
        robber_balance = await self.get_balance(robber_id)

        if robber_balance < 500000:
            return await ctx.send("⚠️ Та дээрэм хийхийн тулд дор хаяж халаасанд **500,000₮** байх шаардлагатай!")

        if target_balance <= 0:
            return await ctx.send(f"⚠️ {target.display_name} дээрэмдэх боломжгүй!")

        if random.uniform(0, 1) < (0.7 if is_vip else 0.5):
            stolen_amount = int(target_balance * (0.1 if is_vip else 0.05))
            await self.update_balance(robber_id, stolen_amount)
            await self.update_balance(target_id, -stolen_amount)
            await ctx.send(f"💰 {ctx.author.display_name} {target.display_name}-аас {stolen_amount:,}₮ хулгайллаа!")
        else:
            await self.update_balance(robber_id, -500000)
            await ctx.send(f"❌ Дээрэм амжилтгүй боллоо, та **500,000₮** торгууль төлсөн!")

        await self.update_cooldown(robber_id, "rob", cooldown_time)

    # ----------------- Хак хийх команд -----------------
    @commands.command(name='hack')
    async def hack(self, ctx, target: discord.Member):
        hacker_id = ctx.author.id
        target_id = target.id
        current_time = int(time.time())

        if hacker_id == target_id:
            return await ctx.send("❌ Өөрийгөө хакдах боломжгүй!")

        block_cooldown = await self.get_cooldown(target_id, "block")
        if current_time < block_cooldown:
            return await ctx.send(f"🛡️ **{target.display_name}** хамгаалагдсан тул хакдах боломжгүй!")

        is_vip = await self.check_vip(hacker_id)
        cooldown_time = 43200 if is_vip else 86400

        cooldown = await self.get_cooldown(hacker_id, "hack")
        if current_time < cooldown:
            remaining_time = cooldown - current_time
            return await ctx.send(f"⏳ Дахин хакдахын тулд хүлээнэ үү: {await self.format_remaining_time(remaining_time)}")

        await self.update_cooldown(hacker_id, "hack", cooldown_time)
        await ctx.send(f"⏳ Хак эхэллээ, 1 минутын дараа хакдах болно!")
        asyncio.create_task(self.hack_with_delay(ctx, hacker_id, target_id))

    @commands.command(name='block')
    async def block(self, ctx):
        user_id = ctx.author.id
        current_time = int(time.time())
        block_until = await self.get_cooldown(user_id, "block")

        if current_time < block_until:
            return await ctx.send(f"⏳ Та блок хийсэн байна! Үлдсэн хугацаа: {await self.format_remaining_time(block_until - current_time)}")
        
        await self.update_cooldown(user_id, "block", 19800)
        await ctx.send(f"🛡️ {ctx.author.display_name} 5 цаг 30 минутын турш хамгаалагдлаа!")

    def cog_unload(self):
        asyncio.create_task(self.conn.close())

async def setup(bot):
    """Bot дээр энэхүү Cog-ийг ачаална."""
    await bot.add_cog(Job(bot))