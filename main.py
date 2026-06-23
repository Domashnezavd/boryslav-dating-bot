import logging
import asyncio
import random
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8904222239:AAF4utz7NX3WOiD5CEVUYozig49Ldcv4mu8"
ADMIN_ID = 2131137264
DB_PATH = "boryslav_dating.db"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Списки для анонімного чату
ROULETTE_QUEUE = []
ACTIVE_CHATS = {}

# Великий масив атмосферних локацій та ідей для Борислава
BORYSLAV_IDEAS = [
    "☕️ **Бориславський романтик:** Прогуляйтеся оновленим міським парком, візьміть гарячий шоколад або ароматну каву в кав'ярні поруч, а потім влаштуйте вечірню прогулянку затишними вуличками до центру.",
    "🍕 **Вечір смаку:** Замовте гарячу піцу в локальному закладі (наприклад, у 'Каменярі' чи іншій улюбленій піцерії), знайдіть гарне місце з краєвидом на місто та обговоріть плани на літо.",
    "🌲 **Краєвиди Борислава:** Влаштуйте міні-пікнік на Крутій Горі або ближче до лісової зони. Свіже повітря, термокружки з чаєм та повна відсутність міського шуму.",
    "🎯 **Активний вихідний:** Домовтеся про спільну поїздку на велосипедах або влаштуйте квест-прогулянку місцями Борислава, про які ви обоє давно забули або де ніколи не були вдвох.",
    "🍿 **Домашній кінотеатр:** Якщо погода не для прогулянок, влаштуйте затишний вечір: замовте суші або піцу, виберіть круту комедію чи детектив і просто відпочиньте від усього світу.",
    "⛲️ **Вечір біля фонтану:** Зустріньтеся біля центрального фонтану, купіть морозиво та просто пройдіться стометрівкою, обговорюючи все на світі без поспіху.",
    "📸 **Фотопрогулянка:** Знайдіть старі автентичні бориславські будиночки чи нафтові вишки в парку, влаштуйте один одному міні-фотосесію на телефон. Буде що згадати!"
]

# --- ВСІ СТАНИ FSM ---
class Registration(StatesGroup):
    name = State()
    age = State()
    gender = State()
    target_gender = State()
    location = State()
    bio = State()
    photo = State()

class EditProfile(StatesGroup):
    waiting_for_field = State()
    waiting_for_value = State()

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_ban = State()
    waiting_for_unban = State()
    waiting_for_search = State()
    waiting_for_verify = State()
    waiting_for_top_add = State()

class AdStates(StatesGroup):
    waiting_for_ad_text = State()

# --- ІНІЦІАЛІЗАЦІЯ БД ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, 
                username TEXT, 
                name TEXT, 
                age INTEGER, 
                gender TEXT, 
                target_gender TEXT,
                location TEXT, 
                bio TEXT, 
                photo TEXT, 
                is_verified INTEGER DEFAULT 0, 
                is_banned INTEGER DEFAULT 0, 
                is_active INTEGER DEFAULT 1, 
                in_top INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                user_id INTEGER, 
                name TEXT, 
                text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id INTEGER,
                target_id INTEGER,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

# --- КЛАВІАТУРИ ---
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
        [KeyboardButton(text="🔍 Знайти анкету за ID"), KeyboardButton(text="⭐️ Додати в ТОП за ID")],
        [KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_sex_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Хлопець 👦"), KeyboardButton(text="Дівчина 👧")]
    ], resize_keyboard=True, one_time_keyboard=True)

def get_target_sex_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Хлопці 👦"), KeyboardButton(text="Дівчата 👧")],
        [KeyboardButton(text="Усі підряд 🔄")]
    ], resize_keyboard=True, one_time_keyboard=True)

