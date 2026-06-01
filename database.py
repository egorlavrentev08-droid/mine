"""
Вечный Майнинг Бот для Telegram
Модуль работы с базой данных SQLite
Версия: 2.0 (с системой сложностей)
"""

import sqlite3
import random
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple

# ========== КОНФИГУРАЦИЯ БАЗЫ ДАННЫХ ==========
DB_NAME = "eternal_bot.db"

# ========== УРОВНИ СЛОЖНОСТИ ==========
COMPLEXITY_LEVELS = {
    'easy': {
        'name': '🟢 Лёгкая',
        'multiplier': 1.0,
        'tolerance': 5.0,  # процент допустимой погрешности
        'task_type': 'simple',
        'description': 'Простые задачи, высокая погрешность',
        'streak_penalty': False,  # сбрасывать ли streak при ошибке
        'cost_multiplier': 1.0,  # множитель стоимости апгрейда
        'income_multiplier': 1.0   # множитель дохода ферм
    },
    'normal': {
        'name': '🟡 Нормальная',
        'multiplier': 1.2,
        'tolerance': 2.0,
        'task_type': 'normal',
        'description': 'Стандартные задачи, небольшая погрешность',
        'streak_penalty': False,
        'cost_multiplier': 1.2,
        'income_multiplier': 1.1
    },
    'hard': {
        'name': '🟠 Сложная',
        'multiplier': 1.5,
        'tolerance': 0.5,
        'task_type': 'complex',
        'description': 'Продвинутые расчёты, почти без погрешности',
        'streak_penalty': True,
        'cost_multiplier': 1.5,
        'income_multiplier': 1.25
    },
    'pro': {
        'name': '🔴 Профессионал',
        'multiplier': 2.0,
        'tolerance': 0.0,
        'task_type': 'pro',
        'description': 'Максимальная сложность и точность',
        'streak_penalty': True,
        'cost_multiplier': 2.0,
        'income_multiplier': 1.5
    }
}

# ========== ОБМЕН ВАЛЮТ ==========

def exchange_currency(user_id: int, from_currency: str, to_currency: str, amount: float) -> Dict:
    """
    Обменять одну валюту на другую по текущему курсу
    
    Args:
        user_id: ID пользователя
        from_currency: валюта, которую продаём (RUB, USD, EUR, BTC)
        to_currency: валюта, которую покупаем
        amount: сумма в from_currency
        
    Returns:
        Dict: {
            'success': bool,
            'message': str,
            'from_amount': float,
            'to_amount': float,
            'rate': float,
            'fee': float,
            'fee_amount': float
        }
    """
    user = get_user(user_id)
    rates = get_exchange_rates()
    
    # Проверка валют
    if from_currency == to_currency:
        return {
            'success': False,
            'message': '❌ Нельзя обменять валюту саму на себя!'
        }
    
    if from_currency not in rates or to_currency not in rates:
        return {
            'success': False,
            'message': '❌ Неподдерживаемая валюта!'
        }
    
    # Проверка баланса
    if user[from_currency.lower()] < amount:
        return {
            'success': False,
            'message': f'❌ Недостаточно {from_currency}! У вас: {user[from_currency.lower()]:,.2f} {from_currency}'
        }
    
    if amount <= 0:
        return {
            'success': False,
            'message': '❌ Сумма должна быть положительной!'
        }
    
    # Расчёт курса
    from_rate = rates[from_currency]
    to_rate = rates[to_currency]
    
    # Курс: сколько to_currency получим за 1 from_currency
    exchange_rate = from_rate / to_rate
    
    # Комиссия зависит от сложности и валюты
    complexity = get_user_complexity(user_id)
    base_fee = 0.01  # 1% базовая комиссия
    
    # Для криптовалют комиссия выше
    if from_currency == 'BTC' or to_currency == 'BTC':
        base_fee = 0.02  # 2%
    
    # На высокой сложности комиссия ниже
    if complexity == 'pro':
        base_fee *= 0.5  # Скидка 50%
    elif complexity == 'hard':
        base_fee *= 0.75  # Скидка 25%
    
    # Расчёт сумм
    fee_amount = amount * base_fee
    amount_after_fee = amount - fee_amount
    to_amount = round(amount_after_fee * exchange_rate, 2)
    
    # Для BTC больше знаков после запятой
    if to_currency == 'BTC':
        to_amount = round(amount_after_fee * exchange_rate, 8)
    
    # Выполняем обмен
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Списываем from_currency
    c.execute(
        f'UPDATE users SET {from_currency.lower()} = {from_currency.lower()} - ? WHERE user_id = ?',
        (amount, user_id)
    )
    
    # Начисляем to_currency
    c.execute(
        f'UPDATE users SET {to_currency.lower()} = {to_currency.lower()} + ? WHERE user_id = ?',
        (to_amount, user_id)
    )
    
    conn.commit()
    conn.close()
    
    # Логируем транзакцию
    add_transaction(
        user_id, 'exchange', f'{from_currency}→{to_currency}',
        amount,
        f'Обмен: {amount:,.2f} {from_currency} → {to_amount:,.2f} {to_currency} '
        f'(курс: {exchange_rate:.4f}, комиссия: {fee_amount:,.2f} {from_currency})'
    )
    
    return {
        'success': True,
        'message': f'✅ Обмен выполнен успешно!',
        'from_amount': amount,
        'to_amount': to_amount,
        'rate': exchange_rate,
        'fee': base_fee * 100,
        'fee_amount': fee_amount
    }

