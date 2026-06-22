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
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

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

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        sql_users = (
            "CREATE TABLE IF NOT EXISTS users ("
            "user_id INTEGER PRIMARY KEY, username TEXT, name TEXT, "
            "age INTEGER, gender TEXT, location TEXT, bio TEXT, "
            "photo TEXT, is_verified INTEGER DEFAULT 0, "
            "is_banned INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1, "
            "in_top INTEGER DEFAULT 1)"
        )
        await db.execute(sql_users)
        
        try:
            await db.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
        except: pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN in_top INTEGER DEFAULT 1")
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
        [KeyboardButton(text="📢 Стрічка оголошень"), KeyboardButton(text="⚡ Побачення наосліп")],
        [KeyboardButton(text="🎫 Ідея для побачення"), KeyboardButton(text="🏆 ТОП-5 Борислава")],
        [KeyboardButton(text="👤 Мій Профіль ✨")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_profile_management_keyboard(is_active, in_top, is_verified):
    active_text = "🟢 Анкета увімкнена (Сховати)" if is_active else "🔴 Анкета вимкнена (Активувати)"
    top_text = "🌟 Сховатись з ТОПу" if in_top else "✨ Показувати в ТОП"
    verify_text = "✅ Ти верифікований" if is_verified else "☑️ Пройти верифікацію"
    buttons = [
        [InlineKeyboardButton(text="📝 Редагувати анкету", callback_data="profile_edit")],
        [InlineKeyboardButton(text=active_text, callback_data="profile_toggle_active")],
        [InlineKeyboardButton(text=top_text, callback_data="profile_toggle_top")]
    ]
    if not is_verified:
        buttons.append([InlineKeyboardButton(text=verify_text, callback_data="profile_verify")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_profile_action_keyboard(target_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{target_id}"), 
         InlineKeyboardButton(text="👎 Дизлайк", callback_data=f"dislike_{target_id}")],
        [InlineKeyboardButton(text="⚠️ Поскаржитись", callback_data=f"report_{target_id}")]
    ])

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
            return await message.answer("❌ Твій профіль заблоковано за порушення правил спільноти.")
        await message.answer(f"✨ Привіт, {user['name']}! Раді бачити тебе в Бориславі знову. 😉", reply_markup=get_main_menu())
    else:
        msg = (
            "👋 Привіт! Ласкаво просимо до інтерактивного простору знайомств Борислава!\n\n"
            "Давай створимо твою круту анкету. Як тебе звати?"
        )
        await message.answer(msg)
        await state.set_state(Registration.name)

@dp.message(Registration.name)
async def reg_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("🔢 Скільки тобі років?")
    await state.set_state(Registration.age)

@dp.message(Registration.age)
async def reg_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("🧮 Введи свій вік цифрами:")
    await state.update_data(age=int(message.text))
    kb = [[KeyboardButton(text="Хлопець 👦"), KeyboardButton(text="Дівчина 👧")]]
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)
    await message.answer("✨ Обери свою стать:", reply_markup=markup)
    await state.set_state(Registration.gender)

@dp.message(Registration.gender)
async def reg_gender(message: types.Message, state: FSMContext):
    gender = "male" if "Хлопець" in message.text else "female"
    await state.update_data(gender=gender)
    kb = [
        [KeyboardButton(text="📍 Центр"), KeyboardButton(text="📍 Баня")],
        [KeyboardButton(text="📍 Мразниця"), KeyboardButton(text="📍 Ґубичі")],
        [KeyboardButton(text="📍 Потік"), KeyboardButton(text="📍 Волянка")],
        [KeyboardButton(text="📍 Тустановичі")],
        [KeyboardButton(text="🌍 Східниця / Трускавець / Дрогобич")]
    ]
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)
    await message.answer("🏡 Обери свій мікрорайон або локацію поруч:", reply_markup=markup)
    await state.set_state(Registration.location)

@dp.message(Registration.location)
async def reg_location(message: types.Message, state: FSMContext):
    loc = message.text.replace("📍 ", "")
    await state.update_data(location=loc)
    await message.answer("📝 Розкажи трохи про себе (твої захоплення, кого шукаєш, чим займаєшся):")
    await state.set_state(Registration.bio)

@dp.message(Registration.bio)
async def reg_bio(message: types.Message, state: FSMContext):
    await state.update_data(bio=message.text)
    await message.answer("📸 Надішли ОДНЕ гарне photo для твоєї картки профілю:")
    await state.set_state(Registration.photo)

