import logging
import asyncio
import os
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import asyncpg

TOKEN = "8904222239:AAF4utz7NX3WOiD5CEVUYozig49Ldcv4mu8"
ADMIN_ID = 2131137264
DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

WAITING_ROOM = []
ACTIVE_CHATS = {}

class Registration(StatesGroup):
    name = State()
    age = State()
    gender = State()
    location = State()
    photo = State()
    bio = State()

class AdState(StatesGroup):
    text = State()

class VerifyState(StatesGroup):
    photo = State()

# --- ПІДКЛЮЧЕННЯ ТА ІНІЦІАЛІЗАЦІЯ БАЗИ ---
async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username TEXT,
        name TEXT,
        age INT,
        gender TEXT,
        location TEXT,
        bio TEXT,
        photo TEXT,
        is_verified INT DEFAULT 0,
        is_banned INT DEFAULT 0
    )""")
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS ads (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        text TEXT,
        created_at DOUBLE PRECISION
    )""")
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS actions (
        id SERIAL PRIMARY KEY,
        from_id BIGINT,
        to_id BIGINT,
        action TEXT,
        UNIQUE(from_id, to_id)
    )""")
    await conn.close()

# --- КЛАВІАТУРИ ---
def get_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="❤️ Дивитись анкети"), KeyboardButton(text="🎲 Анонімна рулетка")],
        [KeyboardButton(text="📢 Стрічка оголошень"), KeyboardButton(text="⚡ Побачення наосліп")],
        [KeyboardButton(text="🎫 Ідея для побачення"), KeyboardButton(text="🏆 ТОП-5 Борислава")],
        [KeyboardButton(text="👤 Моя анкета"), KeyboardButton(text="☑️ Пройти верифікацію")]
    ], resize_keyboard=True)

def get_profile_action_keyboard(target_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{target_id}"),
         InlineKeyboardButton(text="👎 Дизлайк", callback_data=f"dislike_{target_id}")],
        [InlineKeyboardButton(text="⚠️ Поскаржитись", callback_data=f"report_{target_id}")]
    ])

# --- СТАРТ ТА РЕЄСТРАЦІЯ ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    conn = await asyncpg.connect(DATABASE_URL)
    user = await conn.fetchrow("SELECT name, is_banned FROM users WHERE user_id = $1", user_id)
    await conn.close()
    
    if user:
        if user['is_banned'] == 1:
            return await message.answer("❌ Твій профіль заблоковано за порушення правил.")
        await message.answer(f"Привіт, {user['name']}! Раді бачити тебе знову. 😉", reply_markup=get_main_menu())
    else:
        await message.answer("Привіт! Давай створимо твою анкету для знайомств у Бориславі. Як тебе звати?")
        await state.set_state(Registration.name)

@dp.message(Registration.name)
async def reg_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Скільки тобі років?")
    await state.set_state(Registration.age)

@dp.message(Registration.age)
async def reg_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введи вік цифрами:")
    await state.update_data(age=int(message.text))
    await message.answer("Обери стать:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Хлопець 👦"), KeyboardButton(text="Дівчина 👧")]], resize_keyboard=True))
    await state.set_state(Registration.gender)

@dp.message(Registration.gender)
async def reg_gender(message: types.Message, state: FSMContext):
    gender = "male" if "Хлопець" in message.text else "female"
    await state.update_data(gender=gender)
    await message.answer("Введи свій район або місто (Борислав, Східниця, Трускавець, Дрогобич):", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Центр"), KeyboardButton(text="Баня")]], resize_keyboard=True))
    await state.set_state(Registration.location)

@dp.message(Registration.location)
async def reg_location(message: types.Message, state: FSMContext):
    await state.update_data(location=message.text)
    await message.answer("Розкажи про себе (твої хобі, кого шукаєш):")
    await state.set_state(Registration.bio)

@dp.message(Registration.bio)
async def reg_bio(message: types.Message, state: FSMContext):
    await state.update_data(bio=message.text)
    await message.answer("Надішли ОДНЕ фото для анкети:")
    await state.set_state(Registration.photo)

@dp.message(Registration.photo, F.photo)
async def reg_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        INSERT INTO users (user_id, username, name, age, gender, location, bio, photo, is_verified, is_banned) 
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 0, 0)
        ON CONFLICT (user_id) DO UPDATE SET username=$2, name=$3, age=$4, gender=$5, location=$6, bio=$7, photo=$8
    """, message.from_user.id, message.from_user.username, data['name'], data['age'], data['gender'], data['location'], data['bio'], photo_id)
    await conn.close()
    
    await message.answer("🎉 Анкета успішно збережена!", reply_markup=get_main_menu())
    await state.clear()

