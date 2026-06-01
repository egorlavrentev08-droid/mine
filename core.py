"""
Вечный Майнинг Бот для Telegram
Модуль игровой логики
Версия: 2.1 (исправленная)
"""

import random
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# ========== ФОРМАТИРОВАНИЕ БАЛАНСА ==========

def format_balance(user_data: Dict, rates: Dict) -> str:
    """
    Форматировать баланс пользователя для отображения
    """
    rub = user_data.get('rub', 0)
    usd = user_data.get('usd', 0)
    eur = user_data.get('eur', 0)
    btc = user_data.get('btc', 0)
    
    # Расчёт общего капитала в рублях
    total_rub = rub + usd * rates.get('USD', 90) + eur * rates.get('EUR', 100) + btc * rates.get('BTC', 5000000)
    total_usd = rub / rates.get('USD', 90) + usd + eur * rates.get('EUR', 100) / rates.get('USD', 90) + btc * rates.get('BTC', 5000000) / rates.get('USD', 90)
    
    # Форматирование чисел
    rub_str = f"{rub:,.2f}".replace(',', ' ')
    usd_str = f"{usd:,.2f}".replace(',', ' ')
    eur_str = f"{eur:,.2f}".replace(',', ' ')
    btc_str = f"{btc:.8f}"
    total_rub_str = f"{total_rub:,.2f}".replace(',', ' ')
    total_usd_str = f"{total_usd:,.2f}".replace(',', ' ')
    
    text = f"""
🏦 *Ваш счёт*

💎 *Общий капитал:*
{total_rub_str} ₽ (~{total_usd_str} $)

💰 *Рубли (RUB):*
{rub_str} ₽

💵 *Доллары (USD):*
{usd_str} $

💶 *Евро (EUR):*
{eur_str} €

₿ *Биткоин (BTC):*
{btc_str} BTC

📅 *Дата:* {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
    return text


def format_balance_simple(balance: float, currency: str) -> str:
    """Простое форматирование баланса"""
    symbols = {'RUB': '₽', 'USD': '$', 'EUR': '€', 'BTC': '₿'}
    symbol = symbols.get(currency, '')
    return f"{balance:,.2f} {symbol}"


# ========== ГЕНЕРАЦИЯ БУХГАЛТЕРСКИХ ЗАДАЧ (новая система: с учётом баланса и процентов) ==========

def generate_accounting_task(user_data: Dict, user_id: int) -> Tuple[str, Dict, float, float]:
    """
    Сгенерировать задачу по бухгалтерии.
    Теперь задачи — это расчёт процентов от баланса с учётом комиссий и инфляции.
    """
    try:
        import database as db
        complexity = db.get_user_complexity(user_id)
        cfg = db.COMPLEXITY_LEVELS.get(complexity, db.COMPLEXITY_LEVELS['easy'])
        tolerance = cfg.get('tolerance', 5.0) / 100
    except:
        tolerance = 0.05
    
    # Выбираем случайную валюту
    currency = random.choice(['RUB', 'USD', 'EUR', 'BTC'])
    balance = user_data.get(currency.lower(), 0)
    
    if balance <= 0:
        balance = 1000  # Если баланс 0, генерируем задачу с гипотетическим балансом
    
    # Типы задач:
    task_type = random.choice(['percent', 'fee', 'inflation', 'compound'])
    
    if task_type == 'percent':
        # Простой процент от баланса
        percent = random.choice([5, 10, 15, 20, 25, 30, 40, 50])
        correct = round(balance * percent / 100, 2)
        task_text = f"""
📚 *Ежедневная бухгалтерия*

💰 Ваш баланс {currency}: *{balance:,.2f}*

❓ *Вопрос:* Сколько составит *{percent}%* от вашего баланса в {currency}?

📝 Ответ округлите до сотых.
"""
        
    elif task_type == 'fee':
        # Расчёт комиссии за обмен
        percent = random.choice([1, 2, 3, 5, 10])
        correct = round(balance * percent / 100, 2)
        task_text = f"""
