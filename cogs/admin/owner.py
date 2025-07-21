import discord
from discord.ext import commands
import aiosqlite
import asyncio
import os

class Owner(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.synced = False  # Синхрончлолын төлөв

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.synced:
            try:
                synced = await self.bot.tree.sync()
                self.synced = True
                print(f"✅ `{len(synced)}` команд глобал хэмжээнд амжилттай синхрончлогдлоо.")
            except Exception as e:
                print(f"❌ Slash командуудыг синхрончлох үед алдаа гарлаа: {e}")

    @commands.command(name="sync", help="Глобал slash командуудыг синхрончлох.")
    @commands.is_owner()
    async def sync(self, ctx: commands.Context):
        try:
            synced = await self.bot.tree.sync()
            await ctx.send(f"✅ `{len(synced)}` команд глобал хэмжээнд амжилттай синхрончлогдлоо.")
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: {e}")

    @commands.command(name="sync_guild", help="Зөвхөн энэ серверт slash командуудыг синхрончлох.")
    @commands.is_owner()
    async def sync_guild(self, ctx: commands.Context):
        try:
            synced = await self.bot.tree.sync(guild=ctx.guild)
            await ctx.send(f"✅ `{len(synced)}` команд зөвхөн энэ серверт амжилттай синхрончлогдлоо.")
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: {e}")

    @commands.command(name="sync_server", help="Тодорхой серверт slash командуудыг синхрончлох.")
    @commands.is_owner()
    async def sync_server(self, ctx: commands.Context, guild_id: int):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            await ctx.send("❌ Уг сервер олдсонгүй.")
            return
        try:
            synced = await self.bot.tree.sync(guild=guild)
            await ctx.send(f"✅ `{len(synced)}` команд сервер `{guild_id}`-д амжилттай синхрончлогдлоо.")
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: {e}")

    @commands.command(name='load', help='Шинэ нэмэлт (cog) ачаалах.')
    @commands.is_owner()
    async def load(self, ctx: commands.Context, cog: str):
        try:
            await self.bot.load_extension(f"{cog}")
            await ctx.send(f"✅ `{cog}` амжилттай ачаалагдлаа!")
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: `{e}`")

    @commands.command(name='unload', help='Нэмэлтийг (cog) ачаалалгүй болгох.')
    @commands.is_owner()
    async def unload(self, ctx: commands.Context, cog: str):
        try:
            await self.bot.unload_extension(f"{cog}")
            await ctx.send(f"✅ `{cog}` амжилттай ачаалалгүй боллоо!")
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: `{e}`")

    @commands.command(name='reload', help='Нэмэлтийг (cog) дахин ачаалах.')
    @commands.is_owner()
    async def reload(self, ctx: commands.Context, cog: str):
        try:
            await self.bot.unload_extension(f"{cog}")
            await self.bot.load_extension(f"{cog}")
            await ctx.send(f"✅ `{cog}` амжилттай дахин ачаалагдлаа!")
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: `{e}`")

    @commands.command(name='broadcast', help='Economy.db дахь бүх хэрэглэгчдэд DM илгээх.')
    @commands.is_owner()
    async def broadcast_dm(self, ctx: commands.Context, *, message: str):
        """Economy.db дахь бүх хэрэглэгчдэд DM илгээх"""
        if not message.strip():
            await ctx.send("❌ Мессэж хоосон байна!")
            return

        # Database файлын зам
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'economy.db')
        
        if not os.path.exists(db_path):
            await ctx.send("❌ Economy.db файл олдсонгүй!")
            return

        try:
            # Эхлэх мессэж
            status_msg = await ctx.send("🔄 DM илгээж эхэлж байна...")
            
            async with aiosqlite.connect(db_path) as db:
                # Бүх хэрэглэгчийн ID авах
                async with db.execute("SELECT DISTINCT user_id FROM economy") as cursor:
                    user_rows = await cursor.fetchall()
                    user_ids = [row[0] for row in user_rows]

            if not user_ids:
                await status_msg.edit(content="❌ Economy.db-д хэрэглэгч олдсонгүй!")
                return

            total_users = len(user_ids)
            sent_count = 0
            failed_count = 0
            
            # Batch илгээх (Discord rate limit-ээс зайлсхийх)
            for i, user_id in enumerate(user_ids):
                try:
                    user = self.bot.get_user(user_id)
                    if not user:
                        user = await self.bot.fetch_user(user_id)
                    
                    if user:
                        # DM илгээх
                        embed = discord.Embed(
                            title="📢 MongolBot Team",
                            description=message,
                            color=discord.Color.blue()
                        )
                        embed.set_footer(text="MongolBot Development Team")
                        
                        await user.send(embed=embed)
                        sent_count += 1
                    else:
                        failed_count += 1
                        
                except discord.Forbidden:
                    # Хэрэглэгч DM хүлээн авахгүй байгаа
                    failed_count += 1
                except discord.NotFound:
                    # Хэрэглэгч олдсонгүй
                    failed_count += 1
                except Exception as e:
                    failed_count += 1
                    print(f"DM илгээхэд алдаа user_id {user_id}: {e}")

                # Прогресс харуулах (хэрэв 10-аас илүү хэрэглэгч байвал)
                if total_users > 10 and (i + 1) % 10 == 0:
                    await status_msg.edit(content=f"🔄 {i + 1}/{total_users} илгээгдэж байна...")
                
                # Rate limiting (0.5 секунд хүлээх)
                await asyncio.sleep(0.5)

            # Дүгнэлт
            success_embed = discord.Embed(
                title="✅ DM илгээлт дууслаа!",
                color=discord.Color.green()
            )
            success_embed.add_field(name="📊 Статистик", value=f"""
            **Нийт хэрэглэгч:** {total_users}
            **Амжилттай илгээсэн:** {sent_count}
            **Амжилтгүй:** {failed_count}
            **Амжилтын хувь:** {(sent_count/total_users)*100:.1f}%
            """, inline=False)
            
            await status_msg.edit(content="", embed=success_embed)

        except Exception as e:
            await ctx.send(f"❌ DM илгээхэд алдаа гарлаа: `{e}`")

    @commands.command(name='dm_count', help='Economy.db дахь хэрэглэгчийн тоог харах.')
    @commands.is_owner()
    async def dm_count(self, ctx: commands.Context):
        """Economy.db дахь хэрэглэгчийн тоог харах"""
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'economy.db')
        
        if not os.path.exists(db_path):
            await ctx.send("❌ Economy.db файл олдсонгүй!")
            return

        try:
            async with aiosqlite.connect(db_path) as db:
                # Нийт хэрэглэгчийн тоо
                async with db.execute("SELECT COUNT(DISTINCT user_id) FROM economy") as cursor:
                    result = await cursor.fetchone()
                    total_users = result[0] if result else 0
                
                # Нийт балансын дүн
                async with db.execute("SELECT SUM(balance) FROM economy") as cursor:
                    result = await cursor.fetchone()
                    total_balance = result[0] if result and result[0] else 0

            embed = discord.Embed(
                title="📊 Economy Database Статистик",
                color=discord.Color.blue()
            )
            embed.add_field(name="👥 Нийт хэрэглэгч", value=f"{total_users:,}", inline=True)
            embed.add_field(name="💰 Нийт баланс", value=f"{total_balance:,}₮", inline=True)
            embed.add_field(name="📈 Дундаж баланс", value=f"{(total_balance/total_users):,.0f}₮" if total_users > 0 else "0₮", inline=True)
            
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Статистик авахад алдаа гарлаа: `{e}`")

    @commands.command(name='leave_server', help='Тодорхой серверээс bot-ыг гаргах.')
    @commands.is_owner()
    async def leave_server(self, ctx: commands.Context, guild_id: int):
        """Guild ID ашиглан тухайн серверээс bot-ыг гаргах"""
        guild = self.bot.get_guild(guild_id)
        
        if not guild:
            await ctx.send(f"❌ Guild ID `{guild_id}` олдсонгүй эсвэл bot тэр серверт байхгүй байна.")
            return
        
        guild_name = guild.name
        member_count = guild.member_count
        
        try:
            # Confirmation embed
            confirm_embed = discord.Embed(
                title="⚠️ Сервер орхих баталгаажуулалт",
                description=f"**Сервер:** {guild_name}\n**ID:** {guild_id}\n**Гишүүдийн тоо:** {member_count}",
                color=discord.Color.orange()
            )
            confirm_embed.add_field(
                name="❓ Та уг серверээс bot-ыг гаргахдаа итгэлтэй байна уу?",
                value="Энэ үйлдлийг буцаах боломжгүй!",
                inline=False
            )
            
            msg = await ctx.send(embed=confirm_embed)
            await msg.add_reaction("✅")  # Тийм
            await msg.add_reaction("❌")  # Үгүй
            
            def check(reaction: discord.Reaction, user: discord.User):
                return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == msg.id
            
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
                
                if str(reaction.emoji) == "✅":
                    # Серверээс гарах
                    await guild.leave()
                    
                    success_embed = discord.Embed(
                        title="✅ Амжилттай серверээс гарлаа!",
                        description=f"**Сервер:** {guild_name}\n**ID:** {guild_id}",
                        color=discord.Color.green()
                    )
                    await ctx.send(embed=success_embed)
                    
                else:
                    await ctx.send("❌ Серверээс гарах үйлдлийг цуцаллаа.")
                    
            except asyncio.TimeoutError:
                await ctx.send("⏰ Хугацаа дууссан! Серверээс гарах үйлдлийг цуцаллаа.")
                
        except discord.Forbidden:
            await ctx.send(f"❌ Серверээс гарах эрх хүрэлцэхгүй байна!")
        except Exception as e:
            await ctx.send(f"❌ Серверээс гарахад алдаа гарлаа: `{e}`")

    @commands.command(name='list_servers', help='Bot байгаа бүх серверүүдийн жагсаалт.')
    @commands.is_owner()
    async def list_servers(self, ctx: commands.Context):
        """Bot байгаа бүх серверүүдийн жагсаалт харуулах"""
        guilds = self.bot.guilds
        
        if not guilds:
            await ctx.send("❌ Bot ямар ч серверт байхгүй байна.")
            return
        
        # Серверүүдийг гишүүдийн тооноор эрэмбэлэх
        sorted_guilds = sorted(guilds, key=lambda g: g.member_count or 0, reverse=True)
        
        embed = discord.Embed(
            title=f"🏠 Bot байгаа серверүүд ({len(guilds)})",
            color=discord.Color.blue()
        )
        
        # Хуудаслах (Discord embed limit-ээс болж)
        page_size = 10
        pages = []
        
        for i in range(0, len(sorted_guilds), page_size):
            page_guilds = sorted_guilds[i:i + page_size]
            page_content = ""
            
            for guild in page_guilds:
                owner = guild.owner.name if guild.owner else "Тодорхойгүй"
                joined_at = guild.me.joined_at.strftime('%Y-%m-%d %H:%M') if guild.me and guild.me.joined_at else "Тодорхойгүй"
                page_content += f"**{guild.name}**\n"
                page_content += f"├ ID: `{guild.id}`\n"
                page_content += f"├ Гишүүд: {guild.member_count:,}\n"
                page_content += f"├ Эзэн: {owner}\n"
                page_content += f"└ Нэгдсэн огноо: {joined_at}\n\n"
            
            page_embed = discord.Embed(
                title=f"🏠 Bot байгаа серверүүд ({len(guilds)}) - Хуудас {len(pages) + 1}",
                description=page_content,
                color=discord.Color.blue()
            )
            page_embed.set_footer(text=f"Нийт серверүүд: {len(guilds)} | Нийт гишүүд: {sum(g.member_count or 0 for g in guilds):,}")
            pages.append(page_embed)
        
        # Хэрэв 1 хуудас л байвал шууд илгээх
        if len(pages) == 1:
            await ctx.send(embed=pages[0])
            return
        
        # Олон хуудас байвал navigation нэмэх
        current_page = 0
        msg = await ctx.send(embed=pages[current_page])
        
        if len(pages) > 1:
            await msg.add_reaction("⬅️")
            await msg.add_reaction("➡️")
            
            def check(reaction: discord.Reaction, user: discord.User):
                return user == ctx.author and str(reaction.emoji) in ["⬅️", "➡️"] and reaction.message.id == msg.id
            
            while True:
                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                    
                    if str(reaction.emoji) == "➡️" and current_page < len(pages) - 1:
                        current_page += 1
                        await msg.edit(embed=pages[current_page])
                    elif str(reaction.emoji) == "⬅️" and current_page > 0:
                        current_page -= 1
                        await msg.edit(embed=pages[current_page])
                    
                    await msg.remove_reaction(reaction, user)
                    
                except asyncio.TimeoutError:
                    break

    @commands.command(name='delete', help='Хэрэглэгчийн бүх мэдээллийг database-ees устгах.')
    @commands.is_owner()
    async def delete_user_data(self, ctx: commands.Context, user_id: int):
        """Хэрэглэгчийн бүх мэдээллийг database-ees устгах"""
        db_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
        if not os.path.exists(db_dir):
            await ctx.send("❌ Database хавтас олдсонгүй!")
            return

        deleted_tables = []
        failed_tables = []
        # Бүх .db файлуудыг шалгах
        for fname in os.listdir(db_dir):
            if fname.endswith('.db'):
                db_path = os.path.join(db_dir, fname)
                try:
                    async with aiosqlite.connect(db_path) as db:
                        # Бүх хүснэгтүүдийг авах
                        async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
                            tables = [row[0] for row in await cursor.fetchall()]
                        for table in tables:
                            # Хэрэглэгчийн ID багана байгаа эсэхийг шалгах
                            async with db.execute(f"PRAGMA table_info({table})") as cur2:
                                columns = [row[1] for row in await cur2.fetchall()]
                            if 'user_id' in columns:
                                await db.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
                                deleted_tables.append(f"{fname}:{table}")
                        await db.commit()
                except Exception as e:
                    failed_tables.append(f"{fname} ({e})")

        embed = discord.Embed(title="🗑️ Хэрэглэгчийн мэдээлэл устгах", color=discord.Color.red())
        embed.add_field(name="Амжилттай устгасан хүснэгтүүд", value="\n".join(deleted_tables) if deleted_tables else "Байхгүй", inline=False)
        if failed_tables:
            embed.add_field(name="Амжилтгүй хүснэгтүүд", value="\n".join(failed_tables), inline=False)
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))