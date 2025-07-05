import discord
from discord.ext import commands
from discord.ext.commands import Context, Bot
import requests
from googletrans import Translator
import re
from typing import Callable

# Rate limiting system import хийх
from ..utils.rate_limit_decorators import rate_limit_command, RateLimitContext

ALLOWED_GUILD_IDS = {1354106084037759007, 1297446169995251712}
ANILIST_API_URL = "https://graphql.anilist.co"


class Anime(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.translator = Translator()

    def clean_html(self, text: str) -> str:
        if not text:
            return ''
        # <br> болон бусад HTML тагуудыг арилгана
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'<.*?>', '', text)
        # Илүүдэл олон зайг нэг болгох
        text = re.sub(r'\s+', ' ', text)
        # . , : ; ? ! тэмдэгтийн дараах зайг зөв болгох
        text = re.sub(r'([.,:;?!])(?=[^\s])', r'\1 ', text)
        # Олон мөрийн таслалыг зөв болгох
        text = re.sub(r'\n+', '\n', text)
        return text.strip()

    @commands.command(name="search")
    @rate_limit_command()  # Rate limiting нэмэх
    async def anime_or_character_search(self, ctx: Context, search_type: str, *, name: str):
        """
        Анимэ, дүр, эсвэл кино хайх (AniList API)
        Ашиглах: !search anime <нэр> | !search character <нэр> | !search movie <нэр>
        """
        if ctx.guild is None or ctx.guild.id not in ALLOWED_GUILD_IDS:
            await ctx.send("❌ Энэ команд зөвхөн зөвшөөрөгдсөн серверүүдэд ажиллана.")
            return
        async with ctx.typing():
            try:
                if search_type.lower() == "anime":
                    query = '''
                    query ($search: String) {
                      Page(perPage: 5) {
                        media(search: $search, type: ANIME) {
                          id
                          title { romaji english native }
                          description(asHtml: false)
                          coverImage { large }
                          siteUrl
                          popularity
                        }
                      }
                    }
                    '''
                    variables = {"search": name}
                    response = requests.post(ANILIST_API_URL, json={"query": query, "variables": variables}, timeout=10)
                    data = response.json()
                    results = data.get('data', {}).get('Page', {}).get('media', [])
                    if not results:
                        await ctx.send(f"\u274C '{name}' нэртэй анимэ олдсонгүй.")
                        return
                    # popularity бага байх тусам алдартай
                    results.sort(key=lambda a: a.get('popularity', float('inf')))
                    if len(results) > 1:
                        class AnimeSelect(discord.ui.Select):
                            def __init__(self, animes: list, author_id: int, translator: Translator, clean_html: Callable[[str], str]):
                                options = [
                                    discord.SelectOption(label=a['title'].get('romaji', 'No Title')[:100], description=(clean_html(a.get('description', ''))[:90] or 'No description.'), value=str(idx))
                                    for idx, a in enumerate(animes)
                                ]
                                super().__init__(placeholder="Анимэ сонгоно уу...", min_values=1, max_values=1, options=options)
                                self.animes = animes
                                self.author_id = author_id
                                self.translator = translator
                                self.clean_html = clean_html
                            async def callback(self, interaction: discord.Interaction):
                                if interaction.user.id != self.author_id:
                                    await interaction.response.send_message("❌ Зөвхөн команд бичсэн хүн сонгож болно!", ephemeral=True)
                                    return
                                idx = int(self.values[0])
                                anime = self.animes[idx]
                                title = anime['title'].get('romaji', 'No Title')
                                url = anime.get('siteUrl', None)
                                desc = self.clean_html(anime.get('description', 'No description.'))
                                embed = discord.Embed(title=title, url=url, description=desc, color=discord.Color.purple())
                                img = anime.get('coverImage', {}).get('large')
                                if img:
                                    embed.set_thumbnail(url=img)
                                view = TranslateButtonView(self.translator, desc, self.author_id)
                                await interaction.response.edit_message(embed=embed, view=view)
                        class AnimeSelectView(discord.ui.View):
                            def __init__(self, animes: list, author_id: int, translator: Translator, clean_html: Callable[[str], str], timeout: int = 60):
                                super().__init__(timeout=timeout)
                                self.add_item(AnimeSelect(animes, author_id, translator, clean_html))
                        await ctx.send("Тохирох анимэ сонгоно уу:", view=AnimeSelectView(results, ctx.author.id, self.translator, self.clean_html))
                    else:
                        anime = results[0]
                        title = anime['title'].get('romaji', 'No Title')
                        url = anime.get('siteUrl', None)
                        desc = self.clean_html(anime.get('description', 'No description.'))
                        embed = discord.Embed(title=title, url=url, description=desc, color=discord.Color.purple())
                        img = anime.get('coverImage', {}).get('large')
                        if img:
                            embed.set_thumbnail(url=img)
                        view = TranslateButtonView(self.translator, desc, ctx.author.id)
                        await ctx.send(embed=embed, view=view)
                    return
                elif search_type.lower() == "character":
                    query = '''
                    query ($search: String) {
                      Page(perPage: 5) {
                        characters(search: $search) {
                          id
                          name { full native }
                          description
                          image { large }
                          siteUrl
                        }
                      }
                    }
                    '''
                    variables = {"search": name}
                    response = requests.post(ANILIST_API_URL, json={"query": query, "variables": variables}, timeout=10)
                    data = response.json()
                    results = data.get('data', {}).get('Page', {}).get('characters', [])
                    if not results:
                        await ctx.send(f"\u274C '{name}' нэртэй дүр олдсонгүй.")
                        return
                    results = [c for c in results if c.get('description') and c.get('description').strip()]
                    if not results:
                        await ctx.send(f"\u274C Тайлбаргүй дүрүүдийг харуулахгүй.")
                        return
                    if len(results) > 1:
                        class CharSelect(discord.ui.Select):
                            def __init__(self, chars: list, author_id: int, translator: Translator, clean_html: Callable[[str], str]):
                                options = [
                                    discord.SelectOption(label=c['name'].get('full', 'No Name')[:100], description=(clean_html(c.get('description', ''))[:90] or 'No description.'), value=str(idx))
                                    for idx, c in enumerate(chars)
                                ]
                                super().__init__(placeholder="Дүр сонгоно уу...", min_values=1, max_values=1, options=options)
                                self.chars = chars
                                self.author_id = author_id
                                self.translator = translator
                                self.clean_html = clean_html
                            async def callback(self, interaction: discord.Interaction):
                                if interaction.user.id != self.author_id:
                                    await interaction.response.send_message("❌ Зөвхөн команд бичсэн хүн сонгож болно!", ephemeral=True)
                                    return
                                idx = int(self.values[0])
                                char = self.chars[idx]
                                title = char['name'].get('full', 'No Name')
                                url = char.get('siteUrl', None)
                                desc = self.clean_html(char.get('description', 'No description.'))
                                embed = discord.Embed(title=title, url=url, description=desc, color=discord.Color.blue())
                                img = char.get('image', {}).get('large')
                                if img:
                                    embed.set_thumbnail(url=img)
                                view = TranslateButtonView(self.translator, desc, self.author_id)
                                await interaction.response.edit_message(embed=embed, view=view)
                        class CharSelectView(discord.ui.View):
                            def __init__(self, chars: list, author_id: int, translator: Translator, clean_html: Callable[[str], str], timeout: int = 60):
                                super().__init__(timeout=timeout)
                                self.add_item(CharSelect(chars, author_id, translator, clean_html))
                        await ctx.send("Тохирох дүр сонгоно уу:", view=CharSelectView(results, ctx.author.id, self.translator, self.clean_html))
                    else:
                        char = results[0]
                        title = char['name'].get('full', 'No Name')
                        url = char.get('siteUrl', None)
                        desc = self.clean_html(char.get('description', 'No description.'))
                        embed = discord.Embed(title=title, url=url, description=desc, color=discord.Color.blue())
                        img = char.get('image', {}).get('large')
                        if img:
                            embed.set_thumbnail(url=img)
                        view = TranslateButtonView(self.translator, desc, ctx.author.id)
                        await ctx.send(embed=embed, view=view)
                    return
                elif search_type.lower() == "movie":
                    query = '''
                    query ($search: String) {
                      Page(perPage: 5) {
                        media(search: $search, type: ANIME, format: MOVIE) {
                          id
                          title { romaji english native }
                          description(asHtml: false)
                          coverImage { large }
                          siteUrl
                          popularity
                        }
                      }
                    }
                    '''
                    variables = {"search": name}
                    response = requests.post(ANILIST_API_URL, json={"query": query, "variables": variables}, timeout=10)
                    data = response.json()
                    results = data.get('data', {}).get('Page', {}).get('media', [])
                    if not results:
                        await ctx.send(f"\u274C '{name}' нэртэй кино олдсонгүй.")
                        return
                    results.sort(key=lambda a: a.get('popularity', float('inf')))
                    if len(results) > 1:
                        class MovieSelect(discord.ui.Select):
                            def __init__(self, movies: list, author_id: int, translator: Translator, clean_html: Callable[[str], str]):
                                options = [
                                    discord.SelectOption(label=m['title'].get('romaji', 'No Title')[:100], description=(clean_html(m.get('description', ''))[:90] or 'No description.'), value=str(idx))
                                    for idx, m in enumerate(movies)
                                ]
                                super().__init__(placeholder="Кино сонгоно уу...", min_values=1, max_values=1, options=options)
                                self.movies = movies
                                self.author_id = author_id
                                self.translator = translator
                                self.clean_html = clean_html
                            async def callback(self, interaction: discord.Interaction):
                                if interaction.user.id != self.author_id:
                                    await interaction.response.send_message("❌ Зөвхөн команд бичсэн хүн сонгож болно!", ephemeral=True)
                                    return
                                idx = int(self.values[0])
                                movie = self.movies[idx]
                                title = movie['title'].get('romaji', 'No Title')
                                url = movie.get('siteUrl', None)
                                desc = self.clean_html(movie.get('description', 'No description.'))
                                embed = discord.Embed(title=title, url=url, description=desc, color=discord.Color.orange())
                                img = movie.get('coverImage', {}).get('large')
                                if img:
                                    embed.set_thumbnail(url=img)
                                view = TranslateButtonView(self.translator, desc, self.author_id)
                                await interaction.response.edit_message(embed=embed, view=view)
                        class MovieSelectView(discord.ui.View):
                            def __init__(self, movies: list, author_id: int, translator: Translator, clean_html: Callable[[str], str], timeout: int = 60):
                                super().__init__(timeout=timeout)
                                self.add_item(MovieSelect(movies, author_id, translator, clean_html))
                        await ctx.send("Тохирох кино сонгоно уу:", view=MovieSelectView(results, ctx.author.id, self.translator, self.clean_html))
                    else:
                        movie = results[0]
                        title = movie['title'].get('romaji', 'No Title')
                        url = movie.get('siteUrl', None)
                        desc = self.clean_html(movie.get('description', 'No description.'))
                        embed = discord.Embed(title=title, url=url, description=desc, color=discord.Color.orange())
                        img = movie.get('coverImage', {}).get('large')
                        if img:
                            embed.set_thumbnail(url=img)
                        view = TranslateButtonView(self.translator, desc, ctx.author.id)
                        await ctx.send(embed=embed, view=view)
                    return
                else:
                    await ctx.send("❌ Хайх төрөл буруу! 'anime', 'character', эсвэл 'movie' гэж бичнэ үү.")
                    return
            except Exception as e:
                await ctx.send(f"\u274C Алдаа гарлаа: {e}")


