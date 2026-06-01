"""
Вечный Майнинг Бот для Telegram
Модуль игровой логики
Версия: 2.0 (с системой сложностей)
"""

import random
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import database as db

# ========== ФОРМАТИРОВАНИЕ БАЛАНСА ==========

def format_balance(user_data: Dict, rates: Dict) -> str:
    """
    Форматировать баланс пользователя для отображения
    
    Args:
        user_data: данные пользователя из БД
        rates: текущие курсы валют
        
    Returns:
        str: отформатированный текст баланса
    """
    rub = user_data['rub']
    usd = user_data['usd']
    eur = user_data['eur']
    btc = user_data['btc']
    
    # Расчёт общего капитала в разных валютах
    total_rub = rub + usd * rates['USD'] + eur * rates['EUR'] + btc * rates['BTC']
    total_usd = rub / rates['USD'] + usd + eur * rates['EUR'] / rates['USD'] + btc * rates['BTC'] / rates['USD']
    
    # Форматирование чисел
    rub_str = f"{rub:,.2f}".replace(',', ' ')
    usd_str = f"{usd:,.2f}".replace(',', ' ')
    eur_str = f"{eur:,.2f}".replace(',', ' ')
    btc_str = f"{btc:,.6f}"
    total_rub_str = f"{total_rub:,.2f}".replace(',', ' ')
    total_usd_str = f"{total_usd:,.2f}".replace(',', ' ')
    
    # Прогресс-бары (процент от миллиона)
    million = 1_000_000
    rub_percent = min(100, int((rub / million) * 100))
    usd_percent = min(100, int((usd / (million/100)) * 100))
    eur_percent = min(100, int((eur / (million/100)) * 100))
    btc_percent = min(100, int((btc / (million/5_000_000)) * 100))
    
    rub_bar = progress_bar(rub_percent)
    usd_bar = progress_bar(usd_percent)
    eur_bar = progress_bar(eur_percent)
    btc_bar = progress_bar(btc_percent)
    
    text = f"""
🏦 *Ваш счёт*

💰 *Рубли (RUB):*
{rub_bar} {rub_str} ₽

💵 *Доллары (USD):*
{usd_bar} {usd_str} $

💶 *Евро (EUR):*
{eur_bar} {eur_str} €

₿ *Биткоин (BTC):*
{btc_bar} {btc_str} BTC

💎 *Общий капитал:*
{total_rub_str} ₽ (~{total_usd_str} $)

📅 *Дата:* {datetime.now().strftime('%d.%m.%Y')}
🕐 *Время:* {datetime.now().strftime('%H:%M:%S')}
"""
    return text

def progress_bar(percent: int, length: int = 10) -> str:
    """
    Создать текстовый прогресс-бар
    
    Args:
        percent: процент заполнения (0-100)
        length: длина бара в символах
        
    Returns:
        str: прогресс-бар
    """
    filled = int(length * percent / 100)
    empty = length - filled
    
    if percent >= 90:
        bar = '🟩' * filled + '⬜' * empty
    elif percent >= 50:
        bar = '🟨' * filled + '⬜' * empty
    elif percent >= 25:
        bar = '🟧' * filled + '⬜' * empty
    else:
        bar = '🟥' * filled + '⬜' * empty
    
    return bar

# ========== ГЕНЕРАЦИЯ БУХГАЛТЕРСКИХ ЗАДАЧ ==========

def generate_accounting_task(user_data: Dict, user_id: int) -> Tuple[str, Dict, float, float]:
    """
    Сгенерировать задачу по бухгалтерии в зависимости от сложности
    
    Args:
        user_data: данные пользователя
        user_id: ID пользователя (для получения сложности)
        
    Returns:
        Tuple[str, Dict, float, float]: 
            - текст задачи
            - словарь вариантов {текст: значение}
            - правильный ответ
            - допустимая погрешность
    """
    complexity = db.get_user_complexity(user_id)
    cfg = db.COMPLEXITY_LEVELS[complexity]
    task_type = cfg['task_type']
    
    if task_type == 'simple':
        return generate_simple_task(user_data, cfg)
    elif task_type == 'normal':
        return generate_normal_task(user_data, cfg)
    elif task_type == 'complex':
        return generate_complex_task(user_data, cfg)
    elif task_type == 'pro':
        return generate_pro_task(user_data, cfg)
    else:
        return generate_simple_task(user_data, cfg)

