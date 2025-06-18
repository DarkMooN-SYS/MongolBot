import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import aiosqlite
from typing import Optional, Dict, Any, Tuple, Union
from ..utils.database import get_async_db_context

# Set up logging
logger = logging.getLogger(__name__)

# VIP түвшний тохиргоог JSON файлаас унших
json_path = os.path.join(os.path.dirname(__file__), 'vip_levels.json')
try:
    with open(json_path, 'r', encoding='utf-8') as file:
        vip_data = json.load(file)
        VIP_LEVELS = vip_data["VIP_LEVELS"]
        DEFAULT_MAX_BET = vip_data["DEFAULT_MAX_BET"]
        DEFAULT_COOLDOWN = vip_data["DEFAULT_COOLDOWN"]
except FileNotFoundError:
    logger.error(f"⚠️ vip_levels.json файл олдсонгүй: {json_path}")
    VIP_LEVELS = {}
    DEFAULT_MAX_BET = 300000
    DEFAULT_COOLDOWN = 10
except json.JSONDecodeError:
    logger.error("⚠️ vip_levels.json файлын формат буруу байна!")
    VIP_LEVELS = {}
    DEFAULT_MAX_BET = 300000
    DEFAULT_COOLDOWN = 10

class GiftVIPDropdown(discord.ui.Select):
    def __init__(self, ctx: commands.Context, vip_cog: Any, target_user: discord.Member, vip_levels: Dict[str, Dict[str, Any]]):
        super().__init__(
            placeholder="🎁 VIP түвшин сонгох",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=level,
                    description=f"{info['price']:,}₮ - {info['days']} хоног",
                    value=level
                ) for level, info in vip_levels.items()
            ]
        )
        self.ctx = ctx
        self.vip_cog = vip_cog
        self.target_user = target_user

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("⚠️ Та энэ сонголтыг хийх эрхгүй!", ephemeral=True)
            return

        await interaction.response.defer()
        level = self.values[0]
        await self.vip_cog.process_vip_purchase(interaction, interaction.user, level, True, self.target_user)

class GiftVIPView(discord.ui.View):
    def __init__(self, ctx: commands.Context, vip_cog: Any, target_user: discord.Member, vip_levels: Dict[str, Dict[str, Any]]):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.vip_cog = vip_cog
        self.target_user = target_user
        self.vip_levels = vip_levels
        self.add_item(GiftVIPDropdown(ctx, vip_cog, target_user, vip_levels))

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Select):
                item.disabled = True
        try:
            await self.ctx.send("⏳ VIP бэлэглэх цэс хугацаа нь дууссан.", ephemeral=True)
        except:
            pass

class VIPBuyButton(discord.ui.Button):
    def __init__(self, level: str, vip_cog: Any):
        super().__init__(
            label=f"🎟 {level} VIP авах",
            style=discord.ButtonStyle.primary,
            custom_id=f"buyvip_{level}"
        )
        self.level = level
        self.vip_cog = vip_cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await self.vip_cog.process_vip_purchase(interaction, interaction.user, self.level)

class VIPButtons(discord.ui.View):
    def __init__(self, vip_cog: Any):
        super().__init__(timeout=60)
        for level in VIP_LEVELS.keys():
            self.add_item(VIPBuyButton(level, vip_cog))

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

