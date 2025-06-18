from discord.ext import commands
import discord
from typing import Optional

EVENT_POLICY_MESSAGE = (
    "Сайн уу! 👋\n\n"
    "Манай bot-ын нэрэмжит event командууд нь танай серверийн хамт олонд зориулж хөгжүүлэгдсэн бөгөөд зөвхөн албан ёсоор зарлагдсан эвэнтэд ашиглах зориулалттай.\n\n"
    "Харамсалтай нь эвэнт зарлагдаагүй үед энэ командыг ашиглаж, хожил авсан тохиолдол бүртгэгдсэн. Энэ нь event командын зориулалт болон ашиглалтын нөхцөлийг зөрчсөн үйлдэл юм.\n\n"
    "— Иймд уг хожлыг хүчингүйд тооцож, дүнг буцаах шаардлагатай гэж үзлээ.\n"
    "— Цаашид дахин ийм төрлийн үйлдэл гаргавал танай сервер нэрэмжит команд ашиглах эрхээ хязгаарлуулах эрсдэлтэйг анхаарна уу.\n\n"
    "Event команд нь ашиг олох биш, community-д зориулсан эвэнтэд ашиглагдах зорилготой гэдгийг сануулъя.\n\n"
    "Баярлалаа, ойлгож хүлээн авсан гэж найдаж байна. 🙏"
)

EVENT_POLICY_INTERNAL = (
    "Нэрэмжит event командууд нь тухайн серверийн хамт олонд зориулж хөгжүүлэгдсэн бөгөөд зөвхөн албан ёсоор зарлагдсан эвэнтэд ашиглагдах зориулалттай.\n\n"
    "✅ Ашиглах нөхцөл:\n"
    "- Командыг зөвхөн эвэнт зарлагдсан үед ашиглах.\n"
    "- Эвэнт нь зохион байгуулагч талаас (бот хөгжүүлэгч эсвэл админ) баталгаажсан байх шаардлагатай.\n"
    "- Тест хийх шаардлагатай бол зөвхөн developer эсвэл зөвшөөрөгдсөн админ хэрэглэгч ашиглаж болно.\n\n"
    "❌ Хориглох зүйлс:\n"
    "- Эвэнт зарлагдаагүй үед команд ашиглаж бооцоо тавих.\n"
    "- Командыг ашиглан хувийн ашиг олох оролдлого хийх.\n"
    "- Тест нэрийн дор их хэмжээний хожил авах.\n\n"
    "⚠️ Зөрчлийн үр дагавар:\n"
    "- Хожлыг хүчингүйд тооцох.\n"
    "- Танай серверийн нэрэмжит команд ашиглах эрхийг хязгаарлах эсвэл цуцлах.\n"
    "- Давтан зөрчил илэрвэл нэрэмжит эрхийг бүрэн хасах боломжтой.\n\n"
    "Эдгээр бодлогын зорилго нь нэрэмжит эвэнтүүдийг шударга, ил тод, community-д чиглэсэн байдлаар зохион байгуулахад оршино."
)

EVENT_POLICY_RISK = (
    "⚠️ Асуудлын нөлөө — бусад серверүүдэд гарах эрсдэл:\n\n"
    "- Бусад хэрэглэгчид “тест” нэрийн дор санаатайгаар зөрчил гаргах эрсдэл нэмэгдэнэ.\n"
    "- Нэрэмжит эвэнтүүдийн итгэлцэл, шударга байдал алдагдана.\n"
    "- Командуудын нэр хүнд унаж, эвэнтийн тогтолцоо тогтворгүй болох магадлалтай.\n"
    "- Хөгжүүлэгч тал болон админуудын дунд маргаан, үл ойлголцол үүсч болзошгүй.\n\n"
    "Ийм төрлийн зөрчлийг шууд таслан зогсоож, дахин давтагдахгүй байхад анхаарах нь нийт хамтрагч серверүүдийн итгэлцлийг хадгалах гол нөхцөл юм."
)

