import discord
from discord.ext import commands
import random
import asyncio
from typing import Optional, Dict, TYPE_CHECKING, Any
import logging
from ..utils.channel import is_channel_enabled

if TYPE_CHECKING:
    from ..economy.bank import Bank

logger = logging.getLogger(__name__)

class DuelChallengeView(discord.ui.View):
    """1v1 дуэл шалгаруулгын view"""
    
    def __init__(self, challenger_id: int, target_id: int, bet_amount: int, cog: 'RollDuel'):
        super().__init__(timeout=60.0)
        self.challenger_id = challenger_id
        self.target_id = target_id
        self.bet_amount = bet_amount
        self.cog = cog
        self.accepted = False
        self.message: Optional[discord.Message] = None
        
    @discord.ui.button(label="✅ Зөвшөөрөх", style=discord.ButtonStyle.success)
    async def accept_duel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("❌ Зөвхөн сорилт авсан хүн л зөвшөөрч болно!", ephemeral=True)
            return
            
        self.accepted = True
        self.stop()
        
        # Дуэл эхлүүлэх
        duel_view = DuelGameView(self.challenger_id, self.target_id, self.bet_amount, self.cog)
        
        embed = discord.Embed(
            title="⚔️ Шооны Дуэл Эхэллээ!",
            description=f"<@{self.challenger_id}> vs <@{self.target_id}>\n💰 Бэлгэдэх дүн: **{self.bet_amount:,}₮**",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="📋 Дүрэм:", 
            value="• Хоёр тоглогч шоо шидэх\n• Өндөр оноо авсан хүн ялна\n• Ялагч бүх мөнгийг авна", 
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=duel_view)
        
    @discord.ui.button(label="❌ Татгалзах", style=discord.ButtonStyle.danger)
    async def decline_duel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("❌ Зөвхөн сорилт авсан хүн л татгалзаж болно!", ephemeral=True)
            return

        embed = discord.Embed(
            title="❌ Дуэл Татгалзлаа",
            description=f"<@{self.target_id}> дуэлийг татгалзлаа. Мөнгө буцаагдлаа.",
            color=discord.Color.red()
        )

        # Татгалзсан тохиолдолд зөвхөн өөрийнх нь мөнгийг буцаах
        try:
            bank_cog = self.cog.bot.get_cog('Bank')
            if bank_cog and hasattr(bank_cog, 'update_balance'):
                await bank_cog.update_balance('bank', self.target_id, self.bet_amount)  # type: ignore
        except Exception as e:
            logger.error(f"Error refunding money on decline: {e}")

        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    async def on_timeout(self) -> None:
        embed = discord.Embed(
            title="⏰ Хугацаа дууслаа",
            description="Дуэлийн сорилт хүлээх хугацаа дууслаа.",
            color=discord.Color.dark_grey()
        )

        # Timeout үед зөвхөн өөрийнх нь мөнгийг буцаах
        try:
            bank_cog = self.cog.bot.get_cog('Bank')
            if bank_cog and hasattr(bank_cog, 'update_balance'):
                await bank_cog.update_balance('bank', self.target_id, self.bet_amount)  # type: ignore
        except Exception as e:
            logger.error(f"Error refunding money on challenge timeout: {e}")

        try:
            # Get the original message and edit it
            if self.message is not None:
                await self.message.edit(embed=embed, view=None)
        except Exception:
            pass

