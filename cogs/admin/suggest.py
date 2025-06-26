import discord
import random
import sqlite3
from discord.ext import commands
import asyncio
from ..utils.db_helper import get_suggestions_db
from ..utils.channel import is_channel_enabled

class Suggest(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        try:
            self.db = get_suggestions_db()
        except ImportError:
            self.db = sqlite3.connect("data/suggestions.db")
        self.cursor = self.db.cursor()
        self.create_tables()

    def create_tables(self):
        """Өгөгдлийн сангийн хүснэгтийг зөв бүтэцтэй үүсгэх"""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                suggestion TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'Pending',
                author_id INTEGER NOT NULL
            )
        """)
        self.db.commit()

    SUGGESTION_CHANNEL_ID = 1350771239194726431  
    UPDATES_CHANNEL_ID = 1350771327790747670  
    DELETE_DELAY = 5  

    async def process_suggestion(self, ctx: commands.Context, suggestion: str, description: str):
        """Санал хадгалж, embed хэлбэрээр илгээх"""
        self.cursor.execute("INSERT INTO suggestions (suggestion, description, author_id) VALUES (?, ?, ?)",
                            (suggestion, description, ctx.author.id))
        self.db.commit()
        
        suggestion_id = self.cursor.lastrowid

        embed = discord.Embed(title="📜 Шинэ санал!", color=discord.Color.blue())
        embed.add_field(name="📢 Санал:", value=f"**{suggestion}**", inline=False)
        embed.add_field(name="💡 Тайлбар:", value=f"{description}", inline=False)
        avatar_url = ctx.author.avatar.url if ctx.author.avatar else None
        embed.set_footer(text=f"ID: {suggestion_id} • Санал гаргасан: {ctx.author.display_name}", icon_url=avatar_url)

        suggestion_message = await ctx.channel.send(embed=embed)
        await suggestion_message.add_reaction("✅")
        await suggestion_message.add_reaction("❌")
        await suggestion_message.add_reaction("🏆")

        # Устгах үед алдаа гарахаас сэргийлэх
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass

    @commands.command(name="suggest")
    async def suggest(self, ctx: commands.Context, *, message: str):
        """Хэрэглэгч зөвхөн `msuggest` ашиглаж санал оруулж болно"""
        
        if ctx.channel.id != self.SUGGESTION_CHANNEL_ID:
            return
        
        if not ctx.guild or not await is_channel_enabled(ctx.guild.id, ctx.channel.id):
            await ctx.send("Энэ channel-д команд ашиглах боломжгүй!")
            return

        if "|" not in message:
            warning_message = await ctx.send("⚠️ **Та тайлбар бичээгүй байна!**\n📌 Зөв форматаар бичнэ үү: `msuggest <санал> | <тайлбар>`")
            try:
                await ctx.message.delete()
            except discord.NotFound:
                pass
            await warning_message.delete(delay=5)
            return

        suggestion, description = map(str.strip, message.split("|", 1))
        await self.process_suggestion(ctx, suggestion, description)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """#suggestions сувгаас зөвшөөрөгдөөгүй мессежийг устгана"""
        if message.channel.id != self.SUGGESTION_CHANNEL_ID:
            return  # Зөвхөн саналын сувагт хяналт тавина

        ctx = await self.bot.get_context(message)
        if ctx.command and ctx.command.name == "suggest":
            return  # **`!suggest` командыг үлдээх**

        if message.embeds and message.author == self.bot.user:
            return  # **process_suggestion функцээр үүсгэсэн embed мессежийг үлдээх**

        # **Сануулга мессежийг устгахгүй үлдээх**
        if message.author.bot and "⚠️" in message.content:
            return  # Бот өөрөө илгээсэн анхааруулгын мессежийг устгахгүй

        # **Бусад бүх ботын мессежийг устгах (Slot Machine, Coin Toss гэх мэт)**
        if message.author.bot:
            try:
                await message.delete()
            except discord.NotFound:
                pass
            return

        # **Бусад бүх хэрэглэгчийн мессежийг устгана**
        try:
            await message.delete()
        except discord.NotFound:
            return

        # **Сануулга мессеж илгээх**
        warning = await message.channel.send(
            f"⚠️ **Энэ суваг зөвхөн `msuggest` командаар санал авах зориулалттай!**"
        )

        # **5 секунд хүлээж байгаад устгах**
        await asyncio.sleep(self.DELETE_DELAY)
        try:
            await warning.delete()
        except discord.NotFound:
            pass  # Мессеж аль хэдийн устсан бол дахин устгахгүй

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.abc.User):
        """Админ '🏆' дарсан үед саналыг батлах"""
        if user.bot or reaction.message.channel.id != self.SUGGESTION_CHANNEL_ID:
            return
        
        if str(reaction.emoji) == "🏆":
            embed = reaction.message.embeds[0]
            suggestion_text = embed.fields[0].value
            footer_text = embed.footer.text if embed.footer and embed.footer.text else None
            if footer_text and "ID: " in footer_text:
                suggestion_id = int(footer_text.split("ID: ")[1].split(" • ")[0])
            else:
                # If footer is missing or malformed, skip processing
                return

            # ✅ **Өгөгдлийн сангаас тайлбарыг татах**
            self.cursor.execute("SELECT description FROM suggestions WHERE id = ?", (suggestion_id,))
            result = self.cursor.fetchone()
            description_text = result[0] if result else "Тайлбар байхгүй"

            # ✅ **Саналын төлөв шинэчлэх**
            self.cursor.execute("UPDATE suggestions SET status = ? WHERE id = ?", ("Approved", suggestion_id))
            self.db.commit()
            
            updates_channel = self.bot.get_channel(self.UPDATES_CHANNEL_ID)
            if isinstance(updates_channel, discord.TextChannel):
                new_embed = discord.Embed(title="🚀 Шинэ хөгжүүлэлт эхэллээ!", color=discord.Color.green())
                new_embed.add_field(name="📢 Санал:", value=suggestion_text, inline=False)
                new_embed.add_field(name="💡 Тайлбар:", value=description_text, inline=False)
                new_embed.add_field(name="📌 **Төлөв:**", value="🟡 Хийгдэж байна...", inline=False)
                new_embed.set_footer(
                    text=f"ID: {suggestion_id} • Баталсан: {user.display_name}",
                    icon_url=user.display_avatar.url
                )
                await updates_channel.send(embed=new_embed)

    @commands.command(name="update-status")
    @commands.has_permissions(manage_messages=True)
    async def update_status(self, ctx: commands.Context, suggestion_id: int, *, new_status: str):
        """Админ саналуудын төлөв шинэчлэх боломжтой"""
        self.cursor.execute("UPDATE suggestions SET status = ? WHERE id = ?", (new_status, suggestion_id))
        self.db.commit()
        
        msg = await ctx.send(f"✅ **Саналын төлөв амжилттай шинэчлэгдлээ!** `{suggestion_id}` → {new_status}")
        await msg.delete(delay=2)
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass

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
    await bot.add_cog(Suggest(bot))