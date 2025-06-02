import asyncio
import aiosqlite
import os
import discord
from discord.ext import commands
import logging
import traceback
from dotenv import load_dotenv
import sqlite3
import time
from discord.ext import commands
import random
from channel import globally_block_disabled_channels


# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Set up logging
logging.basicConfig(level=logging.WARNING)  # INFO биш, WARNING л бичих

discord.utils.setup_logging(level=logging.INFO)

logger = logging.getLogger(__name__)

# Intents
intents = discord.Intents.all()
intents.members = True
intents.presences = True
intents.message_content = True

# Bot prefix
prefix = "M"

# Create bot instance
async def get_prefix(bot, message):
    return [prefix.lower(), prefix.upper()]  # Том жижиг үсэг ялгахгүйгээр 2 хувилбараар буцаана

activity = discord.Activity(type=discord.ActivityType.playing, name="mhelp")
bot = commands.Bot(command_prefix=get_prefix, case_insensitive=True, intents=intents, activity=activity)
bot.add_check(globally_block_disabled_channels)

bot.owner_id = 751055793893146624  # Change this to your Discord ID

@bot.event
async def on_ready():
    extensions = ['vip', 'report', 'admin', 'fun', 'birthday', 'giveaway', 'horseracing', 
                  'help', 'Owner', 'buh', 'economy', 'bank', 'game', 'suggest', 'count',
                  'support']

    # Бусад когиудыг ачаалах
    for extension in extensions:
        try:
            await bot.load_extension(extension)
            logging.info(f"✅ Ачаалсан: {extension}")
        except Exception as e:
            logging.error(f"🚨 Ачаалж чадсангүй: {extension} - {e}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("🚨 Шаардлагатай аргумент дутуу байна.")
    elif isinstance(error, commands.CommandOnCooldown):
        cooldown_time = int(error.retry_after)
        message = await ctx.send(f"⏳ Энэ командыг дахин ашиглахын тулд ``{cooldown_time}`` секунд хүлээнэ үү.")
        while cooldown_time > 0:
            await asyncio.sleep(1)
            cooldown_time -= 1
            await message.edit(content=f"⏳ Энэ командыг дахин ашиглахын тулд ``{cooldown_time}`` секунд хүлээнэ үү.")
        await message.edit(content="✅ Одоо энэ командыг дахин ашиглаж болно!")

    else:
        logging.error(f"⚠️ Алдаа: {error}")

bot.remove_command("help")

# Define the dm command
@bot.command(name='dm')
@commands.cooldown(1, 5, commands.BucketType.user)
async def dm(ctx, target: str, *, message: str):
    """Хэрэглэгчийн ID, суваг ID, эсвэл суваг дурдах ашиглан мессеж илгээх"""
    try:
        # Хэрэглэгч эсвэл суваг шалгах
        if target.isdigit():
            target_id = int(target)
            user = bot.get_user(target_id)
            channel = bot.get_channel(target_id)

            if user:
                # Хэрэглэгч рүү DM илгээх
                await user.send(message)
                confirmation = await ctx.send(f"Мессеж {user.name} рүү амжилттай илгээгдлээ.")
            elif channel:
                # Суваг руу мессеж илгээх
                await channel.send(message)
                confirmation = await ctx.send(f"Мессеж {channel.name} суваг руу амжилттай илгээгдлээ.")
            else:
                confirmation = await ctx.send("Хэрэглэгч эсвэл суваг олдсонгүй.")
        elif target.startswith("<#") and target.endswith(">"):
            # Суваг дурдах ашигласан тохиолдолд
            channel_id = int(target.strip("<#>"))
            channel = bot.get_channel(channel_id)
            if channel:
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
async def list_guilds(ctx):
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
async def set_prefix_command(ctx, new_prefix: str):
    await ctx.send(f"Command prefix set to {new_prefix}")

# Run the bot
bot.run(TOKEN)