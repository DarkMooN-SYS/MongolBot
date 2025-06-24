import discord
from discord.ext import commands
from typing import Optional, Union
from datetime import datetime
import sqlite3
import logging
import os
from ..utils.db_helper import get_db_path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StaffAppModal(discord.ui.Modal, title='🎮 Ажилтны анкет'):
    def __init__(self, staff_channel_id: Optional[int] = None):
        super().__init__()
        self.staff_channel_id = staff_channel_id
        
        # Хувийн мэдээлэл
        self.username = discord.ui.TextInput(
            label='Таны нэр',
            placeholder='Discord дээрх таны бүтэн нэр',
            style=discord.TextStyle.short,
            required=True,
            max_length=50
        )

        self.age = discord.ui.TextInput(
            label='Таны нас',
            placeholder='Жишээ: 18',
            style=discord.TextStyle.short,
            required=True,
            max_length=2
        )

        self.experience = discord.ui.TextInput(
            label='Туршлага',
            placeholder='Discord сервер удирдсан туршлага, хэр удаан гэх мэт...',
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )

        self.skills = discord.ui.TextInput(
            label='Ур чадварууд',
            placeholder='Discord Bot, команд, серверийн тохиргоо гэх мэт...',
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )

        self.additional = discord.ui.TextInput(
            label='Нэмэлт мэдээлэл',
            placeholder='Өөрийн талаар нэмэлт мэдээлэл, цаг заваа хэрхэн зохицуулах гэх мэт...',
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )

        self.add_item(self.username)
        self.add_item(self.age)
        self.add_item(self.experience)
        self.add_item(self.skills)
        self.add_item(self.additional)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            age = int(self.age.value)
            if age < 16 or age > 99:
                await interaction.response.send_message(
                    '⚠️ Нас 16-99 хооронд байх ёстой!',
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="📝 Шинэ ажилтны анкет",
                description=f"Илгээсэн: {interaction.user.mention}",
                color=0x2ecc71,
                timestamp=datetime.now()
            )

            embed.add_field(
                name="👤 Хувийн мэдээлэл",
                value=f"**Нэр:** {self.username.value}\n**Нас:** {age}",
                inline=False
            )

            embed.add_field(
                name="📚 Туршлага",
                value=self.experience.value,
                inline=False
            )

            embed.add_field(
                name="🎯 Ур чадварууд",
                value=self.skills.value,
                inline=False
            )

            if self.additional.value:
                embed.add_field(
                    name="📌 Нэмэлт мэдээлэл",
                    value=self.additional.value,
                    inline=False
                )

            if interaction.user.avatar:
                embed.set_thumbnail(url=interaction.user.avatar.url)

            embed.set_footer(
                text=f"ID: {interaction.user.id}"
            )

            await interaction.response.defer()

            if not interaction.guild:
                await interaction.followup.send(
                    "⚠️ Энэ команд зөвхөн серверт ажиллана.",
                    ephemeral=True
                )
                return

            if not self.staff_channel_id:
                await interaction.followup.send(
                    "⚠️ Анкет хүлээн авах суваг тохируулаагүй байна.",
                    ephemeral=True
                )
                return

            staff_channel = interaction.guild.get_channel(self.staff_channel_id)
            if isinstance(staff_channel, discord.TextChannel):
                await staff_channel.send(embed=embed)
                success_embed = discord.Embed(
                    title="✅ Анкет амжилттай илгээгдлээ!",
                    description="Таны анкетыг хүлээн авлаа. Удахгүй админууд хариу өгөх болно.",
                    color=0x2ecc71
                )
                await interaction.followup.send(embed=success_embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    "⚠️ Анкет хүлээн авах суваг олдсонгүй. Админтай холбогдоно уу.",
                    ephemeral=True
                )

        except ValueError:
            await interaction.followup.send(
                "⚠️ Нас зөвхөн тоон утга байх ёстой!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in application submission: {e}")
            await interaction.followup.send(
                "⚠️ Анкет илгээх үед алдаа гарлаа. Дахин оролдоно уу.",
                ephemeral=True
            )