# --- ГОЛОВНИЙ СТАРТ І РЕЄСТРАЦІЯ ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_banned, is_active FROM users WHERE user_id=?", (uid,)) as c: 
            user = await c.fetchone()
            
    if user:
        if user[0] == 1:
            return await message.answer("❌ Твій профіль заблоковано адміністрацією за порушення правил спільноти.")
        
        # Якщо був неактивний, повертаємо в пошук
        if user[1] == 0:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE users SET is_active=1 WHERE user_id=?", (uid,))
                await db.commit()
                
        await message.answer("👋 Раді знову бачити тебе у **Boryslav Vibe**! Шукай нові знайомства або публікуй оголошення.", reply_markup=get_main_menu(uid))
    else:
        await message.answer("👋 Привіт! Ласкаво просимо до головного бота знайомств Борислава!\n\nДавай створимо твою анкету. **Як тебе звати?**")
        await state.set_state(Registration.name)

@dp.message(Registration.name)
async def reg_name(message: types.Message, state: FSMContext):
    if len(message.text) > 30:
        return await message.answer("⚠️ Ім'я занадто довге. Введи коротше (до 30 символів):")
    await state.update_data(name=message.text)
    await message.answer("🔢 **Скільки тобі років?**")
    await state.set_state(Registration.age)

@dp.message(Registration.age)
async def reg_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("⚠️ Будь ласка, введи вік цифрами:")
    age = int(message.text)
    if age < 14 or age > 99:
        return await message.answer("⚠️ Введи реальний вік (від 14 до 99 років):")
    await state.update_data(age=age)
    await message.answer("👤 **Вкажи свою стать:**", reply_markup=get_sex_keyboard())
    await state.set_state(Registration.gender)

@dp.message(Registration.gender)
async def reg_gender(message: types.Message, state: FSMContext):
    gender = message.text
    if gender not in ["Хлопець 👦", "Дівчина 👧"]:
        return await message.answer("⚠️ Скористайся кнопками на клавіатурі:")
    await state.update_data(gender=gender)
    await message.answer("🔍 **Хто тебе цікавить?**", reply_markup=get_target_sex_keyboard())
    await state.set_state(Registration.target_gender)

@dp.message(Registration.target_gender)
async def reg_target(message: types.Message, state: FSMContext):
    target = message.text
    if target not in ["Хлопці 👦", "Дівчата 👧", "Усі підряд 🔄"]:
        return await message.answer("⚠️ Скористайся кнопками на клавіатурі:")
    await state.update_data(target_gender=target)
    await message.answer("📍 **Вкажи свій район Борислава** (наприклад: Центр, Коваліва, Губичі, Баня, Мразниця):")
    await state.set_state(Registration.location)

@dp.message(Registration.location)
async def reg_loc(message: types.Message, state: FSMContext):
    if len(message.text) > 40:
        return await message.answer("⚠️ Назва району занадто довга. Напиши лаконічно:")
    await state.update_data(location=message.text)
    await message.answer("📝 **Розкажи коротко про себе** (інтереси, кого шукаєш, чим займаєшся):")
    await state.set_state(Registration.bio)

@dp.message(Registration.bio)
async def reg_bio(message: types.Message, state: FSMContext):
    if len(message.text) > 300:
        return await message.answer("⚠️ Опис занадто великий (максимум 300 символів). Скороти його трішки:")
    await state.update_data(bio=message.text)
    await message.answer("📸 **Надішли своє найкраще фото для анкети:**", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Registration.photo)

@dp.message(Registration.photo, F.photo)
async def reg_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    uid = message.from_user.id
    username = message.from_user.username
    photo_id = message.photo[-1].file_id
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users (user_id, username, name, age, gender, target_gender, location, bio, photo, is_active) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (uid, username, data['name'], data['age'], data['gender'], data['target_gender'], data['location'], data['bio'], photo_id))
        await db.commit()
        
    await state.clear()
    await message.answer("🔥 **Твій профіль успішно створено!** Тепер ти в базі пошуку. Успішних знайомств!", reply_markup=get_main_menu(uid))

