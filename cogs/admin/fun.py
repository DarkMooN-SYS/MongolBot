import discord
from discord import app_commands
from discord.ext import commands
import random
from cogs.utils.channel import is_channel_enabled

class PollView(discord.ui.View):
    def __init__(self, question: str, options: list[str], allow_new_options: bool, max_new_options: int, admin_id: int):
        super().__init__(timeout=None)
        self.question = question
        self.votes = {option: 0 for option in options}
        self.voted_users = {}
        self.allow_new_options = allow_new_options
        self.max_new_options = max_new_options
        self.admin_id = admin_id
        self.new_options_count = 0

        for option in options:
            button = discord.ui.Button(label=option, style=discord.ButtonStyle.primary, custom_id=option)
            button.callback = self.vote_callback
            self.add_item(button)

        if self.allow_new_options:
            self.add_option_button = discord.ui.Button(label="➕ Шинэ сонголт нэмэх", style=discord.ButtonStyle.secondary)
            self.add_option_button.callback = self.add_option
            self.add_item(self.add_option_button)

    async def vote_callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        option = interaction.data.get('custom_id') if interaction.data else None

        if user_id in self.voted_users:
            await interaction.response.send_message("❌ Та аль хэдийн санал өгсөн байна!", ephemeral=True)
            return

        if option is None:
            return

        self.voted_users[user_id] = option
        self.votes[str(option)] += 1

        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def add_option(self, interaction: discord.Interaction):
        if self.new_options_count >= self.max_new_options:
            await interaction.response.send_message("❌ Дахин шинэ сонголт нэмэх боломжгүй!", ephemeral=True)
            return

        modal = OptionModal(self)
        await interaction.response.send_modal(modal)

    def get_embed(self):
        embed = discord.Embed(title="📊 Санал асуулга", description=self.question, color=discord.Color.blue())
        for opt, count in self.votes.items():
            embed.add_field(name=f"🔹 {opt}", value=f"{count} саналаар", inline=False)
        return embed

class OptionModal(discord.ui.Modal, title="Шинэ сонголт нэмэх"):
    def __init__(self, poll_view: 'PollView'):
        super().__init__()
        self.poll_view = poll_view

        self.option = discord.ui.TextInput(label="Таны нэмэх сонголт", placeholder="Сонголтоо бичнэ үү")
        self.add_item(self.option)

    async def on_submit(self, interaction: discord.Interaction):
        new_option = self.option.value.strip()

        if new_option in self.poll_view.votes:
            await interaction.response.send_message("❌ Энэ сонголт аль хэдийн байна!", ephemeral=True)
            return

        self.poll_view.new_options_count += 1
        button = discord.ui.Button(label=new_option, style=discord.ButtonStyle.primary, custom_id=new_option)
        button.callback = self.poll_view.vote_callback
        self.poll_view.add_item(button)
        self.poll_view.votes[new_option] = 0  

        embed = self.poll_view.get_embed()

        if self.poll_view.new_options_count >= self.poll_view.max_new_options:
            self.poll_view.remove_item(self.poll_view.add_option_button)

        await interaction.response.edit_message(embed=embed, view=self.poll_view)

class fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
            
    @commands.command(name="roll", help="1-с тодорхой тоо хүртэл санамсаргүй тоо шиднэ (анхдагч: 6).")
    async def roll(self, ctx: commands.Context, max_number: int = 6):
        if max_number < 1:
            await ctx.send("Хамгийн их тоо 1-ээс их байх ёстой.")
            return
        
        result = random.randint(1, max_number)
        await ctx.send(f"🎲 {ctx.author.mention} **1**-ээс **{max_number}** хүртэлх тоо\n **{result}** гэсэн тоог буулгасан!")


    @app_commands.command(name="poll", description="Санал асуулга үүсгэнэ.")
    async def poll(self, interaction: discord.Interaction, question: str, option1: str, option2: str, option3: str = "", option4: str = "", option5: str = "", option6: str = "", option7: str = "", option8: str = "", option9: str = "", option10: str = "", allow_new_options: bool = False, max_new_options: int = 0):
        options = [option1, option2, option3, option4, option5, option6, option7, option8, option9, option10]
        options = [opt for opt in options if opt]

        if len(options) < 2:
            await interaction.response.send_message("❌ Санал асуулга дор хаяж 2 сонголттой байх ёстой!", ephemeral=True)
            return

        admin_id = interaction.user.id
        view = PollView(question, options, allow_new_options, max_new_options, admin_id)
        self.poll_view = view  # Store the PollView instance for later access

        embed = view.get_embed()

        await interaction.response.send_message(embed=embed, view=view)

    @commands.command(name="end", help="Санал асуулгыг дуусгаж, эцсийн үр дүнг харуулна.")
    async def end(self, ctx: commands.Context):
        # Only allow poll creator (admin) or users with manage_guild permission to end
        if not hasattr(self, 'poll_view') or self.poll_view is None:
            await ctx.send("❌ Одоогоор идэвхтэй санал асуулга байхгүй байна!")
            return
        poll_view = self.poll_view
        # Check if the user is the poll creator or has manage_guild
        if ctx.author.id != poll_view.admin_id and (not isinstance(ctx.author, discord.Member) or not ctx.author.guild_permissions.manage_guild):
            await ctx.send("❌ Та санал асуулгыг дуусгах эрхгүй!")
            return
        # Disable all buttons
        for item in poll_view.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        embed = poll_view.get_embed()
        embed.title = "📊 Санал асуулга дууслаа!"
        await ctx.send(embed=embed)
        self.poll_view = None

    def cog_check(self, ctx: commands.Context) -> bool:
        # Only allow commands in guilds; channel enable check must be async elsewhere
        if not ctx.guild:
            return False
        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        # Async channel check here
        if ctx.guild is None or not await is_channel_enabled(ctx.guild.id, ctx.channel.id):
            await ctx.send("Энэ channel-д команд ашиглах боломжгүй!")
            raise commands.CheckFailure("Channel not enabled for commands.")

# To add the cog to your bot
async def setup(bot: commands.Bot):
    await bot.add_cog(fun(bot))
