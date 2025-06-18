import discord
import random
import sqlite3
from discord.ext import commands
import asyncio
from ..utils.db_helper import get_suggestions_db

class Suggest(commands.Cog):
    def __init__(self, bot):
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

    async def process_suggestion(self, ctx, suggestion, description):
        """Санал хадгалж, embed хэлбэрээр илгээх"""
        self.cursor.execute("INSERT INTO suggestions (suggestion, description, author_id) VALUES (?, ?, ?)",
                            (suggestion, description, ctx.author.id))
        self.db.commit()
        
        suggestion_id = self.cursor.lastrowid

        embed = discord.Embed(title="📜 Шинэ санал!", color=discord.Color.blue())
        embed.add_field(name="📢 Санал:", value=f"**{suggestion}**", inline=False)
        embed.add_field(name="💡 Тайлбар:", value=f"{description}", inline=False)
        embed.set_footer(text=f"ID: {suggestion_id} • Санал гаргасан: {ctx.author.display_name}", icon_url=ctx.author.avatar.url)

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
    async def suggest(self, ctx, *, message):
        """Хэрэглэгч зөвхөн `msuggest` ашиглаж санал оруулж болно"""
        
        if ctx.channel.id != self.SUGGESTION_CHANNEL_ID:
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
    async def on_message(self, message):
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
    async def on_reaction_add(self, reaction, user):
        """Админ '🏆' дарсан үед саналыг батлах"""
        if user.bot or reaction.message.channel.id != self.SUGGESTION_CHANNEL_ID:
            return
        
        if str(reaction.emoji) == "🏆":
            embed = reaction.message.embeds[0]
            suggestion_text = embed.fields[0].value
            suggestion_id = int(embed.footer.text.split("ID: ")[1].split(" • ")[0])

            # ✅ **Өгөгдлийн сангаас тайлбарыг татах**
            self.cursor.execute("SELECT description FROM suggestions WHERE id = ?", (suggestion_id,))
            result = self.cursor.fetchone()
            description_text = result[0] if result else "Тайлбар байхгүй"

            # ✅ **Саналын төлөв шинэчлэх**
            self.cursor.execute("UPDATE suggestions SET status = ? WHERE id = ?", ("Approved", suggestion_id))
            self.db.commit()
            
            updates_channel = self.bot.get_channel(self.UPDATES_CHANNEL_ID)
            if updates_channel:
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
    async def update_status(self, ctx, suggestion_id: int, *, new_status):
        """Админ саналуудын төлөв шинэчлэх боломжтой"""
        self.cursor.execute("UPDATE suggestions SET status = ? WHERE id = ?", (new_status, suggestion_id))
        self.db.commit()
        
        msg = await ctx.send(f"✅ **Саналын төлөв амжилттай шинэчлэгдлээ!** `{suggestion_id}` → {new_status}")
        await msg.delete(delay=2)
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass

async def setup(bot):
    await bot.add_cog(Suggest(bot))