# --- 👤 МІЙ ПРОФІЛЬ (ЧИСТИЙ МІНІМАЛІЗМ) ---
@dp.message(F.text == "👤 Мій Профіль")
async def my_profile(message: types.Message):
    uid = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (uid,)) as c: 
            user = await c.fetchone()
            
    if not user: 
        return await message.answer("Анкету не знайдено. Пропиши /start для реєстрації.")
    
    status = "🌟 ТОП-Користувач" if user['in_top'] else "✨ Учасник клубу"
    verified = " ☑️" if user['is_verified'] else ""
    
    caption = (
        f"✨ **{user['name']}, {user['age']} років** {verified}\n"
        f"📍 {user['location']}\n"
        f"🌿 {status}\n\n"
        f"📝 **Про себе:**\n{user['bio']}"
    )
    
    profile_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Редагувати анкету", callback_data="register_again")],
        [InlineKeyboardButton(text="❌ Видалити / Сховати анкету", callback_data="hide_profile")]
    ])
    
    await bot.send_photo(
        chat_id=uid, 
        photo=user['photo'], 
        caption=caption, 
        parse_mode="Markdown", 
        reply_markup=profile_kb
    )

@dp.callback_query(F.data == "register_again")
async def edit_profile_inline(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer("Давай оновимо твою анкету. Як тебе звати?")
    await state.set_state(Registration.name)

@dp.callback_query(F.data == "hide_profile")
async def hide_profile_inline(call: types.CallbackQuery):
    uid = call.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_active=0 WHERE user_id=?", (uid,))
        await db.commit()
    await call.answer("Анкету приховано з пошуку!", show_alert=True)
    await call.message.answer("📴 Твоя анкета більше не бере участі в пошуку. Щоб повернутися — просто пропиши знову /start у чат.")

# --- ❤️ ПОШУК АНКЕТ ---
@dp.message(F.text == "❤️ Дивитись анкети")
async def view_profiles(message: types.Message):
    uid = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Отримуємо преференції користувача
        async with db.execute("SELECT gender, target_gender FROM users WHERE user_id=?", (uid,)) as c:
            me = await c.fetchone()
            
    if not me:
        return await message.answer("Спочатку створи анкету за допомогою /start")
        
    # Формуємо SQL запит під фільтр статей
    query = "SELECT * FROM users WHERE user_id != ? AND is_banned = 0 AND is_active = 1"
    params = [uid]
    
    if me['target_gender'] == "Хлопці 👦":
        query += " AND gender = 'Хлопець 👦'"
    elif me['target_gender'] == "Дівчата 👧":
        query += " AND gender = 'Дівчина 👧'"
        
    query += " ORDER BY RANDOM() LIMIT 1"
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, tuple(params)) as c:
            user = await c.fetchone()
            
    if not user:
        return await message.answer("😔 За твоїми фільтрами поки немає нових анкет. Спробуй пізніше або зміни стать в налаштуваннях профілю!")
    
    caption = f"👤 **{user['name']}**, {user['age']} років\n📍 район {user['location']}\n\n💬 {user['bio']}"
    
    card_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💌 Написати", url=f"t.me/{user['username']}") if user['username'] else InlineKeyboardButton(text="🔏 Немає юзернейму", callback_data="no_username"),
            InlineKeyboardButton(text="⚠️ Скарга", callback_data=f"report_{user['user_id']}")
        ]
    ])
    
    await bot.send_photo(uid, photo=user['photo'], caption=caption, parse_mode="Markdown", reply_markup=card_kb)

@dp.callback_query(F.data == "no_username")
async def no_username_alert(call: types.CallbackQuery):
    await call.answer("У цього користувача немає публічного @username в Telegram, зв'язатися не вдасться 😔", show_alert=True)

