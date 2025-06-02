import discord
from discord.ext import commands

# Check if the user has admin permissions
def is_admin():
    async def predicate(ctx):
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
            
    @commands.command(name='post')
    @commands.has_permissions(administrator=True)  # Only allow admins to use this command
    async def announce(self, ctx, channel: discord.TextChannel, *, message: str):
        """Send an announcement to a specified channel with emojis."""
        try:
            # Create an embed for the announcement
            embed = discord.Embed(title="📢 ЗАРЛАЛ", description=message, color=0x00ff00)
            embed.set_footer(text=f"Зарлал гаргасан: {ctx.author.display_name}", icon_url=ctx.author.avatar.url)

            # Send the announcement to the specified channel
            await channel.send(f"||@everyone|| sorry for ping", embed=embed)
            await ctx.send(f"Зарлал амжилттай {channel.mention} суваг руу илгээгдлээ!")
        
        except discord.Forbidden:
            await ctx.send("Энэ суваг руу илгээх эрхгүй байна.")
        except discord.HTTPException:
            await ctx.send("Зарлал илгээхэд алдаа гарлаа. Дахин оролдоно уу.")
        except Exception as e:
            await ctx.send(f"Алдаа гарлаа: {str(e)}")

    @announce.error
    async def announce_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Танд энэ командыг ашиглах эрх байхгүй.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Суваг олоход алдаа гарлаа. Суваг ID эсвэл @Mention ашиглана уу.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Суваг болон зарлалын текстийг оруулах хэрэгтэй.")

async def setup(bot):
    await bot.add_cog(Admin(bot))