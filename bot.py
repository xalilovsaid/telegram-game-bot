import os
import json
import html
import logging
import asyncio
import random
import time
import re
import subprocess
import yt_dlp
import imageio_ffmpeg
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_points_user = State()
    waiting_for_points_amount = State()

# Loglarni sozlash
logging.basicConfig(level=logging.INFO)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GAME_URL = os.getenv("GAME_URL", "https://honest-penguin-51.loca.lt").rstrip("/")

if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
    raise ValueError("Iltimos, .env fayliga haqiqiy Telegram Bot Tokenini kiriting!")

# Bot va Dispatcher obyektlarini yaratish
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Foydalanuvchilar ma'lumotlar bazasi (Sodda xotira ko'rinishida)
users_db = {}

# --- Foydalanuvchilar ma'lumotlar bazasini saqlash ---
USERS_FILE = os.path.join(os.path.dirname(__file__), "users.json")

def load_users():
    global users_db
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                users_db.clear()
                for k, v in data.items():
                    users_db[int(k)] = v
            logging.info("Foydalanuvchilar bazasi muvaffaqiyatli yuklandi.")
        except Exception as e:
            logging.error(f"Foydalanuvchilarni yuklashda xatolik: {e}")

def save_users():
    try:
        str_db = {str(k): v for k, v in users_db.items()}
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(str_db, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Foydalanuvchilarni saqlashda xatolik: {e}")

from aiogram import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable
from aiogram.types import TelegramObject

class AutoSaveMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        result = await handler(event, data)
        save_users()
        return result

REVENUE_FILE = "revenue.json"

def get_revenue():
    if os.path.exists(REVENUE_FILE):
        try:
            with open(REVENUE_FILE, "r") as f:
                return json.load(f).get("total_revenue", 0)
        except Exception:
            return 0
    return 0

def add_revenue(amount):
    rev = get_revenue() + amount
    try:
        with open(REVENUE_FILE, "w") as f:
            json.dump({"total_revenue": rev}, f)
    except Exception as e:
        logging.error(f"Revenue yozishda xatolik: {e}")

# 100 dan ortiq mantiqiy va yozma savollarni generatsiya qilish funksiyasi
def generate_questions():
    questions = []
    for i in range(1, 105):  # 104 ta mantiqiy/yozma va rasmli savollar
        template_type = i % 4
        
        # Rasmlarni aylanma shaklda almashtirish (q1.png, q2.png, q3.png, welcome.png)
        images = ["q1.png", "q2.png", "q3.png", "welcome.png"]
        image_idx = (i - 1) % len(images)
        image_name = images[image_idx]
        
        if template_type == 0:
            # 1. Rasmga doir vizual mantiqiy savollar
            if image_name == "q1.png":
                text = f"🎯 <b>{i}-savol (Rasmga doir mantiqiy savol):</b>\n\nFonda ko'rinib turgan 3D logotip qaysi sohaga tegishli deb o'ylaysiz? 👇"
                correct = "Dasturlash va kodlash 💻"
                wrong1 = "Vaqt va soat ⏱"
                wrong2 = "Sport va kuboklar 🏆"
            elif image_name == "q2.png":
                text = f"🎯 <b>{i}-savol (Rasmga doir mantiqiy savol):</b>\n\nFonda tasvirlangan neon rangdagi 3D shakl nima? 👇"
                correct = "Soat (Vaqt) ⏱"
                wrong1 = "Smartfon 📱"
                wrong2 = "Noutbuk 💻"
            elif image_name == "q3.png":
                text = f"🎯 <b>{i}-savol (Rasmga doir mantiqiy savol):</b>\n\nFonda joylashgan oltin rangli sovrin ramzi nimani anglatadi? 👇"
                correct = "G'alaba va muvaffaqiyat 🏆"
                wrong1 = "Dasturlash tillari 💻"
                wrong2 = "Ish vaqti ⏱"
            else:
                text = f"🎯 <b>{i}-savol (Rasmga doir mantiqiy savol):</b>\n\nFonda ko'rsatilgan smartfon ekrani nimani tasvirlamoqda? 👇"
                correct = "Chat bot interfeysini 📱"
                wrong1 = "Taqvim va sanani 📅"
                wrong2 = "Ob-havo ma'lumotini ☀️"
                
        elif template_type == 1:
            # 2. Soat millari orasidagi burchak (Yozma mantiqiy)
            h = (i % 11) + 1  # 1 dan 11 gacha
            correct_angle = h * 30
            if correct_angle > 180:
                correct_angle = 360 - correct_angle
            text = f"🎯 <b>{i}-savol (Mantiqiy yozma savol):</b>\n\nSoat millari roppa-rosa <b>{h}:00</b> ni ko'rsatganda, ular orasidagi eng kichik burchak necha gradus bo'ladi? 👇"
            correct = f"{correct_angle}°"
            wrong1 = f"{correct_angle + 15}°"
            wrong2 = f"{correct_angle - 15}°"
            
        elif template_type == 2:
            # 3. Yoshga doir mantiqiy chalg'ituvchi savol (Yozma)
            diff = (i % 6) + 2  # 2 dan 7 yoshgacha farq
            years = (i % 15) + 5  # 5 dan 19 yilgacha keyin
            text = f"🎯 <b>{i}-savol (Mantiqiy yozma savol):</b>\n\nAka ukasidan <b>{diff} yoshga</b> katta. <b>{years} yildan</b> keyin aka ukasidan necha yoshga katta bo'ladi? 👇"
            correct = f"{diff} yoshga"
            wrong1 = f"{diff + years} yoshga"
            wrong2 = f"{diff * 2} yoshga"
            
        else:
            # 4. Nilufar guli hovuz mantiqiy savoli (Yozma)
            days = (i % 10) + 20  # 20 dan 29 kungacha
            half_days = days - 1
            text = f"🎯 <b>{i}-savol (Mantiqiy yozma savol):</b>\n\nHovuzdagi nilufar guli har kuni 2 barobar ko'payadi. Agar hovuz <b>{days} kunda</b> to'liq qoplangan bo'lsa, hovuzning yarmi necha kunda qoplangan bo'ladi? 👇"
            correct = f"{half_days} kunda"
            wrong1 = f"{int(days / 2)} kunda"
            wrong2 = f"{days - 2} kunda"
            
        options = [
            (correct, f"q_ans_{i}_correct"),
            (wrong1, f"q_ans_{i}_wrong1"),
            (wrong2, f"q_ans_{i}_wrong2"),
        ]
        
        # Variantlarni aralashtirish
        random.seed(i)
        random.shuffle(options)
        
        questions.append({
            "number": i,
            "text": text,
            "options": options,
            "correct_callback": f"q_ans_{i}_correct"
        })
    return questions

QUESTIONS = generate_questions()

# Asosiy salomlashish klaviaturasini yaratish
def get_welcome_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Boshlash 🚀", callback_data="btn_start_onboarding")
    builder.button(text="Kiber Arkanoid 🧱🏓", callback_data="game_breaker")
    builder.button(text="O'yinlar 🎮", callback_data="btn_games_menu")
    builder.button(text="AI Yordamchi ✍️", callback_data="btn_ai_assistant")
    builder.button(text="Do'kon 🛒", callback_data="btn_shop")
    builder.button(text="Reyting 🏆", web_app=WebAppInfo(url=f"{GAME_URL}/leaderboard.html"))
    builder.button(text="Do'stlarni taklif qilish 👥", callback_data="btn_invite")
    builder.button(text="Yordam ℹ️", callback_data="btn_help")
    builder.button(text="Sozlamalar ⚙️", callback_data="btn_settings")
    builder.adjust(1, 1, 2, 2, 2, 1)
    return builder.as_markup()

# Orqaga qaytish tugmasi
def get_back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Orqaga ⬅️", callback_data="btn_back_to_menu")
    return builder.as_markup()

# O'yinlar menyusi tugmalari
def get_games_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Uy Qurish 🏡 (Video O'yin)", callback_data="game_house")
    builder.button(text="Kiber Arena 🎯 (Video O'yin)", callback_data="game_arena")
    builder.button(text="Kiber Tetris 🧱 (Video O'yin)", callback_data="game_tetris")
    builder.button(text="Koinot Jangi 🚀 (Video O'yin)", callback_data="game_space")
    builder.button(text="Dino Run 🦖 (Video O'yin)", callback_data="game_dino")
    builder.button(text="Minorani Taxlash 🧱 (Video O'yin)", callback_data="game_stack")
    builder.button(text="Flappy Kema 🛸 (Video O'yin)", callback_data="game_flappy")
    builder.button(text="Neon Poyga 🏎️ (Video O'yin)", callback_data="game_racer")
    builder.button(text="Kiber Arkanoid 🧱🏓 (Video O'yin)", callback_data="game_breaker")
    builder.button(text="Tic-Tac-Toe ❌⭕ (Inline)", callback_data="game_ttt")
    builder.button(text="Tosh-Qaychi-Qog'oz ✊✌️✋", callback_data="game_rps")
    builder.button(text="Sonni top 🔢", callback_data="game_guess")
    builder.button(text="Omad g'ildiragi 🎡", callback_data="game_wheel")
    builder.button(text="Orqaga ⬅️", callback_data="btn_back_to_menu")
    builder.adjust(2)
    return builder.as_markup()

# Tic-Tac-Toe o'yini klaviaturasi
def get_ttt_keyboard(board):
    builder = InlineKeyboardBuilder()
    for i in range(9):
        text = board[i] if board[i] != " " else "🔹"
        builder.button(text=text, callback_data=f"ttt_cell_{i}")
    builder.adjust(3, 3, 3)
    builder.row(InlineKeyboardButton(text="Taslim bo'lish 🏳️", callback_data="ttt_forfeit"))
    return builder.as_markup()

def get_ttt_restart_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Qayta O'ynash 🔄", callback_data="game_ttt")
    builder.button(text="O'yinlar menyusi ⬅️", callback_data="btn_games_menu")
    builder.adjust(1)
    return builder.as_markup()

# Tic-Tac-Toe g'olibni aniqlash
def check_ttt_winner(board):
    win_patterns = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],
        [0, 3, 6], [1, 4, 7], [2, 5, 8],
        [0, 4, 8], [2, 4, 6]
    ]
    for p in win_patterns:
        if board[p[0]] == board[p[1]] == board[p[2]] != " ":
            return board[p[0]]
    if " " not in board:
        return "Draw"
    return None

# Tosh-Qaychi-Qog'oz tugmalari
def get_rps_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Tosh ✊", callback_data="rps_tosh")
    builder.button(text="Qaychi ✌️", callback_data="rps_qaychi")
    builder.button(text="Qog'oz ✋", callback_data="rps_qogoz")
    builder.button(text="O'yinlar menyusi ⬅️", callback_data="btn_games_menu")
    builder.adjust(3, 1)
    return builder.as_markup()

# Sonni topish o'yini (Matematik dinamik inline tugmalar)
def get_guess_keyboard(min_val: int, max_val: int):
    builder = InlineKeyboardBuilder()
    for n in range(min_val, max_val + 1):
        builder.button(text=str(n), callback_data=f"guess_num_{n}")
    # Tugmalar soniga qarab tekislash
    count = max_val - min_val + 1
    if count <= 5:
        builder.adjust(count)
    else:
        builder.adjust(5, count - 5)
    builder.row(InlineKeyboardButton(text="O'yinlar menyusi ⬅️", callback_data="btn_games_menu"))
    return builder.as_markup()

# Omad g'ildiragi tugmalari
def get_wheel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Aylantirish 🎡", callback_data="wheel_spin")
    builder.button(text="O'yinlar menyusi ⬅️", callback_data="btn_games_menu")
    builder.adjust(1)
    return builder.as_markup()

