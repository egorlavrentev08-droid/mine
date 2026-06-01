"""
Вечный Майнинг Бот для Telegram
Главный файл приложения
Версия: 2.1 (исправленная)
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    CallbackQuery,
    ErrorEvent
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from decimal import Decimal, ROUND_DOWN

import database as db
import core as game
from ai import ai_generator

# ========== КОНФИГУРАЦИЯ ==========
# ЗАМЕНИТЕ НА ТОКЕН ВАШЕГО БОТА!
TOKEN = "8957174394:AAHWE4Ku1Y1XPLqj86TKBnZA783N7QrxGIM"

# ID разрешённого пользователя (только один)
ALLOWED_USER_ID = 6595788533

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Хранилище состояний пользователей (для FSM)
user_states = {}

# ========== ДЕКОРАТОРЫ ОГРАНИЧЕНИЯ ДОСТУПА ==========

def restricted(func):
    """Декоратор для ограничения доступа к message-обработчикам"""
    async def wrapper(message: types.Message, *args, **kwargs):
        if message.from_user.id != ALLOWED_USER_ID:
            await message.answer("🚫 Бот недоступен для Вас.")
            return
        return await func(message, *args, **kwargs)
    return wrapper

def restricted_callback(func):
    """Декоратор для ограничения доступа к callback-обработчикам"""
    async def wrapper(callback: CallbackQuery, *args, **kwargs):
        if callback.from_user.id != ALLOWED_USER_ID:
            await callback.answer("🚫 Бот недоступен для Вас.", show_alert=True)
            return
        return await func(callback, *args, **kwargs)
    return wrapper

# ========== ОБРАБОТЧИК ОШИБОК ==========

@dp.error()
async def error_handler(event: ErrorEvent):
    """Глобальный обработчик ошибок"""
    logger.error(f"Ошибка: {event.exception}")
    
    # Если у сообщения есть chat_id, отправляем уведомление
    try:
        if event.message:
            await event.message.answer(
                "❌ Произошла внутренняя ошибка. Пожалуйста, попробуйте позже."
            )
    except:
        pass

# ========== КЛАВИАТУРА ОБМЕНА ==========

def get_exchange_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора валют для обмена"""
    currencies = ['RUB', 'USD', 'EUR', 'BTC']
    keyboard = []
    
    for from_cur in currencies:
        row = []
        for to_cur in currencies:
            if from_cur != to_cur:
                row.append(InlineKeyboardButton(
                    text=f"{from_cur} → {to_cur}",
                    callback_data=f"exchange_{from_cur}_{to_cur}"
                ))
        if row:
            keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_exchange_amount_keyboard(from_cur: str, to_cur: str) -> InlineKeyboardMarkup:
    """Клавиатура с预设ными суммами для обмена"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="25%", callback_data=f"ex_amount_{from_cur}_{to_cur}_25"),
            InlineKeyboardButton(text="50%", callback_data=f"ex_amount_{from_cur}_{to_cur}_50"),
            InlineKeyboardButton(text="75%", callback_data=f"ex_amount_{from_cur}_{to_cur}_75"),
            InlineKeyboardButton(text="100%", callback_data=f"ex_amount_{from_cur}_{to_cur}_100")
        ],
        [InlineKeyboardButton(text="🔢 Своя сумма", callback_data=f"ex_custom_{from_cur}_{to_cur}")],
        [InlineKeyboardButton(text="🔙 Назад к выбору валют", callback_data="exchange_menu")]
    ])

# ========== ОБРАБОТЧИКИ ОБМЕНА ==========

@dp.message(F.text == "💱 Обмен валют")
@restricted
async def exchange_menu(message: types.Message):
    """Меню обмена валют"""
    user_id = message.from_user.id
    rates = db.get_exchange_rates()
    
    text = "💱 *Обмен валют*\n\n"
    text += "*Текущие курсы (к RUB):*\n"
    text += f"├ USD: {rates['USD']:,.2f} ₽\n"
    text += f"├ EUR: {rates['EUR']:,.2f} ₽\n"
    text += f"└ BTC: {rates['BTC']:,.2f} ₽\n\n"
    text += "*Комиссия (зависит от сложности):*\n"
    
    complexity = db.get_user_complexity(user_id)
    fee = db.COMPLEXITY_LEVELS[complexity]['exchange_fee'] * 100
    text += f"├ Текущая комиссия: {fee:.1f}%\n"
    text += "└ Выше сложность = ниже комиссия!\n\n"
    text += "Выберите направление обмена:"
    
    await message.answer(text, parse_mode="Markdown", reply_markup=get_exchange_keyboard())

@dp.callback_query(F.data.startswith("exchange_"))
@restricted_callback
async def select_exchange_pair(callback: CallbackQuery):
    """Выбор пары валют для обмена"""
    parts = callback.data.split("_")
    
    if len(parts) == 2 and parts[1] == "menu":
        # Вернуться в меню обмена
        await exchange_menu(callback.message)
        await callback.message.delete()
        await callback.answer()
        return
    
    if len(parts) < 3:
        await callback.answer("❌ Неверная команда", show_alert=True)
        return
    
    from_cur = parts[1]
    to_cur = parts[2]
    
    user_id = callback.from_user.id
    user_data = db.get_user(user_id)
    balance = user_data[from_cur.lower()]
    
    text = f"💱 *Обмен: {from_cur} → {to_cur}*\n\n"
    text += f"💰 Ваш баланс {from_cur}: *{balance:,.2f}*\n\n"
    text += "Выберите сумму для обмена\n"
    text += "или введите свою:"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_exchange_amount_keyboard(from_cur, to_cur)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("ex_amount_"))
@restricted_callback
async def exchange_percent(callback: CallbackQuery):
    """Обменять процент от баланса"""
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer("❌ Неверная команда", show_alert=True)
        return
    
    from_cur = parts[2]
    to_cur = parts[3]
    percent = int(parts[4])
    
    user_id = callback.from_user.id
    user_data = db.get_user(user_id)
    balance = user_data[from_cur.lower()]
    
    amount = round(balance * percent / 100, 2)
    
    await execute_exchange(callback, user_id, from_cur, to_cur, amount)

@dp.callback_query(F.data.startswith("ex_custom_"))
@restricted_callback
async def exchange_custom(callback: CallbackQuery):
    """Ввод своей суммы для обмена"""
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Неверная команда", show_alert=True)
        return
    
    from_cur = parts[2]
    to_cur = parts[3]
    
    user_id = callback.from_user.id
    user_states[user_id] = {
        'type': 'exchange',
        'from_cur': from_cur,
        'to_cur': to_cur
    }
    
    await callback.message.answer(
        f"💱 *Введите сумму {from_cur} для обмена на {to_cur}*\n\n"
        f"Пример: 1000\n\n"
        f"Отправьте /cancel для отмены.",
        parse_mode="Markdown"
    )
    await callback.answer()

async def execute_exchange(callback, user_id, from_cur, to_cur, amount):
    """Выполнить обмен валют"""
    result = db.exchange_currency(user_id, from_cur, to_cur, amount)
    
    if result['success']:
        text = f"""
