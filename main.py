import logging
import asyncio
import os
import time
import random
from datetime import datetime
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

TOKEN = "8904222239:AAF4utz7NX3WOiD5CEVUYozig49Ldcv4mu8"
ADMIN_ID = 2131137264
DB_PATH = "boryslav_dating.db"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

WAITING_ROOM = []       # Для рулетки
GLOBAL_CHAT_USERS = []  # Список користувачів у загальному чаті
ACTIVE_CHATS = {}       # Спільна база активних діалогів рулетки

class Registration(StatesGroup):
    name = State()
    age = State()
    gender = State()
    looking_for = State()  # Новий етап вибору
    location = State()
    bio = State()
    photo = State()

class AdState(StatesGroup):
    text = State()

class VerifyState(StatesGroup):
    photo = State()

class AdminStates(StatesGroup):
    broadcast_text = State()

class ManualCheckState(StatesGroup):
    wait_photo = State()

# --- КРАСИВІ ІДЕЇ ДЛЯ БОРИСЛАВЧАН ---
DATE_IDEAS = [
    "Прогулянка біля міського озера з великим стаканчиком кави та круасанами з місцевої пекарні.",
    "Поїздка на вечірню Східницю: піднятися на оглядовий майданчик та зустріти захід сонця разом.",
    "Затишні посиденьки в центрі Борислава за гарячим шоколадом або піцою.",
    "Культурне побачення: відвідайте Аптеку-музей Йогана Зега, а потім прогуляйтеся парком.",
    "Міні-подорож: підніміться на Буковицю пішки або на витягу, щоб побачити панораму міста.",
    "Вечір настільних ігор у кав'ярні або спільний похід у кіно в Дрогобич чи Трускавець.",
    "Романтичний пікнік у парку біля джерела з фруктами та улюбленою музикою в колонці.",
    "Вечірня прогулянка по Тустановичах або Мразниці, рахуючи зірки далеко від міських ліхтарів."
]

async def init_db():
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "user_id INTEGER PRIMARY KEY, username TEXT, name TEXT, "
            "age INTEGER, gender TEXT, looking_for TEXT, location TEXT, bio TEXT, "
            "photo TEXT, is_verified INTEGER DEFAULT 0, "
            "is_banned INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1, "
            "in_top INTEGER DEFAULT 1, is_under_check INTEGER DEFAULT 0, fake_status TEXT DEFAULT '')"
        )
        try: await db.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
        except: pass
        try: await db.execute("ALTER TABLE users ADD COLUMN in_top INTEGER DEFAULT 1")
        except: pass
        try: await db.execute("ALTER TABLE users ADD COLUMN looking_for TEXT")
        except: pass
        try: await db.execute("ALTER TABLE users ADD COLUMN is_under_check INTEGER DEFAULT 0")
        except: pass
        try: await db.execute("ALTER TABLE users ADD COLUMN fake_status TEXT DEFAULT ''")
        except: pass
        
        await db.execute(
            "CREATE TABLE IF NOT EXISTS ads ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, "
            "text TEXT, created_at REAL)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS actions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, from_id INTEGER, "
            "to_id INTEGER, action TEXT, UNIQUE(from_id, to_id))"
        )
        await db.commit()

def get_main_menu():
    kb = [
        [KeyboardButton(text="❤️ Дивитись анкети"), KeyboardButton(text="🎲 Анонімна рулетка")],
        [KeyboardButton(text="📢 Стрічка оголошень"), KeyboardButton(text="⚡ Загальний чат")],
        [KeyboardButton(text="🎫 Ідея для побачення"), KeyboardButton(text="🏆 ТОП-5 Борислава")],
        [KeyboardButton(text="👤 Мій Профіль ✨")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_profile_management_keyboard(is_active, in_top, is_verified):
    active_text = "🟢 Показувати анкету" if is_active else "🔴 Анкета прихована"
    top_text = "🌟 Сховатись з ТОП" if in_top else "✨ Йти в ТОП"
    buttons = [
        [InlineKeyboardButton(text="📝 Редагувати профіль", callback_data="profile_edit")],
        [InlineKeyboardButton(text=active_text, callback_data="profile_toggle_active"),
         InlineKeyboardButton(text=top_text, callback_data="profile_toggle_top")]
    ]
    if not is_verified:
        buttons.append([InlineKeyboardButton(text="☑️ Пройти верифікацію", callback_data="profile_verify")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_profile_action_keyboard(target_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{target_id}"), 
         InlineKeyboardButton(text="👎 Дизлайк", callback_data=f"dislike_{target_id}")],
        [InlineKeyboardButton(text="⚠️ Скарга", callback_data=f"report_{target_id}")]
    ])

def get_admin_inline_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Повна Статистика", callback_data="admin_stats_refresh")],
        [InlineKeyboardButton(text="📢 Рассылка усім", callback_data="admin_broadcast_start")],
        [InlineKeyboardButton(text="❌ Закрити панель", callback_data="admin_clear")]
    ])

