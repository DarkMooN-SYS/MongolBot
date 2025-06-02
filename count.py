import sqlite3
import discord
from discord.ext import commands
from num2words import num2words
import roman

# Database setup
conn = sqlite3.connect("counting.db")
c = conn.cursor()

# Тоолох суваг хадгалах хүснэгт (Дээд тал нь 5 суваг)
c.execute("""
CREATE TABLE IF NOT EXISTS counting_channels (
    server_id INTEGER,
    channel_id INTEGER,
    PRIMARY KEY (server_id, channel_id)
)
""")

# Хэрэглэгчдийн мэдээлэл хадгалах хүснэгт
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER,
    server_id INTEGER,
    language TEXT DEFAULT 'english',
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    count INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, server_id)
)
""")

# Тоолол хадгалах хүснэгт (Default last_number = 0)
c.execute("""
CREATE TABLE IF NOT EXISTS counting (
    channel_id INTEGER PRIMARY KEY,
    last_number INTEGER DEFAULT 0
)
""")
conn.commit()

# Дэмжигдэх хэлнүүд
SUPPORTED_LANGUAGES = {
    "mongolian": "mn",
    "english": "en",
    "russian": "ru",
    "japanese": "ja",
    "german": "de",
    "french": "fr",
    "korean": "ko",
    "roman": "roman"
}

XP_LEVELS = {
    1: 10, 2: 25, 3: 50, 4: 100, 5: 200
}

class Counting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setcountingchannel")
    @commands.has_permissions(administrator=True)
    async def set_counting_channel(self, ctx):
        """Тоолох суваг тохируулах (Дээд тал нь 5)"""
        server_id = ctx.guild.id
        channel_id = ctx.channel.id

        with sqlite3.connect("counting.db") as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM counting_channels WHERE server_id = ?", (server_id,))
            count = c.fetchone()[0]

            if count >= 5:
                await ctx.send("⚠️ Та дээд тал нь 5 тоолох суваг тохируулах боломжтой!")
                return

            c.execute("INSERT OR IGNORE INTO counting_channels (server_id, channel_id) VALUES (?, ?)", (server_id, channel_id))
            c.execute("INSERT OR IGNORE INTO counting (channel_id, last_number) VALUES (?, ?)", (channel_id, 0))
            conn.commit()

        await ctx.send(f"✅ {ctx.channel.mention} одоо тоолох суваг боллоо!")

    @commands.command(name="setlang")
    async def set_language(self, ctx, lang: str):
        """Хэрэглэгч өөрийн тоолох хэлээ сонгох"""
        lang = lang.lower()
        if lang not in SUPPORTED_LANGUAGES:
            await ctx.send("⚠️ Боломжит хэлнүүд: " + ", ".join(SUPPORTED_LANGUAGES.keys()))
            return

        with sqlite3.connect("counting.db") as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO users (user_id, server_id, language) VALUES (?, ?, ?)",
                      (ctx.author.id, ctx.guild.id, lang))
            conn.commit()

        await ctx.send(f"✅ Та одоо {lang} хэлээр тоолж болно!")

    async def get_correct_number(self, number, lang):
        """Зөв тооны текст хувилбарыг буцаах"""
        if lang == "roman":
            return roman.toRoman(number)
        else:
            return num2words(number, lang=SUPPORTED_LANGUAGES[lang])

    async def update_xp(self, user_id, server_id):
        """XP нэмэх, level-up хийх"""
        with sqlite3.connect("counting.db") as conn:
            c = conn.cursor()
            c.execute("SELECT xp, level FROM users WHERE user_id = ? AND server_id = ?", (user_id, server_id))
            user = c.fetchone()

            if user:
                xp, level = user
                xp += 5  # Тоолох бүрт 5 XP нэмэх
                if level in XP_LEVELS and xp >= XP_LEVELS[level]:
                    level += 1
                    await self.bot.get_channel(server_id).send(f"🎉 <@{user_id}> Level {level} хүрлээ!")
                c.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ? AND server_id = ?",
                          (xp, level, user_id, server_id))
            else:
                c.execute("INSERT INTO users (user_id, server_id, xp, level) VALUES (?, ?, ?, ?)",
                          (user_id, server_id, 5, 1))
            conn.commit()

    @commands.command(name="leaderboard")
    async def leaderboard(self, ctx):
        """Хамгийн олон тоолсон хүмүүсийг харуулах"""
        with sqlite3.connect("counting.db") as conn:
            c = conn.cursor()
            c.execute("SELECT user_id, count FROM users WHERE server_id = ? ORDER BY count DESC LIMIT 10", (ctx.guild.id,))
            top_users = c.fetchall()

        if not top_users:
            await ctx.send("⚠️ Одоогоор хэн ч тоолоогүй байна!")
            return

        leaderboard_text = "\n".join([f"🥇 <@{user_id}> - {count} удаа тоолсон" for user_id, count in top_users])
        await ctx.send(f"🏆 **Counting Leaderboard**\n{leaderboard_text}")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Тоололтын мессежийг хянах"""
        if message.author.bot or not message.guild:
            return

        # Тоолох сувгуудыг шалгах
        with sqlite3.connect("counting.db") as conn:
            c = conn.cursor()
            c.execute("SELECT channel_id FROM counting_channels WHERE server_id = ?", (message.guild.id,))
            channels = [row[0] for row in c.fetchall()]

        if message.channel.id not in channels:
            return

        # Хэрэглэгчийн хэл авах
        with sqlite3.connect("counting.db") as conn:
            c = conn.cursor()
            c.execute("SELECT language FROM users WHERE user_id = ? AND server_id = ?", (message.author.id, message.guild.id))
            lang = c.fetchone()
            lang = lang[0] if lang else "english"

        # Өмнөх тоололтын мэдээлэл авах
        with sqlite3.connect("counting.db") as conn:
            c = conn.cursor()
            c.execute("SELECT last_number FROM counting WHERE channel_id = ?", (message.channel.id,))
            last_number = c.fetchone()
            last_number = last_number[0] if last_number else 0

        number = last_number + 1
        correct_word = await self.get_correct_number(number, lang)

        if message.content.lower() != correct_word.lower():
            await message.add_reaction("❌")  # Буруу бол ❌
            await message.channel.send(f"❌ Алдаа! Та **{correct_word}** гэж оруулах ёстой!")
            return

        # Зөв бол ✅
        await message.add_reaction("✅")

        # XP нэмэх, level-up хийх
        await self.update_xp(message.author.id, message.guild.id)

        # Тоолол шинэчлэх
        with sqlite3.connect("counting.db") as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO counting (channel_id, last_number) VALUES (?, ?)",
                      (message.channel.id, number))
            conn.commit()

async def setup(bot):
    await bot.add_cog(Counting(bot))