@dp.message(Registration.photo, F.photo)
async def reg_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH) as db:
        ins_sql = (
            "INSERT OR REPLACE INTO users (user_id, username, name, age, gender, "
            "location, bio, photo, is_verified, is_banned, is_active, in_top) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT is_verified FROM users WHERE user_id=?), 0), 0, 1, 1)"
        )
        await db.execute(ins_sql, (message.from_user.id, message.from_user.username, data['name'], data['age'], data['gender'], data['location'], data['bio'], photo_id, message.from_user.id))
        await db.commit()
    await message.answer("✨ 🎉 Твоя анкета успішно збережена та активована в пошуку!", reply_markup=get_main_menu())
    await state.clear()

@dp.message(F.text.in_({"👤 Мій Профіль ✨", "👤 Моя анкета"}))
async def my_profile(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
    if user:
        v_status = "⚡ **Верифікований користувач** ☑️" if user['is_verified'] else "❌ Профіль не верифіковано"
        a_status = "🟢 Відображається в пошуку" if user['is_active'] else "🔴 Схована з пошуку"
        t_status = "🌟 Бере участь у ТОПі" if user['in_top'] else "💨 Виключено з ТОП-рейтингу"
        caption = (
            f"👑 ✨ **ТВІЙ ПРОФІЛЬ БОРИСЛАВА** ✨ 👑\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏷 **Ім'я:** {user['name']}, {user['age']} років\n"
            f"📍 **Локація:** район {user['location']}\n"
            f"📝 **Про себе:** {user['bio']}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"ℹ️ **Статуси анкети:**\n"
            f"🔹 Статус: {v_status}\n"
            f"🔹 Пошук: {a_status}\n"
            f"🔹 Рейтинг: {t_status}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚙️ *Керуй своєю анкетою за допомогою кнопок нижче:* "
        )
        await bot.send_photo(user_id, photo=user['photo'], caption=caption, reply_markup=get_profile_management_keyboard(user['is_active'], user['in_top'], user['is_verified']), parse_mode="Markdown")
    else:
        await message.answer("У тебе ще немає анкети. Натисни /start для реєстрації! ✨")

@dp.callback_query(F.data == "profile_edit")
async def edit_profile_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Режим редагування. Напиши своє нове ім'я:")
    await state.set_state(Registration.name)
    await callback.answer()

@dp.callback_query(F.data == "profile_toggle_active")
async def toggle_active_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT is_active FROM users WHERE user_id = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            new_val = 0 if res['is_active'] else 1
        await db.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (new_val, user_id))
        await db.commit()
    await callback.answer("Status updated!")
    await callback.message.delete()
    class FakeMsg:
        def __init__(self, uid): self.from_user = self; self.id = uid
        async def answer(self, text, reply_markup=None): await bot.send_message(user_id, text, reply_markup=reply_markup)
    await my_profile(FakeMsg(user_id))

@dp.callback_query(F.data == "profile_toggle_top")
async def toggle_top_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT in_top FROM users WHERE user_id = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            new_val = 0 if res['in_top'] else 1
        await db.execute("UPDATE users SET in_top = ? WHERE user_id = ?", (new_val, user_id))
        await db.commit()
    await callback.answer("Top status updated!")
    await callback.message.delete()
    class FakeMsg:
        def __init__(self, uid): self.from_user = self; self.id = uid
        async def answer(self, text, reply_markup=None): await bot.send_message(user_id, text, reply_markup=reply_markup)
    await my_profile(FakeMsg(user_id))

