import discord
from typing import Union
from discord.ext import commands
from discord import app_commands

# HelpSelect класс: Сонголттой интерактив элемент
class HelpSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="📚 Тусламжийн ангилал сонгох...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        category = self.values[0]
        
        # Өнгөний кодууд
        colors = {
            "Ерөнхий": 0x3498db,    # Цэнхэр
            "Эдийн засаг": 0x2ecc71, # Ногоон
            "Тоглоом": 0xe74c3c,    # Улаан
            "Мусик": 0x9b59b6,      # Ягаан
            "VIP": 0xf1c40f,        # Шар
            "Бусад": 0x95a5a6,      # Саарал
            "Бүгд": 0x9b59b6,       # Нил ягаан
            "Админ": 0x34495e       # Хар саарал
        }

        commands_list = []  # Командуудын жагсаалт
        embed = None

        if category == "Ерөнхий":
            embed = discord.Embed(
                title="🏠 Үндсэн командууд",
                description="**Хамгийн түгээмэл хэрэглэгддэг командууд:**",
                color=colors["Ерөнхий"]
            )
            commands_list = [
                ("📚 `help`", "Тусламжийн цэс харах"),
                ("📚 `tutorial`", "MongolBot-ийн бүрэн заавар"),
                ("🆘 `support`", "Асуудал/санал хүсэлт илгээх")
            ]
            
        elif category == "Эдийн засаг":
            embed = discord.Embed(
                title="💸 Банк & Эдийн засаг",
                description="**Санхүүгийн үйлчилгээнүүд:**",
                color=colors["Эдийн засаг"]
            )
            commands_list = [
                ("💰 `balance`, `bal`", "Таны одоогийн үлдэгдэл"),
                ("🏦 `bank`", "Банкны бүх үйлчилгээ"),
                ("💸 `give @user <дүн>`", "Хэрэглэгчид мөнгө шилжүүлэх"),
                ("📊 `top`", "Баян тоглогчдын жагсаалт"),
                ("🎁 `daily`", "Өдөр тутмын шагнал авах")
            ]
            
        elif category == "Тоглоом":
            embed = discord.Embed(
                title="🎲 Мөрийтэй тоглоомууд",
                description="**Азаа үзэх тоглоомууд:**",
                color=colors["Тоглоом"]
            )
            commands_list = [
                ("🎰 `slots`, `s`", "Слот машин тоглох - 3 адилхан = Их шагнал!"),
                ("🎲 `coinflip`, `cf`", "Зоос шидэх - 2x үржүүлэх боломж"),
                ("🎯 `roulette`, `r`", "Рулет тоглох - 5x хүртэл үржих!"),
                ("💣 `minefield`, `mf`", "Бөмбөгөөс зайлсхийх - Өндөр шагналтай!"),
                ("🎟️ `lottery`", "Сугалааны мэдээлэл харах"),
                ("🎫 `buylottery <тоо>`", "Сугалааны тасалбар авах (VIP: +1 тасалбар)"),
                ("⚔️ `duelroll @user <дүн>`", "1v1 шооны дуэл - ялвал бүх бооцоог авна")
            ]

        elif category == "Мусик":
            embed = discord.Embed(
                title="🎶 Мусик",
                description="**Мусиктэй холбоотой командууд:**",
                color=colors["Мусик"]
            )
            commands_list = [
                ("💰 `play`", "Дуу тоглуулах (эхний дуу шууд, дараагийнх queue-д)"),
                ("🏦 `playlist`", "Playlist эсвэл олон дуу queue-д нэмэх"),
                ("💸 `pause/resume`", "Түр зогсоох/үргэлжлүүлэх"),
                ("📊 `skip`", "Дараагийн дуу руу шилжих"),
                ("🛑 `stop`", "Дууг зогсоох"),
                ("📃 `queue`", "Queue-д байгаа дуунууд"),
                ("🔊 `volume`", "Дууны чанга (default: 50%)"),
                ("🔊 `leave`", "Voice channel-ээс гарах"),
                ("🎶 `musicinfo`, `minfo`", "Дууны мэдээлэл харах")
            ]

        elif category == "VIP":
            embed = discord.Embed(
                title="👑 VIP гишүүнчлэл",
                description="**Онцгой давуу эрхүүд:**",
                color=colors["VIP"]
            )
            commands_list = [
                ("💎 `vip`", "VIP эрх, давуу талууд"),
                ("🎁 `giftvip`", "VIP эрх бэлэглэх"),
                ("👑 `viptop`", "Шилдэг VIP гишүүд"),
                ("💰 `buyvip`", "VIP эрх худалдан авах"),
                ("✨ `dailyvip`", "VIP өдрийн шагнал")
            ]

        elif category == "Ажил & Ур чадвар":
            embed = discord.Embed(
                title="🛠️ Ажил & Ур чадвар",
                description="**Job системийн командууд:**",
                color=0x2980b9
            )
            commands_list = [
                ("🤺 `rob @user`", "Хэрэглэгчийг дээрэмдэх"),
                ("🏦 `rob bank @user`", "Банк дээрэмдэх (20+ rob level)"),
                ("💻 `hack @user`", "Хэрэглэгчийг хакдах"),
                ("💾 `hack save @user`", "Банк хакдах (20+ hack level)"),
                ("🛡️ `block`", "Өөрийгөө 5 цаг хамгаалах"),
                ("📊 `status`, `status @user`", "Статус харах"),
                ("📈 `levelinfo`, `li`", "Дэлгэрэнгүй level мэдээлэл"),
                ("🏆 `rank`, `rank balance`, ...", "Тэргүүлэгчдийн жагсаалт"),
            ]

        elif category == "Бүгд":
            embed = discord.Embed(
                title="📚 Бүх командуудын жагсаалт",
                description=(
                    "**Бүх боломжит командууд:**\n"
                    "`m` угтвартай бичнэ."
                ),
                color=colors["Бүгд"]
            )
            commands_list = [
                ("🏦 `bank`", "Банкны үйлчилгээний төв"),
                ("💰 `balance`, `bal`", "Таны одоогийн үлдэгдэл"),
                ("💸 `give @user`", "Мөнгө шилжүүлэх"),
                ("📊 `top`", "Баян тоглогчид"),
                ("🎁 `daily`", "Өдрийн шагнал"),
                ("🎰 `slots`, `s`", "Слот машин"),
                ("🎲 `coinflip`, `cf`", "Зоос шидэх"),
                ("🎯 `roulette`, `r`", "Рулет тоглоом"),
                ("💣 `minefield`, `mf`", "Бөмбөгөөс зайлсхийх"),
                ("🎟️ `lottery`", "Сугалааны мэдээлэл"),
                ("🎫 `buylottery`", "Сугалааны тасалбар авах"),
                ("👑 `vip`", "VIP гишүүнчлэл"),
                ("📚 `help`", "Тусламж авах"),
                ("🆘 `support`", "Асуудал/санал хүсэлт илгээх")
            ]
            
        elif category == "Админ":
            embed = discord.Embed(
                title="🔒 Админ удирдлага",
                description="**Зөвхөн админ эрхтэй хэрэглэгчдэд:**",
                color=colors["Админ"]
            )
            commands_list = [
                ("📢 `/post`", "Мэдэгдэл нийтлэх (Эрх: administrator + manage_messages)"),
                ("📊 `/poll`", "Санал асуулга үүсгэх"),
                ("🎉 `giveaway`", "Giveaway эхлүүлэх (Эрх: administrator)"),
                ("📝 `staff`", "Ажилтны анкет бөглөх цонх үүсгэх (Эрх: administrator)"),
                ("⚙️ `staffchannel #суваг`", "Ажилтны анкет хүлээн авах суваг тохируулах (Эрх: administrator)"),
                ("📋 `listowners`", "Серверийн эзэдийн жагсаалт"),
                ("💰 `checkbalance`", "Серверийн банкны үлдэгдэл шалгах (Серверийн эзэд)"),
                ("➖ `serverwith <дүн>`", "Серверийн банкнаас мөнгө гаргах (Серверийн эзэд)"),
                ("🎂 `/set_birthday_channel #суваг`", "Төрсөн өдрийн суваг тохируулах (Эрх: administrator)"),
                ("💬 `/set_birthday_message <текст>`", "Төрсөн өдрийн мессеж тохируулах (Эрх: administrator)")
            ]

        else:
            embed = discord.Embed(
                title="⚠️ Ангилал олдсонгүй",
                description="Уучлаарай, ийм ангилал байхгүй байна.",
                color=0xe74c3c
            )
            commands_list = []

        # Командуудыг embed-д нэмэх
        for name, value in commands_list:
            embed.add_field(name=name, value=value, inline=False)

        # Footer нэмэх
        embed.set_footer(text="💡 Командын өмнө *m* угтвар бичнэ")
        
        await interaction.response.edit_message(embed=embed)

