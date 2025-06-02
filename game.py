import discord
from discord.ext import commands
import sqlite3
import logging
import random
import time
import datetime
from discord.ext.commands import CooldownMapping, Cooldown, BucketType
from collections import defaultdict
import aiosqlite  # ✅ SQLite-ийг асинхрон байдлаар ашиглах
import re
from serverbank import ServerBank  # ServerBank классыг импортлол

class MinefieldView(discord.ui.View):
    def __init__(self, interaction, cog, bet, dimension, bombs):
        super().__init__(timeout=None)
        self.owner_id = interaction.user.id  # ✅ Тоглоомыг эхлүүлсэн хэрэглэгчийн ID
        self.cog = cog
        self.bet = bet
        self.dimension = dimension
        self.bombs = bombs
        self.grid = ['⬜' for _ in range(dimension ** 2)]
        self.bomb_positions = random.sample(range(dimension ** 2), bombs)
        self.opened = []
        self.multiplier = 1.0  
        self.cog.bank_cog.update_balance("bank", interaction.user.id, -bet)

        # ✅ Талбарын товчлуурууд үүсгэх
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

        # ✅ "Claim" товч зөвхөн owner дарна
        claim_button = discord.ui.Button(
            label="💰 Claim", style=discord.ButtonStyle.success, custom_id="minefield_claim"
        )
        claim_button.callback = self.claim_reward
        self.add_item(claim_button)

    async def claim_reward(self, interaction: discord.Interaction):
        """✅ Хэрэглэгч шагнал авах товчийг дарсан үед"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("⚠️ Та энэ тоглоомыг эхлүүлээгүй тул шагнал авах боломжгүй!", ephemeral=True)
            return

        user_id = interaction.user.id
        winnings = int(self.bet * self.multiplier)

        self.cog.bank_cog.update_balance("bank", user_id, winnings)  # ✅ Шагнал олгох
        embed = discord.Embed(
            title="🎉 Шагнал авлаа!",
            description=f"🥇 Та **{winnings:,}₮** хожлоо!",
            color=discord.Color.gold()
        )
        await interaction.response.edit_message(embed=embed, view=None)  # ✅ Товчлууруудыг устгах

    def make_callback(self, index):
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
                self.multiplier = 0  # ✅ Шагналын боломжийг устгах

            else:
                self.grid[index] = "✅"
                self.opened.append(index)
                result_text = "✔️ Та аюулгүй талбай дээр дарлаа!"
                color = discord.Color.green()
                self.increase_multiplier()  # ✅ Аюулгүй нүд дарсан бол шагнал өснө

            desc = '\n'.join(' '.join(self.grid[i * self.dimension:(i + 1) * self.dimension]) for i in range(self.dimension))
            embed = discord.Embed(
                title="💣 Minefield",
                description=f"{result_text}\n\n**Одоогийн шагнал: {self.bet * self.multiplier:,}₮**\n\n{desc}",
                color=color
            )
            await interaction.response.edit_message(embed=embed, view=self)

        return callback

    def increase_multiplier(self):
        """✅ Аюулгүй нүд дарсан үед шагналын үржвэрийг нэмэгдүүлэх"""
        multiplier_map = {
            3: [1.2, 1.5, 2, 2.2, 2.5, 3],  # **3×3 нь 6 аюулгүй нүдтэй**
            4: [1.2, 1.5, 2, 2.2, 2.5, 3, 3.2, 3.5, 4, 4.2, 4.5],  # **4×4 нь 11 аюулгүй нүдтэй**
        }

        safe_moves = len(self.opened)  # ✅ Нээсэн аюулгүй нүдний тоо
        max_safe_moves = len(multiplier_map[self.dimension])  # ✅ Нийт боломжит аюулгүй нүд

        if safe_moves <= max_safe_moves:
            self.multiplier = multiplier_map[self.dimension][safe_moves - 1]

    def disable_all_buttons(self):
        """✅ Бүх товчлууруудыг идэвхгүй болгох"""
        for item in self.children:
            item.disabled = True

class Game(commands.Cog):
    def __init__(self, bot, bank_cog, vip_cog):
        self.bot = bot
        self.conn = None
        self.bank_cog = bank_cog  # Bank когийг энд дамжуулна
        self.vip_cog = vip_cog  # VIP когийг энд дамжуулна
        self.conn = bank_cog.conn  # SQLite холболтыг Bank когиос авна
        self.server_bank = ServerBank(self.bot)  # ServerBank классыг ашиглах
        self.c = self.conn.cursor()
        self.MIN_BET = 1
        self.DEFAULT_MAX_BET = 300000  # Энгийн хэрэглэгчийн дээд бооцоо
        self.active_minefields = {}
        self.cooldowns = {
            "flip": CooldownMapping(Cooldown(1, 10), BucketType.user),
            "roulette": CooldownMapping(Cooldown(1, 10), BucketType.user),
            "slots": CooldownMapping(Cooldown(1, 10), BucketType.user),
        }
        self.win_streaks = {}
        self.win_streak = defaultdict(int)  # Хэрэглэгчийн ялалтын цувралыг хадгалах

    async def get_max_bet(self, user_id):
        return await self.vip_cog.get_max_bet_for_user(user_id)

    async def get_command_cooldown(self, user_id):
        return await self.vip_cog.get_cooldown_for_user(user_id)

    async def get_cooldown(self, command_name, user_id):
        base_cooldown = await self.get_command_cooldown(user_id)

        if command_name in self.cooldowns:
            self.cooldowns[command_name]._cooldown = commands.Cooldown(1, base_cooldown)
        else:
            self.cooldowns[command_name] = CooldownMapping(Cooldown(1, base_cooldown), BucketType.user)

        return self.cooldowns[command_name]

    def ensure_connection(self):
        """SQLite холболт амьд байгаа эсэхийг шалгах"""
        try:
            self.conn.execute("SELECT 1")  # Хэрэв холболт идэвхгүй бол `OperationalError` өгнө
        except (sqlite3.ProgrammingError, sqlite3.OperationalError):
            logger.warning("⚠️ Мэдээллийн сантай дахин холбогдож байна...")
            self.conn = self.bank_cog.conn  # `bank_cog.conn`-ийг дахин авна
            self.c = self.conn.cursor()

    async def check_cooldown(self, ctx, command_name):
        user_id = ctx.author.id
        cooldown = await self.get_cooldown(command_name, user_id)
        bucket = cooldown.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()

        if retry_after:
            await ctx.send(f"⏳ Та **{retry_after:.1f}** секунд хүлээнэ үү!")
            return False
        return True

    def parse_bet(self, bet_str):
        """Товчилсон хэлбэрийг (1.5k, 15.5m, 1.5m, 1.5, 15.5b) бодит тоо болгон хөрвүүлэх."""
    
        if bet_str is None:  # `None` тохиолдолд шууд буцаах
            return "❌ Буруу формат! Тоон утга оруулна уу."
    
        bet_str = bet_str.lower().strip().replace(",", ".")

        # Хэмжээг томъёолсон үсгүүд ба тэдний утга
        multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000, "t": 1_000_000_000_000}
    
        # 1.5, 15.5m, 1.5k гэх мэт форматыг зөвшөөрнө
        match = re.fullmatch(r"(\d+(\.\d+)?)([kmbt]?)", bet_str)
        if not match:
            return "❌ Буруу формат! Зөвшөөрөгдсөн хэлбэр: 1.5k, 10m, 2.3b, 5.55k"

        num, _, suffix = match.groups()  # `num` нь тоо, `suffix` нь хэмжүүр (k, m, b, t)

        try:
            return float(num) * multipliers.get(suffix, 1)
        except ValueError:
            return "❌ Алдаа гарлаа! Тоог хөрвүүлэх боломжгүй байна."

    @commands.command(name='cf', aliases=['coinflip'])
    async def flip(self, ctx, amount: str = '1', choice: str = 'heads'):
        if not await self.check_cooldown(ctx, "flip"):
            return

        user_id = ctx.author.id

        if not await self.bank_cog.check_account_and_send_message(ctx):
            return

        max_bet = await self.get_max_bet(user_id)
        if amount.lower() == 'all':
            self.c.execute("SELECT balance FROM bank WHERE user_id=?", (user_id,))
            balance_result = self.c.fetchone()
            amount = min(balance_result[0], max_bet) if balance_result else None
        else:
            amount = self.parse_bet(amount)

        if amount is None or amount < self.MIN_BET or amount > max_bet:
            await ctx.send(f"❌ Буруу бооцоо! Та **{self.MIN_BET}-{max_bet:,}₮** хооронд бооцоо тавина уу.")
            return

        self.c.execute("SELECT balance FROM bank WHERE user_id=?", (user_id,))
        balance_result = self.c.fetchone()
        if balance_result is None or balance_result[0] < amount:
            await ctx.send("⚠️ Таны дансны үлдэгдэл хүрэлцэхгүй байна!")
            return

        choice = choice.lower()
        if choice in ['h', 'heads']:
            choice = 'heads'
        elif choice in ['t', 'tails']:
            choice = 'tails'
        else:
            await ctx.send("Зөвхөн 'heads' эсвэл 'tails' сонгоно уу!")
            return

        if self.win_streak[user_id] >= 2:
            outcome = 'heads' if choice == 'tails' else 'tails'  # Хожигдуулах
            self.win_streak[user_id] = 0  # Цувралыг дахин эхлүүлэх
        else:
            outcome = random.choice(['heads', 'tails'])

        if outcome == choice:
            self.win_streak[user_id] += 1
            winnings = amount * 2
            self.bank_cog.update_balance('bank', ctx.author.id, winnings - amount)
            await ctx.send(
                f"**{ctx.author.mention}**\n"
                f":money_with_wings: **{amount:,}** төгрөгөөр **{choice}** мөрий тавьсан.\n"
                f":game_die: **{outcome}** гарч ирэв.\n"
                f":money_with_wings: Та **{winnings:,}** төгрөг хожлоо!"
            )
        else:
            self.win_streak[user_id] = 0
            self.bank_cog.update_balance('bank', ctx.author.id, -amount)  # Алдагдсан мөнгийг хасах
            await self.server_bank.update_balance(ctx.guild.id, amount)  # Серверийн банк руу мөнгө оруулах
            await ctx.send(
                f"**{ctx.author.display_name}**\n"
                f":money_with_wings: **{amount:,}** төгрөгөөр **{choice}** мөрий тавьсан.\n"
                f":game_die: **{outcome}** гарч ирэв.\n"
                f":money_with_wings: Та **{amount:,}** төгрөг алдсан!"
            )

    @commands.command(name='roulette', aliases=['r'])
    async def roulette(self, ctx, amount: str, choice: str = None):
        if not await self.check_cooldown(ctx, "roulette"):
            return

        user_id = ctx.author.id

        if not await self.bank_cog.check_account_and_send_message(ctx):
            return

        max_bet = await self.get_max_bet(user_id)
        if amount.lower() == 'all':
            self.c.execute("SELECT balance FROM bank WHERE user_id=?", (user_id,))
            balance_result = self.c.fetchone()
            amount = min(balance_result[0], max_bet) if balance_result else None
        else:
            amount = self.parse_bet(amount)

        if amount is None or amount < self.MIN_BET or amount > max_bet:
            await ctx.send(f"❌ Буруу бооцоо! Та **{self.MIN_BET}-{max_bet:,}₮** хооронд бооцоо тавина уу.")
            return

        self.c.execute("SELECT balance FROM bank WHERE user_id=?", (ctx.author.id,))
        balance_result = self.c.fetchone()
        if balance_result is None or balance_result[0] < amount:
            await ctx.send("⚠️ Таны дансны үлдэгдэл хүрэлцэхгүй байна!")
            return

        choice = choice.lower()
        if choice not in ['red', 'black', 'green']:
            await ctx.send("Зөвхөн сонголтууд: **red**, **black**, **green**.")
            return

        if self.win_streak[user_id] >= 2:
            outcome = random.choice([c for c in ['red', 'black', 'green'] if c != choice])  # Ялагдуулах
            self.win_streak[user_id] = 0
        else:
            outcome = random.choices(['red', 'black', 'green'], weights=[18, 18, 2])[0]

        if outcome == choice:
            self.win_streak[user_id] += 1
            winnings = amount * (5 if choice == 'green' else 2)
            self.bank_cog.update_balance('bank', ctx.author.id, winnings - amount)
            await ctx.send(
                f"{ctx.author.mention}\n"
                f":money_with_wings: **{amount:,}** төгрөгөөр **{choice}** мөрий тавьсан.\n"
                f":game_die: **{outcome}** гарч ирэв.\n"
                f":money_with_wings: Та **{winnings:,}** төгрөг хожлоо!"
            )
        else:
            self.win_streak[user_id] = 0
            self.bank_cog.update_balance('bank', ctx.author.id, -amount)  # Алдагдсан мөнгийг хасах
            await self.server_bank.update_balance(ctx.guild.id, amount)  # Серверийн банк руу мөнгө оруулах
            await ctx.send(
                f"**{ctx.author.display_name}**\n"
                f":money_with_wings: **{amount:,}** төгрөгөөр **{choice}** мөрий тавьсан.\n"
                f":game_die: **{outcome}** гарч ирэв.\n"
                f":money_with_wings: Та **{amount:,}** төгрөг алдсан!"
            )

    @commands.command(name="slots", aliases=["s"])
    async def slot_machine(self, ctx, amount: str = '1'):
        if not await self.check_cooldown(ctx, "slots"):
            return

        user_id = ctx.author.id
        if not await self.bank_cog.check_account_and_send_message(ctx):
            return

        max_bet = await self.get_max_bet(user_id)

        if amount.lower() == 'all':
            self.c.execute("SELECT balance FROM bank WHERE user_id=?", (user_id,))
            balance_result = self.c.fetchone()
            if balance_result is None or balance_result[0] <= 0:
                await ctx.send("⚠️ Таны дансны үлдэгдэл хүрэлцэхгүй байна!")
                return
            amount = min(balance_result[0], max_bet)
        else:
            amount = self.parse_bet(amount)
            if amount is None:
                await ctx.send("❌ Буруу утга оруулсан байна. Та бүхэл тоо, all, 1k, 10k, 1m гэх мэт утга оруулна уу.")
                return

        if amount < self.MIN_BET:
            await ctx.send(f"⚠️ Таны бооцоо хамгийн багадаа **{self.MIN_BET}₮** байх ёстой!")
            return
        if amount > max_bet:
            await ctx.send(f"⚠️ Таны бооцоо **{max_bet:,}₮**-с хэтрэхгүй байх ёстой!")
            return

        self.c.execute("SELECT balance FROM bank WHERE user_id=?", (user_id,))
        balance_result = self.c.fetchone()
        if balance_result is None or balance_result[0] < amount:
            await ctx.send("⚠️ Таны дансны үлдэгдэл хүрэлцэхгүй байна!")
            return

        # Win streak систем
        if user_id not in self.win_streaks:
            self.win_streaks[user_id] = 0

        # 50% магадлалтай хожигдоно
        if random.randint(1, 100) <= 60:
            slot_result = random.sample(["🍒", "💎", "🍌", "🥝", "🎰"], 3)
            self.win_streaks[user_id] = 0
        else:
            # 3 ижил тэмдэг гарах магадлалыг тохируулах
            three_identical_weights = {
                "🍒": 30,  # 30% 🍒🍒🍒
                "💎": 10,  # 15% 💎💎💎
                "🍌": 5,  # 5% 🍌🍌🍌
                "🥝": 3,   # 3% 🥝🥝🥝
                "🎰": 1    # 1%  🎰🎰🎰
            }
            chosen_symbol = random.choices(list(three_identical_weights.keys()), weights=three_identical_weights.values(), k=1)[0]
            slot_result = [chosen_symbol] * 2
            self.win_streaks[user_id] += 1
        
        # Шагнал бодох
        multiplier_map = {"🍒": 1.5, "💎": 2, "🍌": 2.5, "🥝": 3, "🎰": 5}
        multiplier = multiplier_map.get(slot_result[0], 0) if len(set(slot_result)) == 1 else 0
        winnings = amount * multiplier if multiplier > 0 else -amount

        # Хэрэв multiplier = 0 бол (алдсан), мөнгийг данснаас хасах болон серверийн банк руу оруулах
        if multiplier == 0:
            self.bank_cog.update_balance('bank', ctx.author.id, -amount)  # Алдагдсан мөнгийг хасах
            await self.server_bank.update_balance(ctx.guild.id, amount)  # Серверийн банк руу мөнгө оруулах
        else:
            self.bank_cog.update_balance('bank', user_id, winnings)
        
        # Үр дүн харуулах
        slot_display = f"| {' | '.join(slot_result)} |"
        if multiplier > 0:
            result_text = (
                f"🎰 **SLOT MACHINE** 🎰\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🧑‍💼 Тоглогч: {ctx.author.mention}\n"
                f"💰 Бооцоо: **{amount:,}**₮\n"
                f"🎲 Үр дүн\n"
                f"{slot_display}\n"
                f"🏆 Шагнал: **+{amount * multiplier:,}₮ (x{multiplier})**\n"
                f"━━━━━━━━━━━━━━━━━━"
            )
        else:
            result_text = (
                f"🎰 **SLOT MACHINE** 🎰\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🧑‍💼 Тоглогч: **{ctx.author.display_name}**\n"
                f"💰 Бооцоо: **{amount:,}**₮\n"
                f"🎲 Үр дүн\n"
                f"{slot_display}\n"
                f"💀 Та алдлаа! **-{amount:,}**₮\n"
                f"━━━━━━━━━━━━━━━━━━"
            )

        await ctx.send(result_text)

    async def start_minefield(self, interaction, dimension, bombs, bet):
        user_id = interaction.user.id
        balance = self.bank_cog.get_balance(user_id, 'bank')

        if balance < bet:
            await interaction.response.send_message("⚠️ Таны дансны үлдэгдэл хүрэлцэхгүй байна!", ephemeral=True)
            return

        view = MinefieldView(interaction, self, bet, dimension, bombs)

        desc = '\n'.join(' '.join(view.grid[i * dimension:(i + 1) * dimension]) for i in range(dimension))

        embed = discord.Embed(
            title=f"💣 Minefield ({dimension}x{dimension}) эхэллээ!",
            description=f"Бооцоо: **{bet:,}₮**\n{desc}",
            color=discord.Color.green()
        )

        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.errors.NotFound:
            await interaction.followup.send(embed=embed, view=view)  # ⚠️ Хэрэв edit_message() ажиллахгүй бол followup.send ашиглах

    @commands.command(name='minefield', aliases=["mf"])
    async def minefield(self, ctx, bet: str = '1'):
        user_id = ctx.author.id

        # ✅ "all" бооцоо → max bet рүү хөрвүүлэх
        if bet.lower() == 'all':
            balance = self.bank_cog.get_balance(user_id, 'bank')
            max_bet = await self.get_max_bet(user_id)
            bet = min(balance, max_bet)  # Max bet болон balance-ийг харгалзах
        else:
            bet = self.parse_bet(bet)  # ✅ `1k`, `10k`, `1m` гэх мэт утгыг хөрвүүлэх

        # ✅ Хэрэглэгчийн max bet шалгах
        max_bet = await self.get_max_bet(user_id)
        if bet > max_bet:
            await ctx.send(f"❌ Таны дээд бооцоо **{max_bet:,}₮** тул илүү их бооцоо тавих боломжгүй!")
            return

        # ✅ Буруу утгатай бооцоо шалгах
        if bet is None or bet < self.MIN_BET:
            await ctx.send(f"❌ Буруу бооцоо! Хамгийн багадаа **{self.MIN_BET}₮** байна.")
            return

        balance = self.bank_cog.get_balance(user_id, 'bank')
        if balance < bet:
            await ctx.send("⚠️ Таны дансны үлдэгдэл хүрэлцэхгүй байна!")
            return

        view = discord.ui.View(timeout=None)

        # ✅ Minefield хэмжээний сонголт
        sizes = {"3x3": (3, 3), "4x4": (4, 5)}
        for label, (dimension, bombs) in sizes.items():
            button = discord.ui.Button(label=label, style=discord.ButtonStyle.primary)

            async def callback(interaction: discord.Interaction, dim=dimension, bom=bombs):
                await self.start_minefield(interaction, dim, bom, bet)  # ✅ `interaction` дамжуулах

            button.callback = callback
            view.add_item(button)

        embed = discord.Embed(
            title="📌 Minefield хэмжээ сонгоно уу!",
            description=f"Та **{bet:,}₮** бооцоо тавилаа. Талбарын хэмжээг сонгоно уу.",
            color=discord.Color.blurple()
        )

        await ctx.send(embed=embed, view=view)

async def setup(bot):
    bank_cog = bot.get_cog("Bank")
    vip_cog = bot.get_cog("VIP")
    await bot.add_cog(Game(bot, bank_cog, vip_cog))
    await bot.add_cog(ServerBank(bot))  # ServerBank когиос оруулах