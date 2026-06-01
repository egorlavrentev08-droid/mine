"""
Вечный Майнинг Бот для Telegram
Главный файл приложения
Версия: 2.0 (с системой сложностей)
"""

import asyncio
import logging
import random
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
import core as game
from ai import ai_generator

# ========== КОНФИГУРАЦИЯ ==========
TOKEN = "8957174394:AAHWE4Ku1Y1XPLqj86TKBnZA783N7QrxGIM"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Хранилище состояний пользователей
user_states = {}

# ========== КЛАВИАТУРЫ ==========

# Главное меню
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

def get_farms_control_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура управления фермами"""
    builder = InlineKeyboardBuilder()
    
    for currency in ['RUB', 'USD', 'EUR', 'BTC']:
        farm = db.get_passive_farm(user_id, currency)
        if farm and farm['is_active']:
            status = "🟢"
            action = "⏸ Выключить"
        else:
            status = "🔴"
            action = "▶️ Включить"
        
        builder.add(InlineKeyboardButton(
            text=f"{status} {currency} - {action}",
            callback_data=f"toggle_{currency}"
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
        InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_farms")
    )
    
    return builder.as_markup()

def get_upgrade_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для апгрейда ферм"""
    builder = InlineKeyboardBuilder()
    
    for currency in ['RUB', 'USD', 'EUR', 'BTC']:
        farm = db.get_passive_farm(user_id, currency)
        if farm:
            level = farm['upgrade_level']
            cost = int(500 * level)
            builder.add(InlineKeyboardButton(
                text=f"⬆️ {currency} (ур.{level}→{level+1}) - {cost:,} {currency}",
                callback_data=f"upgrade_{currency}"
            ))
    
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Назад к фермам", callback_data="back_to_farms"))
    
    return builder.as_markup()

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
            keyboard.append(row[:2])
    
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

def get_personality_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора стиля AI"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🤗 Дружелюбный", callback_data="ai_personality_friendly"),
            InlineKeyboardButton(text="💼 Деловой", callback_data="ai_personality_business")
        ],
        [
            InlineKeyboardButton(text="😏 Саркастичный", callback_data="ai_personality_sarcastic"),
            InlineKeyboardButton(text="💪 Мотивирующий", callback_data="ai_personality_motivating")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="ai_settings_back")]
    ])

def get_complexity_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора сложности"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Лёгкая", callback_data="set_complexity_easy")],
        [InlineKeyboardButton(text="🟡 Нормальная", callback_data="set_complexity_normal")],
        [InlineKeyboardButton(text="🟠 Сложная", callback_data="set_complexity_hard")],
        [InlineKeyboardButton(text="🔴 Профессионал", callback_data="set_complexity_pro")],
        [InlineKeyboardButton(text="ℹ️ Подробнее", callback_data="complexity_info")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")]
    ])

# ========== ОСНОВНЫЕ КОМАНДЫ ==========

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    db.init_db()
    user_data = db.get_user(user_id)
    
    ai_greeting = ai_generator.generate_phrase(
        user_id, "greeting",
        name=user_name,
        farms_count=len(db.get_active_farms(user_id))
    )
    
    welcome_text = f"""
🌟 *Добро пожаловать в Вечный Майнинг Бот!*

👋 *Привет, {user_name}!*

💰 *Ваш стартовый капитал:* 10 000 RUB
💡 *Остальные валюты (USD, EUR, BTC)* можно получить через обмен!

🎯 *Как начать:*
1️⃣ Включите RUB ферму в разделе «⚙️ Мои фермы»
2️⃣ Начните получать пассивный доход
3️⃣ Обменяйте рубли на другие валюты в «💱 Обмен валют»
4️⃣ Включите фермы для других валют
5️⃣ Проходите бухгалтерию для увеличения дохода

⚡ *Важно:* Доход начисляется в реальном времени!
"""
    
    if ai_greeting:
        welcome_text = f"*{ai_greeting}*\n\n{welcome_text}"
    
    await message.answer(welcome_text, reply_markup=main_keyboard, parse_mode="Markdown")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = """
📚 *Помощь по боту*

*Основные функции:*
🏦 *Мой счёт* - просмотр баланса
⚙️ *Мои фермы* - управление фермами
📚 *Бухгалтерия* - ежедневные задачи
📈 *Статистика* - статистика и рекомендации
💱 *Обмен валют* - конвертация валют
🎯 *Сложность* - выбор уровня сложности
🤖 *Настройки AI* - настройка бота

*Команды:*
/start - главное меню
/help - это сообщение
/cancel - отмена действия
"""
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_states:
        del user_states[user_id]
        await message.answer("❌ Действие отменено.", reply_markup=main_keyboard)
    else:
        await message.answer("Нет активных действий.", reply_markup=main_keyboard)