✅ *Обмен выполнен успешно!*

💱 *Детали операции:*
├ Продано: {result['from_amount']:,.2f} {from_cur}
├ Куплено: {result['to_amount']:,.2f} {to_cur}
├ Курс: 1 {from_cur} = {result['rate']:,.4f} {to_cur}
├ Комиссия: {result['fee']}% ({result['fee_amount']:,.2f} {from_cur})
└ Сложность: {db.COMPLEXITY_LEVELS[db.get_user_complexity(user_id)]['name']}

💡 *Совет:* На высокой сложности комиссия ниже!
"""
        
        # AI комментарий
        ai_comment = ai_generator.generate_phrase(
            user_id, "random_advice",
            name=callback.from_user.first_name,
            currency=to_cur
        )
        if ai_comment:
            text += f"\n💬 {ai_comment}"
        
        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Ещё обмен", callback_data="exchange_menu")],
                [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")]
            ])
        )
    else:
        await callback.answer(result['message'], show_alert=True)

@dp.message(F.text.regexp(r'^\d+\.?\d*$'))
@restricted
async def handle_exchange_amount(message: types.Message):
    """Обработка ввода суммы для обмена"""
    user_id = message.from_user.id
    state = user_states.get(user_id)
    
    if not state or state.get('type') != 'exchange':
        return  # Не в режиме обмена
    
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной!")
            return
        
        from_cur = state['from_cur']
        to_cur = state['to_cur']
        
        # Предпросмотр обмена
        preview = db.get_exchange_preview(from_cur, to_cur, amount, user_id)
        
        if preview['success']:
            text = f"""
📋 *Предпросмотр обмена*

💱 {from_cur} → {to_cur}
├ Сумма: {preview['from_amount']:,.2f} {from_cur}
├ Получите: {preview['to_amount']:,.2f} {to_cur}
├ Курс: 1 {from_cur} = {preview['rate']:,.4f} {to_cur}
└ Комиссия: {preview['fee_percent']}% ({preview['fee_amount']:,.2f} {from_cur})

Подтвердите обмен:"""
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"ex_confirm_{from_cur}_{to_cur}_{amount}"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="exchange_menu")
                ]
            ])
            
            await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await message.answer(f"❌ {preview['message']}")
        
        # Очищаем состояние
        if user_id in user_states:
            del user_states[user_id]
        
    except ValueError:
        await message.answer("❌ Введите число!")

@dp.callback_query(F.data.startswith("ex_confirm_"))
@restricted_callback
async def confirm_exchange(callback: CallbackQuery):
    """Подтверждение обмена"""
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer("❌ Неверная команда", show_alert=True)
        return
    
    from_cur = parts[2]
    to_cur = parts[3]
    try:
        amount = float(parts[4])
    except ValueError:
        await callback.answer("❌ Неверная сумма", show_alert=True)
        return
    
    await execute_exchange(callback, callback.from_user.id, from_cur, to_cur, amount)

# ========== КЛАВИАТУРЫ ==========

# Главное меню (обычная клавиатура)
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏦 Мой счёт"), KeyboardButton(text="⚙️ Мои фермы")],
        [KeyboardButton(text="📚 Бухгалтерия"), KeyboardButton(text="📈 Статистика")],
        [KeyboardButton(text="💱 Обмен валют"), KeyboardButton(text="🎯 Сложность")],
        [KeyboardButton(text="🤖 Настройки AI")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие..."
)

def get_farms_control_keyboard(user_id: int):
    """Клавиатура управления фермами"""
    builder = InlineKeyboardBuilder()
    
    active_count = db.get_active_farms_count(user_id)
    
    for currency in ['RUB', 'USD', 'EUR', 'BTC']:
        farm = db.get_passive_farm(user_id, currency)
        if farm and farm['is_active']:
            status = "🟢"
            action = "⏸ Выключить"
            callback_data = f"toggle_{currency}"
        else:
            status = "🔴"
            action = "▶️ Включить"
            # Если уже 2 активные фермы, блокируем включение
            if active_count >= 2 and currency not in db.get_active_farms(user_id):
                action = "🚫 Лимит 2"
                callback_data = "limit_reached"
            else:
                callback_data = f"toggle_{currency}"
        
        builder.add(InlineKeyboardButton(
            text=f"{status} {currency} - {action}",
            callback_data=callback_data
        ))
    
    builder.adjust(1)
    
    builder.row(
        InlineKeyboardButton(text="💰 Собрать всё", callback_data="collect_all"),
        InlineKeyboardButton(text="⬆️ Апгрейд", callback_data="upgrade_menu")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Детальная статистика", callback_data="farm_stats")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Автосбор (6ч)", callback_data="auto_collect_status")
    )
    
    return builder.as_markup()

def get_upgrade_keyboard(user_id: int):
    """Клавиатура для апгрейда ферм"""
    builder = InlineKeyboardBuilder()
    
    for currency in ['RUB', 'USD', 'EUR', 'BTC']:
        farm = db.get_passive_farm(user_id, currency)
        if farm:
            level = farm['upgrade_level']
            complexity = db.get_user_complexity(user_id)
            cost_multiplier = db.COMPLEXITY_LEVELS[complexity]['cost_multiplier']
            cost = int(500 * level * cost_multiplier)
            builder.add(InlineKeyboardButton(
                text=f"⬆️ {currency} (ур.{level}→{level+1}) - {cost:,} {currency}",
                callback_data=f"upgrade_{currency}"
            ))
    
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(text="🔙 Назад к фермам", callback_data="back_to_farms")
    )
    
    return builder.as_markup()

def get_personality_keyboard():
    """Клавиатура выбора стиля AI"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🤗 Дружелюбный", callback_data="ai_personality_friendly"),
            InlineKeyboardButton(text="💼 Деловой", callback_data="ai_personality_business")
        ],
        [
            InlineKeyboardButton(text="😏 Саркастичный", callback_data="ai_personality_sarcastic"),
            InlineKeyboardButton(text="💪 Мотивирующий", callback_data="ai_personality_motivating")
        ],
        [InlineKeyboardButton(text="🔙 Назад к настройкам AI", callback_data="ai_settings_back")]
    ])
    return keyboard