def generate_simple_task(user_data: Dict, cfg: Dict) -> Tuple[str, Dict, float, float]:
    """
    Лёгкая задача: процент от баланса
    
    Returns:
        Tuple: (текст_задачи, варианты, правильный_ответ, погрешность)
    """
    currency = random.choice(['RUB', 'USD', 'EUR', 'BTC'])
    balance = user_data[currency.lower()]
    
    # Простые проценты
    percent = random.choice([5, 10, 15, 20, 25, 30, 40, 50])
    correct = round(balance * percent / 100, 2)
    
    # Погрешность
    tolerance = cfg['tolerance'] / 100 * correct
    
    task_text = f"""
📚 *Ежедневная бухгалтерия*
🎯 Сложность: {cfg['name']}

💰 Ваш баланс {currency}: *{balance:,.2f}*

❓ *Вопрос:* Сколько составит {percent}% от вашего баланса в {currency}?

📝 Ответ округлите до сотых.
"""
    
    # Генерация вариантов
    options = generate_answer_options(correct)
    
    return task_text, options, correct, tolerance

def generate_normal_task(user_data: Dict, cfg: Dict) -> Tuple[str, Dict, float, float]:
    """
    Нормальная задача: процент + комиссия
    
    Returns:
        Tuple: (текст_задачи, варианты, правильный_ответ, погрешность)
    """
    currency = random.choice(['RUB', 'USD', 'EUR', 'BTC'])
    balance = user_data[currency.lower()]
    
    # Процент + комиссия
    percent = random.choice([12, 15, 18, 22, 25, 28, 33])
    fee_percent = random.choice([1, 2, 3, 5])
    fee = round(balance * fee_percent / 100, 2)
    
    # Правильный ответ: начисляем процент, добавляем комиссию
    profit = balance * percent / 100
    correct = round(balance + profit + fee, 2)
    
    # Погрешность
    tolerance = cfg['tolerance'] / 100 * correct
    
    task_text = f"""
📚 *Бухгалтерия*
🎯 Сложность: {cfg['name']}

💰 Ваш баланс {currency}: *{balance:,.2f}*
📈 Начисление: {percent}%
💸 Комиссия за обслуживание: {fee:,.2f} {currency}

❓ *Вопрос:* Какой станет итоговый баланс после начисления процентов и учёта комиссии?

📝 Ответ округлите до сотых.
"""
    
    options = generate_answer_options(correct)
    return task_text, options, correct, tolerance

def generate_complex_task(user_data: Dict, cfg: Dict) -> Tuple[str, Dict, float, float]:
    """
    Сложная задача: процент с учётом инфляции
    
    Returns:
        Tuple: (текст_задачи, варианты, правильный_ответ, погрешность)
    """
    currency = random.choice(['RUB', 'USD', 'EUR', 'BTC'])
    balance = user_data[currency.lower()]
    
    # Начисление процента
    percent = random.choice([15, 20, 25, 30, 35])
    profit = balance * percent / 100
    
    # Инфляция (2-8% от итоговой суммы)
    inflation_rate = random.uniform(2, 8)
    inflation = round((balance + profit) * inflation_rate / 100, 2)
    
    # Правильный ответ: баланс + процент - инфляция
    correct = round(balance + profit - inflation, 2)
    
    # Погрешность
    tolerance = cfg['tolerance'] / 100 * abs(correct)
    
    task_text = f"""
📚 *Продвинутая бухгалтерия*
🎯 Сложность: {cfg['name']}

💰 Исходный баланс {currency}: *{balance:,.2f}*
📈 Доходность: +{percent}% (+{profit:,.2f} {currency})
📉 Инфляция: {inflation_rate:.1f}% (−{inflation:,.2f} {currency})

❓ *Вопрос:* Каким будет реальный баланс с учётом доходности и инфляции?

📝 Ответ округлите до сотых.
"""
    
    options = generate_answer_options(correct)
    return task_text, options, correct, tolerance

