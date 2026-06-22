import logging
import asyncio
import os
import time
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

TOKEN = "8904222239:AAF4utz7NX3WOiD5CEVUYozig49Ldcv4mu8"
ADMIN_ID = 2131137264
DB_PATH = "boryslav_dating.db"

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
    bio = State()
    photo = State()

class AdState(StatesGroup):
    text = State()

class VerifyState(StatesGroup):
    photo = State()

# --- ІНІЦІАЛІЗАЦІЯ БАЗИ ДАНИХ (SQLite) ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            name TEXT,
            age INTEGER,
            gender TEXT,
            location TEXT,
            bio TEXT,
            photo TEXT,
            is_verified INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            created_at REAL
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id INTEGER,
            to_id INTEGER,
            action TEXT,
            UNIQUE(from_id, to_id)
        )""")
        await db.commit()

# --- КЛАВІАТУРИ ---
def get_main_menu():
    kb = [
        [KeyboardButton(text="❤️ Дивитись анкети"), KeyboardButton(text="🎲 Анонімна рулетка")],
        [KeyboardButton(text="📢 Стрічка оголошень"), KeyboardButton(text="⚡ Побачення наосліп")],
        [KeyboardButton(text="🎫 Ідея для побачення"), KeyboardButton(text="🏆 ТОП-5 Борислава")],
        [KeyboardButton(text="👤 Моя анкета"), KeyboardButton(text="☑️ Пройти верифікацію")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_profile_action_keyboard(target_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{target_id}"),
            InlineKeyboardButton(text="👎 Дизлайк", callback_data=f"dislike_{target_id}")
        ],
        [InlineKeyboardButton(text="⚠️ Поскаржитись", callback_data=f"report_{target_id}")]
    ])

# --- СТАРТ ТА РЕЄСТРАЦІЯ ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT name, is_banned FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            
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
    
    kb = [[KeyboardButton(text="Хлопець 👦"), KeyboardButton(text="Дівчина 👧")]]
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)
    await message.answer("Обери стать:", reply_markup=markup)
    await state.set_state(Registration.gender)

@dp.message(Registration.gender)
async def reg_gender(message: types.Message, state: FSMContext):
    gender = "male" if "Хлопець" in message.text else "female"
    await state.update_data(gender=gender)
    
    kb = [[KeyboardButton(text="Центр"), KeyboardButton(text="Баня")]]
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)
    await message.answer("Введи свій район або місто (Борислав, Східниця, Трускавець, Дрогобич):", reply_markup=markup)
    await state.set_state(Registration.location)

@dp.message(Registration.location)
async def reg_location(message: types.Message, state: FSMContext):
    await state.update_data(location=message.text)
    await message.answer("Розкажи про себе (твої хобі, кого шукаєш):")
    await state.set_state(Registration.bio)

@dp.message(Registration.bio)
async def reg_bio(message: types.Message, state: FSMContext):
    await state.update_data(bio=message.text)
    await message.answer("Надішли ОДНЕ фото для анкетної картки:")
    await state.set_state(Registration.photo)

@dp.message(Registration.photo, F.photo)
async def reg_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users (user_id, username, name, age, gender, location, bio, photo, is_verified, is_banned) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
        """, (message.from_user.id, message.from_user.username, data['name'], data['age'], data['gender'], data['location'], data['bio'], photo_id))
        await db.commit()
    
    await message.answer("🎉 Анкета успішно збережена!", reply_markup=get_main_menu())
    await state.clear()