# --- ПЕРЕВІРКА МІДЛВАРІ (БАН + ПЕРЕВІРКА ФЕЙКА) ---
@dp.message(F.text)
async def check_user_status(message: types.Message, state: FSMContext = None):
    # Дозволяємо системні перевірки
    if message.text.startswith("/"): return
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT is_banned, is_under_check FROM users WHERE user_id = ?", (user_id,)) as c:
            u = await c.fetchone()
    if u:
        if u['is_banned'] == 1:
            await message.answer("❌ Твій профіль заблоковано.")
            return True
        if u['is_under_check'] == 1:
            current_state = await state.get_state() if state else None
            if current_state != ManualCheckState.wait_photo.state:
                await message.answer("⚠️ Твій профіль відправлено на обов'язкову перевірку адміном!\n\n📸 Будь ласка, надішли своє актуальне селфі сюди, щоб розблокувати меню:")
                if state: await state.set_state(ManualCheckState.wait_photo)
            return True
    return False

# --- СТАРТ ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT name, is_banned, is_under_check FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
    if user:
        if user['is_banned'] == 1:
            return await message.answer("❌ Твій профіль заблоковано.")
        if user['is_under_check'] == 1:
            await message.answer("⚠️ Твій профіль під перевіркою. Надішли своє селфі фото:")
            await state.set_state(ManualCheckState.wait_photo)
            return
        await message.answer(f"✨ Привіт, {user['name']}! Раді бачити тебе в Бориславі знову. 😉", reply_markup=get_main_menu())
    else:
        await message.answer("👋 Вітаємо у просторі знайомств Борислава!\n\nДавай створимо твою анкету. Як тебе звати?")
        await state.set_state(Registration.name)

@dp.message(Registration.name)
async def reg_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("🔢 Скільки тобі років?")
    await state.set_state(Registration.age)

@dp.message(Registration.age)
async def reg_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("🧮 Введи вік цифрами:")
    await state.update_data(age=int(message.text))
    kb = [[KeyboardButton(text="Хлопець 👦"), KeyboardButton(text="Дівчина 👧")]]
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)
    await message.answer("✨ Обери свою стать:", reply_markup=markup)
    await state.set_state(Registration.gender)

@dp.message(Registration.gender)
async def reg_gender(message: types.Message, state: FSMContext):
    gender = "male" if "Хлопець" in message.text else "female"
    await state.update_data(gender=gender)
    
    kb = [[KeyboardButton(text="Хлопця 👦"), KeyboardButton(text="Дівчину 👧")]]
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)
    await message.answer("🔍 Кого ти шукаєш?", reply_markup=markup)
    await state.set_state(Registration.looking_for)

@dp.message(Registration.looking_for)
async def reg_looking(message: types.Message, state: FSMContext):
    looking = "male" if "Хлопця" in message.text else "female"
    await state.update_data(looking_for=looking)
    
    kb = [
        [KeyboardButton(text="📍 Центр"), KeyboardButton(text="📍 Баня")],
        [KeyboardButton(text="📍 Мразниця"), KeyboardButton(text="📍 Ґубичі")],
        [KeyboardButton(text="📍 Потік"), KeyboardButton(text="📍 Волянка")],
        [KeyboardButton(text="📍 Тустановичі")],
        [KeyboardButton(text="🌍 Околиці (Східниця/Трускавець/Дрогобич)")]
    ]
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)
    await message.answer("🏡 Обери свій район:", reply_markup=markup)
    await state.set_state(Registration.location)

@dp.message(Registration.location)
async def reg_location(message: types.Message, state: FSMContext):
    loc = message.text.replace("📍 ", "")
    await state.update_data(location=loc)
    await message.answer("📝 Розкажи коротко про себе / кого шукаєш:")
    await state.set_state(Registration.bio)

@dp.message(Registration.bio)
async def reg_bio(message: types.Message, state: FSMContext):
    await state.update_data(bio=message.text)
    await message.answer("📸 Надішли одне гарне фото для профілю:")
    await state.set_state(Registration.photo)

@dp.message(Registration.photo, F.photo)
async def reg_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        ins_sql = (
            "INSERT OR REPLACE INTO users (user_id, username, name, age, gender, looking_for, "
            "location, bio, photo, is_verified, is_banned, is_active, in_top, is_under_check, fake_status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT is_verified FROM users WHERE user_id=?), 0), 0, 1, 1, 0, '')"
        )
        await db.execute(ins_sql, (message.from_user.id, message.from_user.username, data['name'], data['age'], data['gender'], data['looking_for'], data['location'], data['bio'], photo_id, message.from_user.id))
        await db.commit()
    await message.answer("✨ 🎉 Твоя анкета активована в пошуку!", reply_markup=get_main_menu())
    await state.clear()