def get_complexity_keyboard():
    """Клавиатура выбора сложности"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🟢 Лёгкая - простые задачи, высокая погрешность", 
            callback_data="set_complexity_easy"
        )],
        [InlineKeyboardButton(
            text="🟡 Нормальная - стандартные задачи, небольшая погрешность", 
            callback_data="set_complexity_normal"
        )],
        [InlineKeyboardButton(
            text="🟠 Сложная - продвинутые расчёты, почти без погрешности", 
            callback_data="set_complexity_hard"
        )],
        [InlineKeyboardButton(
            text="🔴 Профессионал - максимальная сложность и точность", 
            callback_data="set_complexity_pro"
        )],
        [InlineKeyboardButton(text="ℹ️ Подробнее о сложностях", callback_data="complexity_info")]
    ])
    return keyboard

# ========== ОСНОВНЫЕ КОМАНДЫ ==========

@dp.message(Command("start"))
@restricted
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    # Инициализация БД и пользователя
    db.init_db()
    user_data = db.get_user(user_id)
    
    # AI-приветствие
    ai_greeting = ai_generator.generate_phrase(
        user_id, 
        "greeting",
        name=user_name,
        farms_count=len(db.get_active_farms(user_id))
    )
    
    # Приветственное сообщение
    welcome_text = f"""
🌟 *Добро пожаловать в Вечный Майнинг Бот!*

👋 *Привет, {user_name}!*

💰 *Ваш стартовый капитал:* 10 000 RUB
💡 *Остальные валюты (USD, EUR, BTC)* можно получить через обмен!

🎯 *Как начать:*
1️⃣ Включите RUB ферму в разделе «⚙️ Мои фермы»
2️⃣ Начните получать пассивный доход в рублях
3️⃣ Обменяйте рубли на другие валюты в «💱 Обмен валют»
4️⃣ Включите фермы для других валют (максимум 2 активные фермы)
5️⃣ Проходите бухгалтерию для увеличения дохода

⚡ *Важно:* Доход начисляется автоматически каждые 6 часов!
📈 *Совет:* Диверсифицируйте валюты для стабильного роста!

🎯 *Текущая сложность:* {db.COMPLEXITY_LEVELS[db.get_user_complexity(user_id)]['name']}
💰 *Бонус сложности:* x{db.COMPLEXITY_LEVELS[db.get_user_complexity(user_id)]['multiplier']} (чем выше сложность, тем ниже бонус, но меньше комиссия)
"""
    
    if ai_greeting:
        welcome_text = f"*{ai_greeting}*\n\n{welcome_text}"
    
    await message.answer(
        welcome_text, 
        reply_markup=main_keyboard, 
        parse_mode="Markdown"
    )

@dp.message(Command("help"))
@restricted
async def cmd_help(message: types.Message):
    """Обработчик команды /help"""
    help_text = """
📚 *Помощь по боту*

*Основные функции:*
🏦 *Мой счёт* - просмотр баланса всех валют
⚙️ *Мои фермы* - управление пассивными фермами
📚 *Бухгалтерия* - ежедневные задачи для множителя дохода
📈 *Статистика* - ваша статистика и рекомендации
🤖 *Настройки AI* - настройка стиля общения бота
🎯 *Сложность* - выбор уровня сложности задач

*Как зарабатывать:*
1. Включите фермы в разделе "Мои фермы" (максимум 2)
2. Доход начисляется автоматически каждые 6 часов
3. Проходите бухгалтерию каждый день (первые 2 раза засчитываются)
4. Апгрейдите фермы для увеличения дохода

*Команды:*
/start - главное меню
/help - это сообщение
/cancel - отмена текущего действия
"""
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(F.text == "🏦 Мой счёт")
@restricted
async def show_balance(message: types.Message):
    """Показать баланс пользователя"""
    user_id = message.from_user.id
    user_data = db.get_user(user_id)
    rates = db.get_exchange_rates()
    
    balance_text = game.format_balance(user_data, rates)
    
    # Случайный AI-совет (30% шанс)
    if random.random() < 0.3:
        advice = ai_generator.get_random_advice(
            user_id,
            name=message.from_user.first_name,
            currency=random.choice(["рублях", "долларах", "евро", "биткоинах"])
        )
        if advice:
            balance_text += f"\n\n💡 *Совет AI:* {advice}"
    
    await message.answer(
        balance_text, 
        parse_mode="Markdown", 
        reply_markup=main_keyboard
    )

@dp.message(F.text == "⚙️ Мои фермы")
@restricted
async def show_farms(message: types.Message):
    """Показать управление фермами"""
    user_id = message.from_user.id
    user_data = db.get_user(user_id)
    complexity = db.get_user_complexity(user_id)
    active_count = db.get_active_farms_count(user_id)
    
    text = f"⚙️ *Управление вечными фермами*\n"
    text += f"🎯 Сложность: *{db.COMPLEXITY_LEVELS[complexity]['name']}*\n"
    text += f"📊 Активных ферм: *{active_count}/2*\n\n"
    
    for currency in ['RUB', 'USD', 'EUR', 'BTC']:
        farm = db.get_passive_farm(user_id, currency)
        if farm:
            status = "🟢 РАБОТАЕТ" if farm['is_active'] else "🔴 ОСТАНОВЛЕНА"
            hourly_income = user_data[currency.lower()] * (farm['rate_per_hour'] / 100)
            
            # Применяем множитель сложности к отображаемому доходу
            complexity_mult = db.COMPLEXITY_LEVELS[complexity]['income_multiplier']
            effective_income = hourly_income * complexity_mult
            
            text += f"""
*{currency}*
├ Статус: {status}
├ Ставка: {farm['rate_per_hour']}%/час
├ Уровень: {farm['upgrade_level']}
└ Доход: +{effective_income:.2f} {currency}/час

