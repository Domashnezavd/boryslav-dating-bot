from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Головне меню бота
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❤️ Дивитись анкети"), KeyboardButton(text="🎲 Анонімна рулетка")],
            [KeyboardButton(text="⚡ Побачення наосліп"), KeyboardButton(text="📢 Стрічка оголошень")],
            [KeyboardButton(text="🎫 Ідея для побачення"), KeyboardButton(text="🏆 ТОП-5 Борислава")],
            [KeyboardButton(text="👤 Моя анкета"), KeyboardButton(text="☑️ Пройти верифікацію")]
        ],
        resize_keyboard=True
    )

# Вибір локації при реєстрації
def get_location_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Борислав (Центр)"), KeyboardButton(text="Борислав (Баня/Губичі)")],
            [KeyboardButton(text="Трускавець"), KeyboardButton(text="Дрогобич")],
            [KeyboardButton(text="Східниця")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# Вибір статі
def get_gender_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Я Хлопець 👨"), KeyboardButton(text="Я Дівчина 👩")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# Кнопки під анкетами для лайків/дизлайків та скарг
def get_profile_action_keyboard(target_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ Дизлайк", callback_data=f"vote_dislike_{target_id}"),
                InlineKeyboardButton(text="❤️ Лайк", callback_data=f"vote_like_{target_id}")
            ],
            [
                InlineKeyboardButton(text="⚠️ Поскаржитись (Жалоба)", callback_data=f"report_start_{target_id}")
            ]
        ]
    )

# Меню для анонімної чат-рулетки
def get_roulette_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎲 Почати гру"), KeyboardButton(text="🛑 Вийти з чату")],
            [KeyboardButton(text="✨ Розігрів (Міні-гра)")]
        ],
        resize_keyboard=True
    )

# Вибір міні-гри в рулетці
def get_games_choice_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🤐 Правда чи Дія", callback_data="game_select_truth")],
            [InlineKeyboardButton(text="🤔 Що б ти обрав?", callback_data="game_select_rather")]
        ]
    )