# --- МІНІМАЛІСТИЧНИЙ ПРОФІЛЬ ---
@dp.message(F.text.in_({"👤 Мій Профіль ✨", "👤 Моя анкета"}))
async def my_profile(message: types.Message):
    if await check_user_status(message): return
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
    if user:
        v_mark = f" {user['fake_status']}" if user['fake_status'] else (" ☑️" if user['is_verified'] else "")
        caption = (
            f"👤 **{user['name']}**, {user['age']} років{v_mark}\n"
            f"📍 р-н {user['location']}\n"
            f"🔍 Шукає: {'Хлопців 👦' if user['looking_for'] == 'male' else 'Дівчат 👧'}\n\n"
            f"📝 {user['bio']}\n\n"
            f"⚡ *Пошук:* {'Активний 🟢' if user['is_active'] else 'Вимкнено 🔴'} | *ТОП:* {'Бере участь 🌟' if user['in_top'] else 'Приховано 💨'}"
        )
        await bot.send_photo(user_id, photo=user['photo'], caption=caption, reply_markup=get_profile_management_keyboard(user['is_active'], user['in_top'], user['is_verified']), parse_mode="Markdown")
    else:
        await message.answer("У тебе немає анкет. Натисни /start")

@dp.callback_query(F.data == "profile_edit")
async def edit_profile_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Напиши своє нове ім'я:")
    await state.set_state(Registration.name)
    await callback.answer()

@dp.callback_query(F.data == "profile_toggle_active")
async def toggle_active_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT is_active FROM users WHERE user_id = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            new_val = 0 if res['is_active'] else 1
        await db.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (new_val, user_id))
        await db.commit()
    await callback.answer("Статус змінено")
    await callback.message.delete()
    class FakeMsg:
        def __init__(self, uid): self.from_user = self; self.id = uid
        async def answer(self, text, reply_markup=None): await bot.send_message(user_id, text, reply_markup=reply_markup)
    await my_profile(FakeMsg(user_id))

@dp.callback_query(F.data == "profile_toggle_top")
async def toggle_top_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT in_top FROM users WHERE user_id = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            new_val = 0 if res['in_top'] else 1
        await db.execute("UPDATE users SET in_top = ? WHERE user_id = ?", (new_val, user_id))
        await db.commit()
    await callback.answer("Статус ТОП змінено")
    await callback.message.delete()
    class FakeMsg:
        def __init__(self, uid): self.from_user = self; self.id = uid
        async def answer(self, text, reply_markup=None): await bot.send_message(user_id, text, reply_markup=reply_markup)
    await my_profile(FakeMsg(user_id))

