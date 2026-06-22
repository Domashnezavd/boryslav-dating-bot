import logging
import asyncio
import sqlite3
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

import database
import keyboards
import games

TOKEN = "8904222239:AAF4utz7NX3WOiD5CEVUYozig49Ldcv4mu8"
ADMIN_ID = 2131137264

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Тимчасові структури для анонімного чату та побачень
WAITING_ROOM = []
ACTIVE_CHATS = {}
SPEED_QUEUE = {"male": [], "female": []}
SPEED_MATCHES = {}

class Registration(StatesGroup):
    name = State()
    age = State()
    gender = State()
    location = State()
    photo = State()
    bio = State()

class AdState(StatesGroup):
    text = State()

class ReportState(StatesGroup):
    target_id = State()
    reason = State()

# Ініціалізація бази при старті
database.init_db()

def get_db():
    return sqlite3.connect(database.DB_NAME)

@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    conn = get_db()
    user = conn.execute("SELECT name FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    
    if user:
        await message.answer(f"Привіт, {user[0]}! Вітаємо у Борислав Dating! ⛰", reply_markup=keyboards.get_main_menu())
    else:
        await message.answer("Привіт! Давай створимо твою анкету для знайомств у Бориславі та околицях. Як тебе звати?")
        await state.set_state(Registration.name)

@dp.message(Registration.name)
async def reg_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Скільки тобі років?")
    await state.set_state(Registration.age)

@dp.message(Registration.age)
async def reg_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Будь ласка, введи вік цифрами:")
    await state.update_data(age=int(message.text))
    await message.answer("Обери свою стать:", reply_markup=keyboards.get_gender_keyboard())
    await state.set_state(Registration.gender)

@dp.message(Registration.gender)
async def reg_gender(message: types.Message, state: FSMContext):
    gender = "male" if "Хлопець" in message.text else "female"
    await state.update_data(gender=gender)
    await message.answer("Звідки ти? Обери локацію:", reply_markup=keyboards.get_location_keyboard())
    await state.set_state(Registration.location)

@dp.message(Registration.location)
async def reg_location(message: types.Message, state: FSMContext):
    await state.update_data(location=message.text)
    await message.answer("Розкажи трохи про себе (кого шукаєш, чим займаєшся):")
    await state.set_state(Registration.bio)

@dp.message(Registration.bio)
async def reg_bio(message: types.Message, state: FSMContext):
    await state.update_data(bio=message.text)
    await message.answer("Тепер надішли своє фото для анкети:")
    await state.set_state(Registration.photo)

@dp.message(Registration.photo, F.photo)
async def reg_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO users (user_id, username, name, age, gender, location, bio, photo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (message.from_user.id, message.from_user.username, data['name'], data['age'], data['gender'], data['location'], data['bio'], photo_id)
    )
    conn.commit()
    conn.close()
    
    await message.answer("🎉 Анкету успішно створено! Ласкаво просимо до спільноти Борислава.", reply_markup=keyboards.get_main_menu())
    await state.clear()

# --- АНОНІМНА РУЛЕТКА ---
@dp.message(F.text == "🎲 Анонімна рулетка")
async def start_roulette(message: types.Message):
    user_id = message.from_user.id
    if user_id in ACTIVE_CHATS:
        return await message.answer("Ти вже в чаті!")
    
    if WAITING_ROOM:
        partner_id = WAITING_ROOM.pop(0)
        ACTIVE_CHATS[user_id] = partner_id
        ACTIVE_CHATS[partner_id] = user_id
        
        await bot.send_message(user_id, "🎉 Співрозмовника знайдено! Спілкуйтеся анонімно. Для розігріву є міні-ігри.", reply_markup=keyboards.get_roulette_keyboard())
        await bot.send_message(partner_id, "🎉 Співрозмовника знайдено! Спілкуйтеся анонімно. Для розігріву є міні-ігри.", reply_markup=keyboards.get_roulette_keyboard())
    else:
        WAITING_ROOM.append(user_id)
        await message.answer("🔍 Шукаю когось з Борислава або околиць... Зачекай хвилинку.", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Вийти з чату")]], resize_keyboard=True))

@dp.message(F.text == "✨ Розігрів (Міні-гра)")
async def mini_game_start(message: types.Message):
    user_id = message.from_user.id
    if user_id in ACTIVE_CHATS:
        await message.answer("Обери гру для вас обох:", reply_markup=keyboards.get_games_choice_keyboard())

@dp.callback_query(F.data.startswith("game_select_"))
async def play_game(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ACTIVE_CHATS:
        return await callback.answer("Ви не в чаті.")
    
    partner_id = ACTIVE_CHATS[user_id]
    game_type = callback.data.split("_")[2]
    
    if game_type == "truth":
        q = games.get_random_truth_or_dare("truth")
        msg = f"🎲 **МІНІ-ГРА: Правда чи Дія**\n\nПитання для вас: _{q}_"
    else:
        opt1, opt2 = games.get_random_rather()
        msg = f"🤔 **МІНІ-ГРА: Що б ти обрав?**\n\n1️⃣ {opt1}\n   або\n2️⃣ {opt2}"
        
    await bot.send_message(user_id, msg, parse_mode="Markdown")
    await bot.send_message(partner_id, msg, parse_mode="Markdown")
    await callback.answer()

@dp.message(F.text == "🛑 Вийти з чату")
async def exit_chat(message: types.Message):
    user_id = message.from_user.id
    if user_id in WAITING_ROOM:
        WAITING_ROOM.remove(user_id)
        await message.answer("Пошук скасовано.", reply_markup=keyboards.get_main_menu())
    elif user_id in ACTIVE_CHATS:
        p_id = ACTIVE_CHATS.pop(user_id)
        ACTIVE_CHATS.pop(p_id, None)
        await bot.send_message(user_id, "Діалог завершено.", reply_markup=keyboards.get_main_menu())
        await bot.send_message(p_id, "Співрозмовник вийшов з чату.", reply_markup=keyboards.get_main_menu())

# --- ПЕРЕСИЛАННЯ ПОВІДОМЛЕНЬ В РУЛЕТЦІ ---
@dp.message(lambda msg: msg.from_user.id in ACTIVE_CHATS and not msg.text.startswith("/"))
async def chat_echo(message: types.Message):
    p_id = ACTIVE_CHATS[message.from_user.id]
    try:
        await bot.send_message(p_id, f"👤: {message.text}")
    except:
        pass

# --- ІДЕЯ ДЛЯ ПОБАЧЕННЯ ---
@dp.message(F.text == "🎫 Ідея для побачення")
async def date_idea_cmd(message: types.Message):
    idea = games.get_random_date_idea()
    await message.answer(f"💡 **Ідея для побачення в Бориславі:**\n\n{idea}", parse_mode="Markdown")

# --- ЛОКАЛЬНА СТРІЧКА ОГОЛОШЕНЬ ---
@dp.message(F.text == "📢 Стрічка оголошень")
async def ads_menu(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Переглянути стрічку 📋", callback_data="ads_view")],
        [InlineKeyboardButton(text="Опублікувати оголошення ✍️", callback_data="ads_create")]
    ])
    await message.answer("📰 **Локальна стрічка Борислава**\nТут люди шукають компанію на каву або попутників.", reply_markup=kb)

@dp.callback_query(F.data == "ads_view")
async def view_ads(callback: types.CallbackQuery):
    conn = get_db()
    # Показуємо останні 5 оголошень за останні 24 години
    now = time.time()
    day_ago = now - 86400
    all_ads = conn.execute("SELECT ads.text, users.name FROM ads JOIN users ON ads.user_id = users.user_id WHERE ads.created_at > ? ORDER BY ads.id DESC LIMIT 5", (day_ago,)).fetchall()
    conn.close()
    
    if not all_ads:
        return await callback.message.answer("Стрічка поки порожня. Будь першим, хто напише!")
        
    text = "📢 **Останні оголошення в місті:**\n\n"
    for ad, name in all_ads:
        text += f"👤 **{name}**: {ad}\n———————\n"
    await callback.message.answer(text)
    await callback.answer()

@dp.callback_query(F.data == "ads_create")
async def create_ad_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напиши текст свого оголошення (наприклад: 'Хто хоче на каву в центр о 19:00?'):")
    await state.set_state(AdState.text)
    await callback.answer()

@dp.message(AdState.text)
async def create_ad_finish(message: types.Message, state: FSMContext):
    conn = get_db()
    conn.execute("INSERT INTO ads (user_id, text, created_at) VALUES (?, ?, ?)", (message.from_user.id, message.text, time.time()))
    conn.commit()
    conn.close()
    await message.answer("✅ Оголошення додано в стрічку міста на 24 години!")
    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