def get_exchange_preview(from_currency: str, to_currency: str, amount: float, user_id: int) -> Dict:
    """
    Получить предварительный расчёт обмена без выполнения
    
    Args:
        from_currency: валюта продажи
        to_currency: валюта покупки
        amount: сумма
        user_id: ID пользователя (для расчёта комиссии)
        
    Returns:
        Dict с расчётом
    """
    rates = get_exchange_rates()
    
    if from_currency not in rates or to_currency not in rates:
        return {'success': False, 'message': 'Неверная валюта'}
    
    from_rate = rates[from_currency]
    to_rate = rates[to_currency]
    exchange_rate = from_rate / to_rate
    
    complexity = get_user_complexity(user_id)
    base_fee = 0.02 if (from_currency == 'BTC' or to_currency == 'BTC') else 0.01
    
    if complexity == 'pro':
        base_fee *= 0.5
    elif complexity == 'hard':
        base_fee *= 0.75
    
    fee_amount = amount * base_fee
    amount_after_fee = amount - fee_amount
    to_amount = round(amount_after_fee * exchange_rate, 8 if to_currency == 'BTC' else 2)
    
    return {
        'success': True,
        'from_amount': amount,
        'to_amount': to_amount,
        'rate': exchange_rate,
        'fee_percent': base_fee * 100,
        'fee_amount': fee_amount
    }
    
# ========== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ==========