@dp.callback_query(F.data == "profile_verify")
async def verify_shortcut(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("📸 Надішли селфі для верифікації:")
    await state.set_state(VerifyState.photo)
    await callback.answer()

# --- АНКЕТИ ТА ЛАЙКИ (ОНОВЛЕНО ФІЛЬТР СТАТІ) ---
@dp.message(F.text == "❤️ Дивитись анкети")
async def view_profiles(message: types.Message):
    if await check_user_status(message): return
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT gender, looking_for FROM users WHERE user_id = ?", (user_id,)) as c:
            me = await c.fetchone()
        if not me: return await message.answer("Спочатку зареєструйся через /start")
        
        sel_sql = (
            "SELECT * FROM users WHERE user_id != ? AND is_banned = 0 AND is_active = 1 "
            "AND gender = ? AND looking_for = ? "
            "AND user_id NOT IN (SELECT to_id FROM actions WHERE from_id = ?) ORDER BY RANDOM() LIMIT 1"
        )
        async with db.execute(sel_sql, (user_id, me['looking_for'], me['gender'], user_id)) as cursor:
            target = await cursor.fetchone()
            
    if not target:
        return await message.answer("🌍 Анкети твого типу закінчились! Заходь пізніше.")
    v_mark = f" {target['fake_status']}" if target['fake_status'] else (" ☑️" if target['is_verified'] else "")
    caption = f"🔥 **{target['name']}**, {target['age']}{v_mark}\n📍 р-н {target['location']}\n\n📝 {target['bio']}"
    await bot.send_photo(user_id, photo=target['photo'], caption=caption, reply_markup=get_profile_action_keyboard(target['user_id']), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("like_") | F.data.startswith("dislike_"))
async def handle_vote(callback: CallbackQuery):
    action, target_id = callback.data.split("_")
    target_id = int(target_id)
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        db.row_factory = aiosqlite.Row
        try:
            await db.execute("INSERT OR IGNORE INTO actions (from_id, to_id, action) VALUES (?, ?, ?)", (user_id, target_id, action))
            await db.commit()
        except: pass
        
        async with db.execute("SELECT gender, looking_for FROM users WHERE user_id = ?", (user_id,)) as c:
            me = await c.fetchone()
            
        if action == "like":
            async with db.execute("SELECT id FROM actions WHERE from_id = ? AND to_id = ? AND action = 'like'", (target_id, user_id)) as cursor:
                match = await cursor.fetchone()
            if match:
                async with db.execute("SELECT username, name FROM users WHERE user_id = ?", (user_id,)) as c1: u_user = await c1.fetchone()
                async with db.execute("SELECT username, name FROM users WHERE user_id = ?", (target_id,)) as c2: t_user = await c2.fetchone()
                link_u = f"@{u_user['username']}" if u_user['username'] else f"[Посилання](tg://user?id={user_id})"
                link_t = f"@{t_user['username']}" if t_user['username'] else f"[Посилання](tg://user?id={target_id})"
                await bot.send_message(user_id, f"💖 **ВЗАЄМНА СИМПАТІЯ з {t_user['name']}!**\nПосилання: {link_t}", parse_mode="Markdown")
                await bot.send_message(target_id, f"💖 **ВЗАЄМНА СИМПАТІЯ з {u_user['name']}!**\nПосилання: {link_u}", parse_mode="Markdown")
        
        next_sql = (
            "SELECT * FROM users WHERE user_id != ? AND is_banned = 0 AND is_active = 1 "
            "AND gender = ? AND looking_for = ? "
            "AND user_id NOT IN (SELECT to_id FROM actions WHERE from_id = ?) ORDER BY RANDOM() LIMIT 1"
        )
        async with db.execute(next_sql, (user_id, me['looking_for'], me['gender'], user_id)) as cursor:
            next_t = await cursor.fetchone()
            
    try: await callback.message.delete()
    except: pass
    if next_t:
        v_mark = f" {next_t['fake_status']}" if next_t['fake_status'] else (" ☑️" if next_t['is_verified'] else "")
        caption = f"🔥 **{next_t['name']}**, {next_t['age']}{v_mark}\n📍 р-н {next_t['location']}\n\n📝 {next_t['bio']}"
        await bot.send_photo(user_id, photo=next_t['photo'], caption=caption, reply_markup=get_profile_action_keyboard(next_t['user_id']), parse_mode="Markdown")
    else:
        await bot.send_message(user_id, "🌍 Це була остання відповідна анкетка!")
    await callback.answer()

# --- СКАРГИ ТА МОДЕРАЦІЯ ---
@dp.callback_query(F.data.startswith("report_"))
async def report_user(callback: CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    await callback.message.answer("⚠️ Скарга надіслана.")
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT name, username FROM users WHERE user_id = ?", (target_id,)) as cursor:
            bad_user = await cursor.fetchone()
    u_name = f"@{bad_user['username']}" if bad_user['username'] else "Немає"
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 ЗАБАНЕТИ", callback_data=f"admin_ban_{target_id}")],
        [InlineKeyboardButton(text="✅ Ігнор", callback_data="admin_clear")]
    ])
    await bot.send_message(ADMIN_ID, f"🚨 **СКАРГА!**\n🆔 ID: `{target_id}`\n👤 Ім'я: {bad_user['name']}\n🔗 Юзер: {u_name}", reply_markup=admin_kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_ban_"))
async def admin_ban(callback: CallbackQuery):
    target_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        await db.execute("UPDATE users SET is_banned = 1, is_active = 0 WHERE user_id = ?", (target_id,))
        await db.commit()
    await callback.message.edit_text(f"🔴 `{target_id}` забанений.")
    await callback.answer()

@dp.callback_query(F.data == "admin_clear")
async def admin_clear(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()

# --- СТРІЧКА ОГОЛОШЕНЬ ---
@dp.message(F.text == "📢 Стрічка оголошень")
async def ads_menu(message: types.Message):
    if await check_user_status(message): return
    kb = [
        [InlineKeyboardButton(text="📋 Переглянути стрічку", callback_data="ads_view")],
        [InlineKeyboardButton(text="✍️ Опублікувати новину", callback_data="ads_create")]
    ]
    await message.answer("📢 **СТРІЧКА ОГОЛОШЕНЬ БОРИСЛАВА**", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "ads_view")
async def view_ads(callback: CallbackQuery):
    user_id = callback.from_user.id
    day_ago = time.time() - 86400
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        db.row_factory = aiosqlite.Row
        query = (
            "SELECT ads.id, ads.text, ads.created_at, users.name, users.location "
            "FROM ads JOIN users ON ads.user_id = users.user_id "
            "WHERE ads.created_at > ? ORDER BY ads.id DESC LIMIT 10"
        )
        async with db.execute(query, (day_ago,)) as cursor: all_ads = await cursor.fetchall()
        
    if not all_ads: 
        await callback.answer()
        return await callback.message.answer("📭 Стрічка наразі порожня.")
        
    await callback.message.answer("👇 **Останні оголошення міста:**")
    for row in all_ads:
        pub_time = datetime.fromtimestamp(row['created_at']).strftime('%H:%M')
        msg_text = f"📌 **{row['name']}** (р-н {row['location']}) | 🕒 *{pub_time}*\n📝 {row['text']}"
        if user_id == ADMIN_ID:
            adm_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 Видалити (Адмін)", callback_data=f"adelete_{row['id']}")]])
            await bot.send_message(user_id, msg_text, parse_mode="Markdown", reply_markup=adm_kb)
        else:
            await bot.send_message(user_id, msg_text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("adelete_"))
async def admin_delete_ad(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    ad_id = int(callback.data.split("_")[1])
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        await db.execute("DELETE FROM ads WHERE id = ?", (ad_id,))
        await db.commit()
    await callback.message.edit_text("❌ *Оголошення видалено адміністратором.*", parse_mode="Markdown")
    await callback.answer("Видалено!")

@dp.callback_query(F.data == "ads_create")
async def create_ad_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("✍️ Введи текст оголошення:")
    await state.set_state(AdState.text)
    await callback.answer()

@dp.message(AdState.text)
async def create_ad_finish(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        await db.execute("INSERT INTO ads (user_id, text, created_at) VALUES (?, ?, ?)", (message.from_user.id, message.text, time.time()))
        await db.commit()
    await message.answer("✅ Опубліковано!")
    await state.clear()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#          ⚡ ПОЛНОЦІННИЙ ЗАГАЛЬНИЙ ЧАТ ⚡
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@dp.message(F.text == "⚡ Загальний чат")
async def enter_global_chat(message: types.Message, state: FSMContext):
    if await check_user_status(message, state): return
    uid = message.from_user.id
    if uid in ACTIVE_CHATS: return await message.answer("⚠️ Спочатку вийди з анонімної рулетки!")
    
    if uid not in GLOBAL_CHAT_USERS:
        GLOBAL_CHAT_USERS.append(uid)
        
    kb = [[KeyboardButton(text="🚪 Вийти з чату")]]
    await message.answer(
        "⚡ **Ти увійшов у Загальний Чат Борислава!** ⚡\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💬 Будь-яке твоє повідомлення побачать усі учасники кімнати.\n"
        "Жодних анкет, просто живе спілкування містян! 🔥",
        reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    )
    await state.set_state("global_chat_active")

@dp.message(F.text == "🚪 Вийти з чату")
async def exit_global_chat(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if uid in GLOBAL_CHAT_USERS:
        GLOBAL_CHAT_USERS.remove(uid)
    await state.clear()
    await message.answer("🚪 Ти вийшов із загального чату.", reply_markup=get_main_menu())

# --- АНОНІМНА РУЛЕТКА ---
@dp.message(F.text == "🎲 Анонімна рулетка")
async def start_roulette(message: types.Message):
    if await check_user_status(message): return
    user_id = message.from_user.id
    if user_id in GLOBAL_CHAT_USERS: return await message.answer("⚠️ Спочатку вийди із загального чату!")
    if user_id in ACTIVE_CHATS: return
    if WAITING_ROOM:
        p_id = WAITING_ROOM.pop(0)
        ACTIVE_CHATS[user_id] = p_id
        ACTIVE_CHATS[p_id] = user_id
        kb = [[KeyboardButton(text="🛑 Вийти з чату")]]
        await bot.send_message(user_id, "🎉 Знайдено співрозмовника з Борислава! Спілкуйтеся анонімно.", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))
        await bot.send_message(p_id, "🎉 Знайдено співрозмовника з Борислава! Спілкуйтеся анонімно.", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))
    else:
        WAITING_ROOM.append(user_id)
        kb = [[KeyboardButton(text="🛑 Вийти з чату")]]
        await message.answer("🔍 Шукаю для тебе пару... Зачекай хвилинку.", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp.message(F.text == "🛑 Вийти з чату")
async def exit_chat(message: types.Message):
    user_id = message.from_user.id
    if user_id in WAITING_ROOM: WAITING_ROOM.remove(user_id)
    elif user_id in ACTIVE_CHATS:
        p_id = ACTIVE_CHATS.pop(user_id)
        ACTIVE_CHATS.pop(p_id, None)
        try: await bot.send_message(p_id, "🚪 Співрозмовник залишив чат.", reply_markup=get_main_menu())
        except: pass
    await message.answer("Діалог завершено.", reply_markup=get_main_menu())

# --- ОБРОБНИК МУЛЬТИ-ЧАТІВ + ХЕНДЛЕР НА 'ТЮТЮННИК' ---
@dp.message(lambda m: not m.text or not m.text.startswith("/"))
async def chat_handlers(message: types.Message, state: FSMContext):
    if await check_user_status(message, state): return
    uid = message.from_user.id
    current_state = await state.get_state()
    
    # Секретна реакція
    if message.text and "тютюнник" in message.text.casefold():
        await message.answer("Нахуй пса")
        return

    # Логіка Загального чату
    if current_state == "global_chat_active":
        if message.text == "🚪 Вийти з чату": return
        for user in GLOBAL_CHAT_USERS:
            if user != uid:
                try: await bot.send_message(user, f"💬 [Загальний чат] {message.from_user.first_name}: {message.text or '[Медіафайл]'}")
                except: pass
        return

    # Логіка анонімної рулетки
    if uid in ACTIVE_CHATS:
        try: await bot.send_message(ACTIVE_CHATS[uid], f"💬 Співрозмовник: {message.text or '[Медіафайл]'}")
        except: pass

# --- ВЕРИФІКАЦІЯ ---
@dp.message(F.text == "☑️ Пройти верифікацію")
async def verify_start(message: types.Message, state: FSMContext):
    if await check_user_status(message): return
    await message.answer("📸 Надішли своє актуальне селфі:")
    await state.set_state(VerifyState.photo)

@dp.message(VerifyState.photo, F.photo)
async def verify_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await message.answer("⏳ Надіслано модераторам!")
    await state.clear()
    username_str = f"@{message.from_user.username}" if message.from_user.username else f"[Посилання](tg://user?id={message.from_user.id})"
    admin_verify_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Верифікувати", callback_data=f"averify_yes_{message.from_user.id}"), InlineKeyboardButton(text="❌ Відхилити", callback_data="admin_clear")]])
    await bot.send_photo(ADMIN_ID, photo=photo_id, caption=f"👤 **ЗАПИТ НА ВЕРИФІКАЦІЮ**\n🆔 ID: `{message.from_user.id}`\n🔗 Профіль: {username_str}", reply_markup=admin_verify_kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("averify_yes_"))
async def admin_verify_yes(callback: CallbackQuery):
    t_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        await db.execute("UPDATE users SET is_verified = 1, fake_status='' WHERE user_id = ?", (t_id,))
        await db.commit()
    await callback.message.reply(f"🟢 Користувач `{t_id}` верифікований.")
    try: await bot.send_message(t_id, "🎉 Твій профіль успішно верифіковано ☑️!")
    except: pass
    await callback.answer()

# --- КОРРИСТУВАЧ ЗДАЄ ФОТО ПІД ЧАС АДМІН-ПЕРЕВІРКИ ---
@dp.message(ManualCheckState.wait_photo, F.photo)
async def manual_check_photo_received(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await message.answer("⏳ Фото надіслано адміну. Очікуй рішення, функції заблоковані.")
    await state.clear()
    
    uid = message.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"man_confirm_{uid}"),
         InlineKeyboardButton(text="❌ Відмовити (Фейк)", callback_data=f"man_fake_{uid}")]
    ])
    await bot.send_photo(ADMIN_ID, photo=photo_id, caption=f"📸 **ФОТО З ПЕРЕВІРКИ ФЕЙКА**\n🆔 ID: `{uid}`\n👤 Юзер: @{message.from_user.username}", reply_markup=kb)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#          📖 АДМІНІСТРАТИВНА КНИГА КОРИСТУВАЧІВ 📖
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@dp.message(Command("list"))
async def admin_users_list(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await send_user_page(message.from_user.id, page=0, edit=False)

async def send_user_page(chat_id, page: int, edit=False):
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        db.row_factory = aiosqlite.Row
        users = await (await db.execute("SELECT user_id, name, username FROM users")).fetchall()
        
    if not users:
        return await bot.send_message(chat_id, "База даних порожня.")
        
    limit = 7
    total_pages = (len(users) + limit - 1) // limit
    start = page * limit
    end = start + limit
    page_users = users[start:end]
    
    buttons = []
    for u in page_users:
        u_name = u['name'] if u['name'] else "Без імені"
        buttons.append([InlineKeyboardButton(text=f"👤 {u_name} (@{u['username'] or '---'})", callback_data=f"book_view_{u['user_id']}_{page}")])
        
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"book_page_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="noop"))
    if end < len(users):
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"book_page_{page+1}"))
        
    buttons.append(nav_buttons)
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    if edit:
        try: await bot.edit_message_text("📖 **Книга користувачів:**", chat_id=chat_id, message_id=edit, reply_markup=kb)
        except: pass
    else:
        await bot.send_message(chat_id, "📖 **Книга користувачів:**", reply_markup=kb)

