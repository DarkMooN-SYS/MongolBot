import aiosqlite
import discord
from discord.ext import commands

class ServerBank(commands.Cog):
    def __init__(self, bot, db_path='serverbank.db'):
        self.bot = bot
        self.db_path = db_path
        self.bot.loop.create_task(self.setup())

    async def setup(self):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS server_bank (
                    server_id INTEGER,
                    owner_id INTEGER,
                    balance INTEGER DEFAULT 0,
                    PRIMARY KEY (server_id, owner_id)
                )
            ''')
            await conn.commit()

    async def is_owner(self, ctx):
        server_id = ctx.guild.id
        user_id = ctx.author.id
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute(
                'SELECT 1 FROM server_bank WHERE server_id = ? AND owner_id = ?',
                (server_id, user_id)
            ) as cursor:
                return await cursor.fetchone() is not None

    async def update_balance(self, server_id, amount):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                'UPDATE server_bank SET balance = balance + ? WHERE server_id = ?',
                (amount, server_id)
            )
            await conn.commit()

    async def get_balance(self, server_id):
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute(
                'SELECT balance FROM server_bank WHERE server_id = ?',
                (server_id,)
            ) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 0

    @commands.command(name='addserver')
    @commands.is_owner()
    async def add_server_command(self, ctx, guild_id: int, *owners):
        if len(owners) < 1:
            return await ctx.send("⚠️ Дор хаяж 1 хэрэглэгч оруулна уу.")
        
        success = []
        failed = []

        async with aiosqlite.connect(self.db_path) as conn:
            for owner_input in owners:
                try:
                    if owner_input.isdigit():
                        owner_id = int(owner_input)
                    else:
                        owner = await commands.UserConverter().convert(ctx, owner_input)
                        owner_id = owner.id

                    await conn.execute(
                        'INSERT OR IGNORE INTO server_bank (server_id, owner_id, balance) VALUES (?, ?, ?)',
                        (guild_id, owner_id, 10_000_000)
                    )
                    success.append(f"<@{owner_id}>")
                except Exception:
                    failed.append(owner_input)
            await conn.commit()

        result = "✅ Амжилттай нэмэгдсэн:\n" + "\n".join(success)
        if failed:
            result += "\n⚠️ Олдоогүй:\n" + "\n".join(failed)
        await ctx.send(result)

    @commands.command(name='addowners')
    @commands.is_owner()
    async def add_owners_command(self, ctx, server_id: int, *users):
        if len(users) < 1:
            return await ctx.send("⚠️ Дор хаяж 1 хэрэглэгч оруулна уу.")
        
        success = []
        failed = []

        async with aiosqlite.connect(self.db_path) as conn:
            for user in users:
                try:
                    member = await commands.UserConverter().convert(ctx, user)
                    await conn.execute('INSERT OR IGNORE INTO server_bank (server_id, owner_id) VALUES (?, ?)',
                                       (server_id, member.id))
                    success.append(f"<@{member.id}>")
                except Exception:
                    failed.append(user)
            await conn.commit()

        result = "✅ Амжилттай нэмэгдсэн:\n" + "\n".join(success)
        if failed:
            result += "\n⚠️ Олдоогүй:\n" + "\n".join(failed)
        await ctx.send(result)

    @commands.command(name='removeowner')
    @commands.is_owner()
    async def remove_owner_command(self, ctx, server_id: int, user: discord.User):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute('DELETE FROM server_bank WHERE server_id = ? AND owner_id = ?', (server_id, user.id))
            await conn.commit()
        await ctx.send(f"🗑️ {user.mention} сервер {server_id}-ийн эзэмшигчээс хасагдлаа.")

    @commands.command(name='listowners')
    async def list_owners_command(self, ctx):
        # Тухайн серверийн ID-г ашиглана
        server_id = ctx.guild.id

        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute('SELECT owner_id FROM server_bank WHERE server_id = ?', (server_id,)) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            return await ctx.send("❌ Энэ серверт эзэн бүртгэгдээгүй байна.")
    
        mentions = [f"<@{row[0]}>" for row in rows]
        await ctx.send("📋 Серверийн эзэд:\n" + "\n".join(mentions))

    @commands.command(name='checkbalance')
    async def check_balance_command(self, ctx):
        if not await self.is_owner(ctx):
            return await ctx.send("⚠️ Зөвхөн серверийн эзэн ашиглах боломжтой!")
        balance = await self.get_balance(ctx.guild.id)
        await ctx.send(f"💰 Серверийн банкны үлдэгдэл: **{balance:,}₮**")

    @commands.command(name='serverdep')
    async def deposit_command(self, ctx, amount: int):
        if not await self.is_owner(ctx):
            return await ctx.send("⚠️ Зөвхөн серверийн эзэн ашиглах боломжтой!")
        await self.update_balance(ctx.guild.id, amount)
        await ctx.send(f"➕ {amount:,}₮ серверийн банканд нэмэгдлээ!")

    @commands.command(name='serverwith')
    async def withdraw_command(self, ctx, amount: int):
        if not await self.is_owner(ctx):
            return await ctx.send("⚠️ Зөвхөн серверийн эзэн ашиглах боломжтой!")
        balance = await self.get_balance(ctx.guild.id)
        if balance < amount:
            return await ctx.send("⚠️ Серверийн банкны үлдэгдэл хүрэлцэхгүй байна.")
        await self.update_balance(ctx.guild.id, -amount)
        await ctx.send(f"➖ {amount:,}₮ серверийн банкнаас хасагдлаа!")

    @check_balance_command.error
    @deposit_command.error
    @withdraw_command.error
    async def command_error_handler(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("⚠️ Зөвхөн **серверийн эзэд** ашиглах боломжтой.")
        else:
            await ctx.send(f"❌ Алдаа гарлаа: `{error}`")