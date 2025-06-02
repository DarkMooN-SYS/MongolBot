import discord
from discord.ext import commands

class StaffAppModal(discord.ui.Modal, title='Staff Application'):
    def __init__(self):
        super().__init__()
        self.username = discord.ui.TextInput(label='Username', style=discord.TextStyle.short)
        self.experience = discord.ui.TextInput(label='Experience', style=discord.TextStyle.paragraph)
        self.skills = discord.ui.TextInput(label='Skills', style=discord.TextStyle.paragraph)

        self.add_item(self.username)
        self.add_item(self.experience)
        self.add_item(self.skills)

    async def on_submit(self, interaction: discord.Interaction):
        username = self.username.value
        experience = self.experience.value
        skills = self.skills.value

        # Validate the input data
        if not username:
            await interaction.response.send_message('Please enter a username.', ephemeral=True)
            return
        if len(experience) > 500:
            await interaction.response.send_message('Experience cannot be longer than 500 characters.', ephemeral=True)
            return
        if len(skills) > 500:
            await interaction.response.send_message('Skills cannot be longer than 500 characters.', ephemeral=True)
            return

        try:
            await interaction.response.defer()
            await interaction.channel.send(f'Application received from {username}: {experience}, {skills}')
            await interaction.followup.send('Your application has been submitted successfully!', ephemeral=True)
        except discord.HTTPException:
            await interaction.followup.send('Error sending application.', ephemeral=True)

class Report(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='staff', help='Apply for a staff position')
    async def staff_app(self, ctx):
        if ctx.author.guild_permissions.administrator:
            embed = discord.Embed(title="Staff Application", description="Click the button below to apply for a staff position.")
            view = discord.ui.View(timeout=None)
            button = discord.ui.Button(label="Apply Now", style=discord.ButtonStyle.primary)
            button.callback = self.open_modal
            view.add_item(button)
            await ctx.send(embed=embed, view=view)
        else:
            await ctx.send("You don't have permission to use this command.")

    async def open_modal(self, interaction: discord.Interaction):
        modal = StaffAppModal()
        await interaction.response.send_modal(modal)

async def setup(bot):
    await bot.add_cog(Report(bot))