@dp.callback_query(F.data.startswith("book_page_"))
async def book_page_nav(call: CallbackQuery):
    page = int(call.data.split("_")[2])
    await send_user_page(call.message.chat.id, page=page, edit=call.message.message_id)
    await call.answer()

@dp.callback_query(F.data.startswith("book_view_"))
async def book_view_profile(call: CallbackQuery):
    _, _, uid, page = call.data.split("_")
    uid, page = int(uid), int(page)
    
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        db.row_factory = aiosqlite.Row
        user = await (await db.execute("SELECT * FROM users WHERE user_id = ?", (uid,))).fetchone()
        
    if not user:
        return await call.answer("Користувача не знайдено.")
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Верифікувати", callback_data=f"adm_act_verify_{uid}_{page}"),
         InlineKeyboardButton(text="🚫 Забанити", callback_data=f"adm_act_ban_{uid}_{page}")],
        [InlineKeyboardButton(text="🔍 Почати перевірку", callback_data=f"adm_act_check_{uid}_{page}"),
         InlineKeyboardButton(text="❌ Позначити як Фейк", callback_data=f"adm_act_fake_{uid}_{page}")],
        [InlineKeyboardButton(text="↩️ Назад до книги", callback_data=f"book_page_{page}")]
    ])
    
    caption = (
        f"📋 **АНКЕТА З КНИГИ БАЗЫ**\n"
        f"🆔 ID: `{user['user_id']}`\n"
        f"👤 Ім'я: {user['name']}, {user['age']} р.\n"
        f"🔗 Юзер: @{user['username'] or 'немає'}\n"
        f"📍 Район: {user['location']}\n"
        f"📜 Біо: {user['bio']}\n"
        f"⚙️ Статус: Бан: {user['is_banned']} | Вер: {user['is_verified']} | Фейк: {user['fake_status'] or 'ні'}"
    )
    await bot.send_photo(call.message.chat.id, photo=user['photo'], caption=caption, reply_markup=kb, parse_mode="Markdown")
    await call.answer()