class EventPolicy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Disabled old commands ---
    # @commands.command(name="eventpolicy")
    # @commands.has_permissions(administrator=True)
    # async def event_policy_check(self, ctx: commands.Context, user_id: int):
    #     ...
    # @commands.command(name="eventpolicyinfo")
    # @commands.has_permissions(administrator=True)
    # async def event_policy_info(self, ctx: commands.Context):
    #     ...
    # @commands.command(name="eventlog")
    # @commands.has_permissions(administrator=True)
    # async def event_log_dm(self, ctx: commands.Context, user_id: int, *, log_text: str):
    #     ...

    @commands.command(name="eventpolicyfull")
    @commands.has_permissions(administrator=True)
    async def event_policy_full(self, ctx: commands.Context, user_id: Optional[int] = None, *, log_text: Optional[str] = None):
        """
        Event командын бодлогын анхааруулга, дэлгэрэнгүй, зөрчлийн мэдээлэл, чат логийг нэг дор илгээх (user_id болон log_text параметрээр)
        Хэрэглэгч рүү DM болон серверт embed хэлбэрээр илгээнэ.
        log_text өгөөгүй бол тухайн хэрэглэгчийн сүүлийн 5 мессежийг channel-аас автоматаар авна.
        """
        # Хэрэглэгч рүү бодлогын анхааруулга илгээх
        if user_id is not None:
            try:
                user = await self.bot.fetch_user(user_id)
                if user:
                    # Анхааруулга илгээх
                    await user.send(EVENT_POLICY_MESSAGE)
                    # Дэлгэрэнгүй бодлого embed
                    embed = discord.Embed(
                        title="📘 EVENT КОМАНДЫН ДОТООД БОДЛОГО",
                        description=EVENT_POLICY_INTERNAL,
                        color=0x3498db
                    )
                    embed.add_field(
                        name="⚠️ АСУУДЛЫН НӨЛӨӨ — БУСАД СЕРВЕРҮҮДЭД ГАРАХ ЭРСДЭЛ",
                        value=EVENT_POLICY_RISK,
                        inline=False
                    )
                    await user.send(embed=embed)
                    # Чат лог автоматаар авах
                    if not log_text:
                        # Channel history-с тухайн хэрэглэгчийн сүүлийн 5 мессежийг авах
                        messages = []
                        async for message in ctx.channel.history(limit=100):
                            if message.author.id == user_id:
                                messages.append(message)
                                if len(messages) >= 5:
                                    break
                        if messages:
                            messages = list(reversed(messages))  # Хуучнаас шинэ рүү
                            log_text = "\n".join([
                                f"[{m.created_at.strftime('%Y-%m-%d %H:%M')}] {m.author.display_name}: {m.content}" for m in messages
                            ])
                        else:
                            log_text = "(Тухайн хэрэглэгчийн сүүлийн 100 мессежээс чат олдсонгүй.)"
                    # Чат лог илгээх (log_text)
                    if log_text:
                        log_embed = discord.Embed(
                            title="⚠️ Event командын ашиглалтын зөрчилтэй холбоотой чат лог",
                            description=log_text[:4000],
                            color=0xFF0000
                        )
                        log_embed.set_footer(text=f"Админ: {ctx.author} | Сервер: {ctx.guild.name if ctx.guild else 'DM'}")
                        log_embed.timestamp = ctx.message.created_at
                        await user.send(embed=log_embed)
                    await ctx.send(f"✅ <@{user_id}> хэрэглэгч рүү бүх мэдээллийг илгээлээ.")
                else:
                    await ctx.send("⚠️ Хэрэглэгч олдсонгүй!")
            except Exception as e:
                await ctx.send("⚠️ Хэрэглэгч рүү мессеж илгээж чадсангүй.")
                print(e)
        else:
            # Хэрэглэгч заагаагүй бол зөвхөн серверт embed хэлбэрээр илгээнэ
            embed = discord.Embed(
                title="📘 EVENT КОМАНДЫН ДОТООД БОДЛОГО",
                description=EVENT_POLICY_INTERNAL,
                color=0x3498db
            )
            embed.add_field(
                name="⚠️ АСУУДЛЫН НӨЛӨӨ — БУСАД СЕРВЕРҮҮДЭД ГАРАХ ЭРСДЭЛ",
                value=EVENT_POLICY_RISK,
                inline=False
            )
            await ctx.send(embed=embed)
            if not log_text:
                # Channel history-с хамгийн сүүлийн 15 мессежийг авах (user_id байхгүй тул бүх хэрэглэгч)
                messages = []
                async for message in ctx.channel.history(limit=15):
                    messages.append(message)
                if messages:
                    messages = list(reversed(messages))
                    log_text = "\n".join([
                        f"[{m.created_at.strftime('%Y-%m-%d %H:%M')}] {m.author.display_name}: {m.content}" for m in messages
                    ])
                else:
                    log_text = "(Сүүлийн 15 мессеж олдсонгүй.)"
            if log_text:
                log_embed = discord.Embed(
                    title="⚠️ Event командын ашиглалтын зөрчилтэй холбоотой чат лог",
                    description=log_text[:4000],
                    color=0xFF0000
                )
                log_embed.set_footer(text=f"Админ: {ctx.author} | Сервер: {ctx.guild.name if ctx.guild else 'DM'}")
                log_embed.timestamp = ctx.message.created_at
                await ctx.send(embed=log_embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(EventPolicy(bot))