📚 *Ежедневная бухгалтерия*

💰 Ваш баланс {currency}: *{balance:,.2f}*

❓ *Вопрос:* Сколько составит комиссия *{percent}%* от вашего баланса в {currency}?

📝 Ответ округлите до сотых.
"""
        
    elif task_type == 'inflation':
        # Расчёт влияния инфляции
        inflation_rate = random.choice([2, 3, 5, 7, 10])
        months = random.choice([1, 3, 6, 12])
        # Формула: баланс * (1 - инфляция/100)^месяцы
        factor = (1 - inflation_rate / 100) ** months
        correct = round(balance * (1 - factor), 2)
        task_text = f"""
📚 *Ежедневная бухгалтерия*

💰 Ваш баланс {currency}: *{balance:,.2f}*

📉 Инфляция: *{inflation_rate}%* в месяц

❓ *Вопрос:* Какую сумму вы потеряете из-за инфляции за *{months}* месяцев?

📝 Ответ округлите до сотых.
"""
        
    elif task_type == 'compound':
        # Сложный процент (доход от инвестиций)
        rate = random.choice([5, 10, 15, 20])
        periods = random.choice([3, 6, 12])
        # Формула: баланс * (1 + ставка/100)^периоды
        factor = (1 + rate / 100) ** periods
        total = balance * factor
        correct = round(total - balance, 2)
        task_text = f"""
📚 *Ежедневная бухгалтерия*

💰 Ваш баланс {currency}: *{balance:,.2f}*

📈 Ставка: *{rate}%* в месяц

❓ *Вопрос:* Какой доход вы получите за *{periods}* месяцев при сложном проценте?

📝 Ответ округлите до сотых.
"""
    
    # Создаём варианты ответов
    options = {f"{correct:,.2f}": correct}
    
    while len(options) < 4:
        deviation = random.uniform(-0.2, 0.2)
        wrong = round(correct * (1 + deviation), 2)
        if wrong != correct and wrong > 0 and f"{wrong:,.2f}" not in options:
            options[f"{wrong:,.2f}"] = wrong
    
    # Перемешиваем варианты
    items = list(options.items())
    random.shuffle(items)
    options = dict(items)
    
    # Допустимая погрешность
    error_margin = max(0.01, correct * tolerance)
    
    return task_text, options, correct, error_margin


# ========== ИНВЕСТИЦИОННЫЕ РЕКОМЕНДАЦИИ ==========

def get_investment_recommendation(user_data: Dict, rates: Dict) -> str:
    """Анализ портфеля и рекомендации"""
    rub = user_data.get('rub', 0)
    usd = user_data.get('usd', 0)
    eur = user_data.get('eur', 0)
    btc = user_data.get('btc', 0)
    
    rub_value = rub
    usd_value = usd * rates.get('USD', 90)
    eur_value = eur * rates.get('EUR', 100)
    btc_value = btc * rates.get('BTC', 5000000)
    
    total = rub_value + usd_value + eur_value + btc_value
    
    if total == 0:
        return "⚠️ У вас пока нет активов. Включите RUB ферму и начните зарабатывать!"
    
    rub_share = rub_value / total * 100
    usd_share = usd_value / total * 100
    eur_share = eur_value / total * 100
    btc_share = btc_value / total * 100
    
    text = f"📊 *Анализ портфеля:*\n\n"
    text += f"├ RUB: {rub_share:.1f}%\n"
    text += f"├ USD: {usd_share:.1f}%\n"
    text += f"├ EUR: {eur_share:.1f}%\n"
    text += f"└ BTC: {btc_share:.1f}%\n\n"
    
    if rub_share > 70:
        text += "⚠️ *Совет:* Слишком много рублей. Обменяйте часть на USD/EUR/BTC в разделе «💱 Обмен валют»!\n"
    elif btc_share < 5 and total > 1000:
        text += "💡 *Совет:* Добавьте немного BTC для потенциала роста!\n"
    elif 20 <= usd_share <= 40 and 20 <= eur_share <= 40:
        text += "✅ Отличная диверсификация портфеля!\n"
    else:
        text += "📈 Регулярно проходите бухгалтерию для увеличения множителя дохода!\n"
    
    return text


# ========== ФОРМАТИРОВАНИЕ ФЕРМ ==========

def format_farms_info(user_data: Dict, farms: List[Dict]) -> str:
    """Форматирование списка ферм"""
    if not farms:
        return "🚜 У вас нет активных ферм.\n\nВключите ферму в разделе «⚙️ Мои фермы»!"
    
    text = "🚜 *Ваши активные фермы:*\n\n"
    
    for farm in farms:
        currency = farm.get('currency', 'UNK')
        balance = user_data.get(currency.lower(), 0)
        hourly = balance * (farm.get('rate_per_hour', 1) / 100)
        status = "🟢 Работает" if farm.get('is_active') else "🔴 Остановлена"
        
        text += f"""
