import discord
from discord.ext import commands
from typing import Dict, List
import asyncio

class Tutorial(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    @commands.command(name='tutorial')
    async def tutorial_main(self, ctx: commands.Context, *, section: str = ""):
        """MongolBot-ийн бүрэн заавар"""
        
        # Check if specific tutorial was requested by argument
        if section:
            section_lower = section.lower()
            if section_lower in ['1', 'beginner']:
                return await self.tutorial_beginner(ctx)
            elif section_lower in ['2', 'economy']:
                return await self.tutorial_economy(ctx)
            elif section_lower in ['3', 'games']:
                return await self.tutorial_games(ctx)
            elif section_lower in ['4', 'welcome']:
                return await self.welcome_message(ctx)
            elif section_lower in ['5', 'quickguide', 'quick']:
                return await self.quick_guide(ctx)
            elif section_lower in ['6', 'examples', 'example']:
                return await self.examples(ctx)
            elif section_lower in ['7', 'troubleshoot', 'trouble']:
                return await self.troubleshoot(ctx)
        
        embed = discord.Embed(
            title="🤖 MongolBot Заавар",
            description="Танд MongolBot-ийн бүх функцуудын заавар өгье!",
            color=discord.Color.blue()
        )
        
        # Tutorial categories
        categories = [
            "🔰 Эхлэгчдэд",
            "💰 Эдийн засаг", 
            "🎮 Тоглоомууд",
            "🎉 Анхны мэндчилгээ",
            "⚡ Хурдан лавлах",
            "📝 Хэрэглээний жишээ",
            "🔧 Асуудал шийдэх"
        ]
        
        embed.add_field(
            name="📋 Хэсгүүд",
            value="\n".join([f"{i+1}️⃣ {cat}" for i, cat in enumerate(categories)]),
            inline=False
        )
        
        embed.add_field(
            name="🎯 Хэрэглээ",
            value=(
                f"Доорх аргуудын аль нэгээр заавар авна уу:\n\n"
                f"`{ctx.prefix}tutorial beginner` - Эхлэгчдэд\n"
                f"`{ctx.prefix}tutorial economy` - Эдийн засаг\n"
                f"`{ctx.prefix}tutorial games` - Тоглоомууд\n"
                f"`{ctx.prefix}tutorial welcome` - Анхны мэндчилгээ\n"
                f"`{ctx.prefix}tutorial quickguide` - Хурдан лавлах\n"
                f"`{ctx.prefix}tutorial examples` - Хэрэглээний жишээ\n"
                f"`{ctx.prefix}tutorial troubleshoot` - Асуудал шийдэх\n\n"
                f"`{ctx.prefix}help` - Бүх командууд"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💰 Мөнгө олох хурдан зөвлөгөө",
            value=(
                f"**🎯 Өдөр тутмын зүйлс:**\n"
                f"• `{ctx.prefix}daily` - Өдөр бүр 5,000₮ авах\n"
                f"• `{ctx.prefix}deposit 1000` - Мөнгөө аюулгүй хадгалах\n\n"
                f"**🎮 Тоглоомын зөвлөмж:**\n"
                f"• `{ctx.prefix}cf 1000` - Анхлагчдад хялбар\n"
                f"• Бага дүнгээр эхэлж, аажмаар нэмэх\n"
                f"• VIP болвол илүү их боломж\n\n"
                f"**💎 Урт хугацааны зорилго:**\n"
                f"• Bronze VIP (22M₮) зорих\n"
                f"• Сугалааны тасалбар авах"
            ),
            inline=False
        )
        
        embed.set_footer(text="💡 Дэлгэрэнгүй мэдээлэл авахын тулд дээрх командуудыг ашиглана уу")
        
        await ctx.send(embed=embed)
    
    async def tutorial_beginner(self, ctx: commands.Context):
        """Эхлэгчдэд зориулсан заавар"""
        
        embeds = []
        
        # Page 1: Үндсэн мэдээлэл
        embed1 = discord.Embed(
            title="🔰 Эхлэгчдэд зориулсан заавар - 1/3",
            description="MongolBot-тай анх уулзаж байна уу? Энд бүх зайлшгүй мэдээллийг олно!",
            color=discord.Color.green()
        )
        
        embed1.add_field(
            name="📝 Үндсэн команд",
            value=(
                f"`{ctx.prefix}` - Командын эхлэл (prefix)\n"
                f"`{ctx.prefix}help` - Бүх командууд\n"
                f"`{ctx.prefix}balance` - Таны мөнгө\n"
                f"`{ctx.prefix}daily` - Өдөр бүрийн урамшуулал\n"
                f"`{ctx.prefix}tutorial` - Энэ заавар"
            ),
            inline=False
        )
        
        embed1.add_field(
            name="💰 Анхны мөнгө",
            value=(
                "• Анх нэгдэхэд 5,000₮ авна\n"
                f"• `{ctx.prefix}daily` - өдөр бүр 5,000₮\n"
                "• Тоглоом тоглож мөнгө олно\n"
                "• Бусад хүмүүстэй арилжаано"
            ),
            inline=False
        )
        
        embeds.append(embed1)
        
        # Page 2: Эдийн засгийн үндэс
        embed2 = discord.Embed(
            title="🔰 Эхлэгчдэд зориулсан заавар - 2/3", 
            description="Мөнгөтэй хэрхэн ажиллах талаар суралцая!",
            color=discord.Color.green()
        )
        
        embed2.add_field(
            name="🏦 Банк систем",
            value=(
                f"`{ctx.prefix}bank` - Банкны мэдээлэл\n"
                f"`{ctx.prefix}deposit 1000` - Мөнгө хадгалах\n"
                f"`{ctx.prefix}withdraw 1000` - Мөнгө авах\n"
                f"`{ctx.prefix}save 5000` - Хуримтлал үүсгэх\n"
                f"`{ctx.prefix}loan 1000` - Зээл авах"
            ),
            inline=False
        )
        
        embed2.add_field(
            name="💸 Мөнгө дамжуулах",
            value=(
                f"`{ctx.prefix}give @user 1000` - Бусдад өгөх\n"
                "• Анхаарах: Та зөвхөн өөрийн мөнгийг өгч болно\n"
                "• Банкнаас мөнгө гаргаж, дараа нь өгнө"
            ),
            inline=False
        )
        
        embeds.append(embed2)
        
        # Page 3: Анхны алхамууд
        embed3 = discord.Embed(
            title="🔰 Эхлэгчдэд зориулсан заавар - 3/3",
            description="Эхний алхмуудаа хийж MongolBot-ыг эзэмшье!",
            color=discord.Color.green()
        )
        
        embed3.add_field(
            name="🎯 Анхны алхамууд",
            value=(
                f"1️⃣ `{ctx.prefix}daily` - Өдөр бүрийн урамшуулал авах\n"
                f"2️⃣ `{ctx.prefix}balance` - Мөнгөө шалгах\n"
                f"3️⃣ `{ctx.prefix}deposit 1000` - Мөнгөө банканд хадгалах\n"
                f"4️⃣ `{ctx.prefix}cf 1000` - Анхны тоглоом тоглох\n"
                f"5️⃣ `{ctx.prefix}buyvip` - VIP үүсгэх (хүсвэл)"
            ),
            inline=False
        )
        
        embed3.add_field(
            name="❓ Тусламж",
            value=(
                f"`{ctx.prefix}support` - Тусламжийн мэдээлэл\n"
                f"`{ctx.prefix}tutorial economy` - Эдийн засгийн заавар\n"
                f"`{ctx.prefix}tutorial games` - Тоглоомын заавар\n"
                "Асуултууд байвал админтай холбогдоно уу!"
            ),
            inline=False
        )
        
        embeds.append(embed3)
        
        # Send paginated embeds
        await self.send_paginated_embeds(ctx, embeds)
    
    async def tutorial_economy(self, ctx: commands.Context):
        """Эдийн засгийн заавар"""
        
        embeds = []
        
        # Page 1: Үндсэн эдийн засаг
        embed1 = discord.Embed(
            title="💰 Эдийн засгийн заавар - 1/4",
            description="MongolBot-ийн эдийн засгийн бүх функцуудыг суралцая!",
            color=discord.Color.gold()
        )
        
        embed1.add_field(
            name="💵 Үндсэн командууд",
            value=(
                f"`{ctx.prefix}balance` (bal) - Таны мөнгө\n"
                f"`{ctx.prefix}daily` - Өдөр бүрийн 5,000₮\n"
                f"`{ctx.prefix}give @user 1000` - Хэн нэгэнд өгөх\n"
                f"`{ctx.prefix}top` - Баян хүмүүсийн жагсаалт"
            ),
            inline=False
        )
        
        embed1.add_field(
            name="ℹ️ Анхаарах зүйлүүд",
            value=(
                "• Анх нэгдэхэд 5,000₮ авна\n"
                "• Daily-г өдөр бүр авах боломжтой\n"
                "• Мөнгө алдахгүйн тулд банканд хадгална\n"
                "• VIP байвал илүү их урамшуулал авна"
            ),
            inline=False
        )
        
        embeds.append(embed1)
        
        # Page 2: Банк систем
        embed2 = discord.Embed(
            title="💰 Эдийн засгийн заавар - 2/4",
            description="Банк системийг ашиглаж мөнгөө аюулгүй хадгална!",
            color=discord.Color.gold()
        )
        
        embed2.add_field(
            name="🏦 Банкны командууд",
            value=(
                f"`{ctx.prefix}bank` - Банкны мэдээлэл\n"
                f"`{ctx.prefix}deposit 1000` (dep) - Хадгалах\n"
                f"`{ctx.prefix}withdraw 1000` (wit) - Гаргах\n"
                f"`{ctx.prefix}deposit 1000` - Бүгдийг хадгалах\n"
                f"`{ctx.prefix}withdraw 1000` - Бүгдийг гаргах"
            ),
            inline=False
        )
        
        embed2.add_field(
            name="💎 Хуримтлал & Зээл",
            value=(
                f"`{ctx.prefix}save 5000` - Хуримтлал үүсгэх\n"
                f"`{ctx.prefix}witsave 1000` - Хуримтлалаас гаргах\n"
                f"`{ctx.prefix}loan 1000` - Зээл авах\n"
                f"`{ctx.prefix}payloan` - Зээл төлөх"
            ),
            inline=False
        )
        
        embeds.append(embed2)
        
        # Page 3: Server Bank
        embed3 = discord.Embed(
            title="💰 Эдийн засгийн заавар - 3/4",
            description="Серверийн банк - хамтын мөнгөний сан!",
            color=discord.Color.gold()
        )
        
        embed3.add_field(
            name="🏛️ Серверийн банк",
            value=(
                f"`{ctx.prefix}checkbalance` - Серверийн үлдэгдэл\n"
                f"`{ctx.prefix}serverdep 10000` - Серверт хадгалах\n"
                f"`{ctx.prefix}serverwith 5000` - Серверээс авах\n"
                f"`{ctx.prefix}listowners` - Эзэмшигчид"
            ),
            inline=False
        )
        
        embed3.add_field(
            name="⚠️ Анхаарах",
            value=(
                "• Зөвхөн серверийн эзэмшигчид ашиглана\n"
                "• Serverwith хийхэд таны хувийн дансанд нэмэгдэнэ\n"
                "• Хамтын сан тул бусадтай хуваалцана\n"
                "• Админ зөвшөөрөлтэй эзэмшигч болно"
            ),
            inline=False
        )
        
        embeds.append(embed3)
        
        # Page 4: VIP систем
        embed4 = discord.Embed(
            title="💰 Эдийн засгийн заавар - 4/4",
            description="VIP болж илүү их боломжууд олж авъя!",
            color=discord.Color.gold()
        )
        
        embed4.add_field(
            name="💎 VIP Level-үүд",
            value=(
                "🥉 **Bronze** - 22,000,000₮ (30 хоног)\n"
                "🥈 **Silver** - 40,000,000₮ (30 хоног)\n" 
                "🥇 **Gold** - 85,000,000₮ (60 хоног)\n"
                "💎 **Diamond** - 150,000,000₮ (60 хоног)"
            ),
            inline=False
        )
        
        embed4.add_field(
            name="🎁 VIP давуу талууд",
            value=(
                "• Өдөр бүрийн урамшуулал нэмэгдэнэ\n"
                "• Тоглоомын bet лимит нэмэгдэнэ\n"
                "• Cooldown цаг багасна\n"
                "• Зээлийн лимит өсөнө\n"
                "• Сугалааны тасалбар +1"
            ),
            inline=False
        )
        
        embeds.append(embed4)
        
        await self.send_paginated_embeds(ctx, embeds)
    
    async def tutorial_games(self, ctx: commands.Context):
        """Тоглоомын заавар"""
        
        embeds = []
        
        # Page 1: Азартын тоглоомууд
        embed1 = discord.Embed(
            title="🎮 Тоглоомын заавар - 1/3",
            description="Азартын тоглоомоор мөнгө олж, хөгжилтэй цаг өнгөрүүлье!",
            color=discord.Color.purple()
        )
        
        embed1.add_field(
            name="🪙 Зоос шидэх (Coinflip)",
            value=(
                f"`{ctx.prefix}cf 1000` - Зоос шидэх\n"
                f"`{ctx.prefix}coinflip 1000 heads` - Толгой сонгох\n"
                "• 50/50 магадлал\n"
                "• Хожвол 2 дахин их авна\n"
                "• Хамгийн энгийн тоглоом"
            ),
            inline=False
        )
        
        embed1.add_field(
            name="🎯 Рулетка",
            value=(
                f"`{ctx.prefix}roulette 1000 red` - Улаан сонгох\n"
                f"`{ctx.prefix}r 1000 5` - 5 тоо сонгох\n"
                "• Red/Black: 2x урамшуулал\n"
                "• Тоо таах: 36x урамшуулал\n"
                "• Green (0): Бүх мөнгө алдана"
            ),
            inline=False
        )
        
        embeds.append(embed1)
        
        # Page 2: Илүү төвөгтэй тоглоомууд
        embed2 = discord.Embed(
            title="🎮 Тоглоомын заавар - 2/3",
            description="Илүү сонирхолтой тоглоомуудыг туршиж үзье!",
            color=discord.Color.purple()
        )
        
        embed2.add_field(
            name="🎰 Слот машин",
            value=(
                f"`{ctx.prefix}slots 1000` - Слот тоглох\n"
                f"`{ctx.prefix}s 5000` - Богино хэлбэр\n"
                "• 3 ижил тэмдэг гарвал хожино\n"
                "• Өөр өөр тэмдэгт = өөр урамшуулал\n"
                "• Jackpot: 🎰 🎰 🎰 = 5x"
            ),
            inline=False
        )
        
        embed2.add_field(
            name="💣 Мина талбай",
            value=(
                f"`{ctx.prefix}minefield 1000` - Мина тоглоом\n"
                f"`{ctx.prefix}mf 2000` - Богино хэлбэр\n"
                "• 5x5 талбайд мина нуугдсан\n"
                "• Аюулгүй нүд дарж мөнгө цуглуулна\n"
                "• Мина дарвал бүгдийг алдана"
            ),
            inline=False
        )
        
        embeds.append(embed2)
        
        # Page 3: Сугалаа
        embed3 = discord.Embed(
            title="🎮 Тоглоомын заавар - 3/3",
            description="Том төсөлтэй тоглоомууд - сугалаа!",
            color=discord.Color.purple()
        )
        
        embed3.add_field(
            name="🎟️ Сугалаа",
            value=(
                f"`{ctx.prefix}lottery` - Сугалааны мэдээлэл\n"
                f"`{ctx.prefix}buylottery 2` - 2 тасалбар авах\n"
                "• 1 тасалбар = 300,000₮\n"
                "• Сард нэг удаа сугалаа\n"
                "• VIP бол +1 тасалбар авах боломжтой\n"
                "• Бүх мөнгө ялагчид очно"
            ),
            inline=False
        )
        
        embed3.add_field(
            name="🎯 Тоглоомын зөвлөмж",
            value=(
                "• Бага дүнгээр эхэлж дадлага хий\n"
                "• VIP байвал bet лимит өндөр\n"
                "• Cooldown байгааг анхаарна уу\n"
                "• Мөнгө алдах эрсдэлтэй!"
            ),
            inline=False
        )
        
        embeds.append(embed3)
        
        await self.send_paginated_embeds(ctx, embeds)
    
    @commands.command(name='quickguide')
    async def quick_guide(self, ctx: commands.Context):
        """Хурдан лавлах - хамгийн хэрэгтэй командууд"""
        
        embed = discord.Embed(
            title="⚡ Хурдан лавлах",
            description="Хамгийн их ашиглагддаг командуудын жагсаалт",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="💰 Эдийн засаг",
            value=(
                f"`{ctx.prefix}balance` - Мөнгөө харах\n"
                f"`{ctx.prefix}daily` - Өдөр бүрийн урамшуулал\n"
                f"`{ctx.prefix}deposit 1000` - Бүгдийг банканд\n"
                f"`{ctx.prefix}give @user 1000` - Хэн нэгэнд өгөх"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🎮 Тоглоом",
            value=(
                f"`{ctx.prefix}cf 1000` - Зоос шидэх\n"
                f"`{ctx.prefix}slots 1000` - Слот машин\n"
                f"`{ctx.prefix}roulette 1000 red` - Рулетка\n"
                f"`{ctx.prefix}buylottery 2` - Сугалааны тасалбар"
            ),
            inline=True
        )
        
        embed.add_field(
            name="💎 VIP",
            value=(
                f"`{ctx.prefix}vip` - VIP мэдээлэл\n"
                f"`{ctx.prefix}buyvip` - VIP авах\n"
                f"`{ctx.prefix}dailyvip` - VIP урамшуулал\n"
                f"`{ctx.prefix}viptop` - VIP жагсаалт"
            ),
            inline=True
        )
        
        embed.add_field(
            name="❓ Тусламж",
            value=(
                f"`{ctx.prefix}help` - Бүх команд\n"
                f"`{ctx.prefix}tutorial` - Дэлгэрэнгүй заавар\n"
                f"`{ctx.prefix}support` - Тусламж\n"
                f"`{ctx.prefix}quickguide` - Энэ лавлах"
            ),
            inline=True
        )
        
        embed.set_footer(text="💡 Дэлгэрэнгүй мэдээлэл авахын тулд mtutorial ашиглана уу")
        
        await ctx.send(embed=embed)

    @commands.command(name='examples')
    async def examples(self, ctx: commands.Context):
        """Хэрэглээний жишээнүүд"""
        
        embeds = []
        
        # Page 1: Шинэ хэрэглэгчийн жишээ
        embed1 = discord.Embed(
            title="📝 Хэрэглээний жишээ - 1/3",
            description="**Жишээ 1: Шинэ хэрэглэгч**",
            color=discord.Color.blue()
        )
        
        embed1.add_field(
            name="🆕 Шинэ хэрэглэгчийн эхний алхамууд",
            value=(
                "**Батбаяр анх серверт орлоо:**\n\n"
                f"1️⃣ `{ctx.prefix}balance` ➜ 5,000₮ харагдана\n"
                f"2️⃣ `{ctx.prefix}daily` ➜ +5,000₮ (нийт 10,000₮)\n"
                f"3️⃣ `{ctx.prefix}deposit 1000` ➜ Бүх мөнгийг банканд\n"
                f"4️⃣ `{ctx.prefix}cf 1000` ➜ Анхны тоглоом тоглох\n"
                f"5️⃣ `{ctx.prefix}withdraw 5000` ➜ Тоглоомын мөнгө гаргах"
            ),
            inline=False
        )
        
        embed1.add_field(
            name="💡 Батбаярын эхний долоо хоног",
            value=(
                "• Өдөр бүр daily авч 35,000₮ цуглуулсан\n"
                "• Coinflip, slots тоглож дадлага хийсэн\n"
                "• Найзтайгаа мөнгө солилцсон\n"
                "• VIP авахыг зорьж мөнгө хуримтлуулж эхэлсэн"
            ),
            inline=False
        )
        
        embeds.append(embed1)
        
        # Page 2: VIP хэрэглэгчийн жишээ
        embed2 = discord.Embed(
            title="📝 Хэрэглээний жишээ - 2/3", 
            description="**Жишээ 2: VIP хэрэглэгч**",
            color=discord.Color.gold()
        )
        
        embed2.add_field(
            name="💎 Мөнхбаярын VIP амжилт",
            value=(
                "**Мөнхбаяр Bronze VIP боллоо:**\n\n"
                f"1️⃣ `{ctx.prefix}buyvip Bronze` ➜ 22,000,000₮ төлөв\n"
                f"2️⃣ `{ctx.prefix}dailyvip` ➜ Өдөр бүр 500,000₮ авна\n"
                f"3️⃣ `{ctx.prefix}cf 1000000` ➜ Том дүнгээр тоглоно\n"
                f"4️⃣ `{ctx.prefix}buylottery 3` ➜ 3 тасалбар авна (VIP+1)\n"
                f"5️⃣ `{ctx.prefix}loan 2000000` ➜ Илүү их зээл авна"
            ),
            inline=False
        )
        
        embed2.add_field(
            name="🏆 VIP-ийн давуу талууд практикт",
            value=(
                "• Daily: 5,000₮ → 500,000₮ (+495,000₮)\n"
                "• Cooldown: 10 сек → 8 сек (-2 сек)\n"
                "• Max bet: 300,000₮ → 1,000,000₮\n"
                "• Зээл: 1,000,000₮ → 2,000,000₮\n"
                "• Сугалаа: 2 → 3 тасалбар"
            ),
            inline=False
        )
        
        embeds.append(embed2)
        
        # Page 3: Серверийн эзэмшигчийн жишээ  
        embed3 = discord.Embed(
            title="📝 Хэрэглээний жишээ - 3/3",
            description="**Жишээ 3: Серверийн эзэмшигч**",
            color=discord.Color.purple()
        )
        
        embed3.add_field(
            name="🏛️ Админ Цагаанбаярын өдөр",
            value=(
                "**Серверийн санг удирдах:**\n\n"
                f"1️⃣ `{ctx.prefix}checkbalance` ➜ Серверийн үлдэгдэл: 50,000,000₮\n"
                f"2️⃣ `{ctx.prefix}serverwith 10000000` ➜ 10M авсан\n"
                f"3️⃣ `{ctx.prefix}give @member 1000000` ➜ Гишүүнд өгсөн\n"
                f"4️⃣ `{ctx.prefix}serverdep 5000000` ➜ 5M буцаан хадгалсан\n"
                f"5️⃣ `{ctx.prefix}listowners` ➜ Бусад эзэмшигчдийг шалгасан"
            ),
            inline=False
        )
        
        embed3.add_field(
            name="⚙️ Админ ажлууд",
            value=(
                "• Шинэ гишүүдэд анхны мөнгө өгсөн\n"
                "• Channel эрх тохируулсан\n" 
                "• Санал болон тайлан шийдвэрлэсэн\n"
                "• VIP хэрэглэгчдэд урамшуулал өгсөн\n"
                "• Bot prefix серверт тохируулсан"
            ),
            inline=False
        )
        
        embeds.append(embed3)
        
        await self.send_paginated_embeds(ctx, embeds)

    @commands.command(name='troubleshoot')
    async def troubleshoot(self, ctx: commands.Context):
        """Түгээмэл асуудал ба шийдэл"""
        
        embed = discord.Embed(
            title="🔧 Асуудал шийдэх заавар",
            description="Хамгийн түгээмэл асуудлууд болон тэдгээрийн шийдэл",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="❌ \"Хүрэлцэхгүй мөнгө\" гэж гардаг",
            value=(
                "**Шийдэл:**\n"
                f"• `{ctx.prefix}balance` - мөнгөө шалгах\n"
                f"• `{ctx.prefix}withdraw 1000` - банкнаас гаргах\n"
                f"• `{ctx.prefix}daily` - өдөр бүрийн урамшуулал\n"
                "• Найзаасаа мөнгө гуйх эсвэл тоглоом тоглох"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⏰ \"Cooldown\" алдаа гардаг",
            value=(
                "**Шийдэл:**\n"
                "• Тухайн хугацааг хүлээх (ихэвчлэн 10 секунд)\n"
                "• VIP болж cooldown багасгах\n"
                "• Өөр команд ашиглах\n"
                "• Тэвчээртэй байх"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🚫 \"Channel-д команд ашиглах боломжгүй\"",
            value=(
                "**Шийдэл:**\n"
                "• Админаас зөвшөөрөгдсөн channel-д ороход\n"
                "• Админтай холбогдож channel нээхийг хүсэх\n"
                f"• `{ctx.prefix}help` - DM-ээр ажиллана\n"
                "• Бусад серверийн channel шалгах"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💸 \"VIP авч чадахгүй байна\"",
            value=(
                "**Шийдэл:**\n"
                f"• `{ctx.prefix}vip` - үнэ болон шаардлага шалгах\n"
                "• Хангалттай мөнгө цуглуулах\n"
                "• Bronze-ээс эхэлж аажмаар дээшлүүлэх\n"
                "• Найзуудаас мөнгө цуглуулах"
            ),
            inline=False
        )
        
        embed.add_field(
            name="❓ Бусад асуудал",
            value=(
                f"• `{ctx.prefix}support` - тусламжийн мэдээлэл\n"
                "• Админтай шууд холбогдох\n"
                "• Команд дахин оролдох\n"
                "• Bot restart хүлээх"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)

    @commands.command(name='welcome')
    async def welcome_message(self, ctx: commands.Context):
        """Шинэ хэрэглэгчдэд зориулсан анхны мэндчилгээ"""
        
        embed = discord.Embed(
            title="🎉 MongolBot-д тавтай морил!",
            description="Танд MongolBot-ийн бүх боломжуудыг танилцуулья!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="🎯 Анхны 5 алхам",
            value=(
                f"1️⃣ `{ctx.prefix}balance` - Анхны 5,000₮-ээ шалгаарай\n"
                f"2️⃣ `{ctx.prefix}daily` - Өдөр бүрийн +5,000₮ авна уу\n"
                f"3️⃣ `{ctx.prefix}deposit 1000` - Мөнгөө аюулгүй хадгална уу\n"
                f"4️⃣ `{ctx.prefix}cf 1000` - Анхны тоглоом тоглоно уу\n"
                f"5️⃣ `{ctx.prefix}tutorial` - Дэлгэрэнгүй заавар үзнэ үү"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💰 Мөнгө олох арга",
            value=(
                "🎮 Тоглоом тоглох (cf, slots, roulette)\n"
                "💎 VIP болж илүү урамшуулал авах\n"
                "🎟️ Сугалааны тасалбар авах\n"
                "🤝 Найзуудаасаа мөнгө авах\n"
                "⏰ Өдөр бүр daily цуглуулах"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🎵 Бусад боломжууд",
            value=(
                "🏦 Банк, зээл, хуримтлал\n"
                "🏛️ Серверийн банк (эзэмшигчдэд)\n"
                "💡 Санал өгөх, тайлан хийх"
            ),
            inline=True
        )
        
        embed.add_field(
            name="❓ Тусламж хэрэгтэй үү?",
            value=(
                f"`{ctx.prefix}help` - Бүх командууд\n"
                f"`{ctx.prefix}quickguide` - Хурдан лавлах\n"
                f"`{ctx.prefix}tutorial` - Дэлгэрэнгүй заавар\n"
                f"`{ctx.prefix}troubleshoot` - Асуудал шийдэх\n"
                f"`{ctx.prefix}examples` - Хэрэглээний жишээ"
            ),
            inline=False
        )
        
        embed.set_footer(
            text="💡 Эхлээд daily авч, дараа нь cf 1000 тоглож дадлага хийгээрэй!",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else None
        )
        
        await ctx.send(embed=embed)

    async def send_paginated_embeds(self, ctx: commands.Context, embeds: List[discord.Embed]):
        """Send embeds with pagination buttons"""
        if not embeds:
            return
        
        if len(embeds) == 1:
            await ctx.send(embed=embeds[0])
            return
        
        current_page = 0
        message = await ctx.send(embed=embeds[current_page])
        
        # Add reactions for navigation
        await message.add_reaction("⬅️")
        await message.add_reaction("➡️")
        await message.add_reaction("❌")
        
        def check(reaction: discord.Reaction, user: discord.User) -> bool:
            return (user == ctx.author and 
                   str(reaction.emoji) in ["⬅️", "➡️", "❌"] and 
                   reaction.message.id == message.id)
        
        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
                
                if str(reaction.emoji) == "➡️" and current_page < len(embeds) - 1:
                    current_page += 1
                    await message.edit(embed=embeds[current_page])
                    
                elif str(reaction.emoji) == "⬅️" and current_page > 0:
                    current_page -= 1
                    await message.edit(embed=embeds[current_page])
                    
                elif str(reaction.emoji) == "❌":
                    await message.delete()
                    return
                
                # Remove user's reaction
                await message.remove_reaction(reaction.emoji, user)
                
            except asyncio.TimeoutError:
                try:
                    await message.clear_reactions()
                except:
                    pass
                break

async def setup(bot: commands.Bot):
    await bot.add_cog(Tutorial(bot))
