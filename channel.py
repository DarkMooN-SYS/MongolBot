import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite

DB_FILE = "disabled_channels.db"
PREFIX_DB = "prefixes.db"

# === GET PREFIX ===
async def get_prefix(bot, message):
    if not message.guild:
        return commands.when_mentioned_or("m", "M")(bot, message)

    try:
        async with aiosqlite.connect(PREFIX_DB) as db:
            async with db.execute("SELECT prefix FROM prefixes WHERE guild_id = ?", (str(message.guild.id),)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return commands.when_mentioned_or(row[0])(bot, message)
    except:
        pass

    return commands.when_mentioned_or("m", "M")(bot, message)

# === COG ===
class ChannelControl(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.setup_database())

    async def setup_database(self):
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS disabled_channels (
                    guild_id TEXT,
                    channel_id TEXT
                )
            """)
            await db.commit()

    async def disable_channel(self, guild_id: int, channel_id: int):
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute(
                "INSERT OR IGNORE INTO disabled_channels (guild_id, channel_id) VALUES (?, ?)",
                (str(guild_id), str(channel_id))
            )
            await db.commit()

    async def enable_channel(self, guild_id: int, channel_id: int):
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute(
                "DELETE FROM disabled_channels WHERE guild_id = ? AND channel_id = ?",
                (str(guild_id), str(channel_id))
            )
            await db.commit()

    async def is_channel_disabled(self, guild_id: int, channel_id: int) -> bool:
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute(
                "SELECT 1 FROM disabled_channels WHERE guild_id = ? AND channel_id = ?",
                (str(guild_id), str(channel_id))
            ) as cursor:
                return await cursor.fetchone() is not None

    # ✅ TEXT COMMAND
    @commands.command(name="channel")
    @commands.has_permissions(administrator=True)
    async def channel_command(self, ctx, action: str, target: str = None):
        await self.handle_channel_control(ctx, action, target)

    # ✅ SLASH COMMAND
    @app_commands.command(name="channel", description="Суваг идэвхжүүлэх эсвэл идэвхгүй болгох")
    @app_commands.describe(action="enable эсвэл disable", target="all эсвэл #channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_channel(self, interaction: discord.Interaction, action: str, target: str):
        await self.handle_channel_control(interaction, action, target)

    async def handle_channel_control(self, obj, action: str, target: str):
        is_interaction = isinstance(obj, discord.Interaction)
        guild = obj.guild
        author = obj.user if is_interaction else obj.author

        action = action.lower()
        if action not in ["enable", "disable"]:
            msg = "❌ Зөвхөн `enable` эсвэл `disable` гэж бичнэ үү."
            return await (obj.response.send_message(msg) if is_interaction else obj.send(msg))

        # === ALL CHANNELS ===
        if target == "all":
            changed = 0
            for channel in guild.channels:
                if isinstance(channel, (discord.TextChannel, discord.ForumChannel, discord.VoiceChannel, discord.StageChannel)):
                    overwrite = channel.overwrites_for(guild.me)
                    if isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
                        overwrite.send_messages = (action == "enable")
                    else:
                        overwrite.connect = (action == "enable")
                        overwrite.speak = (action == "enable")
                    try:
                        await channel.set_permissions(guild.me, overwrite=overwrite)
                        if action == "disable":
                            await self.disable_channel(guild.id, channel.id)
                        else:
                            await self.enable_channel(guild.id, channel.id)
                        changed += 1
                    except:
                        continue

            msg = f"✅ {changed} суваг{' идэвхгүй боллоо' if action == 'disable' else ' идэвхжлээ'}."
            return await (obj.response.send_message(msg) if is_interaction else obj.send(msg))

        # === ONE CHANNEL ===
        if target.startswith("<#") and target.endswith(">"):
            try:
                channel_id = int(target[2:-1])
                channel = guild.get_channel(channel_id)

                if not channel:
                    return await (obj.response.send_message("❌ Суваг олдсонгүй.") if is_interaction else obj.send("❌ Суваг олдсонгүй."))

                overwrite = channel.overwrites_for(guild.me)
                if isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
                    overwrite.send_messages = (action == "enable")
                else:
                    overwrite.connect = (action == "enable")
                    overwrite.speak = (action == "enable")

                await channel.set_permissions(guild.me, overwrite=overwrite)

                if action == "disable":
                    await self.disable_channel(guild.id, channel.id)
                else:
                    await self.enable_channel(guild.id, channel.id)

                msg = f"✅ {channel.mention} суваг {('идэвхгүй боллоо' if action == 'disable' else 'идэвхжлээ')}."
                return await (obj.response.send_message(msg) if is_interaction else obj.send(msg))
            except:
                msg = "❌ Суваг ID-д алдаа гарлаа."
                return await (obj.response.send_message(msg) if is_interaction else obj.send(msg))

        msg = "❌ Буруу формат. Жишээ: `!channel disable all`, `!channel enable #channel`"
        return await (obj.response.send_message(msg) if is_interaction else obj.send(msg))

    # ✅ BLOCK MESSAGE
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild and not message.author.bot:
            is_disabled = await self.is_channel_disabled(message.guild.id, message.channel.id)

            if is_disabled:
                ctx = await self.bot.get_context(message)

                # Зөвхөн команд бичсэн үед л шалгалт хийнэ
                if ctx.valid and ctx.command:
                    # Админ эсвэл owner бол зөвшөөр
                    if message.author.guild_permissions.administrator or await self.bot.is_owner(message.author):
                        await self.bot.process_commands(message)
                        return

                    # Зөвшөөрөгдсөн командууд
                    if ctx.command.name in ("channel", "mchannel"):
                        await self.bot.process_commands(message)
                        return

                    try:
                        await message.channel.send("🚫 Энэ суваг дээр команд ашиглах боломжгүй.")
                    except:
                        pass
                    return

        # Хэрвээ блок хийгдээгүй бол командыг ажиллуул
        await self.bot.process_commands(message)

# ✅ GLOBAL BLOCK
@commands.check
async def globally_block_disabled_channels(ctx):
    if ctx.guild and not ctx.author.bot:
        try:
            async with aiosqlite.connect(DB_FILE) as db:
                async with db.execute(
                    "SELECT 1 FROM disabled_channels WHERE guild_id = ? AND channel_id = ?",
                    (str(ctx.guild.id), str(ctx.channel.id))
                ) as cursor:
                    if await cursor.fetchone():
                        if ctx.command and ctx.command.name in ("channel", "mchannel"):
                            return True
                        try:
                            await ctx.send("🚫 Энэ суваг дээр команд ашиглах боломжгүй.")
                        except Exception as e:
                            print(f"[!] Мессеж илгээхэд алдаа гарлаа: {e}")
                        return False
        except Exception as e:
            print(f"[!] Глобал check-д алдаа гарлаа: {e}")
            return False
    return True

# ✅ SETUP
async def setup(bot):
    bot.add_check(globally_block_disabled_channels)
    await bot.add_cog(ChannelControl(bot))
    print("[✔] ChannelControl cog loaded, global check enabled")
