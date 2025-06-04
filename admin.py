import discord 
from discord import app_commands
from discord.ext import commands

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="post", description="Зарлал илгээх")
    @app_commands.describe(
        channel="Зарлал илгээх суваг",
        title="Зарлалын гарчиг", 
        message="Зарлалын үндсэн текст"
    )
    @app_commands.checks.has_permissions(administrator=True, manage_messages=True)
    async def post(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        message: str
    ):
        # Check if user has required permissions in target channel
        member = interaction.user if isinstance(interaction.user, discord.Member) else interaction.guild.get_member(interaction.user.id)
        if not member or not channel.permissions_for(member).send_messages:
            await interaction.response.send_message(
                "❌ Танд сонгосон суваг руу зарлал илгээх эрх байхгүй байна.",
                ephemeral=True
            )
            return

        try:
            # Create an embed for the announcement
            embed = discord.Embed(
                title=f"📢 {title}",
                description=message,
                color=0x00ff00
            )
            embed.set_footer(
                text=f"Мэдэгдэл гаргасан: {interaction.user.display_name}",
                icon_url=interaction.user.avatar.url if interaction.user.avatar else None
            )

            # Send the announcement
            await channel.send("||@everyone|| Sorry For Ping", embed=embed)
            await interaction.response.send_message(
                f"✅ Мэдэгдэл амжилттай {channel.mention} суваг руу илгээгдлээ!",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Ботод энэ суваг руу илгээх эрх байхгүй байна.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Алдаа гарлаа: {str(e)}",
                ephemeral=True
            )

    @post.error
    async def post_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            missing_perms = [perm.replace('_', ' ').title() for perm in error.missing_permissions]
            await interaction.response.send_message(
                f"❌ Танд дараах эрхүүд байхгүй байна:\n" + 
                "\n".join(f"• {perm}" for perm in missing_perms),
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Алдаа гарлаа: {str(error)}",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
    # Sync the commands with Discord
    await bot.tree.sync()