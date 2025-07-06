import discord
from discord.ext import commands
from discord.ext.commands import Context
import asyncio
from .profile_db import ProfileDB
from typing import Optional, Any

class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_participants = set()
        self.voice_task = self.bot.loop.create_task(self.voice_xp_loop())
        self.db = ProfileDB(self.bot)
        # Profile customization
        self.profile_settings = {}  # {user_id: {"color": int, "banner": str, ...}}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        uid = message.author.id
        profile = await self.db.get_profile(uid)
        xp = profile['xp'] + 5
        lvl = profile['level']
        msg_count = profile.get('msg_count', 0) + 1  # Increment message count
        level_up = False
        reward = 0
        if xp >= lvl * 100:
            lvl += 1
            level_up = True
            # Level reward logic
            reward = lvl * 1000  # Жишээ: level бүрд 1000₮ * level
        await self.db.update_profile(uid, xp=xp, level=lvl)  # Save XP and level
        if level_up:
            await message.channel.send(f"{message.author.mention} Level up! {lvl}-р түвшинд хүрлээ! Шагнал: {reward}₮")
            # Энд мөнгө нэмэх database update-г хийж болно

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return
        if after.channel and (before.channel != after.channel):
            self.voice_participants.add(member.id)
        elif not after.channel:
            self.voice_participants.discard(member.id)

    async def voice_xp_loop(self) -> None:
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            for uid in list(self.voice_participants):
                profile = await self.db.get_profile(uid)
                xp = profile['xp'] + 10
                lvl = profile['level']
                voice_min = profile.get('voice_min', 0) + 1  # Increment voice minutes
                level_up = False
                reward = 0
                if xp >= lvl * 100:
                    lvl += 1
                    level_up = True
                    reward = lvl * 1000
                # Update XP and level
                await self.db.update_profile(uid, xp=xp, level=lvl)
                # If you want to update voice_min, ensure your update_profile supports it, or update it separately:
                # await self.db.update_profile(uid, voice_min=voice_min)
            await asyncio.sleep(60)  # 1 мин тутамд XP нэмнэ

    @commands.command(name="leaderboard")
    async def leaderboard(self, ctx: Context):
        # Top 10 users by level
        if not ctx.guild:
            await ctx.send("Энэ команд зөвхөн сервер дээр ажиллана.")
            return
        if not self.db.conn:
            await ctx.send("Database холбогдоогүй байна.")
            return
        async with self.db.conn.execute('SELECT user_id, level, xp FROM profiles ORDER BY level DESC, xp DESC LIMIT 10') as cur:
            rows = await cur.fetchall()
        desc = ""
        for i, row in enumerate(rows, 1):
            user = ctx.guild.get_member(row[0]) if ctx.guild else None
            name = user.display_name if isinstance(user, discord.Member) else f"ID:{row[0]}"
            desc += f"**{i}. {name}** — Level: {row[1]}, XP: {row[2]}\n"
        embed = discord.Embed(title="🏆 Leaderboard", description=desc or "Хоосон байна.", color=discord.Color.gold())
        await ctx.send(embed=embed)

    @commands.command(name="profilesettings")
    async def profilesettings(self, ctx: Context, color: Optional[str] = None, banner: Optional[str] = None):
        uid = ctx.author.id
        if uid not in self.profile_settings:
            self.profile_settings[uid] = {}
        if color:
            try:
                self.profile_settings[uid]["color"] = int(color, 16)
            except Exception:
                await ctx.send("Өнгө буруу байна. Жишээ: ff0000")
                return
        if banner:
            self.profile_settings[uid]["banner"] = banner
        await ctx.send("Таны profile тохиргоо шинэчлэгдлээ!")

    @commands.command(name="profile", help="Таны болон бусад хэрэглэгчийн profile-г харуулна.")
    async def profile(self, ctx: Context, member: Optional[discord.Member] = None):
        """
        Хэрэглэгчийн profile, about me, мөнгө, level, XP-г embed хэлбэрээр харуулна.
        !profile [@user] хэлбэрээр ашиглана.
        """
        if member is None:
            if isinstance(ctx.author, discord.Member):
                member = ctx.author
            else:
                await ctx.send("Энэ команд зөвхөн сервер дээр ажиллана.")
                return
        uid = member.id
        profile = await self.db.get_profile(uid)
        xp = profile['xp']
        lvl = profile['level']
        about_me = profile['about'] or "Тайлбар оруулаагүй байна."
        color = self.profile_settings.get(uid, {}).get("color", discord.Color.blurple())
        banner = self.profile_settings.get(uid, {}).get("banner", None)
        # Voice болон мессеж статистик, badge, leaderboard байр
        total_voice_min = profile.get('voice_min', 0)  # DB-г өргөтгөхөд бэлэн
        total_msg = profile.get('msg_count', 0)  # DB-г өргөтгөхөд бэлэн
        badges = profile.get('badges', [])  # DB-г өргөтгөхөд бэлэн
        # Leaderboard байр
        rank = None
        if self.db.conn and ctx.guild:
            async with self.db.conn.execute('SELECT user_id FROM profiles ORDER BY level DESC, xp DESC') as cur:
                all_ids = [row[0] async for row in cur]
            if uid in all_ids:
                rank = all_ids.index(uid) + 1
        badge_str = ' '.join(badges) if badges else '—'
        desc = f"**Level:** {lvl} | **XP:** {xp}\n"
        desc += f"**Voice:** {total_voice_min} мин | **Мессеж:** {total_msg}\n"
        desc += f"**Leaderboard байр:** {rank if rank else '—'}\n"
        desc += f"**Badges:** {badge_str}"
        embed = discord.Embed(
            title=f"{member.display_name} | Профайл",
            description=desc,
            color=color
        )
        if banner:
            embed.set_image(url=banner)
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        embed.add_field(name="About Me", value=about_me, inline=False)
        embed.set_footer(text=f"ID: {member.id} | Нэр: {member}")
        embed.timestamp = member.joined_at if hasattr(member, 'joined_at') else None
        await ctx.send(embed=embed)

    @commands.command(name="profilestats", help="Таны болон бусад хэрэглэгчийн статистик мэдээллийг харуулна.")
    async def profilestats(self, ctx: Context, member: Optional[discord.Member] = None):
        """
        Хэрэглэгчийн profile статистик, about me, level, XP-г embed хэлбэрээр харуулна.
        !profilestats [@user] хэлбэрээр ашиглана.
        """
        if member is None:
            if isinstance(ctx.author, discord.Member):
                member = ctx.author
            else:
                await ctx.send("Энэ команд зөвхөн сервер дээр ажиллана.")
                return
        uid = member.id
        profile = await self.db.get_profile(uid)
        embed = discord.Embed(
            title=f"{member.display_name} | Статистик",
            description=f"**Level:** {profile['level']}\n**XP:** {profile['xp']}\n**About Me:** {profile['about'] or 'Тайлбар оруулаагүй байна.'}",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
        embed.set_footer(text=f"ID: {member.id} | Нэр: {member}")
        await ctx.send(embed=embed)

    @commands.command(name="aboutme", help="Өөрийн 'About Me' хэсгийг шинэчилнэ.")
    async def aboutme(self, ctx: Context, *, text: str):
        """
        Хэрэглэгч өөрийн 'About Me' хэсгийг шинэчилнэ.
        !aboutme <текст>
        """
        uid = ctx.author.id
        profile = await self.db.get_profile(uid)
        await self.db.update_profile(uid, xp=profile['xp'], level=profile['level'], about=text[:256])
        await ctx.send(f"Таны 'About Me' шинэчлэгдлээ!")

async def setup(bot: commands.Bot):
    await bot.add_cog(Profile(bot))