# --- КНОПКИ ДІЙ НАД АНКЕТОЮ З КНИГИ ---
@dp.callback_query(F.data.startswith("adm_act_"))
async def admin_actions_execution(call: CallbackQuery):
    _, _, action, uid, page = call.data.split("_")
    uid, page = int(uid), int(page)
    
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        if action == "verify":
            await db.execute("UPDATE users SET is_verified = 1, fake_status='' WHERE user_id = ?", (uid,))
            await call.message.answer(f"✅ Успішно верифіковано `{uid}`")
        elif action == "ban":
            await db.execute("UPDATE users SET is_banned = 1, is_active = 0 WHERE user_id = ?", (uid,))
            await call.message.answer(f"🚫 Користувач `{uid}` забанений.")
        elif action == "check":
            await db.execute("UPDATE users SET is_under_check = 1 WHERE user_id = ?", (uid,))
            await call.message.answer(f"🔍 Користувачу `{uid}` заблоковано меню. Очікуємо селфі.")
            try: await bot.send_message(uid, "⚠️ Адміністрація вимагає пройти верифікацію особистості! Надішли своє актуальне фото-селфі прямо сюди для розблокування:")
            except: pass
        elif action == "fake":
            await db.execute("UPDATE users SET fake_status = '(ФЕЙК ❌)', is_verified=0 WHERE user_id = ?", (uid,))
            await call.message.answer(f"❌ Користувачу `{uid}` встановлено статус ФЕЙК.")
            try: await bot.send_message(uid, "⚠️ Твоєму профілю надано статус: (ФЕЙК). Можливості обмежені.")
            except: pass
        await db.commit()
    await call.message.delete()
    await send_user_page(call.message.chat.id, page=page, edit=False)
    await call.answer()