def init_db():
    """
    Инициализация базы данных и создание таблиц, если они не существуют.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("PRAGMA foreign_keys = ON")
    
    # Таблица пользователей с новыми значениями по умолчанию
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            rub REAL DEFAULT 10000.0,  -- Было 1000.0
            usd REAL DEFAULT 0.0,      -- Было 1000.0
            eur REAL DEFAULT 0.0,      -- Было 1000.0
            btc REAL DEFAULT 0.0,      -- Было 1000.0
            auditor_streak INTEGER DEFAULT 0,
            last_check DATE,
            total_collected INTEGER DEFAULT 0,
            complexity TEXT DEFAULT 'easy',
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица пассивных ферм
    c.execute('''
        CREATE TABLE IF NOT EXISTS passive_farms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            currency TEXT,
            is_active BOOLEAN DEFAULT 0,
            upgrade_level INTEGER DEFAULT 1,
            rate_per_hour REAL DEFAULT 1.0,
            last_collect TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_earned REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    ''')
    
    # Таблица курсов валют
    c.execute('''
        CREATE TABLE IF NOT EXISTS exchange_rates (
            base TEXT PRIMARY KEY,
            rate REAL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица истории транзакций
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,  -- 'collect', 'upgrade', 'start_farm', 'daily_bonus'
            currency TEXT,
            amount REAL,
            description TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    ''')
    
    # Таблица достижений
    c.execute('''
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            achievement_type TEXT,  -- 'first_collect', 'streak_7', 'level_10', etc.
            achieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    ''')
    
    # Попытка добавить колонку complexity, если её нет (для обратной совместимости)
    try:
        c.execute("ALTER TABLE users ADD COLUMN complexity TEXT DEFAULT 'easy'")
    except sqlite3.OperationalError:
        pass  # Колонка уже существует
    
    # Попытка добавить колонку total_earned в passive_farms
    try:
        c.execute("ALTER TABLE passive_farms ADD COLUMN total_earned REAL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass
    
    # Начальные курсы валют (если таблица пуста)
    c.execute('SELECT COUNT(*) FROM exchange_rates')
    if c.fetchone()[0] == 0:
        initial_rates = {
            'RUB': 1.0,
            'USD': 90.0,
            'EUR': 100.0,
            'BTC': 5000000.0
        }
        for base, rate in initial_rates.items():
            c.execute(
                'INSERT INTO exchange_rates (base, rate) VALUES (?, ?)',
                (base, rate)
            )
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

# ========== РАБОТА С ПОЛЬЗОВАТЕЛЯМИ ==========

def get_user(user_id: int) -> Dict:
    """
    Получить данные пользователя. Если пользователя нет - создаёт нового.
    
    Args:
        user_id: ID пользователя в Telegram
        
    Returns:
        Dict с данными пользователя
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    
    if row:
        user_data = dict(row)
        conn.close()
        return user_data
    
    # Создаём нового пользователя
    c.execute(
        'INSERT INTO users (user_id) VALUES (?)',
        (user_id,)
    )
    conn.commit()
    
    # Создаём начальные фермы для нового пользователя
    for currency in ['RUB', 'USD', 'EUR', 'BTC']:
        c.execute(
            'INSERT INTO passive_farms (user_id, currency) VALUES (?, ?)',
            (user_id, currency)
        )
    
    conn.commit()
    
    # Получаем свежесозданного пользователя
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user_data = dict(c.fetchone())
    
    conn.close()
    
    # Логируем транзакцию создания
    add_transaction(user_id, 'welcome', 'ALL', 0, 'Начальный баланс')
    
    return user_data

def update_user_activity(user_id: int):
    """Обновить время последней активности пользователя"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        'UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?',
        (user_id,)
    )
    conn.commit()
    conn.close()

def get_user_complexity(user_id: int) -> str:
    """
    Получить уровень сложности пользователя
    
    Returns:
        str: 'easy', 'normal', 'hard', 'pro'
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT complexity FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    
    if row and row[0] in COMPLEXITY_LEVELS:
        return row[0]
    return 'easy'

def set_user_complexity(user_id: int, complexity: str) -> bool:
    """
    Установить уровень сложности для пользователя
    
    Args:
        user_id: ID пользователя
        complexity: 'easy', 'normal', 'hard', 'pro'
        
    Returns:
        bool: успешность операции
    """
    if complexity not in COMPLEXITY_LEVELS:
        return False
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        'UPDATE users SET complexity = ? WHERE user_id = ?',
        (complexity, user_id)
    )
    conn.commit()
    conn.close()
    return True

# ========== РАБОТА С ФЕРМАМИ ==========

def get_passive_farm(user_id: int, currency: str) -> Optional[Dict]:
    """
    Получить данные о конкретной ферме пользователя
    
    Args:
        user_id: ID пользователя
        currency: 'RUB', 'USD', 'EUR', 'BTC'
        
    Returns:
        Dict с данными фермы или None
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute(
        'SELECT * FROM passive_farms WHERE user_id = ? AND currency = ?',
        (user_id, currency)
    )
    row = c.fetchone()
    conn.close()
    
    if row:
        farm = dict(row)
        farm['is_active'] = bool(farm['is_active'])
        return farm
    return None

def get_active_farms(user_id: int) -> List[str]:
    """
    Получить список активных валют пользователя
    
    Returns:
        List[str]: список валют (например, ['RUB', 'BTC'])
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        'SELECT currency FROM passive_farms WHERE user_id = ? AND is_active = 1',
        (user_id,)
    )
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