"""
    
    if active_count >= 2:
        text += "⚠️ *Достигнут лимит активных ферм (2).* Чтобы включить новую, выключите одну из активных.\n\n"
    
    text += "💡 *Совет:* Доход начисляется автоматически каждые 6 часов!\n"
    text += "📊 Нажмите «Детальная статистика» для подробной информации."
    
    await message.answer(
        text, 
        parse_mode="Markdown", 
        reply_markup=get_farms_control_keyboard(user_id)
    )

@dp.message(F.text == "📚 Бухгалтерия")
@restricted
async def start_accounting(message: types.Message):
    """Начать ежедневную бухгалтерию"""
    user_id = message.from_user.id
    user_data = db.get_user(user_id)
    
    # Проверяем, можно ли пройти бухгалтерию
    can_do, count = db.can_do_accounting(user_id)
    
    if not can_do:
        multiplier = db.get_daily_multiplier(user_id)
        await message.answer(
            f"✅ *Вы уже прошли бухгалтерию 2 раза сегодня!*\n\n"
            f"🎁 Текущий множитель дохода: x{multiplier}\n"
            f"📅 Streak: {user_data['auditor_streak']} дней\n\n"
            f"Возвращайтесь завтра за новыми задачами!",
            parse_mode="Markdown",
            reply_markup=main_keyboard
        )
        return
    
    # Генерируем задачу с учётом сложности
    task_text, options, correct, tolerance = game.generate_accounting_task(user_data, user_id)
    
    # Сохраняем состояние
    user_states[user_id] = {
        'type': 'accounting',
        'correct': correct,
        'tolerance': tolerance
    }
    
    # Создаём кнопки с вариантами ответов
    builder = InlineKeyboardBuilder()
    for opt_text, opt_value in options.items():
        builder.add(InlineKeyboardButton(
            text=opt_text,
            callback_data=f"answer_{opt_value}"
        ))
    builder.adjust(2)
    
    # Показываем, какая по счёту сегодня задача
    attempt_info = f"(попытка {count+1}/2 сегодня)"
    
    await message.answer(
        f"{task_text}\n\n{attempt_info}",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )

@dp.message(F.text == "📈 Статистика")
@restricted
async def show_stats(message: types.Message):
    """Показать статистику пользователя"""
    user_id = message.from_user.id
    user_data = db.get_user(user_id)
    rates = db.get_exchange_rates()
    
    multiplier = db.get_daily_multiplier(user_id)
    complexity = db.get_user_complexity(user_id)
    recommendation = game.get_investment_recommendation(user_data, rates)
    active_count = db.get_active_farms_count(user_id)
    
    # Информация о фермах
    farms_info = ""
    total_hourly = 0
    for currency in ['RUB', 'USD', 'EUR', 'BTC']:
        farm = db.get_passive_farm(user_id, currency)
        if farm:
            status = "✅" if farm['is_active'] else "⏸"
            hourly = user_data[currency.lower()] * (farm['rate_per_hour'] / 100)
            total_hourly += hourly * rates.get(currency, 1)
            farms_info += f"\n{status} {currency}: ур.{farm['upgrade_level']} | +{hourly:.2f}/час"
    
    # Общий доход в RUB/час
    total_hourly_rub = sum(
        user_data[c.lower()] * (db.get_passive_farm(user_id, c)['rate_per_hour'] / 100) * rates.get(c, 1)
        for c in ['RUB', 'USD', 'EUR', 'BTC']
        if db.get_passive_farm(user_id, c)
    )
    
    stats_text = f"""
📊 *Ваша статистика*

👤 *Профиль:*
├ Уровень сложности: {db.COMPLEXITY_LEVELS[complexity]['name']}
├ Бонус сложности: x{db.COMPLEXITY_LEVELS[complexity]['multiplier']}
├ Streak бухгалтера: {user_data['auditor_streak']} дней
├ Множитель дохода: x{multiplier}
└ Всего сборов: {user_data['total_collected']}

⚙️ *Активные фермы:* {active_count}/2{farms_info}

💰 *Общий доход:* +{total_hourly_rub:,.2f} RUB/час

📈 *Анализ портфеля:*
{recommendation}

💡 *Совет:* Чем выше Streak, тем больше множитель дохода!
"""
    await message.answer(
        stats_text,
        parse_mode="Markdown",
        reply_markup=main_keyboard
    )

# ========== УПРАВЛЕНИЕ ФЕРМАМИ (CALLBACKS) ==========

@dp.callback_query(F.data == "limit_reached")
@restricted_callback
async def limit_reached(callback: CallbackQuery):
    """Уведомление о достижении лимита ферм"""
    await callback.answer("🚫 Достигнут лимит активных ферм (2). Выключите одну, чтобы включить другую.", show_alert=True)

@dp.callback_query(F.data.startswith("toggle_"))
@restricted_callback
async def toggle_farm(callback: CallbackQuery):
    """Включение/выключение фермы"""
    currency = callback.data.split("_")[1]
    user_id = callback.from_user.id
    user_name = callback.from_user.first_name
    
    farm = db.get_passive_farm(user_id, currency)
    active_count = db.get_active_farms_count(user_id)
    
    if farm['is_active']:
        # Собираем доход перед выключением
        profit = db.collect_passive_income(user_id, currency)
        db.toggle_passive_farm(user_id, currency, False)
        
        msg = f"⏸ *Ферма {currency} остановлена*\n"
        if profit > 0:
            msg += f"💰 Последний доход: +{profit:,.2f} {currency}\n"
        msg += f"\nФерма больше не приносит пассивный доход."
    else:
        # Проверяем лимит
        if active_count >= 2:
            await callback.answer("🚫 Достигнут лимит активных ферм (2). Выключите одну, чтобы включить другую.", show_alert=True)
            return
        
        db.toggle_passive_farm(user_id, currency, True)
        
        msg = f"🟢 *Ферма {currency} запущена!*\n"
        msg += f"├ Ставка: {farm['rate_per_hour']}%/час\n"
        msg += f"└ Уровень: {farm['upgrade_level']}\n\n"
        msg += f"Теперь она работает 24/7 и приносит доход каждые 6 часов! ⚡"
        
        # AI-комментарий
        ai_comment = ai_generator.generate_phrase(
            user_id, "farm_start",
            name=user_name,
            currency=currency,
            amount=farm.get('rate_per_hour', 1),
            rate=farm.get('rate_per_hour', 1)
        )
        if ai_comment:
            msg += f"\n\n💬 {ai_comment}"
    
    await callback.message.edit_text(
        msg,
        parse_mode="Markdown",
        reply_markup=get_farms_control_keyboard(user_id)
    )
    await callback.answer()

@dp.callback_query(F.data == "collect_all")
@restricted_callback
async def collect_all(callback: CallbackQuery):
    """Собрать доход со всех ферм"""
    user_id = callback.from_user.id
    user_name = callback.from_user.first_name
    
    total_profit = 0
    profits = []
    
    for currency in ['RUB', 'USD', 'EUR', 'BTC']:
        profit = db.collect_passive_income(user_id, currency)
        if profit > 0:
            total_profit += profit
            profits.append(f"├ {currency}: +{profit:,.2f}")
    
    if profits:
        text = f"💰 *Собрано пассивного дохода:*\n"
        text += "\n".join(profits)
        text += f"\n└ 💵 *Всего:* {total_profit:,.2f}"
        
        # AI-комментарий
        ai_comment = ai_generator.generate_phrase(
            user_id, "collect",
            name=user_name,
            profit=round(total_profit, 2),
            currency="валют"
        )
        if ai_comment:
            text += f"\n\n💬 {ai_comment}"
        
        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_farms_control_keyboard(user_id)
        )
    else:
        await callback.answer(
            "⏰ Нет дохода для сбора! Доход начисляется каждые 6 часов.",
            show_alert=True
        )

@dp.callback_query(F.data == "auto_collect_status")
@restricted_callback
async def auto_collect_status(callback: CallbackQuery):
    """Показать статус автосбора"""
    user_id = callback.from_user.id
    last_collect = db.get_last_auto_collect(user_id)
    now = datetime.now()
    diff = now - last_collect
    hours_until = max(0, 6 - diff.total_seconds() / 3600)
    
    text = f"""