# ========== ОСНОВНЫЕ КНОПКИ МЕНЮ ==========

@dp.message(F.text == "🏦 Мой счёт")
async def show_balance(message: types.Message):
    user_id = message.from_user.id
    user_data = db.get_user(user_id)
    rates = db.get_exchange_rates()
    
    balance_text = game.format_balance(user_data, rates)
    
    if random.random() < 0.3:
        advice = ai_generator.get_random_advice(
            user_id,
            name=message.from_user.first_name,
            currency=random.choice(["рублях", "долларах", "евро", "биткоинах"])
        )
        if advice:
            balance_text += f"\n\n💡 *Совет:* {advice}"
    
    await message.answer(balance_text, parse_mode="Markdown", reply_markup=main_keyboard)

@dp.message(F.text == "⚙️ Мои фермы")
async def show_farms(message: types.Message):
    user_id = message.from_user.id
    user_data = db.get_user(user_id)
    complexity = db.get_user_complexity(user_id)
    
    text = f"⚙️ *Управление вечными фермами*\n"
    text += f"🎯 Сложность: *{db.COMPLEXITY_LEVELS[complexity]['name']}*\n\n"
    
    for currency in ['RUB', 'USD', 'EUR', 'BTC']:
        farm = db.get_passive_farm(user_id, currency)
        if farm:
            status = "🟢 РАБОТАЕТ" if farm['is_active'] else "🔴 ОСТАНОВЛЕНА"
            balance = user_data[currency.lower()]
            hourly_income = balance * (farm['rate_per_hour'] / 100)
            
            text += f"""
*{currency}*
├ Статус: {status}
├ Ставка: {farm['rate_per_hour']}%/час
├ Уровень: {farm['upgrade_level']}
├ Баланс: {balance:,.2f} {currency}
└ Доход/час: +{hourly_income:.2f} {currency}

"""
    
    text += "💡 *Нажмите на кнопки ниже для управления фермами*"
    
    await message.answer(text, parse_mode="Markdown", reply_markup=get_farms_control_keyboard(user_id))

@dp.message(F.text == "📚 Бухгалтерия")
async def start_accounting(message: types.Message):
    user_id = message.from_user.id
    user_data = db.get_user(user_id)
    
    if not db.set_daily_check(user_id):
        multiplier = db.get_daily_multiplier(user_id)
        await message.answer(
            f"✅ *Вы уже прошли бухгалтерию сегодня!*\n\n"
            f"🎁 Множитель: x{multiplier}\n"
            f"📅 Streak: {user_data['auditor_streak']} дней\n\n"
            f"Возвращайтесь завтра!",
            parse_mode="Markdown",
            reply_markup=main_keyboard
        )
        return
    
    task_text, options, correct, tolerance = game.generate_accounting_task(user_data, user_id)
    
    user_states[user_id] = {
        'type': 'accounting',
        'correct': correct,
        'tolerance': tolerance
    }
    
    builder = InlineKeyboardBuilder()
    for opt_text, opt_value in options.items():
        builder.add(InlineKeyboardButton(text=opt_text, callback_data=f"answer_{opt_value}"))
    builder.adjust(2)
    
    await message.answer(task_text, parse_mode="Markdown", reply_markup=builder.as_markup())