def toggle_passive_farm(user_id: int, currency: str, active: bool):
    """
    Включить или выключить ферму
    
    Args:
        user_id: ID пользователя
        currency: валюта фермы
        active: True для включения, False для выключения
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute(
        'UPDATE passive_farms SET is_active = ?, last_collect = CURRENT_TIMESTAMP WHERE user_id = ? AND currency = ?',
        (int(active), user_id, currency)
    )
    
    # Логируем действие
    action = 'start_farm' if active else 'stop_farm'
    add_transaction(user_id, action, currency, 0, 
                    f"{'Запуск' if active else 'Остановка'} фермы {currency}")
    
    conn.commit()
    conn.close()

def collect_passive_income(user_id: int, currency: str) -> float:
    """
    Собрать накопленный пассивный доход с фермы
    
    Args:
        user_id: ID пользователя
        currency: валюта фермы
        
    Returns:
        float: сумма собранного дохода
    """
    farm = get_passive_farm(user_id, currency)
    if not farm:
        return 0.0
    
    user = get_user(user_id)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    now = datetime.now()
    last_str = farm['last_collect']
    
    # Вычисляем прошедшее время в часах
    if last_str:
        try:
            last = datetime.strptime(last_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            # На случай другого формата даты
            last = datetime.now() - timedelta(hours=1)
    else:
        last = datetime.now() - timedelta(hours=1)
    
    hours = max(0, (now - last).total_seconds() / 3600)
    
    if hours > 0 and farm['is_active']:
        # Базовый доход
        base_amount = user[currency.lower()] * (farm['rate_per_hour'] / 100)
        profit = base_amount * hours
        
        # Применяем множители
        # 1. Множитель от бухгалтерии (streak)
        streak_multiplier = get_daily_multiplier(user_id)
        
        # 2. Множитель от сложности
        complexity = get_user_complexity(user_id)
        complexity_multiplier = COMPLEXITY_LEVELS[complexity]['income_multiplier']
        
        # Итоговый доход
        total_profit = profit * streak_multiplier * complexity_multiplier
        
        # Обновляем баланс пользователя
        c.execute(
            f'UPDATE users SET {currency.lower()} = {currency.lower()} + ? WHERE user_id = ?',
            (total_profit, user_id)
        )
        
        # Обновляем last_collect
        c.execute(
            'UPDATE passive_farms SET last_collect = CURRENT_TIMESTAMP, total_earned = total_earned + ? WHERE user_id = ? AND currency = ?',
            (total_profit, user_id, currency)
        )
        
        # Увеличиваем счётчик сборов
        c.execute(
            'UPDATE users SET total_collected = total_collected + 1 WHERE user_id = ?',
            (user_id,)
        )
        
        # Логируем транзакцию
        add_transaction(
            user_id, 'collect', currency, total_profit,
            f'Сбор дохода: {total_profit:.2f} {currency} (x{streak_multiplier} streak, x{complexity_multiplier} сложность)'
        )
        
        # Проверяем достижения
        check_achievements(user_id)
        
        conn.commit()
        conn.close()
        return round(total_profit, 2)
    
    conn.close()
    return 0.0

def upgrade_passive_farm(user_id: int, currency: str) -> bool:
    """
    Улучшить ферму до следующего уровня
    
    Args:
        user_id: ID пользователя
        currency: валюта фермы
        
    Returns:
        bool: True если апгрейд успешен
    """
    farm = get_passive_farm(user_id, currency)
    user = get_user(user_id)
    
    if not farm:
        return False
    
    level = farm['upgrade_level']
    complexity = get_user_complexity(user_id)
    cost_multiplier = COMPLEXITY_LEVELS[complexity]['cost_multiplier']
    
    # Базовая стоимость: 500 * уровень * множитель сложности
    cost = int(500 * level * cost_multiplier)
    
    if user[currency.lower()] >= cost:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        # Списываем стоимость
        c.execute(
            f'UPDATE users SET {currency.lower()} = {currency.lower()} - ? WHERE user_id = ?',
            (cost, user_id)
        )
        
        # Улучшаем ферму
        c.execute(
            '''UPDATE passive_farms 
               SET upgrade_level = upgrade_level + 1, 
                   rate_per_hour = rate_per_hour + 0.5 
               WHERE user_id = ? AND currency = ?''',
            (user_id, currency)
        )
        
        # Логируем транзакцию
        add_transaction(
            user_id, 'upgrade', currency, -cost,
            f'Апгрейд фермы {currency} до уровня {level + 1}'
        )
        
        conn.commit()
        conn.close()
        
        # Проверяем достижения
        check_achievements(user_id)
        
        return True
    
    return False

# ========== БУХГАЛТЕРИЯ ==========

def set_daily_check(user_id: int) -> bool:
    """
    Отметить прохождение ежедневной бухгалтерии
    
    Returns:
        bool: True если сегодня ещё не проходили, False если уже проходили
    """
    user = get_user(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user['last_check'] == today:
        return False  # Уже проходили сегодня
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Обновляем streak и дату
    c.execute(
        'UPDATE users SET last_check = ?, auditor_streak = auditor_streak + 1, last_active = CURRENT_TIMESTAMP WHERE user_id = ?',
        (today, user_id)
    )
    
    conn.commit()
    conn.close()
    
    # Проверяем достижения
    check_achievements(user_id)
    
    return True

def reset_streak(user_id: int):
    """Сбросить streak бухгалтерии (при ошибке на высокой сложности)"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        'UPDATE users SET auditor_streak = 0 WHERE user_id = ?',
        (user_id,)
    )
    conn.commit()
    conn.close()

