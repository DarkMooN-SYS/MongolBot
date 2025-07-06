import discord
from discord.ext import commands
from discord.ext.commands import Context, Bot
import requests
from googletrans import Translator
import re
from typing import Callable, Dict, List
import asyncio

# Rate limiting system import хийх
from ..utils.rate_limit_decorators import rate_limit_command, RateLimitContext

ALLOWED_GUILD_IDS = {1354106084037759007, 1297446169995251712}
ANILIST_API_URL = "https://graphql.anilist.co"

# Search configurations for different types
SEARCH_CONFIGS = {
    "anime": {
        "query": '''
        query ($search: String) {
          Page(perPage: 5) {
            media(search: $search, type: ANIME) {
              id
              title { 
                romaji 
                english 
                native 
              }
              description
              coverImage { 
                large 
              }
              siteUrl
              popularity
            }
          }
        }
        ''',
        "result_path": ["data", "Page", "media"],
        "color": discord.Color.purple(),
        "placeholder": "Анимэ сонгоно уу...",
        "not_found_msg": "анимэ олдсонгүй",
        "sort_key": lambda x: x.get('popularity', float('inf')),
        "title_key": lambda x: x['title'].get('romaji', 'No Title'),
        "url_key": lambda x: x.get('siteUrl', None),
        "image_key": lambda x: x.get('coverImage', {}).get('large')
    },
    "character": {
        "query": '''
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
        ''',
        "result_path": ["data", "Page", "characters"],
        "color": discord.Color.blue(),
        "placeholder": "Дүр сонгоно уу...",
        "not_found_msg": "дүр олдсонгүй",
        "sort_key": None,
        "title_key": lambda x: x['name'].get('full', 'No Name'),
        "url_key": lambda x: x.get('siteUrl', None),
        "image_key": lambda x: x.get('image', {}).get('large'),
        "filter_func": lambda results: [c for c in results if c.get('description') and c.get('description').strip()]
    },
    "movie": {
        "query": '''
        query ($search: String) {
          Page(perPage: 5) {
            media(search: $search, type: ANIME, format: MOVIE) {
              id
              title { 
                romaji 
                english 
                native 
              }
              description
              coverImage { 
                large 
              }
              siteUrl
              popularity
            }
          }
        }
        ''',
        "result_path": ["data", "Page", "media"],
        "color": discord.Color.orange(),
        "placeholder": "Кино сонгоно уу...",
        "not_found_msg": "кино олдсонгүй",
        "sort_key": lambda x: x.get('popularity', float('inf')),
        "title_key": lambda x: x['title'].get('romaji', 'No Title'),
        "url_key": lambda x: x.get('siteUrl', None),
        "image_key": lambda x: x.get('coverImage', {}).get('large')
    }
}


class UniversalSelect(discord.ui.Select):
    """Universal select menu for all search types"""
    
    def __init__(self, results: List[Dict], config: Dict, author_id: int, translator: Translator, clean_html: Callable[[str], str]):
        options = []
        for idx, item in enumerate(results):
            title = config["title_key"](item)[:100]
            description = (clean_html(item.get('description', ''))[:90] or 'No description.')
            options.append(discord.SelectOption(label=title, description=description, value=str(idx)))
        
        super().__init__(
            placeholder=config["placeholder"], 
            min_values=1, 
            max_values=1, 
            options=options
        )
        
        self.results = results
        self.config = config
        self.author_id = author_id
        self.translator = translator
        self.clean_html = clean_html

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Зөвхөн команд бичсэн хүн сонгож болно!", ephemeral=True)
            return
        
        idx = int(self.values[0])
        item = self.results[idx]
        
        title = self.config["title_key"](item)
        url = self.config["url_key"](item)
        desc = self.clean_html(item.get('description', 'No description.'))
        
        embed = discord.Embed(title=title, url=url, description=desc, color=self.config["color"])
        
        img = self.config["image_key"](item)
        if img:
            embed.set_thumbnail(url=img)
        
        view = TranslateButtonView(self.translator, desc, self.author_id)
        await interaction.response.edit_message(embed=embed, view=view)