# HelpView класс: Сонголтын UI-г бүрдүүлэх
class HelpView(discord.ui.View):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__()
        self.add_item(HelpSelect(options))

# Тусламжийн үндсэн embed илгээх функц
async def send_help_embed(ctx_or_interaction: Union[commands.Context, discord.Interaction]):
    # Bot avatar URL авах
    bot_avatar_url = None
    if isinstance(ctx_or_interaction, commands.Context):
        bot_avatar_url = ctx_or_interaction.bot.user.avatar.url if ctx_or_interaction.bot.user.avatar else None
    elif isinstance(ctx_or_interaction, discord.Interaction):
        if ctx_or_interaction.client.user and ctx_or_interaction.client.user.avatar:
            bot_avatar_url = ctx_or_interaction.client.user.avatar.url
        else:
            bot_avatar_url = None

    embed = discord.Embed(
        title="🎮 МонголБот | Тусламжийн Цэс",
        description=(
            "**Сайн байна уу!** \nМонголБот-ын тусламжийн цэсэнд тавтай морил 👋\n\n"
            "💡 **Хэрхэн ашиглах вэ?**\n"
            "• Доорх цэснээс хүссэн ангилалаа сонгоно уу\n"
            "• Бүх команд `m` угтвартай\n"
            "• Slash команд `/` ашиглан бичиж болно\n\n"
            "⚡ **Шинэ командууд нэмэгдсэн!**"
        ),
        color=0x2ecc71  # Тод ногоон өнгө
    )

    # Ангилал бүрийн тайлбар
    categories = {
        "Ерөнхий": {
            "emoji": "🏠",
            "name": "Үндсэн командууд", 
            "desc": "Хамгийн түгээмэл хэрэглэгддэг үндсэн командууд"
        },
        "Эдийн засаг": {
            "emoji": "💸",
            "name": "Банк & Эдийн засаг",
            "desc": "Мөнгө, данс, шилжүүлэг, хадгаламж, зээл"
        },        
        "Тоглоом": {
            "emoji": "🎲",
            "name": "Мөрийтэй тоглоомууд",
            "desc": "Казино, рулет, слот машин, сугалаа, бооцоот тоглоомууд"
        },
        "Мусик": {
            "emoji": "🎶",
            "name": "Мусик",
            "desc": "Дуу тоглуулах, queue, дууны мэдээлэл"
        },
        "VIP": {
            "emoji": "👑",
            "name": "VIP гишүүнчлэл",
            "desc": "Онцгой давуу эрхүүд, VIP шагналууд"
        },
        "Ажил & Ур чадвар": {
            "emoji": "🛠️",
            "name": "Ажил & Ур чадвар",
            "desc": "Job систем, rob/hack, skill level, rank"
        },
        "Бүгд": {
            "emoji": "📚",
            "name": "Бүх командын жагсаалт",
            "desc": "Бүх боломжит командуудын дэлгэрэнгүй жагсаалт"
        }
    }

    # Ангилал бүрийг embed-д нэмэх
    for category, data in categories.items():
        embed.add_field(
            name=f"{data['emoji']} {data['name']}", 
            value=f"```{data['desc']}```",
            inline=False
        )

    # Footer мэдээлэл
    embed.set_footer(
        text="💝 МонголБот-ыг ашигладаг та бүхэнд баярлалаа!",
        icon_url=bot_avatar_url
    )

    # Сонголтын options үүсгэх
    options = [
        discord.SelectOption(
            label=category,
            description=data["desc"][:100],  # Description хэт урт байж болохгүй
            emoji=data["emoji"]
        ) for category, data in categories.items()
    ]

    # Админ эрхтэй хэрэглэгч шалгах
    member = None
    if isinstance(ctx_or_interaction, commands.Context):
        member = ctx_or_interaction.author if isinstance(ctx_or_interaction.author, discord.Member) else None
    elif isinstance(ctx_or_interaction, discord.Interaction):
        member = ctx_or_interaction.user if isinstance(ctx_or_interaction.user, discord.Member) else None

    if member and member.guild_permissions.administrator:
        admin_option = discord.SelectOption(
            label="Админ",
            description="Сервер удирдлагын онцгой командууд",
            emoji="🔒"
        )
        options.append(admin_option)
        embed.add_field(
            name="🔒 Админ удирдлага",
            value="```Зөвхөн админ эрхтэй хэрэглэгчдэд зориулсан командууд```",
            inline=False
        )

    return embed, options


# Help ког: Help командын логик
class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context):
        """!help команд"""
        embed, options = await send_help_embed(ctx)
        await ctx.send(embed=embed, view=HelpView(options))

    @app_commands.command(name="help", description="Тусламжийн мэдээлэл авах") 
    async def help_slash(self, interaction: discord.Interaction):
        """Slash команд /help"""
        embed, options = await send_help_embed(interaction)
        await interaction.response.send_message(embed=embed, view=HelpView(options))

# Cog-г идвэхжүүлэх
async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))