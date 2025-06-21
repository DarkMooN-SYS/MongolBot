import discord
from discord.ext import commands
import logging
import random
import re
from discord.ext.commands import CooldownMapping, Cooldown, BucketType
from collections import defaultdict
from typing import Optional, Any
from discord.abc import Messageable

class MinefieldView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, cog: Any, bet: float, dimension: int, bombs: int):
        super().__init__(timeout=None)
        self.owner_id = interaction.user.id
        self.cog = cog
        self.bet = bet
        self.dimension = dimension
        self.bombs = bombs
        self.grid = ['⬜' for _ in range(dimension ** 2)]
        self.bomb_positions = random.sample(range(dimension ** 2), bombs)
        self.opened = []
        self.multiplier = 1.0
        self.interaction = interaction  # Store the interaction object
        # Товчлууруудыг шууд нэмэх
        for i in range(dimension ** 2):
            row, col = divmod(i, dimension)
            button = discord.ui.Button(
                label="⬜",
                style=discord.ButtonStyle.secondary,
                custom_id=f"minefield_{i}",
                row=row
            )
            button.callback = self.make_callback(i)
            self.add_item(button)
        claim_button = discord.ui.Button(
            label="💰 Claim", style=discord.ButtonStyle.success, custom_id="minefield_claim"
        )
        claim_button.callback = self.claim_reward
        self.add_item(claim_button)
    async def on_timeout(self):
        # Disable all buttons on timeout
        self.disable_all_buttons()
        try:
            await self.interaction.edit_original_response(view=self)
        except Exception:
            pass
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Энэ view-д тусгай async шалгалт хэрэггүй болсон
        return True

    async def claim_reward(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("⚠️ Та энэ тоглоомыг эхлүүлээгүй тул шагнал авах боломжгүй!", ephemeral=True)
            return
        user_id = interaction.user.id
        winnings = int(self.bet * self.multiplier)
        await self.cog.bank_cog.update_balance("bank", user_id, winnings)
        embed = discord.Embed(
            title="🎉 Шагнал авлаа!",
            description=f"🥇 Та **{winnings:,}₮** хожлоо!",
            color=discord.Color.gold()
        )
        try:
            await interaction.response.edit_message(embed=embed, view=None)
        except (discord.errors.NotFound, discord.errors.InteractionResponded):
            if isinstance(interaction.channel, Messageable):
                await interaction.channel.send(embed=embed)

    def make_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message("⚠️ Та энэ тоглоомыг эхлүүлээгүй тул энэ товчлуурыг ашиглах боломжгүй!", ephemeral=True)
                return
            if index in self.opened:
                await interaction.response.defer()
                return
            if index in self.bomb_positions:
                self.grid[index] = "💥"
                result_text = "💥 Та бөмбөг дээр дараад тоглоом дууслаа!"
                color = discord.Color.red()
                self.disable_all_buttons()
                self.multiplier = 0
            else:
                self.grid[index] = "✅"
                self.opened.append(index)
                result_text = "✔️ Та аюулгүй талбай дээр дарлаа!"
                color = discord.Color.green()
                self.increase_multiplier()
            desc = '\n'.join(' '.join(self.grid[i * self.dimension:(i + 1) * self.dimension]) for i in range(self.dimension))
            embed = discord.Embed(
                title="💣 Minefield",
                description=f"{result_text}\n\n**Одоогийн шагнал: {self.bet * self.multiplier:,}₮**\n\n{desc}",
                color=color
            )
            try:
                await interaction.response.edit_message(embed=embed, view=self)
            except (discord.errors.NotFound, discord.errors.InteractionResponded):
                if isinstance(interaction.channel, Messageable):
                    await interaction.channel.send(embed=embed, view=self)
        return callback

    def increase_multiplier(self):
        multiplier_map = {
            3: [1.2, 1.5, 2, 2.2, 2.5, 3],
            4: [1.2, 1.5, 2, 2.2, 2.5, 3, 3.2, 3.5, 4, 4.2, 4.5],
        }
        safe_moves = len(self.opened)
        max_safe_moves = len(multiplier_map[self.dimension])
        if safe_moves <= max_safe_moves and safe_moves > 0:
            self.multiplier = multiplier_map[self.dimension][safe_moves - 1]

    def disable_all_buttons(self):
        for item in self.children:
            if hasattr(item, 'disabled') and isinstance(item, discord.ui.Button):
                item.disabled = True

class Game(commands.Cog):
    def __init__(self, bot: commands.Bot, bank_cog: Any, vip_cog: Any):
        self.bot = bot
        self.bank_cog = bank_cog
        self.vip_cog = vip_cog
        self.MIN_BET = 1
        self.DEFAULT_MAX_BET = 300000
        self.active_minefields = {}
        self.cooldowns = {
            "flip": CooldownMapping(Cooldown(1, 10), BucketType.user),
            "roulette": CooldownMapping(Cooldown(1, 10), BucketType.user),
            "slots": CooldownMapping(Cooldown(1, 10), BucketType.user),
        }
        self.win_streaks = {}
        self.win_streak = defaultdict(int)

    @property
    def server_bank(self) -> Any:
        return self.bot.get_cog("ServerBank")

    async def get_max_bet(self, user_id: int) -> float:
        return await self.vip_cog.get_max_bet_for_user(user_id)

    async def get_command_cooldown(self, user_id: int) -> float:
        return await self.vip_cog.get_cooldown_for_user(user_id)

    async def get_cooldown(self, command_name: str, user_id: int) -> CooldownMapping:
        base_cooldown = await self.get_command_cooldown(user_id)
        if command_name in self.cooldowns:
            self.cooldowns[command_name]._cooldown = commands.Cooldown(1, base_cooldown)
        else:
            self.cooldowns[command_name] = CooldownMapping(Cooldown(1, base_cooldown), BucketType.user)
        return self.cooldowns[command_name]

    async def check_cooldown(self, ctx: commands.Context, command_name: str) -> bool:
        user_id = ctx.author.id
        cooldown = await self.get_cooldown(command_name, user_id)
        bucket = cooldown.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit() if bucket else None
        if retry_after:
            await ctx.send(f"⏳ Та **{retry_after:.1f}** секунд хүлээнэ үү!")
            return False
        return True

    def parse_bet(self, bet_str: Optional[str]) -> Optional[float]:
        if bet_str is None:
            return None
        bet_str = bet_str.lower().strip().replace(",", ".")
        multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000, "t": 1_000_000_000_000}
        match = re.fullmatch(r"(\d+(\.\d+)?)([kmbt]?)", bet_str)
        if not match:
            return None
        num, _, suffix = match.groups()
        try:
            return float(num) * multipliers.get(suffix, 1)
        except ValueError:
            return None

    @commands.command(name='cf', aliases=['coinflip'])
    async def flip(self, ctx: commands.Context, amount: str = '1', choice: Optional[str] = 'heads') -> None:
        if not await self.check_cooldown(ctx, "flip"):
            return
        user_id = ctx.author.id
        if not await self.bank_cog.check_account_and_send_message(ctx):
            return
        max_bet = await self.get_max_bet(user_id)
        if amount.lower() == 'all':
            balance = await self.bank_cog.get_balance(user_id, 'bank')
            amount_f = float(min(balance, max_bet)) if balance else None
        else:
            amount_f = self.parse_bet(amount)
            if amount_f is None:
                await ctx.send("❌ Буруу формат! Тоон утга оруулна уу.")
                return
        if amount_f is None or amount_f < self.MIN_BET or amount_f > max_bet:
            await ctx.send(f"❌ Буруу бооцоо! Та **{self.MIN_BET}-{max_bet:,}₮** хооронд бооцоо тавина уу.")
            return
        balance = await self.bank_cog.get_balance(user_id, 'bank')
        if balance is None or balance < amount_f:
            await ctx.send("⚠️ Таны дансны үлдэгдэл хүрэлцэхгүй байна!")
            return
        choice = (choice or '').lower()
        if choice in ['h', 'heads']:
            choice = 'heads'
        elif choice in ['t', 'tails']:
            choice = 'tails'
        else:
            await ctx.send("Зөвхөн 'heads' эсвэл 'tails' сонгоно уу!")
            return        # Win streak penalty багасгах (3 удаа дараалан хожсон үед л алдуулах)
        if self.win_streak[user_id] >= 3:
            outcome = 'heads' if choice == 'tails' else 'tails'
            self.win_streak[user_id] = 0
        else:
            outcome = random.choice(['heads', 'tails'])
        if outcome == choice:
            self.win_streak[user_id] += 1
            winnings = amount_f * 2
            await self.bank_cog.update_balance('bank', ctx.author.id, winnings - amount_f)
            await ctx.send(
                f"**{ctx.author.mention}**\n"
                f":money_with_wings: **{int(amount_f):,}** төгрөгөөр **{choice}** мөрий тавьсан.\n"
                f":game_die: **{outcome}** гарч ирэв.\n"
                f":money_with_wings: Та **{int(winnings):,}** төгрөг хожлоо!"
            )
        else:
            self.win_streak[user_id] = 0
            await self.bank_cog.update_balance('bank', ctx.author.id, -amount_f)
            if ctx.guild is not None:
                await self.server_bank.update_balance(ctx.guild.id, amount_f)
            await ctx.send(
                f"**{ctx.author.display_name}**\n"
                f":money_with_wings: **{int(amount_f):,}** төгрөгөөр **{choice}** мөрий тавьсан.\n"
                f":game_die: **{outcome}** гарч ирэв.\n"
                f":money_with_wings: Та **{int(amount_f):,}** төгрөг алдсан!"
            )

    @commands.command(name='roulette', aliases=['r'])
    async def roulette(self, ctx: commands.Context, amount: str, choice: Optional[str] = None) -> None:
        if not await self.check_cooldown(ctx, "roulette"):
            return
        user_id = ctx.author.id
        if not await self.bank_cog.check_account_and_send_message(ctx):
            return
        max_bet = await self.get_max_bet(user_id)
        if amount.lower() == 'all':
            balance = await self.bank_cog.get_balance(user_id, 'bank')
            amount_f = float(min(balance, max_bet)) if balance else None
        else:
            amount_f = self.parse_bet(amount)
            if amount_f is None:
                await ctx.send("❌ Буруу формат! Тоон утга оруулна уу.")
                return
        if amount_f is None or amount_f < self.MIN_BET or amount_f > max_bet:
            await ctx.send(f"❌ Буруу бооцоо! Та **{self.MIN_BET}-{max_bet:,}₮** хооронд бооцоо тавина уу.")
            return
        balance = await self.bank_cog.get_balance(user_id, 'bank')
        if balance is None or balance < amount_f:
            await ctx.send("⚠️ Таны дансны үлдэгдэл хүрэлцэхгүй байна!")
            return
        choice = (choice or '').lower()
        if choice not in ['red', 'black', 'green']:
            await ctx.send("Зөвхөн сонголтууд: **red**, **black**, **green**.")
            return        # Roulette win streak penalty багасгах
        if self.win_streak[user_id] >= 3:
            outcome = random.choice([c for c in ['red', 'black', 'green'] if c != choice])
            self.win_streak[user_id] = 0
        else:
            outcome = random.choices(['red', 'black', 'green'], weights=[18, 18, 2])[0]
        if outcome == choice:
            self.win_streak[user_id] += 1
            winnings = amount_f * (5 if choice == 'green' else 2)
            await self.bank_cog.update_balance('bank', ctx.author.id, winnings - amount_f)
            await ctx.send(
                f"{ctx.author.mention}\n"
                f":money_with_wings: **{int(amount_f):,}** төгрөгөөр **{choice}** мөрий тавьсан.\n"
                f":game_die: **{outcome}** гарч ирэв.\n"
                f":money_with_wings: Та **{int(winnings):,}** төгрөг хожлоо!"
            )
        else:
            self.win_streak[user_id] = 0
            await self.bank_cog.update_balance('bank', ctx.author.id, -amount_f)
            if ctx.guild is not None:
                await self.server_bank.update_balance(ctx.guild.id, amount_f)
            await ctx.send(
                f"**{ctx.author.display_name}**\n"
                f":money_with_wings: **{int(amount_f):,}** төгрөгөөр **{choice}** мөрий тавьсан.\n"
                f":game_die: **{outcome}** гарч ирэв.\n"
                f":money_with_wings: Та **{int(amount_f):,}** төгрөг алдсан!"
            )

    @commands.command(name="slots", aliases=["s"])
    async def slot_machine(self, ctx: commands.Context, amount: str = '1') -> None:
        if not await self.check_cooldown(ctx, "slots"):
            return
        user_id = ctx.author.id
        if not await self.bank_cog.check_account_and_send_message(ctx):
            return
        max_bet = await self.get_max_bet(user_id)
        if amount.lower() == 'all':
            balance = await self.bank_cog.get_balance(user_id, 'bank')
            if balance is None or balance <= 0:
                await ctx.send("⚠️ Таны дансны үлдэгдэл хүрэлцэхгүй байна!")
                return
            amount_f = float(min(balance, max_bet))
        else:
            amount_f = self.parse_bet(amount)
            if amount_f is None:
                await ctx.send("❌ Буруу утга оруулсан байна. Та бүхэл тоо, all, 1k, 10k, 1m гэх мэт утга оруулна уу.")
                return
        if amount_f < self.MIN_BET:
            await ctx.send(f"⚠️ Таны бооцоо хамгийн багадаа **{self.MIN_BET}₮** байх ёстой!")
            return
        if amount_f > max_bet:
            await ctx.send(f"⚠️ Таны бооцоо **{max_bet:,}₮**-с хэтрэхгүй байх ёстой!")
            return
        balance = await self.bank_cog.get_balance(user_id, 'bank')
        if balance is None or balance < amount_f:
            await ctx.send("⚠️ Таны дансны үлдэгдэл хүрэлцэхгүй байна!")
            return
        if user_id not in self.win_streaks:
            self.win_streaks[user_id] = 0        # Slots машины алдах магадлалыг 60%-ээс 45% болгох
        if random.randint(1, 100) <= 50:
            slot_result = random.sample(["🍒", "💎", "🍌", "🥝", "🎰"], 3)
            self.win_streaks[user_id] = 0
        else:
            three_identical_weights = {
                "🍒": 40,
                "💎": 20,
                "🍌": 10,
                "🥝": 5,
                "🎰": 1
            }
            chosen_symbol = random.choices(list(three_identical_weights.keys()), weights=list(three_identical_weights.values()), k=1)[0]
            slot_result = [chosen_symbol] * 3
            self.win_streaks[user_id] += 1
        multiplier_map = {"🍒": 1.5, "💎": 2, "🍌": 2.5, "🥝": 3, "🎰": 5}
        multiplier = multiplier_map.get(slot_result[0], 0) if len(set(slot_result)) == 1 else 0
        winnings = amount_f * multiplier if multiplier > 0 else -amount_f
        if multiplier == 0:
            await self.bank_cog.update_balance('bank', ctx.author.id, -amount_f)
            if ctx.guild is not None:
                await self.server_bank.update_balance(ctx.guild.id, amount_f)
        else:
            await self.bank_cog.update_balance('bank', user_id, winnings)
        slot_display = f"| {' | '.join(slot_result)} |"
        if multiplier > 0:
            result_text = (
                f"🎰 **SLOT MACHINE** 🎰\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🧑‍💼 Тоглогч: {ctx.author.mention}\n"
                f"💰 Бооцоо: **{int(amount_f):,}**₮\n"
                f"🎲 Үр дүн\n"
                f"{slot_display}\n"
                f"🏆 Шагнал: **+{int(amount_f * multiplier):,}₮ (x{multiplier})**\n"
                f"━━━━━━━━━━━━━━━━━━"
            )
        else:
            result_text = (
                f"🎰 **SLOT MACHINE** 🎰\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🧑‍💼 Тоглогч: **{ctx.author.display_name}**\n"
                f"💰 Бооцоо: **{int(amount_f):,}**₮\n"
                f"🎲 Үр дүн\n"
                f"{slot_display}\n"
                f"💀 Та алдлаа! **-{int(amount_f):,}**₮\n"
                f"━━━━━━━━━━━━━━━━━━"
            )
        await ctx.send(result_text)

    async def start_minefield(self, interaction: discord.Interaction, dimension: int, bombs: int, bet: float) -> None:
        user_id = interaction.user.id
        balance = await self.bank_cog.get_balance(user_id, 'bank')
        if balance < bet:
            await interaction.response.send_message("⚠️ Таны дансны үлдэгдэл хүрэлцэхгүй байна!", ephemeral=True)
            return
        # Банкнаас мөнгө хасахыг энд хийж, view-д loading button нэмэхгүй
        await self.bank_cog.update_balance("bank", user_id, -bet)
        view = MinefieldView(interaction, self, bet, dimension, bombs)
        desc = '\n'.join(' '.join(view.grid[i * dimension:(i + 1) * dimension]) for i in range(dimension))
        embed = discord.Embed(
            title=f"💣 Minefield ({dimension}x{dimension}) эхэллээ!",
            description=f"Бооцоо: **{int(bet):,}₮**\n{desc}",
            color=discord.Color.green()
        )
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except (discord.errors.NotFound, discord.errors.InteractionResponded):
            if isinstance(interaction.channel, Messageable):
                await interaction.channel.send(embed=embed, view=view)
        except Exception as e:
            if isinstance(interaction.channel, Messageable):
                await interaction.channel.send(f"⚠️ Хүлээгдээгүй алдаа: {e}")

    @commands.command(name='minefield', aliases=["mf"])
    async def minefield(self, ctx: commands.Context, bet: str = '1') -> None:
        user_id = ctx.author.id
        if bet.lower() == 'all':
            balance = await self.bank_cog.get_balance(user_id, 'bank')
            max_bet = await self.get_max_bet(user_id)
            bet_f = float(min(balance, max_bet))
        else:
            bet_f = self.parse_bet(bet)
        max_bet = await self.get_max_bet(user_id)
        if bet_f is None or bet_f < self.MIN_BET:
            await ctx.send(f"❌ Буруу бооцоо! Хамгийн багадаа **{self.MIN_BET}₮** байна.")
            return
        if bet_f > max_bet:
            await ctx.send(f"❌ Таны дээд бооцоо **{max_bet:,}₮** тул илүү их бооцоо тавих боломжгүй!")
            return
        balance = await self.bank_cog.get_balance(user_id, 'bank')
        if balance < bet_f:
            await ctx.send("⚠️ Таны дансны үлдэгдэл хүрэлцэхгүй байна!")
            return
        view = discord.ui.View(timeout=None)
        sizes = {"3x3": (3, 2), "4x4": (4, 3)}
        for label, (dimension, bombs) in sizes.items():
            button = discord.ui.Button(label=label, style=discord.ButtonStyle.primary)
            async def callback(interaction: discord.Interaction, dim: int = dimension, bom: int = bombs):
                await self.start_minefield(interaction, dim, bom, bet_f)
            button.callback = callback
            view.add_item(button)
        embed = discord.Embed(
            title="📌 Minefield хэмжээ сонгоно уу!",
            description=f"Та **{int(bet_f):,}₮** бооцоо тавилаа. Талбарын хэмжээг сонгоно уу.",
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed, view=view)

async def setup(bot: commands.Bot) -> None:
    bank_cog = bot.get_cog("Bank")
    vip_cog = bot.get_cog("VIP")
    await bot.add_cog(Game(bot, bank_cog, vip_cog))