*{currency}* ({status})
├ Уровень: {farm.get('upgrade_level', 1)}
├ Ставка: {farm.get('rate_per_hour', 1)}%/час
├ Баланс: {balance:,.2f}
└ Доход/час: +{hourly:.2f} {currency}

"""
    
    return text


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def format_large_number(number: float) -> str:
    """Форматировать большое число (K, M, B)"""
    if number >= 1_000_000_000:
        return f"{number/1_000_000_000:.2f}B"
    elif number >= 1_000_000:
        return f"{number/1_000_000:.2f}M"
    elif number >= 1_000:
        return f"{number/1_000:.2f}K"
    else:
        return f"{number:,.2f}"


def format_exchange_rates(rates: Dict) -> str:
    """Форматировать курсы валют"""
    text = "📊 *Курсы валют (к RUB)*\n\n"
    text += f"├ 💵 USD: {rates.get('USD', 90):,.2f} ₽\n"
    text += f"├ 💶 EUR: {rates.get('EUR', 100):,.2f} ₽\n"
    text += f"└ ₿ BTC: {rates.get('BTC', 5000000):,.2f} ₽\n"
    return text


def check_diversification(user_data: Dict) -> Optional[str]:
    """Проверить диверсификацию портфеля"""
    rub = user_data.get('rub', 0)
    usd = user_data.get('usd', 0)
    eur = user_data.get('eur', 0)
    btc = user_data.get('btc', 0)
    
    total = rub + usd + eur + btc
    
    if total == 0:
        return None
    
    rub_percent = rub / total * 100
    
    if rub_percent > 90:
        return "⚠️ *Совет:* Обменяйте часть рублей на USD, EUR или BTC в разделе «💱 Обмен валют» для диверсификации!"
    
    if usd == 0 and eur == 0 and btc == 0:
        return "💡 *Совет:* Обменяйте рубли на другие валюты в разделе «💱 Обмен валют» для максимального дохода!"
    
    return None


def calculate_roi(invested: float, earned: float) -> float:
    """Рассчитать ROI (возврат на инвестиции) в процентах"""
    if invested == 0:
        return 0
    return round((earned / invested - 1) * 100, 2)


def get_currency_symbol(currency: str) -> str:
    """Получить символ валюты"""
    symbols = {
        'RUB': '₽',
        'USD': '$',
        'EUR': '€',
        'BTC': '₿'
    }
    return symbols.get(currency, currency)


def format_progress_bar(current: float, target: float, length: int = 10) -> str:
    """Создать прогресс-бар"""
    percent = min(100, int((current / target) * 100)) if target > 0 else 0
    filled = int(length * percent / 100)
    empty = length - filled
    
    if percent >= 75:
        bar = '🟩' * filled + '⬜' * empty
    elif percent >= 50:
        bar = '🟨' * filled + '⬜' * empty
    elif percent >= 25:
        bar = '🟧' * filled + '⬜' * empty
    else:
        bar = '🟥' * filled + '⬜' * empty
    
    return bar


def format_streak_status(streak: int) -> str:
    """Форматировать статус Streak"""
    if streak >= 100:
        return "🔥 Бессмертный"
    elif streak >= 50:
        return "💎 Легендарный"
    elif streak >= 30:
        return "⭐ Элитный"
    elif streak >= 14:
        return "🌟 Продвинутый"
    elif streak >= 7:
        return "✨ Начинающий"
    elif streak >= 3:
        return "🌱 Новичок"
    else:
        return "🥚 Без Streak"


def format_achievement_name(achievement_type: str) -> str:
    """Форматировать название достижения"""
    achievements = {
        'first_collect': '🌟 Первый сбор дохода',
        'streak_7': '📅 Бухгалтер недели',
        'streak_30': '🏆 Месячный марафон',
        'collect_100': '💯 Сотый сбор',
        'first_upgrade': '⬆️ Первый апгрейд',
        'millionaire': '💰 Миллионер',
    }
    
    if achievement_type.startswith('farm_10_'):
        currency = achievement_type.split('_')[2]
        return f'⭐ Ферма {currency} уровня 10'
    
    return achievements.get(achievement_type, achievement_type)


# ========== СТАТИСТИКА ==========

def format_user_stats(user_data: Dict, user_id: int) -> str:
    """Форматировать статистику пользователя"""
    try:
        import database as db
        complexity = db.get_user_complexity(user_id)
        multiplier = db.get_daily_multiplier(user_id)
        streak_status = format_streak_status(user_data.get('auditor_streak', 0))
        
        text = f"""
