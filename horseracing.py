import discord
from discord.ext import commands
import random
import aiosqlite
import asyncio
import sqlite3
import logging
import re

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
    def __init__(self, bot):
        self.bot = bot
        self.races = {}  # Сервер бүрийн уралдааны төлөв хадгалах
        self.conn = None
        self.cursor = None
        self.connect_db()  # 🔹 Өгөгдлийн сантай холбох
        self.owner_id = "751055793893146624"  # Энд өөрийн ID-г оруулна уу

    def connect_db(self):
        """🔹 SQLite өгөгдлийн санг холбох."""
        if self.conn is None:
            self.conn = sqlite3.connect("economy.db", check_same_thread=False, isolation_level=None)
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.cursor = self.conn.cursor()  # 🔹 Курсор үүсгэх

    def ensure_connection(self):
        """🔹 Өгөгдлийн сантай холбогдсон эсэхийг шалгах."""
        try:
            if self.conn is None:
                self.connect_db()
            self.conn.execute("SELECT 1")  # 🔹 Мэдээллийн сан амьд эсэхийг шалгах
        except sqlite3.ProgrammingError:
            logger.error("⚠️ SQLite: Мэдээллийн сан хаагдсан байна! Шинэ холболт үүсгэж байна...")
            self.connect_db()

    async def cog_check(self, ctx):
        """Зөв серверт ажиллаж байгаа эсэхийг шалгана."""
        allowed_guild_ids = [1312484212150108232, 1301022951734382612, 1297446169995251712]
        if ctx.guild.id in allowed_guild_ids:
            return True
        else:
            await ctx.send("Энэ команд зөвхөн тусгай сервер дээр ажилладаг.")
            return False

    def get_race_data(self, guild_id):
        """Серверийн уралдааны өгөгдлийг авах."""
        if guild_id not in self.races:
            self.races[guild_id] = {
                "active": False,
                "bets": {},
                "positions": {number: 0 for number in horses.keys()},
                "task": None,
            }
        return self.races[guild_id]

    def number(self, number_str):
        """Товчилсон хэлбэрийг (1k, 10k, 1m, 1.5k, 2.3m) бодит тоо болгон хөрвүүлэх."""
        number_str = number_str.lower().strip().replace(",", ".")
        
        # Хэмжээг томъёолсон үсгүүд ба тэдний утга
        multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000, "t": 1_000_000_000_000}
        
        # 1.5k, 10m гэх мэт форматыг зөвшөөрнө
        match = re.fullmatch(r"(\d+(\.\d+)?)([kmbt]?)", number_str)
        if not match:
            return "❌ Буруу формат! Зөвшөөрөгдсөн хэлбэр: 1.5k, 10m, 2.3b, 5.55k"

        num, _, suffix = match.groups()  # `num` нь тоо, `suffix` нь хэмжүүр (k, m, b, t)

        try:
            return float(num) * multipliers.get(suffix, 1)
        except ValueError:
            return "❌ Алдаа гарлаа! Тоог хөрвүүлэх боломжгүй байна."

    @commands.command(name="uraldaan")
    @commands.has_permissions(administrator=True)
    async def start_race(self, ctx, action: str):
        """Уралдааныг эхлүүлэх эсвэл дуусгах."""
        guild_id = ctx.guild.id
        race_data = self.get_race_data(guild_id)

        if action == "ehleh":
            if race_data["active"]:
                await ctx.send("Уралдаан аль хэдийн эхэлсэн байна!")
                return

            race_data["active"] = True
            race_data["bets"].clear()
            race_data["positions"] = {number: 0 for number in horses.keys()}
            race_data["owner_id"] = self.owner_id if ctx.author.id == self.owner_id else ctx.author.id

            horse_list = "\n".join([f"{number}: {name}" for number, name in horses.items()])
            await ctx.send(
                f"**<:52FE94ABD1D240EA97065C9B88A7E254:1326040797371568189> Морины Уралдаан Эхэллээ!**\nБооцоо тавихын тулд `mbootsoo [морины дугаар] [мөнгө]` командыг ашиглана уу.\n\n"
                f"**Морьдын жагсаалт:**\n{horse_list}"
            )

            # Countdown
            countdown_message = await ctx.send("Уралдаан эхлэхэд: `2м:00сек` үлдлээ.")
            for remaining_time in range(120, 0, -1):
                minutes, seconds = divmod(remaining_time, 60)
                time_message = f"{minutes}м:{seconds:02d}сек"
                await countdown_message.edit(content=f"Уралдаан эхлэхэд: `{time_message}` үлдлээ.")
                await asyncio.sleep(1)

            await ctx.send("<:52FE94ABD1D240EA97065C9B88A7E254:1326040797371568189> Уралдаан эхэллээ! 🏁")
            race_data["task"] = self.bot.loop.create_task(self.run_race(ctx, guild_id))

        elif action == "duusah":
            if not race_data["active"]:
                await ctx.send("Уралдаан эхлээгүй байна.")
                return

            if race_data["task"]:
                race_data["task"].cancel()
                race_data["task"] = None
  
            # Бооцоог буцаах
            async with aiosqlite.connect("economy.db") as db:
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
    async def place_bet(self, ctx, horse_number: int, amount: str):
        """Бооцоо тавих."""
        self.ensure_connection()  # 🔹 Холболтыг шалгах

        amount = self.number(amount)
        if amount is None or amount <= 0:
            await ctx.send("⚠️ Та 0 буюу түүнээс бага мөнгө тавих боломжгүй!")
            return

        guild_id = ctx.guild.id
        race_data = self.get_race_data(guild_id)

        if not race_data["active"]:
            await ctx.send("⚠️ Уралдаан эхлээгүй байна. `!uraldaan ehleh` командыг ашиглана уу.")
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

        async with aiosqlite.connect("economy.db") as db:
            await db.execute(
                "INSERT OR IGNORE INTO economy (user_id, balance) VALUES (?, 5000)",
                (ctx.author.id,)
            )
            await db.commit()

            async with db.execute("SELECT balance FROM economy WHERE user_id = ?", (ctx.author.id,)) as cursor:
                result = await cursor.fetchone()

            user_balance = result[0] if result else 0
            if user_balance < amount:
                await ctx.send(f"⚠️ Таны үлдэгдэл хүрэлцэхгүй байна! Одоогийн үлдэгдэл: {user_balance:,} ₮")
                return

            await db.execute("UPDATE economy SET balance = balance - ? WHERE user_id = ?", (amount, ctx.author.id))
            await db.commit()

        race_data["bets"][ctx.author.id] = {"horse": horse_number, "amount": amount}
        await ctx.send(f"✅ {ctx.author.mention} **{horses[horse_number]}** дээр **{amount:,}₮** бооцоо тавилаа!")

    async def run_race(self, ctx, guild_id):
        """Уралдааныг удирдах."""
        race_data = self.get_race_data(guild_id)
        race_message = await ctx.send("**<:52FE94ABD1D240EA97065C9B88A7E254:1326040797371568189> Уралдааны Явц:**")
        race_finished = False
        owner_id = race_data["owner_id"]  # Owner-ийн ID-г авах

        while not race_finished:
            for number in horses.keys():
                # Owner-ийн морь илүү хурдан явна
                if owner_id in race_data["bets"] and race_data["bets"][owner_id]["horse"] == number:
                    race_data["positions"][number] += random.randint(1, 7)  # Owner-ийн морь илүү хурдан
                else:
                    race_data["positions"][number] += random.randint(1, 5)  # Бусад морьдууд

                if race_data["positions"][number] >= 150:
                    race_finished = True
                    break

            race_status = "\n".join(
                [f"{horses[number]}:\n{'-' * (pos // 2)}<:52FE94ABD1D240EA97065C9B88A7E254:1326040797371568189>" for number, pos in race_data["positions"].items()]
            )
            await race_message.edit(content=f"<:52FE94ABD1D240EA97065C9B88A7E254:1326040797371568189> **Уралдааны Явц:**\n{race_status}")
            await asyncio.sleep(5)

        winner_number = max(race_data["positions"], key=race_data["positions"].get)
        await ctx.send(f"🏁 **{horses[winner_number]} яллаа!**")
        await self.distribute_rewards(ctx, guild_id, winner_number)
        race_data["active"] = False
        race_data["positions"] = {number: 0 for number in horses.keys()}

    async def distribute_rewards(self, ctx, guild_id, winner_number):
        """Шагнал тараах."""
        race_data = self.get_race_data(guild_id)
        if not race_data["bets"]:
            await ctx.send("⚠️ Хожсон бооцоо тавьсан хэрэглэгч алга байна.")
            return

        winners = []
        losers = []

        async with aiosqlite.connect("economy.db") as db:
            for user_id, bet in race_data["bets"].items():
                try:
                    if bet["horse"] == winner_number:
                        # Хожсон хэрэглэгчид шагнал нэмэх
                        reward = bet["amount"] * 3
                        await db.execute("UPDATE economy SET balance = balance + ? WHERE user_id = ?", (reward, user_id))
                        winners.append(f"<@{user_id}> шагнал: {reward:,} ₮")
                    else:
                        # Хожигдсон хэрэглэгчийг жагсаалтанд нэмэх
                        losers.append(f"<@{user_id}>")
                except Exception as e:
                    await ctx.send(f"⚠️ Алдаа гарлаа: {e}")

            await db.commit()

        if winners:
            await ctx.send(f"🏆 **Хожсон хэрэглэгчид:**\n{', '.join(winners)}")
        else:
            await ctx.send("😞 Хожсон хэрэглэгч алга.")

        if losers:
            await ctx.send(f"😔 **Хожигдсон хэрэглэгчид:**\n{', '.join(losers)}")

# Add the cog to your bot
async def setup(bot):
    await bot.add_cog(HorseRacing(bot))