# --- МОЯ АНКЕТА ---
@dp.message(F.text == "👤 Моя анкета")
async def my_profile(message: types.Message):
    user_id = message.from_user.id
    conn = await asyncpg.connect(DATABASE_URL)
    user = await conn.fetchrow("SELECT name, age, location, bio, photo, is_verified FROM users WHERE user_id = $1", user_id)
    await conn.close()
    
    if user:
        badge = " ☑️ (Верифікований)" if user['is_verified'] else ""
        caption = f"👤 **Твоя анкета{badge}:**\n\n🏷 {user['name']}, {user['age']}\n📍 {user['location']}\n📝 {user['bio']}"
        await bot.send_photo(user_id, photo=user['photo'], caption=caption, parse_mode="Markdown")
    else:
        await message.answer("Спочатку зареєструйся: /start")

# --- ГОРТАННЯ АНКЕТ (❤️ ЛАЙК / 👎 ДИЗЛАЙК) ---
@dp.message(F.text == "❤️ Дивитись анкети")
async def view_profiles(message: types.Message):
    user_id = message.from_user.id
    conn = await asyncpg.connect(DATABASE_URL)
    target = await conn.fetchrow("""
        SELECT user_id, name, age, location, bio, photo, is_verified FROM users 
        WHERE user_id != $1 AND is_banned = 0 AND user_id NOT IN (SELECT to_id FROM actions WHERE from_id = $1) 
        ORDER BY RANDOM() LIMIT 1
    """, user_id)
    await conn.close()
    
    if not target:
        return await message.answer("🌍 Ти переглянув усі доступні анкети! Запроси друзів.")
        
    badge = " ☑️" if target['is_verified'] else ""
    caption = f"🔥 **Знайдено анкету!**\n\n🏷 {target['name']}, {target['age']}{badge}\n📍 {target['location']}\n📝 {target['bio']}"
    await bot.send_photo(user_id, photo=target['photo'], caption=caption, reply_markup=get_profile_action_keyboard(target['user_id']), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("like_") | F.data.startswith("dislike_"))
