import discord
import asyncio
from discord.ext import commands
import random

class DatingEvent(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.male_participants = []
        self.female_participants = []

    @commands.command(name="dating_start")
    async def dating_start(self, ctx):
        guild = ctx.guild
        categories = {"Event": ["Male Waiting", "Female Waiting"], "Date or Not": []}
        existing_categories = {c.name: c for c in guild.categories}

        for category, vcs in categories.items():
            if category not in existing_categories:
                await ctx.send(f"⚠️ `{category}` категори сервер дээр байхгүй байна!")
            else:
                category_obj = existing_categories[category]
                existing_vcs = {c.name for c in category_obj.voice_channels}
                for vc in vcs:
                    if vc not in existing_vcs:
                        await ctx.send(f"⚠️ `{vc}` VC `{category}` категори дотор байхгүй байна!")

                if category == "Date or Not" and not category_obj.voice_channels:
                    await ctx.send("⚠️ `Date or Not` категорид ямар нэг VC байхгүй байна!")

        embed = discord.Embed(title="💖 Dating Event 💖", description="Та доорх товчлууруудыг ашиглан эвэнтэд оролцоно уу.", color=discord.Color.pink())
        view = DatingButtons(self)
        await ctx.send(embed=embed, view=view)

class DatingButtons(discord.ui.View):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    @discord.ui.button(label="❤️ Join", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        guild = interaction.guild
        male_role = discord.utils.get(guild.roles, name="Male")
        female_role = discord.utils.get(guild.roles, name="Female")

        if male_role in user.roles:
            if user.id not in self.cog.male_participants:
                self.cog.male_participants.append(user.id)
                await interaction.response.send_message(f"{user.mention} (Эрэгтэй) эвэнтэд нэгдлээ!", ephemeral=True)
            else:
                await interaction.response.send_message("Та аль хэдийн эвэнтэд нэгдсэн байна!", ephemeral=True)
        elif female_role in user.roles:
            if user.id not in self.cog.female_participants:
                self.cog.female_participants.append(user.id)
                await interaction.response.send_message(f"{user.mention} (Эмэгтэй) эвэнтэд нэгдлээ!", ephemeral=True)
            else:
                await interaction.response.send_message("Та аль хэдийн эвэнтэд нэгдсэн байна!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Та 'Male' эсвэл 'Female' рольтой байх шаардлагатай!", ephemeral=True)

    @discord.ui.button(label="💔 Leave", style=discord.ButtonStyle.red)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user.id in self.cog.male_participants:
            self.cog.male_participants.remove(user.id)
            await interaction.response.send_message(f"{user.mention} эвэнтээс гарлаа!", ephemeral=True)
        elif user.id in self.cog.female_participants:
            self.cog.female_participants.remove(user.id)
            await interaction.response.send_message(f"{user.mention} эвэнтээс гарлаа!", ephemeral=True)
        else:
            await interaction.response.send_message("Та эвэнтэд оролцоогүй байна!", ephemeral=True)

    @discord.ui.button(label="💌 Match", style=discord.ButtonStyle.blurple)
    async def match(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("⚠️ Энэ командыг зөвхөн админ эрхтэй хэрэглэгч ашиглаж болно!", ephemeral=True)
            return
        
        guild = interaction.guild
        event_category = discord.utils.get(guild.categories, name="Event")
        date_category = discord.utils.get(guild.categories, name="Date or Not")
        male_vc = discord.utils.get(event_category.voice_channels, name="Male Waiting")
        female_vc = discord.utils.get(event_category.voice_channels, name="Female Waiting")
        date_vcs = date_category.voice_channels if date_category else []
        
        if len(self.cog.male_participants) < 1 or len(self.cog.female_participants) < 1 or not date_vcs:
            await interaction.response.send_message("⚠️ Хос үүсгэхэд хангалттай хүн болон VC байхгүй байна!", ephemeral=True)
            return
        
        male = random.choice(self.cog.male_participants)
        female = random.choice(self.cog.female_participants)
        user1 = await interaction.client.fetch_user(male)
        user2 = await interaction.client.fetch_user(female)
        match_vc = random.choice(date_vcs)
        
        self.cog.male_participants.remove(male)
        self.cog.female_participants.remove(female)
        
        await interaction.response.send_message(f"💖 Хосууд: {user1.mention} 💕 {user2.mention} `{match_vc.name}` VC руу нэвтэрнэ үү!")
        
        await asyncio.sleep(60)
        await match_vc.send("❌ Хэрэв та болзоогоо цуцлахыг хүсвэл 'Reject' товч дарна уу.")
        
        def check(msg):
            return msg.content.lower() == "reject" and msg.channel == match_vc
        
        try:
            await interaction.client.wait_for("message", check=check, timeout=60)
            await match_vc.send("⚠️ Болзоо цуцлагдлаа! Шинэ хамтрагч хайж байна...")
            await asyncio.sleep(5)
            await self.match(interaction, button)
        except asyncio.TimeoutError:
            await match_vc.send("⌛ Танилцах хугацаа дууслаа!")

async def setup(bot):
    bot.add_cog(DatingEvent(bot))