@dp.message(F.text == "📈 Статистика")
async def show_stats(message: types.Message):
    user_id = message.from_user.id
    user_data = db.get_user(user_id)
    rates = db.get_exchange_rates()
    
    multiplier = db.get_daily_multiplier(user_id)
    complexity = db.get_user_complexity(user_id)
    recommendation = game.get_investment_recommendation(user_data, rates)
    
    farms_info = ""
    total_hourly = 0
    for currency in ['RUB', 'USD', 'EUR', 'BTC']:
        farm = db.get_passive_farm(user_id, currency)
        if farm:
            status = "✅" if farm['is_active'] else "⏸"
            balance = user_data[currency.lower()]
            hourly = balance * (farm['rate_per_hour'] / 100)
            total_hourly += hourly
            farms_info += f"\n{status} {currency}: ур.{farm['upgrade_level']} | +{hourly:.2f}/час"
    
    stats_text = f"""
📊 *Ваша статистика*

👤 *Профиль:*
├ Сложность: {db.COMPLEXITY_LEVELS[complexity]['name']}
├ Streak: {user_data['auditor_streak']} дней
├ Множитель: x{multiplier}
└ Сборов: {user_data['total_collected']}

⚙️ *Фермы:*{farms_info}

💰 *Общий доход:* +{total_hourly:.2f}/час

📈 *Рекомендации:*
{recommendation}
"""
    await message.answer(stats_text, parse_mode="Markdown", reply_markup=main_keyboard)

@dp.message(F.text == "💱 Обмен валют")
async def exchange_menu(message: types.Message):
    rates = db.get_exchange_rates()
    
    text = "💱 *Обмен валют*\n\n"
    text += "*Курсы (к RUB):*\n"
    text += f"├ USD: {rates['USD']:,.2f} ₽\n"
    text += f"├ EUR: {rates['EUR']:,.2f} ₽\n"
    text += f"└ BTC: {rates['BTC']:,.2f} ₽\n\n"
    text += "Выберите направление обмена:"
    
    await message.answer(text, parse_mode="Markdown", reply_markup=get_exchange_keyboard())

@dp.message(F.text == "🎯 Сложность")
async def complexity_menu(message: types.Message):
    user_id = message.from_user.id
    current = db.get_user_complexity(user_id)
    
    text = f"""
🎯 *Настройка сложности*

*Текущая:* {db.COMPLEXITY_LEVELS[current]['name']}
*Множитель:* x{db.COMPLEXITY_LEVELS[current]['income_multiplier']}
*Погрешность:* {db.COMPLEXITY_LEVELS[current]['tolerance']}%

Выберите новый уровень:
"""
    await message.answer(text, parse_mode="Markdown", reply_markup=get_complexity_keyboard())

@dp.message(F.text == "🤖 Настройки AI")
async def ai_settings(message: types.Message):
    user_id = message.from_user.id
    text = ai_generator.format_ai_settings_text(user_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔘 Вкл/Выкл", callback_data="ai_toggle"),
         InlineKeyboardButton(text="✏️ Сменить имя", callback_data="ai_change_name")],
        [InlineKeyboardButton(text="🎭 Стиль", callback_data="ai_change_personality"),
         InlineKeyboardButton(text="📊 Частота", callback_data="ai_change_frequency")],
        [InlineKeyboardButton(text="ℹ️ Тест", callback_data="ai_test"),
         InlineKeyboardButton(text="🔄 Сброс", callback_data="ai_reset")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)