class UniversalSelectView(discord.ui.View):
    """Universal view for all search types"""
    
    def __init__(self, results: List[Dict], config: Dict, author_id: int, translator: Translator, clean_html: Callable[[str], str], timeout: int = 60):
        super().__init__(timeout=timeout)
        self.add_item(UniversalSelect(results, config, author_id, translator, clean_html))


class TranslateButtonView(discord.ui.View):
    def __init__(self, translator: Translator, text: str, author_id: int, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.translator = translator
        self.text_en = text
        self.text_mn = None
        self.author_id = author_id
        self.translated = False
    
    def clean_translation_text(self, text: str) -> str:
        """Орчуулгын өмнө болон дараа текстийг цэвэрлэх"""
        if not text:
            return text
        
        try:
            # Эхний болон төгсгөлийн зайг арилгах
            text = text.strip()
            
            # Зөвхөн зайлшгүй цэвэрлэлт хийх
            # Олон дараалсан зайг нэг болгох
            text = re.sub(r'\s+', ' ', text)
            
            # Unicode кавычкуудыг энгийн болгох
            text = text.replace('"', '"').replace('"', '"')
            text = text.replace(''', "'").replace(''', "'")
            
            # Хэт урт текстийг товчлох (1000+ тэмдэгт)
            if len(text) > 1000:
                text = text[:950] + "..."
            
            return text.strip()
            
        except Exception as e:
            # Алдаа гарвал эх текстийг буцаах
            return text.strip() if text else ""
    
    def post_process_translation(self, text: str) -> str:
        """Орчуулгын дараа текстийг боловсруулах"""
        if not text:
            return text
        
        try:
            # Зөвхөн хамгийн чухал алдаануудыг засах
            simple_replacements = {
                'цаг хугацаа': 'цаг',
                'өөр ертөнц': 'өөр дэлхий',
                'гэрийн тоглоом': 'геймер',
                'бодит ертөнц': 'бодит дэлхий'
            }
            
            for wrong, correct in simple_replacements.items():
                text = text.replace(wrong, correct)
            
            return text.strip()
            
        except Exception:
            return text.strip() if text else ""

    @discord.ui.button(label="Монгол руу орчуулах", style=discord.ButtonStyle.primary)
    async def translate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Зөвхөн команд бичсэн хүн орчуулж болно!", ephemeral=True)
            return
        
        embed = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else None
        if not embed:
            await interaction.response.send_message("❌ Орчуулах embed олдсонгүй!", ephemeral=True)
            return
        
        if not self.translated:
            # Орчуулж байгаа тухай мэдэгдэх
            await interaction.response.defer()
            
            # Хялбар loading мэдэгдэл
            loading_msg = "🔄 Орчуулж байна..."
            try:
                # Орчуулгын өмнө текстийг цэвэрлэх
                clean_text = self.clean_translation_text(self.text_en)
                
                # Хэт богино текст бол орчуулахгүй
                if len(clean_text.strip()) < 10:
                    await interaction.followup.send("❌ Текст хэт богино байна.", ephemeral=True)
                    return
                
                # Run translation in thread to avoid blocking - хялбарчилсан
                def sync_translate():
                    try:
                        translator_instance = Translator()
                        
                        # Урт текстийн тохиолдолд товчлох (500+ тэмдэгт)
                        if len(clean_text) > 500:
                            # Урт текстийг товчлох
                            shortened_text = clean_text[:450] + "..."
                            result = translator_instance.translate(shortened_text, src='en', dest='mn')
                        else:
                            # Богино текст бол шууд орчуулах
                            result = translator_instance.translate(clean_text, src='en', dest='mn')
                        
                        return result
                            
                    except Exception as e:
                        # Орчуулга амжилтгүй бол эх текстийг буцаах
                        from types import SimpleNamespace
                        return SimpleNamespace(text=f"Орчуулга амжилтгүй: {clean_text}")
                
                # Timeout нэмэх (8 секунд)
                try:
                    loop = asyncio.get_event_loop()
                    translation_task = loop.run_in_executor(None, sync_translate)
                    translation_result = await asyncio.wait_for(translation_task, timeout=8.0)
                except asyncio.TimeoutError:
                    await interaction.followup.send("❌ Орчуулга хэт удаан байна. Дахин оролдоно уу.", ephemeral=True)
                    return
                except Exception as e:
                    await interaction.followup.send(f"❌ Орчуулга амжилтгүй: {str(e)[:100]}...", ephemeral=True)
                    return
                
                # Орчуулгын дараа текстийг боловсруулах
                translated_text = self.post_process_translation(translation_result.text)
                self.text_mn = translated_text
                embed.description = self.text_mn
                button.label = "Англи руу буцаах"
                await interaction.edit_original_response(embed=embed, view=self)
                self.translated = True
                
            except Exception as e:
                # Бүх бусад алдаанууд
                await interaction.followup.send(f"❌ Орчуулгад алдаа гарлаа: {str(e)[:50]}...", ephemeral=True)
        else:
            # Англи текстийг цэвэрлэн харуулах
            clean_english = self.clean_translation_text(self.text_en)
            embed.description = clean_english
            button.label = "Монгол руу орчуулах"
            await interaction.response.edit_message(embed=embed, view=self)
            self.translated = False


class Anime(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.translator = Translator()

    def clean_html(self, text: str) -> str:
        """HTML тагуудыг цэвэрлэх"""
        if not text:
            return ''
        
        # <br> болон бусад HTML тагуудыг арилгана
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'<.*?>', '', text)
        
        # Илүүдэл олон зайг нэг болгох
        text = re.sub(r'\s+', ' ', text)
        
        # Тэмдэгтийн дараах зайг зөв болгох
        text = re.sub(r'([.,:;?!])(?=[^\s])', r'\1 ', text)
        
        # Олон мөрийн таслалыг зөв болгох
        text = re.sub(r'\n+', '\n', text)
        
        return text.strip()

    async def _perform_search(self, search_type: str, name: str) -> List[Dict]:
        """API хүсэлт хийх"""
        config = SEARCH_CONFIGS.get(search_type.lower())
        if not config:
            raise ValueError(f"Дэмжигдээгүй хайлтын төрөл: {search_type}")
        
        variables = {"search": name}
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'MongolBot/1.0'
        }
        
        # Retry механизм нэмэх
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    ANILIST_API_URL, 
                    json={"query": config["query"], "variables": variables},
                    headers=headers,
                    timeout=15
                )
                
                # HTTP статус код шалгах
                if response.status_code == 500:
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(2)  # 2 секунд хүлээж дахин оролдох
                        continue
                    else:
                        raise requests.RequestException(f"AniList сервер алдаа (500). Түр зуур хүлээж дахин оролдоно уу.")
                
                response.raise_for_status()
                data = response.json()
                
                # GraphQL алдаа шалгах
                if 'errors' in data:
                    error_msgs = [err.get('message', 'Тодорхойгүй алдаа') for err in data['errors']]
                    raise requests.RequestException(f"GraphQL алдаа: {', '.join(error_msgs)}")
                
                # Navigate through nested path
                result_data = data
                for key in config["result_path"]:
                    result_data = result_data.get(key, {})
                
                if not isinstance(result_data, list):
                    return []
                
                results = result_data
                
                # Apply filter if exists
                if "filter_func" in config:
                    results = config["filter_func"](results)
                
                # Apply sorting if exists
                if config.get("sort_key"):
                    results.sort(key=config["sort_key"])
                
                return results
                
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    import time
                    time.sleep(1)
                    continue
                else:
                    raise requests.RequestException("AniList API хүсэлт timeout болсон")
            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2)
                    continue
                else:
                    raise requests.RequestException("AniList API-тай холбогдож чадсангүй")
            except Exception as e:
                if attempt < max_retries - 1:
                    import time
                    time.sleep(1)
                    continue
                else:
                    raise e
        
        return []

    async def _create_embed_for_item(self, item: Dict, config: Dict) -> discord.Embed:
        """Нэг зүйлийн embed үүсгэх"""
        title = config["title_key"](item)
        url = config["url_key"](item)
        desc = self.clean_html(item.get('description', 'No description.'))
        
        embed = discord.Embed(title=title, url=url, description=desc, color=config["color"])
        
        img = config["image_key"](item)
        if img:
            embed.set_thumbnail(url=img)
        
        return embed

    async def _handle_search_results(self, ctx: Context, results: List[Dict], config: Dict, name: str):
        """Хайлтын үр дүнг боловсруулах"""
        if not results:
            await ctx.send(f"❌ '{name}' нэртэй {config['not_found_msg']}.")
            return
        
        if len(results) == 1:
            # Нэг үр дүн байвал шууд харуулах
            embed = await self._create_embed_for_item(results[0], config)
            desc = self.clean_html(results[0].get('description', 'No description.'))
            view = TranslateButtonView(self.translator, desc, ctx.author.id)
            await ctx.send(embed=embed, view=view)
        else:
            # Олон үр дүн байвал сонголтын цэс харуулах
            message = f"Тохирох {config['not_found_msg'].replace('олдсонгүй', '')} сонгоно уу:"
            view = UniversalSelectView(results, config, ctx.author.id, self.translator, self.clean_html)
            await ctx.send(message, view=view)

    @commands.command(name="search")
    @rate_limit_command()
    async def anime_or_character_search(self, ctx: Context, search_type: str, *, name: str):
        """
        Анимэ, дүр, эсвэл кино хайх (AniList API)
        Ашиглах: !search anime <нэр> | !search character <нэр> | !search movie <нэр>
        """
        # Зөвшөөрөгдсөн серверийн шалгалт
        if ctx.guild is None or ctx.guild.id not in ALLOWED_GUILD_IDS:
            await ctx.send("❌ Энэ команд зөвхөн зөвшөөрөгдсөн серверүүдэд ажиллана.")
            return
        
        # Хүчинтэй хайлтын төрөл эсэхийг шалгах
        if search_type.lower() not in SEARCH_CONFIGS:
            valid_types = ", ".join(f"'{t}'" for t in SEARCH_CONFIGS.keys())
            await ctx.send(f"❌ Хайх төрөл буруу! {valid_types} гэж бичнэ үү.")
            return
        
        async with ctx.typing():
            try:
                config = SEARCH_CONFIGS[search_type.lower()]
                results = await self._perform_search(search_type, name)
                await self._handle_search_results(ctx, results, config, name)
                
            except requests.RequestException as e:
                error_msg = str(e)
                if "500" in error_msg:
                    await ctx.send("❌ AniList серверт түр зуурын алдаа гарлаа. Хэдэн минутын дараа дахин оролдоно уу.")
                elif "timeout" in error_msg.lower():
                    await ctx.send("❌ Хүсэлт удаан байна. Интернет холболтоо шалгаж дахин оролдоно уу.")
                elif "connection" in error_msg.lower():
                    await ctx.send("❌ AniList API-тай холбогдож чадсангүй. Та интернет холболтоо шалгана уу.")
                else:
                    await ctx.send(f"❌ API алдаа: {error_msg}")
            except Exception as e:
                await ctx.send(f"❌ Алдаа гарлаа: {e}")
                # Debug мэдээллийг log-д бичих
                import traceback
                print(f"Anime search алдаа: {traceback.format_exc()}")


async def setup(bot: Bot):
    await bot.add_cog(Anime(bot))
