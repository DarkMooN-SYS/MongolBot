import discord
from discord.ext import commands
import asyncio
import logging
import traceback
from typing import Optional
import os
from dotenv import load_dotenv
from cogs.utils import settings
from datetime import datetime
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

# Rate limit protection settings
STARTUP_DELAY = 5  # seconds to wait before starting operations
RATE_LIMIT_RESET_TIME = 30  # minutes to wait for rate limit to reset

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
        # Rate limit recovery дараа startup delay
        print(f"🕐 Rate limit-ээс сэргийлэхийн тулд {STARTUP_DELAY} секунд хүлээж байна...")
        await asyncio.sleep(STARTUP_DELAY)
        
        # Эхлээд database-уудыг үүсгэх
        try:
            await settings.init_db()
            await settings.load_prefixes()
            print("✅ Database системүүд бэлэн боллоо")
        except Exception as e:
            logger.error(f"❌ Database системийг эхлүүлэхэд алдаа: {e}")
            
        # Rate limit-ээс зайлсхийхийн тулд cog loading хоорондоо жижиг delay
        # Эхлээд VIP системийг ачаална (бусад cog-ууд үүн дээр суурилдаг)
        try:
            await bot.load_extension("cogs.economy.vip")
            print("✅ VIP систем ачаалагдлаа")  # Console-д харуулах
            await asyncio.sleep(0.5)  # Small delay between cog loads
        except Exception as e:
            logger.error(f"❌ VIP систем ачаалахад алдаа: {e}")
            
        # Дараа нь бусад cog-уудыг ачаална
        loaded_count = 0
        for extension in extensions:
            if extension != "cogs.economy.vip":  # VIP-ийг давтж ачаалахгүй
                try:
                    await bot.load_extension(f"{extension}")
                    loaded_count += 1
                    await asyncio.sleep(0.2)  # Small delay between each cog load
                except Exception as e:
                    logger.error(f"🚨 Ачаалж чадсангүй: {extension} - {e}")

        print(f"✅ {loaded_count}/{len(extensions)-1} cog амжилттай ачаалагдлаа")  # Тоо харуулах        
        
        # Rate limit-ээс зайлсхийхийн тулд sync хийхээс өмнө хүлээх
        await asyncio.sleep(2)
        
        # Дараа нь бүх командуудыг sync хийнэ
        try:
            synced = await bot.tree.sync()
            print(f"✅ {len(synced)} slash команд sync хийгдлээ")  # Console-д харуулах
        except discord.HTTPException as e:
            if e.status == 429:  # Rate limited
                print(f"⚠️ Slash команд sync хийхэд rate limit. {RATE_LIMIT_RESET_TIME} минут хүлээж дахин оролдоно уу.")
                logger.error(f"Rate limited during sync: {e}")
            else:
                logger.error(f"❌ Slash команд sync хийхэд алдаа гарлаа: {e}")
        except Exception as e:
            logger.error(f"❌ Slash команд sync хийхэд алдаа гарлаа: {e}")

    except Exception as e:
        logger.error(f"❌ Когууд ачаалахад алдаа гарлаа: {e}")

@bot.event
async def on_ready():
    print(f"✅ {bot.user} амжилттай холбогдлоо!")  # Console-д харуулах
    # Persistent staff setup view бүртгэх - error handling нэмэх
    try:
        from cogs.admin.report import StaffSetupView
        for guild in bot.guilds:
            bot.add_view(StaffSetupView(guild.id))
        print("✅ StaffSetupView persistent views бүртгэгдлээ")
    except ImportError:
        print("[WARNING] StaffSetupView олдсонгүй - report module дутуу байж болзошгүй")
    except Exception as e:
        print(f"[ERROR] StaffSetupView persistent view бүртгэхэд алдаа: {e}")
    
    # Rate limit recovery mode шалгах
    try:
        await load_cogs_and_sync()
    except discord.HTTPException as e:
        if e.status == 429:
            print(f"⚠️ Rate limit байна. {RATE_LIMIT_RESET_TIME} минут хүлээж дахин асааарай.")
        else:
            print(f"❌ HTTP алдаа: {e}")
    except Exception as e:
        print(f"❌ Системийг эхлүүлэхэд алдаа: {e}")