⏰ *Автоматический сбор дохода*

📅 Последний сбор: {last_collect.strftime('%d.%m.%Y %H:%M')}
⏳ До следующего сбора: {hours_until:.1f} часов

💡 Доход начисляется автоматически каждые 6 часов со всех активных ферм.
"""
    
    if hours_until <= 0:
        text += "\n✅ *Сбор доступен!* Нажмите «Собрать всё» для немедленного сбора."
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К фермам", callback_data="back_to_farms")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "upgrade_menu")
@restricted_callback
async def show_upgrade_menu(callback: CallbackQuery):
    """Показать меню апгрейда ферм"""
    user_id = callback.from_user.id
    
    await callback.message.edit_text(
        "⬆️ *Апгрейд ферм*\n\n"
        "Повышение уровня увеличивает доход на 10%\n"
        "и базовую ставку на +0.5%/час\n\n"
        "💡 Чем выше уровень, тем дороже апгрейд\n"
        "💡 Стоимость зависит от сложности\n\n"
        "Выберите ферму для улучшения:",
        parse_mode="Markdown",
        reply_markup=get_upgrade_keyboard(user_id)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("upgrade_"))
@restricted_callback
async def upgrade_farm(callback: CallbackQuery):
    """Апгрейд конкретной фермы"""
    currency = callback.data.split("_")[1]
    user_id = callback.from_user.id
    user_name = callback.from_user.first_name
    
    success = db.upgrade_passive_farm(user_id, currency)
    
    if success:
        farm = db.get_passive_farm(user_id, currency)
        text = (
            f"✅ *Апгрейд успешен!*\n\n"
            f"├ Валюта: {currency}\n"
            f"├ Новый уровень: {farm['upgrade_level']}\n"
            f"├ Новая ставка: {farm['rate_per_hour']}%/час\n"
            f"└ Доход увеличен на 10%!"
        )
        
        # AI-комментарий
        ai_comment = ai_generator.generate_phrase(
            user_id, "upgrade",
            name=user_name,
            currency=currency,
            level=farm['upgrade_level']
        )
        if ai_comment:
            text += f"\n\n💬 {ai_comment}"
        
        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_upgrade_keyboard(user_id)
        )
    else:
        farm = db.get_passive_farm(user_id, currency)
        level = farm['upgrade_level']
        complexity = db.get_user_complexity(user_id)
        cost_multiplier = db.COMPLEXITY_LEVELS[complexity]['cost_multiplier']
        cost = int(500 * level * cost_multiplier)
        await callback.answer(
            f"❌ Недостаточно {currency}! Нужно {cost:,} {currency}",
            show_alert=True
        )

@dp.callback_query(F.data == "farm_stats")
@restricted_callback
async def show_farm_stats(callback: CallbackQuery):
    """Показать детальную статистику по фермам"""
    user_id = callback.from_user.id
    user_data = db.get_user(user_id)
    rates = db.get_exchange_rates()
    
    text = "📊 *Детальная статистика ферм*\n\n"
    
    for currency in ['RUB', 'USD', 'EUR', 'BTC']:
        farm = db.get_passive_farm(user_id, currency)
        if farm:
            balance = user_data[currency.lower()]
            hourly = balance * (farm['rate_per_hour'] / 100)
            daily = hourly * 24
            monthly = daily * 30
            
            text += f"""
*{currency} ферма:*
├ Баланс: {balance:,.2f} {currency}
├ Статус: {'🟢 Активна' if farm['is_active'] else '🔴 Неактивна'}
├ Уровень: {farm['upgrade_level']}
├ Ставка: {farm['rate_per_hour']}%/час
├ Доход/час: {hourly:,.2f} {currency}
├ Доход/день: {daily:,.2f} {currency}
└ Доход/месяц: {monthly:,.2f} {currency}

"""
    
    text += "💡 *Совет:* Апгрейдите фермы для увеличения дохода!"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_farms_control_keyboard(user_id)
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_farms")
@restricted_callback
async def back_to_farms(callback: CallbackQuery):
    """Вернуться к списку ферм"""
    user_id = callback.from_user.id
    
    # Вызываем show_farms, но для callback
    await callback.message.edit_text(
        "⚙️ *Загрузка ферм...*",
        parse_mode="Markdown"
    )
    
    # Повторно показываем фермы
    user_data = db.get_user(user_id)
    complexity = db.get_user_complexity(user_id)
    active_count = db.get_active_farms_count(user_id)
    
    text = f"⚙️ *Управление вечными фермами*\n"
    text += f"🎯 Сложность: *{db.COMPLEXITY_LEVELS[complexity]['name']}*\n"
    text += f"📊 Активных ферм: *{active_count}/2*\n\n"
    
    for currency in ['RUB', 'USD', 'EUR', 'BTC']:
        farm = db.get_passive_farm(user_id, currency)
        if farm:
            status = "🟢 РАБОТАЕТ" if farm['is_active'] else "🔴 ОСТАНОВЛЕНА"
            hourly_income = user_data[currency.lower()] * (farm['rate_per_hour'] / 100)
            text += f"""
