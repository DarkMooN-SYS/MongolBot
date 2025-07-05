import discord
from discord.ext import commands
from discord.ext.commands import Bot
from typing import Optional, List
from datetime import datetime
import sqlite3
import logging
import os
from ..utils.db_helper import get_db_path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Report(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = get_db_path('staff_channels')
        self.questions_db_path = get_db_path('staff_questions')
        self._init_db()
        self._init_questions_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as db:
                c = db.cursor()
                c.execute('''CREATE TABLE IF NOT EXISTS channels
                    (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)''')
                db.commit()
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")

    def _init_questions_db(self):
        try:
            with sqlite3.connect(self.questions_db_path) as db:
                c = db.cursor()
                c.execute('''CREATE TABLE IF NOT EXISTS staff_questions (
                    guild_id INTEGER,
                    q_order INTEGER,
                    label TEXT,
                    placeholder TEXT,
                    style TEXT,
                    required INTEGER,
                    max_length INTEGER,
                    PRIMARY KEY (guild_id, q_order)
                )''')
                db.commit()
        except sqlite3.Error as e:
            logger.error(f"Questions DB init error: {e}")

    def ensure_default_questions(self):
        """Default асуултуудыг өгөгдлийн санд (guild_id=0) автоматаар нэмэх"""
        default_questions = [
            {'label': 'Таны нэр', 'placeholder': 'Discord дээрх таны бүтэн нэр', 'style': 'short', 'required': True, 'max_length': 50},
            {'label': 'Таны нас', 'placeholder': 'Жишээ: 18', 'style': 'short', 'required': True, 'max_length': 2},
            {'label': 'Туршлага', 'placeholder': 'Discord сервер удирдсан туршлага, хэр удаан гэх мэт...', 'style': 'paragraph', 'required': True, 'max_length': 500},
            {'label': 'Ур чадварууд', 'placeholder': 'Discord Bot, команд, серверийн тохиргоо гэх мэт...', 'style': 'paragraph', 'required': True, 'max_length': 500},
            {'label': 'Нэмэлт мэдээлэл', 'placeholder': 'Өөрийн талаар нэмэлт мэдээлэл, цаг заваа хэрхэн зохицуулах гэх мэт...', 'style': 'paragraph', 'required': False, 'max_length': 500}
        ]
        try:
            with sqlite3.connect(self.questions_db_path) as db:
                c = db.cursor()
                c.execute('SELECT COUNT(*) FROM staff_questions WHERE guild_id = 0')
                count = c.fetchone()[0]
                if count == 0:
                    for i, q in enumerate(default_questions):
                        c.execute('''INSERT INTO staff_questions (guild_id, q_order, label, placeholder, style, required, max_length) VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                  (0, i+1, q['label'], q['placeholder'], q['style'], int(q['required']), q['max_length']))
                    db.commit()
        except sqlite3.Error as e:
            logger.error(f"Default questions insert error: {e}")

    def get_questions(self, guild_id: int) -> List[dict]:
        self.ensure_default_questions()
        try:
            with sqlite3.connect(self.questions_db_path) as db:
                c = db.cursor()
                c.execute('SELECT label, placeholder, style, required, max_length FROM staff_questions WHERE guild_id = ? ORDER BY q_order', (guild_id,))
                rows = c.fetchall()
                if not rows:
                    c.execute('SELECT label, placeholder, style, required, max_length FROM staff_questions WHERE guild_id = 0 ORDER BY q_order')
                    rows = c.fetchall()
                return [
                    {
                        'label': row[0],
                        'placeholder': row[1],
                        'style': row[2],
                        'required': bool(row[3]),
                        'max_length': row[4]
                    } for row in rows
                ]
        except sqlite3.Error as e:
            logger.error(f"Questions DB read error: {e}")
            return []

    def add_question(self, guild_id: int, label: str, placeholder: str, style: str, required: bool, max_length: int) -> bool:
        try:
            with sqlite3.connect(self.questions_db_path) as db:
                c = db.cursor()
                c.execute('SELECT MAX(q_order) FROM staff_questions WHERE guild_id = ?', (guild_id,))
                max_order = c.fetchone()[0] or 0
                c.execute('''INSERT INTO staff_questions (guild_id, q_order, label, placeholder, style, required, max_length) VALUES (?, ?, ?, ?, ?, ?, ?)''',
                          (guild_id, max_order + 1, label, placeholder, style, int(required), max_length))
                db.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Questions DB add error: {e}")
            return False

    @commands.command(name='staff')
    @commands.has_permissions(administrator=True)
    async def staff_app(self, ctx: commands.Context):
        if not ctx.guild:
            await ctx.send("⚠️ Энэ команд зөвхөн серверт ажиллана!")
            return
        try:
            with sqlite3.connect(self.db_path) as db:
                c = db.cursor()
                c.execute('SELECT channel_id FROM channels WHERE guild_id = ?', (ctx.guild.id,))
                row = c.fetchone()
                staff_channel_id = row[0] if row else None
        except sqlite3.Error as e:
            logger.error(f"DB error: {e}")
            staff_channel_id = None
        if not staff_channel_id:
            await ctx.send("⚠️ Эхлээд `staff_setup #суваг` командаар анкет хүлээн авах суваг тохируулна уу!")
            return
        questions = self.get_questions(ctx.guild.id)
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
        view.add_item(ApplicationButton(staff_channel_id, questions))
        await ctx.send(embed=embed, view=view)

    @commands.command(name='staffchannel')
    @commands.has_permissions(administrator=True)
    async def staff_channel_setup(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """
        Ажилтны анкет хүлээн авах суваг тохируулах
        Хэрэглэх: !staffchannel #суваг
        """
        if not ctx.guild:
            await ctx.send("⚠️ Энэ команд зөвхөн серверт ажиллана!")
            return
        target_channel = channel or ctx.channel
        if not isinstance(target_channel, discord.TextChannel):
            await ctx.send("⚠️ Зөвхөн текст суваг сонгоно уу!")
            return
        try:
            with sqlite3.connect(self.db_path) as db:
                c = db.cursor()
                c.execute('INSERT OR REPLACE INTO channels (guild_id, channel_id) VALUES (?, ?)', (ctx.guild.id, target_channel.id))
                db.commit()
            await ctx.send(f"✅ Анкет хүлээн авах суваг {target_channel.mention} болгож тохирулав.")
        except sqlite3.Error as e:
            logger.error(f"DB error: {e}")
            await ctx.send("⚠️ Өгөгдлийн санд алдаа гарлаа!")

    @commands.command(name='staffsetup')
    @commands.has_permissions(administrator=True)
    async def staff_setup(self, ctx: commands.Context):
        """
        Асуулт нэмэх button-ыг харуулах
        Хэрэглэх: !staffsetup
        """
        if not ctx.guild:
            await ctx.send("⚠️ Энэ команд зөвхөн серверт ажиллана!")
            return
        view = StaffSetupView(ctx.guild.id)
        await ctx.send("📝 Асуулт нэмэхийн тулд доорх товчийг дарна уу.", view=view)

    def cog_check(self, ctx: commands.Context) -> bool:
        return bool(ctx.guild)

    async def cog_unload(self) -> None:
        pass

class StaffAppModal(discord.ui.Modal):
    def __init__(self, staff_channel_id: Optional[int] = None, questions: Optional[List[dict]] = None):
        super().__init__(title='🎮 Ажилтны анкет')
        self.staff_channel_id = staff_channel_id
        self.inputs: List[discord.ui.TextInput] = []
        questions = questions if questions is not None else [
            {'label': 'Таны нэр', 'placeholder': 'Discord дээрх таны бүтэн нэр', 'style': 'short', 'required': True, 'max_length': 50},
            {'label': 'Таны нас', 'placeholder': 'Жишээ: 18', 'style': 'short', 'required': True, 'max_length': 2},
            {'label': 'Туршлага', 'placeholder': 'Discord сервер удирдсан туршлага, хэр удаан гэх мэт...', 'style': 'paragraph', 'required': True, 'max_length': 500},
            {'label': 'Ур чадварууд', 'placeholder': 'Discord Bot, команд, серверийн тохиргоо гэх мэт...', 'style': 'paragraph', 'required': True, 'max_length': 500},
            {'label': 'Нэмэлт мэдээлэл', 'placeholder': 'Өөрийн талаар нэмэлт мэдээлэл, цаг заваа хэрхэн зохицуулах гэх мэт...', 'style': 'paragraph', 'required': False, 'max_length': 500}
        ]
        for q in questions:
            style = discord.TextStyle.short if q.get('style', 'short') == 'short' else discord.TextStyle.paragraph
            input_field = discord.ui.TextInput(
                label=q.get('label', 'Асуулт'),
                placeholder=q.get('placeholder', ''),
                style=style,
                required=q.get('required', True),
                max_length=q.get('max_length', 100)
            )
            self.add_item(input_field)
            self.inputs.append(input_field)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            age_value = None
            for inp in self.inputs:
                if 'нас' in inp.label:
                    age_value = inp.value
                    break
            if age_value is not None:
                age = int(age_value)
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
            for inp in self.inputs:
                embed.add_field(
                    name=inp.label,
                    value=inp.value,
                    inline=False
                )
            if interaction.user.avatar:
                embed.set_thumbnail(url=interaction.user.avatar.url)
            embed.set_footer(text=f"ID: {interaction.user.id}")
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

class StaffQuestionModal(discord.ui.Modal):
    def __init__(self, guild_id: int):
        super().__init__(title='📝 Асуулт нэмэх')
        self.guild_id = guild_id
        self.label = discord.ui.TextInput(label='Асуултын гарчиг (label)', max_length=100, required=True)
        self.placeholder = discord.ui.TextInput(label='Placeholder (жишээ: Таны нэр)', max_length=200, required=True)
        self.style = discord.ui.TextInput(label='Style (short эсвэл paragraph)', max_length=10, required=True, default='short')
        self.required = discord.ui.TextInput(label='Заавал бөглөх үү? (true эсвэл false)', max_length=5, required=True, default='true')
        self.max_length = discord.ui.TextInput(label='Max length (тоо, жишээ: 50)', max_length=4, required=True, default='50')
        self.add_item(self.label)
        self.add_item(self.placeholder)
        self.add_item(self.style)
        self.add_item(self.required)
        self.add_item(self.max_length)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            style = self.style.value.strip().lower()
            if style not in ('short', 'paragraph'):
                await interaction.response.send_message('Style зөвхөн short эсвэл paragraph байх ёстой!', ephemeral=True)
                return
            required = self.required.value.strip().lower() == 'true'
            max_length = int(self.max_length.value.strip())
            # DB-д хадгалах
            bot = interaction.client
            cog = None
            if isinstance(bot, Bot):
                cog = bot.get_cog('Report')
            if cog and isinstance(cog, Report):
                success = cog.add_question(
                    self.guild_id,
                    self.label.value,
                    self.placeholder.value,
                    style,
                    required,
                    max_length
                )
                if success:
                    await interaction.response.send_message('✅ Асуулт амжилттай нэмэгдлээ!', ephemeral=True)
                else:
                    await interaction.response.send_message('❌ Асуулт нэмэхэд алдаа гарлаа!', ephemeral=True)
            else:
                await interaction.response.send_message('❌ Report cog ачаалагдаагүй байна!', ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f'❌ Алдаа: {e}', ephemeral=True)

class ApplicationButton(discord.ui.Button):
    def __init__(self, staff_channel_id: int, questions: List[dict]):
        super().__init__(
            label="📝 Анкет бөглөх",
            style=discord.ButtonStyle.primary,
            emoji="📋"
        )
        self.staff_channel_id = staff_channel_id
        self.questions = questions

    async def callback(self, interaction: discord.Interaction):
        modal = StaffAppModal(self.staff_channel_id, questions=self.questions)
        await interaction.response.send_modal(modal)

class PersistentStaffAppView(discord.ui.View):
    def __init__(self, report_cog: Report):
        super().__init__(timeout=None)
        self.report_cog = report_cog
        # Add persistent button with custom_id
        self.add_item(PersistentApplicationButton(report_cog))

class PersistentApplicationButton(discord.ui.Button):
    def __init__(self, report_cog: Report):
        super().__init__(
            label="📝 Анкет бөглөх",
            style=discord.ButtonStyle.primary,
            emoji="📋",
            custom_id="persistent_staff_app_button"
        )
        self.report_cog = report_cog

    async def callback(self, interaction: discord.Interaction):
        # Fetch staff_channel_id and questions dynamically
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("⚠️ Энэ команд зөвхөн серверт ажиллана!", ephemeral=True)
            return
        try:
            with sqlite3.connect(self.report_cog.db_path) as db:
                c = db.cursor()
                c.execute('SELECT channel_id FROM channels WHERE guild_id = ?', (guild.id,))
                row = c.fetchone()
                staff_channel_id = row[0] if row else None
        except Exception:
            staff_channel_id = None
        questions = self.report_cog.get_questions(guild.id)
        modal = StaffAppModal(staff_channel_id, questions=questions)
        await interaction.response.send_modal(modal)

class StaffSetupButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(
            label="Асуулт нэмэх",
            style=discord.ButtonStyle.primary,
            custom_id=f"staffsetup_add_question_{guild_id}"
        )
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        modal = StaffQuestionModal(self.guild_id)
        await interaction.response.send_modal(modal)

class StaffSetupView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.add_item(StaffSetupButton(guild_id))

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Report(bot))