# ========== CALLBACK ОБРАБОТЧИКИ ФЕРМ ==========

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("🏠 Главное меню:", reply_markup=main_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "refresh_farms")
async def refresh_farms(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = db.get_user(user_id)
    complexity = db.get_user_complexity(user_id)
    
    text = f"⚙️ *Управление вечными фермами*\n"
    text += f"🎯 Сложность: *{db.COMPLEXITY_LEVELS[complexity]['name']}*\n\n"
    
    for currency in ['RUB', 'USD', 'EUR', 'BTC']:
        farm = db.get_passive_farm(user_id, currency)
        if farm:
            status = "🟢 РАБОТАЕТ" if farm['is_active'] else "🔴 ОСТАНОВЛЕНА"
            balance = user_data[currency.lower()]
            hourly_income = balance * (farm['rate_per_hour'] / 100)
            
            text += f"""
*{currency}*
├ Статус: {status}
├ Ставка: {farm['rate_per_hour']}%/час
├ Уровень: {farm['upgrade_level']}
├ Баланс: {balance:,.2f} {currency}
└ Доход/час: +{hourly_income:.2f} {currency}

"""
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_farms_control_keyboard(user_id))
    await callback.answer()

@dp.callback_query(F.data.startswith("toggle_"))
async def toggle_farm(callback: CallbackQuery):
    currency = callback.data.split("_")[1]
    user_id = callback.from_user.id
    user_name = callback.from_user.first_name
    
    farm = db.get_passive_farm(user_id, currency)
    
    if farm['is_active']:
        profit = db.collect_passive_income(user_id, currency)
        db.toggle_passive_farm(user_id, currency, False)
        msg = f"⏸ *Ферма {currency} остановлена*\n"
        if profit > 0:
            msg += f"💰 Последний доход: +{profit:,.2f} {currency}"
    else:
        db.toggle_passive_farm(user_id, currency, True)
        msg = f"🟢 *Ферма {currency} запущена!*\n├ Ставка: {farm['rate_per_hour']}%/час\n└ Уровень: {farm['upgrade_level']}\n\n⚡ Работает 24/7!"
        
        ai_comment = ai_generator.generate_phrase(
            user_id, "farm_start",
            name=user_name,
            currency=currency,
            rate=farm['rate_per_hour']
        )
        if ai_comment:
            msg += f"\n\n💬 {ai_comment}"
    
    await callback.message.edit_text(msg, parse_mode="Markdown", reply_markup=get_farms_control_keyboard(user_id))
    await callback.answer()

@dp.callback_query(F.data == "collect_all")
async def collect_all(callback: CallbackQuery):
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
        text = f"💰 *Собрано пассивного дохода:*\n" + "\n".join(profits) + f"\n└ 💵 *Всего:* {total_profit:,.2f}"
        
        ai_comment = ai_generator.generate_phrase(
            user_id, "collect",
            name=user_name,
            profit=round(total_profit, 2),
            currency="валют"
        )
        if ai_comment:
            text += f"\n\n💬 {ai_comment}"
        
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_farms_control_keyboard(user_id))
    else:
        await callback.answer("⏰ Нет дохода для сбора! Подождите час.", show_alert=True)

@dp.callback_query(F.data == "upgrade_menu")
async def show_upgrade_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    await callback.message.edit_text(
        "⬆️ *Апгрейд ферм*\n\n"
        "Повышение уровня увеличивает доход на 10%\n"
        "и базовую ставку на +0.5%/час\n\n"
        "Выберите ферму для улучшения:",
        parse_mode="Markdown",
        reply_markup=get_upgrade_keyboard(user_id)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("upgrade_"))