*{currency}*
├ Статус: {status}
├ Ставка: {farm['rate_per_hour']}%/час
├ Уровень: {farm['upgrade_level']}
└ Доход: +{hourly_income:.2f} {currency}/час

"""
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_farms_control_keyboard(user_id)
    )
    await callback.answer()

# ========== БУХГАЛТЕРИЯ (CALLBACKS) ==========

@dp.callback_query(F.data.startswith("answer_"))
@restricted_callback
async def check_accounting(callback: CallbackQuery):
    """Проверка ответа на задачу бухгалтерии"""
    user_id = callback.from_user.id
    state = user_states.get(user_id)
    
    if not state or state.get('type') != 'accounting':
        await callback.answer("⏰ Время задачи истекло. Начните новую.", show_alert=True)
        return
    
    try:
        user_answer = float(callback.data.split("_")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный ответ", show_alert=True)
        return
    
    correct = state['correct']
    tolerance = state['tolerance']
    
    if abs(user_answer - correct) <= tolerance:
        # Правильный ответ
        # Отмечаем прохождение
        was_counted = db.mark_accounting_completed(user_id)
        
        multiplier = db.get_daily_multiplier(user_id)
        streak = db.get_user(user_id)['auditor_streak']
        complexity = db.get_user_complexity(user_id)
        
        text = (
            f"✅ *Правильно!*\n\n"
            f"├ Ваш ответ: {user_answer:,.2f}\n"
            f"├ Правильный: {correct:,.2f}\n"
            f"├ Погрешность: ±{tolerance:,.2f}\n"
            f"├ Множитель дохода: x{multiplier}\n"
            f"├ Streak: {streak} дней\n"
            f"└ Сложность: {db.COMPLEXITY_LEVELS[complexity]['name']}"
        )
        
        if was_counted:
            text += f"\n\n✅ *Этот результат засчитан для Streak!*"
        else:
            text += f"\n\nℹ️ *Этот результат НЕ засчитан для Streak (лимит 2 в день).*"
        
        # AI-комментарий об успехе
        ai_comment = ai_generator.generate_phrase(
            user_id, "accounting_success",
            name=callback.from_user.first_name,
            multiplier=multiplier,
            complexity=db.COMPLEXITY_LEVELS[complexity]['name'],
            streak=streak
        )
        if ai_comment:
            text += f"\n\n💬 {ai_comment}"
        
        await callback.message.edit_text(text, parse_mode="Markdown")
    else:
        # Неправильный ответ
        complexity = db.get_user_complexity(user_id)
        
        if complexity in ['hard', 'pro']:
            # Штраф: сброс streak
            db.reset_streak(user_id)
            text = (
                f"❌ *Ошибка!*\n\n"
                f"├ Ваш ответ: {user_answer:,.2f}\n"
                f"├ Правильный: {correct:,.2f}\n"
                f"└ Streak сброшен из-за высокой сложности!"
            )
        else:
            text = (
                f"❌ *Неправильно*\n\n"
                f"├ Ваш ответ: {user_answer:,.2f}\n"
                f"└ Правильный: {correct:,.2f}\n\n"
                f"Не расстраивайтесь, завтра будет новая задача!"
            )
        
        # AI-комментарий о неудаче
        ai_comment = ai_generator.generate_phrase(
            user_id, "accounting_fail",
            name=callback.from_user.first_name,
            complexity=db.COMPLEXITY_LEVELS[complexity]['name']
        )
        if ai_comment:
            text += f"\n\n💬 {ai_comment}"
        
        await callback.message.edit_text(text, parse_mode="Markdown")
    
    # Очищаем состояние
    if user_id in user_states:
        del user_states[user_id]
    
    await callback.answer()

# ========== НАСТРОЙКИ AI ==========

@dp.message(F.text == "🤖 Настройки AI")
@restricted
async def ai_settings(message: types.Message):
    """Меню настроек AI"""
    user_id = message.from_user.id
    text = ai_generator.format_ai_settings_text(user_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔘 Вкл/Выкл AI", callback_data="ai_toggle"),
            InlineKeyboardButton(text="✏️ Сменить имя", callback_data="ai_change_name")
        ],
        [
            InlineKeyboardButton(text="🎭 Стиль общения", callback_data="ai_change_personality"),
            InlineKeyboardButton(text="📊 Частота ответов", callback_data="ai_change_frequency")
        ],
        [
            InlineKeyboardButton(text="ℹ️ Тестовое сообщение", callback_data="ai_test"),
            InlineKeyboardButton(text="🔄 Сброс настроек", callback_data="ai_reset")
        ]
    ])
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "ai_toggle")
@restricted_callback
async def ai_toggle(callback: CallbackQuery):
    """Включение/выключение AI"""
    user_id = callback.from_user.id
    settings = ai_generator.get_user_settings(user_id)
    
    new_status = not settings["ai_enabled"]
    ai_generator.update_setting(user_id, "ai_enabled", new_status)
    
    status_text = "включен" if new_status else "выключен"
    await callback.answer(f"🤖 AI {status_text}!")
    
    # Обновляем сообщение
    await ai_settings(callback.message)
    await callback.message.delete()

@dp.callback_query(F.data == "ai_change_name")
@restricted_callback
async def ai_change_name(callback: CallbackQuery):
    """Запрос на изменение имени AI"""
    await callback.message.answer(
        "✏️ *Введите новое имя для бота*\n\n"
        "Примеры: Финансовый Гуру, Денежный Маг, Капитан Биткоин\n\n"
        "Имя может содержать до 30 символов. Отправьте /cancel для отмены.",
        parse_mode="Markdown"
    )
    user_states[callback.from_user.id] = "waiting_ai_name"
    await callback.answer()

@dp.callback_query(F.data == "ai_change_personality")
@restricted_callback
async def ai_change_personality(callback: CallbackQuery):
    """Меню выбора стиля AI"""
    await callback.message.edit_text(
        "🎭 *Выберите стиль общения AI:*\n\n"
        "• 🤗 *Дружелюбный* — тёплые, неформальные ответы\n"
        "• 💼 *Деловой* — строгий, профессиональный тон\n"
        "• 😏 *Саркастичный* — юмор и лёгкие подколы\n"
        "• 💪 *Мотивирующий* — вдохновляющие фразы\n\n"
        "Стиль можно изменить в любой момент.",
        parse_mode="Markdown",
        reply_markup=get_personality_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("ai_personality_"))
@restricted_callback
async def set_personality(callback: CallbackQuery):
    """Установка стиля AI"""
    user_id = callback.from_user.id
    personality = callback.data.split("_")[2]
    
    if ai_generator.update_setting(user_id, "personality", personality):
        personality_names = {
            "friendly": "🤗 Дружелюбный",
            "business": "💼 Деловой",
            "sarcastic": "😏 Саркастичный",
            "motivating": "💪 Мотивирующий"
        }
        await callback.answer(f"✅ Стиль изменён на {personality_names[personality]}")
        await ai_settings(callback.message)
        await callback.message.delete()
    else:
        await callback.answer("❌ Ошибка при изменении стиля", show_alert=True)

@dp.callback_query(F.data == "ai_change_frequency")
@restricted_callback
async def ai_change_frequency(callback: CallbackQuery):
    """Меню настройки частоты ответов AI"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="25% (редко)", callback_data="ai_freq_25"),
            InlineKeyboardButton(text="50% (средне)", callback_data="ai_freq_50")
        ],
        [
            InlineKeyboardButton(text="75% (часто)", callback_data="ai_freq_75"),
            InlineKeyboardButton(text="100% (всегда)", callback_data="ai_freq_100")
        ],
        [InlineKeyboardButton(text="🔢 Своё значение", callback_data="ai_freq_custom")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="ai_settings_back")]
    ])
    
    await callback.message.edit_text(
        "📊 *Настройка частоты ответов AI*\n\n"
        "Как часто бот будет комментировать ваши действия?\n\n"
        "• 25% — только иногда\n"
        "• 50% — примерно каждый второй раз\n"
        "• 75% — очень часто\n"
        "• 100% — всегда\n"
        "• Своё — любое число от 1 до 100\n\n"
        "💡 Выше частота = более живое общение!",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("ai_freq_"))
