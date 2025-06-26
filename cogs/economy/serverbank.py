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
        # Update balance for all owners (shared bank)
        async with get_async_db_context('serverbank') as conn:
            await conn.execute(
                'UPDATE server_bank SET balance = balance + ? WHERE server_id = ?',
                (amount, server_id)
            )
            await conn.commit()

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

        async with get_async_db_context('serverbank') as conn:
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
    async def remove_owner_command(self, ctx: commands.Context, server_id: int, user: discord.User):
        async with get_async_db_context('serverbank') as conn:
            await conn.execute('DELETE FROM server_bank WHERE server_id = ? AND owner_id = ?', (server_id, user.id))
            await conn.commit()
        await ctx.send(f"🗑️ {user.mention} сервер {server_id}-ийн эзэмшигчээс хасагдлаа.")

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
        if balance < amount:
            return await ctx.send("⚠️ Серверийн банкны үлдэгдэл хүрэлцэхгүй байна.")
          # Remove money from server bank
        await self.update_balance(ctx.guild.id, -amount)
          # Add money to user's personal balance
        try:
            # Get the economy cog to add money to user's account
            economy_cog = self.bot.get_cog('Economy')
            if economy_cog and hasattr(economy_cog, 'update_balance'):
                # Type ignore for dynamic cog access
                await economy_cog.update_balance('economy', ctx.author.id, amount)  # type: ignore
                await ctx.send(f"✅ {amount:,}₮ серверийн банкнаас хасагдаж, таны хувийн дансанд нэмэгдлээ!")
            else:
                # If economy cog not found, still remove from server bank but notify user
                await ctx.send(f"⚠️ {amount:,}₮ серверийн банкнаас хасагдлаа! (Economy систем олдсонгүй)")
        except Exception as e:
            # If adding to personal balance fails, add money back to server bank
            await self.update_balance(ctx.guild.id, amount)
            await ctx.send(f"❌ Таны хувийн дансанд мөнгө нэмэхэд алдаа гарлаа: {e}")
            return

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
