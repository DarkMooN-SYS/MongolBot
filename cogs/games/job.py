import os
from pathlib import Path
import discord
from discord.ext import commands
import aiosqlite
import random
import asyncio
import time
import json
from typing import Optional, Any

class Job(commands.Cog):
    def __init__(self, bot: commands.Bot):
        """
        Job cog-ийг үүсгэх конструктор.
        - Ботын объект болон өгөгдлийн сангийн замыг тохируулна.
        - Өгөгдлийн сангийн холболтыг асинхрон байдлаар үүсгэнэ.
        """
        self.bot: commands.Bot = bot
        # Өгөгдлийн санг хадгалах data хавтсыг зааж өгнө
        self.data_dir: Path = Path(__file__).parent.parent.parent / 'data'
        self.data_dir.mkdir(exist_ok=True)
        self.db_path: Path = self.data_dir / 'economy.db'
        self.conn: Optional[aiosqlite.Connection] = None
        self.bot.loop.create_task(self.setup_database())
        self.job_levels = self.load_job_levels()

    async def setup_database(self) -> None:
        """
        Өгөгдлийн сангийн хүснэгтүүдийг үүсгэнэ.
        - economy: хэрэглэгчийн мөнгө
        - bank: банкны данс
        - job_cooldowns: cooldown-ууд
        - job: хэрэглэгчийн level, XP мэдээлэл
        """
        self.conn = await aiosqlite.connect(str(self.db_path))
        await self.conn.execute("PRAGMA journal_mode=WAL;")
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS economy (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bank (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS job_cooldowns (
                user_id INTEGER PRIMARY KEY,
                hack_cooldown INTEGER DEFAULT 0,
                rob_cooldown INTEGER DEFAULT 0,
                block_cooldown INTEGER DEFAULT 0
            )
        """)
        # job хүснэгтийг үүсгэх/шинэчлэх
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS job (
                user_id INTEGER PRIMARY KEY,
                level INTEGER DEFAULT 1,
                rob_level INTEGER DEFAULT 1,
                hack_level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                vip_expiry INTEGER DEFAULT 0
            )
        """)
        # Хэрэв job хүснэгт байгаа бол шаардлагатай баганууд нэмэх
        try:
            await self.conn.execute("ALTER TABLE job ADD COLUMN level INTEGER DEFAULT 1")
        except:
            pass
        try:
            await self.conn.execute("ALTER TABLE job ADD COLUMN rob_level INTEGER DEFAULT 1")
        except:
            pass
        try:
            await self.conn.execute("ALTER TABLE job ADD COLUMN hack_level INTEGER DEFAULT 1")
        except:
            pass
        try:
            await self.conn.execute("ALTER TABLE job ADD COLUMN xp INTEGER DEFAULT 0")
        except:
            pass
        try:
            await self.conn.execute("ALTER TABLE job ADD COLUMN vip_expiry INTEGER DEFAULT 0")
        except:
            pass
        await self.conn.commit()

    async def check_vip(self, user_id: int) -> bool:
        """
        Хэрэглэгч VIP эсэхийг шалгана.
        """
        if self.conn is None:
            return False
        async with self.conn.execute("SELECT vip_expiry FROM job WHERE user_id=?", (user_id,)) as cursor:
            vip_status = await cursor.fetchone()
        return bool(vip_status and vip_status[0])

    async def get_balance(self, user_id: int) -> int:
        """
        Хэрэглэгчийн мөнгөний үлдэгдлийг буцаана.
        """
        if self.conn is None:
            return 0
        async with self.conn.execute("SELECT balance FROM economy WHERE user_id=?", (user_id,)) as cursor:
            result = await cursor.fetchone()
        return result[0] if result else 0

    async def update_balance(self, user_id: int, amount: int) -> int:
        """
        Хэрэглэгчийн мөнгийг нэмэх/хасах (сөрөг үлдэгдэл үүсгэхгүй)
        """
        if self.conn is None:
            return 0
        current_balance = await self.get_balance(user_id)
        new_balance = max(current_balance + amount, 0)
        await self.conn.execute("""
            INSERT INTO economy (user_id, balance) VALUES (?, ?) 
            ON CONFLICT(user_id) DO UPDATE SET balance = ?
        """, (user_id, new_balance, new_balance))
        await self.conn.commit()
        return new_balance

    async def get_cooldown(self, user_id: int, cooldown_type: str) -> int:
        """
        Хэрэглэгчийн cooldown-ыг авах (hack, rob, block)
        """
        if self.conn is None:
            return 0
        async with self.conn.execute(f"SELECT {cooldown_type}_cooldown FROM job_cooldowns WHERE user_id=?", (user_id,)) as cursor:
            result = await cursor.fetchone()
        return result[0] if result else 0

    async def hack_with_delay(self, ctx: commands.Context, hacker_id: int, target_id: int, percent: float = 0.05) -> None:
        """
        Хак командын 1 минутын delay болон мөнгө шилжүүлэх логик.
        """
        await asyncio.sleep(60)  # 1 минут хүлээнэ
        target_bank_balance = await self.get_bank_balance(target_id)
        if target_bank_balance <= 0:
            user = ctx.bot.get_user(target_id)
            name = user.display_name if user else str(target_id)
            await ctx.send(f"⚠️ **{name}** хакдах боломжгүй, банканд ямар ч мөнгөгүй байна!")
            return
        stolen_amount = int(target_bank_balance * percent)
        await self.update_bank_balance(hacker_id, stolen_amount)
        await self.update_bank_balance(target_id, -stolen_amount)
        hacker = ctx.bot.get_user(hacker_id)
        target = ctx.bot.get_user(target_id)
        hacker_name = hacker.display_name if hacker else str(hacker_id)
        target_name = target.display_name if target else str(target_id)
        await ctx.send(f"💻 **{hacker_name}** **{target_name}**-ын банкнаас {stolen_amount:,}₮ хакдлаа!")

    async def hack_bank_with_delay(self, ctx: commands.Context, hacker_id: int, target_id: int, percent: float = 0.03) -> None:
        """
        Банк хак командын 1 минутын delay болон мөнгө шилжүүлэх логик.
        """
        await asyncio.sleep(60)  # 1 минут хүлээнэ
        target_bank_balance = await self.get_bank_balance(target_id)
        if target_bank_balance <= 0:
            user = ctx.bot.get_user(target_id)
            name = user.display_name if user else str(target_id)
            await ctx.send(f"⚠️ **{name}** банк хакдах боломжгүй, банканд ямар ч мөнгөгүй байна!")
            return
        stolen_amount = int(target_bank_balance * percent)
        await self.update_bank_balance(hacker_id, stolen_amount)
        await self.update_bank_balance(target_id, -stolen_amount)
        hacker = ctx.bot.get_user(hacker_id)
        target = ctx.bot.get_user(target_id)
        hacker_name = hacker.display_name if hacker else str(hacker_id)
        target_name = target.display_name if target else str(target_id)
        await ctx.send(f"💾 **{hacker_name}** **{target_name}**-ын банкны хадгаламжаас {stolen_amount:,}₮ хакдлаа!")

    async def update_cooldown(self, user_id: int, cooldown_type: str, duration: int) -> None:
        """
        Cooldown-ыг шинэчлэх (hack, rob, block)
        """
        if self.conn is None:
            return
        block_until = int(time.time()) + duration
        await self.conn.execute(f"""
            INSERT INTO job_cooldowns (user_id, {cooldown_type}_cooldown) 
            VALUES (?, ?) 
            ON CONFLICT(user_id) DO UPDATE SET {cooldown_type}_cooldown = excluded.{cooldown_type}_cooldown
        """, (user_id, block_until))
        await self.conn.commit()

    async def get_bank_balance(self, user_id: int) -> int:
        """
        Банкны дансны үлдэгдэл авах
        """
        if self.conn is None:
            return 0
        async with self.conn.execute("SELECT balance FROM bank WHERE user_id=?", (user_id,)) as cursor:
            result = await cursor.fetchone()
        return result[0] if result else 0

    async def update_bank_balance(self, user_id: int, amount: int) -> int:
        """
        Банкны дансны мөнгийг нэмэх/хасах
        """
        if self.conn is None:
            return 0
        current_balance = await self.get_bank_balance(user_id)
        new_balance = max(current_balance + amount, 0)
        await self.conn.execute("""
            INSERT INTO bank (user_id, balance) VALUES (?, ?) 
            ON CONFLICT(user_id) DO UPDATE SET balance = excluded.balance
        """, (user_id, new_balance))
        await self.conn.commit()
        return new_balance

    async def format_remaining_time(self, remaining_time: int) -> str:
        """
        Үлдсэн хугацааг (секунд) цаг, минут, секунд болгон форматлана.
        """
        hours, remainder = divmod(remaining_time, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours} цаг, {minutes} мин, {seconds} сек"

    async def get_user_status_data(self, user_id: int) -> dict:
        """
        Хэрэглэгчийн статусын мэдээллийг dict хэлбэрээр буцаана.
        """
        if self.conn is None:
            return {
                "level": 1,
                "rob_level": 1, 
                "hack_level": 1,
                "balance": 0,
                "bank": 0,
                "is_vip": False,
                "xp": 0
            }
        
        # Хэрэглэгчийн бичлэг байгаа эсэхийг шалгах, байхгүй бол үүсгэх
        await self.conn.execute("""
            INSERT OR IGNORE INTO job (user_id, level, rob_level, hack_level, xp, vip_expiry) 
            VALUES (?, 1, 1, 1, 0, 0)
        """, (user_id,))
        await self.conn.commit()
        
        # Level, rob_level, hack_level, XP авах (байхгүй бол 1 гэж үзнэ)
        level = rob_level = hack_level = xp = 1
        async with self.conn.execute("SELECT level, rob_level, hack_level, xp FROM job WHERE user_id=?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                level = row[0] if row[0] is not None else 1
                rob_level = row[1] if row[1] is not None else 1
                hack_level = row[2] if row[2] is not None else 1
                xp = row[3] if row[3] is not None else 0
        
        # Мөнгө болон банкны үлдэгдэл авах
        balance = await self.get_balance(user_id)
        bank = await self.get_bank_balance(user_id)
        
        # VIP статус шалгах
        is_vip = await self.check_vip(user_id)
        
        return {
            "level": level,
            "rob_level": rob_level,
            "hack_level": hack_level,
            "balance": balance,
            "bank": bank,
            "is_vip": is_vip,
            "xp": xp
        }

    async def make_status_embed(self, ctx: commands.Context, status: dict, member: Optional[discord.abc.User] = None) -> discord.Embed:
        """
        Хэрэглэгчийн статусын мэдээллийг discord embed болгон форматлана.
        """
        if member is None:
            member = ctx.author
        display_name = getattr(member, 'display_name', None) or getattr(member, 'name', 'Хэрэглэгч')
        avatar_url = getattr(member, 'display_avatar', None)
        if avatar_url is None:
            avatar_url = getattr(member, 'avatar', None)
        if avatar_url is not None:
            avatar_url = avatar_url.url if hasattr(avatar_url, 'url') else str(avatar_url)
        else:
            avatar_url = None

        # VIP статусаар өнгө тодорхойлох
        embed_color = discord.Color.gold() if status["is_vip"] else discord.Color.from_rgb(52, 152, 219)
        
        # Хэрэглэгчийн нийт хөрөнгө тооцоолох
        total_wealth = status["balance"] + status["bank"]
        
        # Level прогресс тооцоолох
        current_level = status["level"]
        current_xp = status.get("xp", 0)
        xp_for_next_level = 100 + (current_level - 1) * 20
        xp_progress = (current_xp / xp_for_next_level) * 100 if xp_for_next_level > 0 else 0
        
        # Progress bar үүсгэх
        progress_bar_length = 10
        filled_length = int(progress_bar_length * xp_progress // 100)
        progress_bar = "█" * filled_length + "░" * (progress_bar_length - filled_length)
        
        embed = discord.Embed(
            title=f"📊 {display_name} - Профайл статус",
            description=f"{'👑 VIP Гишүүн' if status['is_vip'] else '🌟 Энгийн хэрэглэгч'}",
            color=embed_color
        )
        
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        
        # Түвшин ба XP мэдээлэл
        embed.add_field(
            name="⭐ Түвшин & Туршлага",
            value=f"**Түвшин:** {current_level}\n"
                  f"**XP:** {current_xp:,}/{xp_for_next_level:,}\n"
                  f"**Прогресс:** {progress_bar} {xp_progress:.1f}%",
            inline=False
        )
        
        # Санхүүгийн мэдээлэл
        embed.add_field(
            name="� Санхүүгийн байдал",
            value=f"💸 **Халаас:** {status['balance']:,}₮\n"
                  f"🏦 **Банк:** {status['bank']:,}₮\n"
                  f"💎 **Нийт:** {total_wealth:,}₮",
            inline=True
        )
        
        # Ур чадварын түвшин ба прогресс
        requirements = await self.get_next_level_requirements(member.id)
        rob_needed = requirements['xp_needed_for_rob']
        hack_needed = requirements['xp_needed_for_hack']
        
        if rob_needed == 0:
            rob_display = "MAX"
        else:
            rob_display = f"{rob_needed} XP"
            
        if hack_needed == 0:
            hack_display = "MAX"
        else:
            hack_display = f"{hack_needed} XP"
        
        embed.add_field(
            name="⚔️ Ур чадварын түвшин",
            value=f"🤺 **Роб:** {status['rob_level']} ({rob_display})\n"
                  f"💻 **Хак:** {status['hack_level']} ({hack_display})\n"
                  f"🛡️ **Хамгаалалт:** Идэвхтэй",
            inline=True
        )
        
        # Статус ба онцлогууд
        vip_status = "👑 Идэвхтэй" if status["is_vip"] else "❌ Хаалттай"
        rank_emoji = self.get_rank_emoji(current_level)
        embed.add_field(
            name="🏆 Статус ба Зэрэглэл",
            value=f"**VIP:** {vip_status}\n"
                  f"**Зэрэг:** {rank_emoji} {self.get_rank_name(current_level)}\n"
                  f"**ID:** #{member.id}",
            inline=False
        )
        
        # Footer мэдээлэл
        embed.set_footer(
            text=f"MongolBot Economy System • {ctx.guild.name if ctx.guild else 'DM'}", 
            icon_url=ctx.bot.user.avatar.url if ctx.bot.user.avatar else None
        )
        
        return embed

    def load_job_levels(self):
        """
        job_levels.json файлыг ачаална.
        """
        levels_path = Path(__file__).parent / 'job_levels.json'
        if not levels_path.exists():
            return {}
        with open(levels_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_level_config(self, job_type: str, level: int) -> dict:
        """
        Тухайн job-ийн түвшний тохиргоог буцаана.
        job_type: 'ROB_LEVELS' эсвэл 'HACK_LEVELS'
        level: хэрэглэгчийн түвшин
        """
        levels = self.job_levels.get(job_type, {})
        default = self.job_levels.get(f"DEFAULT_{job_type.split('_')[0]}", {})
        config = default.copy()
        for lvl in sorted(map(int, levels.keys())):
            if level >= lvl:
                config.update(levels[str(lvl)])
        return config

    async def level_up_user(self, user_id: int, level_type: str = "level") -> None:
        """
        Хэрэглэгчийн level, rob_level, эсвэл hack_level-ийг 1-ээр нэмэгдүүлж, DM-ээр мэдэгдэл илгээнэ.
        level_type: "level", "rob_level", эсвэл "hack_level"
        """
        if self.conn is None:
            return
        # Level-ийг нэмэгдүүлэх
        await self.conn.execute(f"""
            UPDATE job SET {level_type} = COALESCE({level_type}, 1) + 1 WHERE user_id = ?
        """, (user_id,))
        await self.conn.commit()
        # Шинэ level-ийг авах
        async with self.conn.execute(f"SELECT {level_type} FROM job WHERE user_id=?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        new_level = row[0] if row else None
        # Хэрэглэгчид DM илгээх
        user = self.bot.get_user(user_id)
        if user is not None:
            try:
                await user.send(f"🎉 Таны {level_type.replace('_', ' ')} шинэ түвшин: {new_level} боллоо! Баяр хүргэе!")
            except Exception:
                pass  # Хэрэглэгч DM хаалттай байж болно

    async def add_xp(self, user_id: int, amount: int = 10) -> None:
        """
        Хэрэглэгчид XP нэмэх, level up шалгах, skill level автомат шинэчлэх
        """
        if self.conn is None:
            return
        # Хэрэглэгчийн бичлэг байгаа эсэхийг шалгах, байхгүй бол үүсгэх
        await self.conn.execute("""
            INSERT OR IGNORE INTO job (user_id, level, rob_level, hack_level, xp, vip_expiry) 
            VALUES (?, 1, 1, 1, 0, 0)
        """, (user_id,))
        # XP болон level авах
        async with self.conn.execute("SELECT xp, level FROM job WHERE user_id=?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        xp = row[0] if row and row[0] is not None else 0
        level = row[1] if row and row[1] is not None else 1
        xp += amount
        # Level up-д шаардагдах XP (жишээ: 100 + (level-1)*20)
        level_up_xp = 100 + (level - 1) * 20
        leveled_up = False
        while xp >= level_up_xp:
            xp -= level_up_xp
            level += 1
            leveled_up = True
            level_up_xp = 100 + (level - 1) * 20
        # Update main level and XP
        await self.conn.execute("UPDATE job SET xp=?, level=? WHERE user_id=?", (xp, level, user_id))
        await self.conn.commit()
        
        # Skill level автомат шинэчлэх
        await self.check_and_upgrade_skill_levels(user_id)
        
        # Level ахисан бол DM илгээх
        if leveled_up:
            user = self.bot.get_user(user_id)
            if user is not None:
                try:
                    await user.send(f"🎉 Таны level шинэ түвшин: {level} боллоо! Баяр хүргэе!")
                except Exception:
                    pass

    async def check_and_upgrade_skill_levels(self, user_id: int) -> None:
        """
        Хэрэглэгчийн XP-ийн дагуу rob_level, hack_level автомат нэмэгдүүлэх
        Max level: Rob 30, Hack 30
        """
        if self.conn is None:
            return
            
        # Хэрэглэгчийн статус авах
        status = await self.get_user_status_data(user_id)
        current_xp = status.get("xp", 0)
        rob_level = status.get("rob_level", 1)
        hack_level = status.get("hack_level", 1)
        
        # Rob level нэмэгдүүлэх шалгуур (200 XP тутамд +1, max 30)
        new_rob_level = min(1 + (current_xp // 200), 30)
        
        # Hack level нэмэгдүүлэх шалгуур (250 XP тутамд +1, max 30) 
        new_hack_level = min(1 + (current_xp // 250), 30)
        
        # Level шинэчлэх
        if new_rob_level > rob_level:
            await self.conn.execute("UPDATE job SET rob_level = ? WHERE user_id = ?", (new_rob_level, user_id))
            await self.send_skill_level_up_notification(user_id, "rob_level", rob_level, new_rob_level)
            
        if new_hack_level > hack_level:
            await self.conn.execute("UPDATE job SET hack_level = ? WHERE user_id = ?", (new_hack_level, user_id))
            await self.send_skill_level_up_notification(user_id, "hack_level", hack_level, new_hack_level)
            
        if new_rob_level > rob_level or new_hack_level > hack_level:
            await self.conn.commit()

    async def send_skill_level_up_notification(self, user_id: int, skill_type: str, old_level: int, new_level: int) -> None:
        """
        Skill level ахиход DM мэдэгдэл илгээх
        """
        user = self.bot.get_user(user_id)
        if user is not None:
            try:
                skill_name = "Роб" if skill_type == "rob_level" else "Хак"
                await user.send(f"🎉 Таны **{skill_name}** skill level {old_level} → {new_level} боллоо! Баяр хүргэе!")
            except Exception:
                pass

    async def get_next_level_requirements(self, user_id: int) -> dict:
        """
        Дараагийн level-д хэрэхэд шаардагдах XP мэдээллийг буцаана
        """
        status = await self.get_user_status_data(user_id)
        current_level = status.get("level", 1)
        current_xp = status.get("xp", 0)
        rob_level = status.get("rob_level", 1)
        hack_level = status.get("hack_level", 1)
        
        # Дараагийн main level-д шаардагдах XP
        next_level_xp = 100 + (current_level - 1) * 20
        xp_needed_for_level = max(next_level_xp - current_xp, 0)
        
        # Дараагийн rob level-д шаардагдах XP (max 30)
        if rob_level >= 30:
            xp_needed_for_rob = 0  # MAX түвшин
        else:
            next_rob_level_xp = rob_level * 200
            xp_needed_for_rob = max(next_rob_level_xp - current_xp, 0)
        
        # Дараагийн hack level-д шаардагдах XP (max 30)
        if hack_level >= 30:
            xp_needed_for_hack = 0  # MAX түвшин
        else:
            next_hack_level_xp = hack_level * 250
            xp_needed_for_hack = max(next_hack_level_xp - current_xp, 0)
        
        return {
            "current_xp": current_xp,
            "next_level": current_level + 1,
            "xp_for_next_level": next_level_xp,
            "xp_needed_for_level": xp_needed_for_level,
            "next_rob_level": min(rob_level + 1, 30),
            "xp_needed_for_rob": xp_needed_for_rob,
            "next_hack_level": min(hack_level + 1, 30),
            "xp_needed_for_hack": xp_needed_for_hack
        }

    def get_rank_emoji(self, level: int) -> str:
        """
        Түвшинд тохирсон зэрэглэлийн emoji буцаана.
        """
        if level >= 100:
            return "👑"  # Император
        elif level >= 75:
            return "🏆"  # Мастер
        elif level >= 50:
            return "🥇"  # Эксперт
        elif level >= 25:
            return "🥈"  # Мэргэжилтэн
        elif level >= 10:
            return "🥉"  # Туршлагатай
        else:
            return "🌟"  # Шинэхэн

    def get_rank_name(self, level: int) -> str:
        """
        Түвшинд тохирсон зэрэглэлийн нэр буцаана.
        """
        if level >= 100:
            return "Император"
        elif level >= 75:
            return "Мастер"
        elif level >= 50:
            return "Эксперт"
        elif level >= 25:
            return "Мэргэжилтэн"
        elif level >= 10:
            return "Туршлагатай"
        else:
            return "Шинэхэн"

    # ----------------- Роб хийх команд group -----------------
    @commands.group(name='rob', invoke_without_command=True)
    async def rob(self, ctx: commands.Context, target: discord.Member) -> None:
        """
        Хэрэглэгч өөр нэгэн хэрэглэгчийг дээрэмдэх команд.
        VIP бол илүү өндөр амжилтын хувь, бага cooldown авна.
        """
        robber_id, target_id = ctx.author.id, target.id

        # Бот болон өөрийгөө дээрэмдэхээс сэргийлнэ
        if target.bot or target_id == ctx.bot.user.id:
            await ctx.send("❌ Бот болон хэн ч байхгүй хэрэглэгчийг дээрэмдэх боломжгүй!")
            return

        if robber_id == target_id:
            await ctx.send("❌ Өөрийгөө дээрэмдэх боломжгүй!")
            return

        is_vip = await self.check_vip(robber_id)
        cooldown = await self.get_cooldown(robber_id, "rob")

        # Cooldown шалгах
        if int(time.time()) < cooldown:
            await ctx.send(f"⏳ Дахин дээрэмдэхийн тулд хүлээнэ үү: {await self.format_remaining_time(cooldown - int(time.time()))}")
            return

        target_balance = await self.get_balance(target_id)
        robber_balance = await self.get_balance(robber_id)

        if target_balance <= 0:
            await ctx.send(f"⚠️ {target.display_name} дээрэмдэх боломжгүй!")
            return

        status = await self.get_user_status_data(robber_id)
        rob_level = status.get("rob_level", 1)
        rob_config = self.get_level_config("ROB_LEVELS", rob_level)
        cooldown_time = rob_config.get("cooldown", 3600)
        success_chance = rob_config.get("success", 0.5)
        percent = rob_config.get("percent", 0.02)

        # Амжилттай бол мөнгө хулгайлна, үгүй бол торгууль төлнө
        if random.uniform(0, 1) < success_chance:
            stolen_amount = int(target_balance * percent)
            await self.update_balance(robber_id, stolen_amount)
            await self.update_balance(target_id, -stolen_amount)
            await ctx.send(f"💰 {ctx.author.display_name} {target.display_name}-аас {stolen_amount:,}₮ хулгайллаа!")
            await self.add_xp(robber_id, 20)
        else:
            # Дээрэм амжилтгүй болсон тохиолдолд хэрэглэгчийн үлдэгдлийн 10%-ийг торгууль болгон авна
            penalty = max(int(robber_balance * 0.1), 1000)  # Хамгийн багадаа 1000₮
            penalty = min(penalty, robber_balance)  # Үлдэгдлээс ихгүй
            await self.update_balance(robber_id, -penalty)
            await ctx.send(f"❌ Дээрэм амжилтгүй боллоо, та **{penalty:,}₮** торгууль төлсөн!")
            await self.add_xp(robber_id, 5)
        await self.update_cooldown(robber_id, "rob", cooldown_time)

    @rob.command(name='bank')
    async def rob_bank(self, ctx: commands.Context, target: discord.Member) -> None:
        """
        Хэрэглэгч банк дээрэмдэх команд (!rob bank @user)
        20 түвшинээс дээш хэрэглэгчид зөвхөн боломжтой
        """
        robber_id, target_id = ctx.author.id, target.id
        
        # 20 түвшин шаардлага шалгах
        status = await self.get_user_status_data(robber_id)
        rob_level = status.get("rob_level", 1)
        
        if rob_level < 20:
            await ctx.send(f"❌ **Rob Bank** командыг ашиглахын тулд та дор хаяж **20 rob level**-тэй байх ёстой! (Таны одоогийн rob level: {rob_level})")
            return
        
        rob_config = self.get_level_config("ROB_LEVELS", rob_level)
        cooldown_time = rob_config.get("cooldown", 3600)
        percent = rob_config.get("percent", 0.03)  # Банк дээрэмд илүү өндөр хувь
        cooldown = await self.get_cooldown(robber_id, "rob")
        if int(time.time()) < cooldown:
            await ctx.send(f"⏳ Дахин дээрэмдэхийн тулд хүлээнэ үү: {await self.format_remaining_time(cooldown - int(time.time()))}")
            return
        target_bank = await self.get_bank_balance(target_id)
        if target_bank <= 0:
            await ctx.send(f"⚠️ {target.display_name}-ын банк хоосон байна!")
            return
        stolen_amount = int(target_bank * percent)
        await self.update_bank_balance(robber_id, stolen_amount)
        await self.update_bank_balance(target_id, -stolen_amount)
        await self.update_cooldown(robber_id, "rob", cooldown_time)
        await self.add_xp(robber_id, 30)
        await ctx.send(f"🏦 {ctx.author.display_name} {target.display_name}-ын банкнаас {stolen_amount:,}₮ дээрэмдлээ!")

    # ----------------- Хак хийх команд group -----------------
    @commands.group(name='hack', invoke_without_command=True)
    async def hack(self, ctx: commands.Context, target: discord.Member) -> None:
        """
        Хэрэглэгч өөр нэгэн хэрэглэгчийг хакдах команд.
        VIP бол бага cooldown авна.
        """
        hacker_id = ctx.author.id
        target_id = target.id
        current_time = int(time.time())

        # Өөрийгөө хакдахаас сэргийлнэ
        if hacker_id == target_id:
            await ctx.send("❌ Өөрийгөө хакдах боломжгүй!")
            return

        block_cooldown = await self.get_cooldown(target_id, "block")
        if current_time < block_cooldown:
            await ctx.send(f"🛡️ **{target.display_name}** хамгаалагдсан тул хакдах боломжгүй!")
            return

        is_vip = await self.check_vip(hacker_id)
        cooldown = await self.get_cooldown(hacker_id, "hack")

        status = await self.get_user_status_data(hacker_id)
        hack_level = status.get("hack_level", 1)
        hack_config = self.get_level_config("HACK_LEVELS", hack_level)
        cooldown_time = hack_config.get("cooldown", 86400)
        success_chance = hack_config.get("success", 0.5)
        percent = hack_config.get("percent", 0.02)

        if current_time < cooldown:
            remaining_time = cooldown - current_time
            await ctx.send(f"⏳ Дахин хакдахын тулд хүлээнэ үү: {await self.format_remaining_time(remaining_time)}")
            return
        if random.uniform(0, 1) < success_chance:
            await self.update_cooldown(hacker_id, "hack", cooldown_time)
            await ctx.send(f"⏳ Хак эхэллээ, 1 минутын дараа хакдах болно!")
            asyncio.create_task(self.hack_with_delay(ctx, hacker_id, target_id, percent))
            await self.add_xp(hacker_id, 25)
        else:
            await self.update_cooldown(hacker_id, "hack", cooldown_time)
            # Амжилтгүй бол торгууль төлнө
            hacker_balance = await self.get_balance(hacker_id)
            penalty = max(int(hacker_balance * 0.1), 1000)  # Хамгийн багадаа 1000₮
            penalty = min(penalty, hacker_balance)  # Үлдэгдлээс ихгүй
            await self.update_balance(hacker_id, -penalty)
            await ctx.send(f"❌ Хак амжилтгүй боллоо, та **{penalty:,}₮** торгууль төлсөн!")
            await self.add_xp(hacker_id, 5)

    @hack.command(name='save')
    async def hack_save(self, ctx: commands.Context, target: discord.Member) -> None:
        """
        Хэрэглэгч банкны хадгаламжийг хакдах команд (!hack save @user)
        20 түвшинээс дээш хэрэглэгчид зөвхөн боломжтой
        """
        hacker_id, target_id = ctx.author.id, target.id
        current_time = int(time.time())

        # Өөрийгөө хакдахаас сэргийлнэ
        if hacker_id == target_id:
            await ctx.send("❌ Өөрийгөө хакдах боломжгүй!")
            return

        # Хамгаалалт шалгах
        block_cooldown = await self.get_cooldown(target_id, "block")
        if current_time < block_cooldown:
            await ctx.send(f"🛡️ **{target.display_name}** хамгаалагдсан тул хакдах боломжгүй!")
            return
        
        # 20 түвшин шаардлага шалгах
        status = await self.get_user_status_data(hacker_id)
        hack_level = status.get("hack_level", 1)
        
        if hack_level < 20:
            await ctx.send(f"❌ **Hack Save** командыг ашиглахын тулд та дор хаяж **20 hack level**-тэй байх ёстой! (Таны одоогийн hack level: {hack_level})")
            return
        
        hack_config = self.get_level_config("HACK_LEVELS", hack_level)
        cooldown_time = hack_config.get("cooldown", 86400)
        percent = hack_config.get("percent", 0.03)  # Хадгаламж хакдах хувь
        cooldown = await self.get_cooldown(hacker_id, "hack")
        
        if current_time < cooldown:
            await ctx.send(f"⏳ Дахин хакдахын тулд хүлээнэ үү: {await self.format_remaining_time(cooldown - current_time)}")
            return
            
        # Банк хак эхлүүлэх (1 минутын delay-тай)
        await self.update_cooldown(hacker_id, "hack", cooldown_time)
        await ctx.send(f"⏳ Банк хак эхэллээ, 1 минутын дараа хакдах болно!")
        asyncio.create_task(self.hack_bank_with_delay(ctx, hacker_id, target_id, percent))
        await self.add_xp(hacker_id, 40)

    @commands.command(name='block')
    async def block(self, ctx: commands.Context) -> None:
        """
        Хэрэглэгч өөрийгөө 5 цаг хамгаалах команд.
        """
        user_id = ctx.author.id
        current_time = int(time.time())
        block_until = await self.get_cooldown(user_id, "block")

        if current_time < block_until:
            await ctx.send(f"⏳ Та блок хийсэн байна! Үлдсэн хугацаа: {await self.format_remaining_time(block_until - current_time)}")
            return
        await self.update_cooldown(user_id, "block", 18000)
        await ctx.send(f"🛡️ {ctx.author.display_name} 5 цаг турш хамгаалагдлаа!")

    @commands.command(name='status')
    async def status(self, ctx: commands.Context, member: Optional[discord.abc.User] = None) -> None:
        """
        Хэрэглэгчийн статусын мэдээллийг embed хэлбэрээр харуулна.
        Жишээ: !status - өөрийн статус
        Жишээ: !status @user - бусад хэрэглэгчийн статус
        """
        target_member = member if member else ctx.author
        status = await self.get_user_status_data(target_member.id)
        embed = await self.make_status_embed(ctx, status, target_member)
        await ctx.send(embed=embed)

    @commands.command(name='resetcooldown')
    @commands.is_owner()
    async def reset_cooldown(self, ctx: commands.Context, user: discord.User, cooldown_type: Optional[str] = None) -> None:
        """
        Ботын эзэн хэрэглэгчийн cooldown-уудыг reset хийх команд.
        Жишээ: !resetcooldown @user hack
        Жишээ: !resetcooldown @user (бүх cooldown-уудыг reset хийнэ)
        """
        user_id = user.id
        
        if cooldown_type and cooldown_type.lower() not in ['hack', 'rob', 'block']:
            await ctx.send("❌ Зөвшөөрөгдсөн cooldown төрлүүд: `hack`, `rob`, `block`")
            return
        
        if self.conn is None:
            await ctx.send("❌ Өгөгдлийн санд холбогдох боломжгүй!")
            return
        
        try:
            if cooldown_type:
                # Тодорхой нэг cooldown reset хийх
                cooldown_column = f"{cooldown_type.lower()}_cooldown"
                await self.conn.execute(f"""
                    INSERT INTO job_cooldowns (user_id, {cooldown_column}) 
                    VALUES (?, 0) 
                    ON CONFLICT(user_id) DO UPDATE SET {cooldown_column} = 0
                """, (user_id,))
                await self.conn.commit()
                
                embed = discord.Embed(
                    title="✅ Cooldown Reset хийгдлээ",
                    description=f"**{user.display_name}**-ын **{cooldown_type}** cooldown reset хийгдлээ!",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
                
                # Хэрэглэгчид DM илгээх
                try:
                    await user.send(f"✅ Таны **{cooldown_type}** cooldown ботын эзнээр reset хийгдлээ!")
                except:
                    pass
                    
            else:
                # Бүх cooldown-уудыг reset хийх
                await self.conn.execute("""
                    INSERT INTO job_cooldowns (user_id, hack_cooldown, rob_cooldown, block_cooldown) 
                    VALUES (?, 0, 0, 0) 
                    ON CONFLICT(user_id) DO UPDATE SET 
                        hack_cooldown = 0,
                        rob_cooldown = 0,
                        block_cooldown = 0
                """, (user_id,))
                await self.conn.commit()
                
                embed = discord.Embed(
                    title="✅ Бүх Cooldown Reset хийгдлээ",
                    description=f"**{user.display_name}**-ын бүх cooldown-ууд (hack, rob, block) reset хийгдлээ!",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
                
                # Хэрэглэгчид DM илгээх
                try:
                    await user.send("✅ Таны бүх cooldown-ууд (hack, rob, block) ботын эзнээр reset хийгдлээ!")
                except:
                    pass
                    
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: {str(e)}")

    @commands.command(name='levelup')
    @commands.is_owner()
    async def level_up_command(self, ctx: commands.Context, user: discord.User, level_type: str = "level", amount: int = 1) -> None:
        """
        Ботын эзэн хэрэглэгчийн level-ийг нэмэгдүүлэх команд.
        Жишээ: !levelup @user level 5
        Жишээ: !levelup @user rob_level 2
        """
        user_id = user.id
        
        valid_types = ["level", "rob_level", "hack_level"]
        if level_type not in valid_types:
            await ctx.send(f"❌ Зөвшөөрөгдсөн level төрлүүд: `{', '.join(valid_types)}`")
            return
        
        if amount < 1 or amount > 50:
            await ctx.send("❌ Level нэмэгдүүлэх хэмжээ 1-50 хооронд байх ёстой!")
            return
        
        if self.conn is None:
            await ctx.send("❌ Өгөгдлийн санд холбогдох боломжгүй!")
            return
        
        try:
            # Хэрэглэгчийн бичлэг байгаа эсэхийг шалгах
            await self.conn.execute("""
                INSERT OR IGNORE INTO job (user_id, level, rob_level, hack_level, xp, vip_expiry) 
                VALUES (?, 1, 1, 1, 0, 0)
            """, (user_id,))
            
            # Одоогийн level авах
            async with self.conn.execute(f"SELECT {level_type} FROM job WHERE user_id=?", (user_id,)) as cursor:
                row = await cursor.fetchone()
            current_level = row[0] if row and row[0] is not None else 1
            
            # Level нэмэгдүүлэх
            new_level = current_level + amount
            await self.conn.execute(f"""
                UPDATE job SET {level_type} = ? WHERE user_id = ?
            """, (new_level, user_id))
            await self.conn.commit()
            
            embed = discord.Embed(
                title="⭐ Level нэмэгдлээ!",
                description=f"**{user.display_name}**-ын **{level_type}** {current_level} → {new_level} боллоо!",
                color=discord.Color.green()
            )
            embed.add_field(name="Нэмэгдсэн хэмжээ", value=f"+{amount} level", inline=True)
            embed.add_field(name="Шинэ зэрэглэл", value=f"{self.get_rank_emoji(new_level)} {self.get_rank_name(new_level)}", inline=True)
            
            await ctx.send(embed=embed)
            
            # Хэрэглэгчид DM илгээх
            try:
                await user.send(f"🎉 Таны **{level_type}** {amount} түвшинээр нэмэгдэж {new_level} боллоо! Ботын эзэн танд энэ урамшууллыг өгсөн байна!")
            except:
                pass
                    
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: {str(e)}")

    @commands.command(name='addxp')
    @commands.is_owner()
    async def add_xp_command(self, ctx: commands.Context, user: discord.User, amount: int = 100) -> None:
        """
        Ботын эзэн хэрэглэгчид XP нэмэх команд.
        Жишээ: !addxp @user 500
        """
        user_id = user.id
        
        if amount < 1 or amount > 10000:
            await ctx.send("❌ XP нэмэгдүүлэх хэмжээ 1-10000 хооронд байх ёстой!")
            return
        
        try:
            old_status = await self.get_user_status_data(user_id)
            old_level = old_status["level"]
            
            await self.add_xp(user_id, amount)
            
            new_status = await self.get_user_status_data(user_id)
            new_level = new_status["level"]
            
            embed = discord.Embed(
                title="✨ XP нэмэгдлээ!",
                description=f"**{user.display_name}**-д **{amount:,} XP** нэмэгдлээ!",
                color=discord.Color.blue()
            )
            embed.add_field(name="Одоогийн XP", value=f"{new_status['xp']:,}", inline=True)
            
            if new_level > old_level:
                level_increase = new_level - old_level
                embed.add_field(name="🎉 Level өсөв!", value=f"+{level_increase} level (Level {new_level})", inline=True)
                embed.color = discord.Color.gold()
            
            await ctx.send(embed=embed)
                    
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: {str(e)}")

    @commands.command(name='rank')
    async def leaderboards(self, ctx: commands.Context, category: str = "level") -> None:
        """
        Тэргүүлэгчдийн жагсаалт харуулах команд.
        Жишээ: !leaderboards level
        Жишээ: !rank balance
        Жишээ: !lb xp
        """
        valid_categories = ["level", "balance", "bank", "rob_level", "hack_level", "xp"]
        
        if category not in valid_categories:
            await ctx.send(f"❌ Зөвшөөрөгдсөн категориуд: `{', '.join(valid_categories)}`")
            return
        
        if self.conn is None:
            await ctx.send("❌ Өгөгдлийн санд холбогдох боломжгүй!")
            return
        
        try:
            # Категорийн дагуу query бэлтгэх
            if category in ["level", "rob_level", "hack_level", "xp"]:
                # job хүснэгтээс
                query = f"""
                    SELECT user_id, {category} FROM job 
                    WHERE {category} > 0 
                    ORDER BY {category} DESC 
                    LIMIT 10
                """
            elif category == "balance":
                # economy хүснэгтээс
                query = """
                    SELECT user_id, balance FROM economy 
                    WHERE balance > 0 
                    ORDER BY balance DESC 
                    LIMIT 10
                """
            else:  # bank
                # bank хүснэгтээс
                query = """
                    SELECT user_id, balance FROM bank 
                    WHERE balance > 0 
                    ORDER BY balance DESC 
                    LIMIT 10
                """
            
            async with self.conn.execute(query) as cursor:
                results = await cursor.fetchall()
            
            if not results:
                await ctx.send(f"❌ {category} категорид мэдээлэл байхгүй байна!")
                return
            
            results_list = list(results)  # Convert to list for len() function
            
            # Embed үүсгэх
            category_names = {
                "level": "Түвшин",
                "balance": "Халаасны мөнгө", 
                "bank": "Банкны мөнгө",
                "rob_level": "Роб түвшин",
                "hack_level": "Хак түвшин",
                "xp": "Туршлагын оноо"
            }
            
            category_emojis = {
                "level": "⭐",
                "balance": "💸",
                "bank": "🏦", 
                "rob_level": "🤺",
                "hack_level": "💻",
                "xp": "✨"
            }
            
            embed = discord.Embed(
                title=f"{category_emojis.get(category, '🏆')} {category_names.get(category, category)} - Тэргүүлэгчид",
                description="Top 10 хэрэглэгчдийн жагсаалт",
                color=discord.Color.gold()
            )
            
            leaderboard_text = ""
            for i, (user_id, value) in enumerate(results_list, 1):
                user = ctx.bot.get_user(user_id)
                username = user.display_name if user else f"User#{user_id}"
                
                # Medal emoji
                if i == 1:
                    medal = "🥇"
                elif i == 2:
                    medal = "🥈"
                elif i == 3:
                    medal = "🥉"
                else:
                    medal = f"{i}."
                
                # Value форматлах
                if category in ["balance", "bank"]:
                    formatted_value = f"{value:,}₮"
                elif category == "xp":
                    formatted_value = f"{value:,} XP"
                else:
                    formatted_value = f"Level {value}"
                
                leaderboard_text += f"{medal} **{username}** - {formatted_value}\n"
            
            embed.add_field(
                name=f"🏆 Top 10 - {category_names.get(category, category)}",
                value=leaderboard_text,
                inline=False
            )
            
            embed.set_footer(text=f"MongolBot Economy • Серверт нийт {len(results_list)} хэрэглэгч бүртгэлтэй")
            
            await ctx.send(embed=embed)
                    
        except Exception as e:
            await ctx.send(f"❌ Алдаа гарлаа: {str(e)}")

    @commands.command(name='levelinfo', aliases=['li'])
    async def level_info_alias(self, ctx: commands.Context, member: Optional[discord.abc.User] = None) -> None:
        """
        !status detailed командын товч хэлбэр - дэлгэрэнгүй level мэдээлэл
        """
        # Manually parse arguments to simulate detailed=True
        args = ctx.message.content.split()[1:]  # Remove !levelinfo part
        target_member = member if member else ctx.author
        
        # Get user data
        status = await self.get_user_status_data(target_member.id)
        requirements = await self.get_next_level_requirements(target_member.id)
        
        embed = discord.Embed(
            title=f"📈 {target_member.display_name} - Дэлгэрэнгүй статус",
            color=discord.Color.blue()
        )
        
        if hasattr(target_member, 'display_avatar') and target_member.display_avatar:
            embed.set_thumbnail(url=target_member.display_avatar.url)
        
        # Main Level мэдээлэл
        current_level = status["level"]
        current_xp = status["xp"]
        xp_for_next = requirements["xp_for_next_level"]
        xp_needed = requirements["xp_needed_for_level"]
        
        embed.add_field(
            name="⭐ Main Level",
            value=f"**Одоогийн түвшин:** {current_level}\n"
                  f"**Одоогийн XP:** {current_xp:,}\n"
                  f"**Дараагийн level:** {current_level + 1}\n"
                  f"**Шаардагдах XP:** {xp_needed:,}\n"
                  f"**Нийт XP:** {xp_for_next:,}",
            inline=False
        )
        
        # Rob Level мэдээлэл
        rob_level = status["rob_level"]
        rob_xp_needed = requirements["xp_needed_for_rob"]
        
        embed.add_field(
            name="🤺 Rob Level",
            value=f"**Одоогийн түвшин:** {rob_level}\n"
                  f"**Одоогийн XP:** {current_xp:,}\n"
                  f"**Дараагийн level:** {rob_level + 1 if rob_xp_needed > 0 else 'MAX'}\n"
                  f"**Шаардагдах XP:** {rob_xp_needed:,} ({'MAX' if rob_xp_needed == 0 else 'XP'})",
            inline=True
        )
        
        # Hack Level мэдээлэл
        hack_level = status["hack_level"]
        hack_xp_needed = requirements["xp_needed_for_hack"]
        
        embed.add_field(
            name="💻 Hack Level",
            value=f"**Одоогийн түвшин:** {hack_level}\n"
                  f"**Одоогийн XP:** {current_xp:,}\n"
                  f"**Дараагийн level:** {hack_level + 1 if hack_xp_needed > 0 else 'MAX'}\n"
                  f"**Шаардагдах XP:** {hack_xp_needed:,} ({'MAX' if hack_xp_needed == 0 else 'XP'})",
            inline=True
        )
        
        # Level тохиргоо мэдээлэл
        rob_config = self.get_level_config("ROB_LEVELS", rob_level)
        hack_config = self.get_level_config("HACK_LEVELS", hack_level)
        
        embed.add_field(
            name="⚙️ Одоогийн тохиргоо",
            value=f"**Rob:** {rob_config.get('success', 0.5)*100:.0f}% амжилт, {rob_config.get('percent', 0.02)*100:.1f}% хулгай\n"
                  f"**Hack:** {hack_config.get('success', 0.5)*100:.0f}% амжилт, {hack_config.get('percent', 0.02)*100:.1f}% хулгай\n"
                  f"**Rob Cooldown:** {rob_config.get('cooldown', 3600)//60} мин\n"
                  f"**Hack Cooldown:** {hack_config.get('cooldown', 86400)//3600} цаг",
            inline=False
        )
        
        embed.set_footer(text=f"XP систем: Main Level +20 XP/level, Rob +200 XP/level (max 30), Hack +250 XP/level (max 30)")
        
        await ctx.send(embed=embed)

    async def cog_unload(self) -> None:
        """
        Cog ачаалалгүй болох үед өгөгдлийн сангийн холболтыг хаана.
        """
        if self.conn:
            await self.conn.close()

async def setup(bot: commands.Bot) -> None:
    """
    Bot дээр энэхүү Cog-ийг ачаална.
    """
    await bot.add_cog(Job(bot))