def get_daily_multiplier(user_id: int) -> float:
    """
    Получить текущий множитель дохода на основе streak
    
    Returns:
        float: множитель (1.0 - 3.0)
    """
    user = get_user(user_id)
    streak = user['auditor_streak']
    complexity = get_user_complexity(user_id)
    base_multiplier = COMPLEXITY_LEVELS[complexity]['multiplier']
    
    if streak >= 30:
        return 3.0 * base_multiplier
    elif streak >= 14:
        return 2.0 * base_multiplier
    elif streak >= 7:
        return 1.5 * base_multiplier
    elif streak >= 1:
        return 1.25 * base_multiplier
    
    return 1.0 * base_multiplier

# ========== КУРСЫ ВАЛЮТ ==========

def get_exchange_rates() -> Dict[str, float]:
    """
    Получить текущие курсы валют
    
    Returns:
        Dict: {'RUB': 1.0, 'USD': 90.0, 'EUR': 100.0, 'BTC': 5000000.0}
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT base, rate FROM exchange_rates')
    rows = c.fetchall()
    conn.close()
    
    rates = {row[0]: row[1] for row in rows}
    
    # Если курсы не найдены, возвращаем значения по умолчанию
    if not rates:
        rates = {'RUB': 1.0, 'USD': 90.0, 'EUR': 100.0, 'BTC': 5000000.0}
    
    return rates

def update_exchange_rates():
    """
    Обновить курсы валют (имитация рыночных колебаний)
    Вызывается раз в сутки
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Случайные колебания курсов (±5%)
    for currency in ['USD', 'EUR', 'BTC']:
        c.execute('SELECT rate FROM exchange_rates WHERE base = ?', (currency,))
        row = c.fetchone()
        if row:
            current_rate = row[0]
            # Случайное изменение от -5% до +5%
            change = random.uniform(-0.05, 0.05)
            new_rate = current_rate * (1 + change)
            c.execute(
                'UPDATE exchange_rates SET rate = ?, last_updated = CURRENT_TIMESTAMP WHERE base = ?',
                (new_rate, currency)
            )
    
    conn.commit()
    conn.close()
    print("📊 Курсы валют обновлены")

