from cogs.utils.shop_utils import (
    get_active_effects,
    is_rob_protected,
    get_auto_money,
    has_auto_claim_daily,
    get_shop_discount,
    get_effects_summary
)
import discord
from discord.ext import commands
from typing import Optional, Dict, Any
import json
import os
import logging
from datetime import datetime, timedelta
from ..utils.database import get_async_connection
from ..utils.channel import is_channel_enabled
import aiosqlite

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Shop(commands.Cog):
    from discord.ext import tasks

    def __init__(self, bot: commands.Bot) -> None:
        """Shop когийг эхлүүлэх"""
        self.bot = bot
        self.conn: Optional[aiosqlite.Connection] = None
        self.shop_data: Dict[str, Any] = {}
        self.item_id_mapping: Dict[int, str] = {}  # numeric_id -> text_id
        self.reverse_id_mapping: Dict[str, int] = {}  # text_id -> numeric_id
        self.bot.loop.create_task(self.setup_database())
        self.load_shop_data()
        self.auto_money_task.start()
        
    def load_shop_data(self) -> None:
        """Shop өгөгдлийг JSON файлаас ачаалах"""
        try:
            json_path = os.path.join(os.path.dirname(__file__), 'shop_items.json')
            with open(json_path, 'r', encoding='utf-8') as file:
                self.shop_data = json.load(file)
            
            # Create numeric ID mappings
            self.create_id_mappings()
            logger.info("✅ Shop өгөгдөл амжилттай ачаалагдлаа")
        except FileNotFoundError:
            logger.error("❌ shop_items.json файл олдсонгүй")
            self.shop_data = {"categories": {}, "items": {}, "limited_items": {}}
        except json.JSONDecodeError:
            logger.error("❌ shop_items.json файлын формат буруу")
            self.shop_data = {"categories": {}, "items": {}, "limited_items": {}}

    async def setup_database(self) -> None:
        """Database тохиргоо"""
        self.conn = await get_async_connection('economy')
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS shop_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_id TEXT NOT NULL,
                purchase_date TEXT NOT NULL,
                expiry_date TEXT,
                active BOOLEAN DEFAULT 1,
                quantity INTEGER DEFAULT 1
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_inventory (
                user_id INTEGER NOT NULL,
                item_id TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                expiry_date TEXT,
                effects TEXT,
                last_auto_money_claim TEXT,
                PRIMARY KEY (user_id, item_id)
            )
        """)
        # Add last_auto_money_claim column if missing
        # Correctly check for column existence
        async with self.conn.execute("PRAGMA table_info(user_inventory)") as cursor:
            info = await cursor.fetchall()
        columns = [row[1] for row in info]
        if "last_auto_money_claim" not in columns:
            await self.conn.execute("ALTER TABLE user_inventory ADD COLUMN last_auto_money_claim TEXT")
        await self.conn.commit()

    async def ensure_connection(self) -> None:
        if self.conn is None:
            await self.setup_database()
        if self.conn is None:
            raise RuntimeError("Database connection is not established!")

    async def get_user_balance(self, user_id: int) -> int:
        """Хэрэглэгчийн мөнгөний үлдэгдлийг авах"""
        await self.ensure_connection()
        if self.conn is None:
            raise RuntimeError("Database connection is not established!")
        async with self.conn.execute("SELECT balance FROM economy WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0

    async def update_user_balance(self, user_id: int, amount: int) -> bool:
        """Хэрэглэгчийн мөнгийг шинэчлэх"""
        await self.ensure_connection()
        if self.conn is None:
            raise RuntimeError("Database connection is not established!")
        
        current_balance = await self.get_user_balance(user_id)
        if current_balance + amount < 0:
            return False
            
        await self.conn.execute("""
            INSERT INTO economy (user_id, balance)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?
        """, (user_id, current_balance + amount, amount))
        await self.conn.commit()
        return True

    def create_shop_embed(self, category: str = "all") -> discord.Embed:
        """Shop-ийн embed үүсгэх"""
        if category == "all":
            embed = discord.Embed(
                title="🛍️ MongolBot Дэлгүүр",
                description="Төрөл бүрийн зүйлс худалдан авч, ботын функцуудыг сайжруулаарай!\n\n💡 **Худалдан авах:** `!buy <numeric_id> [тоо_хэмжээ]`\n📋 **Жишээ:** `!buy 1 1`",
                color=0x00ff00
            )
            # Категориудыг харуулах
            for cat_id, cat_info in self.shop_data.get("categories", {}).items():
                item_count = len([item for item in self.shop_data.get("items", {}).values() 
                                if item.get("category") == cat_id])
                embed.add_field(
                    name=f"{cat_info['emoji']} {cat_info['name']}",
                    value=f"{cat_info['description']}\n`{item_count} зүйл`",
                    inline=True
                )
        else:
            # Тухайн категорийн зүйлсийг харуулах
            cat_info = self.shop_data.get("categories", {}).get(category, {})
            embed = discord.Embed(
                title=f"{cat_info.get('emoji', '🛍️')} {cat_info.get('name', 'Дэлгүүр')}",
                description=cat_info.get('description', 'Зүйлсийн жагсаалт'),
                color=0x00ff00
            )
            
            items = {k: v for k, v in self.shop_data.get("items", {}).items() 
                    if v.get("category") == category and v.get("purchasable", True)}
            
            for item_id, item in items.items():
                numeric_id = self.get_numeric_id_from_text(item_id)
                price_text = f"{item['price']:,}₮"
                if item.get("stock", -1) != -1:
                    price_text += f" (Үлдэгдэл: {item['stock']})"
                
                embed.add_field(
                    name=f"{item['emoji']} {item['name']}",
                    value=f"{item['description']}\n**{price_text}**\n`ID: {numeric_id}`",
                    inline=False
                )
            
            # Footer нэмэх
            embed.set_footer(text="💡 Худалдан авах: mbuy <numeric_id> [тоо_хэмжээ] • Жишээ: mbuy 1 1")
        
        return embed

    @commands.command(name='shop!!!!!')
    async def shop(self, ctx: commands.Context, category: str = "all") -> None:
        """Дэлгүүрийг харах"""
        if not await is_channel_enabled(ctx.guild.id if ctx.guild else 0, ctx.channel.id):
            await ctx.send("Энэ channel-д команд ашиглах боломжгүй!")
            return
            
        try:
            embed = self.create_shop_embed(category)
            view = ShopView(self, category)
            await ctx.send(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Shop командад алдаа: {e}")
            await ctx.send("⚠️ Дэлгүүрийг ачаалахад алдаа гарлаа!")

    @commands.command(name='buy!!!!!')
    async def buy_item(self, ctx: commands.Context, item_id: str, quantity: int = 1) -> None:
        """Зүйл худалдан авах"""
        if not await is_channel_enabled(ctx.guild.id if ctx.guild else 0, ctx.channel.id):
            await ctx.send("Энэ channel-д команд ашиглах боломжгүй!")
            return
            
        try:
            # Зүйл байгаа эсэхийг шалгах (numeric эсвэл text ID хүлээн авна)
            item = self.get_item_by_id(item_id)
            original_item_id = item_id
            
            # Numeric ID бол text ID руу хөрвүүлэх
            if item_id.isdigit():
                text_id = self.get_text_id_from_numeric(int(item_id))
                if text_id:
                    item_id = text_id
            
            if not item or not item.get("purchasable", True):
                embed = discord.Embed(
                    title="❌ Зүйл олдсонгүй!",
                    description=f"**`{original_item_id}`** зүйл олдсонгүй эсвэл худалдан авах боломжгүй!",
                    color=0xff0000
                )
                embed.add_field(
                    name="💡 Зөвлөгөө",
                    value="• `mshop` командаар бүх зүйлсийг харна уу\n• Зүйлийн ID-г зөв бичсэн эсэхийг шалгана уу\n• Жишээ: `mbuy 1 1` (1-р зүйлээс 1 ширхэг авах)",
                    inline=False
                )
                await ctx.send(embed=embed)
                return
                
            # Хэрэглэгчийн VIP/Boost статусыг шалгах
            member = ctx.author
            is_vip = any(role.name.lower() == "vip" for role in getattr(member, "roles", []))
            # Boost хийсэн эсэхийг premium_since property болон role name хоёуланг шалгана
            is_boosted = (getattr(member, "premium_since", None) is not None) or any("boost" in role.name.lower() for role in getattr(member, "roles", []))
            category = item.get("category", "")
            if category == "premium" and not is_vip:
                await ctx.send("⛔ Энэ зүйл зөвхөн VIP эрхтэй хэрэглэгчдэд!")
                return
            if category == "boosters" and not is_boosted:
                await ctx.send("⛔ Энэ зүйл зөвхөн сервер boost хийсэн хэрэглэгчдэд!")
                return
            # 'tools' category restriction removed: now all users can buy

            # Shop discount effect-ийг shop_utils-аас авна
            await self.ensure_connection()
            if self.conn is None:
                await ctx.send("❌ Database холболтод алдаа!")
                return
            discount = await get_shop_discount(self.conn, ctx.author.id)
            logger.info(f"Shop discount for user {ctx.author.id}: {discount}")  # Debug log
            total_price = int(item["price"] * (1 - discount) * quantity)

            # Балансыг шалгах
            user_balance = await self.get_user_balance(ctx.author.id)
            if user_balance < total_price:
                await ctx.send(f"💸 Таны мөнгө хүрэлцэхгүй! Хэрэгтэй: **{total_price:,}₮**, Танд: **{user_balance:,}₮**")
                return
    # Эдгээр utility-уудыг shop_utils.py-аас шууд ашиглана

            # Үлдэгдэл шалгах
            stock = item.get("stock", -1)
            if stock != -1 and stock < quantity:
                await ctx.send(f"📦 Хангалттай үлдэгдэл байхгүй! Үлдэгдэл: {stock}, Хүссэн: {quantity}")
                return

            # Худалдан авах
            success = await self.purchase_item(ctx.author.id, item_id, item, quantity)
            if success:
                # Мөнгө хасах
                await self.update_user_balance(ctx.author.id, -total_price)

                # Үлдэгдэл шинэчлэх
                if stock != -1:
                    # JSON файлыг шинэчлэх логик энд байх ёстой
                    pass

                embed = discord.Embed(
                    title="✅ Амжилттай худалдан авлаа!",
                    description=f"**{item['emoji']} {item['name']}** x{quantity}",
                    color=0x00ff00
                )

                # Numeric ID харуулах
                display_id = original_item_id if original_item_id.isdigit() else self.get_numeric_id_from_text(item_id)
                embed.add_field(name="🆔 Зүйлийн ID", value=f"`{display_id}`", inline=True)
                embed.add_field(name="💰 Төлсөн дүн", value=f"{total_price:,}₮", inline=True)
                embed.add_field(name="💎 Үлдэгдэл", value=f"{user_balance - total_price:,}₮", inline=True)

                # Add usage info if available
                if "effects" in item:
                    effects_text = ""
                    effects = item["effects"]
                    if "duration_days" in effects:
                        effects_text += f"⏰ {effects['duration_days']} хоног хугацаатай\n"
                    if "description" in effects:
                        effects_text += f"📝 {effects['description']}"
                    
                    if effects_text:
                        embed.add_field(name="ℹ️ Нэмэлт мэдээлэл", value=effects_text, inline=False)
                
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Худалдан авахад алдаа гарлаа!")
                
        except Exception as e:
            logger.error(f"Buy командад алдаа: {e}")
            await ctx.send("⚠️ Худалдан авахад алдаа гарлаа!")

    async def purchase_item(self, user_id: int, item_id: str, item: Dict[str, Any], quantity: int) -> bool:
        """
        Зүйл худалдан авах процесс.
        - Хугацаа шалгах
        - Inventory шинэчлэх
        - Худалдан авалт хадгалах
        - Эффект merge хийх
        - Санхүүгийн төлбөр автоматаар хасах
        - Хэрэглэгчид DM мэдэгдэл илгээх
        """
        try:
            await self.ensure_connection()
            if self.conn is None:
                return False

            # ✅ Эхлээд хэрэглэгчийн мөнгө шалгах
            total_price = item["price"] * quantity
            async with self.conn.execute("SELECT balance FROM economy WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
            if not row or row[0] < total_price:
                return False  # Мөнгөгүй бол худалдаа хийгдэхгүй

            # ✅ Хугацаа шалгах
            purchase_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            expiry_date = None
            if "duration_days" in item.get("effects", {}):
                expiry = datetime.now() + timedelta(days=item["effects"]["duration_days"])
                expiry_date = expiry.strftime("%Y-%m-%d %H:%M:%S")

            # ✅ Effects json болгож хөрвүүлэх
            effects_json = json.dumps(item.get("effects", {}))

            # ✅ Inventory дотор өмнө нь байгаа эсэхийг шалгах ба merge хийх
            async with self.conn.execute("SELECT effects FROM user_inventory WHERE user_id=? AND item_id=?", (user_id, item_id)) as cursor:
                row = await cursor.fetchone()
            if row and row[0]:
                try:
                    existing_effects = json.loads(row[0])
                    new_effects = item.get("effects", {})
                    merged_effects = {**existing_effects, **new_effects}
                    effects_json = json.dumps(merged_effects)
                except Exception:
                    pass  # Merge хийхэд алдаа гарвал одоогийн effects-ээр хадгална

            # ✅ Худалдан авалтыг shop_purchases-д бүртгэх
            await self.conn.execute("""
                INSERT INTO shop_purchases (user_id, item_id, purchase_date, expiry_date, quantity)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, item_id, purchase_date, expiry_date, quantity))

            # ✅ Inventory-г шинэчлэх
            await self.conn.execute("""
                INSERT INTO user_inventory (user_id, item_id, quantity, expiry_date, effects)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, item_id) DO UPDATE SET 
                quantity = quantity + ?, expiry_date = ?, effects = ?
            """, (user_id, item_id, quantity, expiry_date, effects_json, quantity, expiry_date, effects_json))

            # ✅ Мөнгийг хасах
            await self.conn.execute("UPDATE economy SET balance = balance - ? WHERE user_id = ?", (total_price, user_id))

            await self.conn.commit()

            # ✅ Хэрэглэгчид мэдэгдэл илгээх
            user = self.bot.get_user(user_id)
            if user is None:
                try:
                    user = await self.bot.fetch_user(user_id)
                except Exception as fetch_err:
                    print(f"[❌] Fetch user алдаа: {fetch_err}")
                    user = None

            if user:
                try:
                    await user.send(
                        f"🎉 Та {quantity} ширхэг `{item['name']}` амжилттай худалдан авлаа!\n💸 Төлсөн: ₮{total_price:,}"
                    )
                except Exception as dm_error:
                    print(f"[⚠️] DM илгээхэд алдаа гарлаа: {type(dm_error).__name__} - {dm_error}")
        except Exception as e:
            # Handle any exception that occurs in the purchase_item method
            print(f"[❌] purchase_item error: {e}")
            return False
        return True

    @commands.command(name='inventory!!!!!', aliases=['inv!!!!!'])
    async def inventory(self, ctx: commands.Context) -> None:
        """Хэрэглэгчийн inventory харах"""
        if not await is_channel_enabled(ctx.guild.id if ctx.guild else 0, ctx.channel.id):
            await ctx.send("Энэ channel-д команд ашиглах боломжгүй!")
            return
            
        try:
            await self.ensure_connection()
            if self.conn is None:
                await ctx.send("❌ Database холболтод алдаа!")
                return
                
            async with self.conn.execute("""
                SELECT item_id, quantity, expiry_date, effects 
                FROM user_inventory 
                WHERE user_id = ? AND quantity > 0
            """, (ctx.author.id,)) as cursor:
                items = await cursor.fetchall()
            
            if not items:
                await ctx.send("📦 Таны inventory хоосон байна!")
                return
                
            embed = discord.Embed(
                title=f"📦 {ctx.author.display_name}-ийн Inventory",
                color=0x3498db
            )
            
            for item_id, quantity, expiry_date, effects_json in items:
                item_info = self.shop_data.get("items", {}).get(item_id, {})
                if not item_info:
                    item_info = self.shop_data.get("limited_items", {}).get(item_id, {})
                
                item_name = item_info.get("name", item_id)
                item_emoji = item_info.get("emoji", "📦")
                
                value = f"Тоо хэмжээ: {quantity}"
                if expiry_date:
                    try:
                        expiry = datetime.strptime(expiry_date, "%Y-%m-%d %H:%M:%S")
                        if expiry > datetime.now():
                            days_left = (expiry - datetime.now()).days
                            value += f"\n⏰ {days_left} хоног үлдсэн"
                        else:
                            value += "\n❌ Хугацаа дууссан"
                    except Exception:
                        value += "\n❌ Хугацаа дууссан"
                else:
                    value += "\n♾️ Хугацаагүй"
                
                embed.add_field(
                    name=f"{item_emoji} {item_name}",
                    value=value,
                    inline=True
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Inventory командад алдаа: {e}")
            await ctx.send("⚠️ Inventory ачаалахад алдаа гарлаа!")

    @commands.command(name='testeffects')
    async def test_effects(self, ctx: commands.Context) -> None:
        """Таны бүх effect utility-уудыг тестлэх"""
        await self.ensure_connection()
        if self.conn is None:
            await ctx.send("❌ Database холболтод алдаа!")
            return
        user_id = ctx.author.id
        try:
            effects = await get_active_effects(self.conn, user_id)
            rob_protected = await is_rob_protected(self.conn, user_id)
            auto_money = await get_auto_money(self.conn, user_id)
            auto_claim_daily = await has_auto_claim_daily(self.conn, user_id)
            shop_discount = await get_shop_discount(self.conn, user_id)
            effects_summary = await get_effects_summary(self.conn, user_id)

            # Detailed effect summary
            embed = discord.Embed(
                title=f"🧪 {ctx.author.display_name}-ийн идэвхтэй эффектүүд",
                color=0x2ecc71
            )
            # Show each effect in a readable way
            if effects:
                for k, v in effects.items():
                    effect_lines = [f"**{k}**: {v}"]
                    embed.add_field(
                        name=f"✨ {k}",
                        value="\n".join(effect_lines),
                        inline=False
                    )
            else:
                embed.description = "Идэвхтэй эффект байхгүй байна."

            # Add utility results
            embed.add_field(name="🛡️ Rob Protected", value=str(rob_protected), inline=True)
            embed.add_field(name="💸 Auto Money", value=str(auto_money), inline=True)
            embed.add_field(name="🎁 Auto Claim Daily", value=str(auto_claim_daily), inline=True)
            embed.add_field(name="🏷️ Shop Discount", value=f"{shop_discount*100:.1f}%", inline=True)
            embed.add_field(name="📋 Summary", value=str(effects_summary), inline=False)

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Effect test command error: {e}")
            await ctx.send(f"⚠️ Effect тест хийхэд алдаа гарлаа! {e}")

    def create_id_mappings(self) -> None:
        """Numeric ID болон text ID хоорондын mapping үүсгэх"""
        self.item_id_mapping.clear()
        self.reverse_id_mapping.clear()
        
        numeric_id = 1
        
        # Regular items
        for text_id in self.shop_data.get("items", {}):
            self.item_id_mapping[numeric_id] = text_id
            self.reverse_id_mapping[text_id] = numeric_id
            numeric_id += 1
        
        # Limited items  
        for text_id in self.shop_data.get("limited_items", {}):
            self.item_id_mapping[numeric_id] = text_id
            self.reverse_id_mapping[text_id] = numeric_id
            numeric_id += 1

    def get_item_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        """ID-аар зүйл хайх (numeric эсвэл text ID хүлээн авна)"""
        # Numeric ID эсэхийг шалгах
        if item_id.isdigit():
            numeric_id = int(item_id)
            text_id = self.item_id_mapping.get(numeric_id)
            if text_id:
                item_id = text_id
            else:
                return None
        
        # Text ID ашиглан зүйл хайх
        item = self.shop_data.get("items", {}).get(item_id)
        if not item:
            item = self.shop_data.get("limited_items", {}).get(item_id)
        
        return item

    def get_text_id_from_numeric(self, numeric_id: int) -> Optional[str]:
        """Numeric ID-аас text ID авах"""
        return self.item_id_mapping.get(numeric_id)

    def get_numeric_id_from_text(self, text_id: str) -> Optional[int]:
        """Text ID-аас numeric ID авах"""
        return self.reverse_id_mapping.get(text_id)

    def cog_check(self, ctx: commands.Context) -> bool:
        if not ctx.guild:
            return False
        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        if not ctx.guild or not await is_channel_enabled(ctx.guild.id, ctx.channel.id):
            await ctx.send("Энэ channel-д команд ашиглах боломжгүй!")
            raise commands.CheckFailure("Channel not enabled for commands.")
        
    @tasks.loop(minutes=1)
    async def auto_money_task(self):
        await self.ensure_connection()
        if self.conn is None:
            logger.error("auto_money_task: Database connection is not established!")
            return
        # Get all user_inventory rows with auto_money effect
        async with self.conn.execute("SELECT user_id, item_id, effects, last_auto_money_claim FROM user_inventory WHERE quantity > 0") as cursor:
            rows = await cursor.fetchall()
        now = datetime.now()
        for user_id, item_id, effects_json, last_claim in rows:
            try:
                effects = json.loads(effects_json) if effects_json else {}
                if "auto_money" in effects:
                    amount = int(effects["auto_money"])
                    # Use default interval 60 minutes if missing or invalid
                    try:
                        interval = int(effects.get("interval_minutes", 2))
                        if interval <= 0:
                            interval = 2
                    except Exception:
                        interval = 2
                    # Check expiry
                    async with self.conn.execute("SELECT expiry_date FROM user_inventory WHERE user_id=? AND item_id=?", (user_id, item_id)) as c:
                        expiry_row = await c.fetchone()
                    expiry_date = None
                    if expiry_row and expiry_row[0]:
                        try:
                            expiry_date = datetime.strptime(expiry_row[0], "%Y-%m-%d %H:%M:%S")
                        except Exception:
                            expiry_date = None
                    if expiry_date and expiry_date < now:
                        continue  # expired
                    # Check last claim
                    if last_claim:
                        try:
                            last_claim_dt = datetime.strptime(last_claim, "%Y-%m-%d %H:%M:%S")
                        except Exception:
                            last_claim_dt = None
                    else:
                        last_claim_dt = None
                    should_give = False
                    delta = None
                    if not last_claim_dt:
                        should_give = True
                    else:
                        delta = now - last_claim_dt
                        if interval > 0 and delta.total_seconds() >= interval * 60:
                            should_give = True
                    if should_give:
                        # Give money to main balance (economy table)
                        old_balance = await self.get_user_balance(user_id)
                        await self.update_user_balance(user_id, amount)
                        new_balance = await self.get_user_balance(user_id)
                        # Update last_auto_money_claim
                        if self.conn is not None:
                            await self.conn.execute("UPDATE user_inventory SET last_auto_money_claim=? WHERE user_id=? AND item_id=?", (now.strftime("%Y-%m-%d %H:%M:%S"), user_id, item_id))
                            await self.conn.commit()
                        # Send DM notification
                        try:
                            user = self.bot.get_user(user_id)
                            msg = (
                                f"💸 Автомат орлого идэвхжлээ!\n"
                                f"Таны өмнөх баланс: {old_balance:,}₮\n"
                                f"Нэмэгдсэн: {amount:,}₮\n"
                                f"Шинэ баланс: {new_balance:,}₮"
                            )
                            sent = False
                            if user:
                                try:
                                    await user.send(msg)
                                    sent = True
                                except Exception:
                                    pass
                            if not sent:
                                try:
                                    user = await self.bot.fetch_user(user_id)
                                    await user.send(msg)
                                    sent = True
                                except Exception:
                                    pass
                            if not sent:
                                logger.error(f"Failed to send DM to user {user_id}: DM blocked or other error.")
                        except Exception as dm_err:
                            logger.error(f"Failed to send DM to user {user_id}: {dm_err}")
            except Exception as e:
                logger.error(f"auto_money_task error for user {user_id}: {e}")

    async def cog_unload(self):
        self.auto_money_task.cancel()

class ShopView(discord.ui.View):
    def __init__(self, shop_cog: Shop, current_category: str = "all"):
        super().__init__(timeout=300)
        self.shop_cog = shop_cog
        self.current_category = current_category
        
        # Category selector нэмэх
        self.add_item(CategorySelector(shop_cog, current_category))
        
        # Refresh button
        refresh_btn = discord.ui.Button(label="🔄 Шинэчлэх", style=discord.ButtonStyle.secondary)
        refresh_btn.callback = self.refresh_callback
        self.add_item(refresh_btn)

    async def refresh_callback(self, interaction: discord.Interaction) -> None:
        """Shop мэдээллийг шинэчлэх"""
        self.shop_cog.load_shop_data()  # This will also refresh ID mappings
        embed = self.shop_cog.create_shop_embed(self.current_category)
        await interaction.response.edit_message(embed=embed, view=self)


class CategorySelector(discord.ui.Select):
    def __init__(self, shop_cog: Shop, current_category: str):
        self.shop_cog = shop_cog
        
        options = [
            discord.SelectOption(
                label="Бүх зүйл",
                value="all",
                emoji="🛍️",
                default=(current_category == "all")
            )
        ]
        
        for cat_id, cat_info in shop_cog.shop_data.get("categories", {}).items():
            options.append(discord.SelectOption(
                label=cat_info["name"],
                value=cat_id,
                emoji=cat_info["emoji"],
                description=cat_info["description"][:50],
                default=(current_category == cat_id)
            ))
        
        super().__init__(placeholder="Категори сонгох...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        selected_category = self.values[0]
        embed = self.shop_cog.create_shop_embed(selected_category)
        
        # View шинэчлэх
        new_view = ShopView(self.shop_cog, selected_category)
        await interaction.response.edit_message(embed=embed, view=new_view)

def setup(bot: commands.Bot):
    return bot.add_cog(Shop(bot))

# NOTE: If shop_discount is still not working, check cogs/utils/shop_utils.py's get_shop_discount function.
# Make sure it only considers active, unexpired items with shop_discount effect.