@dp.callback_query(F.data == "profile_verify")
async def verify_shortcut(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("📸 Надішли своє селфі для верифікації профілю:")
    await state.set_state(VerifyState.photo)
    await callback.answer()

@dp.message(F.text == "❤️ Дивитись анкети")
async def view_profiles(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sel_sql = (
            "SELECT * FROM users WHERE user_id != ? AND is_banned = 0 AND is_active = 1 "
            "AND user_id NOT IN (SELECT to_id FROM actions WHERE from_id = ?) ORDER BY RANDOM() LIMIT 1"
        )
        async with db.execute(sel_sql, (user_id, user_id)) as cursor:
            target = await cursor.fetchone()
    if not target:
        return await message.answer("🌍 Ти переглянув усі доступні на цей момент анкети! Заходь пізніше.")
    badge = " ☑️ (Перевірений)" if target['is_verified'] else ""
    caption = f"🔥 **Нова анкета з Борислава!**\n\n🏷 **{target['name']}**, {target['age']}{badge}\n📍 **Район:** {target['location']}\n📝 **Про себе:** {target['bio']}"
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
        except: pass
        if action == "like":
            async with db.execute("SELECT id FROM actions WHERE from_id = ? AND to_id = ? AND action = 'like'", (target_id, user_id)) as cursor:
                match = await cursor.fetchone()
            if match:
                async with db.execute("SELECT username, name FROM users WHERE user_id = ?", (user_id,)) as c1: u_user = await c1.fetchone()
                async with db.execute("SELECT username, name FROM users WHERE user_id = ?", (target_id,)) as c2: t_user = await c2.fetchone()
                link_u = f"@{u_user['username']}" if u_user['username'] else f"[Посилання](tg://user?id={user_id})"
                link_t = f"@{t_user['username']}" if t_user['username'] else f"[Посилання](tg://user?id={target_id})"
                await bot.send_message(user_id, f"💖 **ВЗАЄМНА СИМПАТІЯ з {t_user['name']}!**\nПочинайте спілкування прямо зараз: {link_t}", parse_mode="Markdown")
                await bot.send_message(target_id, f"💖 **ВЗАЄМНА СИМПАТІЯ з {u_user['name']}!**\nПочинайте спілкування прямо зараз: {link_u}", parse_mode="Markdown")
        
        next_sql = (
            "SELECT * FROM users WHERE user_id != ? AND is_banned = 0 AND is_active = 1 "
            "AND user_id NOT IN (SELECT to_id FROM actions WHERE from_id = ?) ORDER BY RANDOM() LIMIT 1"
        )
        async with db.execute(next_sql, (user_id, user_id)) as cursor:
            next_t = await cursor.fetchone()
    try: await callback.message.delete()
    except: pass
    if next_t:
        badge = " ☑️" if next_t['is_verified'] else ""
        caption = f"🔥 **Наступна анкета!**\n\n🏷 **{next_t['name']}**, {next_t['age']}{badge}\n📍 **Район:** {next_t['location']}\n📝 **Про себе:** {next_t['bio']}"
        await bot.send_photo(user_id, photo=next_t['photo'], caption=caption, reply_markup=get_profile_action_keyboard(next_t['user_id']), parse_mode="Markdown")
    else:
        await bot.send_message(user_id, "🌍 Це була остання активна анкета! Зазирни пізніше.")
    await callback.answer()

@dp.callback_query(F.data.startswith("report_"))
async def report_user(callback: CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    await callback.message.answer("⚠️ Дякуємо! Скарга надіслана адміністраторам міста на перевірку.")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT name, username FROM users WHERE user_id = ?", (target_id,)) as cursor:
            bad_user = await cursor.fetchone()
    u_name = f"@{bad_user['username']}" if bad_user['username'] else "Немає юзернейма"
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 ЗАБАНЕТИ", callback_data=f"admin_ban_{target_id}")],
        [InlineKeyboardButton(text="✅ Ігнорувати", callback_data="admin_clear")]
    ])
    await bot.send_message(ADMIN_ID, f"🚨 **СКАРГА НА КОРИСТУВАЧА!**\n\n🆔 ID: `{target_id}`\n👤 Ім'я: {bad_user['name']}\n🔗 Юзернейм: {u_name}", reply_markup=admin_kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_ban_"))
async def admin_ban(callback: CallbackQuery):
    target_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned = 1, is_active = 0 WHERE user_id = ?", (target_id,))
        await db.commit()
    await callback.message.edit_text(f"🔴 Користувач `{target_id}` успішно ЗАБАНЕНИЙ та видалений з пошуку.")
    await callback.answer()

@dp.callback_query(F.data == "admin_clear")
async def admin_clear(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()

@dp.message(F.text == "☑️ Пройти верифікацію")
async def verify_start(message: types.Message, state: FSMContext):
    await message.answer("📸 Надішли своє актуальне селфі для верифікації профілю та отримання галочки ☑️:")
    await state.set_state(VerifyState.photo)

@dp.message(VerifyState.photo, F.photo)
async def verify_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await message.answer("⏳ Дякуємо! Фото успішно надіслано модераторам. Очікуй сповіщення!")
    await state.clear()
    username_str = f"@{message.from_user.username}" if message.from_user.username else f"[Посилання](tg://user?id={message.from_user.id})"
    admin_verify_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Підтвердити галочку", callback_data=f"averify_yes_{message.from_user.id}"), InlineKeyboardButton(text="❌ Відхилити запит", callback_data="admin_clear")]])
    await bot.send_photo(ADMIN_ID, photo=photo_id, caption=f"👤 **ЗАПИТ НА ВЕРИФІКАЦІЮ**\n\n🆔 ID: `{message.from_user.id}`\n🔗 Профіль: {username_str}", reply_markup=admin_verify_kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("averify_yes_"))
async def admin_verify_yes(callback: CallbackQuery):
    t_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_verified = 1 WHERE user_id = ?", (t_id,))
        await db.commit()
    await callback.message.reply(f"🟢 Користувач `{t_id}` верифікований.")
    try: await bot.send_message(t_id, "🎉 Вітаємо! Твій профіль успішно верифіковано! Тобі присвоєно офіційну галочку ☑️!")
    except: pass
    await callback.answer()

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c1: total = (await c1.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_active = 1") as c2: active = (await c2.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1") as c3: banned = (await c3.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_verified = 1") as c4: verified = (await c4.fetchone())[0]
    stats_text = f"📊 🛠 **АДМІН-ПАНЕЛЬ БОТА** 🛠 📊\n" f"━━━━━━━━━━━━━━━━━━━━\n" f"👥 Всього користувачів: **{total}**\n" f"🟢 Активні в пошуку: **{active}**\n" f"☑️ Верифіковані: **{verified}**\n" f"🔴 В бані: **{banned}**\n" f"━━━━━━━━━━━━━━━━━━━━"
    await message.answer(stats_text, parse_mode="Markdown")

@dp.message(F.text == "🏆 ТОП-5 Борислава")
async def top_profiles(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = (
            "SELECT users.name, users.location, users.is_verified, COUNT(actions.id) as likes_count "
            "FROM users LEFT JOIN actions ON users.user_id = actions.to_id AND actions.action = 'like' "
            "WHERE users.is_banned = 0 AND users.in_top = 1 GROUP BY users.user_id "
            "ORDER BY likes_count DESC, users.name ASC LIMIT 5"
        )
        async with db.execute(query) as cursor: rows = await cursor.fetchall()
    text = "🏆 **ТОП-5 найпопулярніших анкет Борислава** 🏆\n" "*(Рейтинг оновлюється автоматично в реальному часі)*\n" "━━━━━━━━━━━━━━━━━━━━\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for idx, row in enumerate(rows):
        badge = " ☑️" if row['is_verified'] else ""
        text += f"{medals[idx]} **{row['name']}**{badge} (район {row['location']}) — ❤️ Лайків: {row['likes_count']}\n"
    if not rows: text += "Рейтинг поки формується. Ставте більше лайків! 😉"
    text += "\n━━━━━━━━━━━━━━━━━━━━\n💡 *Ти завжди можеш виключити себе з рейтингу в меню «Мій Профіль ✨».*"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🎲 Анонімна рулетка")
async def start_roulette(message: types.Message):
    user_id = message.from_user.id
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

@dp.message(lambda m: m.from_user.id in ACTIVE_CHATS and not m.text.startswith("/"))
async def echo_chat(message: types.Message):
    try: await bot.send_message(ACTIVE_CHATS[message.from_user.id], f"👤 Анонім: {message.text}")
    except: pass

@dp.message(F.text == "📢 Стрічка оголошень")
async def ads_menu(message: types.Message):
    kb = [[InlineKeyboardButton(text="Переглянути стрічку 📋", callback_data="ads_view"), InlineKeyboardButton(text="Опублікувати оголошення ✍️", callback_data="ads_create")]]
    await message.answer("📰 **Локальна стрічка оголошень м. Борислав**", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "ads_view")
async def view_ads(callback: CallbackQuery):
    day_ago = time.time() - 86400
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT ads.text, users.name FROM ads JOIN users ON ads.user_id = users.user_id WHERE ads.created_at > ? ORDER BY ads.id DESC LIMIT 5", (day_ago,)) as cursor: all_ads = await cursor.fetchall()
    if not all_ads: return await callback.message.answer("Стрічка оголошень поки порожня. Будь першим!")
    text = "📢 **Останні оголошення за 24 години:**\n\n"
    for row in all_ads: text += f"👤 **{row['name']}**: {row['text']}\n———————\n"
    await callback.message.answer(text); await callback.answer()

@dp.callback_query(F.data == "ads_create")
async def create_ad_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Напиши текст свого оголошення (події, барахолка, новини):")
    await state.set_state(AdState.text); await callback.answer()

@dp.message(AdState.text)
async def create_ad_finish(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO ads (user_id, text, created_at) VALUES (?, ?, ?)", (message.from_user.id, message.text, time.time()))
        await db.commit()
    await message.answer("✅ Твоє оголошення додано на 24 години!"); await state.clear()

@dp.message(F.text == "🎫 Ідея для побачення")
async def date_idea_cmd(message: types.Message):
    idea = (
        "Затишне побачення: Прогуляйтеся оновленим міським парком у Бориславі, "
        "візьміть ароматну каву або гарячий шоколад, а потім влаштуйте "
        "вечірню прогулянку вуличками до центру."
    )
    await message.answer(f"💡 **Ідея для ідеального побачення:**\n\n{idea}", parse_mode="Markdown")

@dp.message(F.text == "⚡ Побачення наосліп")
async def speed_date(message: types.Message):
    await message.answer("⚡ **Побачення наосліп**\n\nЦей режим автоматично запускається кожної п'ятниці о 20:00! Готуй круті історії.")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