def generate_pro_task(user_data: Dict, cfg: Dict) -> Tuple[str, Dict, float, float]:
    """
    Профессиональная задача: конвертация валют с начислением процентов
    
    Returns:
        Tuple: (текст_задачи, варианты, правильный_ответ, погрешность)
    """
    rates = db.get_exchange_rates()
    
    # Выбираем основную валюту и валюту для конвертации
    currency = random.choice(['RUB', 'USD', 'EUR', 'BTC'])
    balance = user_data[currency.lower()]
    
    # Выбираем другую валюту
    alt_currency = random.choice([c for c in ['RUB', 'USD', 'EUR', 'BTC'] if c != currency])
    
    # Курс конвертации
    rate = rates[currency] / rates[alt_currency]
    
    # Сколько конвертируем (10-40% от баланса)
    convert_percent = random.choice([10, 15, 20, 25, 30, 35, 40])
    amount_to_convert = round(balance * convert_percent / 100, 2)
    converted_amount = round(amount_to_convert * rate, 2)
    
    # Процент прибыли в альтернативной валюте
    profit_percent = random.choice([8, 12, 15, 18, 22, 25])
    profit_in_alt = round(converted_amount * profit_percent / 100, 2)
    total_in_alt = converted_amount + profit_in_alt
    
    # Обратная конвертация
    back_amount = round(total_in_alt / rate, 2)
    
    # Итоговый баланс
    remaining = balance - amount_to_convert
    correct = round(remaining + back_amount, 2)
    
    # Погрешность = 0 (абсолютная точность)
    tolerance = 0
    
    task_text = f"""
📚 *Профессиональный учёт*
🎯 Сложность: {cfg['name']}

💰 Исходный баланс {currency}: *{balance:,.2f}*

🔄 *Операции:*
├ Конвертация {amount_to_convert:,.2f} {currency} → {alt_currency}
│  (Курс: 1 {currency} = {rate:.4f} {alt_currency})
├ Получено: {converted_amount:,.2f} {alt_currency}
├ Доходность в {alt_currency}: +{profit_percent}% (+{profit_in_alt:,.2f} {alt_currency})
├ Итого в {alt_currency}: {total_in_alt:,.2f} {alt_currency}
└ Обратная конвертация: {total_in_alt:,.2f} {alt_currency} → {currency}

❓ *Вопрос:* Какой итоговый баланс в {currency} после всех операций?

⚠️ *Требуется абсолютная точность!*
📝 Ответ округлите до сотых.
"""
    
    options = generate_answer_options(correct, variance=0.02)
    return task_text, options, correct, tolerance

def generate_answer_options(correct: float, num_options: int = 4, variance: float = 0.15) -> Dict[str, float]:
    """
    Сгенерировать варианты ответов для задачи
    
    Args:
        correct: правильный ответ
        num_options: количество вариантов (включая правильный)
        variance: максимальное отклонение неправильных вариантов
        
    Returns:
        Dict: {текст_ответа: числовое_значение}
    """
    options = {f"{correct:,.2f}": correct}
    
    attempts = 0
    while len(options) < num_options and attempts < 50:
        # Случайное отклонение
        deviation = random.uniform(-variance, variance)
        wrong = round(correct * (1 + deviation), 2)
        
        # Убедимся, что вариант отличается от правильного
        if wrong != correct and wrong > 0:
            options[f"{wrong:,.2f}"] = wrong
        
        attempts += 1
    
    # Перемешиваем варианты
    items = list(options.items())
    random.shuffle(items)
    
    return dict(items)

# ========== ИНВЕСТИЦИОННЫЕ РЕКОМЕНДАЦИИ ==========