# --- ОБРОБКА РІШЕНЬ ПЕРЕВІРКИ ФЕЙКІВ ---
@dp.callback_query(F.data.startswith("man_"))
async def manual_check_decision(call: CallbackQuery):
    _, decision, uid = call.data.split("_")
    uid = int(uid)
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        if decision == "confirm":
            await db.execute("UPDATE users SET is_under_check = 0, is_verified = 1, fake_status = '' WHERE user_id = ?", (uid,))
            await call.message.edit_caption(caption="🟢 Перевірка пройдена. Верифіковано.")
            try: await bot.send_message(uid, "🎉 Перевірку пройдено! Твій профіль верифіковано та розблоковано.", reply_markup=get_main_menu())
            except: pass
        elif decision == "fake":
            await db.execute("UPDATE users SET is_under_check = 0, is_verified = 0, fake_status = '(ФЕЙК ❌)' WHERE user_id = ?", (uid,))
            await call.message.edit_caption(caption="❌ Заявку відхилено. Видано мітку ФЕЙК.")
            try: await bot.send_message(uid, "⚠️ Тобі відмовлено у верифікації. Профіль отримав плашку (ФЕЙК).", reply_markup=get_main_menu())
            except: pass
        await db.commit()
    await call.answer()

# --- СУПЕР АДМІН-ПАНЕЛЬ ---
async def get_stats_text():
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c1: total = (await c1.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_active = 1") as c2: active = (await c2.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1") as c3: banned = (await c3.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_verified = 1") as c4: verified = (await c4.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM ads") as c5: ads_count = (await c5.fetchone())[0]
    return (
        f"📊 **АДМІН-ЦЕНТР**\n━━━━━━━━━━━━━\n"
        f"👥 Всього анкет: **{total}**\n🟢 В пошуку: **{active}**\n"
        f"☑️ Галочка: **{verified}**\n🔴 В бані: **{banned}**\n"
        f"📢 Оголошень: **{ads_count}**\n━━━━━━━━━━━━━\n"
        f"• `/ban ID/@username` | `/unban ID/@username`\n"
        f"• Книга учасників: `/list`"
    )

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    stats_text = await get_stats_text()
    await message.answer(stats_text, parse_mode="Markdown", reply_markup=get_admin_inline_menu())

