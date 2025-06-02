import discord
from discord.ext import commands, tasks
import aiosqlite
import logging
import datetime
import asyncio
import json
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc)
expiry_date = now + timedelta(days=30)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# VIP түвшний тохиргоог JSON файлаас унших
with open('vip_levels.json', 'r', encoding='utf-8') as file:
    vip_data = json.load(file)

VIP_LEVELS = vip_data["VIP_LEVELS"]
DEFAULT_MAX_BET = vip_data["DEFAULT_MAX_BET"]
DEFAULT_COOLDOWN = vip_data["DEFAULT_COOLDOWN"]

class GiftVIPDropdown(discord.ui.Select):
    def __init__(self, ctx, vip_cog, target_user, vip_levels):
        self.ctx = ctx
        self.vip_cog = vip_cog
        self.target_user = target_user
        self.vip_levels = vip_levels  # vip_levels-г дамжуулах

        options = [
            discord.SelectOption(label=level, description=f"Үнэ: {info['price'] * 0.90:,}₮ - {info['days']} хоног", value=level)
            for level, info in self.vip_levels.items()
        ]

        super().__init__(placeholder="🎁 Бэлэглэх VIP түвшинг сонгоно уу!", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("⛔ Энэхүү цэсийг зөвхөн та ашиглаж болно!", ephemeral=True)

        await interaction.response.defer()
        selected_vip = self.values[0]

        success = await self.vip_cog.process_vip_purchase(interaction, self.ctx.author, selected_vip, is_gift=True, recipient=self.target_user)

        if success:
            await interaction.followup.send(f"🎁 **{self.ctx.author.display_name}** -> **{self.target_user.display_name}** руу **{selected_vip} VIP** амжилттай бэлэглэв! 💎 Энэ эрх **                       {(datetime.now() + timedelta(days=self.vip_levels[selected_vip]['days'])).strftime('%Y-%m-%d')}** хүртэл хүчинтэй.", ephemeral=False)
        else:
            return  # ❌ Хэрэв аль хэдийн амжилттай болвол, дахин алдааны хариу илгээхгүй!

class GiftVIPView(discord.ui.View):
    def __init__(self, ctx, vip_cog, target_user, vip_levels):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.vip_cog = vip_cog
        self.target_user = target_user
        self.vip_levels = vip_levels
        self.add_item(GiftVIPDropdown(ctx, vip_cog, target_user, vip_levels))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        await self.ctx.send("⏳ VIP бэлэглэх цэс хугацаа нь дууссан.", ephemeral=True)

# VIP худалдан авах товчлуур
class VIPBuyButton(discord.ui.Button):
    def __init__(self, level, vip_cog):
        super().__init__(label=f"🎟 {level} VIP авах", style=discord.ButtonStyle.primary, custom_id=f"buyvip_{level}")
        self.level = level
        self.vip_cog = vip_cog

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.vip_cog.process_vip_purchase(interaction, interaction.user, self.level)

# VIP худалдан авах товчлуурууд
class VIPButtons(discord.ui.View):
    def __init__(self, vip_cog):
        super().__init__(timeout=60)
        for level in VIP_LEVELS.keys():
            self.add_item(VIPBuyButton(level, vip_cog))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

# VIP системийн гол класс
class VIP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.setup_database())
        self.vip_levels = VIP_LEVELS

    async def setup_database(self):
        """📌 `aiosqlite` ашиглан мэдээллийн сангийн хүснэгтүүдийг тохируулах"""
        self.conn = await aiosqlite.connect("economy.db")
        await self.conn.execute("PRAGMA journal_mode=WAL;")
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users1 (
                user_id INTEGER PRIMARY KEY,
                vip_expiry DATETIME DEFAULT NULL,
                vip_level TEXT DEFAULT NULL,
                vip_count INTEGER DEFAULT 0,
                gifted_vip_count INTEGER DEFAULT 0,
                last_claimed DATETIME DEFAULT NULL
            )
        """)
        await self.conn.commit()
        logger.info("✅ VIP хүснэгтийг шалгаж дууслаа!")

        if not self.remove_expired_vip.is_running():
            self.remove_expired_vip.start()

    async def get_vip_level(self, user_id):
        """🎟 Хэрэглэгчийн VIP түвшинг асинхрон хэлбэрээр шалгах"""
        async with self.conn.execute("SELECT vip_level FROM users1 WHERE user_id=?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else None

    async def get_max_bet_for_user(self, user_id):
        vip_level = await self.get_vip_level(user_id)
        return self.vip_levels.get(vip_level, {}).get("max_bet", DEFAULT_MAX_BET)

    async def get_cooldown_for_user(self, user_id):
        vip_level = await self.get_vip_level(user_id)
        return self.vip_levels.get(vip_level, {}).get("cooldown", DEFAULT_COOLDOWN)

    async def check_vip(self, user_id) -> bool:
        async with self.conn.execute("SELECT vip_expiry FROM users1 WHERE user_id=?", (user_id,)) as cursor:
            vip_status = await cursor.fetchone()
        return bool(vip_status and vip_status[0] and datetime.strptime(vip_status[0], "%Y-%m-%d %H:%M:%S") > datetime.now())

    @commands.command(name="vip")
    async def vip(self, ctx):
        """VIP эрхийн мэдээлэл харуулах"""
        async with self.conn.execute("SELECT vip_expiry, vip_level, vip_count, gifted_vip_count FROM users1 WHERE user_id=?", (ctx.author.id,)) as cursor:
            vip_status = await cursor.fetchone()

        if not vip_status:
            return await ctx.send("⚠️ Та VIP эрхгүй байна. `mbuyvip` командаар VIP худалдан аваарай!")

        expiry_date, vip_level, vip_count, gifted_vip_count = vip_status

        if expiry_date and datetime.strptime(expiry_date.split(".")[0], "%Y-%m-%d %H:%M:%S") > datetime.now():
            embed = discord.Embed(title="💎 VIP мэдээлэл", color=discord.Color.gold())
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)
            embed.add_field(name="📅 VIP дуусах хугацаа", value=expiry_date[:10], inline=False)
            embed.add_field(name="🏆 VIP түвшин", value=vip_level, inline=True)
            embed.add_field(name="🔹 Нийт VIP авсан", value=f"{vip_count} удаа", inline=False)
            embed.add_field(name="🎁 Нийт VIP бэлэглэсэн", value=f"{gifted_vip_count} удаа", inline=True)

            embed.set_footer(text="🎟 **Та VIP түвшин шинэчлэх боломжтой!**")

            await ctx.send(embed=embed)
        else:
            await ctx.send("⚠️ Таны VIP эрх дууссан байна. `mbuyvip` командаар аваарай!")

    @commands.command(name="viptop")
    async def viptop(self, ctx):
        """📈 Хамгийн их VIP авсан болон бэлэглэсэн хэрэглэгчдийн жагсаалт"""
        async with self.conn.execute("SELECT user_id, vip_count, gifted_vip_count FROM users1 ORDER BY vip_count DESC, gifted_vip_count DESC LIMIT 10") as cursor:
            top_vip_users = await cursor.fetchall()

        embed = discord.Embed(title="💎 VIP Топ жагсаалт", color=discord.Color.gold())
        leaderboard = "🏆 Хамгийн их VIP авсан болон бэлэглэсэн:\n\n"
        leaderboard += "№  Хэрэглэгч            VIP авсан  VIP бэлэглэсэн\n"

        for i, (user_id, vip_count, gifted_vip_count) in enumerate(top_vip_users, start=1):
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            display_name = user.display_name if user else f"User({user_id})"

            leaderboard += f"#{i} {display_name[:20]:<20} - {vip_count} удаа  {gifted_vip_count} удаа\n"

        leaderboard += "\n"
        embed.description = leaderboard
        await ctx.send(embed=embed)

    @commands.command(name="buyvip")
    async def buy_vip(self, ctx):
        """VIP худалдан авах цэс харуулах"""
        embed = discord.Embed(title="💎 VIP ХУДАЛДАН АВАХ", color=discord.Color.gold())
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)
        embed.description = "Та авах VIP түвшинг сонгоно уу."

        for level, info in self.vip_levels.items():
            embed.add_field(name=f"🎟 {level}", value=f"💰 **{info['price']:,}₮** - {info['days']} хоног", inline=False)

        embed.set_footer(text="🎟 **VIP авахын тулд доорх товчийг дарна уу!**")

        view = VIPButtons(self)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="extendvip")
    async def extend_vip(self, ctx):
        async with self.conn.execute("SELECT vip_expiry, vip_level FROM users1 WHERE user_id=?", (ctx.author.id,)) as cursor:
            vip_status = await cursor.fetchone()

        if not vip_status or not vip_status[0]:
            return await ctx.send("❌ Танд сунгах VIP эрх байхгүй байна!")

        expiry_date, vip_level = vip_status

        # 🔹 expiry_date нь `None` эсвэл `datetime` төрөл биш бол хөрвүүлэх
        if expiry_date:
            if isinstance(expiry_date, str):
                expiry_date = datetime.strptime(expiry_date, "%Y-%m-%d %H:%M:%S")
        else:
            return await ctx.send("❌ Таны VIP хугацаа дууссан тул сунгах боломжгүй!")

        extend_price = self.vip_levels.get(vip_level, {}).get("extend_price")

        if extend_price is None:
            return await ctx.send("⚠️ Таны VIP түвшинд сунгах үнэ байхгүй байна!")

        async with self.conn.execute("SELECT balance FROM economy WHERE user_id=?", (ctx.author.id,)) as cursor:
            balance = (await cursor.fetchone() or [0])[0]

        if balance < extend_price:
            return await ctx.send(f"❌ Танд сунгалт хийхэд {extend_price:,}₮ хэрэгтэй байна!")

        # 🔹 VIP хугацааг сунгах
        new_expiry = expiry_date + timedelta(days=self.vip_levels[vip_level]["days"])

        await self.conn.execute("UPDATE economy SET balance = balance - ? WHERE user_id=?", (extend_price, ctx.author.id))
        await self.conn.execute("UPDATE users1 SET vip_expiry = ? WHERE user_id=?", (new_expiry.strftime("%Y-%m-%d %H:%M:%S"), ctx.author.id))
        await self.conn.commit()

        await ctx.send(f"✅ Таны VIP сунгагдаж, шинэ дуусах хугацаа: **{new_expiry.strftime('%Y-%m-%d')}** боллоо.")

    @commands.command(name="dailyvip")
    async def daily_vip_bonus(self, ctx):
        async with self.conn.execute("SELECT vip_level, last_claimed FROM users1 WHERE user_id=?", (ctx.author.id,)) as cursor:
            vip_status = await cursor.fetchone()

        if not vip_status or not vip_status[0]:
            return await ctx.send("❌ Та VIP эрхгүй тул энэ командыг ашиглах боломжгүй!")

        vip_level, last_claimed = vip_status
        today = datetime.now().strftime("%Y-%m-%d")
    
        if last_claimed == today:
            return await ctx.send("⏳ Та өнөөдөр аль хэдийн урамшууллаа авсан байна!")

        bonus = self.vip_levels[vip_level]["bonus"]

        await self.conn.execute("UPDATE economy SET balance = balance + ? WHERE user_id=?", (bonus, ctx.author.id))
        await self.conn.execute("UPDATE users1 SET last_claimed = ? WHERE user_id=?", (today, ctx.author.id))
        await self.conn.commit()

        embed = discord.Embed(title="🎁 VIP Өдөр тутмын урамшуулал!", color=discord.Color.gold())
        embed.add_field(name="VIP түвшин", value=vip_level)
        embed.add_field(name="Шагнал", value=f"{bonus:,}₮")
        await ctx.send(embed=embed)

    @commands.command(name="fixgiftvip")
    async def giftvip(self, ctx, user: discord.Member):
        """💳 Найздаа VIP эрх бэлэглэх"""
        if ctx.author.id == user.id:
            return await ctx.send("⚠️ Та өөртөө VIP эрх бэлэглэж болохгүй!")

        async with self.conn.execute("SELECT vip_expiry FROM users1 WHERE user_id=?", (ctx.author.id,)) as cursor:
            sender_vip = await cursor.fetchone()

        if not sender_vip or not sender_vip[0]:
            return await ctx.send("⚠️ Та VIP эрхгүй тул бусдад VIP бэлэглэх боломжгүй!")

        embed = discord.Embed(title="🎁 VIP эрх бэлэглэх", description=f"💡 {user.mention} -д ямар түвшний VIP эрх бэлэглэх вэ?", color=discord.Color.gold())
        embed.set_footer(text="🎟 Доорх цэсээс сонголтоо хийнэ үү.")

        view = GiftVIPView(ctx, self, user, self.vip_levels)  # vip_levels-г дамжуулах
        await ctx.send(embed=embed, view=view)

    async def process_vip_purchase(self, interaction: discord.Interaction, user, level, is_gift=False, recipient: discord.Member = None):
        """🎟 VIP худалдан авах болон бэлэглэх үйл явц"""

        if level not in self.vip_levels:
            return await interaction.followup.send(f"⚠️ **{level}** түвшин байхгүй байна!", ephemeral=True)

        level_info = self.vip_levels[level]
        price = level_info["price"]
        days = level_info["days"]

        # Хэрвээ бэлэглэж байгаа бол хямдралын хувь
        if is_gift:
            discount = level_info.get("gift_discount", 1.0)
            price = int(price * discount)

        # Балансыг шалгаж хасах мөнгө
        async with self.conn.execute("SELECT balance FROM economy WHERE user_id=?", (user.id,)) as cursor:
            row = await cursor.fetchone()
            balance = row[0] if row else 0

        if balance < price:
            return await interaction.followup.send(f"⚠️ VIP авахад танд **{price:,}₮** хэрэгтэй байна!", ephemeral=True)

        # Мөнгө хасах, зөвхөн нэг удаа
        await self.conn.execute(
            "UPDATE economy SET balance = balance - ? WHERE user_id=? AND balance >= ?",
            (price, user.id, price)
        )

        # VIP хугацааг шинэчлэх эсвэл сунгах
        expiry_date_str = ""
        async with self.conn.execute("SELECT vip_expiry FROM users1 WHERE user_id=?", (user.id,)) as cursor:
            row = await cursor.fetchone()
            current_expiry = None
            if row and row[0]:
                current_expiry = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")

        new_expiry = datetime.now() + timedelta(days=days)
        if current_expiry and current_expiry > datetime.now():
            new_expiry = max(current_expiry, datetime.now()) + timedelta(days=days)

        expiry_date_str = new_expiry.strftime("%Y-%m-%d %H:%M:%S")

        # VIP мэдээллийг шинэчлэх
        await self.conn.execute("""
            INSERT INTO users1 (user_id, vip_expiry, vip_level, vip_count, gifted_vip_count) 
            VALUES (?, ?, ?, ?, ?) 
            ON CONFLICT(user_id) DO UPDATE SET
                vip_expiry=excluded.vip_expiry,
                vip_level=excluded.vip_level,
                vip_count=COALESCE(users1.vip_count, 0) + 1,
                gifted_vip_count=COALESCE(users1.gifted_vip_count, 0) + (1 if ? else 0)
        """, (
            user.id, expiry_date_str, level, 1 if not is_gift else 0, 1 if is_gift else 0
        ))

        # Хэрвээ бэлэглэж байгаа бол
        if is_gift:
            await self.conn.execute("UPDATE users1 SET gifted_vip_count = gifted_vip_count + 1 WHERE user_id=?", (user.id,))

        await self.conn.commit()

        # Үр дүнг илэрхийлэх
        if is_gift:
            await interaction.followup.send(
                f"✅ **{user.display_name}** → **{recipient.display_name}** рүү **{level} VIP** эрхийг **{price:,}₮**-өөр бэлэглэлээ! 💎 Энэ эрх **{expiry_date_str[:10]}** хүртэл хүчинтэй.",
                ephemeral=False
            )
        else:
            embed = discord.Embed(title="✅ VIP эрх амжилттай авлаа!", color=discord.Color.green())
            embed.set_author(name=user.display_name, icon_url=user.avatar.url)
            embed.add_field(name="📅 VIP дуусах хугацаа", value=expiry_date_str[:10], inline=False)
            embed.add_field(name="🏆 VIP түвшин", value=level, inline=True)
            embed.set_footer(text="🎟 **VIP мэдээлэл харах бол mvip командыг ашиглаарай!**")
            await interaction.followup.send(embed=embed)


    @tasks.loop(hours=1)
    async def remove_expired_vip(self):
        try:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")  # Зөв ашиглалт
            async with self.conn.execute(
                "UPDATE users1 SET vip_expiry = NULL, vip_level = NULL WHERE vip_expiry IS NOT NULL AND vip_expiry < ?",
                (now,),
            ):
                await self.conn.commit()
            logger.info("✅ Хугацаа нь дууссан VIP эрхүүдийг амжилттай устгалаа!")
        except Exception as e:
            logger.error(f"❌ Хугацаа нь дууссан VIP эрхүүдийг устгахад алдаа гарлаа: {e}")

    async def cog_unload(self):
        """Ког устгахад таскуудыг зогсоох"""
        if self.remove_expired_vip.is_running():
            self.remove_expired_vip.cancel()
        await self.conn.close()

async def setup(bot):
    await bot.add_cog(VIP(bot))  # 🛠 Ботод VIP когийг нэмэх