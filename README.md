# 🤖 MongolBot

> **Монгол хэл дээрх олон боломжтой Discord бот**

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Discord.py](https://img.shields.io/badge/discord.py-2.0+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)

## 📋 Тайлбар

MongolBot бол Монгол хэл дээр бүрэн дэмжлэгтэй Discord бот юм. Энэхүү бот нь эдийн засаг, тоглоом, хөгжим, администрацийн болон олон төрлийн боломжуудыг санал болгодог.

## ✨ Онцлог боломжууд

### 🚦 **Global Rate Limiting System** ⭐ NEW!
- 🛡️ **Discord API хамгаалалт** - Rate limit-ээс автоматаар сэргийлэх
- 📊 **Бодит цагийн статистик** - Хүсэлт, блок хувийн мэдээлэл
- ⚙️ **Автомат тохиргоо** - Серверийн хэмжээнээс хамааруулан тохируулах
- 🎯 **45 хүсэлт/секунд хязгаар** - Discord-ын 50-ээс аюулгүй доош
- 🔧 **Удирдах командууд** - `>ratelimit_stats`, `>toggle_rate_limit`

### 💰 Эдийн засгийн систем
- 🏦 **Банкны систем** - Мөнгө хадгалах, шилжүүлэх
- 💳 **VIP систем** - Түвшин, тусгай боломжууд
- 🏪 **Дэлгүүр** - Янз бүрийн зүйл худалдаж авах
- 🏛️ **Серверийн банк** - Нийтийн мөнгөн санд

### 🎮 Тоглоомууд
- 🪙 **Зоос шидэх** (`cf`) - Heads/Tails тоглоом
- 🎰 **Слот машин** (`slots`) - Азартын тоглоом
- 🎯 **Рулетка** (`roulette`) - Өнгө таах тоглоом
- 💣 **Minefield** (`mf`) - Тэсрэх бөмбөг зайлсуулах
- 🎫 **Сугалаа** (`lottery`) - Үндэсний сугалаа
- 💼 **Ажил** (`job`) - Мөнгө олох ажил

### 🎵 Хөгжим
- ▶️ **Тоглуулах** - YouTube, Spotify дэмжлэгтэй
- ⏸️ **Зогсоох/Үргэлжлүүлэх** - Хөгжим удирдах
- 📜 **Жагсаалт** - Хөгжмийн жагсаалт харах
- 🔀 **Холих** - Дууг санамсаргүй дараалалд тавих

### 👑 Администрацийн хэрэгслүүд
- 🚫 **Модерация** - Ban, kick, timeout
- 📝 **Гомдол систем** - Хэрэглэгчийн гомдол
- 🎁 **Бэлэг тарааx** (`giveaway`) - Автомат бэлэг тараах
- 🎂 **Төрсөн өдөр** - Автомат мэндчилгээ
- 💡 **Санал** - Хэрэглэгчийн санал авах

### 🔧 Хэрэгслүүд
- 📊 **Профайл** - Хэрэглэгчийн мэдээлэл
- 🆘 **Тусламж** (`mhelp`) - Командын заавар
- ⚙️ **Тохиргоо** - Сувгийн эрх, префикс
- 📞 **Дэмжлэг** - Админтай холбогдох

## 🚀 Суулгах заавар

### Шаардлага
- Python 3.8+
- Discord.py 2.0+
- SQLite3
- FFmpeg (хөгжмийн хувьд)

### 1️⃣ Repository clone хийх
```bash
git clone https://github.com/DarkMooN-SYS/MongolBot.git
cd MongolBot
```

### 2️⃣ Package суулгах
```bash
pip install -r requirements.txt
```

### 3️⃣ Environment variables тохируулах
`.env` файл үүсгээд дараах мэдээллийг оруулна уу:
```env
DISCORD_BOT_TOKEN=your_bot_token_here
```

### 4️⃣ Ботыг ажиллуулах
```bash
python bot.py
```

## 📖 Хэрэглээний заавар

### Үндсэн командууд

#### 💰 Эдийн засаг
```
mbal                 # Данс харах
mtransfer @user 100  # Мөнгө шилжүүлэх
mshop               # Дэлгүүр харах
mvip                # VIP статус харах
```

#### 🎮 Тоглоомууд
```
mcf 1000 heads      # Зоос шидэх
mslots 500          # Слот тоглох
mroulette 1000 red  # Рулетка тоглох
mminefield 2000     # Minefield тоглох
```

#### 🎵 Хөгжим
```
mplay <URL/нэр>     # Хөгжим тоглуулах
mpause              # Зогсоох
mresume             # Үргэлжлүүлэх
mqueue              # Жагсаалт харах
```

#### 🛠️ Администрация
```
mkick @user         # Хэрэглэгч хөөх
mban @user          # Хэрэглэгч бандах
mgiveaway           # Бэлэг тараах
msuggest            # Санал өгөх
```

## 🏗️ Файлын бүтэц

```
MongolBot/
├── bot.py              # Үндсэн бот файл
├── requirements.txt    # Python packages
├── .env               # Environment variables
├── data/              # Database файлууд
│   ├── bot.db
│   ├── economy.db
│   └── ...
├── cogs/              # Bot модулууд
│   ├── admin/         # Админ командууд
│   ├── economy/       # Эдийн засгийн систем
│   ├── games/         # Тоглоомууд
│   ├── music/         # Хөгжмийн систем
│   ├── profile/       # Хэрэглэгчийн профайл
│   ├── shop/          # Дэлгүүрийн систем
│   ├── server/        # Серверийн боломжууд
│   └── utils/         # Туслах хэрэгслүүд
└── assets/            # Зураг, медиа файлууд
```

## 🤝 Хувь нэмэр оруулах

1. Repository-г fork хийнэ үү
2. Feature branch үүсгэнэ үү (`git checkout -b feature/AmazingFeature`)
3. Өөрчлөлтөө commit хийнэ үү (`git commit -m 'Add some AmazingFeature'`)
4. Branch-дээ push хийнэ үү (`git push origin feature/AmazingFeature`)
5. Pull Request үүсгэнэ үү

## 📝 License

Энэхүү төсөл нь MIT лицензтэй. Дэлгэрэнгүй мэдээллийг `LICENSE` файлаас үзнэ үү.

## 📞 Холбоо барих

- **GitHub**: [DarkMooN-SYS](https://github.com/DarkMooN-SYS)
- **Discord**: Ботын `mhelp` командыг ашиглан тусламж авна уу

## 🙏 Талархал

- Discord.py community
- MongoDB community
- Бүх хувь нэмэр оруулагчид

---

**⭐ Хэрэв энэхүү төсөл танд таалагдсан бол star өгөх сонирхолтой байна уу!**