async def handle_vote(callback: types.CallbackQuery):
    action, target_id = callback.data.split("_")
    target_id = int(target_id)
    user_id = callback.from_user.id
    
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("INSERT INTO actions (from_id, to_id, action) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING", user_id, target_id, action)
    except:
        pass
        
    if action == "like":
        match = await conn.fetchrow("SELECT id FROM actions WHERE from_id = $1 AND to_id = $2 AND action = 'like'", target_id, user_id)
        if match:
            u_user = await conn.fetchrow("SELECT username, name FROM users WHERE user_id = $1", user_id)
            t_user = await conn.fetchrow("SELECT username, name FROM users WHERE user_id = $1", target_id)
            
            link_u = f"@{u_user['username']}" if u_user['username'] else f"[Посилання](tg://user?id={user_id})"
            link_t = f"@{t_user['username']}" if t_user['username'] else f"[Посилання](tg://user?id={target_id})"
            
            await bot.send_message(user_id, f"💖 **Взаємна симпатія з {t_user['name']}!**\nПочинайте спілкування: {link_t}", parse_mode="Markdown")
            await bot.send_message(target_id, f"💖 **Взаємна симпатія з {u_user['name']}!**\nПочинайте спілкування: {link_u}", parse_mode="Markdown")

    # Автоматично підтягуємо наступну анкету
    next_t = await conn.fetchrow("""
        SELECT user_id, name, age, location, bio, photo, is_verified FROM users 
        WHERE user_id != $1 AND is_banned = 0 AND user_id NOT IN (SELECT to_id FROM actions WHERE from_id = $1) 
        ORDER BY RANDOM() LIMIT 1
    """, user_id)
    await conn.close()
    
    try:
        await callback.message.delete()
    except:
        pass

    if next_t:
        badge = " ☑️" if next_t['is_verified'] else ""
        caption = f"🔥 **Наступна анкета!**\n\n🏷 {next_t['name']}, {next_t['age']}{badge}\n📍 {next_t['location']}\n📝 {next_t['bio']}"
        await bot.send_photo(user_id, photo=next_t['photo'], caption=caption, reply_markup=get_profile_action_keyboard(next_t['user_id']), parse_mode="Markdown")
    else:
        await bot.send_message(user_id, "🌍 Це була остання анкета на сьогодні!")
    await callback.answer()

# --- СКАРГИ ТА АДМІН-ПАНЕЛЬ ---
@dp.callback_query(F.data.startswith("report_"))
async def report_user(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    await callback.message.answer("⚠️ Скарга надіслана модераторам.")
    
    conn = await asyncpg.connect(DATABASE_URL)
    bad_user = await conn.fetchrow("SELECT name, username FROM users WHERE user_id = $1", target_id)
    await conn.close()
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Забанити", callback_data=f"admin_ban_{target_id}"),
         InlineKeyboardButton(text="✅ Ігнорувати", callback_data="admin_clear")]
    ])
    await bot.send_message(ADMIN_ID, f"🚨 **ЖАЛОБА!**\nID: `{target_id}`\nІм'я: {bad_user['name']} (@{bad_user['username']})", reply_markup=admin_kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_ban_"))
async def admin_ban(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[2])
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("UPDATE users SET is_banned = 1 WHERE user_id = $1", target_id)
    await conn.close()
    await callback.message.edit_text(f"🔴 Користувач {target_id} ЗАБАНЕНИЙ.")
    await callback.answer()

@dp.callback_query(F.data == "admin_clear")
async def admin_clear(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()

# --- СТРІЧКА ОГОЛОШЕНЬ ---
@dp.message(F.text == "📢 Стрічка оголошень")
async def ads_menu(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Переглянути стрічку 📋", callback_data="ads_view")],
        [InlineKeyboardButton(text="Опублікувати оголошення ✍️", callback_data="ads_create")]
    ])
    await message.answer("📰 **Локальна стрічка Борислава**", reply_markup=kb)

@dp.callback_query(F.data == "ads_view")
async def view_ads(callback: types.CallbackQuery):
    conn = await asyncpg.connect(DATABASE_URL)
    day_ago = time.time() - 86400
    all_ads = await conn.fetch("""
        SELECT ads.text, users.name FROM ads 
        JOIN users ON ads.user_id = users.user_id 
        WHERE ads.created_at > $1 ORDER BY ads.id DESC LIMIT 5
    """, day_ago)
    await conn.close()
    
    if not all_ads:
        return await callback.message.answer("Стрічка поки порожня.")
        
    text = "📢 **Останні оголошення:**\n\n"
    for row in all_ads:
        text += f"👤 **{row['name']}**: {row['text']}\n———————\n"
    await callback.message.answer(text)
    await callback.answer()

@dp.callback_query(F.data == "ads_create")
async def create_ad_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напиши текст свого оголошення:")
    await state.set_state(AdState.text)
    await callback.answer()

@dp.message(AdState.text)
async def create_ad_finish(message: types.Message, state: FSMContext):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("INSERT INTO ads (user_id, text, created_at) VALUES ($1, $2, $3)", message.from_user.id, message.text, time.time())
    await conn.close()
    await message.answer("✅ Додано на 24 години!")
    await state.clear()

# --- ВЕРИФІКАЦІЯ СЕЛФІ ---
@dp.message(F.text == "☑️ Пройти верифікацію")
async def verify_start(message: types.Message, state: FSMContext):
    await message.answer("📸 Надішли своє селфі для верифікації профілю:")
    await state.set_state(VerifyState.photo)

@dp.message(VerifyState.photo, F.photo)
async def verify_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await message.answer("⏳ Фото надіслано адміну на перевірку!")
    await state.clear()
    
    admin_verify_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"averify_yes_{message.from_user.id}"),
         InlineKeyboardButton(text="❌ Відхилити", callback_data="admin_clear")]
    ])
    await bot.send_photo(ADMIN_ID, photo=photo_id, caption=f"👤 Запит верифікації від ID: `{message.from_user.id}`", reply_markup=admin_verify_kb)