@dp.callback_query(F.data.startswith("report_"))
async def report_user(call: types.CallbackQuery):
    target_id = int(call.data.split("_")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO reports (reporter_id, target_id, reason) VALUES (?, ?, ?)", (call.from_user.id, target_id, "Скарга з анкети"))
        await db.commit()
    await call.answer("Скарга надіслана адміну. Дякуємо за пильність!", show_alert=True)
    await bot.send_message(ADMIN_ID, f"⚠️ **СКАРГА!** Користувач ID {call.from_user.id} поскаржився на анкету ID `{target_id}`.")

# --- 🎲 АНОНІМНА РУЛЕТКА (ПОВНА ВЕРСІЯ) ---
@dp.message(F.text == "🎲 Анонімна рулетка")
async def roulette_start(message: types.Message):
    uid = message.from_user.id
    if uid in ACTIVE_CHATS or uid in ROULETTE_QUEUE:
        return await message.answer("Ти вже перебуваєш у черзі або маєш активний діалог!")
        
    ROULETTE_QUEUE.append(uid)
    if len(ROULETTE_QUEUE) >= 2:
        p1 = ROULETTE_QUEUE.pop(0)
        p2 = ROULETTE_QUEUE.pop(0)
        ACTIVE_CHATS[p1] = p2
        ACTIVE_CHATS[p2] = p1
        await bot.send_message(p1, "🎉 **Співрозмовника з Борислава знайдено!** Спілкуйтеся анонімно прямо тут. Текст, фото, стікери підтримуються. Для виходу тисни кнопку нижче.", reply_markup=get_roulette_menu())
        await bot.send_message(p2, "🎉 **Співрозмовника з Борислава знайдено!** Спілкуйтеся анонімно прямо тут. Текст, photo, стікери підтримуються. Для виходу тисни кнопку нижче.", reply_markup=get_roulette_menu())
    else:
        await message.answer("🔍 Шукаю вільну людину для спілкування наосліп... Зачекай трішки.", reply_markup=get_roulette_menu())

@dp.message(F.text == "🚪 Вийти з рулетки")
async def roulette_exit(message: types.Message):
    uid = message.from_user.id
    if uid in ROULETTE_QUEUE:
        ROULETTE_QUEUE.remove(uid)
        await message.answer("Пошук співрозмовника скасовано.", reply_markup=get_main_menu(uid))
    elif uid in ACTIVE_CHATS:
        partner = ACTIVE_CHATS.pop(uid)
        ACTIVE_CHATS.pop(partner, None)
        await message.answer("Ти вийшов з анонімного чату.", reply_markup=get_main_menu(uid))
        try: await bot.send_message(partner, "🚫 Співрозмовник завершив діалог. Можеш запустити пошук знову.", reply_markup=get_main_menu(partner))
        except: pass

@dp.message(lambda msg: msg.from_user.id in ACTIVE_CHATS and not msg.text.startswith("🚪"))
async def roulette_forwarder(message: types.Message):
    partner = ACTIVE_CHATS[message.from_user.id]
    try:
        if message.text:
            await bot.send_message(partner, f"💬: {message.text}")
        elif message.photo:
            await bot.send_photo(partner, photo=message.photo[-1].file_id, caption=message.caption if message.caption else "📸 Фото")
        elif message.sticker:
            await bot.send_sticker(partner, sticker=message.sticker.file_id)
        elif message.voice:
            await bot.send_voice(partner, voice=message.voice.file_id)
        elif message.video_note:
            await bot.send_video_note(partner, video_note=message.video_note.file_id)
    except Exception as e:
        logging.error(f"Помилка пересилки повідомлення в рулетці: {e}")

# --- 🏆 ТОП-5 БОРИСЛАВА (ГАРАНТОВАНІ АНКЕТИ) ---
@dp.message(F.text == "🏆 ТОП-5 Борислава")
async def show_top_five(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE is_banned = 0 AND in_top = 1 LIMIT 5") as c:
            top_users = await c.fetchall()
        
        # Якщо призначеного топу немає або мало, добираємо активних
        if len(top_users) < 5:
            needed = 5 - len(top_users)
            existing_ids = [u['user_id'] for u in top_users] if top_users else [0]
            query = f"SELECT * FROM users WHERE is_banned = 0 AND is_active = 1 AND user_id NOT IN ({','.join(map(str, existing_ids))}) ORDER BY created_at DESC LIMIT {needed}"
            async with db.execute(query) as c2:
                extra_users = await c2.fetchall()
                top_users = list(top_users) + list(extra_users)
            
    if not top_users:
        return await message.answer("🌟 Наразі база пуста, немає кого показати в ТОПі.")
        
    await message.answer("🔥 **🏆 ТОП-5 НАЙКРАЩИХ АНКЕТ БОРИСЛАВА** 🔥")
    for idx, user in enumerate(top_users, 1):
        caption = f"⭐ **Місце #{idx}**\n👑 **{user['name']}**, {user['age']} років\n📍 район {user['location']}\n💬 *«{user['bio']}»*"
        if user['username']:
            caption += f"\n🔗 @{user['username']}"
        try:
            await bot.send_photo(message.from_user.id, photo=user['photo'], caption=caption, parse_mode="Markdown")
            await asyncio.sleep(0.3)
        except: pass

# --- 🎫 ІДЕЯ ДЛЯ ПОБАЧЕННЯ ---
@dp.message(F.text == "🎫 Ідея для побачення")
async def idea_cmd(message: types.Message):
    await message.answer(f"💡 **Ось чудова атмосфера для вашого побачення:**\n\n{random.choice(BORYSLAV_IDEAS)}", parse_mode="Markdown")

# --- 📢 СТРІЧКА ОГОЛОШЕНЬ (З МОДЕРАЦІЄЮ ДЛЯ АДМІНА) ---
@dp.message(F.text == "📢 Стрічка оголошень")
async def show_ads(message: types.Message):
    uid = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id, name, text FROM ads ORDER BY id DESC LIMIT 5") as cursor: 
            ads = await cursor.fetchall()
            
    if not ads: 
        inline_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Додати своє оголошення", callback_data="add_ad")]
        ])
        return await message.answer("📰 **Стрічка оголошень Борислава порожня.**\n\nБудь першим, хто щось опублікує тут!", reply_markup=inline_kb)
    
    await message.answer("📰 **ЛОКАЛЬНА СТРІЧКА М. БОРИСЛАВ**")
    for ad in ads:
        feed_item = f"👤 **{ad['name']}**:\n«{ad['text']}»"
        buttons = [[InlineKeyboardButton(text="✍️ Додати своє", callback_data="add_ad")]]
        
        # Модераторська кнопка тільки для тебе
        if uid == ADMIN_ID:
            buttons.insert(0, [InlineKeyboardButton(text="🗑 Видалити оголошення", callback_data=f"del_ad_{ad['id']}")])
            
        inline_kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer(feed_item, parse_mode="Markdown", reply_markup=inline_kb)