@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    """
    Бүх команд дээр гарсан алдааг боловсруулах
    
    Args:
        ctx (commands.Context): Команд контекст
        error (Exception): Гарсан алдаа
    """
    # Rate limit handling нэмэх
    if isinstance(error, discord.HTTPException) and error.status == 429:
        global last_rate_limit_time
        last_rate_limit_time = datetime.now()
        rate_limit_message = "⚠️ Discord API rate limit. Хэсэг хугацаа хүлээж дахин оролдоно уу."
        try:
            await ctx.send(rate_limit_message)
        except:
            logger.error("Rate limit message илгээж чадсангүй")
        logger.warning(f"Rate limited in command {ctx.command}: {error}")
        return
    
    # Embed message бэлтгэх
    error_embed = discord.Embed(color=discord.Color.red())
    error_embed.set_author(name="❌ Алдаа")
    
    # Алдааны төрлийг шалгах
    if isinstance(error, commands.CommandNotFound):
        return  # Команд олдохгүй бол алдаа харуулахгүй
        
    elif isinstance(error, commands.MissingRequiredArgument):
        command_name = ctx.command.name if ctx.command else "энэ команд"
        param_name = error.param.name
        translated_param = {
            "member": "хэрэглэгч", "user": "хэрэглэгч", "channel": "суваг", 
            "role": "роль", "amount": "дүн", "reason": "шалтгаан", 
            "text": "текст", "name": "нэр"
        }.get(param_name, param_name)
        
        error_embed.description = f"❌ **{translated_param}** дутуу байна!\n💡 `{ctx.prefix}help {command_name}` - заавар харах"
        
    elif isinstance(error, AttributeError) and str(error).endswith("'NoneType' object has no attribute 'lower'"):
        command_name = ctx.command.name if ctx.command else "энэ команд"
        error_embed.description = f"❌ **{command_name}** - хоосон утга оруулсан байна!"
        
    elif isinstance(error, commands.CommandOnCooldown):
        cooldown_time = int(error.retry_after)
        message = await ctx.send(f"⏳ Энэ командыг дахин ашиглахын тулд `{cooldown_time}` секунд хүлээнэ үү.")
        while cooldown_time > 0:
            await asyncio.sleep(1)
            cooldown_time -= 1
            try:
                await message.edit(content=f"⏳ Энэ командыг дахин ашиглахын тулд `{cooldown_time}` секунд хүлээнэ үү.")
            except (discord.NotFound, discord.HTTPException):
                break
        try:
            await message.edit(content="✅ Одоо энэ командыг дахин ашиглаж болно!")
        except (discord.NotFound, discord.HTTPException):
            pass
        return
        
    elif isinstance(error, commands.MissingPermissions):
        missing_perms = []
        for perm in error.missing_permissions:
            translated_perm = {
                "kick_members": "хөөх", "ban_members": "бандах", "administrator": "админ",
                "manage_channels": "суваг удирдах", "manage_guild": "сервер удирдах",
                "manage_messages": "мессеж удирдах", "manage_roles": "роль удирдах"
            }.get(perm, perm.replace("_", " "))
            missing_perms.append(f"`{translated_perm}`")
            
        error_embed.description = f"❌ Танд эрх хүрэлцэхгүй: {', '.join(missing_perms)}"
        
    elif isinstance(error, commands.BotMissingPermissions):
        missing_perms = []
        for perm in error.missing_permissions:
            translated_perm = {
                "kick_members": "хөөх", "ban_members": "бандах", "administrator": "админ",
                "manage_channels": "суваг удирдах", "manage_guild": "сервер удирдах",
                "manage_messages": "мессеж удирдах", "manage_roles": "роль удирдах"
            }.get(perm, perm.replace("_", " "))
            missing_perms.append(f"`{translated_perm}`")
            
        error_embed.description = f"❌ Ботд эрх хүрэлцэхгүй: {', '.join(missing_perms)}"
        
    elif isinstance(error, commands.MemberNotFound):
        error_embed.description = "❌ Хэрэглэгч олдсонгүй!"
        
    elif isinstance(error, commands.ChannelNotFound):
        error_embed.description = "❌ Суваг олдсонгүй!"
        
    elif isinstance(error, commands.RoleNotFound):
        error_embed.description = "❌ Роль олдсонгүй!"
        
    elif str(error) == "Channel not enabled for commands.":
        await send_channel_permission_error(ctx)
        return
    
    else:
        # Алдааны мэдээллийг логдох
        error_embed.description = "⚠️ Алдаа гарлаа. Админтай холбогдоно уу."
        logging.error(f"Алдаа: {ctx.command} - {error}")
        logging.error(traceback.format_exc())

    try:
        # Алдааны мессеж илгээх
        message = await ctx.send(embed=error_embed)
        # 7 секундын дараа мессежийг устгах
        await asyncio.sleep(7)
        await message.delete()
    except discord.Forbidden:
        pass
    except Exception as send_error:
        logger.error(f"Алдааны мессеж илгээхэд алдаа: {send_error}")

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