# ========== ТРАНЗАКЦИИ ==========

def add_transaction(user_id: int, trans_type: str, currency: str, amount: float, description: str = ""):
    """
    Добавить запись о транзакции
    
    Args:
        user_id: ID пользователя
        trans_type: тип ('collect', 'upgrade', 'start_farm', 'daily_bonus', 'welcome')
        currency: валюта
        amount: сумма (положительная для дохода, отрицательная для расхода)
        description: описание
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        'INSERT INTO transactions (user_id, type, currency, amount, description) VALUES (?, ?, ?, ?, ?)',
        (user_id, trans_type, currency, amount, description)
    )
    conn.commit()
    conn.close()

def get_transactions(user_id: int, limit: int = 10) -> List[Dict]:
    """
    Получить последние транзакции пользователя
    
    Args:
        user_id: ID пользователя
        limit: количество записей
        
    Returns:
        List[Dict]: список транзакций
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        '''SELECT * FROM transactions 
           WHERE user_id = ? 
           ORDER BY timestamp DESC 
           LIMIT ?''',
        (user_id, limit)
    )
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ========== ДОСТИЖЕНИЯ ==========

def check_achievements(user_id: int):
    """
    Проверить и выдать новые достижения
    
    Args:
        user_id: ID пользователя
    """
    user = get_user(user_id)
    achievements = get_user_achievements(user_id)
    
    new_achievements = []
    
    # Первый сбор дохода
    if user['total_collected'] >= 1 and 'first_collect' not in achievements:
        add_achievement(user_id, 'first_collect')
        new_achievements.append('Первый сбор дохода 🌟')
    
    # Streak 7 дней
    if user['auditor_streak'] >= 7 and 'streak_7' not in achievements:
        add_achievement(user_id, 'streak_7')
        new_achievements.append('Бухгалтер недели 📅')
    
    # Streak 30 дней
    if user['auditor_streak'] >= 30 and 'streak_30' not in achievements:
        add_achievement(user_id, 'streak_30')
        new_achievements.append('Месячный марафон 🏆')
    
    # 100 сборов
    if user['total_collected'] >= 100 and 'collect_100' not in achievements:
        add_achievement(user_id, 'collect_100')
        new_achievements.append('Сотый сбор 💯')
    
    # Проверка уровней ферм
    for currency in ['RUB', 'USD', 'EUR', 'BTC']:
        farm = get_passive_farm(user_id, currency)
        if farm and farm['upgrade_level'] >= 10:
            ach_name = f'farm_10_{currency}'
            if ach_name not in achievements:
                add_achievement(user_id, ach_name)
                new_achievements.append(f'Ферма {currency} уровня 10 ⭐')
    
    return new_achievements

def add_achievement(user_id: int, achievement_type: str):
    """Добавить достижение пользователю"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        'INSERT OR IGNORE INTO achievements (user_id, achievement_type) VALUES (?, ?)',
        (user_id, achievement_type)
    )
    conn.commit()
    conn.close()

def get_user_achievements(user_id: int) -> List[str]:
    """Получить список достижений пользователя"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        'SELECT achievement_type FROM achievements WHERE user_id = ?',
        (user_id,)
    )
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

# ========== СТАТИСТИКА И ЛИДЕРЫ ==========

def get_top_users(limit: int = 10) -> List[Dict]:
    """
    Получить топ пользователей по общему капиталу
    
    Args:
        limit: количество мест в топе
        
    Returns:
        List[Dict]: список лидеров
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Вычисляем общий капитал в рублях
    c.execute('''
        SELECT 
            u.user_id,
            u.rub,
            u.usd,
            u.eur,
            u.btc,
            u.auditor_streak,
            u.complexity,
            (u.rub * r1.rate + u.usd * r2.rate + u.eur * r3.rate + u.btc * r4.rate) as total_capital
        FROM users u
        CROSS JOIN (SELECT rate FROM exchange_rates WHERE base = 'RUB') r1
        CROSS JOIN (SELECT rate FROM exchange_rates WHERE base = 'USD') r2
        CROSS JOIN (SELECT rate FROM exchange_rates WHERE base = 'EUR') r3
        CROSS JOIN (SELECT rate FROM exchange_rates WHERE base = 'BTC') r4
        ORDER BY total_capital DESC
        LIMIT ?
    ''', (limit,))
    
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_total_users() -> int:
    """Получить общее количество пользователей"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    count = c.fetchone()[0]
    conn.close()
    return count