@restricted_callback
async def set_frequency(callback: CallbackQuery):
    """Установка частоты ответов AI"""
    user_id = callback.from_user.id
    freq_value = callback.data.split("_")[2]
    
    if freq_value == "custom":
        await callback.message.answer(
            "🔢 *Введите число от 1 до 100*\n\n"
            "Это будет процент ответов на ваши действия.\n"
            "Отправьте /cancel для отмены.",
            parse_mode="Markdown"
        )
        user_states[user_id] = "waiting_ai_freq"
        await callback.answer()
        return
    
    frequency = int(freq_value)
    if ai_generator.update_setting(user_id, "response_chance", frequency):
        await callback.answer(f"✅ Частота ответов: {frequency}%")
        await ai_settings(callback.message)
        await callback.message.delete()
    else:
        await callback.answer("❌ Ошибка при сохранении", show_alert=True)

@dp.callback_query(F.data == "ai_test")
@restricted_callback
async def ai_test(callback: CallbackQuery):
    """Тестовое сообщение AI"""
    user_id = callback.from_user.id
    
    test_phrase = ai_generator.generate_phrase(
        user_id, "random_advice",
        name=callback.from_user.first_name,
        currency=random.choice(["Рубль", "Доллар", "Евро", "Биткоин"])
    )
    
    if test_phrase:
        await callback.message.answer(
            f"🧪 *Тестовое сообщение AI:*\n\n{test_phrase}",
            parse_mode="Markdown"
        )
    else:
        await callback.message.answer(
            "🤖 AI выключен. Включите его в настройках!"
        )
    
    await callback.answer()

@dp.callback_query(F.data == "ai_reset")
@restricted_callback
async def ai_reset(callback: CallbackQuery):
    """Сброс настроек AI"""
    user_id = callback.from_user.id
    ai_generator.reset_user_settings(user_id)
    await callback.answer("✅ Настройки AI сброшены!")
    await ai_settings(callback.message)
    await callback.message.delete()

@dp.callback_query(F.data == "ai_settings_back")
@restricted_callback
async def ai_back(callback: CallbackQuery):
    """Вернуться в настройки AI"""
    await ai_settings(callback.message)
    await callback.message.delete()
    await callback.answer()

# ========== СИСТЕМА СЛОЖНОСТИ ==========

@dp.message(F.text == "🎯 Сложность")
@restricted
async def complexity_menu(message: types.Message):
    """Меню выбора сложности"""
    user_id = message.from_user.id
    current = db.get_user_complexity(user_id)
    
    text = f"""
🎯 *Настройка сложности*

*Текущая сложность:* {db.COMPLEXITY_LEVELS[current]['name']}
*Бонус дохода:* x{db.COMPLEXITY_LEVELS[current]['multiplier']} (чем выше сложность, тем ниже бонус)
*Комиссия обмена:* {db.COMPLEXITY_LEVELS[current]['exchange_fee']*100}% (чем выше сложность, тем ниже комиссия)
*Допустимая погрешность:* {db.COMPLEXITY_LEVELS[current]['tolerance']}%

📊 *Доступные уровни:*
• 🟢 Лёгкая — простые задачи, высокая погрешность (5%)
• 🟡 Нормальная — стандартные задачи, небольшая погрешность (2%)
• 🟠 Сложная — продвинутые расчёты, почти без погрешности (0.5%)
• 🔴 Профессионал — максимальная сложность и точность (0%)

⚠️ *Внимание:* На высокой сложности ошибки в бухгалтерии приводят к сбросу Streak!
"""
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=get_complexity_keyboard()
    )

@dp.callback_query(F.data.startswith("set_complexity_"))
@restricted_callback
async def set_complexity(callback: CallbackQuery):
    """Установка сложности"""
    user_id = callback.from_user.id
    complexity = callback.data.split("_")[2]
    
    if complexity in db.COMPLEXITY_LEVELS:
        db.set_user_complexity(user_id, complexity)
        level_info = db.COMPLEXITY_LEVELS[complexity]
        
        text = (
            f"✅ *Сложность изменена!*\n\n"
            f"├ Уровень: {level_info['name']}\n"
            f"├ Бонус дохода: x{level_info['multiplier']}\n"
            f"├ Комиссия обмена: {level_info['exchange_fee']*100}%\n"
            f"└ Погрешность: {level_info['tolerance']}%\n\n"
            f"Новые задачи будут соответствовать этому уровню."
        )
        
        # AI-комментарий
        ai_comment = ai_generator.generate_phrase(
            user_id, "complexity_change",
            name=callback.from_user.first_name,
            complexity=level_info['name']
        )
        if ai_comment:
            text += f"\n\n💬 {ai_comment}"
        
        await callback.message.edit_text(
            text,
            parse_mode="Markdown"
        )
        await callback.answer(f"Сложность: {level_info['name']}")
    else:
        await callback.answer("❌ Некорректная сложность", show_alert=True)