# --- МОЯ АНКЕТА ---
@dp.message(F.text.in_({"👤 Моя анкету", "👤 Моя анкета"}))
async def my_profile(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT name, age, location, bio, photo, is_verified FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
    
    if user:
        badge = " ☑️ (Верифікований)" if user['is_verified'] else ""
        caption = f"👤 **Твоя анкета{badge}:**\n\n🏷 {user['name']}, {user['age']}\n📍 {user['location']}\n📝 {user['bio']}"
        await bot.send_photo(user_id, photo=user['photo'], caption=caption, parse_mode="Markdown")
    else:
        await message.answer("Спочатку зареєструйся: /start")

# --- ГОРТАННЯ АНКЕТ ---
@dp.message(F.text == "❤️ Дивитись анкети")
async def view_profiles(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT user_id, name, age, location, bio, photo, is_verified FROM users 
            WHERE user_id != ? AND is_banned = 0 AND user_id NOT IN (SELECT to_id FROM actions WHERE from_id = ?) 
            ORDER BY RANDOM() LIMIT 1
        """, (user_id, user_id)) as cursor:
            target = await cursor.fetchone()
    
    if not target:
        return await message.answer("🌍 Ти переглянув усі доступні анкети! Заходь пізніше.")
        
    badge = " ☑️" if target['is_verified'] else ""
    caption = f"🔥 **Знайдено анкету!**\n\n🏷 {target['name']}, {target['age']}{badge}\n📍 {target['location']}\n📝 {target['bio']}"
    await bot.send_photo(user_id, photo=target['photo'], caption=caption, reply_markup=get_profile_action_keyboard(target['user_id']), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("like_") | F.data.startswith("dislike_"))
async def handle_vote(callback: CallbackQuery):
    action, target_id = callback.data.split("_")
    target_id = int(target_id)
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        try:
            await db.execute("INSERT OR IGNORE INTO actions (from_id, to_id, action) VALUES (?, ?, ?)", (user_id, target_id, action))
            await db.commit()
        except:
            pass
            
        if action == "like":
            async with db.execute("SELECT id FROM actions WHERE from_id = ? AND to_id = ? AND action = 'like'", (target_id, user_id)) as cursor:
                match = await cursor.fetchone()
            if match:
                async with db.execute("SELECT username, name FROM users WHERE user_id = ?", (user_id,)) as c1:
                    u_user = await c1.fetchone()
                async with db.execute("SELECT username, name FROM users WHERE user_id = ?", (target_id,)) as c2:
                    t_user = await c2.fetchone()
                
                link_u = f"@{u_user['username']}" if u_user['username'] else f"[Посилання](tg://user?id={user_id})"
                link_t = f"@{t_user['username']}" if t_user['username'] else f"[Посилання](tg://user?id={target_id})"
                
                await bot.send_message(user_id, f"💖 **Взаємна симпатія з {t_user['name']}!**\nПочинайте спілкування: {link_t}", parse_mode="Markdown")
                await bot.send_message(target_id, f"💖 **Взаємна симпатія з {u_user['name']}!**\nПочинайте спілкування: {link_u}", parse_mode="Markdown")

        async with db.execute("""
            SELECT user_id, name, age, location, bio, photo, is_verified FROM users 
            WHERE user_id != ? AND is_banned = 0 AND user_id NOT IN (SELECT to_id FROM actions WHERE from_id = ?) 
            ORDER BY RANDOM() LIMIT 1
        """, (user_id, user_id)) as cursor:
            next_t = await cursor.fetchone()

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
async def report_user(callback: CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    await callback.message.answer("⚠️ Скарга надіслана модераторам.")
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT name, username FROM users WHERE user_id = ?", (target_id,)) as cursor:
            bad_user = await cursor.fetchone()
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Забанити", callback_data=f"admin_ban_{target_id}"),
            InlineKeyboardButton(text="✅ Ігнорувати", callback_data="admin_clear")
        ]
    ])
    await bot.send_message(ADMIN_ID, f"🚨 **ЖАЛОБА!**\nID: `{target_id}`\nІм'я: {bad_user['name']} (@{bad_user['username']})", reply_markup=admin_kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_ban_"))
async def admin_ban(callback: CallbackQuery):
    target_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
        await db.commit()
    await callback.message.edit_text(f"🔴 Користувач {target_id} ЗАБАНЕНИЙ.")
    await callback.answer()

@dp.callback_query(F.data == "admin_clear")
async def admin_clear(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()

# --- СТРІЧКА ОГОЛОШЕНЬ ---
@dp.message(F.text == "📢 Стрічка оголошень")
async def ads_menu(message: types.Message):
    kb = [[
        InlineKeyboardButton(text="Переглянути стрічку 📋", callback_data="ads_view"),
        InlineKeyboardButton(text="Опублікувати оголошення ✍️", callback_data="ads_create")
    ]]
    await message.answer("📰 **Локальна стрічка Борислава**", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "ads_view")
async def view_ads(callback: CallbackQuery):
    day_ago = time.time() - 86400
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT ads.text, users.name FROM ads 
            JOIN users ON ads.user_id = users.user_id 
            WHERE ads.created_at > ? ORDER BY ads.id DESC LIMIT 5
        """, (day_ago,)) as cursor:
            all_ads = await cursor.fetchall()
    
    if not all_ads:
        return await callback.message.answer("Стрічка поки порожня.")
        
    text = "📢 **Останні оголошення:**\n\n"
    for row in all_ads:
        text += f"👤 **{row['name']}**: {row['text']}\n———————\n"
    await callback.message.answer(text)
    await callback.answer()

@dp.callback_query(F.data == "ads_create")
async def create_ad_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Напиши текст свого оголошення:")
    await state.set_state(AdState.text)
    await callback.answer()

@dp.message(AdState.text)
async def create_ad_finish(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO ads (user_id, text, created_at) VALUES (?, ?, ?)", (message.from_user.id, message.text, time.time()))
        await db.commit()
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
        [
            InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"averify_yes_{message.from_user.id}"),
            InlineKeyboardButton(text="❌ Відхилити", callback_data="admin_clear")
        ]
    ])
    await bot.send_photo(ADMIN_ID, photo=photo_id, caption=f"👤 Запит верифікації від ID: `{message.from_user.id}`", reply_markup=admin_verify_kb)

@dp.callback_query(F.data.startswith("averify_yes_"))
async def admin_verify_yes(callback: CallbackQuery):
    t_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_verified = 1 WHERE user_id = ?", (t_id,))
        await db.commit()
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
        
        kb = [[KeyboardButton(text="🛑 Вийти з чату")]]
        markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        await bot.send_message(user_id, "🎉 Знайдено співрозмовника!", reply_markup=markup)
        await bot.send_message(p_id, "🎉 Знайдено співрозмовника!", reply_markup=markup)
    else:
        WAITING_ROOM.append(user_id)
        kb = [[KeyboardButton(text="🛑 Вийти з чату")]]
        markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        await message.answer("🔍 Шукаю когось...", reply_markup=markup)

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
    # Прямо вставляємо ідею без додаткових файлів
    idea = "Затишне побачення: Прогуляйтеся міським парком у Бориславі, зайдіть на каву в центр та влаштуйте змагання на найкумеднішу історію з дитинства. ☕"
    await message.answer(f"💡 **Ідея для побачення в Бориславі:**\n\n{idea}", parse_mode="Markdown")

@dp.message(F.text == "🏆 ТОП-5 Борислава")
async def top_profiles(message: types.Message):
    await message.answer("🏆 **🏆 ТОП-5 активних анкет міста:**\n\nЗбираємо статистику лайків!")

@dp.message(F.text == "⚡ Побачення наосліп")
async def speed_date(message: types.Message):
    await message.answer("⚡ **Побачення наосліп**\nРежим запускається щоп'ятниці о 20:00!")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
