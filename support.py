import discord
from discord.ext import commands

class Support(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="support")
    async def support(self, ctx):
        """Ботын тусламж болон албан ёсны серверүүдийн мэдээлэл"""
        embed = discord.Embed(
            title="🤖 Ботын тусламж",
            description="Доорх серверүүдээс шаардлагатай тусламжаа авна уу.",
            color=discord.Color.blue()
        )

        embed.add_field(name="📜 Командуудын жагсаалт", value="Бүх командуудыг харах бол `mhelp` гэж бичнэ үү.", inline=False)
        embed.add_field(name="🏠 Ботын үндсэн сервер", value="[Энд дарж нэгдээрэй](https://discord.gg/GnVkB37xZS)", inline=False)
        embed.add_field(name="🛠️ Тусламжийн сервер", value="[Энд дарж нэгдээрэй](https://discord.gg/9ccChND6Zz)", inline=False)
        embed.add_field(name="📩 Ботын урилга", value="[Бот нэмэх](https://discord.com/oauth2/authorize?client_id=1268983042425487472&permissions=8&integration_type=0&scope=bot)", inline=False)
        embed.set_footer(text="Хэрэв танд нэмэлт тусламж хэрэгтэй бол тусламжийн серверт нэгдээрэй!")

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Support(bot))