class VIP(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.vip_levels = VIP_LEVELS
        # Start the periodic task after database setup in on_ready

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Бот асахад хүү тооцоолох процессыг эхлүүлэх"""
        await self.setup_database()

    async def setup_database(self) -> None:
        """📌 Database холболт тохируулах"""
        try:
            async with get_async_db_context('economy') as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS users1 (
                        user_id INTEGER PRIMARY KEY,
                        vip_expiry DATETIME DEFAULT NULL,
                        vip_level TEXT DEFAULT NULL,
                        vip_count INTEGER DEFAULT 0,
                        gifted_vip_count INTEGER DEFAULT 0,
                        last_claimed DATETIME DEFAULT NULL
                    )
                """)
                await db.commit()
                logger.info("✅ VIP хүснэгтийг шалгаж дууслаа!")

            # Start the periodic task after database setup
            if not self.remove_expired_vip.is_running():
                self.remove_expired_vip.start()
                logger.info("✅ VIP хугацаа шалгах процессыг эхлүүллээ!")
        except Exception as e:
            logger.error(f"❌ VIP database тохируулахад алдаа: {e}")

    async def get_vip_level(self, user_id: int) -> Optional[str]:
        """🎟 Хэрэглэгчийн VIP түвшинг асинхрон хэлбэрээр шалгах"""
        try:
            async with get_async_db_context('economy') as db:
                async with db.execute("SELECT vip_level FROM users1 WHERE user_id=?", (user_id,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else None
        except Exception:
            return None

    async def get_max_bet_for_user(self, user_id: int) -> int:
        vip_level = await self.get_vip_level(user_id)
        return self.vip_levels.get(vip_level, {}).get("max_bet", DEFAULT_MAX_BET)

    async def get_cooldown_for_user(self, user_id: int) -> int:
        vip_level = await self.get_vip_level(user_id)
        return self.vip_levels.get(vip_level, {}).get("cooldown", DEFAULT_COOLDOWN)

    async def check_vip(self, user_id: int) -> bool:
        """VIP эрх хүчинтэй эсэхийг шалгах"""
        try:
            async with get_async_db_context('economy') as db:
                async with db.execute("SELECT vip_expiry FROM users1 WHERE user_id=?", (user_id,)) as cursor:
                    vip_status = await cursor.fetchone()
                    if vip_status and vip_status[0]:
                        return datetime.strptime(vip_status[0], "%Y-%m-%d %H:%M:%S") > datetime.now()
                    return False
        except Exception:
            return False

    def get_user_avatar_url(self, user: Union[discord.Member, discord.User]) -> Optional[str]:
        """Хэрэглэгчийн avatar URL-ийг авах"""
        if user and user.avatar:
            return str(user.avatar.url)
        return None

    async def get_user_data(self, user_id: int) -> Optional[Tuple[str, str, int, int]]:
        """Хэрэглэгчийн VIP мэдээллийг авах"""
        try:
            async with get_async_db_context('economy') as db:
                async with db.execute(
                    "SELECT vip_expiry, vip_level, vip_count, gifted_vip_count FROM users1 WHERE user_id=?", 
                    (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return None
                    return (
                        str(row[0]) if row[0] else "",  # vip_expiry
                        str(row[1]) if row[1] else "",  # vip_level
                        int(row[2]) if row[2] else 0,   # vip_count
                        int(row[3]) if row[3] else 0    # gifted_vip_count
                    )
        except Exception:
            return None

    async def get_balance(self, user_id: int) -> int:
        """Хэрэглэгчийн balance авах"""
        try:
            async with get_async_db_context('economy') as db:
                async with db.execute("SELECT balance FROM economy WHERE user_id=?", (user_id,)) as cursor:
                    row = await cursor.fetchone()
                    return int(row[0]) if row and row[0] else 0
        except Exception:
            return 0

    async def update_balance(self, user_id: int, amount: int) -> bool:
        """Хэрэглэгчийн balance өөрчлөх"""
        try:
            async with get_async_db_context('economy') as db:
                await db.execute(
                    "UPDATE economy SET balance = balance + ? WHERE user_id = ?",
                    (amount, user_id)
                )
                await db.commit()
                return True
        except Exception:
            return False

    @commands.command(name="vip")
    async def vip(self, ctx: commands.Context) -> Optional[discord.Message]:
        """VIP эрхийн мэдээлэл харуулах"""
        data = await self.get_user_data(ctx.author.id)
        if not data:
            return await ctx.send("⚠️ Та VIP эрхгүй байна. `mbuyvip` командаар VIP худалдан аваарай!")

        expiry_date, vip_level, vip_count, gifted_vip_count = data
        if expiry_date and datetime.strptime(expiry_date.split(".")[0], "%Y-%m-%d %H:%M:%S") > datetime.now():
            embed = discord.Embed(title="💎 VIP мэдээлэл", color=discord.Color.gold())
            embed.set_author(name=ctx.author.display_name)
            avatar_url = self.get_user_avatar_url(ctx.author)
            if avatar_url:
                embed.set_author(name=ctx.author.display_name, icon_url=avatar_url)
            
            embed.add_field(name="📅 VIP дуусах хугацаа", value=expiry_date[:10], inline=False)
            embed.add_field(name="🏆 VIP түвшин", value=vip_level, inline=True)
            embed.add_field(name="🔹 Нийт VIP авсан", value=f"{vip_count} удаа", inline=False)
            embed.add_field(name="🎁 Нийт VIP бэлэглэсэн", value=f"{gifted_vip_count} удаа", inline=True)
            embed.set_footer(text="🎟 **Та VIP түвшин шинэчлэх боломжтой!**")

            return await ctx.send(embed=embed)
        else:
            return await ctx.send("⚠️ Таны VIP эрх дууссан байна. `mbuyvip` командаар аваарай!")

    @commands.command(name="viptop")
    async def viptop(self, ctx: commands.Context) -> Optional[discord.Message]:
        """📈 Хамгийн их VIP авсан болон бэлэглэсэн хэрэглэгчдийн жагсаалт"""
        try:
            async with get_async_db_context('economy') as db:
                async with db.execute(
                    "SELECT user_id, vip_count, gifted_vip_count FROM users1 ORDER BY vip_count DESC, gifted_vip_count DESC LIMIT 10"
                ) as cursor:
                    top_vip_users = await cursor.fetchall()

            if not top_vip_users:
                return await ctx.send("⚠️ VIP эрх авсан хэрэглэгч байхгүй байна!")

            embed = discord.Embed(title="💎 VIP Топ жагсаалт", color=discord.Color.gold())
            leaderboard = "🏆 Хамгийн их VIP авсан болон бэлэглэсэн:\n\n"
            leaderboard += "№  Хэрэглэгч            VIP авсан  VIP бэлэглэсэн\n"

            for i, row in enumerate(top_vip_users, start=1):
                user_id = int(row[0])
                vip_count = int(row[1]) if row[1] else 0
                gifted_vip_count = int(row[2]) if row[2] else 0
                
                user = self.bot.get_user(user_id)
                display_name = user.name if user else f"User({user_id})"

                leaderboard += f"#{i} {display_name[:20]:<20} - {vip_count} удаа  {gifted_vip_count} удаа\n"

            embed.description = leaderboard
            return await ctx.send(embed=embed)
        except Exception:
            return await ctx.send("⚠️ Системд алдаа гарлаа!")

    @commands.command(name="buyvip")
    async def buy_vip(self, ctx: commands.Context) -> Optional[discord.Message]:
        """VIP худалдан авах цэс харуулах"""
        embed = discord.Embed(title="💎 VIP ХУДАЛДАН АВАХ", color=discord.Color.gold())
        embed.set_author(name=ctx.author.name)
        avatar_url = self.get_user_avatar_url(ctx.author)
        if avatar_url:
            embed.set_author(name=ctx.author.name, icon_url=avatar_url)
            
        embed.description = "Та авах VIP түвшинг сонгоно уу."

        for level, info in self.vip_levels.items():
            embed.add_field(
                name=f"🎟 {level}", 
                value=f"💰 **{info['price']:,}₮** - {info['days']} хоног", 
                inline=False
            )

        embed.set_footer(text="🎟 **VIP авахын тулд доорх товчийг дарна уу!**")

        view = VIPButtons(self)
        return await ctx.send(embed=embed, view=view)

    @commands.command(name="dailyvip")
    async def daily_vip_bonus(self, ctx: commands.Context) -> Optional[discord.Message]:
        """VIP хэрэглэгчийн өдөр тутмын урамшуулал"""
        data = await self.get_user_data(ctx.author.id)
        if not data or not data[1]:  # vip_level
            return await ctx.send("❌ Та VIP эрхгүй тул энэ командыг ашиглах боломжгүй!")

        # VIP түвшин шалгах
        vip_level = data[1]
        if vip_level not in self.vip_levels:
            return await ctx.send("❌ Танай VIP түвшин хүчингүй байна!")
            
        bonus = self.vip_levels[vip_level].get("bonus", 0)
        today = datetime.now().strftime("%Y-%m-%d")

        try:
            async with get_async_db_context('economy') as db:
                # Өнөөдөр авсан эсэхийг шалгах
                async with db.execute("SELECT last_claimed FROM users1 WHERE user_id=?", (ctx.author.id,)) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0] == today:
                        return await ctx.send("⏳ Та өнөөдөр аль хэдийн урамшууллаа авсан байна!")

                # Урамшуулал олгох
                if not await self.update_balance(ctx.author.id, bonus):
                    return await ctx.send("⚠️ Урамшуулал олгоход алдаа гарлаа!")

                # Авсан өдрийг хадгалах
                await db.execute("UPDATE users1 SET last_claimed = ? WHERE user_id=?", (today, ctx.author.id))
                await db.commit()

            embed = discord.Embed(title="🎁 VIP Өдөр тутмын урамшуулал!", color=discord.Color.gold())
            embed.add_field(name="VIP түвшин", value=vip_level)
            embed.add_field(name="Шагнал", value=f"{bonus:,}₮")
            
            return await ctx.send(embed=embed)
        except Exception:
            return await ctx.send("⚠️ Системд алдаа гарлаа!")

    @commands.command(name="giftvip")
    async def giftvip(self, ctx: commands.Context, user: discord.Member) -> Optional[discord.Message]:
        """💳 Найздаа VIP эрх бэлэглэх"""
        if ctx.author.id == user.id:
            return await ctx.send("⚠️ Та өөртөө VIP эрх бэлэглэж болохгүй!")

        # Бэлэглэгчийн VIP шалгах
        data = await self.get_user_data(ctx.author.id)
        if not data or not data[0]:
            return await ctx.send("⚠️ Та VIP эрхгүй тул бусдад VIP бэлэглэх боломжгүй!")

        embed = discord.Embed(
            title="🎁 VIP эрх бэлэглэх", 
            description=f"💡 {user.mention} -д ямар түвшний VIP эрх бэлэглэх вэ?", 
            color=discord.Color.gold()
        )
        embed.set_footer(text="🎟 Доорх цэсээс сонголтоо хийнэ үү.")

        view = GiftVIPView(ctx, self, user, self.vip_levels)
        return await ctx.send(embed=embed, view=view)

    async def process_vip_purchase(self, interaction: discord.Interaction, user: discord.Member, level: str, is_gift: bool = False, recipient: Optional[discord.Member] = None) -> None:
        """🎟 VIP худалдан авах болон бэлэглэх үйл явц"""
        try:
            # VIP түвшин шалгах
            if level not in self.vip_levels:
                await interaction.followup.send(f"⚠️ **{level}** түвшин байхгүй байна!", ephemeral=True)
                return

            level_info = self.vip_levels[level]
            price = level_info["price"]
            days = level_info["days"]

            # Бэлэглэж байгаа бол хямдрал тооцох
            if is_gift:
                if not recipient:
                    await interaction.followup.send("⚠️ Бэлэг хүлээн авагч сонгогдоогүй байна!", ephemeral=True)
                    return
                    
                discount = level_info.get("gift_discount", 1.0)
                price = int(price * discount)

            # Балансыг шалгах
            balance = await self.get_balance(user.id)
            if balance < price:
                await interaction.followup.send(f"⚠️ VIP авахад танд **{price:,}₮** хэрэгтэй байна! Одоогийн үлдэгдэл: **{balance:,}₮**", ephemeral=True)
                return

            async with get_async_db_context('economy') as db:
                # Мөнгө хасах
                await db.execute(
                    "UPDATE economy SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
                    (price, user.id, price)
                )

                # Хуучин VIP-ийн хугацааг шалгах
                target_user = recipient if is_gift else user
                if not target_user:
                    raise ValueError("Target user is missing")

                async with db.execute(
                    "SELECT vip_expiry, vip_level FROM users1 WHERE user_id=?", 
                    (target_user.id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    current_expiry = None
                    if row and row[0]:
                        try:
                            current_expiry = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            current_expiry = None

                # Шинэ хугацаа тооцох
                now = datetime.now()
                if current_expiry and current_expiry > now:
                    new_expiry = current_expiry + timedelta(days=days)
                else:
                    new_expiry = now + timedelta(days=days)

                # VIP мэдээлэл шинэчлэх
                await db.execute("""
                    INSERT INTO users1 (user_id, vip_expiry, vip_level, vip_count, gifted_vip_count)
                    VALUES (?, ?, ?, COALESCE((SELECT vip_count FROM users1 WHERE user_id=?) + 1, 1), 
                           COALESCE((SELECT gifted_vip_count FROM users1 WHERE user_id=?), 0))
                    ON CONFLICT(user_id) DO UPDATE SET
                        vip_expiry=excluded.vip_expiry,
                        vip_level=excluded.vip_level,
                        vip_count=excluded.vip_count
                """, (target_user.id, new_expiry.strftime("%Y-%m-%d %H:%M:%S"), level, target_user.id, target_user.id))

                if is_gift:
                    # Бэлэглэсэн тоог нэмэх
                    await db.execute("""
                        UPDATE users1 SET gifted_vip_count = COALESCE(gifted_vip_count, 0) + 1 
                        WHERE user_id=?
                    """, (user.id,))

                await db.commit()

            # Амжилттай гүйлгээний мессэж
            if is_gift and recipient:
                embed = discord.Embed(
                    title="🎁 VIP эрх бэлэглэлээ!",
                    description=f"**{user.name}** → **{recipient.name}** руу **{level} VIP** эрхийг **{price:,}₮**-өөр бэлэглэлээ!",
                    color=discord.Color.green()
                )
                embed.add_field(name="📅 VIP дуусах хугацаа", value=new_expiry.strftime("%Y-%m-%d"), inline=False)
                await interaction.followup.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="✅ VIP эрх амжилттай авлаа!",
                    color=discord.Color.green()
                )
                embed.set_author(name=user.name)
                if user.avatar:
                    embed.set_author(name=user.name, icon_url=user.avatar.url)
                embed.add_field(name="📅 VIP дуусах хугацаа", value=new_expiry.strftime("%Y-%m-%d"), inline=False)
                embed.add_field(name="🏆 VIP түвшин", value=level, inline=True)
                embed.add_field(name="💰 Төлсөн дүн", value=f"{price:,}₮", inline=True)
                embed.set_footer(text="🎟 VIP мэдээлэл харах бол mvip командыг ашиглаарай!")
                await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"VIP худалдан авахад алдаа гарлаа: {e}")
            await interaction.followup.send("⚠️ VIP авах үед алдаа гарлаа. Та дахин оролдоно уу!", ephemeral=True)

    @tasks.loop(hours=1)
    async def remove_expired_vip(self) -> None:
        """Хугацаа нь дууссан VIP эрхүүдийг устгах"""
        try:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            async with get_async_db_context('economy') as db:
                await db.execute(
                    "UPDATE users1 SET vip_expiry = NULL, vip_level = NULL WHERE vip_expiry IS NOT NULL AND vip_expiry < ?",
                    (now,)
                )
                await db.commit()
                logger.info("✅ Хугацаа дууссан VIP эрхүүдийг амжилттай устгалаа!")
        except Exception as e:
            logger.error(f"❌ VIP эрхүүдийг устгахад алдаа гарлаа: {str(e)}")

    async def cog_unload(self):
        """When cog is unloaded, cancel the task"""
        if hasattr(self, 'remove_expired_vip'):
            self.remove_expired_vip.cancel()

async def setup(bot: commands.Bot) -> None:
    """🛠 Ботод VIP когийг нэмэх"""
    await bot.add_cog(VIP(bot))
