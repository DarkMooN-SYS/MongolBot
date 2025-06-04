import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
from typing import Literal

DB_FILE = "disabled_channels.db"

# === COG ===
class ChannelControl(commands.Cog):
    def __init__(self, bot: commands.Bot):
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

    async def get_guild_prefix(self, guild_id: int) -> str:
        """Серверийн prefix-г bot.db-с авах"""
        try:
            async with aiosqlite.connect('bot.db') as db:
                async with db.execute(
                    'SELECT prefix FROM guilds WHERE guild_id = ?',
                    (str(guild_id),)
                ) as cursor:
                    result = await cursor.fetchone()
                    return result[0] if result else 'm'  # Default prefix m болгов
        except Exception as e:
            print(f"[!] Префикс авахад алдаа гарлаа: {e}")
            return 'm'  # Error үед мөн m prefix буцаана

    # ✅ SLASH COMMAND
    @app_commands.command(name="channel", description="Сувгийг идэвхжүүлэх/идэвхгүй болгох")
    @app_commands.describe(
        action="Сонголт: Идэвхжүүлэх эсвэл Идэвхгүй болгох",
        target="Бүх суваг (all) эсвэл тодорхой нэг суваг сонгоно"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="✅ Идэвхжүүлэх", value="enable"),
        app_commands.Choice(name="❌ Идэвхгүй болгох", value="disable")
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def channel_control(self, interaction: discord.Interaction, action: Literal["enable", "disable"], target: str):
        # Даруй хариу өгөх
        await interaction.response.defer()

        try:
            guild = interaction.guild
            if not guild:
                return await interaction.followup.send("❌ Энэ команд зөвхөн сервер дээр ажиллана")

            if target.lower() == "all":
                # Нэг мөр мэдээлэл өгөх
                await interaction.followup.send("⏳ Сувгуудыг шалгаж байна...")
                
                changed = 0
                failed = 0
                
                for channel in guild.channels:
                    if isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
                        try:
                            # Зөвхөн чат сувгуудыг өөрчлөх
                            if action == "disable":
                                await self.disable_channel(guild.id, channel.id)
                            else:
                                await self.enable_channel(guild.id, channel.id)
                            changed += 1
                        except:
                            failed += 1
                            continue

                status = "хаагдлаа" if action == "disable" else "нээгдлээ"
                return await interaction.edit_original_response(
                    content=f"✅ {changed} суваг {status}"
                )

            # Нэг суваг өөрчлөх
            if target.startswith("<#") and target.endswith(">"):
                try:
                    channel_id = int(target[2:-1])
                    channel = guild.get_channel(channel_id)

                    if not channel:
                        return await interaction.followup.send("❌ Суваг олдсонгүй")

                    if action == "disable":
                        await self.disable_channel(guild.id, channel.id)
                        msg = f"✅ {channel.mention} суваг хаагдлаа"
                    else:
                        await self.enable_channel(guild.id, channel.id)
                        msg = f"✅ {channel.mention} суваг нээгдлээ"

                    return await interaction.followup.send(msg)

                except ValueError:
                    return await interaction.followup.send("❌ Буруу суваг")

            await interaction.followup.send("❌ `/channel enable #channel` эсвэл `/channel disable all` гэж бичнэ үү")

        except Exception as e:
            await interaction.followup.send(f"❌ Алдаа гарлаа: {str(e)}")

    # ✅ BLOCK MESSAGE
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Мессеж бичих үеийн шалгалт:
        - Хэрэв энгийн текст бол зөвшөөрнө
        - Хэрэв команд бол, идэвхгүй сувагт блоклоно
        """
        if message.guild and not message.author.bot:
            # Админ эсвэл owner-г шалгах
            is_admin = isinstance(message.author, discord.Member) and (
                message.author.guild_permissions.administrator or 
                await self.bot.is_owner(message.author)
            )
            
            # Серверийн prefix-г авах
            prefix = await self.get_guild_prefix(message.guild.id)
            
            # Команд мөн эсэхийг шалгах 
            is_command = message.content.startswith((prefix, '/', '>', 'M', 'm'))  # M, m prefix нэмэв
            
            if not is_command:
                return
                
            is_disabled = await self.is_channel_disabled(message.guild.id, message.channel.id)
            
            if is_disabled and not is_admin:
                try:
                    await message.delete()
                    await message.channel.send(
                        "🚫 Уучлаарай, энэ суваг дээр команд ашиглах боломжгүй байна.", 
                        delete_after=5
                    )
                except:
                    pass
                return

# ✅ SETUP
async def setup(bot: commands.Bot):
    """Cog-ийг ачаалах"""
    await bot.add_cog(ChannelControl(bot))
    print("[✔] Сувгийн удирдлагын систем амжилттай ачаалагдлаа")
