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
activity = discord.Game(name="MongolBot - Discord Bot")  # Ботын үйл ажиллагаа
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
    'cogs.games.job',
    
    # Duel Games
    'cogs.duelgame.duelroll',
    
    
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
    
    # Discord HTTP client rate limiting патч хийх
    if patch_discord_http(bot):
        print("✅ Discord HTTP rate limiting идэвхжүүлэгдлээ")
    
    # Auto-configure rate limiting
    await auto_configure_rate_limiting()

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
    # Rate limit handling шинэчилсэн
    if isinstance(error, discord.HTTPException) and error.status == 429:
        global last_rate_limit_time
        last_rate_limit_time = datetime.now()
        
        # Response headers-ээс retry_after авах
        retry_after = getattr(error.response, 'headers', {}).get('Retry-After', '60')
        try:
            retry_after_seconds = float(retry_after)
        except (ValueError, TypeError):
            retry_after_seconds = 60
        
        # Global rate limit эсэхийг шалгах
        is_global = getattr(error.response, 'headers', {}).get('X-RateLimit-Global') == 'true'
        
        if is_global:
            # Global rate limiter-д мэдэгдэх
            set_global_limit(retry_after_seconds)
            rate_limit_message = f"🔴 Global rate limit! {int(retry_after_seconds)} секунд хүлээнэ үү."
            logger.error(f"Global rate limit: {retry_after_seconds}s")
        else:
            rate_limit_message = f"⚠️ Rate limit: {int(retry_after_seconds)} секунд хүлээж дахин оролдоно уу."
            logger.warning(f"Route rate limit on {ctx.command}: {retry_after_seconds}s")
        
        try:
            await ctx.send(rate_limit_message)
        except:
            logger.error("Rate limit message илгээж чадсангүй")
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

        error_embed.description = f"❌ **{translated_param}** дутуу байна!\n💡 `{ctx.prefix}help`, `{ctx.prefix}tutorial` - заавар харах"

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

# Rate limit statistics command нэмэх
@bot.command(name="ratelimit_stats", aliases=["rlstats"])
@commands.is_owner()
async def rate_limit_statistics(ctx: commands.Context):
    """Rate limit статистик харах (зөвхөн owner)"""
    try:
        from cogs.utils.rate_limiter import get_rate_limit_stats
        stats = get_rate_limit_stats()
        
        embed = discord.Embed(title="🚦 Rate Limit Статистик", color=0x00ff00)
        
        # Үндсэн статистик
        embed.add_field(
            name="📊 Нийт мэдээлэл",
            value=f"```\n"
                  f"Нийт хүсэлт: {stats['total_requests']}\n"
                  f"Блоклосон: {stats['total_blocked']}\n"
                  f"Блок хувь: {stats['block_rate_percent']:.1f}%\n"
                  f"Дундаж хүсэлт/сек: {stats['average_requests_per_second']:.1f}\n"
                  f"```",
            inline=False
        )
        
        # Одоогийн төлөв
        embed.add_field(
            name="⚡ Одоогийн төлөв",
            value=f"```\n"
                  f"Одоогийн дараалал: {stats['current_queue_size']}\n"
                  f"Хязгаар: {stats['requests_per_second_limit']}/сек\n"
                  f"Global limit: {'✅ Тийм' if stats['is_globally_limited'] else '❌ Үгүй'}\n"
                  f"Reset хүртэл: {stats['global_reset_in']:.1f}с\n"
                  f"```",
            inline=False
        )
        
        # Сүүлийн endpoint-ууд
        if stats['recent_endpoints']:
            recent = "\n".join(stats['recent_endpoints'][-5:])  # Сүүлийн 5
            embed.add_field(
                name="🔄 Сүүлийн endpoint-ууд",
                value=f"```\n{recent}\n```",
                inline=False
            )
        
        await ctx.send(embed=embed)
        
    except ImportError:
        await ctx.send("❌ Rate limiter систем олдсонгүй")
    except Exception as e:
        await ctx.send(f"❌ Статистик авахад алдаа: {e}")

