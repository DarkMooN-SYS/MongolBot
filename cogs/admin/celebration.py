import discord
from discord.ext import commands
from discord import app_commands
import logging
from datetime import datetime, timezone
from typing import Optional, List
from ..utils.database import get_async_db_context

logger = logging.getLogger(__name__)

class Celebration(commands.Cog):
    """Server Milestone Celebration System - Сервер тооны баярын систем"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # Milestone тоонууд
        self.milestones = [50, 75, 100, 150, 200, 250, 500, 1000, 1500, 2000, 2500, 5000, 10000]
    
    async def cog_load(self):
        """Cog ачаалагдах үед database тохируулах"""
        await self.setup_database()
    
    async def setup_database(self):
        """Database хүснэгт үүсгэх"""
        async with get_async_db_context('celebration') as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS milestone_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    milestone_count INTEGER NOT NULL,
                    guild_count INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    notified INTEGER DEFAULT 0
                )
            ''')
            await db.commit()
    
    def is_milestone(self, count: int) -> bool:
        """Тоо milestone эсэхийг шалгах"""
        return count in self.milestones
    
    async def get_last_milestone(self) -> Optional[int]:
        """Сүүлийн milestone авах"""
        async with get_async_db_context('celebration') as db:
            async with db.execute(
                'SELECT milestone_count FROM milestone_history ORDER BY timestamp DESC LIMIT 1'
            ) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 0
    
    async def log_milestone(self, milestone: int, guild_count: int, event_type: str):
        """Milestone-ийг database-д хадгалах"""
        timestamp = datetime.now(timezone.utc).isoformat()
        async with get_async_db_context('celebration') as db:
            await db.execute('''
                INSERT INTO milestone_history 
                (milestone_count, guild_count, event_type, timestamp, notified)
                VALUES (?, ?, ?, ?, 1)
            ''', (milestone, guild_count, event_type, timestamp))
            await db.commit()
    
    async def send_milestone_notification(self, milestone: int, guild_count: int, event_type: str):
        """Bot owner-т milestone мэдэгдэл илгээх"""
        try:
            owner = self.bot.get_user(self.bot.owner_id)
            if not owner:
                try:
                    owner = await self.bot.fetch_user(self.bot.owner_id)
                except:
                    logger.error(f"Could not fetch bot owner with ID {self.bot.owner_id}")
                    return
            
            if owner:
                # Баярын мэссеж
                celebration_messages = {
                    50: "🎉 Тав дахь арав! Анхны том milestone!",
                    75: "🌟 Долоод ес! Гайхалтай ахиц!",
                    100: "🎊 ЗУУН СЕРВЕР! Энэ бол том амжилт!",
                    150: "⭐ Зуун тавин сервер! Өсөж байна!",
                    200: "🚀 Хоёр зуун сервер! Гайхалтай!",
                    250: "💎 Хоёр зуун тавин! Илүү дээр!",
                    500: "🏆 ТАВ ЗУУН СЕРВЕР! Асар том амжилт!",
                    1000: "👑 МЯНГАН СЕРВЕР! Хааны амжилт!",
                    1500: "🌌 Мянга тавин! Одод руу өндийж байна!",
                    2000: "🎆 ХОЁР МЯНГА! Домогт амжилт!",
                    2500: "🌠 Хоёр мянга тавин! Тэнгэрийн амжилт!",
                    5000: "🌟🎊 ТАВ МЯНГА! ДОМОГТ MILESTONE! 🎊🌟",
                    10000: "👑🎉 АРВАН МЯНГА! ХААНТ АМЖИЛТ! 🎉👑"
                }
                
                message = celebration_messages.get(milestone, f"🎉 {milestone} сервер! Гайхалтай амжилт!")
                
                embed = discord.Embed(
                    title="🎉 Server Milestone Баяр! 🎉",
                    description=message,
                    color=discord.Color.gold(),
                    timestamp=datetime.now(timezone.utc)
                )
                
                embed.add_field(
                    name="📊 Статистик",
                    value=(
                        f"**Milestone:** {milestone:,} сервер\n"
                        f"**Одоогийн тоо:** {guild_count:,} сервер\n"
                        f"**Үйл явдал:** {event_type}"
                    ),
                    inline=False
                )
                
                embed.add_field(
                    name="🤖 MongolBot",
                    value="Монголын хамгийн том Discord Bot!",
                    inline=False
                )
                
                embed.set_footer(text="MongolBot Milestone System")
                if self.bot.user and self.bot.user.display_avatar:
                    embed.set_thumbnail(url=self.bot.user.display_avatar.url)
                
                await owner.send(embed=embed)
                logger.info(f"Milestone notification sent to owner: {milestone} servers")
                
        except Exception as e:
            logger.error(f"Failed to send milestone notification: {e}")
    
    async def check_milestone(self, guild_count: int, event_type: str):
        """Milestone хүрсэн эсэхийг шалгаж мэдэгдэх"""
        # Одоогийн тоо milestone эсэхийг шалгах
        if not self.is_milestone(guild_count):
            return
        
        # Өмнө нь энэ milestone-ийг тэмдэглэсэн эсэхийг шалгах
        last_milestone = await self.get_last_milestone()
        if guild_count <= last_milestone:
            return
        
        # Milestone тэмдэглэх
        await self.log_milestone(guild_count, guild_count, event_type)
        await self.send_milestone_notification(guild_count, guild_count, event_type)
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Сервер нэмэгдэхэд milestone шалгах"""
        guild_count = len(self.bot.guilds)
        logger.info(f"Joined guild: {guild.name} (ID: {guild.id}). Total guilds: {guild_count}")
        await self.check_milestone(guild_count, "Сервер нэмэгдсэн")
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        """Сервер устахад лог хийх"""
        guild_count = len(self.bot.guilds)
        logger.info(f"Left guild: {guild.name} (ID: {guild.id}). Total guilds: {guild_count}")
    
    @commands.command(name='mcelebrate', help='Гар аргаар milestone баяр тэмдэглэх (owner only)')
    @commands.is_owner()
    async def manual_celebrate(self, ctx: commands.Context, milestone: Optional[int] = None):
        """Гар аргаар milestone тэмдэглэх"""
        guild_count = len(self.bot.guilds)
        
        if milestone is None:
            milestone = guild_count
        
        if not self.is_milestone(milestone):
            await ctx.send(f"❌ {milestone} нь milestone биш. Milestone тоонууд: {', '.join(map(str, self.milestones))}")
            return
        
        # Milestone тэмдэглэх
        await self.log_milestone(milestone, guild_count, "Гар аргаар тэмдэглэсэн")
        await self.send_milestone_notification(milestone, guild_count, "Гар аргаар тэмдэглэсэн")
        
        embed = discord.Embed(
            title="🎉 Milestone Тэмдэглэгдлээ!",
            description=f"**{milestone}** сервер milestone амжилттай тэмдэглэгдлээ!",
            color=discord.Color.green()
        )
        embed.add_field(name="Одоогийн сервер тоо", value=f"{guild_count:,}", inline=True)
        await ctx.send(embed=embed)
    
    @app_commands.command(name='mstats', description='Server milestone статистик харах')
    async def milestone_stats(self, interaction: discord.Interaction):
        """Milestone статистик харуулах"""
        guild_count = len(self.bot.guilds)
        
        # Milestone түүх авах
        async with get_async_db_context('celebration') as db:
            async with db.execute(
                'SELECT milestone_count, timestamp, event_type FROM milestone_history ORDER BY milestone_count DESC LIMIT 10'
            ) as cursor:
                history = await cursor.fetchall()
        
        embed = discord.Embed(
            title="📊 MongolBot Server Statistics",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="🤖 Одоогийн төлөв",
            value=(
                f"**Сервер тоо:** {guild_count:,}\n"
                f"**Хэрэглэгч тоо:** {sum(g.member_count for g in self.bot.guilds if g.member_count):,}"
            ),
            inline=False
        )
        
        # Дараагийн milestone
        next_milestone = None
        for milestone in self.milestones:
            if milestone > guild_count:
                next_milestone = milestone
                break
        
        if next_milestone:
            remaining = next_milestone - guild_count
            embed.add_field(
                name="🎯 Дараагийн Milestone",
                value=f"**{next_milestone:,}** сервер\n({remaining:,} сервер хэрэгтэй)",
                inline=False
            )
        
        # Milestone түүх
        if history:
            history_text = ""
            for milestone, timestamp, event_type in history[:5]:
                date = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                history_text += f"🎉 **{milestone:,}** сервер - {date}\n"
            
            embed.add_field(
                name="🏆 Milestone Түүх",
                value=history_text or "Milestone түүх байхгүй",
                inline=False
            )
        
        embed.set_footer(text="MongolBot - Монголын #1 Discord Bot")
        await interaction.response.send_message(embed=embed)
    
    @commands.command(name='mannounce', help='Milestone announcement бүх сервэрт илгээх (owner only)')
    @commands.is_owner()
    async def milestone_announce(self, ctx: commands.Context, *, message: str):
        """Milestone announcement бүх сервэрт илгээх"""
        if not message.strip():
            await ctx.send("❌ Хоосон мэссеж илгээх боломжгүй!")
            return
            
        guild_count = len(self.bot.guilds)
        if guild_count == 0:
            await ctx.send("❌ Бот ямар ч сервэрт байхгүй байна!")
            return
            
        sent_count = 0
        failed_count = 0
        
        embed = discord.Embed(
            title="📢 MongolBot Announcement",
            description=message,
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="📊 Статистик", 
            value=f"MongolBot одоо **{guild_count:,}** сервэрт байна!",
            inline=False
        )
        
        embed.set_footer(text="MongolBot - Монголын #1 Discord Bot")
        if self.bot.user and self.bot.user.display_avatar:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        # Прогресс мэссеж
        progress_msg = await ctx.send("📤 Announcement илгээж байна...")
        
        for guild in self.bot.guilds:
            try:
                # Системийн суваг олох
                channel = None
                for ch in guild.text_channels:
                    if ch.permissions_for(guild.me).send_messages:
                        channel = ch
                        break
                
                if channel:
                    await channel.send(embed=embed)
                    sent_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send announcement to {guild.name}: {e}")
        
        # Үр дүнг мэдэгдэх
        result_embed = discord.Embed(
            title="✅ Announcement Илгээгдлээ",
            color=discord.Color.green()
        )
        result_embed.add_field(name="Амжилттай", value=f"{sent_count:,} сервэр", inline=True)
        result_embed.add_field(name="Амжилтгүй", value=f"{failed_count:,} сервэр", inline=True)
        result_embed.add_field(name="Нийт", value=f"{guild_count:,} сервэр", inline=True)
        
        await progress_msg.edit(content="", embed=result_embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Celebration(bot))