def get_investment_recommendation(user_data: Dict, rates: Dict) -> str:
    """
    Проанализировать портфель и дать рекомендацию
    
    Args:
        user_data: данные пользователя
        rates: текущие курсы
        
    Returns:
        str: текст рекомендации
    """
    # Расчёт долей в портфеле
    rub_value = user_data['rub'] * rates['RUB']
    usd_value = user_data['usd'] * rates['USD']
    eur_value = user_data['eur'] * rates['EUR']
    btc_value = user_data['btc'] * rates['BTC']
    
    total = rub_value + usd_value + eur_value + btc_value
    
    if total == 0:
        return "⚠️ У вас пока нет активов. Начните с включения ферм!"
    
    rub_share = rub_value / total * 100
    usd_share = usd_value / total * 100
    eur_share = eur_value / total * 100
    btc_share = btc_value / total * 100
    
    recommendations = []
    
    # Анализ диверсификации
    if rub_share > 50:
        recommendations.append("⚠️ Слишком большая доля в рублях. Рекомендуется диверсификация в другие валюты.")
    
    if btc_share < 5:
        recommendations.append("💡 Рассмотрите увеличение доли биткоина для потенциала роста.")
    
    if btc_share > 50:
        recommendations.append("⚠️ Высокая доля биткоина — это рискованно. Подумайте о фиксации части прибыли.")
    
    if usd_share < 10:
        recommendations.append("💵 Полезно иметь хотя бы 10-20% в долларах для стабильности.")
    
    if 20 <= usd_share <= 40 and 20 <= eur_share <= 40 and 5 <= btc_share <= 20:
        recommendations.append("✅ Ваш портфель хорошо сбалансирован!")
    
    # Анализ абсолютных значений
    total_rub = total
    if total_rub < 10000:
        recommendations.append("🎯 Фокусируйтесь на накоплении: включайте все фермы и проходите бухгалтерию ежедневно.")
    elif total_rub < 100000:
        recommendations.append("📈 Хороший прогресс! Продолжайте апгрейдить фермы для увеличения дохода.")
    elif total_rub < 1000000:
        recommendations.append("🚀 Отличный результат! Вы на пути к первому миллиону.")
    else:
        recommendations.append("👑 Впечатляющий капитал! Вы настоящий финансовый магнат!")
    
    # Собираем финальный текст
    text = "📊 *Анализ портфеля:*\n\n"
    text += f"├ RUB: {rub_share:.1f}%\n"
    text += f"├ USD: {usd_share:.1f}%\n"
    text += f"├ EUR: {eur_share:.1f}%\n"
    text += f"└ BTC: {btc_share:.1f}%\n\n"
    
    text += "*Рекомендации:*\n"
    for rec in recommendations:
        text += f"{rec}\n"
    
    return text

# ========== ФОРМАТИРОВАНИЕ ФЕРМ ==========

def format_farm_info(user_data: Dict, user_id: int) -> str:
    """
    Форматировать информацию о всех фермах пользователя
    
    Args:
        user_data: данные пользователя
        user_id: ID пользователя
        
    Returns:
        str: отформатированный текст
    """
    complexity = db.get_user_complexity(user_id)
    cfg = db.COMPLEXITY_LEVELS[complexity]
    
    text = f"⚙️ *Ваши фермы*\n"
    text += f"🎯 Сложность: *{cfg['name']}*\n"
    text += f"📊 Множитель дохода: x{cfg['income_multiplier']}\n\n"
    
    total_hourly_rub = 0
    rates = db.get_exchange_rates()
    
    for currency in ['RUB', 'USD', 'EUR', 'BTC']:
        farm = db.get_passive_farm(user_id, currency)
        if farm:
            status_emoji = "🟢" if farm['is_active'] else "🔴"
            status_text = "Работает" if farm['is_active'] else "Остановлена"
            
            balance = user_data[currency.lower()]
            hourly = balance * (farm['rate_per_hour'] / 100)
            daily = hourly * 24
            
            # С учётом множителей
            multiplier = db.get_daily_multiplier(user_id)
            effective_hourly = hourly * multiplier * cfg['income_multiplier']
            effective_daily = daily * multiplier * cfg['income_multiplier']
            
            # В рублях для общего подсчёта
            hourly_rub = effective_hourly * rates.get(currency, 1)
            total_hourly_rub += hourly_rub
            
            # Уровень фермы с эмодзи
            level = farm['upgrade_level']
            if level >= 20:
                level_emoji = "👑"
            elif level >= 15:
                level_emoji = "💎"
            elif level >= 10:
                level_emoji = "⭐"
            elif level >= 5:
                level_emoji = "🔷"
            else:
                level_emoji = "🔹"
            
            text += f"""
{status_emoji} *{currency} ферма* {level_emoji}
├ Статус: {status_text}
├ Баланс: {balance:,.2f} {currency}
├ Уровень: {level}
├ Ставка: {farm['rate_per_hour']}%/час
├ Доход/час: {effective_hourly:,.2f} {currency}
├ Доход/день: {effective_daily:,.2f} {currency}
└ Всего заработано: {farm.get('total_earned', 0):,.2f} {currency}

"""
    
    text += f"💰 *Общий доход:* ~{total_hourly_rub:,.2f} ₽/час"
    
    return text