📊 *Ваша статистика*

👤 *Профиль:*
├ Сложность: {db.COMPLEXITY_LEVELS.get(complexity, {}).get('name', 'Лёгкая')}
├ Streak: {user_data.get('auditor_streak', 0)} дней ({streak_status})
├ Множитель дохода: x{multiplier}
└ Всего сборов: {user_data.get('total_collected', 0)}

💡 *Совет:* Проходите бухгалтерию каждый день для увеличения множителя!
"""
        return text
    except:
        return f"📊 *Статистика*\n\nStreak: {user_data.get('auditor_streak', 0)} дней"


# ========== ТЕСТИРОВАНИЕ ==========

if __name__ == "__main__":
    print("🧪 Тестирование модуля core.py")
    print("=" * 50)
    
    test_user = {
        'rub': 10000.0,
        'usd': 100.0,
        'eur': 50.0,
        'btc': 0.001,
        'auditor_streak': 7,
        'total_collected': 42
    }
    
    test_rates = {
        'RUB': 1.0,
        'USD': 90.0,
        'EUR': 100.0,
        'BTC': 5000000.0
    }
    
    # Тест format_balance
    balance_text = format_balance(test_user, test_rates)
    print("✅ format_balance работает")
    
    # Тест генерации задач
    print("\n📚 Тест генерации задач бухгалтерии:")
    for i in range(5):
        task_text, options, correct, tolerance = generate_accounting_task(test_user, 123456789)
        print(f"   Задача {i+1}: правильный ответ = {correct}")
    
    # Тест get_investment_recommendation
    rec = get_investment_recommendation(test_user, test_rates)
    print(f"\n✅ get_investment_recommendation: {rec[:50]}...")
    
    # Тест format_large_number
    print(f"\n✅ format_large_number(1000000): {format_large_number(1000000)}")
    
    # Тест format_progress_bar
    bar = format_progress_bar(5000, 10000)
    print(f"✅ progress_bar: {bar}")
    
    # Тест format_streak_status
    status = format_streak_status(7)
    print(f"✅ format_streak_status(7): {status}")
    
    print("\n✅ Все тесты пройдены!")
