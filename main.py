import logging
import asyncio
import random
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

TOKEN = "8904222239:AAF4utz7NX3WOiD5CEVUYozig49Ldcv4mu8"
ADMIN_ID = 2131137264
DB_PATH = "boryslav_dating.db"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

ROULETTE_QUEUE = []
ACTIVE_CHATS = {}

# Атмосферні ідеї під Борислав
BORYSLAV_IDEAS = [
    "☕️ **Бориславський романтик:** Прогуляйтеся оновленим міським парком, візьміть гарячий шоколад або ароматну каву в кав'ярні поруч, а потім влаштуйте вечірню прогулянку затишними вуличками до центру.",
    "🍕 **Вечір смаку:** Замовте гарячу піцу в локальному закладі (наприклад, у 'Каменярі' чи іншій улюбленій піцерії), знайдіть гарне місце з краєвидом на місто та обговоріть плани на літо.",
    "🌲 **Краєвиди Борислава:** Влаштуйте міні-пікнік на Крутій Горі або ближче до лісової зони. Свіже повітря, термокружки з чаєм та повна відсутність міського шуму.",
    "🎯 **Активний вихідний:** Домовтеся про спільну поїздку на велосипедах або влаштуйте квест-прогулянку місцями Борислава, про які ви обоє давно забули або де ніколи не були вдвох.",
    "🍿 **Домашній кінотеатр:** Якщо погода не для прогулянок, влаштуйте затишний вечір: замовте суші або піцу, виберіть круту комедію чи детектив і просто відпочиньте від усього світу."
]

# Стани FSM
class Registration(StatesGroup):
    name = State()
    age = State()
    gender = State()
    location = State()
    bio = State()
    photo = State()

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_ban = State()
    waiting_for_unban = State()
    waiting_for_search = State()