def get_total_collected_all() -> float:
    """Получить общую сумму собранного дохода всеми пользователями"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT SUM(total_earned) FROM passive_farms')
    total = c.fetchone()[0]
    conn.close()
    return total or 0.0

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def reset_all_farms():
    """Сбросить статус всех ферм (для отладки)"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('UPDATE passive_farms SET is_active = 0')
    conn.commit()
    conn.close()
    print("⚠️ Все фермы остановлены")

def get_database_stats() -> Dict:
    """
    Получить статистику базы данных
    
    Returns:
        Dict: статистика
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    stats = {}
    
    # Пользователи
    c.execute('SELECT COUNT(*) FROM users')
    stats['total_users'] = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM users WHERE complexity = "pro"')
    stats['pro_users'] = c.fetchone()[0]
    
    # Фермы
    c.execute('SELECT COUNT(*) FROM passive_farms WHERE is_active = 1')
    stats['active_farms'] = c.fetchone()[0]
    
    c.execute('SELECT AVG(upgrade_level) FROM passive_farms')
    avg_level = c.fetchone()[0]
    stats['avg_farm_level'] = round(avg_level or 0, 1)
    
    # Транзакции
    c.execute('SELECT COUNT(*) FROM transactions')
    stats['total_transactions'] = c.fetchone()[0]
    
    # Достижения
    c.execute('SELECT COUNT(*) FROM achievements')
    stats['total_achievements'] = c.fetchone()[0]
    
    conn.close()
    return stats

# ========== ТЕСТИРОВАНИЕ (если запущен напрямую) ==========

if __name__ == "__main__":
    print("🧪 Тестирование модуля database.py")
    print("=" * 50)
    
    # Инициализация
    init_db()
    
    # Тестовый пользователь
    test_user_id = 123456789
    
    # Создание/получение пользователя
    user = get_user(test_user_id)
    print(f"✅ Пользователь создан: ID={user['user_id']}")
    print(f"   Баланс: RUB={user['rub']}, USD={user['usd']}, EUR={user['eur']}, BTC={user['btc']}")
    
    # Сложность
    complexity = get_user_complexity(test_user_id)
    print(f"   Сложность: {COMPLEXITY_LEVELS[complexity]['name']}")
    
    # Смена сложности
    set_user_complexity(test_user_id, 'hard')
    complexity = get_user_complexity(test_user_id)
    print(f"   Новая сложность: {COMPLEXITY_LEVELS[complexity]['name']}")
    
    # Фермы
    farm = get_passive_farm(test_user_id, 'BTC')
    print(f"   Ферма BTC: активно={farm['is_active']}, уровень={farm['upgrade_level']}")
    
    # Включение фермы
    toggle_passive_farm(test_user_id, 'BTC', True)
    farm = get_passive_farm(test_user_id, 'BTC')
    print(f"   Ферма BTC включена: {farm['is_active']}")
    
    # Бухгалтерия
    can_check = set_daily_check(test_user_id)
    print(f"   Можно пройти бухгалтерию: {can_check}")
    
    # Множитель
    multiplier = get_daily_multiplier(test_user_id)
    print(f"   Множитель дохода: x{multiplier}")
    
    # Статистика БД
    stats = get_database_stats()
    print(f"\n📊 Статистика БД:")
    print(f"   Пользователей: {stats['total_users']}")
    print(f"   Активных ферм: {stats['active_farms']}")
    print(f"   Средний уровень ферм: {stats['avg_farm_level']}")
    
    print("\n✅ Все тесты пройдены!")
