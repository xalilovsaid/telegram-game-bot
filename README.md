# Telegram Onboarding Bot

[![Deploy to Render](https://render.com/images/deploy-to-render.svg)](https://render.com/deploy?repo=https://github.com/xalilovsaid/telegram-game-bot)

Ushbu bot yangi kirgan foydalanuvchilar bilan shaxsan salomlashib, ularga 10 ball bonus beruvchi va interaktiv inline tugmalarga ega bo'lgan Telegram bot namunasidir.

## 🚀 Ishga tushirish qadamlari

### 1. Bot Tokenini olish
1. Telegram'da [@BotFather](https://t.me/BotFather) botiga kiring va `/newbot` buyrug'ini yuboring.
2. Botga nom va username bering.
3. BotFather taqdim etgan **API Token**ni nusxalab oling.

### 2. Konfiguratsiya
Loyiha jildidagi `.env` faylini oching va bot tokeningizni joylashtiring:
```env
BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ  # <-- O'z tokeningizni yozing
```

### 3. Kutubxonalarni o'rnatish
Terminalda loyiha jildiga o'tib, quyidagi buyruqni bajaring:
```bash
pip install -r requirements.txt
```

### 4. Botni ishga tushirish
Loyihani ishga tushirish uchun:
```bash
python bot.py
```

Telegram'da o'z botingizga kiring va `/start` tugmasini bosing! 🎉
