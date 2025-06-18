import discord
from discord.ext import commands
import random
import asyncio

class Buh(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.matches = {}

    @commands.command(name='buh')
    async def buh(self, ctx, opponent: discord.Member = None):
        """Бөхийн барилдаан эхлүүлэх"""
        if opponent is None:
            await ctx.send("⚠️ Та өрсөлдөх хүнээ сонгоно уу!\nЖишээ: `mbuh @username`")
            return
            
        if opponent.bot:
            await ctx.send("⚠️ Та боттой барилдах боломжгүй!")
            return
            
        if opponent == ctx.author:
            await ctx.send("⚠️ Та өөртэйгөө барилдах боломжгүй!")
            return

        if ctx.channel.id in self.matches:
            await ctx.send("⚠️ Энэ суваг дээр аль хэдийн барилдаан явагдаж байна!")
            return

        # Урилга үүсгэх
        embed = discord.Embed(
            title="🤼 Бөхийн барилдаан",
            description=f"{opponent.mention}, {ctx.author.mention} тантай барилдахыг урьж байна!\n"
                      "Хүлээн авах бол ✅ дээр дарна уу.",
            color=discord.Color.blue()
        )
        
        invite = await ctx.send(embed=embed)
        await invite.add_reaction("✅")

        def check(reaction, user):
            return user == opponent and str(reaction.emoji) == "✅"

        try:
            await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("⌛ Хугацаа дууслаа! Барилдаан цуцлагдлаа.")
            return

        # Барилдаан эхлүүлэх
        self.matches[ctx.channel.id] = True
        
        wrestlers = [ctx.author, opponent]
        moves = ["барилдлаа", "өргөлөө", "давж орлоо", "хаялаа"]
        health = {ctx.author.id: 100, opponent.id: 100}

        # Барилдааны мэдээлэл
        match_embed = discord.Embed(
            title="🤼 Бөхийн барилдаан эхэллээ!",
            description=f"**{ctx.author.display_name}** vs **{opponent.display_name}**\n"
                      f"Үлдсэн амь: 100 | 100",
            color=discord.Color.green()
        )
        match_msg = await ctx.send(embed=match_embed)

        # Барилдааны үндсэн давталт
        while True:
            attacker = random.choice(wrestlers)
            defender = next(w for w in wrestlers if w != attacker)
            
            move = random.choice(moves)
            damage = random.randint(10, 30)
            
            health[defender.id] -= damage

            match_embed.description = (
                f"**{attacker.display_name}** {move}!\n"
                f"**{defender.display_name}** {damage} өвтгөлөө.\n\n"
                f"🔴 {ctx.author.display_name}: {health[ctx.author.id]}\n"
                f"🔵 {opponent.display_name}: {health[opponent.id]}"
            )
            
            await match_msg.edit(embed=match_embed)
            await asyncio.sleep(2)

            if health[defender.id] <= 0:
                match_embed.description = f"🏆 **{attacker.display_name}** ялалт байгууллаа!"
                match_embed.color = discord.Color.gold()
                await match_msg.edit(embed=match_embed)
                break

        del self.matches[ctx.channel.id]

async def setup(bot):
    await bot.add_cog(Buh(bot))