async def upgrade_farm(callback: CallbackQuery):
    currency = callback.data.split("_")[1]
    user_id = callback.from_user.id
    user_name = callback.from_user.first_name
    
    success = db.upgrade_passive_farm(user_id, currency)
    
    if success:
        farm = db.get_passive_farm(user_id, currency)
        text = f"✅ *Апгрейд успешен!*\n\n├ Валюта: {currency}\n├ Новый уровень: {farm['upgrade_level']}\n├ Новая ставка: {farm['rate_per_hour']}%/час\n└ Доход увеличен на 10%!"
        
        ai_comment = ai_generator.generate_phrase(
            user_id, "upgrade",
            name=user_name,
            currency=currency,
            level=farm['upgrade_level']
        )
        if ai_comment:
            text += f"\n\n💬 {ai_comment}"
        
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_upgrade_keyboard(user_id))
    else:
        farm = db.get_passive_farm(user_id, currency)
        level = farm['upgrade_level']
        cost = int(500 * level)
        await callback.answer(f"❌ Недостаточно {currency}! Нужно {cost:,} {currency}", show_alert=True)

@dp.callback_query(F.data == "farm_stats")
async def farm_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = db.get_user(user_id)
    
    text = "📊 *Детальная статистика ферм*\n\n"
    
    for currency in ['RUB', 'USD', 'EUR', 'BTC']:
        farm = db.get_passive_farm(user_id, currency)
        if farm:
            balance = user_data[currency.lower()]
            hourly = balance * (farm['rate_per_hour'] / 100)
            daily = hourly * 24
            monthly = daily * 30
            
            text += f"""
*{currency}:*
├ Баланс: {balance:,.2f} {currency}
├ Статус: {'🟢 Активна' if farm['is_active'] else '🔴 Неактивна'}
├ Уровень: {farm['upgrade_level']}
├ Ставка: {farm['rate_per_hour']}%/час
├ Доход/час: {hourly:,.2f} {currency}
├ Доход/день: {daily:,.2f} {currency}
└ Доход/месяц: {monthly:,.2f} {currency}

"""
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_farms_control_keyboard(user_id))
    await callback.answer()

@dp.callback_query(F.data == "back_to_farms")
async def back_to_farms(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = db.get_user(user_id)
    complexity = db.get_user_complexity(user_id)
    
    text = f"⚙️ *Управление вечными фермами*\n"
    text += f"🎯 Сложность: *{db.COMPLEXITY_LEVELS[complexity]['name']}*\n\n"
    
    for currency in ['RUB', 'USD', 'EUR', 'BTC']:
        farm = db.get_passive_farm(user_id, currency)
        if farm:
            status = "🟢 РАБОТАЕТ" if farm['is_active'] else "🔴 ОСТАНОВЛЕНА"
            balance = user_data[currency.lower()]
            hourly_income = balance * (farm['rate_per_hour'] / 100)
            
            text += f"""
*{currency}*
├ Статус: {status}
├ Ставка: {farm['rate_per_hour']}%/час
├ Уровень: {farm['upgrade_level']}
├ Баланс: {balance:,.2f} {currency}
└ Доход/час: +{hourly_income:.2f} {currency}

"""
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_farms_control_keyboard(user_id))
    await callback.answer()

# ========== CALLBACK ОБРАБОТЧИКИ БУХГАЛТЕРИИ ==========