@dp.callback_query(F.data == "admin_stats_refresh")
async def admin_refresh_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    text = await get_stats_text()
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_admin_inline_menu())
    await callback.answer("Оновлено!")

@dp.callback_query(F.data == "admin_broadcast_start")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("✍️ Введіть текст розсилки:")
    await state.set_state(AdminStates.broadcast_text)
    await callback.answer()

@dp.message(AdminStates.broadcast_text)
async def admin_broadcast_send(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    broadcast_msg = message.text
    await state.clear()
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT user_id FROM users WHERE is_banned = 0") as cursor: users = await cursor.fetchall()
    await message.answer(f"⏳ Починаю розсилку для {len(users)} людей...")
    success = 0
    for row in users:
        try:
            await bot.send_message(row['user_id'], broadcast_msg, parse_mode="Markdown")
            success += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ Доставлено: {success}/{len(users)}")

@dp.message(Command("ban"))
async def cmd_ban(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 2: return
    target = args[1].replace("@", "")
    
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        await db.execute("UPDATE users SET is_banned = 1, is_active = 0 WHERE user_id = ? OR username = ?", (target, target))
        await db.commit()
    await message.answer(f"🔴 Користувач {target} забанений.")

@dp.message(Command("unban"))
async def cmd_unban(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 2: return
    target = args[1].replace("@", "")
    
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        await db.execute("UPDATE users SET is_banned = 0, is_active = 1 WHERE user_id = ? OR username = ?", (target, target))
        await db.commit()
    await message.answer(f"🟢 Користувач {target} розбанений.")

# --- ТРЕНДОВІ ІДЕЇ ТА ТОП-5 ---
@dp.message(F.text == "🏆 ТОП-5 Борислава")
async def top_profiles(message: types.Message):
    if await check_user_status(message): return
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        db.row_factory = aiosqlite.Row
        query = (
            "SELECT users.name, users.location, users.is_verified, users.fake_status, COUNT(actions.id) as likes_count "
            "FROM users LEFT JOIN actions ON users.user_id = actions.to_id AND actions.action = 'like' "
            "WHERE users.is_banned = 0 AND users.in_top = 1 GROUP BY users.user_id "
            "ORDER BY likes_count DESC, users.name ASC LIMIT 5"
        )
        async with db.execute(query) as cursor: rows = await cursor.fetchall()
    text = "🏆 **...ТОП-5 найпопулярніших анкет Борислава...** 🏆\n━━━━━━━━━━━━━━━━━━━━\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for idx, row in enumerate(rows):
        v_mark = f" {row['fake_status']}" if row['fake_status'] else (" ☑️" if row['is_verified'] else "")
        text += f"{medals[idx]} **{row['name']}**{v_mark} (р-н {row['location']}) — ❤️ {row['likes_count']}\n"
    if not rows: text += "Рейтинг формується..."
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🎫 Ідея для побачення")
async def date_idea_cmd(message: types.Message):
    if await check_user_status(message): return
    idea = random.choice(DATE_IDEAS)
    await message.answer(f"💡 **Нова ідея для тебе:**\n\n{idea}")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
