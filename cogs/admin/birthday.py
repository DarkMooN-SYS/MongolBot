import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
import threading
from datetime import datetime, timedelta
import pytz
import time
from ..utils.db_helper import get_birthdays_db

# Монголын цагийн бүс
MONGOLIA_TIMEZONE = pytz.timezone("Asia/Ulaanbaatar")

def execute_with_retry(func):
    """SQLite алдаа гарахад дахин оролдох механизм."""
    def wrapper(*args, **kwargs):
        retries = 3
        for attempt in range(retries):
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError:
                if attempt < retries - 1:
                    time.sleep(0.5)
                else:
                    raise
    return wrapper

class Birthday(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lock = threading.Lock()
        try:
            self.conn = get_birthdays_db()
        except ImportError:
            self.conn = sqlite3.connect('data/birthdays.db', check_same_thread=False)
        self.c = self.conn.cursor()
        self.create_tables()
        self.check_birthdays.start()

    @execute_with_retry
    def create_tables(self):
        """Өгөгдлийн сангийн хүснэгтүүдийг үүсгэх."""
        with self.lock:
            self.c.execute("PRAGMA journal_mode=WAL;")
            self.c.execute('''
                CREATE TABLE IF NOT EXISTS birthdays (
                    user_id INTEGER PRIMARY KEY,
                    birthday TEXT
                )
            ''')
            self.c.execute('''
                CREATE TABLE IF NOT EXISTS birthday_channels (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER
                )
            ''')
            self.c.execute('''
                CREATE TABLE IF NOT EXISTS birthday_messages (
                    guild_id INTEGER PRIMARY KEY,
                    message_template TEXT DEFAULT "Happy Birthday, {user}! 🎉 We hope you have an amazing day!"
                )
            ''')
            self.conn.commit()

    @app_commands.command(name="set_birthday", description="Set your birthday (YYYY-MM-DD).")
    async def set_birthday(self, interaction: discord.Interaction, date: str):
        """Хэрэглэгчийн төрсөн өдрийг тохируулах."""
        try:
            birthday = datetime.strptime(date, "%Y-%m-%d").date()
            with self.lock:
                self.c.execute('''
                    INSERT OR REPLACE INTO birthdays (user_id, birthday)
                    VALUES (?, ?)
                ''', (interaction.user.id, str(birthday)))
                self.conn.commit()
            await interaction.response.send_message(f"Таны төрсөн өдөр **{birthday}** болгон тохируулсан. 🎉", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Огнооны формат буруу. **YYYY-MM-DD**-г ашиглана уу.", ephemeral=True)

    @app_commands.command(name="set_birthday_channel", description="Төрсөн өдрийн мэдэгдэлийн сувгийг тохируулах.")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_birthday_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Төрсөн өдрийн зарлалын сувгийг тохируулах."""
        if not channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message("Би энэ суваг руу мессеж илгээх эрхгүй байна.", ephemeral=True)
            return

        self.c.execute('''
            INSERT OR REPLACE INTO birthday_channels (guild_id, channel_id)
            VALUES (?, ?)
        ''', (interaction.guild.id, channel.id))
        self.conn.commit()
        await interaction.response.send_message(f"🎂 Төрсөн өдрийн зарыг одоо {channel.mention}-д илгээх болно.")

    @app_commands.command(name="set_birthday_message", description="Set a custom birthday message.")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_birthday_message(self, interaction: discord.Interaction, message: str):
        """
        Төрсөн өдрийн мессежийг тохируулах.
        """
        if '{mention}' not in message and '{user}' not in message:
            await interaction.response.send_message("Загварт **{mention}** эсвэл **{user}** орсон байх ёстой.", ephemeral=True)
            return

        self.c.execute('''
            INSERT OR REPLACE INTO birthday_messages (guild_id, message_template)
            VALUES (?, ?)
        ''', (interaction.guild.id, message))
        self.conn.commit()
        await interaction.response.send_message(f"**Төрсөн өдрийн захиасыг тохируулсан! 🎂\nЗагвар:**\n{message}")

    @app_commands.command(name="upcoming_birthdays", description="Удахгүй болох төрсөн өдрийн жагсаалтыг харах.")
    async def upcoming_birthdays(self, interaction: discord.Interaction):
        """Ойрын төрсөн өдрүүдийг харуулах."""
        today = datetime.now(MONGOLIA_TIMEZONE).date()
        upcoming = self.c.execute('''
            SELECT user_id, birthday FROM birthdays
            WHERE STRFTIME('%m-%d', birthday) >= STRFTIME('%m-%d', ?)
            ORDER BY STRFTIME('%m-%d', birthday) ASC
        ''', (today,)).fetchall()

        if upcoming:
            embed = discord.Embed(
                title="🎂 Удахгүй болох төрсөн өдрүүд",
                color=discord.Color.blue(),
                timestamp=datetime.now(MONGOLIA_TIMEZONE)
            )
            for user_id, birthday in upcoming:
                user = self.bot.get_user(user_id)
                if user:
                    embed.add_field(name=user.name, value=birthday, inline=False)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("Удахгүй болох төрсөн өдөр олдсонгүй!")

    @tasks.loop(hours=24)
    async def check_birthdays(self):
        """Өнөөдөр төрсөн өдрийг шалгах, зарлах."""
        today = datetime.now(MONGOLIA_TIMEZONE).date()
        with self.lock:
            birthdays_today = self.c.execute('''
                SELECT user_id FROM birthdays
                WHERE STRFTIME('%m-%d', birthday) = STRFTIME('%m-%d', ?)
            ''', (today,)).fetchall()

        for user_id, in birthdays_today:
            user = self.bot.get_user(user_id)
            if user:
                for guild in self.bot.guilds:
                    with self.lock:
                        channel_data = self.c.execute('''
                            SELECT channel_id FROM birthday_channels WHERE guild_id = ?
                        ''', (guild.id,)).fetchone()
                        message_data = self.c.execute('''
                            SELECT message_template FROM birthday_messages WHERE guild_id = ?
                        ''', (guild.id,)).fetchone()
                    
                    if not channel_data:
                        continue
                    
                    birthday_channel = guild.get_channel(channel_data[0])
                    if not birthday_channel:
                        continue

                    message_template = message_data[0] if message_data else "Төрсөн өдрийн мэнд хүргэе, {mention}! 🎉"
                    message = message_template.format(mention=user.mention, user=user.display_name)
                    embed = discord.Embed(
                        title=f"🎉 Happy Birthday, {user.display_name}! 🎂",
                        description=message,
                        color=discord.Color.gold(),
                        timestamp=datetime.now(MONGOLIA_TIMEZONE)
                    )
                    embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else "")
                    await birthday_channel.send(content=user.mention, embed=embed)

    @check_birthdays.before_loop
    async def before_check_birthdays(self):
        now = datetime.now(MONGOLIA_TIMEZONE)
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        await discord.utils.sleep_until(next_midnight)

    def cog_unload(self):
        """Cog-ийг хаах үед өгөгдлийн сангийн холболтыг хаах."""
        with self.lock:
            self.conn.commit()
            self.conn.close()

async def setup(bot):
    await bot.add_cog(Birthday(bot))