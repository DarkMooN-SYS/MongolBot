import discord
from discord.ext import commands, tasks
import random
import asyncio
from datetime import datetime, timedelta
import sqlite3
import pytz
from ..utils.db_helper import get_db_path

# SQLite өгөгдлийн сан үүсгэх
def get_giveaway_connection():
    return sqlite3.connect(get_db_path('giveaways'))

# Initialize database
with get_giveaway_connection() as conn:
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS giveaways (
                 message_id INTEGER PRIMARY KEY,
                 channel_id INTEGER,
                 end_time TEXT,
                 prize TEXT,
                 winners_count INTEGER)
              ''')
    conn.commit()

class GiveawayModal(discord.ui.Modal):
    def __init__(self, is_owner_giveaway=False):
        super().__init__(title="🎉 Giveaway үүсгэх!")
        self.is_owner_giveaway = is_owner_giveaway  

        self.duration = discord.ui.TextInput(
            label="Үргэлжлэх хугацаа (минутаар)", placeholder="e.g., 5", required=True
        )
        self.winners = discord.ui.TextInput(
            label="Ялагчдын тоо", placeholder="e.g., 2", required=True
        )
        self.prize = discord.ui.TextInput(
            label="Шагнал", placeholder="e.g., 100000₮ эсвэл Nitro Boost", required=True
        )

        self.add_item(self.duration)
        self.add_item(self.winners)
        self.add_item(self.prize)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            duration_minutes = int(self.duration.value)
            winners_count = int(self.winners.value)
            prize_value = self.prize.value

            if duration_minutes < 1 or winners_count < 1:
                await interaction.response.send_message("⚠️ Буруу утга оруулсан байна!", ephemeral=True)
                return

            duration_seconds = duration_minutes * 60
            start_time = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Asia/Ulaanbaatar'))
            end_time = start_time + timedelta(seconds=duration_seconds)

            participants = set()

            embed = discord.Embed(title="🎉 Giveaway эхэллээ! 🎉", color=discord.Color.blue())
            embed.add_field(name="🏆 Шагнал", value=f"{prize_value}", inline=False)
            embed.add_field(name="👥 Ялагчдын тоо", value=winners_count, inline=False)
            embed.add_field(name="⏳ Үргэлжлэх хугацаа", value=f"{duration_minutes} минут", inline=False)
            embed.add_field(name="📅 Дуусах цаг", value=end_time.strftime("%Y-%m-%d %H:%M:%S (%Z)"), inline=False)
            embed.add_field(name="👤 Нийт оролцогчид", value="0", inline=False)
            embed.set_footer(text="Доорх товчийг дарж giveaway-д оролцоорой!")
            
            giveaway_message = await interaction.channel.send(embed=embed)

            with get_giveaway_connection() as conn:
                c = conn.cursor()
                c.execute("INSERT INTO giveaways VALUES (?, ?, ?, ?, ?)",
                          (giveaway_message.id, interaction.channel.id, end_time.isoformat(), prize_value, winners_count))
                conn.commit()

            # Giveaway-д оролцох товч (custom_id заавал нэмэх)
            enter_button = discord.ui.Button(label="📝 Оролцох", style=discord.ButtonStyle.primary, custom_id="enter_giveaway")

            async def enter_giveaway_callback(button_interaction: discord.Interaction):
                if button_interaction.user.id in participants:
                    await button_interaction.response.send_message("⚠️ Та giveaway-д аль хэдийн орсон байна!", ephemeral=True)
                else:
                    participants.add(button_interaction.user.id)
                    embed.set_field_at(4, name="👤 Нийт оролцогчид", value=str(len(participants)), inline=False)
                    await giveaway_message.edit(embed=embed)
                    await button_interaction.response.send_message("✅ Та giveaway-д оролцлоо!", ephemeral=True)

            enter_button.callback = enter_giveaway_callback

            # Persistent View тохируулах
            view = discord.ui.View(timeout=None)
            view.add_item(enter_button)

            # Ботод persistent view бүртгэх
            interaction.client.add_view(view)

            await giveaway_message.edit(view=view)

            # Giveaway хугацаа дуусахыг хүлээх
            await asyncio.sleep(duration_seconds)

            if participants:
                winners = random.sample(list(participants), min(len(participants), winners_count))
                winner_mentions = ', '.join([f'<@{winner}>' for winner in winners])
                await interaction.channel.send(f"🎉 **Giveaway дууслаа!** 🎉\n🏆 **Ялагчид:** {winner_mentions}\n🎁 **Шагнал:** {prize_value}\n👤 **Нийт оролцогчид:** {len(participants)}")
            else:
                await interaction.channel.send("🎉 **Giveaway дууслаа!** 🎉\n⚠️ **Хэн ч giveaway-д оролцоогүй байна.**")

            with get_giveaway_connection() as conn:
                c = conn.cursor()
                c.execute("DELETE FROM giveaways WHERE message_id = ?", (giveaway_message.id,))
                conn.commit()
        except ValueError:
            await interaction.response.send_message("⚠️ Зөв тоон утга оруулна уу!", ephemeral=True)

# Giveaway командууд
class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='giveaway', help='Starts a giveaway. Admins only.')
    @commands.has_permissions(administrator=True)
    async def giveaway(self, ctx):
        start_button = discord.ui.Button(label="Start Giveaway", style=discord.ButtonStyle.success, custom_id="start_giveaway")

        async def start_giveaway_callback(interaction: discord.Interaction):
            modal = GiveawayModal(is_owner_giveaway=False)
            await interaction.response.send_modal(modal)

        start_button.callback = start_giveaway_callback
        view = discord.ui.View(timeout=None)
        view.add_item(start_button)

        self.bot.add_view(view)
        await ctx.send("🎉 **Giveaway эхлүүлэхийн тулд доорх товчийг дарна уу!**", view=view)

async def setup(bot):
    await bot.add_cog(Giveaway(bot))