class DuelGameView(discord.ui.View):
    """Дуэлийн тоглоомын view"""
    
    def __init__(self, player1_id: int, player2_id: int, bet_amount: int, cog: 'RollDuel'):
        super().__init__(timeout=120.0)
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.bet_amount = bet_amount
        self.cog = cog
        self.player1_rolled = False
        self.player2_rolled = False
        self.player1_roll = 0
        self.player2_roll = 0
        self.message: Optional[discord.Message] = None
        
    @discord.ui.button(label="🎲 Шоо Шидэх", style=discord.ButtonStyle.primary, emoji="🎲")
    async def roll_dice(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        
        if user_id not in [self.player1_id, self.player2_id]:
            await interaction.response.send_message("❌ Та энэ дуэлд оролцоогүй байна!", ephemeral=True)
            return
            
        # Шоо шидсэн эсэхийг шалгах
        if user_id == self.player1_id and self.player1_rolled:
            await interaction.response.send_message("❌ Та аль хэдийн шоо шидсэн байна!", ephemeral=True)
            return
        elif user_id == self.player2_id and self.player2_rolled:
            await interaction.response.send_message("❌ Та аль хэдийн шоо шидсэн байна!", ephemeral=True)
            return
            
        # Шооны үр дүн
        roll_result = random.randint(1, 100)
        
        if user_id == self.player1_id:
            self.player1_rolled = True
            self.player1_roll = roll_result
        else:
            self.player2_rolled = True
            self.player2_roll = roll_result
            
        # Embed үүсгэх
        embed = discord.Embed(
            title="⚔️ Шооны Дуэл",
            color=discord.Color.orange()
        )
        
        # Тоглогчдын үр дүн
        player1_status = f"🎲 **{self.player1_roll}**" if self.player1_rolled else "⏳ Хүлээж байна..."
        player2_status = f"🎲 **{self.player2_roll}**" if self.player2_rolled else "⏳ Хүлээж байна..."
        
        embed.add_field(name=f"👤 <@{self.player1_id}>", value=player1_status, inline=True)
        embed.add_field(name=f"👤 <@{self.player2_id}>", value=player2_status, inline=True)
        embed.add_field(name="💰 Бэлгэдэх дүн", value=f"**{self.bet_amount:,}₮**", inline=True)
        
        # Хэрэв хоёулаа шидсэн бол үр дүн гаргах
        if self.player1_rolled and self.player2_rolled:
            await self.finish_duel(interaction, embed)
        else:
            await interaction.response.edit_message(embed=embed, view=self)
            
    async def finish_duel(self, interaction: discord.Interaction, embed: discord.Embed):
        """Дуэл дуусгах"""
        
        # Ялагчийг тодорхойлох
        if self.player1_roll > self.player2_roll:
            winner_id = self.player1_id
            loser_id = self.player2_id
            winner_roll = self.player1_roll
            loser_roll = self.player2_roll
        elif self.player2_roll > self.player1_roll:
            winner_id = self.player2_id
            loser_id = self.player1_id
            winner_roll = self.player2_roll
            loser_roll = self.player1_roll
        else:
            # Тэнцсэн тохиолдол
            embed.title = "🤝 Тэнцлээ!"
            embed.color = discord.Color.yellow()
            embed.add_field(
                name="📊 Үр дүн:", 
                value="Хоёулаа ижил оноо авсан тул тэнцлээ! Мөнгө буцаагдлаа.", 
                inline=False
            )
            
            # Тэнцсэн тохиолдолд мөнгө буцаах
            try:
                bank_cog = self.cog.bot.get_cog('Bank')
                if bank_cog and hasattr(bank_cog, 'update_balance'):
                    await bank_cog.update_balance('bank', self.player1_id, self.bet_amount)  # type: ignore
                    await bank_cog.update_balance('bank', self.player2_id, self.bet_amount)  # type: ignore
            except Exception as e:
                logger.error(f"Error refunding money on tie: {e}")
            
            await interaction.response.edit_message(embed=embed, view=None)
            return
            
        # Мөнгө шилжүүлэх
        try:
            bank_cog = self.cog.bot.get_cog('Bank')
            if bank_cog and hasattr(bank_cog, 'update_balance'):
                # Хожигчийн мөнгийг нэмэх (хоёр тоглогчийн нийлбэр бооцоо)
                total_winnings = self.bet_amount + self.bet_amount
                await bank_cog.update_balance('bank', winner_id, total_winnings)  # type: ignore
                embed.title = "🏆 Дуэл Дууслаа!"
                embed.color = discord.Color.gold()
                embed.add_field(
                    name="🎉 Ялагч:", 
                    value=f"<@{winner_id}> - **{winner_roll}** оноо", 
                    inline=False
                )
                embed.add_field(
                    name="😢 Ялагдсан:", 
                    value=f"<@{loser_id}> - **{loser_roll}** оноо", 
                    inline=False
                )
                embed.add_field(
                    name="💰 Хожсон дүн:", 
                    value=f"**{total_winnings:,}₮**", 
                    inline=False
                )
            else:
                embed.add_field(name="❌ Алдаа:", value="Банкны систем олдсонгүй!", inline=False)
                
        except Exception as e:
            logger.error(f"Error in duel finish: {e}")
            embed.add_field(name="❌ Алдаа:", value="Мөнгө шилжүүлэхэд алдаа гарлаа!", inline=False)
            
        await interaction.response.edit_message(embed=embed, view=None)
        
    async def on_timeout(self) -> None:
        embed = discord.Embed(
            title="⏰ Дуэл цуцлагдлаа",
            description="Хугацаа дууссан тул дуэл цуцлагдлаа. Мөнгө буцаагдлаа.",
            color=discord.Color.dark_grey()
        )
        
        # Timeout үед зөвхөн өөрийнх нь мөнгийг буцаах
        try:
            bank_cog = self.cog.bot.get_cog('Bank')
            if bank_cog and hasattr(bank_cog, 'update_balance'):
                await bank_cog.update_balance('bank', self.player1_id, self.bet_amount)  # type: ignore
                await bank_cog.update_balance('bank', self.player2_id, self.bet_amount)  # type: ignore
        except Exception as e:
            logger.error(f"Error refunding money on timeout: {e}")
        
        try:
            if self.message is not None:
                await self.message.edit(embed=embed, view=None)
        except Exception:
            pass

class RollDuel(commands.Cog):
    import re

    def parse_bet(self, bet_str: Optional[str]) -> Optional[float]:
        if bet_str is None:
            return None
        bet_str = bet_str.lower().strip().replace(",", ".")
        multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000, "t": 1_000_000_000_000}
        match = self.re.fullmatch(r"(\d+(\.\d+)?)([kmbt]?)", bet_str)
        if not match:
            return None
        num, _, suffix = match.groups()
        try:
            return float(num) * multipliers.get(suffix, 1)
        except ValueError:
            return None
    """Шооны дуэл - 1v1 тоглоом"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_duels: Dict[int, bool] = {}  # Идэвхтэй дуэлүүд
        
    @commands.command(name='duelroll')
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def duel_challenge(self, ctx: commands.Context, target: discord.Member, bet_amount: str):
        """
        Өөр хүнтэй шооны дуэл хийх
        
        Жишээ: mдуэл @хэрэглэгч 1000
        """
        # Parse bet amount using parse_bet
        bet_parsed = self.parse_bet(str(bet_amount))
        if bet_parsed is None or bet_parsed != int(bet_parsed):
            embed = discord.Embed(
                title="❌ Алдаа!",
                description="Бэлгэдэх дүнг зөвхөн бүхэл тоогоор оруулна уу! Жишээ: mduelroll @хэрэглэгч 1000, mduelroll @хэрэглэгч 1k",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        bet_amount_int = int(bet_parsed)
        if ctx.guild is None or not await is_channel_enabled(ctx.guild.id, ctx.channel.id):
            return
        challenger = ctx.author
        
        # Өөрөө өөртөө сорилт өгөх боломжгүй
        if target.id == challenger.id:
            embed = discord.Embed(
                title="❌ Алдаа!",
                description="Та өөртөө сорилт өгөх боломжгүй!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
            
        # Бот руу сорилт өгөх боломжгүй
        if target.bot:
            embed = discord.Embed(
                title="❌ Алдаа!",
                description="Ботруу сорилт өгөх боломжгүй!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
            
        # Мөнгөний дүн шалгах
        if bet_amount_int < 100:
            embed = discord.Embed(
                title="❌ Алдаа!",
                description="Хамгийн бага бэлгэдэх дүн **100₮** байх ёстой!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
            
        if bet_amount_int > 5000000:
            embed = discord.Embed(
                title="❌ Алдаа!",
                description="Хамгийн их бэлгэдэх дүн **5,000,000₮** байх ёстой!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
            
        # Идэвхтэй дуэл шалгах
        if challenger.id in self.active_duels:
            embed = discord.Embed(
                title="❌ Алдаа!",
                description="Та аль хэдийн дуэлд оролцож байна!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
            
        if target.id in self.active_duels:
            embed = discord.Embed(
                title="❌ Алдаа!",
                description="Энэ хэрэглэгч аль хэдийн дуэлд оролцож байна!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
            
        # Банкны мөнгө шалгах
        try:
            bank_cog = self.bot.get_cog('Bank')
            if not bank_cog or not hasattr(bank_cog, 'get_balance'):
                embed = discord.Embed(
                    title="❌ Алдаа!",
                    description="Банкны систем идэвхгүй байна!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            # Сорилт өгсөн хүний мөнгө шалгах
            challenger_balance = await bank_cog.get_balance(challenger.id, 'bank')  # type: ignore
            if challenger_balance is None or challenger_balance < bet_amount_int:
                embed = discord.Embed(
                    title="❌ Хангалтгүй мөнгө!",
                    description=f"Танд **{bet_amount_int:,}₮** хангалттай мөнгө байхгүй байна!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            # Сорилт авсан хүний мөнгө шалгах
            target_balance = await bank_cog.get_balance(target.id, 'bank')  # type: ignore
            if target_balance is None or target_balance < bet_amount_int:
                embed = discord.Embed(
                    title="❌ Алдаа!",
                    description=f"<@{target.id}> хэрэглэгчид **{bet_amount_int:,}₮** хангалттай мөнгө байхгүй байна!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            # Мөнгө хасах
            await bank_cog.update_balance('bank', challenger.id, -bet_amount_int)  # type: ignore
            await bank_cog.update_balance('bank', target.id, -bet_amount_int)  # type: ignore
        except Exception as e:
            logger.error(f"Error checking balances for duel: {e}")
            embed = discord.Embed(
                title="❌ Алдаа!",
                description="Мөнгө шалгахад алдаа гарлаа!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
            
        # Идэвхтэй дуэлүүдэд нэмэх
        self.active_duels[challenger.id] = True
        self.active_duels[target.id] = True
        # Сорилтын embed
        embed = discord.Embed(
            title="⚔️ Шооны Дуэлийн Сорилт!",
            description=f"<@{challenger.id}> танд **{bet_amount_int:,}₮**-ний төлөө дуэл өгч байна!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="🎯 Сорилогч:", 
            value=f"<@{challenger.id}>", 
            inline=True
        )
        embed.add_field(
            name="🎯 Сорилт авсан:", 
            value=f"<@{target.id}>", 
            inline=True
        )
        embed.add_field(
            name="💰 Бэлгэдэх дүн:", 
            value=f"**{bet_amount_int:,}₮**", 
            inline=True
        )
        embed.add_field(
            name="📋 Дүрэм:", 
            value="• Хоёр тоглогч шоо шидэх (1-100)\n• Өндөр оноо авсан хүн ялна\n• Ялагч **бүх мөнгийг** авна", 
            inline=False
        )
        embed.set_footer(text="60 секундын дотор хариулна уу!")
        view = DuelChallengeView(challenger.id, target.id, bet_amount_int, self)
        message = await ctx.send(f"<@{target.id}>", embed=embed, view=view)
        view.message = message
        
        # Хүлээх
        await view.wait()
        
        # Идэвхтэй дуэлээс хасах
        self.active_duels.pop(challenger.id, None)
        self.active_duels.pop(target.id, None)
        
        # Хэрэв зөвшөөрөөгүй бол мөнгө буцаах
        if not view.accepted:
            try:
                if hasattr(bank_cog, 'update_balance'):
                    await bank_cog.update_balance('bank', challenger.id, bet_amount_int)  # type: ignore
                    await bank_cog.update_balance('bank', target.id, bet_amount_int)  # type: ignore
            except Exception as e:
                logger.error(f"Error refunding money: {e}")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RollDuel(bot))