@dp.callback_query(F.data.startswith("answer_"))
async def check_accounting(callback: CallbackQuery):
    user_id = callback.from_user.id
    state = user_states.get(user_id)
    
    if not state or state.get('type') != 'accounting':
        await callback.answer("⏰ Время истекло. Начните новую задачу.", show_alert=True)
        return
    
    try:
        user_answer = float(callback.data.split("_")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный ответ", show_alert=True)
        return
    
    correct = state['correct']
    tolerance = state['tolerance']
    
    if abs(user_answer - correct) <= tolerance:
        multiplier = db.get_daily_multiplier(user_id)
        streak = db.get_user(user_id)['auditor_streak']
        complexity = db.get_user_complexity(user_id)
        
        text = f"✅ *Правильно!*\n\n├ Ваш ответ: {user_answer:,.2f}\n├ Правильный: {correct:,.2f}\n├ Множитель: x{multiplier}\n├ Streak: {streak} дней\n└ Сложность: {db.COMPLEXITY_LEVELS[complexity]['name']}"
        
        ai_comment = ai_generator.generate_phrase(
            user_id, "accounting_success",
            name=callback.from_user.first_name,
            multiplier=multiplier,
            streak=streak
        )
        if ai_comment:
            text += f"\n\n💬 {ai_comment}"
        
        await callback.message.edit_text(text, parse_mode="Markdown")
    else:
        complexity = db.get_user_complexity(user_id)
        
        if complexity in ['hard', 'pro']:
            db.reset_streak(user_id)
            text = f"❌ *Ошибка!*\n\n├ Ваш ответ: {user_answer:,.2f}\n├ Правильный: {correct:,.2f}\n└ Streak сброшен!"
        else:
            text = f"❌ *Неправильно*\n\n├ Ваш ответ: {user_answer:,.2f}\n└ Правильный: {correct:,.2f}\n\nЗавтра новая задача!"
        
        ai_comment = ai_generator.generate_phrase(
            user_id, "accounting_fail",
            name=callback.from_user.first_name,
            complexity=db.COMPLEXITY_LEVELS[complexity]['name']
        )
        if ai_comment:
            text += f"\n\n💬 {ai_comment}"
        
        await callback.message.edit_text(text, parse_mode="Markdown")
    
    if user_id in user_states:
        del user_states[user_id]
    
    await callback.answer()

# ========== CALLBACK ОБРАБОТЧИКИ ОБМЕНА ==========

@dp.callback_query(F.data == "exchange_menu")
async def exchange_menu_callback(callback: CallbackQuery):
    rates = db.get_exchange_rates()
    
    text = "💱 *Обмен валют*\n\n"
    text += "*Курсы (к RUB):*\n"
    text += f"├ USD: {rates['USD']:,.2f} ₽\n"
    text += f"├ EUR: {rates['EUR']:,.2f} ₽\n"
    text += f"└ BTC: {rates['BTC']:,.2f} ₽\n\n"
    text += "Выберите направление:"
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_exchange_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("exchange_"))
async def select_exchange_pair(callback: CallbackQuery):
    parts = callback.data.split("_")
    
    if len(parts) < 3:
        await exchange_menu_callback(callback)
        return
    
    from_cur = parts[1]
    to_cur = parts[2]
    
    user_id = callback.from_user.id
    user_data = db.get_user(user_id)
    balance = user_data[from_cur.lower()]
    
    text = f"💱 *Обмен: {from_cur} → {to_cur}*\n\n"
    text += f"💰 Ваш баланс {from_cur}: *{balance:,.2f}*\n\n"
    text += "Выберите сумму:"
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_exchange_amount_keyboard(from_cur, to_cur))
    await callback.answer()

@dp.callback_query(F.data.startswith("ex_amount_"))
async def exchange_percent(callback: CallbackQuery):
    parts = callback.data.split("_")
    from_cur = parts[2]
    to_cur = parts[3]
    percent = int(parts[4])
    
    user_id = callback.from_user.id
    user_data = db.get_user(user_id)
    balance = user_data[from_cur.lower()]
    amount = balance * percent / 100
    
    result = db.exchange_currency(user_id, from_cur, to_cur, amount)
    
    if result['success']:
        text = f"✅ *Обмен выполнен!*\n\n├ Продано: {result['from_amount']:,.2f} {from_cur}\n├ Куплено: {result['to_amount']:,.2f} {to_cur}\n├ Курс: 1 {from_cur} = {result['rate']:.4f} {to_cur}\n└ Комиссия: {result['fee']:.1f}% ({result['fee_amount']:,.2f} {from_cur})"
        
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_exchange_keyboard())
    else:
        await callback.answer(result['message'], show_alert=True)

@dp.callback_query(F.data.startswith("ex_custom_"))
async def exchange_custom(callback: CallbackQuery):
    parts = callback.data.split("_")
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
        f"Отправьте /cancel для отмены.",
        parse_mode="Markdown"
    )
    await callback.answer()

