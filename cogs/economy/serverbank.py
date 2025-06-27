import discord
from discord.ext import commands
from typing import Optional, List, Tuple, Union
from ..utils.database import get_async_db_context
from ..utils.channel import is_channel_enabled

class ServerBank(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.bot.loop.create_task(self.setup())

    async def setup(self):
        async with get_async_db_context('serverbank') as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS server_bank (
                    server_id INTEGER,
                    owner_id INTEGER,
                    balance INTEGER DEFAULT 0,
                    PRIMARY KEY (server_id, owner_id)
                )
            ''')
            await conn.commit()

    async def is_owner(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            return False
        server_id: int = ctx.guild.id
        user_id: int = ctx.author.id
        async with get_async_db_context('serverbank') as conn:
            async with conn.execute(
                'SELECT 1 FROM server_bank WHERE server_id = ? AND owner_id = ?',
                (server_id, user_id)
            ) as cursor:
                return await cursor.fetchone() is not None

    async def update_balance(self, server_id: int, amount: int) -> None:
        # Update balance for only one owner (the one with the smallest owner_id)
        async with get_async_db_context('serverbank') as conn:
            async with conn.execute(
                'SELECT owner_id FROM server_bank WHERE server_id = ? ORDER BY owner_id ASC LIMIT 1',
                (server_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    owner_id = row[0]
                    await conn.execute(
                        'UPDATE server_bank SET balance = balance + ? WHERE server_id = ? AND owner_id = ?',
                        (amount, server_id, owner_id)
                    )
                    await conn.commit()

    async def safe_withdraw(self, server_id: int, amount: int) -> bool:
        """Аюулгүй мөнгө гаргах - сөрөг үлдэгдэл үүсгэхгүй (зөвхөн нэг эзэмшигчийн мөрөнд)"""
        async with get_async_db_context('serverbank') as conn:
            # Only check and update the row for the smallest owner_id
            async with conn.execute(
                'SELECT owner_id, balance FROM server_bank WHERE server_id = ? ORDER BY owner_id ASC LIMIT 1',
                (server_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return False
                owner_id, current_balance = row
                if current_balance < amount or current_balance - amount < 0:
                    return False
                await conn.execute(
                    'UPDATE server_bank SET balance = balance - ? WHERE server_id = ? AND owner_id = ?',
                    (amount, server_id, owner_id)
                )
                await conn.commit()
                return True

    async def get_balance(self, server_id: int) -> int:
        # Sum balance across all owners (shared bank)
        async with get_async_db_context('serverbank') as conn:
            async with conn.execute(
                'SELECT SUM(balance) FROM server_bank WHERE server_id = ?',
                (server_id,)
            ) as cursor:
                result = await cursor.fetchone()
                return result[0] if result and result[0] is not None else 0

    @commands.command(name='addserver')
    async def addserver(self, ctx: commands.Context):
        if not ctx.guild or not await is_channel_enabled(ctx.guild.id, ctx.channel.id):
            await ctx.send("Энэ channel-д команд ашиглах боломжгүй!")
            return
        
        if not await self.is_owner(ctx):
            return await ctx.send("⚠️ Зөвхөн серверийн эзэн ашиглах боломжтой!")

        await ctx.send("Сервер нэмэх команд.")
        # ...existing code for adding server...

    @commands.command(name='addowners')
    @commands.is_owner()
    async def add_owners_command(self, ctx: commands.Context, server_id: int, *users: str):
        if len(users) < 1:
            return await ctx.send("⚠️ Дор хаяж 1 хэрэглэгч оруулна уу.")
        
        success = []
        failed = []
        already_exists = []

        async with get_async_db_context('serverbank') as conn:
            for user in users:
                try:
                    member = await commands.UserConverter().convert(ctx, user)
                    
                    # Эхлээд тухайн хэрэглэгч аль хэдийн эзэн байгаа эсэхийг шалгах
                    async with conn.execute('SELECT 1 FROM server_bank WHERE server_id = ? AND owner_id = ?', (server_id, member.id)) as cursor:
                        exists = await cursor.fetchone()
                    
                    if exists:
                        already_exists.append(f"<@{member.id}>")
                    else:
                        await conn.execute('INSERT INTO server_bank (server_id, owner_id, balance) VALUES (?, ?, 0)',
                                           (server_id, member.id))
                        success.append(f"<@{member.id}>")
                except Exception:
                    failed.append(user)
            await conn.commit()

        result = ""
        if success:
            result += "✅ Амжилттай нэмэгдсэн:\n" + "\n".join(success)
        if already_exists:
            if result:
                result += "\n\n"
            result += "⚠️ Аль хэдийн эзэн байгаа:\n" + "\n".join(already_exists)
        if failed:
            if result:
                result += "\n\n"
            result += "❌ Олдоогүй:\n" + "\n".join(failed)
        
        if not result:
            result = "❌ Ямар ч өөрчлөлт хийгдсэнгүй."
            
        await ctx.send(result)

    @commands.command(name='removeowner')
    @commands.is_owner()
    async def remove_owner_command(self, ctx: commands.Context, server_id: int, user: discord.User):
        async with get_async_db_context('serverbank') as conn:
            # Эхлээд тухайн хэрэглэгч тэр серверийн эзэн байгаа эсэхийг шалгах
            async with conn.execute('SELECT 1 FROM server_bank WHERE server_id = ? AND owner_id = ?', (server_id, user.id)) as cursor:
                exists = await cursor.fetchone()
            
            if not exists:
                return await ctx.send(f"❌ {user.mention} сервер {server_id}-ийн эзэн биш байна.")
            
            # Устгах
            await conn.execute('DELETE FROM server_bank WHERE server_id = ? AND owner_id = ?', (server_id, user.id))
            await conn.commit()
        
        await ctx.send(f"🗑️ {user.mention} сервер {server_id}-ийн эзэмшигчээс амжилттай хасагдлаа.")

    @commands.command(name='listowners')
    async def list_owners_command(self, ctx: commands.Context):
        # Тухайн серверийн ID-г ашиглана
        if ctx.guild is None:
            return await ctx.send("❌ Энэ команд зөвхөн сервер дээр ажиллана.")
        server_id = ctx.guild.id

        async with get_async_db_context('serverbank') as conn:
            async with conn.execute('SELECT owner_id FROM server_bank WHERE server_id = ?', (server_id,)) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            return await ctx.send("❌ Энэ серверт эзэн бүртгэгдээгүй байна.")
    
        mentions = [f"<@{row[0]}>" for row in rows]
        await ctx.send("📋 Серверийн эзэд:\n" + "\n".join(mentions))

    @commands.command(name='checkbalance')
    async def check_balance_command(self, ctx: commands.Context):
        if ctx.guild is None:
            return await ctx.send("❌ Энэ команд зөвхөн сервер дээр ажиллана.")
        if not await self.is_owner(ctx):
            return await ctx.send("⚠️ Зөвхөн серверийн эзэн ашиглах боломжтой!")
        balance = await self.get_balance(ctx.guild.id)
        await ctx.send(f"💰 Серверийн банкны үлдэгдэл: **{balance:,}₮**")    
    
    @commands.command(name='serverwith')
    async def withdraw_command(self, ctx: commands.Context, amount: Optional[int] = None):
        if ctx.guild is None:
            return await ctx.send("❌ Энэ команд зөвхөн сервер дээр ажиллана.")
        if not await self.is_owner(ctx):
            return await ctx.send("⚠️ Зөвхөн серверийн эзэн ашиглах боломжтой!")
        
        if amount is None:
            return await ctx.send("⚠️ Мөнгөний хэмжээг заана уу! Жишээ: `!serverwith 1000`")
        
        if amount <= 0:
            return await ctx.send("⚠️ Тоо хэмжээ 0-ээс их байх ёстой!")
            
        balance = await self.get_balance(ctx.guild.id)
        if balance <= 0:
            return await ctx.send("⚠️ Серверийн банкны үлдэгдэл 0 эсвэл сөрөг байна!")
        if balance < amount:
            return await ctx.send(f"⚠️ Серверийн банкны үлдэгдэл хүрэлцэхгүй байна! Одоогийн үлдэгдэл: **{balance:,}₮**")
        
        # Аюулгүй мөнгө гаргах
        success = await self.safe_withdraw(ctx.guild.id, amount)
        if not success:
            return await ctx.send("⚠️ Мөнгө гаргахад алдаа гарлаа!")
        
        # Add money to user's personal balance
        try:
            # Get the bank cog to add money to user's bank account
            bank_cog = self.bot.get_cog('Bank')
            if bank_cog and hasattr(bank_cog, 'update_balance'):
                # Add to bank account, not economy account
                await bank_cog.update_balance('bank', ctx.author.id, amount)  # type: ignore
                await ctx.send(f"✅ {amount:,}₮ серверийн банкнаас хасагдаж, таны хувийн дансанд нэмэгдлээ!")
            else:
                # If bank cog not found, still remove from server bank but notify user
                await ctx.send(f"⚠️ {amount:,}₮ серверийн банкнаас хасагдаж, таны хувийн дансанд нэмэгдсэнгүй! (Bank систем олдсонгүй)")
        except Exception as e:
            # If adding to personal balance fails, add money back to server bank
            await self.update_balance(ctx.guild.id, amount)
            await ctx.send(f"❌ Таны хувийн дансанд мөнгө нэмэхэд алдаа гарлаа: {e}")
            return

    @commands.command(name='removeserver')
    @commands.is_owner()
    async def remove_server_command(self, ctx: commands.Context, server_id: int):
        """Серверийг бүрэн устгах команд (зөвхөн bot owner)"""
        async with get_async_db_context('serverbank') as conn:
            # Серверийн бүх эзэд болон үлдэгдлийг устгах
            async with conn.execute('SELECT COUNT(*) FROM server_bank WHERE server_id = ?', (server_id,)) as cursor:
                result = await cursor.fetchone()
                count = result[0] if result else 0
            
            if count == 0:
                return await ctx.send(f"❌ Сервер {server_id} олдсонгүй.")
            
            await conn.execute('DELETE FROM server_bank WHERE server_id = ?', (server_id,))
            await conn.commit()
        
        await ctx.send(f"🗑️ Сервер {server_id} болон түүний бүх эзэд амжилттай устгагдлаа! ({count} эзэн устгагдлаа)")

    @commands.command(name='listservers')
    @commands.is_owner()
    async def list_servers_command(self, ctx: commands.Context):
        """Бүх серверүүдийн жагсаалт (зөвхөн bot owner)"""
        async with get_async_db_context('serverbank') as conn:
            async with conn.execute('''
                SELECT server_id, COUNT(owner_id) as owner_count, SUM(balance) as total_balance 
                FROM server_bank 
                GROUP BY server_id 
                ORDER BY server_id
            ''') as cursor:
                rows = await cursor.fetchall()

        if not rows:
            return await ctx.send("❌ Серверийн банк хоосон байна.")
        
        embed = discord.Embed(
            title="📊 Серверийн банкны жагсаалт",
            color=discord.Color.blue()
        )
        
        for server_id, owner_count, total_balance in rows:
            try:
                guild = self.bot.get_guild(server_id)
                server_name = guild.name if guild else f"Unknown Server ({server_id})"
            except:
                server_name = f"Unknown Server ({server_id})"
            
            embed.add_field(
                name=f"🏛️ {server_name}",
                value=f"ID: `{server_id}`\n👥 Эзэд: {owner_count}\n💰 Үлдэгдэл: {total_balance:,}₮",
                inline=True
            )
        
        await ctx.send(embed=embed)

    @commands.command(name='fixbalance')
    @commands.is_owner()
    async def fix_balance_command(self, ctx: commands.Context, server_id: int):
        """Серверийн банкны сөрөг үлдэгдлийг засах (зөвхөн bot owner)"""
        async with get_async_db_context('serverbank') as conn:
            # Тухайн серверийн одоогийн үлдэгдэлийг авах
            async with conn.execute('SELECT SUM(balance) FROM server_bank WHERE server_id = ?', (server_id,)) as cursor:
                result = await cursor.fetchone()
                current_balance = result[0] if result and result[0] is not None else 0
            
            if current_balance >= 0:
                return await ctx.send(f"✅ Сервер {server_id}-ийн үлдэгдэл аль хэдийн зөв байна: **{current_balance:,}₮**")
            
            # Сөрөг үлдэгдлийг 0 болгох
            fix_amount = -current_balance
            await conn.execute('UPDATE server_bank SET balance = 0 WHERE server_id = ?', (server_id,))
            await conn.commit()
            
            await ctx.send(f"🔧 Сервер {server_id}-ийн үлдэгдэл засагдлаа!\n"
                          f"⬇️ Өмнөх үлдэгдэл: **{current_balance:,}₮**\n"
                          f"⬆️ Шинэ үлдэгдэл: **0₮**")

    async def cog_command_error(self, ctx: commands.Context, error: Exception):
        """Handle errors for all commands in this cog"""
        if isinstance(error, commands.CheckFailure):
            await ctx.send("⚠️ Зөвхөн **серверийн эзэд** ашиглах боломжтой.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("⚠️ Мөнгөний хэмжээг заана уу! Жишээ: `!serverwith 1000`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("⚠️ Зөв тоо оруулна уу!")
        else:
            await ctx.send(f"❌ Алдаа гарлаа: `{error}`")

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

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerBank(bot))