# Ініціалізація бази даних
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
                is_banned INTEGER DEFAULT 0, 
                is_active INTEGER DEFAULT 1, 
                in_top INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                user_id INTEGER, 
                name TEXT, 
                text TEXT
            )
        """)
        await db.commit()

# Клавіатури
def get_main_menu(user_id):
    kb = [
        [KeyboardButton(text="❤️ Дивитись анкети"), KeyboardButton(text="🎲 Анонімна рулетка")],
        [KeyboardButton(text="📢 Стрічка оголошень"), KeyboardButton(text="🏆 ТОП-5 Борислава")],
        [KeyboardButton(text="🎫 Ідея для побачення"), KeyboardButton(text="👤 Мій Профіль")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="🛠 Адмін-панель")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_roulette_menu():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🚪 Вийти з рулетки")]], resize_keyboard=True)

def get_admin_menu():
    kb = [
        [KeyboardButton(text="📢 Зробити розсилку"), KeyboardButton(text="📊 Статистика бота")],
        [KeyboardButton(text="🚫 Забанити за ID"), KeyboardButton(text="🟢 Розбанити за ID")],
        [KeyboardButton(text="🔍 Знайти анкету за ID"), KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- АДМІН-ПАНЕЛЬ ---
@dp.message(F.text == "🛠 Адмін-панель")
async def admin_btn(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    await message.answer("🛠 **Панель адміністратора активована!**", reply_markup=get_admin_menu())

@dp.message(F.text == "🔙 Назад")
async def back_btn(message: types.Message):
    await message.answer("Повертаюсь у головне меню.", reply_markup=get_main_menu(message.from_user.id))

@dp.message(F.text == "📊 Статистика бота")
async def admin_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c1: total = (await c1.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_active = 1") as c2: active = (await c2.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1") as c3: banned = (await c3.fetchone())[0]
    stats_text = f"📊 **СТАТИСТИКА БОТА**\n\n👥 Всього людей: {total}\n🟢 Активні: {active}\n🔴 Забанені: {banned}"
    await message.answer(stats_text)

@dp.message(F.text == "📢 Зробити розсилку")
async def broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("✍️ Надішли текст розсилки:")
    await state.set_state(AdminStates.waiting_for_broadcast)

@dp.message(AdminStates.waiting_for_broadcast)
async def broadcast_finish(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    text = message.text
    await state.clear()
    await message.answer("🚀 Розсилка запущена...")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor: rows = await cursor.fetchall()
    success, failed = 0, 0
    for row in rows:
        try:
            await bot.send_message(row[0], f"📢 **ПОВІДОМЛЕННЯ ВІД АДМІНІСТРАЦІЇ:**\n\n{text}")
            success += 1
            await asyncio.sleep(0.05)
        except: failed += 1
    await message.answer(f"✅ Готово!\n🟢 Доставлено: {success}\n🔴 Заблокували: {failed}", reply_markup=get_admin_menu())

@dp.message(F.text == "🚫 Забанити за ID")
async def ban_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("🔢 Введи Telegram ID для бану:")
    await state.set_state(AdminStates.waiting_for_ban)

@dp.message(AdminStates.waiting_for_ban)
async def ban_finish(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID or not message.text.isdigit(): return
    target = int(message.text)
    await state.clear()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned=1, is_active=0 WHERE user_id=?", (target,))
        await db.commit()
    await message.answer(f"🔴 Користувача {target} забанено!", reply_markup=get_admin_menu())
    try: await bot.send_message(target, "❌ Твій профіль заблоковано адміністрацією.")
    except: pass

@dp.message(F.text == "🟢 Розбанити за ID")
async def unban_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("🔢 Введи Telegram ID для розбану:")
    await state.set_state(AdminStates.waiting_for_unban)

@dp.message(AdminStates.waiting_for_unban)
async def unban_finish(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID or not message.text.isdigit(): return
    target = int(message.text)
    await state.clear()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned=0, is_active=1 WHERE user_id=?", (target,))
        await db.commit()
    await message.answer(f"🟢 Користувача {target} розбанено!", reply_markup=get_admin_menu())

@dp.message(F.text == "🔍 Знайти анкету за ID")
async def search_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("🔢 Введи Telegram ID для пошуку:")
    await state.set_state(AdminStates.waiting_for_search)

@dp.message(AdminStates.waiting_for_search)
async def search_finish(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID or not message.text.isdigit(): return
    target = int(message.text)
    await state.clear()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (target,)) as c: user = await c.fetchone()
    if not user: return await message.answer("❌ Анкету не знайдено.", reply_markup=get_admin_menu())
    b_status = "🔴 В БАНІ" if user['is_banned'] else "🟢 Активний"
    caption = f"🔍 Знайдено:\n👤 {user['name']}, {user['age']} р.\n📍 {user['location']}\n🔗 @{user['username']}\n💬 {user['bio']}\nСтатус: {b_status}"
    await bot.send_photo(ADMIN_ID, photo=user['photo'], caption=caption, reply_markup=get_admin_menu())

# --- АНОНІМНА РУЛЕТКА ---
@dp.message(F.text == "🎲 Анонімна рулетка")
async def roulette_start(message: types.Message):
    uid = message.from_user.id
    if uid in ACTIVE_CHATS or uid in ROULETTE_QUEUE:
        return await message.answer("Ти вже шукаєш або спілкуєшся!")
        
    ROULETTE_QUEUE.append(uid)
    if len(ROULETTE_QUEUE) >= 2:
        p1 = ROULETTE_QUEUE.pop(0)
        p2 = ROULETTE_QUEUE.pop(0)
        ACTIVE_CHATS[p1] = p2
        ACTIVE_CHATS[p2] = p1
        await bot.send_message(p1, "🎉 **Співрозмовника знайдено!** Спілкуйтеся прямо тут.", reply_markup=get_roulette_menu())
        await bot.send_message(p2, "🎉 **Співрозмовника знайдено!** Спілкуйтеся прямо тут.", reply_markup=get_roulette_menu())
    else:
        await message.answer("🔍 Пошук анонімного співрозмовника...", reply_markup=get_roulette_menu())

@dp.message(F.text == "🚪 Вийти з рулетки")
async def roulette_exit(message: types.Message):
    uid = message.from_user.id
    if uid in ROULETTE_QUEUE:
        ROULETTE_QUEUE.remove(uid)
        await message.answer("Пошук скасовано.", reply_markup=get_main_menu(uid))
    elif uid in ACTIVE_CHATS:
        partner = ACTIVE_CHATS.pop(uid)
        ACTIVE_CHATS.pop(partner, None)
        await message.answer("Ти вийшов з чату.", reply_markup=get_main_menu(uid))
        try: await bot.send_message(partner, "🚫 Співрозмовник завершив діалог.", reply_markup=get_main_menu(partner))
        except: pass

@dp.message(lambda msg: msg.from_user.id in ACTIVE_CHATS and not msg.text.startswith("🚪"))
async def roulette_forward(message: types.Message):
    partner = ACTIVE_CHATS[message.from_user.id]
    try:
        if message.text: await bot.send_message(partner, f"💬: {message.text}")
        elif message.photo: await bot.send_photo(partner, photo=message.photo[-1].file_id, caption="📸 Фото")
    except: pass

# --- ❤️ ДИВИТИСЬ АНКЕТИ (ПОВНОЦІННА ЛОГІКА) ---
@dp.message(F.text == "❤️ Дивитись анкети")
async def view_profiles(message: types.Message):
    uid = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id != ? AND is_banned = 0 AND is_active = 1 ORDER BY RANDOM() LIMIT 1", (uid,)) as c:
            user = await c.fetchone()
    if not user:
        return await message.answer("😔 Поки що немає інших активних анкет у базі.")
    
    caption = f"👤 **{user['name']}**, {user['age']} років\n📍 район {user['location']}\n\n💬 {user['bio']}"
    if user['username']:
        caption += f"\n\n🔗 Написати: @{user['username']}"
    await bot.send_photo(uid, photo=user['photo'], caption=caption, parse_mode="Markdown")

# --- 🏆 ТОП-5 БОРИСЛАВА (РЕАЛЬНИЙ ФІКСОВАНИЙ ТОП) ---
@dp.message(F.text == "🏆 ТОП-5 Борислава")
async def show_top_five(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Витягуємо 5 реальних анкет, позначених адміністратором як in_top = 1
        async with db.execute("SELECT * FROM users WHERE is_banned = 0 AND in_top = 1 ORDER BY user_id ASC LIMIT 5") as c:
            top_users = await c.fetchall()
            
    if not top_users:
        return await message.answer("🌟 ТОП-5 зараз порожній. Адміністрація ще не призначила топ-користувачів!")
        
    await message.answer("🔥 **🏆 ТОП-5 НАЙКРАЩИХ АНКЕТ БОРИСЛАВА** 🔥")
    for user in top_users:
        caption = f"👑 **{user['name']}**, {user['age']} років\n📍 район {user['location']}\n💬 *«{user['bio']}»*"
        if user['username']:
            caption += f"\n🔗 @{user['username']}"
        try:
            await bot.send_photo(message.from_user.id, photo=user['photo'], caption=caption, parse_mode="Markdown")
            await asyncio.sleep(0.2)
        except: pass

# --- ЛОКАЛЬНІ ФІЧІ БОРИСЛАВА ---
@dp.message(F.text == "🎫 Ідея для побачення")
async def idea_cmd(message: types.Message):
    await message.answer(f"💡 **Ось атмосфера для вашого дня:**\n\n{random.choice(BORYSLAV_IDEAS)}", parse_mode="Markdown")

@dp.message(F.text == "📢 Стрічка оголошень")
async def show_ads(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT name, text FROM ads ORDER BY id DESC LIMIT 5") as cursor: 
            ads = await cursor.fetchall()
            
    if not ads: 
        return await message.answer("Стрічка поки порожня.")
    
    feed = "📰 **ЛОКАЛЬНА СТРІЧКА М. БОРИСЛАВ**\n\n"
    for ad in ads: 
        feed += f"👤 **{ad['name']}**:\n*«{ad['text']}»*\n━━━━━━━━━━━━━━\n"
    await message.answer(feed, parse_mode="Markdown")

# --- РЕЄСТРАЦІЯ ТА ПРОФІЛЬ ---
@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, is_banned FROM users WHERE user_id=?", (message.from_user.id,)) as c: 
            user = await c.fetchone()
            
    if user:
        if user[1] == 1:
            return await message.answer("❌ Твій профіль заблоковано за порушення правил.")
        await message.answer("Привіт! Раді бачити у Boryslav Vibe.", reply_markup=get_main_menu(message.from_user.id))
    else:
        await message.answer("Привіт! Давай створимо тобі крутий профіль. Як тебе звати?")
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
    await state.update_data(gender=message.text)
    await message.answer("Вкажи свій район Борислава (наприклад: Центр, Коваліва, Губичі):")
    await state.set_state(Registration.location)

@dp.message(Registration.location)
async def reg_loc(message: types.Message, state: FSMContext):
    await state.update_data(loc=message.text)
    await message.answer("Розкажи коротко про себе (інтереси, кого шукаєш):")
    await state.set_state(Registration.bio)

@dp.message(Registration.bio)
async def reg_bio(message: types.Message, state: FSMContext):
    await state.update_data(bio=message.text)
    await message.answer("Надішли своє найкраще фото для анкети:")
    await state.set_state(Registration.photo)

@dp.message(Registration.photo, F.photo)
async def reg_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users (user_id, username, name, age, gender, location, bio, photo) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (message.from_user.id, message.from_user.username, data['name'], data['age'], data['gender'], data['loc'], data['bio'], message.photo[-1].file_id))
        await db.commit()
    await message.answer("🔥 Профіль успішно налаштовано!", reply_markup=get_main_menu(message.from_user.id))
    await state.clear()

@dp.message(F.text == "👤 Мій Профіль")
async def my_profile(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (message.from_user.id,)) as c: 
            user = await c.fetchone()
            
    if not user: return
    
    status_text = "⚡️ Верифікований користувач ☑️" if user['is_verified'] else "🔹 Новий аккаунт"
    caption = (
        f"👑 **ТВІЙ ПРОФІЛЬ БОРИСЛАВА**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 **Ім'я:** {user['name']}, {user['age']} років\n"
        f"📍 **Локація:** район {user['location']}\n"
        f"💬 **Про себе:** {user['bio']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"ℹ️ {status_text}"
    )
    await bot.send_photo(message.from_user.id, photo=user['photo'], caption=caption, parse_mode="Markdown", reply_markup=get_main_menu(message.from_user.id))

# --- ЗАПУСК ---
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