@dp.callback_query(F.data.startswith("averify_yes_"))
async def admin_verify_yes(callback: types.CallbackQuery):
    t_id = int(callback.data.split("_")[2])
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("UPDATE users SET is_verified = 1 WHERE user_id = $1", t_id)
    await conn.close()
    await callback.message.reply(f"🟢 Користувач {t_id} верифікований.")
    try:
        await bot.send_message(t_id, "🎉 Твій профіль верифіковано! Тобі присвоєно галочку ☑️!")
    except:
        pass
    await callback.answer()

# --- АНОНІМНА РУЛЕТКА ---
@dp.message(F.text == "🎲 Анонімна рулетка")
async def start_roulette(message: types.Message):
    user_id = message.from_user.id
    if user_id in ACTIVE_CHATS: return
    if WAITING_ROOM:
        p_id = WAITING_ROOM.pop(0)
        ACTIVE_CHATS[user_id] = p_id
        ACTIVE_CHATS[p_id] = user_id
        await bot.send_message(user_id, "🎉 Знайдено співрозмовника!", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Вийти з чату")]], resize_keyboard=True))
        await bot.send_message(p_id, "🎉 Знайдено співрозмовника!", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Вийти з чату")]], resize_keyboard=True))
    else:
        WAITING_ROOM.append(user_id)
        await message.answer("🔍 Шукаю когось...", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Вийти з чату")]], resize_keyboard=True))

@dp.message(F.text == "🛑 Вийти з чату")
async def exit_chat(message: types.Message):
    user_id = message.from_user.id
    if user_id in WAITING_ROOM: WAITING_ROOM.remove(user_id)
    elif user_id in ACTIVE_CHATS:
        p_id = ACTIVE_CHATS.pop(user_id)
        ACTIVE_CHATS.pop(p_id, None)
        try:
            await bot.send_message(p_id, "Співрозмовник вийшов.", reply_markup=get_main_menu())
        except: pass
    await message.answer("Діалог завершено.", reply_markup=get_main_menu())

@dp.message(lambda m: m.from_user.id in ACTIVE_CHATS and not m.text.startswith("/"))
async def echo_chat(message: types.Message):
    try:
        await bot.send_message(ACTIVE_CHATS[message.from_user.id], f"👤: {message.text}")
    except: pass

@dp.message(F.text == "🎫 Ідея для побачення")
async def date_idea_cmd(message: types.Message):
    import games
    await message.answer(f"💡 **Ідея для побачення в Бориславі:**\n\n{games.get_random_date_idea()}", parse_mode="Markdown")

@dp.message(F.text == "🏆 ТОП-5 Борислава")
async def top_profiles(message: types.Message):
    await message.answer("🏆 **ТОП-5 активних анкет міста:**\n\nЗбираємо статистику лайків!")

@dp.message(F.text == "⚡ Побачення наосліп")
async def speed_date(message: types.Message):
    await message.answer("⚡ **Побачення наосліп**\nРежим запускається щоп'ятниці о 20:00!")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