# Savol yuborish uchun asinxron funksiya
async def send_question(message: Message, step: int, user_name: str, user_id: int):
    if step > len(QUESTIONS):
        response_text = (
            f"🎉 <b>Marafon Yakunlandi!</b>\n\n"
            f"Siz barcha 100 dan ortiq mantiqiy va yozma savollarga javob berdingiz! 🏆\n\n"
            f"Yakuniy balansingiz: <b>{users_db[user_id]['points']} ball</b> 💎\n\n"
            f"Bilimingiz uchun rahmat!"
        )
        photo_path = os.path.join(os.path.dirname(__file__), "welcome.png")
        if os.path.exists(photo_path):
            photo = FSInputFile(photo_path)
            await message.answer_photo(
                photo=photo,
                caption=response_text,
                reply_markup=get_back_keyboard(),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                text=response_text,
                reply_markup=get_back_keyboard(),
                parse_mode="HTML"
            )
        return

    q = QUESTIONS[step - 1]
    
    # Rasmlarni aylanma shaklda almashtirish (q1, q2, q3, welcome)
    images = ["q1.png", "q2.png", "q3.png", "welcome.png"]
    image_name = images[(step - 1) % len(images)]
    photo_path = os.path.join(os.path.dirname(__file__), image_name)
    
    # Javob tugmalari
    builder = InlineKeyboardBuilder()
    for label, callback_data in q["options"]:
        builder.button(text=label, callback_data=callback_data)
    builder.adjust(1)
    
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await message.answer_photo(
            photo=photo,
            caption=q["text"],
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            text=q["text"],
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

# /start buyrug'i uchun handler
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    # Referal ID tekshirish
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].split("_")[1])
        except (ValueError, IndexError):
            pass

    is_new_user = user_id not in users_db
    
    if is_new_user:
        users_db[user_id] = {
            "name": user_name,
            "current_question_step": 1,
            "points": 0,
            "guess_game": {"secret": 0, "attempts": 3, "min_val": 1, "max_val": 10},
            "last_spin_time": 0,
            "referrer_id": referrer_id,
            "referrals_count": 0,
            "vip_status": False,
            "point_multiplier": 1,
            "helmet_color": "yellow",
            "unlocked_helmets": ["yellow"]
        }
        # Refererga bonus berish
        if referrer_id and referrer_id in users_db and referrer_id != user_id:
            users_db[referrer_id]["points"] += 50
            users_db[referrer_id]["referrals_count"] = users_db[referrer_id].get("referrals_count", 0) + 1
            try:
                await message.bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎉 <b>Do'stingiz ({html.escape(user_name)}) taklifnomangiz orqali qo'shildi!</b>\n\nSizga <b>+50 bonus ball</b> berildi! 💰",
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.error(f"Refererga xabar yuborishda xatolik: {e}")
    else:
        # Eski foydalanuvchilar maydonlarini tekshirish
        if "referrals_count" not in users_db[user_id]:
            users_db[user_id]["referrals_count"] = 0
        if "vip_status" not in users_db[user_id]:
            users_db[user_id]["vip_status"] = False
        if "point_multiplier" not in users_db[user_id]:
            users_db[user_id]["point_multiplier"] = 1
        if "helmet_color" not in users_db[user_id]:
            users_db[user_id]["helmet_color"] = "yellow"
        if "unlocked_helmets" not in users_db[user_id]:
            users_db[user_id]["unlocked_helmets"] = ["yellow"]
        
    if is_new_user:
        welcome_text = (
            f"Salom, <b>{html.escape(user_name)}</b>! 👋\n\n"
            f"🤖 <b>Aqlli Telegram Botimizga xush kelibsiz!</b>\n\n"
            f"Siz botimizga birinchi marta kirdingiz. Botning asosiy imkoniyatlari: 👇\n\n"
            f"1️⃣ <b>Mantiqiy Marafon 🚀</b>: Marafonni boshlang, savollarga javob berib onboardingni yakunlang va ballar yig'ing!\n"
            f"2️⃣ <b>Qiziqarli O'yinlar 🎮</b>: Tower Stack, Dino Run va House Builder o'yinlarini o'ynab qo'shimcha ballar to'plang.\n"
            f"3️⃣ <b>Do'kon 🛒</b>: Yig'ilgan ballaringizga premium dubulg'alar, jetpack va maxsus o'yin skinlarini xarid qiling.\n"
            f"4️⃣ <b>Instagram/YouTube Yuklovchi 📥</b>: Istalgan Instagram yoki YouTube videosi havolasini yuborib, video va uning musiqasini yuklab oling.\n"
            f"5️⃣ <b>Video Qidiruvchi 🔍</b>: Videoning nomini yozib yuboring va bot uni YouTube'dan topib beradi!\n\n"
            f"🎁 Sizga boshlang'ich <b>10 ta test ballari</b> sovg'a qilindi! 💎\n\n"
            f"Boshlash uchun quyidagi tugmalardan birini bosing: 👇"
        )
        users_db[user_id]["points"] = 10
    else:
        welcome_text = (
            f"Salom, <b>{html.escape(user_name)}</b>! 👋\n\n"
            f"🤖 <b>Aqlli Telegram Botimizga</b> qaytishingiz bilan qutlaymiz!\n\n"
            f"Bu yerda siz onboarding marafonini boshlashingiz yoki qiziqarli mini-o'yinlar o'ynab ball yig'ishingiz mumkin! 🎮💎\n\n"
            f"Joriy balansingiz: <b>{users_db[user_id]['points']} ball</b> 💎"
        )
    
    photo_path = os.path.join(os.path.dirname(__file__), "welcome.png")
    if os.path.exists(photo_path):
        try:
            photo = FSInputFile(photo_path)
            await message.answer_photo(
                photo=photo,
                caption=welcome_text,
                reply_markup=get_welcome_keyboard(),
                parse_mode="HTML"
            )
            return
        except Exception as e:
            logging.error(f"Rasmni yuborishda xatolik: {e}")
            
    await message.answer(
        text=welcome_text,
        reply_markup=get_welcome_keyboard(),
        parse_mode="HTML"
    )

