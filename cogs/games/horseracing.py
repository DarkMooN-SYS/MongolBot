import discord
from discord.ext import commands
import random
import asyncio
import logging
import re
from typing import Dict, Any, Optional
from ..utils.database import get_async_db_context

# Лог үүсгэх
logger = logging.getLogger(__name__)

horses = {
    1: "Их Хааны Морь",
    2: "Говийн Салхи", 
    3: "Хүлэг Баатар",
    4: "Тэнгэрийн Хүлэг",
    5: "Ширмэн Туяа"
}

class HorseRacing(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.races: Dict[int, Dict[str, Any]] = {}  # Сервер бүрийн уралдааны төлөв хадгалах

    def get_race_data(self, guild_id: int) -> Dict[str, Any]:
        """Серверийн уралдааны өгөгдлийг авах."""
        if guild_id not in self.races:
            self.races[guild_id] = {
                "active": False,
                "bets": {},
                "positions": {number: 0 for number in horses.keys()},
                "task": None,
            }
        return self.races[guild_id]

    def number(self, number_str: str) -> float:
        """Товчилсон хэлбэрийг (1k, 10k, 1m, 1.5k, 2.3m) бодит тоо болгон хөрвүүлэх."""
        number_str = number_str.lower().strip().replace(",", ".")
        
        # Хэмжээг томъёолсон үсгүүд ба тэдний утга
        multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000, "t": 1_000_000_000_000}
        
        # 1.5k, 10m гэх мэт форматыг зөвшөөрнө
        match = re.fullmatch(r"(\d+(\.\d+)?)([kmbt]?)", number_str)
        if not match:
            raise ValueError("❌ Буруу формат! Зөвшөөрөгдсөн хэлбэр: 1.5k, 10m, 2.3b, 5.55k")

        num, _, suffix = match.groups()  # `num` нь тоо, `suffix` нь хэмжүүр (k, m, b, t)

        try:
            return float(num) * multipliers.get(suffix, 1)
        except ValueError:
            raise ValueError("❌ Алдаа гарлаа! Тоог хөрвүүлэх боломжгүй байна.")

    @commands.command(name="uraldaan")
    @commands.has_permissions(administrator=True)
    async def start_race(self, ctx: commands.Context, action: str):
        """Уралдааныг эхлүүлэх эсвэл дуусгах."""
        if not ctx.guild:
            await ctx.send("Энэ командыг зөвхөн сервер дээр ашиглаж болно.")
            return
            
        guild_id = ctx.guild.id
        race_data = self.get_race_data(guild_id)

        if action == "ehleh":
            if race_data["active"]:
                await ctx.send("Уралдаан аль хэдийн эхэлсэн байна!")
                return
                
            race_data["active"] = True
            race_data["bets"].clear()
            race_data["positions"] = {number: 0 for number in horses.keys()}

            horse_list = "\n".join([f"{number}: {name}" for number, name in horses.items()])
            await ctx.send(
                f"**🐎 Морины Уралдаан Эхэллээ!**\nБооцоо тавихын тулд `>bootsoo [морины дугаар] [мөнгө]` командыг ашиглана уу.\n\n"
                f"**Морьдын жагсаалт:**\n{horse_list}"
            )

            # Countdown
            countdown_message = await ctx.send("Уралдаан эхлэхэд: `2м:00сек` үлдлээ.")
            for remaining_time in range(120, 0, -1):
                minutes, seconds = divmod(remaining_time, 60)
                time_message = f"{minutes}м:{seconds:02d}сек"
                await countdown_message.edit(content=f"Уралдаан эхлэхэд: `{time_message}` үлдлээ.")
                await asyncio.sleep(1)

            await ctx.send("🐎 Уралдаан эхэллээ! 🏁")
            race_data["task"] = self.bot.loop.create_task(self.run_race(ctx, guild_id))

        elif action == "duusah":
            if not race_data["active"]:
                await ctx.send("Уралдаан эхлээгүй байна.")
                return

            if race_data["task"]:
                race_data["task"].cancel()
                race_data["task"] = None
  
            # Бооцоог буцаах
            async with get_async_db_context('economy') as db:
                for user_id, bet in race_data["bets"].items():
                    try:
                        # Бооцооны мөнгийг буцаана
                        await db.execute("UPDATE economy SET balance = balance + ? WHERE user_id = ?", (bet["amount"], user_id))
                    except Exception as e:
                        await ctx.send(f"⚠️ Алдаа гарлаа: {e}")

                await db.commit()

            race_data["active"] = False
            race_data["bets"].clear()
            race_data["positions"].clear()
            await ctx.send("Уралдаан цуцлагдлаа. Бооцоог буцаалаа.")

    @commands.command(name="bootsoo")
    async def place_bet(self, ctx: commands.Context, horse_number: int, amount: str):
        """Бооцоо тавих."""
        if not ctx.guild:
            await ctx.send("Энэ командыг зөвхөн сервер дээр ашиглаж болно.")
            return

        try:
            amount_float = self.number(amount)
        except ValueError as e:
            await ctx.send(str(e))
            return
            
        if amount_float <= 0:
            await ctx.send("⚠️ Та 0 буюу түүнээс бага мөнгө тавих боломжгүй!")
            return

        guild_id = ctx.guild.id
        race_data = self.get_race_data(guild_id)

        if not race_data["active"]:
            await ctx.send("⚠️ Уралдаан эхлээгүй байна. `>uraldaan ehleh` командыг ашиглана уу.")
            return

        if race_data["positions"] and any(pos > 0 for pos in race_data["positions"].values()):
            await ctx.send("⚠️ Уралдаан аль хэдийн эхэлсэн тул бооцоо тавих боломжгүй.")
            return

        if horse_number not in horses:
            horse_list = "\n".join([f"{number}: {name}" for number, name in horses.items()])
            await ctx.send(f"⚠️ Буруу морины дугаар байна. Боломжит морьд:\n{horse_list}")
            return

        if ctx.author.id in race_data["bets"]:
            await ctx.send("⚠️ Та аль хэдийн бооцоо тавьсан байна!")
            return

        async with get_async_db_context('economy') as db:
            await db.execute(
                "INSERT OR IGNORE INTO economy (user_id, balance) VALUES (?, 5000)",
                (ctx.author.id,)
            )
            await db.commit()

            async with db.execute("SELECT balance FROM economy WHERE user_id = ?", (ctx.author.id,)) as cursor:
                result = await cursor.fetchone()

            user_balance = result[0] if result else 0
            if user_balance < amount_float:
                await ctx.send(f"⚠️ Таны үлдэгдэл хүрэлцэхгүй байна! Одоогийн үлдэгдэл: {user_balance:,} ₮")
                return
                
            await db.execute("UPDATE economy SET balance = balance - ? WHERE user_id = ?", (amount_float, ctx.author.id))
            await db.commit()

        race_data["bets"][ctx.author.id] = {"horse": horse_number, "amount": amount_float}
        await ctx.send(f"✅ {ctx.author.mention} **{horses[horse_number]}** дээр **{amount_float:,.0f}₮** бооцоо тавилаа!")

    async def run_race(self, ctx: commands.Context, guild_id: int):
        """Уралдааныг удирдах."""
        race_data = self.get_race_data(guild_id)
        race_message = await ctx.send("**🐎 Уралдааны Явц:**")
        race_finished = False

        while not race_finished:
            for number in horses.keys():
                # Бүх морины хурдыг ижил хурдтай, шударга явуулна
                race_data["positions"][number] += random.randint(1, 5)  # Бүх морь тэгш хурдаар давхина

                if race_data["positions"][number] >= 150:
                    race_finished = True
                    break

            race_status = "\n".join(
                [f"{horses[number]}:\n{'-' * (pos // 2)}🐎" for number, pos in race_data["positions"].items()]
            )
            await race_message.edit(content=f"🐎 **Уралдааны Явц:**\n{race_status}")
            await asyncio.sleep(5)

        winner_number = max(race_data["positions"], key=race_data["positions"].get)
        await ctx.send(f"🏁 **{horses[winner_number]} яллаа!**")
        await self.distribute_rewards(ctx, guild_id, winner_number)
        race_data["active"] = False
        race_data["positions"] = {number: 0 for number in horses.keys()}

    async def distribute_rewards(self, ctx: commands.Context, guild_id: int, winner_number: int):
        """Шагнал тараах."""
        race_data = self.get_race_data(guild_id)
        if not race_data["bets"]:
            await ctx.send("⚠️ Бооцоо тавьсан хэрэглэгч алга байна.")
            return

        winners = []
        losers = []

        async with get_async_db_context('economy') as db:
            for user_id, bet in race_data["bets"].items():
                try:
                    if bet["horse"] == winner_number:
                        # Хожсон хэрэглэгчид шагнал нэмэх
                        reward = bet["amount"] * 3
                        await db.execute("UPDATE economy SET balance = balance + ? WHERE user_id = ?", (reward, user_id))
                        winners.append(f"<@{user_id}> шагнал: {reward:,.0f} ₮")
                    else:
                        # Хожигдсон хэрэглэгчийг жагсаалтанд нэмэх
                        losers.append(f"<@{user_id}>")
                except Exception as e:
                    await ctx.send(f"⚠️ Алдаа гарлаа: {e}")

            await db.commit()

        if winners:
            await ctx.send(f"🏆 **Хожсон хэрэглэгчид:**\n{chr(10).join(winners)}")
        else:
            await ctx.send("😞 Хожсон хэрэглэгч алга.")

        if losers:
            await ctx.send(f"😔 **Хожигдсон хэрэглэгчид:**\n{', '.join(losers)}")

# Add the cog to your bot
async def setup(bot: commands.Bot):
    await bot.add_cog(HorseRacing(bot))