# ========== СТАТИСТИКА И ДОСТИЖЕНИЯ ==========

def format_statistics(user_data: Dict, user_id: int) -> str:
    """
    Форматировать статистику пользователя
    
    Args:
        user_data: данные пользователя
        user_id: ID пользователя
        
    Returns:
        str: отформатированная статистика
    """
    complexity = db.get_user_complexity(user_id)
    multiplier = db.get_daily_multiplier(user_id)
    achievements = db.get_user_achievements(user_id)
    rates = db.get_exchange_rates()
    
    # Расчёт общего капитала
    total = (
        user_data['rub'] * rates['RUB'] +
        user_data['usd'] * rates['USD'] +
        user_data['eur'] * rates['EUR'] +
        user_data['btc'] * rates['BTC']
    )
    
    # Прогресс к миллиону
    million = 1_000_000
    million_percent = min(100, int((total / million) * 100))
    million_bar = progress_bar(million_percent, 15)
    
    # Streak эмодзи
    streak = user_data['auditor_streak']
    if streak >= 100:
        streak_status = "🔥 Бессмертный"
    elif streak >= 50:
        streak_status = "💎 Легендарный"
    elif streak >= 30:
        streak_status = "⭐ Элитный"
    elif streak >= 14:
        streak_status = "🌟 Продвинутый"
    elif streak >= 7:
        streak_status = "✨ Начинающий"
    else:
        streak_status = "🌱 Новичок"
    
    text = f"""
📊 *Статистика игрока*

👤 *Профиль:*
├ Уровень сложности: {db.COMPLEXITY_LEVELS[complexity]['name']}
├ Streak бухгалтера: {streak} дней {streak_status}
├ Множитель дохода: x{multiplier}
└ Всего сборов: {user_data['total_collected']}

💰 *Капитал:*
{million_bar}
├ Общий капитал: {total:,.2f} ₽
├ До миллиона: {million - total:,.2f} ₽
└ Прогресс: {million_percent}%

🏆 *Достижения:* ({len(achievements)})
"""
    
    if achievements:
        for ach in achievements[:5]:  # Показываем последние 5
            text += f"├ {format_achievement(ach)}\n"
        if len(achievements) > 5:
            text += f"└ ... и ещё {len(achievements) - 5}\n"
    else:
        text += "└ Пока нет достижений. Начните играть!\n"
    
    text += f"\n📅 *Дата регистрации:* {user_data.get('registration_date', 'Неизвестно')}"
    
    return text

def format_achievement(ach_type: str) -> str:
    """Форматировать название достижения"""
    achievements_names = {
        'first_collect': '🌟 Первый сбор',
        'streak_7': '📅 Бухгалтер недели',
        'streak_30': '🏆 Месячный марафон',
        'collect_100': '💯 Сотый сбор',
    }
    
    # Проверяем достижения ферм
    if ach_type.startswith('farm_10_'):
        currency = ach_type.split('_')[2]
        return f'⭐ Ферма {currency} уровня 10'
    
    return achievements_names.get(ach_type, ach_type)

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def format_large_number(number: float) -> str:
    """
    Форматировать большое число с суффиксами (K, M, B)
    
    Args:
        number: число
        
    Returns:
        str: отформатированное число
    """
    if number >= 1_000_000_000:
        return f"{number/1_000_000_000:.2f}B"
    elif number >= 1_000_000:
        return f"{number/1_000_000:.2f}M"
    elif number >= 1_000:
        return f"{number/1_000:.2f}K"
    else:
        return f"{number:,.2f}"

def get_random_currency_emoji(currency: str) -> str:
    """Получить эмодзи для валюты"""
    emojis = {
        'RUB': '₽',
        'USD': '$',
        'EUR': '€',
        'BTC': '₿'
    }
    return emojis.get(currency, '💰')