# "Boshlash 🚀" marafoni uchun handler
@dp.callback_query(F.data == "btn_start_onboarding")
async def process_start_onboarding(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.setdefault(user_id, {
        "name": callback.from_user.first_name,
        "current_question_step": 1,
        "points": 0,
        "guess_game": {"secret": 0, "attempts": 3, "min_val": 1, "max_val": 10},
        "last_spin_time": 0,
        "vip_status": False,
        "point_multiplier": 1,
        "helmet_color": "yellow",
        "unlocked_helmets": ["yellow"]
    })
    
    step = user_data.get("current_question_step", 1)
    
    if step <= len(QUESTIONS):
        await callback.message.delete()
        await send_question(callback.message, step, callback.from_user.first_name, user_id)
    else:
        text = (
            f"ℹ️ <b>Siz marafonni yakunlab bo'lgansiz!</b>\n\n"
            f"Sizning joriy balansingiz: <b>{user_data['points']} ball</b> 💎"
        )
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        ) if callback.message.photo else await callback.message.edit_text(
            text=text,
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()

# Do'stlarni taklif qilish (Referal) handler
@dp.callback_query(F.data == "btn_invite")
async def process_invite_friends(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.setdefault(user_id, {
        "name": callback.from_user.first_name,
        "current_question_step": 1,
        "points": 0,
        "guess_game": {"secret": 0, "attempts": 3, "min_val": 1, "max_val": 10},
        "last_spin_time": 0,
        "referrals_count": 0
    })
    
    # Eski ma'lumotlarda referrals_count bo'lmasa, 0 qilib beramiz
    if "referrals_count" not in user_data:
        user_data["referrals_count"] = 0
        
    bot_info = await callback.bot.get_me()
    bot_username = bot_info.username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    share_text = f"Daxshatli onboarding boti va interaktiv multiplayer o'yinlarini sinab ko'ring! 🏡🎮"
    share_url = f"https://t.me/share/url?url={ref_link}&text={share_text}"
    
    invite_text = (
        f"👥 <b>Do'stlarni Taklif Qilish Tizimi</b>\n\n"
        f"Sizning shaxsiy taklif havolangiz:\n"
        f"<code>{ref_link}</code>\n\n"
        f"Har bir taklif qilgan do'stingiz uchun sizga <b>+50 bonus ball</b> berildi! 💰\n\n"
        f"Siz taklif qilgan do'stlar soni: <b>{user_data['referrals_count']} ta</b>\n"
        f"Joriy balansingiz: <b>{user_data['points']} ball</b> 💎"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Do'stga yuborish ✉️", url=share_url)
    builder.button(text="Orqaga ⬅️", callback_data="btn_back_to_menu")
    builder.adjust(1)
    
    await callback.message.delete()
    
    photo_path = os.path.join(os.path.dirname(__file__), "welcome.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=invite_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=invite_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()

# Savollarga javob berish handlerlari
@dp.callback_query(F.data.startswith("q_ans_"))
async def handle_answer(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.setdefault(user_id, {
        "name": callback.from_user.first_name,
        "current_question_step": 1,
        "points": 0,
        "guess_game": {"secret": 0, "attempts": 3, "min_val": 1, "max_val": 10},
        "last_spin_time": 0
    })
    
    data_parts = callback.data.split("_")
    step_num = int(data_parts[2])
    status = data_parts[3]
    
    if user_data["current_question_step"] == step_num:
        user_data["current_question_step"] += 1
        
        if status == "correct":
            user_data["points"] += 1
            change_text = "Javob qabul qilindi! 💎"
        else:
            user_data["points"] = max(0, user_data["points"] - 1)
            change_text = "Javob qabul qilindi! (Ball ayirildi) 💔"
            
        feedback_text = (
            f"📝 <b>{change_text}</b>\n\n"
            f"Joriy balansingiz: <b>{user_data['points']} ball</b>\n\n"
            f"<i>Keyingi savolga o'tilmoqda...</i>"
        )
        
        await callback.message.edit_caption(
            caption=feedback_text,
            parse_mode="HTML"
        ) if callback.message.photo else await callback.message.edit_text(
            text=feedback_text,
            parse_mode="HTML"
        )
        await callback.answer()
        
        await asyncio.sleep(1.5)
        
        await callback.message.delete()
        await send_question(callback.message, user_data["current_question_step"], callback.from_user.first_name, user_id)
    else:
        await callback.answer("Siz bu savolga allaqachon javob bergansiz!", show_alert=True)

# ----------------- O'YINLAR BO'LIMI HANDLERLARI -----------------

# O'yinlar menyusini ko'rsatish
@dp.callback_query(F.data == "btn_games_menu")
async def process_games_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.setdefault(user_id, {
        "name": callback.from_user.first_name,
        "current_question_step": 1,
        "points": 0,
        "guess_game": {"secret": 0, "attempts": 3, "min_val": 1, "max_val": 10},
        "last_spin_time": 0
    })
    
    games_text = (
        f"🎮 <b>O'yinlar bo'limiga xush kelibsiz!</b>\n\n"
        f"Bu yerda siz turli mini-o'yinlar o'ynab, qo'shimcha ballar yutishingiz mumkin! 🚀\n\n"
        f"Sizning balansingiz: <b>{user_data.get('points', 0)} ball</b> 💎\n\n"
        f"Iltimos, o'yinlardan birini tanlang: 👇"
    )
    
    try:
        await callback.message.delete()
    except Exception:
        pass
    photo_path = os.path.join(os.path.dirname(__file__), "games_menu.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=games_text,
            reply_markup=get_games_keyboard(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=games_text,
            reply_markup=get_games_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()

# --- Game 0: Space Shooter (Koinot Jangi) ---
@dp.callback_query(F.data == "game_space")
async def start_game_space(callback: CallbackQuery):
    space_text = (
        f"🚀 <b>Koinot Jangi (HTML5 Video O'yin)</b>\n\n"
        f"Loyihangiz tarkibida to'liq ishlaydigan HTML5/Canvas video o'yini yaratildi!\n\n"
        f"<b>Qanday o'ynash mumkin?</b>\n"
        f"1️⃣ Quyidagi <b>'O'yinni Boshlash 🚀'</b> tugmasini bosib, uni brauzeringizda oching.\n"
        f"2️⃣ <i>(Agar ogohlantirish sahifasi chiqsa, 'Click to Continue' yoki 'Bypass' tugmasini bosing)</i>\n"
        f"3️⃣ Yoki kompyuteringizdagi <code>game.html</code> faylini to'g'ridan-to'g'ri oching.\n\n"
        f"Koinot jangida omad yor bo'lsin! ☄️"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="O'yinni Boshlash 🚀", url=f"{GAME_URL}/game.html")
    builder.button(text="Orqaga ⬅️", callback_data="btn_games_menu")
    builder.adjust(1)
    
    await callback.message.delete()
    
    photo_path = os.path.join(os.path.dirname(__file__), "q1.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=space_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=space_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()

# --- Game 0c: Kiber Tetris ---
@dp.callback_query(F.data == "game_tetris")
async def start_game_tetris(callback: CallbackQuery):
    tetris_text = (
        f"🧱 <b>Kiber Tetris (HTML5 Retro Video O'yin)</b>\n\n"
        f"Kompyuteringiz va telefoningiz uchun retro-kiberpank uslubidagi Tetris o'yini tayyorlandi!\n\n"
        f"<b>Qanday o'ynash mumkin?</b>\n"
        f"1️⃣ Quyidagi <b>'O'yinni Boshlash 🧱'</b> tugmasini bosib, uni brauzeringizda oching.\n"
        f"2️⃣ Bloklarni joylang, qatorlarni o'chiring va eng ko'p ball yig'ib reytingda 1-o'ringa chiqing!\n\n"
        f"Tetris jangida omad yor bo'lsin! 🚀"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="O'yinni Boshlash 🧱", url=f"{GAME_URL}/tetris.html")
    builder.button(text="Orqaga ⬅️", callback_data="btn_games_menu")
    builder.adjust(1)
    
    await callback.message.delete()
    
    photo_path = os.path.join(os.path.dirname(__file__), "q1.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=tetris_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=tetris_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()

# --- Game 0d: Kiber Arena ---
@dp.callback_query(F.data == "game_arena")
async def start_game_arena(callback: CallbackQuery):
    arena_text = (
        f"🎯 <b>Kiber Arena (HTML5 Top-down Action Shooter)</b>\n\n"
        f"Kompyuteringiz uchun ajoyib top-down (tepadan qarash) twin-stick otishma o'yini tayyorlandi!\n\n"
        f"<b>Qanday o'ynash mumkin?</b>\n"
        f"1️⃣ Quyidagi <b>'O'yinni Boshlash 🎯'</b> tugmasini bosib, uni brauzeringizda oching.\n"
        f"2️⃣ <code>WASD</code> yoki strelkalar bilan harakatlaning, sichqoncha bilan mo'ljal oling va plasma otish uchun bosing!\n"
        f"3️⃣ Dushmanlarni yo'q qiling, tushgan bonuslarni (Triple shot, Blast, Heal) oling va yuqori rekord o'rnating!\n\n"
        f"Arenalardagi jangda o'zingizni ko'rsating! 💥"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="O'yinni Boshlash 🎯", url=f"{GAME_URL}/arena.html")
    builder.button(text="Orqaga ⬅️", callback_data="btn_games_menu")
    builder.adjust(1)
    
    await callback.message.delete()
    
    photo_path = os.path.join(os.path.dirname(__file__), "q1.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=arena_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=arena_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()

# --- Game 0b: House Builder (Uy Qurish) ---
@dp.callback_query(F.data == "game_house")
async def start_game_house(callback: CallbackQuery):
    house_text = (
        f"🏡 <b>Orzular Uyi Quruvchisi (HTML5 Video O'yin)</b>\n\n"
        f"Ushbu video o'yinda siz o'z uyingizni poydevoridan to tomigacha qurasiz!\n\n"
        f"<b>Qanday o'ynash mumkin?</b>\n"
        f"1️⃣ Quruvchi qahramon 👷‍♂️ ishlayotganda ekranda paydo bo'luvchi oltin tangalarni bosing.\n"
        f"2️⃣ Yig'ilgan pullarni yangi qavatlar va qurilish tezligini oshirishga sarflang!\n"
        f"3️⃣ O'yinni boshlash uchun quyidagi tugmani bosing.\n\n"
        f"<i>(Ogohlantirish chiqsa, 'Click to Continue' yoki 'Bypass' tugmasini bosing)</i>"
    )
    
    user_id = callback.from_user.id
    user_data = users_db.setdefault(user_id, {})
    vip = 1 if user_data.get("vip_status", False) else 0
    helmet = user_data.get("helmet_color", "yellow")
    
    jetpack = 1 if user_data.get("jetpack_unlocked", False) else 0
    skin = user_data.get("builder_skin", "standard")
    
    builder = InlineKeyboardBuilder()
    builder.button(text="O'yinni Boshlash 🚀", url=f"{GAME_URL}/house_builder.html?user_id={user_id}&vip={vip}&helmet={helmet}&jetpack={jetpack}&skin={skin}")
    builder.button(text="Orqaga ⬅️", callback_data="btn_games_menu")
    builder.adjust(1)
    
    await callback.message.delete()
    
    photo_path = os.path.join(os.path.dirname(__file__), "q3.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=house_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=house_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()

# --- Game 0c: Dino Run ---
@dp.callback_query(F.data == "game_dino")
async def start_game_dino(callback: CallbackQuery):
    dino_text = (
        f"🦖 <b>Neon Dino Run (HTML5 Video O'yin)</b>\n\n"
        f"Ushbu video o'yinda to'siqlardan sakrab o'tib, yangi rekordlar o'rnating!\n\n"
        f"<b>Qanday o'ynash mumkin?</b>\n"
        f"1️⃣ Quyidagi 'O'yinni Boshlash 🚀' tugmasini bosib, uni brauzeringizda oching.\n"
        f"2️⃣ <i>(Agar sahifa ogohlantirish ko'rsatsa, 'Click to Continue' yoki 'Bypass' tugmasini bosing)</i>\n\n"
        f"Dino yugurishida omad tilaymiz! ⚡"
    )
    
    user_id = callback.from_user.id
    user_data = users_db.setdefault(user_id, {})
    skin = "dragon" if "dino_dragon" in user_data.get("unlocked_skins", []) else "dino"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="O'yinni Boshlash 🚀", url=f"{GAME_URL}/dino.html?skin={skin}")
    builder.button(text="Orqaga ⬅️", callback_data="btn_games_menu")
    builder.adjust(1)
    
    await callback.message.delete()
    
    photo_path = os.path.join(os.path.dirname(__file__), "q2.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=dino_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=dino_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()

# --- Game 0d: Tower Stack ---
@dp.callback_query(F.data == "game_stack")
async def start_game_stack(callback: CallbackQuery):
    stack_text = (
        f"🧱 <b>Minorani Taxlash (HTML5 Video O'yin)</b>\n\n"
        f"Bloklarni birining ustiga birini aniq joylashtirib, eng baland minorani quring!\n\n"
        f"<b>Qanday o'ynash mumkin?</b>\n"
        f"1️⃣ Quyidagi 'O'yinni Boshlash 🚀' tugmasini bosib, uni brauzeringizda oching.\n"
        f"2️⃣ <i>(Agar sahifa ogohlantirish ko'rsatsa, 'Click to Continue' yoki 'Bypass' tugmasini bosing)</i>\n\n"
        f"Balandroq minoralar sari! 🏆"
    )
    
    user_id = callback.from_user.id
    user_data = users_db.setdefault(user_id, {})
    skin = "cosmic" if "stack_cosmic" in user_data.get("unlocked_skins", []) else "standard"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="O'yinni Boshlash 🚀", url=f"{GAME_URL}/stack.html?skin={skin}")
    builder.button(text="Orqaga ⬅️", callback_data="btn_games_menu")
    builder.adjust(1)
    
    await callback.message.delete()
    
    photo_path = os.path.join(os.path.dirname(__file__), "q1.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=stack_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=stack_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()

# --- Game 0e: Flappy Space-Ship ---
@dp.callback_query(F.data == "game_flappy")
async def start_game_flappy(callback: CallbackQuery):
    flappy_text = (
        f"🛸 <b>Flappy Space-Ship (HTML5 Video O'yin)</b>\n\n"
        f"Koinot kemangizni tor to'siqlar orasidan to'qnashuvlarsiz uchirib o'tkazing!\n\n"
        f"<b>Qanday o'ynash mumkin?</b>\n"
        f"1️⃣ Quyidagi 'O'yinni Boshlash 🚀' tugmasini bosib, uni brauzeringizda oching.\n"
        f"2️⃣ <i>(Agar sahifa ogohlantirish ko'rsatsa, 'Click to Continue' yoki 'Bypass' tugmasini bosing)</i>\n\n"
        f"Parvozingiz bexatar bo'lsin! ☄️"
    )
    
    user_id = callback.from_user.id
    user_data = users_db.setdefault(user_id, {})
    skin = "rocket" if "flappy_rocket" in user_data.get("unlocked_skins", []) else "ufo"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="O'yinni Boshlash 🚀", url=f"{GAME_URL}/flappy.html?skin={skin}")
    builder.button(text="Orqaga ⬅️", callback_data="btn_games_menu")
    builder.adjust(1)
    
    await callback.message.delete()
    
    photo_path = os.path.join(os.path.dirname(__file__), "q3.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=flappy_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=flappy_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()

# --- Game 0r: Cyber Racer ---
@dp.callback_query(F.data == "game_racer")
async def start_game_racer(callback: CallbackQuery):
    racer_text = (
        f"🏎️ <b>Neon Cyber Racer (HTML5 Video O'yin)</b>\n\n"
        f"Futuristik retro yo'llarda yuqori tezlikda kiber-poyga o'ynang! Boshqa mashinalardan qochib eng yuqori natijani o'rnating!\n\n"
        f"<b>O'yin yangilanishlari:</b>\n"
        f"• <b>5 ta noyob baza:</b> O'rmon 🌲, Cho'l 🏜️, Kiber-Shahar 🌆, Qishloq 🏡 va yangi <b>Drift Arena 🌀</b>!\n"
        f"• <b>2 xil o'yin rejimi:</b> Klassik (Karyera) yoki Drift Arena (Cheksiz drift arena)!\n"
        f"• Nitro ⚡ tezlik boosteri va burilishlardagi drift skidmarks effektlari!\n\n"
        f"<b>Qanday o'ynash mumkin?</b>\n"
        f"1️⃣ Quyidagi 'O'yinni Boshlash 🚀' tugmasini bosib, uni brauzeringizda oching.\n"
        f"2️⃣ <i>(Mashinangizni chapga/o'ngga sensorli tugmalar yoki klaviaturaning chap/o'ng ko'rsatkichlari orqali boshqarasiz)</i>\n\n"
        f"Poygada omad tilaymiz! ⚡"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="O'yinni Boshlash 🚀", url=f"{GAME_URL}/racer.html")
    builder.button(text="Orqaga ⬅️", callback_data="btn_games_menu")
    builder.adjust(1)
    
    await callback.message.delete()
    
    photo_path = os.path.join(os.path.dirname(__file__), "racer.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=racer_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=racer_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()

# --- Game 0g: Kiber Arkanoid ---
@dp.callback_query(F.data == "game_breaker")
async def start_game_breaker(callback: CallbackQuery):
    breaker_text = (
        f"🧱🏓 <b>Kiber Arkanoid (HTML5 Video O'yin)</b>\n\n"
        f"Uchqun sochuvchi neon to'plar, bonus lazer qurollari va 3 xil qiyinchilikdagi premium arkanoid o'yini! Google Play'ga chiqarishga tayyor!\n\n"
        f"<b>Qanday o'ynash mumkin?</b>\n"
        f"1️⃣ Quyidagi 'O'yinni Boshlash 🚀' tugmasini bosib, uni brauzeringizda oching.\n"
        f"2️⃣ <i>(Platformani barmog'ingiz bilan chapga/o'ngga surib to'pni qaytaring, bonuslarni tutib oling!)</i>\n\n"
        f"Kiber-arkanoidda omad tilaymiz! ⚡"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="O'yinni Boshlash 🚀", url=f"{GAME_URL}/brick_breaker.html")
    builder.button(text="Orqaga ⬅️", callback_data="btn_back_to_menu")
    builder.adjust(1)
    
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    photo_path = os.path.join(os.path.dirname(__file__), "breaker.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=breaker_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=breaker_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()

# --- Game 0f: Tic-Tac-Toe (X-O) ---
@dp.callback_query(F.data == "game_ttt")
async def start_game_ttt(callback: CallbackQuery):
    user_id = callback.from_user.id
    users_db.setdefault(user_id, {})["ttt_board"] = [" "] * 9
    
    ttt_text = (
        f"❌⭕ <b>Tic-Tac-Toe (X-O) O'yini</b>\n\n"
        f"Siz: ❌ (Siz boshlaysiz)\n"
        f"Bot: ⭕\n\n"
        f"Iltimos, navbatdagi yurishingizni katakchalardan birini tanlab amalga oshiring: 👇"
    )
    
    await callback.message.delete()
    
    photo_path = os.path.join(os.path.dirname(__file__), "welcome.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=ttt_text,
            reply_markup=get_ttt_keyboard(users_db[user_id]["ttt_board"]),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=ttt_text,
            reply_markup=get_ttt_keyboard(users_db[user_id]["ttt_board"]),
            parse_mode="HTML"
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("ttt_cell_"))
async def process_ttt_cell(callback: CallbackQuery):
    user_id = callback.from_user.id
    cell_idx = int(callback.data.split("_")[2])
    
    user_data = users_db.setdefault(user_id, {
        "points": 0,
        "ttt_board": [" "] * 9
    })
    board = user_data.setdefault("ttt_board", [" "] * 9)
    
    if board[cell_idx] != " ":
        await callback.answer("Bu katakcha band! 🚫", show_alert=True)
        return
        
    board[cell_idx] = "❌"
    
    winner = check_ttt_winner(board)
    if winner:
        await handle_ttt_end(callback, winner, board, user_data)
        return
        
    empty_cells = [i for i, val in enumerate(board) if val == " "]
    if empty_cells:
        bot_idx = random.choice(empty_cells)
        board[bot_idx] = "⭕"
        
        winner = check_ttt_winner(board)
        if winner:
            await handle_ttt_end(callback, winner, board, user_data)
            return

    try:
        await callback.message.edit_reply_markup(
            reply_markup=get_ttt_keyboard(board)
        )
    except Exception:
        pass
    await callback.answer()

@dp.callback_query(F.data == "ttt_forfeit")
async def process_ttt_forfeit(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.setdefault(user_id, {"points": 0})
    user_data["points"] = max(0, user_data.get("points", 0) - 5)
    
    text = (
        f"🏳️ <b>Siz taslim bo'ldingiz!</b>\n\n"
        f"Sizdan <b>-5 ball</b> ayirildi. 💔\n"
        f"Joriy balansingiz: <b>{user_data['points']} ball</b> 💎"
    )
    await callback.message.delete()
    await callback.message.answer(
        text=text,
        reply_markup=get_ttt_restart_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

async def handle_ttt_end(callback: CallbackQuery, winner: str, board: list, user_data: dict):
    if winner == "❌":
        user_data["points"] += 10
        msg_text = (
            f"🎉 <b>G'alaba!</b>\n\n"
            f"Siz botni mag'lub etdingiz! Sizga <b>+10 ball</b> berildi! 💰\n\n"
            f"Joriy balansingiz: <b>{user_data['points']} ball</b> 💎"
        )
    elif winner == "⭕":
        user_data["points"] = max(0, user_data["points"] - 5)
        msg_text = (
            f"💔 <b>Mag'lubiyat!</b>\n\n"
            f"Bot g'alaba qozondi! Sizdan <b>-5 ball</b> ayirildi.\n\n"
            f"Joriy balansingiz: <b>{user_data['points']} ball</b> 💎"
        )
    else:
        msg_text = (
            f"🤝 <b>Durang!</b>\n\n"
            f"Hech kim yutmadi. O'yin tenglik bilan yakunlandi.\n\n"
            f"Joriy balansingiz: <b>{user_data['points']} ball</b> 💎"
        )
        
    await callback.message.delete()
    
    board_visual = "\n".join([
        f"| {board[0]} | {board[1]} | {board[2]} |",
        f"| {board[3]} | {board[4]} | {board[5]} |",
        f"| {board[6]} | {board[7]} | {board[8]} |"
    ])
    
    final_text = f"{msg_text}\n\n<b>Yakuniy taxta:</b>\n<code>{board_visual}</code>"
    
    await callback.message.answer(
        text=final_text,
        reply_markup=get_ttt_restart_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

# --- Game 1: Tosh-Qaychi-Qog'oz ---
@dp.callback_query(F.data == "game_rps")
async def start_game_rps(callback: CallbackQuery):
    rps_text = (
        f"✊✌️✋ <b>Tosh-Qaychi-Qog'oz O'yini</b>\n\n"
        f"Kompyuterga qarshi o'ynang! G'alaba uchun **+3 ball**, mag'lubiyat uchun **-1 ball**.\n\n"
        f"Quyidagilardan birini tanlang: 👇"
    )
    await callback.message.delete()
    
    photo_path = os.path.join(os.path.dirname(__file__), "q1.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=rps_text,
            reply_markup=get_rps_keyboard(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=rps_text,
            reply_markup=get_rps_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("rps_"))
async def process_rps_choice(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.setdefault(user_id, {"name": callback.from_user.first_name, "points": 0})
    
    user_choice_raw = callback.data.split("_")[1]
    choices = {"tosh": "Tosh ✊", "qaychi": "Qaychi ✌️", "qogoz": "Qog'oz ✋"}
    user_choice = choices.get(user_choice_raw)
    
    # ✊✌️✋ Jonli animatsiya hissi (Visual countdown)
    animation_steps = [
        "✊ **Tosh...**",
        "✌️ **Qaychi...**",
        "✋ **Qog'oz...**",
        "⚡ **BATTLE!**"
    ]
    for anim in animation_steps:
        try:
            await callback.message.edit_caption(caption=anim, parse_mode="HTML") if callback.message.photo else await callback.message.edit_text(text=anim, parse_mode="HTML")
            await asyncio.sleep(0.4)
        except Exception:
            pass
            
    bot_choice_raw = random.choice(["tosh", "qaychi", "qogoz"])
    bot_choice = choices.get(bot_choice_raw)
    
    # Natijani aniqlash
    if user_choice_raw == bot_choice_raw:
        result = "🤝 **Durang!** Ballar o'zgarmadi."
        points_change = 0
    elif (user_choice_raw == "tosh" and bot_choice_raw == "qaychi") or \
         (user_choice_raw == "qaychi" and bot_choice_raw == "qogoz") or \
         (user_choice_raw == "qogoz" and bot_choice_raw == "tosh"):
        result = "🎉 **Siz yutdingiz!** (+3 ball)"
        points_change = 3
    else:
        result = "😢 **Siz yutqazdingiz!** (-1 ball)"
        points_change = -1
        
    user_data["points"] = max(0, user_data["points"] + points_change)
    
    result_text = (
        f"✊✌️✋ <b>Tosh-Qaychi-Qog'oz Natijasi:</b>\n\n"
        f"👤 Siz: <b>{user_choice}</b>\n"
        f"🤖 Bot: <b>{bot_choice}</b>\n\n"
        f"{result}\n\n"
        f"Sizning joriy balansingiz: <b>{user_data['points']} ball</b> 💎\n\n"
        f"Yana o'ynashni xohlaysizmi? 👇"
    )
    
    await callback.message.edit_caption(
        caption=result_text,
        reply_markup=get_rps_keyboard(),
        parse_mode="HTML"
    ) if callback.message.photo else await callback.message.edit_text(
        text=result_text,
        reply_markup=get_rps_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

# --- Game 2: Sonni top o'yini (Realistik tugma qisqarishi bilan) ---
@dp.callback_query(F.data == "game_guess")
async def start_game_guess(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.setdefault(user_id, {"name": callback.from_user.first_name, "points": 0})
    
    # O'yin holatini boshlang'ich sozlash
    secret = random.randint(1, 10)
    user_data["guess_game"] = {
        "secret": secret,
        "attempts": 3,
        "min_val": 1,
        "max_val": 10
    }
    
    guess_text = (
        f"🔢 <b>Sonni topish o'yini</b>\n\n"
        f"Men 1 dan 10 gacha bo'lgan son o'yladim. Uni **3 ta urinishda** toping! 🤔\n"
        f"G'alaba: **+5 ball** | Mag'lubiyat: **-2 ball**.\n\n"
        f"Taxminiy sonni tanlang: 👇"
    )
    
    await callback.message.delete()
    
    photo_path = os.path.join(os.path.dirname(__file__), "q2.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=guess_text,
            reply_markup=get_guess_keyboard(1, 10),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=guess_text,
            reply_markup=get_guess_keyboard(1, 10),
            parse_mode="HTML"
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("guess_num_"))
async def process_guess(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.setdefault(user_id, {"name": callback.from_user.first_name, "points": 0})
    
    game_state = user_data.setdefault("guess_game", {"secret": random.randint(1, 10), "attempts": 3, "min_val": 1, "max_val": 10})
    secret = game_state["secret"]
    attempts = game_state["attempts"]
    min_val = game_state.get("min_val", 1)
    max_val = game_state.get("max_val", 10)
    
    chosen = int(callback.data.split("_")[2])
    
    if attempts <= 0:
        await callback.answer("O'yin yakunlangan, qayta boshlang!", show_alert=True)
        return
        
    if chosen == secret:
        # G'alaba
        user_data["points"] += 5
        game_state["attempts"] = 0
        response_text = (
            f"🎉 <b>Tabriklaymiz! Sonni topdingiz!</b>\n\n"
            f"O'ylangan son haqiqatan ham **{secret}** edi! **+5 ball** qo'shildi! 💎\n\n"
            f"Joriy balansingiz: <b>{user_data['points']} ball</b> 💎"
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="Qayta o'ynash 🔄", callback_data="game_guess")
        builder.button(text="O'yinlar menyusi ⬅️", callback_data="btn_games_menu")
        builder.adjust(1)
        markup = builder.as_markup()
    else:
        attempts -= 1
        game_state["attempts"] = attempts
        
        # Matematik jihatdan oraliqni qisqartirish
        if chosen > secret:
            max_val = min(max_val, chosen - 1)
            hint = f"maxfiy sondan KATTA. (Kichikroq son tanlang)"
        else:
            min_val = max(min_val, chosen + 1)
            hint = f"maxfiy sondan KICHIK. (Kattaroq son tanlang)"
            
        game_state["min_val"] = min_val
        game_state["max_val"] = max_val
        
        if attempts > 0 and min_val <= max_val:
            response_text = (
                f"❌ <b>Xato taxmin!</b>\n\n"
                f"Siz tanlagan {chosen} soni {hint}.\n"
                f"Tavsiya etilgan oraliq: <b>{min_val} dan {max_val} gacha</b>.\n"
                f"Sizda yana <b>{attempts} ta</b> urinish qoldi! ⏳\n\n"
                f"Keraksiz tugmalar o'chirildi! Qolgan sonlardan birini tanlang: 👇"
            )
            markup = get_guess_keyboard(min_val, max_val)
        else:
            # Mag'lubiyat
            user_data["points"] = max(0, user_data["points"] - 2)
            response_text = (
                f"😢 <b>Imkoniyatlar tugadi!</b>\n\n"
                f"O'ylangan son **{secret}** edi. Sizdan **-2 ball** ayirildi. 💔\n\n"
                f"Joriy balansingiz: <b>{user_data['points']} ball</b> 💎"
            )
            builder = InlineKeyboardBuilder()
            builder.button(text="Qayta o'ynash 🔄", callback_data="game_guess")
            builder.button(text="O'yinlar menyusi ⬅️", callback_data="btn_games_menu")
            builder.adjust(1)
            markup = builder.as_markup()
            
    await callback.message.edit_caption(
        caption=response_text,
        reply_markup=markup,
        parse_mode="HTML"
    ) if callback.message.photo else await callback.message.edit_text(
        text=response_text,
        reply_markup=markup,
        parse_mode="HTML"
    )
    await callback.answer()

# --- Game 3: Omad G'ildiragi (Aylanish Animatsiyasi bilan) ---
@dp.callback_query(F.data == "game_wheel")
async def start_game_wheel(callback: CallbackQuery):
    wheel_text = (
        f"🎡 <b>Omad G'ildiragi</b>\n\n"
        f"G'ildirakni aylantirib, tasodifiy ballarni yutib oling yoki boy bering! 😉\n"
        f"(Spin qilish uchun 5 soniya oraliq cooldown mavjud)\n\n"
        f"Omadingizni sinab ko'rishga tayyormisiz? 👇"
    )
    await callback.message.delete()
    
    photo_path = os.path.join(os.path.dirname(__file__), "q3.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=wheel_text,
            reply_markup=get_wheel_keyboard(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=wheel_text,
            reply_markup=get_wheel_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()

@dp.callback_query(F.data == "wheel_spin")
async def process_wheel_spin(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.setdefault(user_id, {"name": callback.from_user.first_name, "points": 0, "last_spin_time": 0})
    
    current_time = time.time()
    last_spin = user_data.get("last_spin_time", 0)
    
    if current_time - last_spin < 5:
        remaining = int(5 - (current_time - last_spin))
        await callback.answer(f"G'ildirak hali aylanmoqda! Iltimos, {remaining} soniya kuting. ⏳", show_alert=True)
        return
        
    user_data["last_spin_time"] = current_time
    
    # 🎡 Realistik aylanish animatsiyasi (Emoji freymlari)
    spin_frames = [
        "🎡 <b>[ 👑 | 💎 | ⚡ | 💔 | 💀 ] G'ildirak aylanmoqda... 🌀</b>",
        "🎡 <b>[ 💀 | 👑 | 💎 | ⚡ | 💔 ] Tezlik oshmoqda... ⚡</b>",
        "🎡 <b>[ 💔 | 💀 | 👑 | 💎 | ⚡ ] Sekinlashmoqda... ⏳</b>",
        "🎡 <b>[ ⚡ | 💔 | 💀 | 👑 | 💎 ] Deyarli to'xtadi... 🎯</b>"
    ]
    
    for frame in spin_frames:
        try:
            await callback.message.edit_caption(caption=frame, parse_mode="HTML") if callback.message.photo else await callback.message.edit_text(text=frame, parse_mode="HTML")
            await asyncio.sleep(0.4)
        except Exception:
            pass
            
    # Tasodifiy mukofotlar
    prizes = [
        ("+10 ball 👑", 10),
        ("+5 ball ⭐", 5),
        ("+3 ball 💎", 3),
        ("+1 ball ⚡", 1),
        ("0 ball (Hech narsa) ⚪", 0),
        ("-1 ball 💔", -1),
        ("-3 ball 💀", -3),
        ("-5 ball 🌋", -5)
    ]
    prize_name, val = random.choice(prizes)
    
    mult = user_data.get("point_multiplier", 1)
    actual_val = val * mult if val > 0 else val
    user_data["points"] = max(0, user_data["points"] + actual_val)
    
    result_text = (
        f"🎡 <b>Omad G'ildiragi Natijasi:</b>\n\n"
        f"G'ildirak sizga: <b>{prize_name}</b> taqdim etdi!\n\n"
        f"Sizning joriy balansingiz: <b>{user_data['points']} ball</b> 💎\n\n"
        f"Yana aylantirib ko'rasizmi? 👇"
    )
    
    await callback.message.edit_caption(
        caption=result_text,
        reply_markup=get_wheel_keyboard(),
        parse_mode="HTML"
    ) if callback.message.photo else await callback.message.edit_text(
        text=result_text,
        reply_markup=get_wheel_keyboard(),
        parse_mode="HTML"
    )

# "Yordam ℹ️" tugmasi
@dp.callback_query(F.data == "btn_help")
async def process_help(callback: CallbackQuery):
    help_text = (
        f"📖 <b>Yordam bo'limi</b>\n\n"
        f"Bu bot onboarding marafoni va turli qiziqarli o'yinlarni o'z ichiga oladi.\n\n"
        f"<b>Qoidalar:</b>\n"
        f"• <b>Marafonda:</b> To'g'ri javob uchun +1 ball, xato javob uchun -1 ball.\n"
        f"• <b>O'yinlarda:</b> Har bir mini-o'yinning o'z yutuq va mag'lubiyat ballari bor.\n"
        f"• Ballar minimal 0 bo'ladi, ya'ni manfiyga tushmaydi."
    )
    await callback.message.delete()
    photo_path = os.path.join(os.path.dirname(__file__), "q3.png")
    if os.path.exists(photo_path):
        await callback.message.answer_photo(
            photo=FSInputFile(photo_path),
            caption=help_text,
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=help_text,
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()

# "Sozlamalar ⚙️" tugmasi
@dp.callback_query(F.data == "btn_settings")
async def process_settings(callback: CallbackQuery):
    settings_text = (
        f"⚙️ <b>Sozlamalar bo'limi</b>\n\n"
        f"Bu yerda siz bot sozlamalarini boshqarishingiz mumkin.\n\n"
        f"<i>(Hozircha sozlamalar demo rejimida ishlamoqda)</i>"
    )
    await callback.message.delete()
    photo_path = os.path.join(os.path.dirname(__file__), "q2.png")
    if os.path.exists(photo_path):
        await callback.message.answer_photo(
            photo=FSInputFile(photo_path),
            caption=settings_text,
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=settings_text,
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()

# --- AI Assistant Section ---
@dp.callback_query(F.data == "btn_ai_assistant")
async def process_ai_assistant(callback: CallbackQuery):
    ai_intro_text = (
        f"✍️ <b>AI Yordamchi (Sun'iy Intellekt Matn Yozuvchisi)</b>\n\n"
        f"Ushbu funksiya orqali siz istalgan mavzuda matn, insho, she'r yoki reklama postlarini yozdirishingiz mumkin!\n\n"
        f"<b>Iltimos, nima haqida yozish kerakligini xabarda yozib yuboring:</b>\n"
        f"<i>(Masalan: 'Futbol tarixi haqida insho', 'Kiberpank mashinalari haqida she'r')</i>"
    )
    
    user_id = callback.from_user.id
    users_db.setdefault(user_id, {})["state"] = "waiting_for_ai"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Orqaga ⬅️", callback_data="btn_back_to_menu")
    
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    photo_path = os.path.join(os.path.dirname(__file__), "downloader.png")
    if os.path.exists(photo_path):
        await callback.message.answer_photo(
            photo=FSInputFile(photo_path),
            caption=ai_intro_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=ai_intro_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()

# "Orqaga ⬅️" tugmasi handler (Bosh sahifaga qaytish)
@dp.callback_query(F.data == "btn_back_to_menu")
async def process_back_to_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    users_db.setdefault(user_id, {})["state"] = None
    user_name = callback.from_user.first_name
    user_points = users_db.get(user_id, {}).get("points", 0)
    
    welcome_text = (
        f"Salom, <b>{html.escape(user_name)}</b>! 👋\n\n"
        f"🤖 <b>Aqlli Telegram Botimizga</b> xush kelibsiz!\n\n"
        f"Bu yerda siz onboarding marafonini boshlashingiz yoki qiziqarli mini-o'yinlar o'ynab ball yig'ishingiz mumkin! 🎮💎\n\n"
        f"Joriy balansingiz: <b>{user_points} ball</b> 💎"
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    photo_path = os.path.join(os.path.dirname(__file__), "welcome.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=welcome_text,
            reply_markup=get_welcome_keyboard(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=welcome_text,
            reply_markup=get_welcome_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()

# ----------------- ADMIN PANEL HANDLERLARI -----------------

ADMIN_IDS = set()
env_admins = os.getenv("ADMIN_IDS")
if env_admins:
    for aid in env_admins.split(","):
        try:
            ADMIN_IDS.add(int(aid.strip()))
        except ValueError:
            pass

# Admin qilish buyrug'i
@dp.message(Command("make_admin"))
async def cmd_make_admin(message: Message):
    user_id = message.from_user.id
    ADMIN_IDS.add(user_id)
    
    # Adminga VIP status va ball taqdim etish
    user_data = users_db.setdefault(user_id, {
        "points": 0,
        "vip_status": False,
        "point_multiplier": 1,
        "helmet_color": "yellow",
        "unlocked_helmets": ["yellow"],
        "unlocked_skins": []
    })
    user_data["vip_status"] = True
    user_data["points"] = max(user_data.get("points", 0), 5000)
    
    await message.answer(
        "🎉 <b>Siz muvaffaqiyatli ravishda Admin ro'yxatiga qo'shildingiz!</b>\n\n"
        "🎁 Maxsus sovg'a: Sizga **VIP Status 🌟** berildi va testingiz uchun **5000 ball 💎** taqdim etildi!\n\n"
        "Endi botni boshqarish uchun /admin buyrug'ini yuboring.",
        parse_mode="HTML"
    )

# Adminlikdan chiqish buyrug'i
@dp.message(Command("exit_admin"))
async def cmd_exit_admin(message: Message):
    user_id = message.from_user.id
    if user_id in ADMIN_IDS:
        ADMIN_IDS.remove(user_id)
    
    user_data = users_db.get(user_id)
    if user_data:
        user_data["vip_status"] = False
        
    await message.answer(
        "👋 <b>Siz adminlikdan chiqdingiz!</b>\n\n"
        "Sizning VIP statusiz bekor qilindi va oddiy foydalanuvchi rejimiga qaytdingiz.",
        parse_mode="HTML"
    )

# Admin Panel klaviatura
def get_admin_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Statistika 📊", callback_data="admin_stats")
    builder.button(text="Xabar yuborish 📢", callback_data="admin_broadcast")
    builder.button(text="Ball qo'shish 💎", callback_data="admin_add_points")
    builder.button(text="Chiqish ❌", callback_data="admin_close")
    builder.adjust(1)
    return builder.as_markup()

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        await message.answer(
            "🚫 <b>Kechirasiz, siz admin emassiz!</b>\n\n"
            "Admin huquqini olish uchun /make_admin buyrug'ini yuboring.",
            parse_mode="HTML"
        )
        return
    
    await message.answer(
        "👮‍♂️ <b>Admin Paneliga xush kelibsiz!</b>\n\nQuyidagi amallardan birini tanlang:",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_menu")
async def process_admin_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("Ruxsat berilmagan! 🚫", show_alert=True)
        return
        
    await callback.message.edit_text(
        text="👮‍♂️ <b>Admin Paneliga xush kelibsiz!</b>\n\nQuyidagi amallardan birini tanlang:",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def process_admin_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("Ruxsat berilmagan! 🚫", show_alert=True)
        return
        
    total_users = len(users_db)
    total_points = sum(u.get("points", 0) for u in users_db.values())
    avg_points = total_points / total_users if total_users > 0 else 0
    revenue = get_revenue()
    
    stats_text = (
        f"📊 <b>Bot Statistikasi (Faqat Admin uchun)</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users} ta</b>\n"
        f"💎 Jami yig'ilgan ballar: <b>{total_points} ball</b>\n"
        f"🎯 O'rtacha ko'rsatkich: <b>{avg_points:.1f} ball/user</b>\n\n"
        f"💸 <b>JAMI DAROMAD (Tushum):</b> <code>{revenue:,} so'm</code> 💳"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Orqaga ⬅️", callback_data="admin_menu")
    
    await callback.message.edit_text(
        text=stats_text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_close")
async def process_admin_close(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def process_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("Ruxsat berilmagan! 🚫", show_alert=True)
        return
        
    await state.set_state(AdminStates.waiting_for_broadcast)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Bekor qilish ❌", callback_data="admin_cancel")
    
    await callback.message.edit_text(
        text="📢 <b>Foydalanuvchilarga xabar yuborish</b>\n\nYubormoqchi bo'lgan xabaringiz matnini kiriting:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_cancel")
async def process_admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        text="👮‍♂️ <b>Admin Paneliga xush kelibsiz!</b>\n\nQuyidagi amallardan birini tanlang:",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(AdminStates.waiting_for_broadcast)
async def process_broadcast_text(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return
        
    broadcast_text = message.text
    await state.clear()
    
    status_msg = await message.answer("📤 <i>Xabar barcha a'zolarga yuborilmoqda, kuting...</i>", parse_mode="HTML")
    
    success = 0
    failed = 0
    
    for uid in list(users_db.keys()):
        try:
            await message.bot.send_message(chat_id=uid, text=broadcast_text, parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
            
    await status_msg.edit_text(
        text=f"✅ <b>Yuborish yakunlandi!</b>\n\n"
             f"👤 Muvaffaqiyatli yuborildi: <b>{success} ta</b>\n"
             f"🚫 Bloklagan/Xatolik: <b>{failed} ta</b>",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_add_points")
async def process_admin_add_points(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("Ruxsat berilmagan! 🚫", show_alert=True)
        return
        
    await state.set_state(AdminStates.waiting_for_points_user)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Bekor qilish ❌", callback_data="admin_cancel")
    
    await callback.message.edit_text(
        text="💎 <b>Foydalanuvchiga ball qo'shish</b>\n\nKimga ball qo'shmoqchisiz? O'yinchining Telegram ID raqamini yozing:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(AdminStates.waiting_for_points_user)
async def process_points_user(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return
        
    try:
        target_uid = int(message.text.strip())
        if target_uid not in users_db:
            await message.answer("❌ Bunday foydalanuvchi topilmadi! Qayta kiriting yoki bekor qiling:")
            return
            
        await state.update_data(target_uid=target_uid)
        await state.set_state(AdminStates.waiting_for_points_amount)
        await message.answer(f"Qancha ball bermoqchisiz? (Masalan, 100):")
    except ValueError:
        await message.answer("❌ Iltimos, faqat raqamli Telegram ID yozing:")

@dp.message(AdminStates.waiting_for_points_amount)
async def process_points_amount(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return
        
    try:
        amount = int(message.text.strip())
        data = await state.get_data()
        target_uid = data["target_uid"]
        await state.clear()
        
        users_db[target_uid]["points"] += amount
        
        try:
            await message.bot.send_message(
                chat_id=target_uid,
                text=f"🎁 <b>Admin sizga {amount} bonus ball yubordi!</b>\n\nJoriy balansingiz: <b>{users_db[target_uid]['points']} ball</b> 💎",
                parse_mode="HTML"
            )
        except Exception:
            pass
            
        await message.answer(
            text=f"✅ <b>Muvaffaqiyatli!</b>\n\nFoydalanuvchiga <b>{amount} ball</b> qo'shildi.",
            reply_markup=get_admin_keyboard(),
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Iltimos, faqat musbat raqam kiriting:")

# --- VIRTUAL DO'KON TIZIMI (SHOP) ---

def get_shop_keyboard(user_data):
    builder = InlineKeyboardBuilder()
    
    vip_text = "🌟 VIP Status [Sotib olingan]" if user_data.get("vip_status", False) else "🌟 VIP Status (💰500 ball)"
    mult_text = f"⚡ 2x Ko'paytirgich [Sotib olingan]" if user_data.get("point_multiplier", 1) == 2 else "⚡ 2x Ko'paytirgich (💰250 ball)"
    
    red_text = "🔴 Qizil Dubulg'a [Sotib olingan]" if "red" in user_data.get("unlocked_helmets", []) else "🔴 Qizil Dubulg'a (💰150 ball)"
    gold_text = "👑 Oltin Dubulg'a [Sotib olingan]" if "gold" in user_data.get("unlocked_helmets", []) else "👑 Oltin Dubulg'a (💰350 ball)"
    
    active_helmet = user_data.get("helmet_color", "yellow")
    if active_helmet == "red":
        red_text += " [Aktiv]"
    elif active_helmet == "gold":
        gold_text += " [Aktiv]"
        
    jetpack_text = "🎒 Jetpack (Speed +50%) [Sotib olingan]" if user_data.get("jetpack_unlocked", False) else "🎒 Jetpack (Speed +50%) (💰400 ball)"
    
    unlocked_skins = user_data.setdefault("unlocked_skins", [])
    
    neon_text = "👽 Neon Quruvchi Skini [Sotib olingan]" if "neon" in unlocked_skins else "👽 Neon Quruvchi Skini (💰300 ball)"
    robot_text = "🤖 Robot Quruvchi Skini [Sotib olingan]" if "robot" in unlocked_skins else "🤖 Robot Quruvchi Skini (💰450 ball)"
    
    active_skin = user_data.get("builder_skin", "standard")
    if active_skin == "neon":
        neon_text += " [Aktiv]"
    elif active_skin == "robot":
        robot_text += " [Aktiv]"
        
    dino_skin_text = "🐉 Kiber Ajdarho (Dino) [Sotib olingan]" if "dino_dragon" in unlocked_skins else "🐉 Kiber Ajdarho (Dino) (💰200 ball)"
    stack_skin_text = "🌌 Koinot Bloklari (Stack) [Sotib olingan]" if "stack_cosmic" in unlocked_skins else "🌌 Koinot Bloklari (Stack) (💰200 ball)"
    flappy_skin_text = "🚀 Falcon Raketasi (Flappy) [Sotib olingan]" if "flappy_rocket" in unlocked_skins else "🚀 Falcon Raketasi (Flappy) (💰200 ball)"
    
    builder.button(text=vip_text, callback_data="buy_vip")
    builder.button(text=mult_text, callback_data="buy_multiplier")
    builder.button(text="🎡 Omad G'ildiragi +1 (💰100 ball)", callback_data="buy_spin")
    builder.button(text=red_text, callback_data="buy_helmet_red")
    builder.button(text=gold_text, callback_data="buy_helmet_gold")
    builder.button(text=jetpack_text, callback_data="buy_jetpack")
    builder.button(text=neon_text, callback_data="buy_skin_neon")
    builder.button(text=robot_text, callback_data="buy_skin_robot")
    builder.button(text=dino_skin_text, callback_data="buy_skin_dino")
    builder.button(text=stack_skin_text, callback_data="buy_skin_stack")
    builder.button(text=flappy_skin_text, callback_data="buy_skin_flappy")
    builder.button(text="💎 Ball Sotib Olish 💳", callback_data="buy_points_menu")
    builder.button(text="Orqaga ⬅️", callback_data="btn_back_to_menu")
    builder.adjust(1)
    return builder.as_markup()

@dp.callback_query(F.data == "btn_shop")
async def process_shop_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.setdefault(user_id, {
        "points": 0,
        "vip_status": False,
        "point_multiplier": 1,
        "helmet_color": "yellow",
        "unlocked_helmets": ["yellow"]
    })
    
    shop_text = (
        f"🛒 <b>Virtual Do'konga xush kelibsiz!</b>\n\n"
        f"To'plagan ballaringiz evaziga bot va o'yinlar uchun maxsus yangilanishlar sotib oling! 💎\n\n"
        f"Sizning balansingiz: <b>{user_data.get('points', 0)} ball</b> 💎"
    )
    
    await callback.message.delete()
    photo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=shop_text,
            reply_markup=get_shop_keyboard(user_data),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=shop_text,
            reply_markup=get_shop_keyboard(user_data),
            parse_mode="HTML"
        )
    await callback.answer()

@dp.callback_query(F.data == "buy_vip")
async def process_buy_vip(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.get(user_id, {})
    if user_data.get("vip_status", False):
        await callback.answer("Sizda VIP status allaqachon mavjud! ✨", show_alert=True)
        return
        
    points = user_data.get("points", 0)
    if points >= 500:
        user_data["points"] -= 500
        user_data["vip_status"] = True
        await callback.answer("Tabriklaymiz! 🌟 VIP Status muvaffaqiyatli sotib olindi!", show_alert=True)
        await process_shop_menu(callback)
    else:
        await callback.answer("Mablag' yetarli emas! 💔 Yana 💰500 ball yig'ing.", show_alert=True)

@dp.callback_query(F.data == "buy_multiplier")
async def process_buy_multiplier(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.get(user_id, {})
    if user_data.get("point_multiplier", 1) == 2:
        await callback.answer("Sizda 2x Ko'paytirgich allaqachon faol! ⚡", show_alert=True)
        return
        
    points = user_data.get("points", 0)
    if points >= 250:
        user_data["points"] -= 250
        user_data["point_multiplier"] = 2
        await callback.answer("Tabriklaymiz! ⚡ Endi barcha ballaringiz 2 barobar ko'p hisoblanadi!", show_alert=True)
        await process_shop_menu(callback)
    else:
        await callback.answer("Mablag' yetarli emas! 💔 Yana 💰250 ball yig'ing.", show_alert=True)

@dp.callback_query(F.data == "buy_spin")
async def process_buy_spin(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.get(user_id, {})
    points = user_data.get("points", 0)
    if points >= 100:
        user_data["points"] -= 100
        user_data["last_spin_time"] = 0
        await callback.answer("Tabriklaymiz! Omad g'ildiragi zudlik bilan qayta aylantirish uchun tayyor! 🎡", show_alert=True)
        await process_shop_menu(callback)
    else:
        await callback.answer("Mablag' yetarli emas! 💔 Yana 💰100 ball yig'ing.", show_alert=True)

@dp.callback_query(F.data == "buy_helmet_red")
async def process_buy_helmet_red(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.get(user_id, {})
    unlocked = user_data.setdefault("unlocked_helmets", ["yellow"])
    
    if "red" in unlocked:
        user_data["helmet_color"] = "yellow" if user_data.get("helmet_color", "yellow") == "red" else "red"
        await callback.answer(f"Dubulg'a rangi {user_data['helmet_color'].upper()} qilib o'zgartirildi! 🎨", show_alert=True)
        await process_shop_menu(callback)
        return
        
    points = user_data.get("points", 0)
    if points >= 150:
        user_data["points"] -= 150
        unlocked.append("red")
        user_data["helmet_color"] = "red"
        await callback.answer("Tabriklaymiz! 🔴 Qizil dubulg'a sotib olindi va faollashtirildi!", show_alert=True)
        await process_shop_menu(callback)
    else:
        await callback.answer("Mablag' yetarli emas! 💔 Yana 💰150 ball yig'ing.", show_alert=True)

@dp.callback_query(F.data == "buy_helmet_gold")
async def process_buy_helmet_gold(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.get(user_id, {})
    unlocked = user_data.setdefault("unlocked_helmets", ["yellow"])
    
    if "gold" in unlocked:
        user_data["helmet_color"] = "yellow" if user_data.get("helmet_color", "yellow") == "gold" else "gold"
        await callback.answer(f"Dubulg'a rangi {user_data['helmet_color'].upper()} qilib o'zgartirildi! 🎨", show_alert=True)
        await process_shop_menu(callback)
        return
        
    points = user_data.get("points", 0)
    if points >= 350:
        user_data["points"] -= 350
        unlocked.append("gold")
        user_data["helmet_color"] = "gold"
        await callback.answer("Tabriklaymiz! 👑 Oltin dubulg'a sotib olindi va faollashtirildi!", show_alert=True)
        await process_shop_menu(callback)
    else:
        await callback.answer("Mablag' yetarli emas! 💔 Yana 💰350 ball yig'ing.", show_alert=True)

# --- BALL SOTIB OLISH (PAYMENTS) ---

def get_points_packages_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 100 ball — 10,000 so'm", callback_data="buy_points_100")
    builder.button(text="💎 500 ball — 45,000 so'm", callback_data="buy_points_500")
    builder.button(text="💎 1000 ball — 80,000 so'm", callback_data="buy_points_1000")
    builder.button(text="Orqaga ⬅️", callback_data="btn_shop")
    builder.adjust(1)
    return builder.as_markup()

@dp.callback_query(F.data == "buy_points_menu")
async def process_buy_points_menu(callback: CallbackQuery):
    await callback.message.delete()
    
    text = (
        f"💎 <b>Ball sotib olish (To'lov xizmati)</b>\n\n"
        f"Kerakli ball miqdorini tanlang va Click/Payme orqali virtual to'lovni yakunlang: 👇"
    )
    photo_path = os.path.join(os.path.dirname(__file__), "welcome.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_points_packages_keyboard(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=text,
            reply_markup=get_points_packages_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_points_"))
async def process_points_purchase_confirm(callback: CallbackQuery):
    data = callback.data.split("_")
    if len(data) < 3 or data[2] == "menu":
        return
        
    points_amount = int(data[2])
    cost = 10000 if points_amount == 100 else (45000 if points_amount == 500 else 80000)
    
    text = (
        f"💸 <b>To'lovni tasdiqlash</b>\n\n"
        f"<b>Paket:</b> {points_amount} ball 💎\n"
        f"<b>Narxi:</b> {cost:,} so'm\n\n"
        f"Virtual to'lovni tasdiqlash uchun quyidagi tugmani bosing: 👇"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="CLICK / PAYME orqali to'lash 💳", callback_data=f"pay_confirm_{points_amount}_{cost}")
    builder.button(text="Bekor qilish ❌", callback_data="buy_points_menu")
    builder.adjust(1)
    
    await callback.message.delete()
    photo_path = os.path.join(os.path.dirname(__file__), "welcome.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("pay_confirm_"))
async def process_pay_confirm(callback: CallbackQuery):
    parts = callback.data.split("_")
    points_amount = int(parts[2])
    cost = int(parts[3])
    
    user_id = callback.from_user.id
    user_data = users_db.setdefault(user_id, {"points": 0})
    user_data["points"] += points_amount
    
    add_revenue(cost)
    
    success_text = (
        f"✅ <b>To'lov muvaffaqiyatli yakunlandi!</b>\n\n"
        f"Sizning hisobingizga <b>+{points_amount} ball</b> qo'shildi! 🚀\n"
        f"Joriy balansingiz: <b>{user_data['points']} ball</b> 💎"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Do'konga qaytish 🛒", callback_data="btn_shop")
    builder.button(text="Asosiy menyu ⬅️", callback_data="btn_back_to_menu")
    builder.adjust(1)
    
    await callback.message.delete()
    photo_path = os.path.join(os.path.dirname(__file__), "welcome.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=success_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=success_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    
    await callback.answer(f"Hisobingizga +{points_amount} ball qo'shildi! 🎉", show_alert=True)

# --- PREMIUM XARIDLAR VA SKINLAR CALLBACKLARI ---

@dp.callback_query(F.data == "buy_jetpack")
async def process_buy_jetpack(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.get(user_id, {})
    if user_data.get("jetpack_unlocked", False):
        await callback.answer("Sizda Jetpack allaqachon sotib olingan! 🎒", show_alert=True)
        return
        
    points = user_data.get("points", 0)
    if points >= 400:
        user_data["points"] -= 400
        user_data["jetpack_unlocked"] = True
        await callback.answer("Tabriklaymiz! 🎒 Reaktiv Ranset (Jetpack) muvaffaqiyatli sotib olindi va faollashdi!", show_alert=True)
        await process_shop_menu(callback)
    else:
        await callback.answer("Mablag' yetarli emas! 💔 Yana 💰400 ball yig'ing.", show_alert=True)

@dp.callback_query(F.data == "buy_skin_neon")
async def process_buy_skin_neon(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.get(user_id, {})
    unlocked = user_data.setdefault("unlocked_skins", [])
    
    if "neon" in unlocked:
        user_data["builder_skin"] = "standard" if user_data.get("builder_skin", "standard") == "neon" else "neon"
        await callback.answer(f"Quruvchi skini {user_data['builder_skin'].upper()} qilib belgilandi! 🎨", show_alert=True)
        await process_shop_menu(callback)
        return
        
    points = user_data.get("points", 0)
    if points >= 300:
        user_data["points"] -= 300
        unlocked.append("neon")
        user_data["builder_skin"] = "neon"
        await callback.answer("Tabriklaymiz! 👽 Neon Quruvchi skini sotib olindi va faollashtirildi!", show_alert=True)
        await process_shop_menu(callback)
    else:
        await callback.answer("Mablag' yetarli emas! 💔 Yana 💰300 ball yig'ing.", show_alert=True)

@dp.callback_query(F.data == "buy_skin_robot")
async def process_buy_skin_robot(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.get(user_id, {})
    unlocked = user_data.setdefault("unlocked_skins", [])
    
    if "robot" in unlocked:
        user_data["builder_skin"] = "standard" if user_data.get("builder_skin", "standard") == "robot" else "robot"
        await callback.answer(f"Quruvchi skini {user_data['builder_skin'].upper()} qilib belgilandi! 🎨", show_alert=True)
        await process_shop_menu(callback)
        return
        
    points = user_data.get("points", 0)
    if points >= 450:
        user_data["points"] -= 450
        unlocked.append("robot")
        user_data["builder_skin"] = "robot"
        await callback.answer("Tabriklaymiz! 🤖 Robot Quruvchi skini sotib olindi va faollashtirildi!", show_alert=True)
        await process_shop_menu(callback)
    else:
        await callback.answer("Mablag' yetarli emas! 💔 Yana 💰450 ball yig'ing.", show_alert=True)

@dp.callback_query(F.data == "buy_skin_dino")
async def process_buy_skin_dino(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.get(user_id, {})
    unlocked = user_data.setdefault("unlocked_skins", [])
    
    if "dino_dragon" in unlocked:
        await callback.answer("Sizda ushbu skin allaqachon sotib olingan! 🐉 Dino Run o'yinini boshlaganingizda faollashadi.", show_alert=True)
        return
        
    points = user_data.get("points", 0)
    if points >= 200:
        user_data["points"] -= 200
        unlocked.append("dino_dragon")
        await callback.answer("Tabriklaymiz! 🐉 Kiber Ajdarho skini sotib olindi va Dino Run o'yiniga ulandi!", show_alert=True)
        await process_shop_menu(callback)
    else:
        await callback.answer("Mablag' yetarli emas! 💔 Yana 💰200 ball yig'ing.", show_alert=True)

@dp.callback_query(F.data == "buy_skin_stack")
async def process_buy_skin_stack(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.get(user_id, {})
    unlocked = user_data.setdefault("unlocked_skins", [])
    
    if "stack_cosmic" in unlocked:
        await callback.answer("Sizda ushbu skin allaqachon sotib olingan! 🌌 Tower Stack o'yinini boshlaganingizda faollashadi.", show_alert=True)
        return
        
    points = user_data.get("points", 0)
    if points >= 200:
        user_data["points"] -= 200
        unlocked.append("stack_cosmic")
        await callback.answer("Tabriklaymiz! 🌌 Koinot Bloklari skini sotib olindi va Tower Stack o'yiniga ulandi!", show_alert=True)
        await process_shop_menu(callback)
    else:
        await callback.answer("Mablag' yetarli emas! 💔 Yana 💰200 ball yig'ing.", show_alert=True)

@dp.callback_query(F.data == "buy_skin_flappy")
async def process_buy_skin_flappy(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_db.get(user_id, {})
    unlocked = user_data.setdefault("unlocked_skins", [])
    
    if "flappy_rocket" in unlocked:
        await callback.answer("Sizda ushbu skin allaqachon sotib olingan! 🚀 Falcon Raketasi o'yinni boshlaganingizda faollashadi.", show_alert=True)
        return
        
    points = user_data.get("points", 0)
    if points >= 200:
        user_data["points"] -= 200
        unlocked.append("flappy_rocket")
        await callback.answer("Tabriklaymiz! 🚀 Falcon Raketasi skini sotib olindi va Flappy o'yiniga ulandi!", show_alert=True)
        await process_shop_menu(callback)
    else:
        await callback.answer("Mablag' yetarli emas! 💔 Yana 💰200 ball yig'ing.", show_alert=True)

@dp.callback_query(F.data == "btn_leaderboard")
async def process_leaderboard(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    sorted_users = sorted(
        users_db.items(),
        key=lambda item: item[1].get("points", 0),
        reverse=True
    )
    
    my_rank = 0
    for idx, (uid, data) in enumerate(sorted_users):
        if uid == user_id:
            my_rank = idx + 1
            break
            
    my_points = users_db.get(user_id, {}).get("points", 0)
    
    leaderboard_text = "🏆 <b>KUCHLI O'YINCHILAR REYTINGI (TOP 10)</b>\n\n"
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    top_10 = sorted_users[:10]
    for idx, (uid, data) in enumerate(top_10):
        name = html.escape(data.get("name", "Quruvchi"))
        points = data.get("points", 0)
        vip_tag = " 🌟" if data.get("vip_status", False) else ""
        medal = medals[idx] if idx < len(medals) else f"[{idx+1}]"
        leaderboard_text += f"{medal} {name}{vip_tag} — <b>{points:,} ball</b>\n"
        
    if not top_10:
        leaderboard_text += "⏳ Reyting hali shakllanmagan. Birinchi bo'lib ball to'plang!\n"
        
    leaderboard_text += f"\n---------------------------------\n"
    leaderboard_text += f"👤 Sizning o'rningiz: <b>#{my_rank if my_rank > 0 else 'Noma\'lum'}</b> (<b>{my_points:,} ball</b>)"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Yangilash 🔄", callback_data="btn_leaderboard")
    builder.button(text="Orqaga ⬅️", callback_data="btn_back_to_menu")
    builder.adjust(1)
    
    await callback.message.delete()
    photo_path = os.path.join(os.path.dirname(__file__), "q1.png")
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=leaderboard_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            text=leaderboard_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()

# --- INSTAGRAM REELS/VIDEO DOWNLOADER HANDLER ---

DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

@dp.message(lambda msg: msg.text and ("instagram.com/" in msg.text))
async def handle_instagram_link(message: Message):
    urls = re.findall(r'https?://[^\s]+instagram\.com/[^\s]+', message.text)
    if not urls:
        await message.reply("❌ Xato: Xabaringizda to'g'ri Instagram havolasi topilmadi.")
        return
        
    url = urls[0]
    status_msg = await message.reply("📥 <b>Instagram video aniqlandi!</b>\n\nYuklab olinmoqda, iltimos kuting... ⏳", parse_mode="HTML")
    
    file_id = f"ig_{int(time.time())}_{random.randint(1000, 9999)}"
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    video_template = os.path.join(DOWNLOADS_DIR, f"{file_id}.%(ext)s")
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': video_template,
        'ffmpeg_location': ffmpeg_path,
        'quiet': True,
        'no_warnings': True,
    }
    
    video_filename = None
    audio_filename = None
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_filename = ydl.prepare_filename(info)
            
        if not video_filename or not os.path.exists(video_filename):
            raise Exception("Yuklangan video fayli topilmadi.")
            
        if os.path.getsize(video_filename) > 50 * 1024 * 1024:
            await status_msg.edit_text("⚠️ Video hajmi juda katta (50MB dan ortiq). Telegram orqali yuborib bo'lmaydi.")
            if os.path.exists(video_filename):
                os.remove(video_filename)
            return

        await status_msg.edit_text("🎵 <b>Video yuklandi!</b>\nMusiqa ajratib olinmoqda... ⏳", parse_mode="HTML")
        
        audio_filename = os.path.splitext(video_filename)[0] + ".mp3"
        ffmpeg_cmd = [
            ffmpeg_path,
            '-y',
            '-i', video_filename,
            '-vn',
            '-acodec', 'libmp3lame',
            '-q:a', '2',
            audio_filename
        ]
        
        subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        await status_msg.edit_text("📤 <b>Yuborilmoqda...</b> 🚀", parse_mode="HTML")
        
        await message.reply_video(
            video=FSInputFile(video_filename),
            caption="🎥 <b>Instagram Reels</b>\n\n@SBR_Nexus_bot orqali yuklandi 🚀",
            parse_mode="HTML"
        )
        
        if os.path.exists(audio_filename):
            title = info.get('title', 'Instagram Music')
            uploader = info.get('uploader', 'Instagram')
            
            await message.reply_audio(
                audio=FSInputFile(audio_filename),
                caption="🎵 <b>Reels Musiqasi</b>\n\n@SBR_Nexus_bot orqali ajratildi 🚀",
                title=title,
                performer=uploader,
                parse_mode="HTML"
            )
            
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Instagram download error: {e}")
        await status_msg.edit_text("❌ <b>Xatolik yuz berdi!</b>\n\nInstagram videoni yuklab bo'lmadi. Havola to'g'ri ekanligini yoki video ommaviy (public) sahifada ekanligini tekshiring.", parse_mode="HTML")
    finally:
        if video_filename and os.path.exists(video_filename):
            try:
                os.remove(video_filename)
            except Exception:
                pass
        if audio_filename and os.path.exists(audio_filename):
            try:
                os.remove(audio_filename)
            except Exception:
                pass

# --- AI MATN YARATISH TIZIMI ---
def markdown_to_html(text: str) -> str:
    import re
    text = html.escape(text)
    text = re.sub(r'```(.*?)```', r'<pre><code>\1</code></pre>', text, flags=re.DOTALL)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    return text

async def handle_ai_generation(message: Message):
    import aiohttp
    prompt = message.text.strip()
    status_msg = await message.reply("⏳ <b>Sun'iy intellekt matn yozmoqda, iltimos kuting...</b>", parse_mode="HTML")
    
    url = "https://text.pollinations.ai/"
    payload = {
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "model": "openai",
        "jsonMode": False
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    result_text = await response.text()
                    if result_text:
                        formatted_result = markdown_to_html(result_text)
                        
                        if len(formatted_result) > 3500:
                            parts = [formatted_result[i:i+3500] for i in range(0, len(formatted_result), 3500)]
                            await status_msg.delete()
                            for idx, part in enumerate(parts):
                                caption_part = f"✍️ <b>Sun'iy Intellekt Natijasi (Qism {idx+1}):</b>\n\n{part}"
                                await message.reply(caption_part, parse_mode="HTML")
                        else:
                            ai_caption = f"✍️ <b>Sun'iy Intellekt Natijasi:</b>\n\n{formatted_result}"
                            await status_msg.edit_text(ai_caption, parse_mode="HTML")
                    else:
                        await status_msg.edit_text("❌ Sun'iy intellektdan bo'sh javob qaytdi. Qayta urinib ko'ring.")
                else:
                    await status_msg.edit_text("❌ AI xizmati vaqtincha band. Keyinroq urinib ko'ring.")
    except Exception as e:
        await status_msg.edit_text(f"❌ Kutilmagan xatolik yuz berdi: {str(e)}")

# --- YOUTUBE QIDIRUV VA YUKLASH TIZIMI ---

@dp.message(lambda msg: msg.text and not msg.text.startswith("/") and "instagram.com/" not in msg.text)
async def handle_youtube_search(message: Message):
    user_id = message.from_user.id
    user_data = users_db.setdefault(user_id, {})
    if user_data.get("state") == "waiting_for_ai":
        user_data["state"] = None
        await handle_ai_generation(message)
        return
        
    query = message.text.strip()
    status_msg = await message.reply(f"🔍 <b>\"{query}\"</b> bo'yicha YouTube'dan qidirilmoqda... ⏳", parse_mode="HTML")
    
    ydl_opts = {
        'extract_flat': 'in_playlist',
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            results = ydl.extract_info(f"ytsearch5:{query}", download=False)
            entries = results.get('entries', [])
            
        if not entries:
            await status_msg.edit_text("❌ Hech qanday video topilmadi. Boshqa so'zlar bilan qidirib ko'ring.")
            return
            
        text = f"🔎 <b>Qidiruv natijalari: \"{html.escape(query)}\"</b>\n\n"
        builder = InlineKeyboardBuilder()
        
        for idx, entry in enumerate(entries):
            vid_id = entry.get('id')
            title = entry.get('title', 'Video')
            duration_sec = entry.get('duration')
            
            duration_str = ""
            if duration_sec:
                m, s = divmod(int(duration_sec), 60)
                h, m = divmod(m, 60)
                if h > 0:
                    duration_str = f" ({h:02d}:{m:02d}:{s:02d})"
                else:
                    duration_str = f" ({m:02d}:{s:02d})"
            
            text += f"{idx+1}️⃣ <b>{html.escape(title)}</b>{duration_str}\n\n"
            
            builder.button(text=f"🎥 {idx+1} Video", callback_data=f"yt_vid_{vid_id}")
            builder.button(text=f"🎵 {idx+1} Musiqa", callback_data=f"yt_aud_{vid_id}")
            
        text += "Yuklab olish uchun quyidagi tugmalarni bosing: 👇"
        builder.adjust(2)
        
        await status_msg.delete()
        photo_path = os.path.join(os.path.dirname(__file__), "downloader.png")
        if os.path.exists(photo_path):
            await message.reply_photo(
                photo=FSInputFile(photo_path),
                caption=text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        else:
            await message.reply(text=text, reply_markup=builder.as_markup(), parse_mode="HTML")
        
    except Exception as e:
        logging.error(f"YouTube search error: {e}")
        await status_msg.edit_text("❌ Qidiruv davomida xatolik yuz berdi. Iltimos qaytadan urinib ko'ring.")

@dp.callback_query(F.data.startswith("yt_vid_"))
async def process_youtube_video_download(callback: CallbackQuery):
    video_id = callback.data.split("_")[2]
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    status_msg = await callback.message.reply("📥 Video yuklab olinmoqda... ⏳")
    await callback.answer("Video yuklanmoqda...")
    
    file_id = f"yt_{video_id}_{int(time.time())}"
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    video_template = os.path.join(DOWNLOADS_DIR, f"{file_id}.%(ext)s")
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': video_template,
        'ffmpeg_location': ffmpeg_path,
        'quiet': True,
        'no_warnings': True,
    }
    
    video_filename = None
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_filename = ydl.prepare_filename(info)
            title = info.get('title', 'Video')
            
        if not video_filename or not os.path.exists(video_filename):
            raise Exception("Yuklangan video fayli topilmadi.")
            
        if os.path.getsize(video_filename) > 50 * 1024 * 1024:
            await status_msg.edit_text("⚠️ Video hajmi juda katta (50MB dan ortiq). Faqat musiqasini yuklab olishingiz mumkin.")
            if os.path.exists(video_filename):
                os.remove(video_filename)
            return

        await status_msg.edit_text("📤 Yuborilmoqda... 🚀")
        
        await callback.message.reply_video(
            video=FSInputFile(video_filename),
            caption=f"🎥 <b>{html.escape(title)}</b>\n\n@SBR_Nexus_bot orqali yuklandi 🚀",
            parse_mode="HTML"
        )
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"YouTube video download error: {e}")
        await status_msg.edit_text("❌ Videoni yuklab bo'lmadi. Havola bloklangan yoki video xususiy bo'lishi mumkin.")
    finally:
        if video_filename and os.path.exists(video_filename):
            try:
                os.remove(video_filename)
            except Exception:
                pass

@dp.callback_query(F.data.startswith("yt_aud_"))
async def process_youtube_audio_download(callback: CallbackQuery):
    video_id = callback.data.split("_")[2]
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    status_msg = await callback.message.reply("📥 Musiqa yuklab olinmoqda... ⏳")
    await callback.answer("Musiqa yuklanmoqda...")
    
    file_id = f"yt_{video_id}_{int(time.time())}"
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    video_template = os.path.join(DOWNLOADS_DIR, f"{file_id}.%(ext)s")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': video_template,
        'ffmpeg_location': ffmpeg_path,
        'quiet': True,
        'no_warnings': True,
    }
    
    video_filename = None
    audio_filename = None
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_filename = ydl.prepare_filename(info)
            title = info.get('title', 'Music')
            uploader = info.get('uploader', 'YouTube')
            
        if not video_filename or not os.path.exists(video_filename):
            raise Exception("Yuklangan video fayli topilmadi.")

        await status_msg.edit_text("🎵 Musiqa ajratib olinmoqda... ⏳")
        
        audio_filename = os.path.splitext(video_filename)[0] + ".mp3"
        ffmpeg_cmd = [
            ffmpeg_path,
            '-y',
            '-i', video_filename,
            '-vn',
            '-acodec', 'libmp3lame',
            '-q:a', '2',
            audio_filename
        ]
        
        subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        await status_msg.edit_text("📤 Yuborilmoqda... 🚀")
        
        await callback.message.reply_audio(
            audio=FSInputFile(audio_filename),
            caption=f"🎵 <b>{html.escape(title)}</b>\n\n@SBR_Nexus_bot orqali yuklandi 🚀",
            title=title,
            performer=uploader,
            parse_mode="HTML"
        )
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"YouTube audio download error: {e}")
        await status_msg.edit_text("❌ Musiqani yuklab bo'lmadi. Iltimos keyinroq urinib ko'ring.")
    finally:
        if video_filename and os.path.exists(video_filename):
            try:
                os.remove(video_filename)
            except Exception:
                pass
        if audio_filename and os.path.exists(audio_filename):
            try:
                os.remove(audio_filename)
            except Exception:
                pass

# Asosiy ishga tushirish funksiyasi
async def main() -> None:
    print("Bot ishga tushdi...")
    load_users()
    dp.message.outer_middleware(AutoSaveMiddleware())
    dp.callback_query.outer_middleware(AutoSaveMiddleware())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
