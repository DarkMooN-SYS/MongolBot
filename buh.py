import random
import asyncio
import sqlite3
import discord
from discord.ext import commands
from datetime import datetime, timedelta

# Өгөгдлийн сан холбох
def get_db_connection():
    return sqlite3.connect("buh.db")

with get_db_connection() as conn:
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS wrestlers (
        user_id INTEGER PRIMARY KEY,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0,
        rest BOOLEAN DEFAULT 0,
        win_streak INTEGER DEFAULT 0,
        rest_until TEXT DEFAULT NULL
    )''')
    conn.commit()

ranks = [
    (30, "Даян аварга"),
    (20, "Улсын гарьд"),
    (10, "Аймгийн арслан"),
    (5, "Сумын заан")
]

class Buh(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_resting(self, user_id):
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT rest_until FROM wrestlers WHERE user_id = ?", (user_id,))
            rest_until = c.fetchone()[0]
            if rest_until is None:
                return False
            rest_until_time = datetime.fromisoformat(rest_until)
            if datetime.now() >= rest_until_time:
                # Хугацаа дууссан бол амралтыг цуцална
                c.execute("UPDATE wrestlers SET rest_until = NULL WHERE user_id = ?", (user_id,))
                conn.commit()
                return False
            return True

    async def cog_check(self, ctx):
        allowed_guild_ids = [1312484212150108232]  # Зөвшөөрөгдсөн серверийн ID
        if ctx.guild.id not in allowed_guild_ids:
            await ctx.send("⛔ Энэ команд зөвхөн тусгай зөвшөөрөлтэй сервер дээр ажиллана!")
            return False
        return True

    @commands.command(name="buhchallenge")
    async def buhchallenge(self, ctx, opponent: discord.Member):
        user = ctx.author
        if user == opponent:
            await ctx.send("⚠️ Өөртэйгөө барилдаж болохгүй!")
            return

        with get_db_connection() as conn:
            c = conn.cursor()
            for member in (user, opponent):
                c.execute("INSERT OR IGNORE INTO wrestlers (user_id) VALUES (?)", (member.id,))

        if self.is_resting(user.id):
            await ctx.send(f"⚠️ {user.mention} та одоогоор амарч байна!")
            return
        if self.is_resting(opponent.id):
            await ctx.send(f"⚠️ {opponent.mention} одоогоор амарч байна!")
            return

        await ctx.send(f"🤼‍♂️ {user.mention} vs {opponent.mention} - Барилдаан эхэллээ!")

        winner, loser = random.sample([user, opponent], 2)

        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE wrestlers SET wins = wins + 1, win_streak = win_streak + 1 WHERE user_id = ?", (winner.id,))
            c.execute("UPDATE wrestlers SET losses = losses + 1, win_streak = 0 WHERE user_id = ?", (loser.id,))
            
            # Ялагдсан бөхийг 1 цаг амраана
            rest_until = datetime.now() + timedelta(hours=1)
            c.execute("UPDATE wrestlers SET rest_until = ? WHERE user_id = ?", (rest_until.isoformat(), loser.id))

            c.execute("SELECT wins FROM wrestlers WHERE user_id = ?", (winner.id,))
            wins = c.fetchone()[0]
            conn.commit()

        # Шинэ цол олгох эсэхийг шалгах
        new_rank = None
        for win_count, rank_name in ranks:
            if wins == win_count:
                new_rank = rank_name
                break

        embed = discord.Embed(
            title="🤼‍♂️ Бөхийн барилдаан дууслаа!",
            color=discord.Color.gold()
        )
        embed.add_field(name="🥇 Ялагч", value=winner.mention, inline=True)
        embed.add_field(name="😞 Ялагдагч", value=loser.mention, inline=True)
        embed.add_field(name="⏳ Амралт", value="1 цаг амарна", inline=False)

        if new_rank:
            role = discord.utils.get(ctx.guild.roles, name=new_rank)
            if not role:
                role = await ctx.guild.create_role(name=new_rank)
            await winner.add_roles(role)

            old_ranks = [r[1] for r in ranks if r[1] != new_rank]
            for old_rank in old_ranks:
                old_role = discord.utils.get(ctx.guild.roles, name=old_rank)
                if old_role and old_role in winner.roles:
                    await winner.remove_roles(old_role)

            embed.add_field(name="🎉 Шинэ цол", value=f"**{new_rank}**", inline=False)

        await ctx.send(embed=embed)

    @commands.command(name="buhleaderboard")
    async def buhleaderboard(self, ctx):
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT user_id, wins, losses, win_streak FROM wrestlers ORDER BY wins DESC, win_streak DESC")
            wrestlers = c.fetchall()

        if not wrestlers:
            await ctx.send("Одоогоор бөхчүүдийн мэдээлэл алга.")
            return

        embed = discord.Embed(title="🏆 Бөхчүүдийн чансаа", color=discord.Color.gold())
        for idx, (user_id, wins, losses, streak) in enumerate(wrestlers, start=1):
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"Хэрэглэгч-{user_id}"
            embed.add_field(
                name=f"#{idx} {name}",
                value=f"🏅 Хожил: {wins} | ❌ Ялагдал: {losses} | 🔥 Streak: {streak}",
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.command(name="buhreset")
    @commands.has_permissions(administrator=True)  # Only allow admins to use this command
    async def buhreset(self, ctx):
        """Бүх бөхчүүдийг амралтаас гаргах (нэг бүрчлэн биш, бүгдийг нэг дор)"""
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE wrestlers SET rest = 0")
            conn.commit()
        await ctx.send("✅ **Бүх бөхчүүдийн амралтыг цуцаллаа!** Одоо бүгд дахин барилдаж болно.")
        
    @commands.command(name="bituuniibuh")
    @commands.has_permissions(administrator=True)  # Only allow admins to use this command
    async def bituuniibuh(self, ctx):
        """Битүүний бөхийн барилдаан - Реакц дарж бүртгүүлэх хувилбар"""

        today = datetime.now()
        if today.month != 2 or today.day != 28:  # Битүүний өдөр тохируулах
            await ctx.send("⛔ Энэ команд зөвхөн **Битүүний өдөр** ажиллана!")
            return

        message = await ctx.send(
            "🏅 **Битүүний бөхийн барилдаан** эхэлж байна!\n"
            "Оролцохыг хүсвэл доорх `✅` тэмдэг дээр дарна уу.\n"
            "⏳ Бүртгэл 60 секунд үргэлжилнэ."
        )
        await message.add_reaction("✅")

        participants = []

        def check(reaction, user):
            return (
                user != self.bot.user
                and str(reaction.emoji) == "✅"
                and reaction.message.id == message.id
            )

        try:
            while True:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
                if user not in participants:
                    participants.append(user)
                    await ctx.send(f"{user.mention} амжилт хүсье! Та амжилттай бүртгүүллээ.")
        except asyncio.TimeoutError:
            if len(participants) < 2:
                await ctx.send("⚠️ Бүртгүүлсэн хүмүүс хэт цөөхөн байна. Барилдаан цуцлагдлаа.")
                return

        await ctx.send(f"✅ **Битүүний бөхийн барилдаан албан ёсоор эхэллээ!** ({len(participants)} бөх бүртгэгдсэн)")

        while len(participants) > 1:
            random.shuffle(participants)
            next_round = []
            for i in range(0, len(participants), 2):
                if i + 1 >= len(participants):
                    next_round.append(participants[i])
                    continue
                user1, user2 = participants[i], participants[i + 1]
                await ctx.send(f"🤼 {user1.mention} vs {user2.mention}")
                winner = random.choice([user1, user2])
                next_round.append(winner)
                await asyncio.sleep(2)
                await ctx.send(f"🏅 {winner.mention} дараагийн шатанд шалгарлаа!")
            participants = next_round

        final_winner = participants[0]
        role = discord.utils.get(ctx.guild.roles, name="Битүүний аварга")
        if not role:
            role = await ctx.guild.create_role(name="Битүүний аварга")
        await final_winner.add_roles(role)

        await ctx.send(f"🏆 **{final_winner.mention}** нь энэ жилийн **Битүүний аварга** боллоо! 🎉")

async def setup(bot):
    await bot.add_cog(Buh(bot))