@dp.callback_query(F.data == "complexity_info")
@restricted_callback
async def complexity_info(callback: CallbackQuery):
    """Подробная информация о сложностях"""
    info_text = """
📚 *Подробнее о сложностях*

🟢 *Лёгкая сложность:*
• Простые задачи (проценты от баланса)
• Погрешность до 5%
• Бонус дохода: x0.8
• Комиссия обмена: 3%
• Без штрафов за ошибки

🟡 *Нормальная сложность:*
• Стандартные задачи с комиссиями
• Погрешность до 2%
• Бонус дохода: x1.0
• Комиссия обмена: 2%
• Без штрафов за ошибки

🟠 *Сложная сложность:*
• Продвинутые расчёты с учётом инфляции
• Погрешность до 0.5%
• Бонус дохода: x0.6
• Комиссия обмена: 1.5%
• Ошибка = сброс Streak

🔴 *Профессионал:*
• Сложные многошаговые задачи
• Погрешность 0% (абсолютная точность)
• Бонус дохода: x0.5
• Комиссия обмена: 1%
• Ошибка = сброс Streak

💡 *Совет:* Начинайте с лёгкой сложности и повышайте по мере освоения!
"""
    await callback.message.edit_text(
        info_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К выбору сложности", callback_data="back_to_complexity")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_complexity")
@restricted_callback
async def back_to_complexity(callback: CallbackQuery):
    """Вернуться к выбору сложности"""
    await complexity_menu(callback.message)
    await callback.message.delete()
    await callback.answer()

# ========== ОБРАБОТКА ПОЛЬЗОВАТЕЛЬСКОГО ВВОДА ==========

@dp.message(Command("cancel"))
@restricted
async def cmd_cancel(message: types.Message):
    """Отмена текущего действия"""
    user_id = message.from_user.id
    if user_id in user_states:
        del user_states[user_id]
        await message.answer("❌ Действие отменено.", reply_markup=main_keyboard)
    else:
        await message.answer("Нет активных действий для отмены.", reply_markup=main_keyboard)

@dp.message(F.text)
@restricted
async def handle_text_input(message: types.Message):
    """Обработка текстового ввода (для настроек AI)"""
    user_id = message.from_user.id
    state = user_states.get(user_id)
    
    if state == "waiting_ai_name":
        # Установка имени AI
        new_name = message.text[:30]  # Ограничение 30 символов
        # Экранируем фигурные скобки в имени
        new_name = new_name.replace("{", "\\{").replace("}", "\\}")
        if ai_generator.update_setting(user_id, "bot_name", new_name):
            await message.answer(
                f"✅ Имя бота изменено на: *{new_name}*",
                parse_mode="Markdown"
            )
        else:
            await message.answer("❌ Ошибка при изменении имени")
        
        del user_states[user_id]
        await ai_settings(message)
    
    elif state == "waiting_ai_freq":
        # Установка частоты ответов AI
        try:
            freq = int(message.text)
            if 1 <= freq <= 100:
                if ai_generator.update_setting(user_id, "response_chance", freq):
                    await message.answer(f"✅ Частота ответов установлена на {freq}%")
                else:
                    await message.answer("❌ Ошибка при сохранении")
            else:
                await message.answer("❌ Число должно быть от 1 до 100!")
        except ValueError:
            await message.answer("❌ Пожалуйста, введите целое число от 1 до 100!")
        
        if user_id in user_states:
            del user_states[user_id]
        await ai_settings(message)
    
    else:
        # Неизвестная команда
        await message.answer(
            "Используйте кнопки меню для навигации.\n"
            "Команды: /start, /help, /cancel",
            reply_markup=main_keyboard
        )

# ========== ФОНОВАЯ ЗАДАЧА ДЛЯ АВТОСБОРА ==========

async def auto_collect_background():
    """Фоновая задача для автоматического сбора дохода каждые 6 часов"""
    while True:
        try:
            # Проверяем всех пользователей
            # В реальности для одного пользователя это избыточно, но оставляем для универсальности
            await asyncio.sleep(3600)  # Проверяем каждый час
            
            # Для одного пользователя просто проверяем
            result = db.check_and_collect_auto(ALLOWED_USER_ID)
            if result:
                logger.info(f"Автосбор выполнен для пользователя {ALLOWED_USER_ID}")
                # Можно отправить уведомление, но пока оставим в логах
                
        except Exception as e:
            logger.error(f"Ошибка в фоновой задаче автосбора: {e}")
            await asyncio.sleep(300)  # При ошибке ждём 5 минут

# ========== ЗАПУСК БОТА ==========

async def on_startup():
    """Действия при запуске бота"""
    logger.info("Инициализация базы данных...")
    db.init_db()
    logger.info("База данных готова")
    
    # Запускаем фоновую задачу
    asyncio.create_task(auto_collect_background())
    logger.info("Фоновая задача автосбора запущена")
    
    logger.info("Бот запущен и готов к работе!")

async def main():
    """Главная функция запуска"""
    # Регистрация действий при старте
    dp.startup.register(on_startup)
    
    logger.info("=" * 50)
    logger.info("🚀 Вечный Майнинг Бот v2.1 запускается...")
    logger.info("📊 Поддерживаемые функции:")
    logger.info("  • Вечные фермы (работают 24/7, максимум 2 активные)")
    logger.info("  • 4 уровня сложности (бонус понижается на высокой сложности)")
    logger.info("  • AI-комментарии с разными стилями")
    logger.info("  • Бухгалтерия (бесконечно, но засчитываются первые 2 раза)")
    logger.info("  • Автосбор дохода каждые 6 часов")
    logger.info("  • Апгрейд ферм")
    logger.info("  • Обмен валют с комиссией от сложности")
    logger.info("  • Настройка AI (имя, стиль, частота)")
    logger.info("=" * 50)
    
    # Запуск polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
