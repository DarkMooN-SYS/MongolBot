import discord
from discord.ext import commands, tasks
import random
import asyncio
from datetime import datetime, timedelta
import sqlite3
import pytz
from typing import Optional, Set, List, Union
from ..utils.db_helper import get_db_path
from ..utils.database import get_async_connection
from cogs.utils.channel import is_channel_enabled

# Channel шалгах функц
def is_valid_giveaway_channel(channel) -> bool:  # type: ignore
    """Giveaway зохион байгуулж болох арнал эсэхийг шалгах"""
    if channel is None:
        return False
    
    # DM channel-ийг хасах
    if isinstance(channel, discord.DMChannel):
        return False
    
    # Category channel болон Forum channel-ийг хасах
    if isinstance(channel, (discord.CategoryChannel, discord.ForumChannel)):
        return False
    
    # Send method байгаа эсэхийг шалгах
    if not hasattr(channel, 'send'):
        return False
        
    return True

# Persistent View класс
class GiveawaySelectView(discord.ui.View):
    def __init__(self, is_owner: bool = False):
        super().__init__(timeout=None)
        self.add_item(GiveawayTypeSelect(is_owner=is_owner))

# Giveaway-ийн ангилал сонгох Select Menu
class GiveawayTypeSelect(discord.ui.Select):
    def __init__(self, is_owner: bool = False):
        self.is_owner = is_owner
        
        options = [
            discord.SelectOption(
                label="💰 Мөнгөн шагнал",
                description="Монгол төгрөгөөр мөнгөн шагнал",
                emoji="💰",
                value="money"
            ),
            discord.SelectOption(
                label="🎮 Nitro/Gaming",
                description="Discord Nitro эсвэл тоглоомын шагнал",
                emoji="🎮",
                value="gaming"
            ),
            discord.SelectOption(
                label="🎁 Бусад шагнал",
                description="Бусад төрлийн шагнал",
                emoji="🎁",
                value="other"
            )
        ]
        
        if is_owner:
            options.append(
                discord.SelectOption(
                    label="👑 Онцгой шагнал",
                    description="Owner-ийн тусгай шагнал",
                    emoji="👑",
                    value="special"
                )
            )
        
        custom_id = f"giveaway_type_select_{'owner' if is_owner else 'admin'}"
        
        super().__init__(
            placeholder="Giveaway-ийн төрлийг сонгоно уу...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=custom_id
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        selected = self.values[0]
        
        # Сонгосон төрлийн дагуу modal үүсгэх
        if selected == "money":
            modal = MoneyGiveawayModal(is_owner_giveaway=self.is_owner)
        elif selected == "gaming":
            modal = GamingGiveawayModal(is_owner_giveaway=self.is_owner)
        elif selected == "special" and self.is_owner:
            modal = SpecialGiveawayModal(is_owner_giveaway=True)
        else:
            modal = GiveawayModal(is_owner_giveaway=self.is_owner)
            
        await interaction.response.send_modal(modal)

# Мөнгөн шагналын тусгай Modal
class MoneyGiveawayModal(discord.ui.Modal):
    def __init__(self, is_owner_giveaway: bool = False):
        super().__init__(title="💰 Мөнгөн шагналын Giveaway")
        self.is_owner_giveaway = is_owner_giveaway

        self.duration = discord.ui.TextInput(
            label="Үргэлжлэх хугацаа (минутаар)", placeholder="e.g., 5", required=True
        )
        self.winners = discord.ui.TextInput(
            label="Ялагчдын тоо", placeholder="e.g., 2", required=True
        )
        self.amount = discord.ui.TextInput(
            label="Мөнгөн дүн (төгрөгөөр)", 
            placeholder="e.g., 50000 (автоматаар ₮ нэмэгдэнэ)", 
            required=True
        )
        
        if self.is_owner_giveaway:
            self.requirement = discord.ui.TextInput(
                label="Тусгай шаардлага (заавал биш)", 
                placeholder="e.g., Server boost хийх, роль авах гэх мэт", 
                required=False
            )
            self.add_item(self.requirement)

        self.add_item(self.duration)
        self.add_item(self.winners)
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            duration_minutes = int(self.duration.value)
            winners_count = int(self.winners.value)
              # Мөнгөн дүнг форматлах
            try:
                amount_clean = self.amount.value.replace(',', '').replace(' ', '').strip()
                if amount_clean.replace('.', '').isdigit():
                    amount_float = float(amount_clean)
                    if amount_float == int(amount_float):
                        prize_value = f"{int(amount_float):,}₮".replace(',', ' ')
                    else:
                        prize_value = f"{amount_float:,.2f}₮".replace(',', ' ')
                else:
                    prize_value = self.amount.value + "₮"
            except:
                prize_value = self.amount.value + "₮"
            
            await self._create_giveaway(interaction, duration_minutes, winners_count, prize_value)
        except ValueError:
            await interaction.response.send_message("⚠️ Зөв тоон утга оруулна уу!", ephemeral=True)

    async def _create_giveaway(self, interaction: discord.Interaction, duration_minutes: int, winners_count: int, prize_value: str) -> None:
        # Respond immediately to avoid interaction timeout
        await interaction.response.send_message("✅ Мөнгөн шагналын giveaway бэлдэж байна...", ephemeral=True)
        
        # Giveaway үүсгэх ерөнхий логик (дараа нь бусад Modal-д ч ашиглана)
        if duration_minutes < 1 or winners_count < 1:
            await interaction.followup.send("⚠️ Буруу утга оруулсан байна!", ephemeral=True)
            return

        duration_seconds = duration_minutes * 60
        start_time = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Asia/Ulaanbaatar'))
        end_time = start_time + timedelta(seconds=duration_seconds)
        
        participants: Set[int] = set()

        if not is_valid_giveaway_channel(interaction.channel):
            await interaction.followup.send("⚠️ Энэ арналд giveaway зохион байгуулах боломжгүй байна!", ephemeral=True)
            return        # Type assertion for type checking
        assert interaction.channel is not None
        channel = interaction.channel
        
        # Send method-тэй эсэх болон channel төрөл шалгах
        if (
            not hasattr(channel, 'send')
            or isinstance(channel, (discord.CategoryChannel, discord.ForumChannel))
        ):
            await interaction.followup.send("⚠️ Энэ арналд мессеж илгээх боломжгүй байна!", ephemeral=True)
            return

        embed = discord.Embed(
            title="💰 Мөнгөн шагналын Giveaway эхэллээ! 💰" if not self.is_owner_giveaway else "👑💰 Owner Мөнгөн шагнал эхэллээ! 💰👑",
            color=discord.Color.green() if not self.is_owner_giveaway else discord.Color.gold()
        )
        embed.add_field(name="💰 Мөнгөн шагнал", value=f"{prize_value}", inline=False)
        embed.add_field(name="👥 Ялагчдын тоо", value=winners_count, inline=False)
        embed.add_field(name="⏳ Үргэлжлэх хугацаа", value=f"{duration_minutes} минут", inline=False)
        embed.add_field(name="📅 Дуусах цаг", value=end_time.strftime("%Y-%m-%d %H:%M:%S (%Z)"), inline=False)
        embed.add_field(name="👤 Нийт оролцогчид", value="0", inline=False)
        
        if self.is_owner_giveaway and hasattr(self, 'requirement') and self.requirement.value:
            embed.add_field(name="📋 Тусгай шаардлага", value=self.requirement.value, inline=False)
            embed.set_footer(text="Доорх товчийг дарж giveaway-д оролцоорой!")
        
        try:
            giveaway_message = await channel.send(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ Мессеж илгээхэд алдаа гарлаа: {str(e)}", ephemeral=True)
            return

        with get_giveaway_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO giveaways VALUES (?, ?, ?, ?, ?)",
                      (giveaway_message.id, channel.id, end_time.isoformat(), prize_value, winners_count))
            conn.commit()

        enter_button = discord.ui.Button(
            label="💰 Мөнгөн шагналд оролцох",
            style=discord.ButtonStyle.success, 
            custom_id="enter_money_giveaway"
        )

        async def enter_giveaway_callback(interaction: discord.Interaction) -> None:
            if interaction.user.id in participants:
                await interaction.response.send_message("⚠️ Та giveaway-д аль хэдийн орсон байна!", ephemeral=True)
            else:
                # Эхлээд response илгээх
                await interaction.response.send_message("💰 Та мөнгөн шагналын giveaway-д оролцлоо!", ephemeral=True)
                
                # Дараа нь participants-д нэмж embed update хийх
                participants.add(interaction.user.id)
                participant_field_index = 4 if not (self.is_owner_giveaway and hasattr(self, 'requirement') and self.requirement.value) else 5
                embed.set_field_at(participant_field_index, name="👤 Нийт оролцогчид", value=str(len(participants)), inline=False)
                await giveaway_message.edit(embed=embed)

        enter_button.callback = enter_giveaway_callback
        view = discord.ui.View(timeout=None)
        view.add_item(enter_button)
        interaction.client.add_view(view)
        await giveaway_message.edit(view=view)

        await asyncio.sleep(duration_seconds)# Use channel.send instead of interaction.followup due to 15-minute timeout
        if participants:
            winners = random.sample(list(participants), min(len(participants), winners_count))
            winner_mentions = ', '.join([f'<@{winner}>' for winner in winners])
            
            # Owner giveaway бол мөнгөн шагналыг ялагчдад автоматаар нэмэх
            money_added_results = []
            if self.is_owner_giveaway:
                # Prize-аас зөвхөн тоог гаргаж авах
                try:
                    # ₮ тэмдэгт болон зайнуудыг арилгах
                    clean_prize = prize_value.replace('₮', '').replace(' ', '').replace(',', '')
                    money_amount = int(clean_prize)
                    
                    # Ялагч бүрт мөнгө нэмэх
                    for winner_id in winners:
                        success = await add_money_to_economy(winner_id, money_amount)
                        money_added_results.append(success)
                        
                    if all(money_added_results):
                        money_status = f"\n💳 **{money_amount:,}₮ ялагч бүрийн халаасанд автоматаар нэмэгдлээ!**"
                    else:
                        money_status = f"\n⚠️ **Зарим ялагчийн халаасанд мөнгө нэмэхэд алдаа гарлаа.**"
                except (ValueError, AttributeError):
                    money_status = f"\n⚠️ **Мөнгөн шагналыг автоматаар нэмэх боломжгүй байна.**"
            else:
                money_status = ""
            
            end_msg = f"💰 **Мөнгөн шагналын Giveaway дууслаа!** 💰\n🏆 **Ялагчид:** {winner_mentions}\n💰 **Шагнал:** {prize_value}\n👤 **Нийт оролцогчид:** {len(participants)}{money_status}"
            try:
                await channel.send(end_msg)
            except Exception as e:
                print(f"Error sending giveaway end message: {e}")
        else:
            try:
                await channel.send("💰 **Мөнгөн шагналын Giveaway дууслаа!** 💰\n⚠️ **Хэн ч giveaway-д оролцоогүй байна.**")
            except Exception as e:
                print(f"Error sending giveaway end message: {e}")

        with get_giveaway_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM giveaways WHERE message_id = ?", (giveaway_message.id,))
            conn.commit()

# Gaming шагналын Modal
class GamingGiveawayModal(discord.ui.Modal):
    def __init__(self, is_owner_giveaway: bool = False):
        super().__init__(title="🎮 Gaming шагналын Giveaway")
        self.is_owner_giveaway = is_owner_giveaway

        self.duration = discord.ui.TextInput(
            label="Үргэлжлэх хугацаа (минутаар)", placeholder="e.g., 10", required=True
        )
        self.winners = discord.ui.TextInput(
            label="Ялагчдын тоо", placeholder="e.g., 1", required=True
        )
        self.game_prize = discord.ui.TextInput(
            label="Gaming шагнал", 
            placeholder="e.g., Discord Nitro, Steam Gift Card", 
            required=True
        )

        self.add_item(self.duration)
        self.add_item(self.winners)
        self.add_item(self.game_prize)

    async def on_submit(self, interaction: discord.Interaction):
        # Gaming giveaway-ийн логик энд
        await interaction.response.send_message("🎮 Gaming Giveaway удахгүй нэмэгдэнэ!", ephemeral=True)

# Special шагналын Modal (зөвхөн owner)
class SpecialGiveawayModal(discord.ui.Modal):
    def __init__(self, is_owner_giveaway: bool = True):
        super().__init__(title="👑 Онцгой шагналын Giveaway")
        self.is_owner_giveaway = is_owner_giveaway

        self.duration = discord.ui.TextInput(
            label="Үргэлжлэх хугацаа (минутаар)", placeholder="e.g., 30", required=True
        )
        self.winners = discord.ui.TextInput(
            label="Ялагчдын тоо", placeholder="e.g., 1", required=True
        )
        self.special_prize = discord.ui.TextInput(
            label="Онцгой шагнал", 
            placeholder="e.g., VIP статус, Тусгай роль", 
            required=True
        )

        self.add_item(self.duration)
        self.add_item(self.winners)
        self.add_item(self.special_prize)

    async def on_submit(self, interaction: discord.Interaction):
        # Special giveaway-ийн логик энд
        await interaction.response.send_message("👑 Онцгой Giveaway удахгүй нэмэгдэнэ!", ephemeral=True)

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
    def __init__(self, is_owner_giveaway: bool = False):
        super().__init__(title="🎉 Giveaway үүсгэх!")
        self.is_owner_giveaway = is_owner_giveaway

        self.duration = discord.ui.TextInput(
            label="Үргэлжлэх хугацаа (минутаар)", placeholder="e.g., 5", required=True
        )
        self.winners = discord.ui.TextInput(
            label="Ялагчдын тоо", placeholder="e.g., 2", required=True
        )        
        self.prize = discord.ui.TextInput(
            label="Шагнал", 
            placeholder="e.g., 100000 (автоматаар ₮ нэмэгдэнэ) эсвэл Nitro Boost" if is_owner_giveaway else "e.g., 100000₮ эсвэл Nitro Boost", 
            required=True
        )
        
        # Owner giveaway бол тусгай шаардлага field нэмэх
        if self.is_owner_giveaway:
            self.requirement = discord.ui.TextInput(
                label="Тусгай шаардлага (заавал биш)", 
                placeholder="e.g., Server boost хийх, роль авах гэх мэт", 
                required=False
            )
            self.add_item(self.requirement)

        self.add_item(self.duration)
        self.add_item(self.winners)
        self.add_item(self.prize)

    async def on_submit(self, interaction: discord.Interaction):
        # Respond immediately to avoid interaction timeout
        await interaction.response.send_message("✅ Giveaway бэлдэж байна...", ephemeral=True)
        
        try:
            duration_minutes = int(self.duration.value)
            winners_count = int(self.winners.value)
            prize_value = self.prize.value

            # Owner giveaway бол шагналын утгыг шалгаж монгол төгрөг нэмэх
            if self.is_owner_giveaway:
                # Хэрэв зөвхөн тоо оруулсан бол монгол төгрөг нэмэх
                try:
                    # Зай болон орон нутгийн тэмдэгтүүдийг арилгах
                    clean_prize = prize_value.replace(',', '').replace(' ', '').strip()
                    
                    # Хэрэв зөвхөн тоо бол
                    if clean_prize.isdigit():
                        # Тооны утгыг форматлаж монгол төгрөг нэмэх
                        amount = int(clean_prize)
                        prize_value = f"{amount:,}₮".replace(',', ' ')
                    # Хэрэв аль хэдийн ₮ тэмдэгт агуулсан бол
                    elif '₮' not in prize_value and clean_prize.replace('.', '').isdigit():
                        # Аравтын бутархай тоо байж болно
                        amount = float(clean_prize)
                        if amount == int(amount):  # Бүхэл тоо бол
                            prize_value = f"{int(amount):,}₮".replace(',', ' ')
                        else:  # Аравтын бутархай бол
                            prize_value = f"{amount:,.2f}₮".replace(',', ' ')
                except ValueError:
                    # Хэрэв тоо биш утга бол анхны утгыг хэрэглэнэ
                    pass

            if duration_minutes < 1 or winners_count < 1:
                await interaction.followup.send("⚠️ Буруу утга оруулсан байна!", ephemeral=True)
                return

            duration_seconds = duration_minutes * 60
            start_time = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Asia/Ulaanbaatar'))
            end_time = start_time + timedelta(seconds=duration_seconds)

            participants: Set[int] = set()            # Check if interaction channel is valid for giveaway
            if not is_valid_giveaway_channel(interaction.channel):
                await interaction.followup.send("⚠️ Энэ арналд giveaway зохион байгуулах боломжгүй байна!", ephemeral=True)
                return            # Type assertion for type checking
            assert interaction.channel is not None
            channel = interaction.channel
            
            # Send method-тэй эсэхийг дахин шалгах
            if (
                not hasattr(channel, 'send')
                or isinstance(channel, (discord.CategoryChannel, discord.ForumChannel))
            ):
                await interaction.followup.send("⚠️ Энэ арналд мессеж илгээх боломжгүй байна!", ephemeral=True)
                return

            embed = discord.Embed(
                title="🎉 Giveaway эхэллээ! 🎉" if not self.is_owner_giveaway else "👑 Owner Giveaway эхэллээ! 👑",
                color=discord.Color.blue() if not self.is_owner_giveaway else discord.Color.gold()
            )
            embed.add_field(name="🏆 Шагнал", value=f"{prize_value}", inline=False)
            embed.add_field(name="👥 Ялагчдын тоо", value=winners_count, inline=False)
            embed.add_field(name="⏳ Үргэлжлэх хугацаа", value=f"{duration_minutes} минут", inline=False)
            embed.add_field(name="📅 Дуусах цаг", value=end_time.strftime("%Y-%m-%d %H:%M:%S (%Z)"), inline=False)
            embed.add_field(name="👤 Нийт оролцогчид", value="0", inline=False)
              # Owner giveaway бол тусгай шаардлага нэмэх
            if self.is_owner_giveaway and hasattr(self, 'requirement') and self.requirement.value:
                embed.add_field(name="📋 Тусгай шаардлага", value=self.requirement.value, inline=False)
                embed.set_footer(text="Доорх товчийг дарж giveaway-д оролцоорой!")
            
            try:
                giveaway_message = await channel.send(embed=embed)
            except Exception as e:
                await interaction.followup.send(f"⚠️ Мессеж илгээхэд алдаа гарлаа: {str(e)}", ephemeral=True)
                return

            with get_giveaway_connection() as conn:
                c = conn.cursor()
                c.execute("INSERT INTO giveaways VALUES (?, ?, ?, ?, ?)",
                          (giveaway_message.id, channel.id, end_time.isoformat(), prize_value, winners_count))
                conn.commit()

            # Giveaway-д оролцох товч (custom_id заавал нэмэх)
            enter_button = discord.ui.Button(
                label="📝 Оролцох" if not self.is_owner_giveaway else "👑 Owner Giveaway-д оролцох", 
                style=discord.ButtonStyle.primary if not self.is_owner_giveaway else discord.ButtonStyle.secondary, 
                custom_id="enter_giveaway"
            )

            async def enter_giveaway_callback(interaction: discord.Interaction) -> None:
                if interaction.user.id in participants:
                    await interaction.response.send_message("⚠️ Та giveaway-д аль хэдийн орсон байна!", ephemeral=True)
                else:
                    # Эхлээд response илгээх
                    success_msg = "✅ Та giveaway-д оролцлоо!" if not self.is_owner_giveaway else "👑 Та Owner Giveaway-д оролцлоо!"
                    await interaction.response.send_message(success_msg, ephemeral=True)
                    
                    # Дараа нь participants-д нэмж embed update хийх
                    participants.add(interaction.user.id)
                    # Field index шалгах (тусгай шаардлага байвал field нэмэгддэг)
                    participant_field_index = 4 if not (self.is_owner_giveaway and hasattr(self, 'requirement') and self.requirement.value) else 5
                    embed.set_field_at(participant_field_index, name="👤 Нийт оролцогчид", value=str(len(participants)), inline=False)
                    await giveaway_message.edit(embed=embed)

            enter_button.callback = enter_giveaway_callback

            # Persistent View тохируулах
            view = discord.ui.View(timeout=None)
            view.add_item(enter_button)

            # Ботод persistent view бүртгэх
            interaction.client.add_view(view)

            await giveaway_message.edit(view=view)

            # Giveaway хугацаа дуусахыг хүлээх
            await asyncio.sleep(duration_seconds)

            # Use channel.send instead of interaction.followup due to 15-minute timeout
            if participants:
                winners = random.sample(list(participants), min(len(participants), winners_count))
                winner_mentions = ', '.join([f'<@{winner}>' for winner in winners])
                end_msg = f"🎉 **Giveaway дууслаа!** 🎉\n🏆 **Ялагчид:** {winner_mentions}\n🎁 **Шагнал:** {prize_value}\n👤 **Нийт оролцогчид:** {len(participants)}"
                if self.is_owner_giveaway:
                    end_msg = f"👑 **Owner Giveaway дууслаа!** 👑\n🏆 **Ялагчид:** {winner_mentions}\n🎁 **Шагнал:** {prize_value}\n👤 **Нийт оролцогчид:** {len(participants)}"
                try:
                    await channel.send(end_msg)
                except Exception as e:
                    print(f"Error sending giveaway end message: {e}")
            else:
                no_participants_msg = "🎉 **Giveaway дууслаа!** 🎉\n⚠️ **Хэн ч giveaway-д оролцоогүй байна.**"
                if self.is_owner_giveaway:
                    no_participants_msg = "👑 **Owner Giveaway дууслаа!** 👑\n⚠️ **Хэн ч giveaway-д оролцоогүй байна.**"
                try:
                    await channel.send(no_participants_msg)
                except Exception as e:
                    print(f"Error sending giveaway end message: {e}")

            with get_giveaway_connection() as conn:
                c = conn.cursor()
                c.execute("DELETE FROM giveaways WHERE message_id = ?", (giveaway_message.id,))
                conn.commit()
        except ValueError:
            await interaction.followup.send("⚠️ Зөв тоон утга оруулна уу!", ephemeral=True)

# Giveaway командууд
class Giveaway(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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

    @commands.command(name='giveaway', aliases=['gw'], help='Starts a giveaway. Admins only.')
    async def giveaway(self, ctx: commands.Context):
        # Persistent Select Menu View үүсгэх
        view = GiveawaySelectView(is_owner=False)
        
        embed = discord.Embed(
            title="🎉 Giveaway үүсгэх",
            description="Доорх цэснээс giveaway-ийн төрлийг сонгоно уу:",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=view)

    @commands.command(name='ownergiveaway', aliases=['og'], help='Starts an owner giveaway. Bot owner only.')
    @commands.is_owner()
    async def owner_giveaway(self, ctx: commands.Context) -> None:
        # Owner-ийн Persistent Select Menu View
        view = GiveawaySelectView(is_owner=True)
        
        embed = discord.Embed(
            title="👑 Owner Giveaway үүсгэх", 
            description="Доорх цэснээс giveaway-ийн төрлийг сонгоно уу:\n(Owner-д зориулсан нэмэлт сонголттой)",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed, view=view)

async def setup(bot: commands.Bot) -> None:
    # Persistent view-уудыг бүртгэх
    bot.add_view(GiveawaySelectView(is_owner=False))
    bot.add_view(GiveawaySelectView(is_owner=True))
    
    await bot.add_cog(Giveaway(bot))

# Economy системтэй холбогдох функц
async def add_money_to_economy(user_id: int, amount: int) -> bool:
    """Economy системд мөнгө нэмэх функц
    
    Args:
        user_id (int): Хэрэглэгчийн ID
        amount (int): Нэмэх мөнгөний хэмжээ
        
    Returns:
        bool: Амжилттай эсэх
    """
    try:
        conn = await get_async_connection('economy')
        await conn.execute("PRAGMA journal_mode=WAL;")
        
        # Хэрэглэгчийн Халаас байгаа эсэхийг шалгах болон үүсгэх
        async with conn.execute("SELECT balance FROM economy WHERE user_id=?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            current_balance = int(result[0]) if result and result[0] is not None else 5000
        
        # Мөнгө нэмэх - last_reward field ч байгаа тул тэрийг хамт update хийх
        new_balance = current_balance + amount
        await conn.execute("""
            INSERT INTO economy (user_id, balance, last_reward)
            VALUES (?, ?, 0)
            ON CONFLICT(user_id) DO UPDATE SET balance=?""",
            (user_id, new_balance, new_balance))
        
        await conn.commit()
        await conn.close()
        print(f"Successfully added {amount}₮ to user {user_id}. New balance: {new_balance}₮")
        return True
    except Exception as e:
        print(f"Error adding money to economy: {e}")
        import traceback
        traceback.print_exc()
        return False