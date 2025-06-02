import sqlite3
import random
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import matplotlib.pyplot as plt
import os
from datetime import datetime
import pytz

class StockMarket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.setup_database()
        if not self.bot.get_cog("StockMarket"):  # Prevent duplicate tasks
            self.bot.loop.create_task(self.update_stock_prices())
            self.bot.loop.create_task(self.send_stock_update())

    def setup_database(self):
        """Өгөгдлийн сангийн хүснэгтүүдийг үүсгэх."""
        conn = sqlite3.connect("economy.db")
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS global_companies (
                company_name TEXT PRIMARY KEY,
                current_price INTEGER,
                stock INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_history (
                company_name TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                current_price INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_channels (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER
            )
        """)

        conn.commit()
        conn.close()

    async def update_stock_prices(self):
        """Бүх хувьцааны үнийг тодорхой интервалтай шинэчилнэ."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                conn = sqlite3.connect("economy.db")
                cursor = conn.cursor()

                cursor.execute("SELECT company_name, current_price FROM global_companies")
                companies = cursor.fetchall()

                for company_name, current_price in companies:
                    change_percentage = random.uniform(-0.10, 0.10)  # -13% -аас +15% хүртэлх өөрчлөлт
                    new_price = int(max(3000, min(current_price * (1 + change_percentage), 6000)))

                    cursor.execute("""
                        UPDATE global_companies
                        SET current_price = ?
                        WHERE company_name = ?
                    """, (new_price, company_name))

                    cursor.execute("""
                        INSERT INTO stock_history (company_name, current_price)
                        VALUES (?, ?)
                    """, (company_name, new_price))

                conn.commit()
                print("Хувьцааны үнэ шинэчлэгдлээ.")
            except sqlite3.Error as e:
                print(f"Алдаа: {e}")
            finally:
                conn.close()
            await asyncio.sleep(300)

    async def send_stock_update(self):
        """Хувьцааны мэдээллийг график хэлбэрээр илгээнэ."""

        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            try:
                conn = sqlite3.connect("economy.db")
                cursor = conn.cursor()

                # Суваг ID-г өгөгдлийн сангаас авна
                cursor.execute("SELECT guild_id, channel_id FROM stock_channels")
                results = cursor.fetchall()

                for guild_id, channel_id in results:
                    # Discord серверийн гильдийг тодорхойлох
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        print(f"Сервер {guild_id} олдсонгүй.")
                        continue

                    # Суваг ID-г тодорхойлох
                    channel = guild.get_channel(channel_id)
                    if not channel:
                        print(f"Суваг {channel_id} олдсонгүй.")
                        continue

                    cursor.execute("SELECT company_name FROM global_companies")
                    companies = cursor.fetchall()

                    for company_name, in companies:
                        cursor.execute("""
                            SELECT timestamp, current_price
                            FROM stock_history
                            WHERE company_name = ?
                            ORDER BY timestamp DESC LIMIT 10
                        """, (company_name,))
                        stock_data = cursor.fetchall()

                        if not stock_data:
                            continue

                        graph_path = self.generate_stock_graph(stock_data, company_name)
                        print(f"График үүсгэгдсэн: {graph_path}")

                        # График илгээх
                        await channel.send(file=discord.File(graph_path))

                        os.remove(graph_path)
            except Exception as e:
                print(f"Алдаа: {e}")
            finally:
                conn.close()
            await asyncio.sleep(300)

    def validate_and_convert_data(self, raw_data):
        """
        Өгөгдлийг шалгаж, шаардлагатай формат руу хөрвүүлнэ.
        :param raw_data: Зурвас (list) хэлбэртэй өгөгдөл.
        :return: Хувиргасан өгөгдөл [(timestamp, price), ...].
        """
        converted_data = []
        try:
            # Огноо ба үнэ хоёрыг хос хэлбэрт оруулах
            for i in range(0, len(raw_data), 2):
                timestamp_raw = raw_data[i]
                price = raw_data[i + 1]

                # Огноо болон үнийг зөв эсэхийг шалгах
                timestamp = datetime.strptime(timestamp_raw, "%Y-%m-%d %H:%M:%S")
                price = float(price)

                # Хос хэлбэрт оруулах
                converted_data.append((timestamp.strftime("%Y-%m-%d %H:%M:%S"), price))
        except (IndexError, ValueError) as e:
            print(f"Алдаа: Өгөгдөл буруу байна -> {raw_data} ({e})")
        return converted_data

    def generate_stock_graph(self, all_stock_data, company_names):
        """Олон компанийн хувьцааны үнийн шугаман график үүсгэх."""
        import matplotlib.dates as mdates
        mongolia_timezone = pytz.timezone("Asia/Ulaanbaatar")

        plt.figure(figsize=(16, 10))
        ax = plt.gca()

        # Өнгөний тохируулга
        colors = ["blue", "red", "green", "orange", "purple", "cyan", "magenta", "yellow"]

        # Компани тус бүрийн өгөгдлийг графикт нэмэх
        for i, (company_name, raw_data) in enumerate(zip(company_names, all_stock_data)):
            stock_data = self.validate_and_convert_data(raw_data)
            timestamps = []
            prices = []

            # Өгөгдлийг зөв форматтай эсэхийг шалгах
            for timestamp_raw, price in stock_data:
                try:
                    # Огноо-цагийг хөрвүүлэх
                    timestamp = datetime.strptime(timestamp_raw, "%Y-%m-%d %H:%M:%S").astimezone(mongolia_timezone)
                    timestamps.append(timestamp)
                    prices.append(price)
                except ValueError:
                    print(f"Алдаа: Огноо-цагийн формат буруу байна -> {timestamp_raw}")
                    continue

            # Хоосон өгөгдөлтэй компанийг алгасах
            if not timestamps or not prices:
                print(f"Анхааруулга: {company_name} компанийн өгөгдөл байхгүй байна.")
                continue

            # Шугамыг графикт нэмэх (цэгийг шугамаар холбох)
            ax.plot(timestamps, prices, marker="o", linestyle="-", label=company_name, color=colors[i % len(colors)])

            # Шошго нэмэх
            for j, price in enumerate(prices):
                vertical_offset = 50 if j % 2 == 0 else -50  # Цэгүүдийг ээлжлэн дээр/доор байрлуулах
                ax.text(timestamps[j], price + vertical_offset, f"{price} ₮", fontsize=10, ha="center", 
                        color="green" if (j > 0 and price > prices[j - 1]) or j == 0 else "red")

        # Тэнхлэгүүдийн тохиргоо
        ax.set_title("Компаниудын хувьцааны үнэ", fontsize=20, pad=20)
        ax.set_xlabel("Цаг (Монголын цаг)", fontsize=14, labelpad=15)
        ax.set_ylabel("Үнэ (₮)", fontsize=14, labelpad=15)
        ax.grid(True, linestyle="--", alpha=0.6)

        # X-тэнхлэгийн цагийн формат
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        plt.xticks(rotation=45, fontsize=12)
        plt.yticks(fontsize=12)

        # Домог (legend)
        if len(ax.get_legend_handles_labels()[1]) > 0:  # Зөвхөн өгөгдөлтэй шугамыг домогт нэмэх
            plt.legend(loc="upper left", fontsize=12)

        # Зайг зохицуулах
        plt.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.2)

        # График хадгалах
        file_path = "all_companies_stock_graph_line_chart.png"
        plt.savefig(file_path)
        plt.close()

        return file_path

    @app_commands.command(name="company-create", description="Компани үүсгэнэ.")
    @app_commands.describe(company_name="Компаний нэр", initial_stock="Эхний хувьцааны тоо")
    async def create_company(self, interaction: discord.Interaction, company_name: str, initial_stock: int = 1000):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Энэ командыг гүйцэтгэхэд админ эрх шаардлагатай.", ephemeral=True)
            return

        initial_price = random.uniform(3000, 5000)

        conn = sqlite3.connect("economy.db")
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO global_companies (company_name, current_price, stock)
                VALUES (?, ?, ?)
            """, (company_name, initial_price, initial_stock))
            conn.commit()

            await interaction.response.send_message(
                f"✅ Компани үүсгэгдлээ: `{company_name}`\n"
                f"💵 Эхний үнэ: `{initial_price:.2f} ₮`\n"
                f"📦 Нөөц: `{initial_stock}` хувьцаа", ephemeral=True
            )
        except sqlite3.Error as e:
            await interaction.response.send_message(f"❌ Алдаа гарлаа: {e}", ephemeral=True)
        finally:
            conn.close()

    @app_commands.command(name="company-delete", description="Компани устгана.")
    @app_commands.describe(company_name="Компаний нэр")
    async def delete_company(self, interaction: discord.Interaction, company_name: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Энэ командыг гүйцэтгэхэд админ эрх шаардлагатай.", ephemeral=True)
            return

        conn = sqlite3.connect("economy.db")
        cursor = conn.cursor()

        try:
            cursor.execute("""
                DELETE FROM global_companies WHERE company_name = ?
            """, (company_name,))
            conn.commit()

            cursor.execute("SELECT * FROM global_companies WHERE company_name = ?", (company_name,))
            company = cursor.fetchone()

            if company:
                await interaction.response.send_message(f"❌ `{company_name}` компани устгагдаагүй.", ephemeral=True)
            else:
                await interaction.response.send_message(f"✅ `{company_name}` компани амжилттай устгагдлаа.", ephemeral=True)
        except sqlite3.Error as e:
            await interaction.response.send_message(f"❌ Алдаа гарлаа: {e}", ephemeral=True)
        finally:
            conn.close()

    @app_commands.command(name="shop", description="Бүх серверийн хувьцааг харуулна.")
    async def shop(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)  # Interaction-г deferred болгоно

        conn = sqlite3.connect("economy.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT company_name, current_price, stock
            FROM global_companies
        """)
        companies = cursor.fetchall()
        conn.close()

        if not companies:
            await interaction.followup.send("Ямар ч хувьцаа байхгүй байна.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🛒 Дэлгүүр",
            description="Бүх серверүүдийн хувьцаануудын мэдээлэл",
            color=discord.Color.green()
        )

        for company_name, current_price, stock in companies:
            embed.add_field(
                name=f"📈 {company_name}",
                value=f"Үнэ: {current_price:.2f} ₮\nҮлдэгдэл: {stock} хувьцаа",
                inline=False
            )

        await interaction.followup.send(embed=embed)  # Deferred interaction дээр followup ашиглана

    @app_commands.command(name="setstock", description="График илгээх сувгийг тохируулна (зөвхөн админ).")
    @app_commands.describe(channel="График илгээх суваг")
    async def set_graph_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Энэ командыг гүйцэтгэхэд админ эрх шаардлагатай.", ephemeral=True)
            return

        conn = sqlite3.connect("economy.db")
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO stock_channels (guild_id, channel_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id)
                DO UPDATE SET channel_id = excluded.channel_id
            """, (interaction.guild.id, channel.id))
            conn.commit()

            await interaction.response.send_message(f"✅ График илгээх суваг: {channel.mention} болгож тохирууллаа.", ephemeral=True)
        except sqlite3.Error as e:
            await interaction.response.send_message(f"❌ Алдаа гарлаа: {e}", ephemeral=True)
        finally:
            conn.close()

    # Дэлгүүр харуулах
    @app_commands.command(name="shop-buy", description="Хувьцаа худалдаж авна.")
    @app_commands.describe(company_name="Хувьцааны нэр", amount="Худалдаж авах хувьцааны тоо")
    async def shop_buy(self, interaction: discord.Interaction, company_name: str, amount: int):
        await interaction.response.defer(ephemeral=True)  # Defer the response to extend thinking time

        if amount <= 0:
            await interaction.followup.send("❌ Хувьцааны тоо 0 эсвэл сөрөг байж болохгүй. Зөв тоо оруулна уу!", ephemeral=True)
            return

        user_id = interaction.user.id
        guild_id = interaction.guild.id

        conn = sqlite3.connect("economy.db")
        cursor = conn.cursor()

        try:
            # Компани шалгах
            cursor.execute("""
                SELECT current_price, stock
                FROM global_companies
                WHERE company_name = ?
            """, (company_name,))
            company = cursor.fetchone()

            if not company:
                await interaction.followup.send(f"❌ `{company_name}` нэртэй компани олдсонгүй. Зөв нэр оруулна уу!", ephemeral=True)
                return

            current_price, stock = company

            if amount > stock:
                await interaction.followup.send(f"❌ Үлдэгдэл хүрэлцэхгүй байна. Үлдэгдэл: `{stock}` хувьцаа.", ephemeral=True)
                return

            # Хэрэглэгчийн баланс шалгах
            cursor.execute("""
                SELECT balance
                FROM economy
                WHERE user_id = ?
            """, (user_id,))
            user = cursor.fetchone()

            if not user:
                cursor.execute("""
                    INSERT INTO economy (user_id, balance)
                    VALUES (?, 10000)
                """, (user_id,))
                conn.commit()
                balance = 10000
            else:
                balance = user[0]

            total_cost = current_price * amount

            if balance < total_cost:
                await interaction.followup.send(
                    f"❌ Баланс хүрэлцэхгүй байна! Таны баланс: `{balance:.2f} ₮`, нийт дүн: `{total_cost:.2f} ₮`.",
                    ephemeral=True
                )
                return

            # Хувьцаа худалдан авах
            new_balance = balance - total_cost
            new_stock = stock - amount

            cursor.execute("""
                UPDATE economy SET balance = ? WHERE user_id = ?
            """, (new_balance, user_id))

            cursor.execute("""
                UPDATE global_companies SET stock = ? WHERE company_name = ?
            """, (new_stock, company_name))

            cursor.execute("""
                INSERT INTO user_stocks (user_id, guild_id, company_name, shares)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, guild_id, company_name)
                DO UPDATE SET shares = shares + excluded.shares
            """, (user_id, guild_id, company_name, amount))
            conn.commit()

            await interaction.followup.send(
                f"✅ Та `{amount}` хувьцааг `{company_name}` компанид амжилттай худалдаж авлаа!", ephemeral=True
            )
        except sqlite3.Error as e:
            await interaction.followup.send(f"❌ Алдаа гарлаа: {e}", ephemeral=True)
        finally:
            conn.close()

    # Хувьцаа зарах
    @app_commands.command(name="shop-sell", description="Хувьцаа зарна.")
    @app_commands.describe(company_name="Хувьцааны нэр", amount="Зарах хувьцааны тоо")
    async def shop_sell(self, interaction: discord.Interaction, company_name: str, amount: int):
        await interaction.response.defer(ephemeral=True)

        if amount <= 0:
            await interaction.followup.send("❌ Хувьцааны тоо 0 эсвэл сөрөг байж болохгүй. Зөв тоо оруулна уу!", ephemeral=True)
            return

        user_id = interaction.user.id
        guild_id = interaction.guild.id

        conn = sqlite3.connect("economy.db")
        cursor = conn.cursor()

        try:
            # Хэрэглэгчийн хувьцааны үлдэгдэл шалгах
            cursor.execute("""
                SELECT shares
                FROM user_stocks
                WHERE user_id = ? AND guild_id = ? AND company_name = ?
            """, (user_id, guild_id, company_name))
            user_stock = cursor.fetchone()

            if not user_stock or user_stock[0] < amount:
                await interaction.followup.send(
                    f"❌ Танд хангалттай хувьцаа байхгүй байна! Эзэмшсэн хувьцаа: `{user_stock[0] if user_stock else 0}`.",
                    ephemeral=True
                )
                return

            # Компани шалгах
            cursor.execute("""
                SELECT current_price
                FROM global_companies
                WHERE company_name = ?
            """, (company_name,))
            company = cursor.fetchone()

            if not company:
                await interaction.followup.send(f"❌ `{company_name}` нэртэй компани олдсонгүй. Зөв нэр оруулна уу!", ephemeral=True)
                return

            current_price = company[0]
            total_earnings = current_price * amount

            new_shares = user_stock[0] - amount
            cursor.execute("""
                UPDATE user_stocks SET shares = ? WHERE user_id = ? AND guild_id = ? AND company_name = ?
            """, (new_shares, user_id, guild_id, company_name))

            cursor.execute("""
                UPDATE economy SET balance = balance + ? WHERE user_id = ?
            """, (total_earnings, user_id))
            conn.commit()

            await interaction.followup.send(
                f"✅ Та `{amount}` хувьцааг `{company_name}` компанид амжилттай зарлаа! Орлого: `{total_earnings:.2f} ₮`.",
                ephemeral=True
            )
        except sqlite3.Error as e:
            await interaction.followup.send(f"❌ Алдаа гарлаа: {e}", ephemeral=True)
        finally:
            conn.close()

# Add cog to bot
async def setup(bot):
    await bot.add_cog(StockMarket(bot))