# ========== CALLBACK ОБРАБОТЧИКИ СЛОЖНОСТИ ==========

@dp.callback_query(F.data.startswith("set_complexity_"))
async def set_complexity(callback: CallbackQuery):
    user_id = callback.from_user.id
    complexity = callback.data.split("_")[2]
    
    if complexity in db.COMPLEXITY_LEVELS:
        db.set_user_complexity(user_id, complexity)
        level_info = db.COMPLEXITY_LEVELS[complexity]
        
        text = f"✅ *Сложность изменена!*\n\n├ Уровень: {level_info['name']}\n├ Множитель: x{level_info['income_multiplier']}\n└ Погрешность: {level_info['tolerance']}%"
        
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_keyboard)
        await callback.answer(f"Сложность: {level_info['name']}")
    else:
        await callback.answer("❌ Некорректная сложность", show_alert=True)

@dp.callback_query(F.data == "complexity_info")
async def complexity_info(callback: CallbackQuery):
    info_text = """
📚 *Уровни сложности*

🟢 *Лёгкая:* простые задачи, погрешность 5%
🟡 *Нормальная:* стандартные задачи, погрешность 2%
🟠 *Сложная:* продвинутые расчёты, погрешность 0.5%
🔴 *Профессионал:* макс. сложность, точность 0%

⚠️ На высокой сложности ошибки сбрасывают Streak!
"""
    await callback.message.edit_text(info_text, parse_mode="Markdown", reply_markup=get_complexity_keyboard())
    await callback.answer()

# ========== CALLBACK ОБРАБОТЧИКИ AI ==========

@dp.callback_query(F.data == "ai_toggle")
async def ai_toggle(callback: CallbackQuery):
    user_id = callback.from_user.id
    settings = ai_generator.get_user_settings(user_id)
    new_status = not settings["ai_enabled"]
    ai_generator.update_setting(user_id, "ai_enabled", new_status)
    await callback.answer(f"🤖 AI {'включен' if new_status else 'выключен'}!")
    await ai_settings(callback.message)
    await callback.message.delete()

@dp.callback_query(F.data == "ai_change_name")
async def ai_change_name(callback: CallbackQuery):
    await callback.message.answer(
        "✏️ *Введите новое имя бота*\n\n/cancel для отмены.",
        parse_mode="Markdown"
    )
    user_states[callback.from_user.id] = "waiting_ai_name"
    await callback.answer()

@dp.callback_query(F.data == "ai_change_personality")
async def ai_change_personality(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎭 *Выберите стиль общения:*",
        parse_mode="Markdown",
        reply_markup=get_personality_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("ai_personality_"))
async def set_personality(callback: CallbackQuery):
    user_id = callback.from_user.id
    personality = callback.data.split("_")[2]
    ai_generator.update_setting(user_id, "personality", personality)
    await callback.answer("✅ Стиль изменён!")
    await ai_settings(callback.message)
    await callback.message.delete()

@dp.callback_query(F.data == "ai_change_frequency")
async def ai_change_frequency(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="25%", callback_data="ai_freq_25"),
         InlineKeyboardButton(text="50%", callback_data="ai_freq_50")],
        [InlineKeyboardButton(text="75%", callback_data="ai_freq_75"),
         InlineKeyboardButton(text="100%", callback_data="ai_freq_100")],
        [InlineKeyboardButton(text="🔢 Своё", callback_data="ai_freq_custom")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="ai_settings_back")]
    ])
    await callback.message.edit_text("📊 *Частота ответов*", parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("ai_freq_"))
async def set_frequency(callback: CallbackQuery):
    user_id = callback.from_user.id
    freq_value = callback.data.split("_")[2]
    
    if freq_value == "custom":
        await callback.message.answer("🔢 *Введите число от 1 до 100*", parse_mode="Markdown")
        user_states[user_id] = "waiting_ai_freq"
        await callback.answer()
        return
    
    frequency = int(freq_value)
    ai_generator.update_setting(user_id, "response_chance", frequency)
    await callback.answer(f"✅ Частота: {frequency}%")
    await ai_settings(callback.message)
    await callback.message.delete()

