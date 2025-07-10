import discord
from discord import app_commands
from discord.ext import commands
import random
from ..utils.channel import is_channel_enabled

class fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
            
    @commands.command(name="roll", help="1-с тодорхой тоо хүртэл санамсаргүй тоо шиднэ (анхдагч: 6).")
    async def roll(self, ctx: commands.Context, max_number: int = 6):
        if max_number < 1:
            await ctx.send("Хамгийн их тоо 1-ээс их байх ёстой.")
            return
        
        result = random.randint(1, max_number)
        await ctx.send(f"🎲 {ctx.author.mention} **1**-ээс **{max_number}** хүртэлх тоо\n **{result}** гэсэн тоог буулгасан!")

    def cog_check(self, ctx: commands.Context) -> bool:
        # Only allow commands in guilds; channel enable check must be async elsewhere
        if not ctx.guild:
            return False
        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        # Async channel check here
        if ctx.guild is None or not await is_channel_enabled(ctx.guild.id, ctx.channel.id):
            await ctx.send("Энэ channel-д команд ашиглах боломжгүй!")
            raise commands.CheckFailure("Channel not enabled for commands.")

# To add the cog to your bot
async def setup(bot: commands.Bot):
    await bot.add_cog(fun(bot))
