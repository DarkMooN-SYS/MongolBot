import discord
from discord.ext import commands
from discord import app_commands

# HelpSelect класс: Сонголттой интерактив элемент
class HelpSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Тусламжийн ангилал сонгох", options=options)

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        embed = discord.Embed(color=0x00ff00)

        if category == "Эдийн засаг":
            embed.title = "💸 Эдийн засгийн командууд"
            embed.description = "Эдийн засгийн холбогдолтой командуудын жагсаалт:"
            commands = [
                ("`balance` эсвэл `bal`", "Таны халаасандах мөнгийг харуулах."),
                ("`give`", "@user-д мөнгө өгөх."),
                ("`top`", "TOP 5 хэрэглэгчдийн жагсаалт."),
                ("`daily`", "Өдрийн шагналаа авах."),
            ]
            
        elif category == "Мөрийтэй тоглоом":
            embed.title = "🎮 Мөрийтэй тоглоомын командууд"
            embed.description = "Тоглоомын командуудын жагсаалт:"
            commands = [
                ("`bank`", "Дансны Мэдээлэл."),
                ("`coinflip - cf`", "Зоос шидэх мөрийт тоглоом."),
                ("`roulette - r`", "Рулет тоглоомд мөрий тавих."),
                ("`slots - s`", "🎰 **Slot Machine** – Бооцоо тавиад азаа үзээрэй!"),
                ("`minefield - mf`", "Бөмбөгнөөс зайлсхийж шагнал авах")
            ]

        elif category == "VIP":
            embed.title = "👑 VIP командууд"
            embed.description = "VIP командуудын жагсаалт:"
            commands = [
                ("`vip`", "VIP эрх авах."),
                ("`giftvip`", "VIP эрх бэлэглэх."),
                ("`viptop`", "VIP TOP 5 хэрэглэгчд."),
                ("`buyvip`", "VIP худалдаж авах."),
                ("`dailyvip`", "VIP Өдрийн шагналаа авах.")
            ]

        elif category == "Бусад":
            embed.title = "🤔 Бусад командууд"
            embed.description = "Бусад төрлийн командуудын жагсаалт:"
            commands = [
                ("`help`", "Тусламжийн команд."),
                ("`dm`", "@user эсвэл #channel руу мессеж илгээх."),
                ("`roll`", "Шоо шидэх."),
                ("`support`", "Асуудал гарсан уу?")
            ]

        elif category == "Бүгд":
            embed.title = "📚 Бүх командуудын жагсаалт"
            embed.description = "Бүх боломжит командууд:"
            commands = [
                ("`bank`", "Дансны Мэдээлэл."),
                ("`balance` эсвэл `bal`", "Таны халаасандах мөнгийг харуулах."),
                ("`give`", "@user-д мөнгө өгөх."),
                ("`top`", "TOP 5 хэрэглэгчдийн жагсаалт."),
                ("`daily`", "Өдрийн шагналаа авах."),
                ("`coinflip - cf`", "Зоос шидэх мөрийт тоглоом."),
                ("`roulette - r`", "Рулет тоглоомд мөрий тавих."),
                ("`slots, s`", "🎰 **Slot Machine** – Бооцоо тавиад азаа үзээрэй!"),
                ("`minefield - mf`", "Бөмбөгнөөс зайлсхийж шагнал авах"),
                ("`help`", "Тусламжийн команд."),
                ("`dm`", "@user эсвэл #channel руу мессеж илгээх."),
                ("`roll`", "Шоо шидэх."),
                ("`vip`", "VIP эрх авах."),
                ("`giftvip`", "VIP эрх бэлэглэх."),
                ("`viptop`", "VIP TOP 5 хэрэглэгчд."),
                ("`buyvip`", "VIP худалдаж авах."),
                ("`dailyvip`", "VIP Өдрийн шагналаа авах."),
                ("`support`", "Асуудал гарсан уу?")
            ]

        elif category == "Админ":
            embed.title = "🔒 Админ командууд"
            embed.description = "Зөвхөн админ эрхтэй хэрэглэгчдийн ашиглах командууд:"
            commands = [
                ("`kick`", "Хэрэглэгчийг серверээс гаргах."),
                ("`ban`", "Хэрэглэгчийг серверээс хасах.")
            ]

        for name, value in commands:
            embed.add_field(name=name, value=value, inline=False)

        await interaction.response.edit_message(embed=embed)

# HelpView класс: Сонголтын UI-г бүрдүүлэх
class HelpView(discord.ui.View):
    def __init__(self, options):
        super().__init__()
        self.add_item(HelpSelect(options))

# Тусламжийн үндсэн embed илгээх функц
async def send_help_embed(ctx_or_interaction):
    embed = discord.Embed(
        title="📖 Тусламжийн командууд",
        description="Доорх командуудын ангиллаас сонгон дэлгэрэнгүй мэдээлэл аваарай.",
        color=0x00ff00
    )
    embed.add_field(name="💸 Эдийн засаг", value="Эдийн засгийн командууд", inline=False)
    embed.add_field(name="🎮 Мөрийтэй тоглоом", value="Тоглоомын командууд", inline=False)
    embed.add_field(name="👑 VIP", value="VIP командууд", inline=False)
    embed.add_field(name="🤔 Бусад", value="Бусад командууд", inline=False)
    embed.add_field(name="📚 Бүгд", value="Бүх командуудын жагсаалт", inline=False)

    options = [
        discord.SelectOption(label="Эдийн засаг", description="Эдийн засгийн командууд", emoji="💸"),
        discord.SelectOption(label="Мөрийтэй тоглоом", description="Тоглоомын командууд", emoji="🎮"),
        discord.SelectOption(label="VIP", description="VIP командууд", emoji="👑"),
        discord.SelectOption(label="Бусад", description="Бусад командууд", emoji="🤔"),
        discord.SelectOption(label="Бүгд", description="Бүх командуудын жагсаалт", emoji="📚")
    ]

    if hasattr(ctx_or_interaction, "user") and ctx_or_interaction.user.guild_permissions.administrator:
        embed.add_field(name="🔒 Админ", value="Админ командууд", inline=False)
        options.append(discord.SelectOption(label="Админ", description="Админ командууд", emoji="🔒"))

    return embed, options


# Help ког: Help командын логик
class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_command(self, ctx):
        """!help команд"""
        embed, options = await send_help_embed(ctx)
        await ctx.send(embed=embed, view=HelpView(options))

    @app_commands.command(name="help", description="Тусламжийн мэдээлэл авах")
    async def help_slash(self, interaction: discord.Interaction):
        """Slash команд /help"""
        embed, options = await send_help_embed(interaction)
        await interaction.response.send_message(embed=embed, view=HelpView(options))

# Cog-г идвэхжүүлэх
async def setup(bot):
    await bot.add_cog(Help(bot))