import discord
from discord.ext import commands
import asyncio
import logging
import traceback
from typing import Optional
import os
from dotenv import load_dotenv
from cogs.utils import settings
# MongolBot - Discord Bot

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Check if token exists
if not TOKEN:
    print("❌ DISCORD_BOT_TOKEN байхгүй байна! .env файлаа шалгана уу.")
    exit(1)

# Logging тохиргоо - spam багасгахын тулд WARNING level ашиглах
logging.basicConfig(
    level=logging.WARNING,  # INFO-ээс WARNING болгосон
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Зөвхөн чухал мэдээллүүдийг INFO level-ээр харуулах
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Intents
intents = discord.Intents.all()
intents.members = True
intents.presences = True
intents.message_content = True

# Bot үүсгэх хэсгийг өөрчлөх
activity = discord.Activity(type=discord.ActivityType.playing, name="mhelp")
bot = commands.Bot(
    command_prefix=settings.get_prefix,  # settings.py-с prefix авах
    case_insensitive=True, 
    intents=intents, 
    activity=activity
)

bot.owner_id = 751055793893146624  # Change this to your Discord ID

# Extensions list шинэчлэх 
extensions = [

    # Utils Cogs - Channel must be loaded first
    'cogs.utils.channel',
    'cogs.utils.support',
    'cogs.utils.help',
    'cogs.utils.tutorial',

    # Music Cogs
    'cogs.music.music',
    
    # Economy Cogs
    'cogs.economy.bank',
    'cogs.economy.economy', 
    'cogs.economy.serverbank',
    'cogs.economy.vip',

    # Games Cogs
    'cogs.games.game',
    'cogs.games.lottery',
    
    # Server Cogs
    'cogs.server.anime',
    'cogs.server.horseracing',

    # Admin Cogs
    'cogs.admin.admin',
    'cogs.admin.owner',
    'cogs.admin.suggest',
    'cogs.admin.giveaway',
    'cogs.admin.fun',
    'cogs.admin.birthday',
    'cogs.admin.report',
    'cogs.admin.event_policy',
]
# Cog-уудыг зөв дарааллаар ачаалах
async def load_cogs_and_sync():
    try:
        # Эхлээд database-уудыг үүсгэх
        try:
            await settings.init_db()
            await settings.load_prefixes()
            print("✅ Database системүүд бэлэн боллоо")
        except Exception as e:
            logger.error(f"❌ Database системийг эхлүүлэхэд алдаа: {e}")
            
        # Эхлээд VIP системийг ачаална (бусад cog-ууд үүн дээр суурилдаг)
        try:
            await bot.load_extension("cogs.economy.vip")
            print("✅ VIP систем ачаалагдлаа")  # Console-д харуулах
        except Exception as e:
            logger.error(f"❌ VIP систем ачаалахад алдаа: {e}")
            
        # Дараа нь бусад cog-уудыг ачаална
        loaded_count = 0
        for extension in extensions:
            if extension != "cogs.economy.vip":  # VIP-ийг давтж ачаалахгүй
                try:
                    await bot.load_extension(f"{extension}")
                    loaded_count += 1
                except Exception as e:
                    logger.error(f"🚨 Ачаалж чадсангүй: {extension} - {e}")

        print(f"✅ {loaded_count}/{len(extensions)-1} cog амжилттай ачаалагдлаа")  # Тоо харуулах        # Дараа нь бүх командуудыг sync хийнэ
        try:
            synced = await bot.tree.sync()
            print(f"✅ {len(synced)} slash команд sync хийгдлээ")  # Console-д харуулах
        except Exception as e:
            logger.error(f"❌ Slash команд sync хийхэд алдаа гарлаа: {e}")

    except Exception as e:
        logger.error(f"❌ Когууд ачаалахад алдаа гарлаа: {e}")

@bot.event
async def on_ready():
    print(f"✅ {bot.user} амжилттай холбогдлоо!")  # Console-д харуулах
    await load_cogs_and_sync()

@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    """
    Бүх команд дээр гарсан алдааг боловсруулах
    
    Args:
        ctx (commands.Context): Команд контекст
        error (Exception): Гарсан алдаа
    """
    # Embed message бэлтгэх
    error_embed = discord.Embed(color=discord.Color.red())
    error_embed.set_author(name="❌ Алдаа")
    
    # Алдааны төрлийг шалгах
    if isinstance(error, commands.CommandNotFound):
        return  # Команд олдохгүй бол алдаа харуулахгүй
        
    elif isinstance(error, commands.MissingRequiredArgument):
        # Командын нэрийг авах
        command_name = ctx.command.name if ctx.command else "энэ команд"
        
        # Тухайн командын хэрэглээг харуулах жишээ гаргах
        usage = ""
        if ctx.command and ctx.command.help:
            usage = f"\n\nЖишээ нь: `{ctx.prefix}{command_name} {ctx.command.help}`"
        
        # Дутуу орсон мэдээллийн нэрийг монгол болгох
        param_name = error.param.name
        translated_param = {
            "member": "хэрэглэгч",
            "user": "хэрэглэгч",
            "channel": "суваг",
            "role": "роль",
            "message": "мессеж",
            "amount": "тоо хэмжээ",
            "reason": "шалтгаан",
            "target": "зорилтот",
            "text": "текст",
            "name": "нэр",
            "description": "тайлбар"
        }.get(param_name, param_name)
        
        error_embed.description = f"❗ **{command_name}** командыг ашиглахад **{translated_param}** гэсэн мэдээлэл дутуу байна.{usage}"
        error_embed.set_footer(text=f"💡 Командын бүрэн заавар авахын тулд {ctx.prefix}help {command_name} гэж бичнэ үү")
        
    elif isinstance(error, AttributeError) and str(error).endswith("'NoneType' object has no attribute 'lower'"):
        command_name = ctx.command.name if ctx.command else "энэ команд"
        error_embed.description = f"❌ **{command_name}** командад хоосон утга оруулсан байна.\n💡 Та утга оруулсан эсэхээ шалгаад дахин оролдоно уу"
        
    elif isinstance(error, commands.CommandOnCooldown):
        await send_cooldown_error(ctx, error)
        return
        
    elif isinstance(error, commands.MissingPermissions):
        missing_perms = []
        for perm in error.missing_permissions:
            translated_perm = {
                "kick_members": "гишүүдийг хөөх",
                "ban_members": "гишүүдийг бандах",
                "administrator": "админ",
                "manage_channels": "сувгуудыг удирдах",
                "manage_guild": "серверийг удирдах",
                "manage_messages": "мессежүүдийг удирдах",
                "manage_roles": "ролиудыг удирдах",
                "manage_webhooks": "вебхүүкүүдийг удирдах",
                "manage_emojis": "эможинуудыг удирдах",
                "view_audit_log": "аудит лог харах",
                "view_guild_insights": "сервер статистик харах",
                "moderate_members": "гишүүдийг зохицуулах"
            }.get(perm, perm.replace("_", " ").title())
            missing_perms.append(f"`{translated_perm}`")
            
        error_embed.description = f"❌ Танд дараах эрх байхгүй байна:\n{', '.join(missing_perms)}"
        
    elif isinstance(error, commands.BotMissingPermissions):
        missing_perms = []
        for perm in error.missing_permissions:
            translated_perm = {
                "kick_members": "гишүүдийг хөөх",
                "ban_members": "гишүүдийг бандах",
                "administrator": "админ",
                "manage_channels": "сувгуудыг удирдах",
                "manage_guild": "серверийг удирдах",
                "manage_messages": "мессежүүдийг удирдах",
                "manage_roles": "ролиудыг удирдах",
                "manage_webhooks": "вебхүүкүүдийг удирдах",
                "manage_emojis": "эможинуудыг удирдах",
                "view_audit_log": "аудит лог харах",
                "view_guild_insights": "сервер статистик харах",
                "moderate_members": "гишүүдийг зохицуулах"
            }.get(perm, perm.replace("_", " ").title())
            missing_perms.append(f"`{translated_perm}`")
            
        error_embed.description = f"❌ Ботд дараах эрх байхгүй байна:\n{', '.join(missing_perms)}"
        
    elif isinstance(error, commands.MemberNotFound):
        error_embed.description = "❌ Таны заасан хэрэглэгч олдсонгүй.\n💡 Та хэрэглэгчийн нэр эсвэл ID-г зөв оруулсан эсэхээ шалгана уу"
        
    elif isinstance(error, commands.ChannelNotFound):
        error_embed.description = "❌ Таны заасан суваг олдсонгүй.\n💡 Та сувгийн нэр эсвэл ID-г зөв оруулсан эсэхээ шалгана уу"
        
    elif isinstance(error, commands.RoleNotFound):
        error_embed.description = "❌ Таны заасан роль олдсонгүй.\n💡 Та ролийн нэр эсвэл ID-г зөв оруулсан эсэхээ шалгана уу"
        
    elif str(error) == "Channel not enabled for commands.":
        await send_channel_permission_error(ctx)
        return
    
    else:
        # Алдааны мэдээллийг логдох
        error_embed.description = "⚠️ Уучлаарай, алдаа гарлаа. Админтай холбогдоно уу."
        logging.error(f"Алдаа гарлаа командад: {ctx.command}")
        logging.error(f"Алдааны мэдээлэл: {error}")
        logging.error("Traceback:")
        logging.error(traceback.format_exc())

    try:
        # Алдааны мессеж илгээх
        message = await ctx.send(embed=error_embed)
        # 10 секундын дараа мессежийг устгах
        await asyncio.sleep(10)
        await message.delete()
    except discord.Forbidden:
        pass  # Хэрэв мессеж илгээх эрх байхгүй бол алгасах
    except (RuntimeError, discord.ConnectionClosed, discord.HTTPException):
        # Session хаагдсан эсвэл холболт тасарсан бол алгасах
        logger.warning("Discord session хаагдсан эсвэл холболт тасарсан тул алдааны мессеж илгээж чадсангүй")
        pass
    except Exception as send_error:
        # Бусад алдаануудыг log-д бичих
        logger.error(f"Алдааны мессеж илгээхэд алдаа гарлаа: {send_error}")
        pass

bot.remove_command("help")

# Define the dm command
@bot.command(name='dm')
@commands.cooldown(1, 5, commands.BucketType.user)
async def dm(ctx: commands.Context, target: str, *, message: str):
    """Хэрэглэгчийн ID, суваг ID, эсвэл суваг дурдах ашиглан мессеж илгээх"""
    try:
        # Хэрэглэгч эсвэл суваг шалгах
        if target.isdigit():
            target_id = int(target)
            user = bot.get_user(target_id)
            channel = bot.get_channel(target_id)

            if user:
                # Хэрэглэгч рүү DM илгээхээс өмнө эрх шалгах
                member = None
                if ctx.guild:
                    member = ctx.guild.get_member(user.id)
                if member:
                    # Хэрэглэгчийн DM, бичих, харах эрхийг шалгах
                    can_dm = True
                    if member.voice is None and ctx.guild is not None and not any(
                        ch.permissions_for(member).send_messages for ch in ctx.guild.text_channels
                    ):
                        can_dm = False
                    if not can_dm:
                        confirmation = await ctx.send(f"{user.name} хэрэглэгчид DM илгээх боломжгүй: бичих/харуулах эрхгүй байна.")
                        await asyncio.sleep(5)
                        await confirmation.delete()
                        await ctx.message.delete()
                        return
                try:
                    await user.send(message)
                    confirmation = await ctx.send(f"Мессеж {user.name} рүү амжилттай илгээгдлээ.")
                except discord.Forbidden:
                    confirmation = await ctx.send(f"{user.name} хэрэглэгч DM хаалттай байна.")
            elif channel and isinstance(channel, discord.TextChannel):
                # Зөвхөн TextChannel бол мессеж илгээх
                member = ctx.guild.get_member(ctx.author.id) if ctx.guild else None
                if not member:
                    confirmation = await ctx.send("Гишүүн олдсонгүй.")
                else:
                    perms = channel.permissions_for(member)
                    if not perms.send_messages:
                        confirmation = await ctx.send(f"Танд {channel.name} сувагт бичих эрх байхгүй байна.")
                    else:
                        await channel.send(message)
                        confirmation = await ctx.send(f"Мессеж {channel.name} суваг руу амжилттай илгээгдлээ.")
            else:
                confirmation = await ctx.send("Хэрэглэгч эсвэл суваг олдсонгүй.")
        elif target.startswith("<#") and target.endswith(">"):
            # Суваг дурдах ашигласан тохиолдолд
            channel_id = int(target.strip("<#>"))
            channel = bot.get_channel(channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                member = ctx.guild.get_member(ctx.author.id) if ctx.guild else None
                if not member:
                    confirmation = await ctx.send("Гишүүн олдсонгүй.")
                else:
                    perms = channel.permissions_for(member)
                    if not perms.send_messages:
                        confirmation = await ctx.send(f"Танд {channel.name} сувагт бичих эрх байхгүй байна.")
                    else:
                        await channel.send(message)
                        confirmation = await ctx.send(f"Мессеж {channel.name} суваг руу амжилттай илгээгдлээ.")
            else:
                confirmation = await ctx.send("Суваг олдсонгүй.")
        else:
            confirmation = await ctx.send("Хэрэглэгчийн ID, суваг ID, эсвэл суваг дурдах ашиглана уу.")

        # Хэрэглэгчийн анхны мессежийг устгах
        await ctx.message.delete()
        # Амжилтын мессежийг 5 сек дараа устгах
        await asyncio.sleep(5)
        await confirmation.delete()

    except discord.Forbidden:
        confirmation = await ctx.send("Мессеж илгээх эрхгүй байна.")
        await asyncio.sleep(5)
        await confirmation.delete()

    except Exception as e:
        logging.error(f"Алдаа гарлаа: {e}")
        confirmation = await ctx.send("Мессеж илгээх явцад алдаа гарлаа.")
        await asyncio.sleep(5)
        await confirmation.delete()
        
# Command to list all guilds the bot is in and send invite links
@bot.command(name='list_guilds')
@commands.is_owner()
async def list_guilds(ctx: commands.Context):
    if bot.guilds:
        response_lines = []
        for guild in bot.guilds:
            # Text channel-ийг шалгах
            if guild.text_channels:
                channel = guild.text_channels[0]  # Эхний текст суваг
                try:
                    invite = await channel.create_invite(max_age=3600, max_uses=1)  # Invite үүсгэх
                    response_lines.append(f"{guild.name} (ID: {guild.id}) - Invite: {invite.url}")
                except Exception as e:
                    response_lines.append(f"{guild.name} (ID: {guild.id}) - Could not create invite: {e}")
            else:
                response_lines.append(f"{guild.name} (ID: {guild.id}) - No text channels available.")
        
        # Уртыг зохицуулж хэсэгчлэн илгээх
        message_chunks = []
        chunk = ""
        for line in response_lines:
            if len(chunk) + len(line) + 1 > 2000:  # 2000 тэмдэгтийн хязгаарыг шалгах
                message_chunks.append(chunk)
                chunk = ""
            chunk += line + "\n"
        if chunk:
            message_chunks.append(chunk)

        # Мессежүүдийг нэг бүрчлэн илгээх
        for chunk in message_chunks:
            await ctx.send(chunk)
    else:
        await ctx.send("I am not in any guilds.")

@bot.command(name='setprefix')
@commands.has_permissions(administrator=True)
async def set_prefix_command(ctx: commands.Context, new_prefix: str):
    """Серверийн command prefix-ийг өөрчлөх"""
    try:
        if ctx.guild is None:
            await ctx.send("Энэ командыг зөвхөн сервер дээр ашиглаж болно.")
            return

        # Шинэ префиксийг хадгалах
        result = await settings.set_prefix(ctx.guild.id, new_prefix)
        
        # Embed message илгээх
        embed = discord.Embed(
            title="✅ Префикс амжилттай өөрчлөгдлөө!",
            description=f"Шинэ префикс: `{new_prefix}`",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"🛠️ {ctx.author.name} өөрчиллөө")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        # Алдаа гарвал мэдэгдэх
        embed = discord.Embed(
            title="❌ Алдаа гарлаа",
            description="Префикс өөрчлөх үед алдаа гарлаа. Дахин оролдоно уу.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        logger.error(f"Префикс өөрчлөх үед алдаа гарлаа: {str(e)}")

@bot.command(name='commands')
@commands.is_owner()
async def list_all_commands(ctx: commands.Context):
    """Ботын бүх командуудыг цэгцтэй, embed хэлбэрээр харуулна (owner only)"""
    commands_per_embed = 25  # Discord embed field limit
    commands_list = [cmd for cmd in bot.commands if not cmd.hidden]
    if not commands_list:
        await ctx.send("Команд олдсонгүй.")
        return
    for i in range(0, len(commands_list), commands_per_embed):
        embed = discord.Embed(title="🤖 Ботын бүх командууд", color=discord.Color.blurple())
        for command in commands_list[i:i+commands_per_embed]:
            aliases = f"\n**Aliases:** {', '.join(command.aliases)}" if command.aliases else ""
            # Help текстээс Args: хэсгийг арилгах
            help_text = command.help or "Тайлбар байхгүй"
            if "Args:" in help_text:
                help_text = help_text.split("Args:")[0].strip()
            desc = help_text + aliases
            embed.add_field(
                name=f"`{ctx.prefix}{command.name}`",
                value=desc,
                inline=False
            )
        await ctx.send(embed=embed)

# --- Custom error handlers ---
async def send_cooldown_error(ctx: commands.Context, error: commands.CommandOnCooldown):
    cooldown_time = int(error.retry_after)
    minutes = cooldown_time // 60
    seconds = cooldown_time % 60
    if minutes > 0:
        time_text = f"{minutes} минут {seconds} секунд"
    else:
        time_text = f"{seconds} секунд"
    error_embed = discord.Embed(color=discord.Color.red())
    error_embed.set_author(name="⏳ Түр хүлээнэ үү")
    error_embed.description = f"⏳ Та {error.cooldown.per:.1f} секунд тутамд нэг удаа энэ командыг ашиглах боломжтой!\n\nДахин ашиглахын тулд `{time_text}` хүлээнэ үү!"
    try:
        message = await ctx.send(embed=error_embed)
        while cooldown_time > 0:
            await asyncio.sleep(1)
            cooldown_time -= 1
            if cooldown_time > 60:
                time_text = f"{cooldown_time//60} минут {cooldown_time%60} секунд"
            else:
                time_text = f"{cooldown_time} секунд"
            error_embed.description = f"⏳ Та {error.cooldown.per:.1f} секунд тутамд нэг удаа энэ командыг ашиглах боломжтой!\n\nДахин ашиглахын тулд `{time_text}` хүлээнэ үү!"
            try:
                await message.edit(embed=error_embed)
            except (discord.NotFound, discord.HTTPException, RuntimeError):
                break
        try:
            error_embed.color = discord.Color.green()
            error_embed.set_author(name="✅ Команд бэлэн боллоо")
            error_embed.description = "Одоо энэ командыг дахин ашиглаж болно!"
            await message.edit(embed=error_embed)
        except (discord.NotFound, discord.HTTPException, RuntimeError):
            pass
    except (discord.Forbidden, RuntimeError, discord.ConnectionClosed, discord.HTTPException):
        pass

async def send_channel_permission_error(ctx: commands.Context):
    error_embed = discord.Embed(color=discord.Color.red())
    error_embed.set_author(name="❌ Алдаа")
    error_embed.description = "❌ Энэ сувгаар командыг ашиглах боломжгүй! Админ зөвшөөрсөн сувгаар ашиглана уу."
    try:
        message = await ctx.send(embed=error_embed)
        await asyncio.sleep(10)
        await message.delete()
    except discord.Forbidden:
        pass
    except (RuntimeError, discord.ConnectionClosed, discord.HTTPException):
        logger.warning("Discord session хаагдсан эсвэл холболт тасарсан тул алдааны мессеж илгээж чадсангүй")
        pass
    except Exception as send_error:
        logger.error(f"Алдааны мессеж илгээхэд алдаа гарлаа: {send_error}")
        pass

# Run the bot
if TOKEN is None:
    raise ValueError("DISCORD_BOT_TOKEN environment variable is not set.")
bot.run(TOKEN)