# Rate limit monitoring харах команд
@bot.command(name="rate_monitor", aliases=["rm"])
@commands.is_owner()
async def rate_limit_monitoring(ctx: commands.Context):
    """Real-time rate limit мониторинг харах (зөвхөн owner)"""
    try:
        report = rate_limit_monitor.get_monitoring_report()
        recent_incidents = rate_limit_monitor.get_recent_incidents(5)
        
        embed = discord.Embed(title="📡 Real-time Rate Limit Monitor", color=0xFF5722)
        
        # Нийт мэдээлэл
        embed.add_field(
            name="📊 Нийт мэдээлэл",
            value=f"```\n"
                  f"Нийт тохиолдол: {report['total_incidents']}\n"
                  f"Мониторинг хугацаа: {report['monitoring_since'] or 'N/A'}\n"
                  f"```",
            inline=False
        )
        
        # Сүүлийн хугацааны статистик
        for period, data in report["periods"].items():
            period_name = {"last_minute": "Сүүлийн минут", "last_5_minutes": "Сүүлийн 5 минут", "last_hour": "Сүүлийн цаг"}.get(period, period)
            
            embed.add_field(
                name=f"⏰ {period_name}",
                value=f"```\n"
                      f"Тохиолдол: {data['count']}\n"
                      f"Global: {data['global_count']}\n"
                      f"Дундаж хүлээлт: {data['avg_retry_after']:.1f}с\n"
                      f"```",
                inline=True
            )
        
        # Сүүлийн тохиолдлууд
        if recent_incidents:
            incidents_text = "\n".join([
                f"{incident['method']} {incident['path'].split('/')[-1]} - {incident['retry_after']:.1f}с"
                for incident in recent_incidents
            ])
            embed.add_field(
                name="🚨 Сүүлийн 5 тохиолдол",
                value=f"```\n{incidents_text}\n```",
                inline=False
            )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Мониторинг мэдээлэл авахад алдаа: {e}")

# Rate limit түүх цэвэрлэх команд
@bot.command(name="clear_rate_history", aliases=["crh"])
@commands.is_owner()
async def clear_rate_limit_history(ctx: commands.Context):
    """Rate limit monitoring түүхийг цэвэрлэх (зөвхөн owner)"""
    try:
        rate_limit_monitor.clear_history()
        rate_limiter.reset_stats()
        await ctx.send("✅ Rate limit түүх болон статистик цэвэрлэгдлээ")
    except Exception as e:
        await ctx.send(f"❌ Алдаа гарлаа: {e}")

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

# Global rate limiting toggle команд
@bot.command(name="toggle_rate_limit", aliases=["trl"])
@commands.is_owner()
async def toggle_global_rate_limiting(ctx: commands.Context, enable: Optional[bool] = None):
    """Global rate limiting асааж/унтрааж (зөвхөн owner)"""
    try:
        from cogs.utils.rate_limiter import rate_limiter
        
        if enable is None:
            # Одоогийн төлөвийг харах
            stats = rate_limiter.get_stats()
            current_status = "✅ Асаалттай" if rate_limiter.max_requests_per_second < 50 else "❌ Унтраалттай"
            
            embed = discord.Embed(title="🚦 Global Rate Limiting", color=0x00ff00)
            embed.add_field(name="Одоогийн төлөв", value=current_status, inline=False)
            embed.add_field(name="Хязгаар", value=f"{rate_limiter.max_requests_per_second}/секунд", inline=True)
            embed.add_field(name="Нийт хүсэлт", value=f"{stats['total_requests']}", inline=True)
            embed.add_field(name="Блоклосон", value=f"{stats['total_blocked']}", inline=True)
            
            await ctx.send(embed=embed)
            return
        
        if enable:
            # Rate limiting асаах
            rate_limiter.max_requests_per_second = 45  # 50-ээс доош
            await ctx.send("✅ Global rate limiting асаагдлаа (45 хүсэлт/секунд)")
        else:
            # Rate limiting унтраах  
            rate_limiter.max_requests_per_second = 1000  # Их тоо (практикт унтраасан)
            await ctx.send("❌ Global rate limiting унтраагдлаа")
            
    except ImportError:
        await ctx.send("❌ Rate limiter систем олдсонгүй")
    except Exception as e:
        await ctx.send(f"❌ Алдаа гарлаа: {e}")

# Rate limit reset команд  
@bot.command(name="reset_rate_limit", aliases=["rrl"])
@commands.is_owner()
async def reset_rate_limiting(ctx: commands.Context):
    """Rate limiting статистикийг reset хийх (зөвхөн owner)"""
    try:
        from cogs.utils.rate_limiter import rate_limiter
        
        # Статистикийг reset хийх
        rate_limiter.reset_stats()
        
        # Global rate limit-ийг арилгах
        rate_limiter.is_globally_limited = False
        rate_limiter.global_reset_time = None
        
        global last_rate_limit_time
        last_rate_limit_time = None
        
        await ctx.send("✅ Rate limiting систем reset хийгдлээ")
        
    except ImportError:
        await ctx.send("❌ Rate limiter систем олдсонгүй")
    except Exception as e:
        await ctx.send(f"❌ Алдаа гарлаа: {e}")