class TranslateButtonView(discord.ui.View):
    def __init__(self, translator: Translator, text: str, author_id: int, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.translator = translator
        self.text_en = text
        self.text_mn = None
        self.author_id = author_id
        self.translated = False

    @discord.ui.button(label="Монгол руу орчуулах", style=discord.ButtonStyle.primary)
    async def translate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Зөвхөн команд бичсэн хүн орчуулж болно!", ephemeral=True)
            return
        embed = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else None
        if not embed:
            await interaction.response.send_message("\u274C Орчуулах embed олдсонгүй!", ephemeral=True)
            return
        
        if not self.translated:
            try:
                # Simple translation without async complications
                import asyncio
                def sync_translate():
                    return self.translator.translate(self.text_en, src='en', dest='mn')
                
                # Run translation in thread to avoid blocking
                loop = asyncio.get_event_loop()
                translation_result = await loop.run_in_executor(None, sync_translate)
                
                self.text_mn = translation_result.text
                embed.description = self.text_mn
                button.label = "Англи руу буцаах"
                await interaction.response.edit_message(embed=embed, view=self)
                self.translated = True
            except Exception as e:
                await interaction.response.send_message(f"\u274C Орчуулга амжилтгүй: {e}", ephemeral=True)
        else:
            embed.description = self.text_en
            button.label = "Монгол руу орчуулах"
            await interaction.response.edit_message(embed=embed, view=self)
            self.translated = False


async def setup(bot: Bot):
    await bot.add_cog(Anime(bot))