@dp.callback_query(F.data == "ai_test")
async def ai_test(callback: CallbackQuery):
    user_id = callback.from_user.id
    test_phrase = ai_generator.generate_phrase(
        user_id, "random_advice",
        name=callback.from_user.first_name,
        currency="инвестициях"
    )
    if test_phrase:
        await callback.message.answer(f"🧪 *Тест:*\n\n{test_phrase}", parse_mode="Markdown")
    else:
        await callback.message.answer("🤖 AI выключен.")
    await callback.answer()

@dp.callback_query(F.data == "ai_reset")
async def ai_reset(callback: CallbackQuery):
    user_id = callback.from_user.id
    ai_generator.reset_user_settings(user_id)
    await callback.answer("✅ Настройки AI сброшены!")
    await ai_settings(callback.message)
    await callback.message.delete()

@dp.callback_query(F.data == "ai_settings_back")
async def ai_back(callback: CallbackQuery):
    await ai_settings(callback.message)
    await callback.message.delete()
    await callback.answer()

# ========== ОБРАБОТЧИКИ ТЕКСТОВОГО ВВОДА ==========

@dp.message(F.text)
async def handle_text_input(message: types.Message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    
    if state == "waiting_ai_name":
        new_name = message.text[:30]
        ai_generator.update_setting(user_id, "bot_name", new_name)
        await message.answer(f"✅ Имя бота: *{new_name}*", parse_mode="Markdown")
        del user_states[user_id]
        await ai_settings(message)
    
    elif state == "waiting_ai_freq":
        try:
            freq = int(message.text)
            if 1 <= freq <= 100:
                ai_generator.update_setting(user_id, "response_chance", freq)
                await message.answer(f"✅ Частота: {freq}%")
            else:
                await message.answer("❌ Число от 1 до 100!")
        except ValueError:
            await message.answer("❌ Введите число!")
        del user_states[user_id]
        await ai_settings(message)
    
    elif isinstance(state, dict) and state.get('type') == 'exchange':
        try:
            amount = float(message.text)
            if amount <= 0:
                await message.answer("❌ Положительная сумма!")
                return
            
            from_cur = state['from_cur']
            to_cur = state['to_cur']
            user_data = db.get_user(user_id)
            
            if user_data[from_cur.lower()] < amount:
                await message.answer(f"❌ Недостаточно {from_cur}!")
                return
            
            result = db.exchange_currency(user_id, from_cur, to_cur, amount)
            
            if result['success']:
                text = f"✅ *Обмен выполнен!*\n\n├ Продано: {result['from_amount']:,.2f} {from_cur}\n├ Куплено: {result['to_amount']:,.2f} {to_cur}\n├ Курс: 1 {from_cur} = {result['rate']:.4f} {to_cur}\n└ Комиссия: {result['fee']:.1f}% ({result['fee_amount']:,.2f} {from_cur})"
                await message.answer(text, parse_mode="Markdown")
            else:
                await message.answer(result['message'])
            
            del user_states[user_id]
            
        except ValueError:
            await message.answer("❌ Введите число!")
    
    else:
        await message.answer(
            "Используйте кнопки меню.\nКоманды: /start, /help, /cancel",
            reply_markup=main_keyboard
        )

# ========== ЗАПУСК БОТА ==========

async def on_startup():
    logger.info("Инициализация базы данных...")
    db.init_db()
    logger.info("✅ База данных готова")
    logger.info("🚀 Бот запущен!")

async def main():
    dp.startup.register(on_startup)
    logger.info("=" * 50)
    logger.info("🚀 Вечный Майнинг Бот v2.0 запускается...")
    logger.info("=" * 50)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