@dp.callback_query(F.data.startswith("del_ad_"))
async def delete_ad_callback(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("❌ Ти не адмін!", show_alert=True)
        
    ad_id = int(call.data.split("_")[2])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM ads WHERE id = ?", (ad_id,))
        await db.commit()
        
    await call.answer("✅ Оголошення видалено")
    await call.message.edit_text("🗑 _Це оголошення було видалено адміністратором._", parse_mode="Markdown")

@dp.callback_query(F.data == "add_ad")
async def add_ad_callback(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer("✍️ Введіть текст вашого оголошення (до 150 символів):")
    await state.set_state(AdStates.waiting_for_ad_text)

@dp.message(AdStates.waiting_for_ad_text)
async def save_user_ad(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    text = message.text
    await state.clear()
    
    if len(text) > 150:
        return await message.answer("⚠️ Текст оголошення занадто великий. Ліміт 150 символів.")
        
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT name FROM users WHERE user_id = ?", (uid,)) as c:
            user = await c.fetchone()
            
    name = user['name'] if user else "Анонім"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO ads (user_id, name, text) VALUES (?, ?, ?)", (uid, name, text))
        await db.commit()
        
    await message.answer("✅ Ваше оголошення успішно додано в загальну стрічку!", reply_markup=get_main_menu(uid))

# --- ПОВНА АДМІН-ПАНЕЛЬ ---
@dp.message(F.text == "🛠 Адмін-панель")
async def admin_btn(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    await message.answer("🛠 **Панель адміністратора активована!** Керуй базою за допомогою кнопок.", reply_markup=get_admin_menu())

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
        async with db.execute("SELECT COUNT(*) FROM ads") as c4: ads_count = (await c4.fetchone())[0]
    stats_text = f"📊 **СТАТИСТИКА БОТА**\n\n👥 Всього користувачів: {total}\n🟢 Активні анкети: {active}\n🔴 В бані: {banned}\n📢 Постів у стрічці: {ads_count}"
    await message.answer(stats_text)

@dp.message(F.text == "📢 Зробити розсилку")
async def broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("✍️ Надішли текст розсилки для всіх користувачів:")
    await state.set_state(AdminStates.waiting_for_broadcast)

@dp.message(AdminStates.waiting_for_broadcast)
async def broadcast_finish(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    text = message.text
    await state.clear()
    await message.answer("🚀 Розсилка запущена на сервері...")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor: rows = await cursor.fetchall()
    success, failed = 0, 0
    for row in rows:
        try:
            await bot.send_message(row[0], f"📢 **ПОВІДОМЛЕННЯ ВІД АДМІНІСТРАЦІЇ:**\n\n{text}")
            success += 1
            await asyncio.sleep(0.05)
        except: failed += 1
    await message.answer(f"✅ Готово!\n🟢 Доставлено: {success}\n🔴 Не доставлено (блок): {failed}", reply_markup=get_admin_menu())

@dp.message(F.text == "🚫 Забанити за ID")
async def ban_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("🔢 Введи конкретний Telegram ID для видачі бану:")
    await state.set_state(AdminStates.waiting_for_ban)

@dp.message(AdminStates.waiting_for_ban)
async def ban_finish(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID or not message.text.isdigit(): return
    target = int(message.text)
    await state.clear()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned=1, is_active=0 WHERE user_id=?", (target,))
        await db.commit()
    await message.answer(f"🔴 Користувача {target} успішно забанено!", reply_markup=get_admin_menu())
    try: await bot.send_message(target, "❌ Твій профіль заблоковано адміністрацією за порушення правил.")
    except: pass

@dp.message(F.text == "🟢 Розбанити за ID")
async def unban_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("🔢 Введи Telegram ID для зняття бану:")
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
    await message.answer("🔢 Введи Telegram ID користувача:")
    await state.set_state(AdminStates.waiting_for_search)

@dp.message(AdminStates.waiting_for_search)
async def search_finish(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID or not message.text.isdigit(): return
    target = int(message.text)
    await state.clear()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (target,)) as c: user = await c.fetchone()
    if not user: return await message.answer("❌ Анкету не знайдено в БД.", reply_markup=get_admin_menu())
    
    b_status = "🔴 В БАНІ" if user['is_banned'] else "🟢 Активний"
    t_status = "⭐️ У ТОПі" if user['in_top'] else "Ні"
    caption = f"🔍 Знайдено користувача:\n👤 {user['name']}, {user['age']} р.\n📍 {user['location']}\n🔗 @{user['username']}\n💬 {user['bio']}\n\nБазовий статус: {b_status}\nТОП: {t_status}"
    await bot.send_photo(ADMIN_ID, photo=user['photo'], caption=caption, reply_markup=get_admin_menu())

@dp.message(F.text == "⭐️ Додати в ТОП за ID")
async def top_add_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("🔢 Введи Telegram ID для примусового додавання в ТОП-5:")
    await state.set_state(AdminStates.waiting_for_top_add)

@dp.message(AdminStates.waiting_for_top_add)
async def top_add_finish(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID or not message.text.isdigit(): return
    target = int(message.text)
    await state.clear()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET in_top=1 WHERE user_id=?", (target,))
        await db.commit()
    await message.answer(f"⭐️ Користувача {target} додано в категорію ТОП-5!", reply_markup=get_admin_menu())

# --- АСИНХРОННИЙ СТАРТ ФАЙЛУ ---
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