class ApplicationButton(discord.ui.Button):
    def __init__(self, staff_channel_id: int):
        super().__init__(
            label="📝 Анкет бөглөх",
            style=discord.ButtonStyle.primary,
            emoji="📋"
        )
        self.staff_channel_id = staff_channel_id

    async def callback(self, interaction: discord.Interaction):
        modal = StaffAppModal(self.staff_channel_id)
        await interaction.response.send_modal(modal)

class Report(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = get_db_path('staff_channels')
        self._init_db()

    def _init_db(self):
        """Initialize the database"""
        try:
            with sqlite3.connect(self.db_path) as db:
                c = db.cursor()
                c.execute('''CREATE TABLE IF NOT EXISTS channels
                    (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)''')
                db.commit()
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")

    async def get_staff_channel(self, guild_id: int) -> Optional[int]:
        """Get staff channel ID for a guild"""
        try:
            with sqlite3.connect(self.db_path) as db:
                c = db.cursor()
                c.execute('SELECT channel_id FROM channels WHERE guild_id = ?', (guild_id,))
                result = c.fetchone()
                return result[0] if result else None
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None

    async def set_staff_channel(self, guild_id: int, channel_id: int) -> bool:
        """Set staff channel ID for a guild"""
        try:
            with sqlite3.connect(self.db_path) as db:
                c = db.cursor()
                c.execute('INSERT OR REPLACE INTO channels (guild_id, channel_id) VALUES (?, ?)',
                         (guild_id, channel_id))
                db.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False

    @commands.command(name='staffchannel')
    @commands.has_permissions(administrator=True)
    async def staff_setup(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Ажилтны анкет хүлээн авах суваг тохируулах

        Args:
            ctx: Context
            channel: Optional[discord.TextChannel], анкет хүлээн авах суваг
        """
        if not ctx.guild:
            await ctx.send("⚠️ Энэ команд зөвхөн серверт ажиллана!")
            return

        target_channel = channel or ctx.channel
        if not isinstance(target_channel, discord.TextChannel):
            await ctx.send("⚠️ Зөвхөн текст суваг сонгох боломжтой!")
            return

        if await self.set_staff_channel(ctx.guild.id, target_channel.id):
            embed = discord.Embed(
                title="✅ Амжилттай тохируулагдлаа",
                description=f"Ажилтны анкет энэ сувагт илгээгдэх болно: {target_channel.mention}",
                color=0x2ecc71
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("⚠️ Алдаа гарлаа. Дахин оролдоно уу.")

    @commands.command(name='staff')
    @commands.has_permissions(administrator=True)
    async def staff_app(self, ctx: commands.Context):
        """Ажилтны анкет бөглөх цонх үүсгэх"""
        if not ctx.guild:
            await ctx.send("⚠️ Энэ команд зөвхөн серверт ажиллана!")
            return

        staff_channel_id = await self.get_staff_channel(ctx.guild.id)
        if not staff_channel_id:
            await ctx.send("⚠️ Эхлээд `staff_setup #суваг` командаар анкет хүлээн авах суваг тохируулна уу!")
            return

        embed = discord.Embed(
            title="🎮 Ажилтны анкет",
            description=(
                "**МонголБот-д тавтай морил!**\n\n"
                "Бид шинэ ажилтан авч байна. Та доорх товчийг дарж анкет бөглөнө үү.\n\n"
                "**Шаардлага:**\n"
                "• 16-аас дээш настай\n"
                "• Discord сервер удирдсан туршлагатай\n"
                "• Идэвхтэй онлайн байх боломжтой\n"
                "• Баг хамт олонд нийцтэй\n\n"
                "**Давуу тал:**\n"
                "• VIP эрх\n"
                "• Онцгой эрх\n"
                "• Урамшуулал\n"
            ),
            color=0x3498db
        )
        
        view = discord.ui.View(timeout=None)
        view.add_item(ApplicationButton(staff_channel_id))
        await ctx.send(embed=embed, view=view)

    def cog_check(self, ctx: commands.Context) -> bool:
        # Only allow commands in guilds; channel enable check must be async elsewhere
        if not ctx.guild:
            return False
        return True

    async def cog_unload(self) -> None:
        """Clean up on cog unload"""
        pass

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Report(bot))