# Safe message deletion команд  
@bot.command(name="clear_safe", aliases=["cs"])
@commands.has_permissions(manage_messages=True)
async def clear_messages_safe(ctx: commands.Context, amount: int = 10):
    """Rate limit-тай аюулгүй message устгах (админ зориулалт)"""
    if amount > 100:
        await ctx.send("❌ Дээд талаар 100 мессеж устгаж болно.")
        return
    
    try:
        from cogs.utils.discord_integration import safe_message_delete
        
        # Мессежүүдийг авах
        messages = []
        async for message in ctx.channel.history(limit=amount + 1):  # +1 for command message
            messages.append(message)
        
        deleted_count = 0
        
        # Rate limit-тай нэг бүрчлэн устгах
        for message in messages:
            try:
                await safe_message_delete(message)
                deleted_count += 1
                
                # Хооронд жижиг зай өгөх
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.warning(f"Мессеж устгахад алдаа: {e}")
                continue
        
        # Үр дүн мэдэгдэх (түр мессежээр)
        result_msg = await ctx.send(f"✅ {deleted_count} мессеж rate limit-тай аюулгүй устгагдлаа")
        await asyncio.sleep(3)
        await safe_message_delete(result_msg)
        
    except ImportError:
        await ctx.send("❌ Discord integration систем олдсонгүй")
    except Exception as e:
        await ctx.send(f"❌ Алдаа гарлаа: {e}")

# Discord rate limit статус харах команд
@bot.command(name="discord_status", aliases=["ds"])
@commands.is_owner()
async def discord_rate_limit_status(ctx: commands.Context):
    """Discord API rate limit статус харах (зөвхөн owner)"""
    try:
        from cogs.utils.rate_limiter import get_rate_limit_stats
        
        stats = get_rate_limit_stats()
        
        embed = discord.Embed(title="🌐 Discord API Rate Limit Status", color=0x5865F2)
        
        # Discord API мэдээлэл
        embed.add_field(
            name="📡 Discord API",
            value=f"```\n"
                  f"Latency: {bot.latency*1000:.0f}ms\n"
                  f"Guilds: {len(bot.guilds)}\n"
                  f"Users: {len(bot.users)}\n"
                  f"```",
            inline=True
        )
        
        # Rate limiting статистик
        embed.add_field(
            name="🚦 Rate Limiting",
            value=f"```\n"
                  f"Хязгаар: {rate_limiter.max_requests_per_second}/сек\n"
                  f"Одоогийн: {stats['current_queue_size']}\n"
                  f"Global limit: {'✅' if stats['is_globally_limited'] else '❌'}\n"
                  f"```",
            inline=True
        )
        
        # Сүүлийн мэдээлэл
        recent_endpoints = stats.get('recent_endpoints', [])
        if recent_endpoints:
            recent_text = '\n'.join(recent_endpoints[-5:])
            embed.add_field(
                name="🔄 Сүүлийн API хүсэлтүүд",
                value=f"```\n{recent_text}\n```",
                inline=False
            )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Статистик авахад алдаа: {e}")

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

# Global rate limiter дуудах
from cogs.utils.rate_limiter import rate_limiter, set_global_limit
from cogs.utils.discord_integration import patch_discord_http, safe_message_delete
from cogs.utils.rate_limit_monitor import rate_limit_monitor

# Rate limiting дэмжих global variables
last_rate_limit_time = None

# Rate limit checking функц
async def check_rate_limit_status():
    """Rate limit статус шалгах"""
    global last_rate_limit_time
    if last_rate_limit_time:
        time_since_limit = (datetime.now() - last_rate_limit_time).total_seconds() / 60
        if time_since_limit < RATE_LIMIT_RESET_TIME:
            remaining = RATE_LIMIT_RESET_TIME - time_since_limit
            logger.warning(f"⚠️ Rate limit идэвхтэй. {remaining:.1f} минут үлдсэн")
            return False
        else:
            logger.info("✅ Rate limit арилсан")
            last_rate_limit_time = None
    return True

# Auto-configure rate limiting on bot startup
async def auto_configure_rate_limiting():
    """Bot эхлэх үед rate limiting автоматаар тохируулах"""
    try:
        from cogs.utils.rate_limiter import rate_limiter
        
        # Server тоо болон хэрэглэгчдийн тооноос хамааруулж тохируулах
        total_members = sum(guild.member_count or 0 for guild in bot.guilds)
        guild_count = len(bot.guilds)
        
        # Автомат тохиргоо логик
        if guild_count == 0:
            # Серверт ороогүй бол conservative
            rate_limit = 30
        elif total_members > 50000:
            # Том серверууд (50k+ хэрэглэгч)
            rate_limit = 25
        elif total_members > 10000:
            # Дунд серверууд (10k+ хэрэглэгч)
            rate_limit = 30
        elif total_members > 1000:
            # Жижиг серверууд (1k+ хэрэглэгч)
            rate_limit = 35
        else:
            # Маш жижиг серверууд
            rate_limit = 40
        
        # Rate limit тохируулах
        rate_limiter.max_requests_per_second = rate_limit
        
        print(f"🚦 Rate Limiting автомат тохируулга:")
        print(f"   📊 {guild_count} сервер, {total_members} хэрэглэгч")
        print(f"   ⚙️ {rate_limit} хүсэлт/секунд тохируулагдлаа")
        
    except ImportError:
        print("⚠️ Rate limiter систем олдсонгүй")
    except Exception as e:
        print(f"⚠️ Rate limiting тохиргоонд алдаа: {e}")

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