def calculate_roi(invested: float, earned: float) -> float:
    """
    Рассчитать ROI (возврат на инвестиции)
    
    Args:
        invested: вложенная сумма
        earned: заработанная сумма
        
    Returns:
        float: ROI в процентах
    """
    if invested == 0:
        return 0
    return round((earned / invested - 1) * 100, 2)

# ========== ТЕСТИРОВАНИЕ ==========

if __name__ == "__main__":
    print("🧪 Тестирование модуля core.py")
    print("=" * 50)
    
    # Тестовые данные
    test_user = {
        'user_id': 123,
        'rub': 5000.0,
        'usd': 100.0,
        'eur': 50.0,
        'btc': 0.001,
        'auditor_streak': 7,
        'total_collected': 42,
        'registration_date': '2024-01-15'
    }
    
    test_rates = {
        'RUB': 1.0,
        'USD': 90.0,
        'EUR': 100.0,
        'BTC': 5000000.0
    }
    
    # Тест форматирования баланса
    balance_text = format_balance(test_user, test_rates)
    print("✅ Форматирование баланса работает")
    
    # Тест прогресс-бара
    bar = progress_bar(75)
    print(f"✅ Прогресс-бар: {bar}")
    
    # Тест форматирования чисел
    print(f"✅ 1000 -> {format_large_number(1000)}")
    print(f"✅ 1000000 -> {format_large_number(1000000)}")
    print(f"✅ 1000000000 -> {format_large_number(1000000000)}")
    
    print("\n✅ Все тесты пройдены!")

    def format_exchange_rates(rates: Dict) -> str:
    """
    Форматировать курсы валют для отображения
    
    Args:
        rates: словарь курсов из БД
        
    Returns:
        str: отформатированный текст
    """
    text = "📊 *Текущие курсы валют*\n\n"
    text += "*Относительно RUB:*\n"
    text += f"├ 💵 USD: {rates['USD']:,.2f} ₽\n"
    text += f"├ 💶 EUR: {rates['EUR']:,.2f} ₽\n"
    text += f"└ ₿ BTC: {rates['BTC']:,.2f} ₽\n\n"
    
    text += "*Кросс-курсы:*\n"
    text += f"├ EUR/USD: {rates['EUR']/rates['USD']:,.4f}\n"
    text += f"├ BTC/USD: {rates['BTC']/rates['USD']:,.2f}\n"
    text += f"└ BTC/EUR: {rates['BTC']/rates['EUR']:,.2f}\n"
    
    text += f"\n🕐 Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    
    return text

def check_diversification(user_data: Dict) -> Optional[str]:
    """
    Проверить, нужно ли пользователю diversify валюты
    
    Returns:
        str: сообщение-подсказка или None
    """
    rub = user_data['rub']
    usd = user_data['usd']
    eur = user_data['eur']
    btc = user_data['btc']
    
    total = rub + usd + eur + btc
    
    if total == 0:
        return "💡 У вас нет средств. Начните с включения RUB фермы!"
    
    rub_percent = rub / total * 100 if total > 0 else 0
    
    if rub_percent > 90:
        return (
            "⚠️ *Почти все ваши средства в рублях!*\n"
            "💡 *Совет:* Обменяйте часть рублей на USD, EUR или BTC "
            "в разделе «💱 Обмен валют» для диверсификации."
        )
    
    if usd == 0 and eur == 0 and btc == 0:
        return (
            "💡 *У вас только рубли!*\n"
            "🔄 Обменяйте часть на другие валюты в «💱 Обмен валют» "
            "и включите соответствующие фермы для максимального дохода!"
        )
    
    return None

@dp.message(F.text == "🏦 Мой счёт")
async def show_balance(message: types.Message):
    """Показать баланс пользователя"""
    user_id = message.from_user.id
    user_data = db.get_user(user_id)
    rates = db.get_exchange_rates()
    
    balance_text = game.format_balance(user_data, rates)
    
    # Проверка диверсификации
    diversification_tip = game.check_diversification(user_data)
    if diversification_tip:
        balance_text += f"\n\n{diversification_tip}"
    
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