@bot.command(name='rate_status')
@commands.is_owner()
async def rate_limit_status(ctx: commands.Context):
    """Rate limit статусыг шалгах (owner only)"""
    global last_rate_limit_time
    if last_rate_limit_time:
        time_since_limit = (datetime.now() - last_rate_limit_time).total_seconds() / 60
        if time_since_limit < RATE_LIMIT_RESET_TIME:
            remaining = RATE_LIMIT_RESET_TIME - time_since_limit
            embed = discord.Embed(
                title="⚠️ Rate Limit Статус",
                description=f"Rate limit дээр байна.\n⏰ {remaining:.1f} минут үлдсэн.",
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title="✅ Rate Limit Статус", 
                description="Rate limit арилсан. Бүх систем хэвийн ажиллаж байна.",
                color=discord.Color.green()
            )
            last_rate_limit_time = None
    else:
        embed = discord.Embed(
            title="✅ Rate Limit Статус",
            description="Rate limit байхгүй. Бүх систем хэвийн ажиллаж байна.",
            color=discord.Color.green()
        )
    await ctx.send(embed=embed)

# --- Custom error handlers ---

async def send_channel_permission_error(ctx: commands.Context):
    error_embed = discord.Embed(color=discord.Color.red())
    error_embed.set_author(name="❌ Алдаа")
    error_embed.description = "❌ Энэ сувгаар команд ашиглах боломжгүй!"
    try:
        message = await ctx.send(embed=error_embed)
        await asyncio.sleep(7)
        await message.delete()
    except Exception:
        pass

# --- DM Relay (Direct DM chat) ---
# Set the admin/owner user ID for DM relay
DM_ADMIN_ID = 751055793893146624  # Change to your Discord ID if needed

dm_chat_map = {}  # user_id <-> last message id

@bot.event
async def on_message(message: discord.Message):
    # Prevent recursion for bot's own messages
    if message.author.bot:
        return
    # 1. User sends DM to bot
    if isinstance(message.channel, discord.DMChannel):
        # If message is from admin, relay to last user
        if message.author.id == DM_ADMIN_ID:
            # If admin replies to a DM, relay to the original user
            if message.reference and message.reference.message_id:
                for user_id, msg_id in dm_chat_map.items():
                    if msg_id == message.reference.message_id:
                        user = bot.get_user(user_id)
                        if user:
                            files = [await a.to_file() for a in message.attachments] if message.attachments else []
                            if files:
                                await user.send(f"👤 Админ: {message.content}", files=files)
                            else:
                                await user.send(f"👤 Админ: {message.content}")
                        break
            return
        # If message is from a user, relay to admin
        admin = bot.get_user(DM_ADMIN_ID)
        if admin:
            files = [await a.to_file() for a in message.attachments] if message.attachments else []
            if files:
                sent = await admin.send(f"✉️ {message.author} (ID: {message.author.id}):\n{message.content}", files=files)
            else:
                sent = await admin.send(f"✉️ {message.author} (ID: {message.author.id}):\n{message.content}")
            # Store mapping for reply
            dm_chat_map[message.author.id] = sent.id
        return
    # 2. If admin replies to a DM in their own DM channel
    if message.guild is None and message.author.id == DM_ADMIN_ID:
        if message.reference and message.reference.message_id:
            for user_id, msg_id in dm_chat_map.items():
                if msg_id == message.reference.message_id:
                    user = bot.get_user(user_id)
                    if user:
                        files = [await a.to_file() for a in message.attachments] if message.attachments else []
                        if files:
                            await user.send(f"👤 Админ: {message.content}", files=files)
                        else:
                            await user.send(f"👤 Админ: {message.content}")
                    break
        return
    await bot.process_commands(message)

# Rate limit monitoring
last_rate_limit_time = None

async def check_rate_limit_status():
    """Rate limit статусыг шалгах"""
    global last_rate_limit_time
    if last_rate_limit_time:
        time_since_limit = (datetime.now() - last_rate_limit_time).total_seconds() / 60
        if time_since_limit < RATE_LIMIT_RESET_TIME:
            remaining = RATE_LIMIT_RESET_TIME - time_since_limit
            print(f"⚠️ Rate limit дээр байна. {remaining:.1f} минут үлдсэн.")
            return False
        else:
            print("✅ Rate limit арилсан.")
            last_rate_limit_time = None
    return True

# Run the bot with rate limit protection
if TOKEN is None:
    raise ValueError("DISCORD_BOT_TOKEN environment variable is not set.")

try:
    print("🚀 Бот эхэлж байна...")
    bot.run(TOKEN)
except discord.HTTPException as e:
    if e.status == 429:
        print(f"❌ Rate limit-ээс болж бот эхлэж чадсангүй. {RATE_LIMIT_RESET_TIME} минут хүлээж дахин оролдоно уу.")
        print(f"💡 Зөвлөгөө: Ботыг {RATE_LIMIT_RESET_TIME} минут унтрааж дахин асаана уу.")
    else:
        print(f"❌ HTTP алдаа: {e}")
except Exception as e:
    print(f"❌ Бот асахад алдаа: {e}")
    logger.error(f"Bot startup error: {e}")
