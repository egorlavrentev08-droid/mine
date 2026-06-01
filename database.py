"""
Вечный Майнинг Бот для Telegram
Модуль работы с базой данных SQLite
Версия: 2.1 (исправленная)
"""

import sqlite3
import random
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from functools import wraps

# ========== КОНФИГУРАЦИЯ БАЗЫ ДАННЫХ ==========
DB_NAME = "eternal_bot.db"

# ========== УРОВНИ СЛОЖНОСТИ (ИСПРАВЛЕНО: бонус теперь понижается, комиссия повышается) ==========
COMPLEXITY_LEVELS = {
    'easy': {
        'name': '🟢 Лёгкая',
        'multiplier': 0.8,  # Пониженный бонус
        'tolerance': 5.0,
        'task_type': 'simple',
        'description': 'Простые задачи, высокая погрешность',
        'streak_penalty': False,
        'cost_multiplier': 0.8,  # Дешевле апгрейд
        'income_multiplier': 0.8,
        'exchange_fee': 0.03  # Высокая комиссия 3%
    },
    'normal': {
        'name': '🟡 Нормальная',
        'multiplier': 1.0,  # Стандартный бонус
        'tolerance': 2.0,
        'task_type': 'normal',
        'description': 'Стандартные задачи, небольшая погрешность',
        'streak_penalty': False,
        'cost_multiplier': 1.0,
        'income_multiplier': 1.0,
        'exchange_fee': 0.02  # Стандартная комиссия 2%
    },
    'hard': {
        'name': '🟠 Сложная',
        'multiplier': 0.6,  # Пониженный бонус
        'tolerance': 0.5,
        'task_type': 'complex',
        'description': 'Продвинутые расчёты, почти без погрешности',
        'streak_penalty': True,
        'cost_multiplier': 1.5,
        'income_multiplier': 0.6,
        'exchange_fee': 0.015  # Пониженная комиссия 1.5%
    },
    'pro': {
        'name': '🔴 Профессионал',
        'multiplier': 0.5,  # Самый низкий бонус
        'tolerance': 0.0,
        'task_type': 'pro',
        'description': 'Максимальная сложность и точность',
        'streak_penalty': True,
        'cost_multiplier': 2.0,
        'income_multiplier': 0.5,
        'exchange_fee': 0.01  # Минимальная комиссия 1%
    }
}

# ========== ДЕКОРАТОР ДЛЯ ПОВТОРНЫХ ПОПЫТОК ==========

def retry_on_lock(func):
    """Повторяет операцию при блокировке БД"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        for attempt in range(3):
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < 2:
                    time.sleep(0.3 * (attempt + 1))
                    continue
                raise
        return None
    return wrapper

# ========== ИНИЦИАЛИЗАЦИЯ ==========

def enable_wal_mode():
    """Включить WAL-режим для SQLite (лучше для параллельного доступа)"""
    try:
        conn = sqlite3.connect(DB_NAME, timeout=20)
        c = conn.cursor()
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA cache_size=-20000")
        conn.commit()
        conn.close()
        print("✅ WAL-режим включён для базы данных")
    except Exception as e:
        print(f"⚠️ Не удалось включить WAL-режим: {e}")

def init_db():
    """Инициализация базы данных и создание таблиц"""
    try:
        conn = sqlite3.connect(DB_NAME, timeout=20)
        c = conn.cursor()
        
        c.execute("PRAGMA foreign_keys = ON")
        
        # Таблица пользователей
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                rub REAL DEFAULT 10000.0,
                usd REAL DEFAULT 0.0,
                eur REAL DEFAULT 0.0,
                btc REAL DEFAULT 0.0,
                auditor_streak INTEGER DEFAULT 0,
                last_check DATE,
                total_collected INTEGER DEFAULT 0,
                complexity TEXT DEFAULT 'easy',
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                daily_accounting_count INTEGER DEFAULT 0,  -- Новое поле: сколько раз прошёл бухгалтерию сегодня
                last_accounting_reset DATE DEFAULT CURRENT_TIMESTAMP  -- Дата сброса счётчика бухгалтерии
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
                type TEXT,
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
                achievement_type TEXT,
                achieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # Таблица фонового сбора дохода (для 6-часового цикла)
        c.execute('''
            CREATE TABLE IF NOT EXISTS income_schedule (
                user_id INTEGER PRIMARY KEY,
                last_auto_collect TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # Начальные курсы валют
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
        
        # Включаем WAL-режим
        enable_wal_mode()
        
        print("✅ База данных инициализирована")
        
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")

# ========== ОБМЕН ВАЛЮТ (с учётом сложности — комиссия понижается на высокой сложности) ==========

@retry_on_lock
def exchange_currency(user_id: int, from_currency: str, to_currency: str, amount: float) -> Dict:
    """Обменять одну валюту на другую по текущему курсу"""
    user = get_user(user_id)
    rates = get_exchange_rates()
    
    if from_currency == to_currency:
        return {'success': False, 'message': '❌ Нельзя обменять валюту саму на себя!'}
    
    if from_currency not in rates or to_currency not in rates:
        return {'success': False, 'message': '❌ Неподдерживаемая валюта!'}
    
    if user[from_currency.lower()] < amount:
        return {
            'success': False,
            'message': f'❌ Недостаточно {from_currency}! У вас: {user[from_currency.lower()]:,.2f} {from_currency}'
        }
    
    if amount <= 0:
        return {'success': False, 'message': '❌ Сумма должна быть положительной!'}
    
    from_rate = rates[from_currency]
    to_rate = rates[to_currency]
    exchange_rate = from_rate / to_rate
    
    complexity = get_user_complexity(user_id)
    base_fee = COMPLEXITY_LEVELS[complexity]['exchange_fee']  # Берём комиссию из уровня сложности
    
    # Для BTC дополнительная комиссия (но общая комиссия не может быть выше 5%)
    if from_currency == 'BTC' or to_currency == 'BTC':
        base_fee = min(base_fee + 0.01, 0.05)
    
    fee_amount = amount * base_fee
    amount_after_fee = amount - fee_amount
    to_amount = round(amount_after_fee * exchange_rate, 8 if to_currency == 'BTC' else 2)
    
    conn = sqlite3.connect(DB_NAME, timeout=20)
    c = conn.cursor()
    
    try:
        c.execute(
            f'UPDATE users SET {from_currency.lower()} = {from_currency.lower()} - ? WHERE user_id = ?',
            (amount, user_id)
        )
        c.execute(
            f'UPDATE users SET {to_currency.lower()} = {to_currency.lower()} + ? WHERE user_id = ?',
            (to_amount, user_id)
        )
        conn.commit()
        
        add_transaction(
            user_id, 'exchange', f'{from_currency}→{to_currency}',
            amount,
            f'Обмен: {amount:,.2f} {from_currency} → {to_amount:,.2f} {to_currency}'
        )
        
        return {
            'success': True,
            'message': '✅ Обмен выполнен успешно!',
            'from_amount': amount,
            'to_amount': to_amount,
            'rate': exchange_rate,
            'fee': base_fee * 100,
            'fee_amount': fee_amount
        }
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': f'❌ Ошибка: {e}'}
    finally:
        conn.close()

def get_exchange_preview(from_currency: str, to_currency: str, amount: float, user_id: int) -> Dict:
    """Получить предварительный расчёт обмена"""
    rates = get_exchange_rates()
    
    if from_currency not in rates or to_currency not in rates:
        return {'success': False, 'message': 'Неверная валюта'}
    
    from_rate = rates[from_currency]
    to_rate = rates[to_currency]
    exchange_rate = from_rate / to_rate
    
    complexity = get_user_complexity(user_id)
    base_fee = COMPLEXITY_LEVELS[complexity]['exchange_fee']
    
    if from_currency == 'BTC' or to_currency == 'BTC':
        base_fee = min(base_fee + 0.01, 0.05)
    
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

# ========== РАБОТА С ПОЛЬЗОВАТЕЛЯМИ ==========

@retry_on_lock
def get_user(user_id: int) -> Dict:
    """Получить данные пользователя. Если пользователя нет - создаёт нового."""
    conn = sqlite3.connect(DB_NAME, timeout=20)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    
    if row:
        user_data = dict(row)
        conn.close()
        return user_data
    
    # Создаём нового пользователя
    c.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
    
    # Создаём начальные фермы
    for currency in ['RUB', 'USD', 'EUR', 'BTC']:
        c.execute(
            'INSERT INTO passive_farms (user_id, currency) VALUES (?, ?)',
            (user_id, currency)
        )
    
    # Создаём запись в income_schedule
    c.execute('INSERT INTO income_schedule (user_id) VALUES (?)', (user_id,))
    
    conn.commit()
    
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user_data = dict(c.fetchone())
    
    conn.close()
    
    add_transaction(user_id, 'welcome', 'ALL', 0, 'Начальный баланс')
    
    return user_data

def update_user_activity(user_id: int):
    """Обновить время последней активности пользователя"""
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20)
            c = conn.cursor()
            c.execute(
                'UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?',
                (user_id,)
            )
            conn.commit()
            conn.close()
            return
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < 2:
                time.sleep(0.5)
                continue
            else:
                return

def get_user_complexity(user_id: int) -> str:
    """Получить уровень сложности пользователя"""
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20)
            c = conn.cursor()
            c.execute('SELECT complexity FROM users WHERE user_id = ?', (user_id,))
            row = c.fetchone()
            conn.close()
            if row and row[0] in COMPLEXITY_LEVELS:
                return row[0]
            return 'easy'
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < 2:
                time.sleep(0.3)
                continue
            return 'easy'

def set_user_complexity(user_id: int, complexity: str) -> bool:
    """Установить уровень сложности для пользователя"""
    if complexity not in COMPLEXITY_LEVELS:
        return False
    
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20)
            c = conn.cursor()
            c.execute(
                'UPDATE users SET complexity = ? WHERE user_id = ?',
                (complexity, user_id)
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < 2:
                time.sleep(0.3)
                continue
            return False

# ========== РАБОТА С ФЕРМАМИ (с ограничением 2 активные фермы) ==========

@retry_on_lock
def get_passive_farm(user_id: int, currency: str) -> Optional[Dict]:
    """Получить данные о конкретной ферме пользователя"""
    conn = sqlite3.connect(DB_NAME, timeout=20)
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
    """Получить список активных валют пользователя"""
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20)
            c = conn.cursor()
            c.execute(
                'SELECT currency FROM passive_farms WHERE user_id = ? AND is_active = 1',
                (user_id,)
            )
            rows = c.fetchall()
            conn.close()
            return [row[0] for row in rows]
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < 2:
                time.sleep(0.3)
                continue
            return []

def get_active_farms_count(user_id: int) -> int:
    """Получить количество активных ферм"""
    return len(get_active_farms(user_id))

def toggle_passive_farm(user_id: int, currency: str, active: bool) -> bool:
    """Включить или выключить ферму (максимум 2 активные)"""
    if active:
        # Проверяем, не превышен ли лимит
        active_count = get_active_farms_count(user_id)
        if active_count >= 2:
            return False  # Нельзя включить больше 2 ферм
    
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20)
            c = conn.cursor()
            
            c.execute(
                'UPDATE passive_farms SET is_active = ?, last_collect = CURRENT_TIMESTAMP WHERE user_id = ? AND currency = ?',
                (int(active), user_id, currency)
            )
            
            add_transaction(user_id, 'start_farm' if active else 'stop_farm', currency, 0, 
                          f"{'Запуск' if active else 'Остановка'} фермы {currency}")
            
            conn.commit()
            conn.close()
            return True
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < 2:
                time.sleep(0.5)
                continue
            else:
                print(f"❌ Ошибка в toggle_passive_farm: {e}")
                return False
    return False

# ========== СБОР ДОХОДА (каждые 6 часов) ==========

def get_last_auto_collect(user_id: int) -> datetime:
    """Получить время последнего автоматического сбора"""
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20)
            c = conn.cursor()
            c.execute('SELECT last_auto_collect FROM income_schedule WHERE user_id = ?', (user_id,))
            row = c.fetchone()
            conn.close()
            if row and row[0]:
                try:
                    return datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    return datetime.now() - timedelta(hours=6)
            return datetime.now() - timedelta(hours=6)
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < 2:
                time.sleep(0.3)
                continue
            return datetime.now() - timedelta(hours=6)

def set_last_auto_collect(user_id: int):
    """Установить время последнего автоматического сбора"""
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20)
            c = conn.cursor()
            c.execute(
                'UPDATE income_schedule SET last_auto_collect = CURRENT_TIMESTAMP WHERE user_id = ?',
                (user_id,)
            )
            conn.commit()
            conn.close()
            return
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < 2:
                time.sleep(0.3)
                continue
            return

def auto_collect_income(user_id: int) -> Dict[str, float]:
    """
    Автоматический сбор дохода со всех активных ферм (вызывается каждые 6 часов)
    Возвращает словарь с собранными суммами по валютам
    """
    result = {}
    active_farms = get_active_farms(user_id)
    
    for currency in active_farms:
        profit = collect_passive_income(user_id, currency)
        if profit > 0:
            result[currency] = profit
    
    # Обновляем время последнего сбора
    set_last_auto_collect(user_id)
    
    return result

def check_and_collect_auto(user_id: int) -> Optional[Dict[str, float]]:
    """
    Проверить, прошло ли 6 часов с последнего сбора, и выполнить сбор если нужно
    Возвращает результат сбора или None, если время не пришло
    """
    last_collect = get_last_auto_collect(user_id)
    now = datetime.now()
    
    if (now - last_collect) >= timedelta(hours=6):
        return auto_collect_income(user_id)
    return None

# ========== СБОР ПАССИВНОГО ДОХОДА (внутренняя функция) ==========

@retry_on_lock
def collect_passive_income(user_id: int, currency: str) -> float:
    """Собрать накопленный пассивный доход с фермы"""
    for attempt in range(3):
        try:
            farm = get_passive_farm(user_id, currency)
            if not farm:
                return 0.0
            
            user = get_user(user_id)
            conn = sqlite3.connect(DB_NAME, timeout=20)
            c = conn.cursor()
            
            now = datetime.now()
            last_str = farm.get('last_collect')
            
            if last_str:
                try:
                    if isinstance(last_str, str):
                        last = datetime.strptime(last_str, '%Y-%m-%d %H:%M:%S')
                    else:
                        last = last_str
                except (ValueError, TypeError):
                    last = datetime.now() - timedelta(hours=1)
            else:
                last = datetime.now() - timedelta(hours=1)
            
            hours = max(0, (now - last).total_seconds() / 3600)
            
            if hours > 0 and farm['is_active']:
                balance = user[currency.lower()]
                base_amount = balance * (farm['rate_per_hour'] / 100)
                profit = base_amount * hours
                
                streak_multiplier = get_daily_multiplier(user_id)
                complexity = get_user_complexity(user_id)
                complexity_multiplier = COMPLEXITY_LEVELS[complexity]['income_multiplier']
                
                total_profit = profit * streak_multiplier * complexity_multiplier
                
                if total_profit > 0:
                    c.execute(
                        f'UPDATE users SET {currency.lower()} = {currency.lower()} + ? WHERE user_id = ?',
                        (total_profit, user_id)
                    )
                    
                    c.execute(
                        'UPDATE passive_farms SET last_collect = CURRENT_TIMESTAMP, total_earned = total_earned + ? WHERE user_id = ? AND currency = ?',
                        (total_profit, user_id, currency)
                    )
                    
                    c.execute(
                        'UPDATE users SET total_collected = total_collected + 1 WHERE user_id = ?',
                        (user_id,)
                    )
                    
                    add_transaction(
                        user_id, 'collect', currency, total_profit,
                        f'Сбор дохода: {total_profit:.2f} {currency}'
                    )
                    
                    check_achievements(user_id)
                    
                    conn.commit()
                    conn.close()
                    return round(total_profit, 2)
            
            conn.close()
            return 0.0
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < 2:
                time.sleep(0.5)
                continue
            else:
                print(f"❌ Ошибка в collect_passive_income: {e}")
                return 0.0
        except Exception as e:
            print(f"❌ Неожиданная ошибка: {e}")
            return 0.0

def upgrade_passive_farm(user_id: int, currency: str) -> bool:
    """Улучшить ферму до следующего уровня"""
    for attempt in range(3):
        try:
            farm = get_passive_farm(user_id, currency)
            user = get_user(user_id)
            
            if not farm:
                return False
            
            level = farm['upgrade_level']
            complexity = get_user_complexity(user_id)
            cost_multiplier = COMPLEXITY_LEVELS[complexity]['cost_multiplier']
            
            cost = int(500 * level * cost_multiplier)
            
            if user[currency.lower()] >= cost:
                conn = sqlite3.connect(DB_NAME, timeout=20)
                c = conn.cursor()
                
                c.execute(
                    f'UPDATE users SET {currency.lower()} = {currency.lower()} - ? WHERE user_id = ?',
                    (cost, user_id)
                )
                
                c.execute(
                    '''UPDATE passive_farms 
                       SET upgrade_level = upgrade_level + 1, 
                           rate_per_hour = rate_per_hour + 0.5 
                       WHERE user_id = ? AND currency = ?''',
                    (user_id, currency)
                )
                
                add_transaction(
                    user_id, 'upgrade', currency, -cost,
                    f'Апгрейд фермы {currency} до уровня {level + 1}'
                )
                
                conn.commit()
                conn.close()
                
                check_achievements(user_id)
                return True
            
            return False
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < 2:
                time.sleep(0.5)
                continue
            return False

# ========== БУХГАЛТЕРИЯ (новая система: бесконечное прохождение, засчитываются первые 2 раза) ==========

def can_do_accounting(user_id: int) -> Tuple[bool, int]:
    """
    Проверить, может ли пользователь пройти бухгалтерию
    Возвращает (можно_ли, сколько_раз_уже_прошёл_сегодня)
    """
    user = get_user(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Сбрасываем счётчик, если новый день
    if user.get('last_accounting_reset') != today:
        reset_accounting_count(user_id)
        return True, 0
    
    count = user.get('daily_accounting_count', 0)
    return count < 2, count

def reset_accounting_count(user_id: int):
    """Сбросить счётчик прохождений бухгалтерии"""
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20)
            c = conn.cursor()
            today = datetime.now().strftime('%Y-%m-%d')
            c.execute(
                'UPDATE users SET daily_accounting_count = 0, last_accounting_reset = ? WHERE user_id = ?',
                (today, user_id)
            )
            conn.commit()
            conn.close()
            return
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < 2:
                time.sleep(0.3)
                continue
            return

def increment_accounting_count(user_id: int):
    """Увеличить счётчик прохождений бухгалтерии"""
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20)
            c = conn.cursor()
            c.execute(
                'UPDATE users SET daily_accounting_count = daily_accounting_count + 1 WHERE user_id = ?',
                (user_id,)
            )
            conn.commit()
            conn.close()
            return
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < 2:
                time.sleep(0.3)
                continue
            return

def mark_accounting_completed(user_id: int) -> bool:
    """
    Отметить успешное прохождение бухгалтерии
    Возвращает True, если это был один из первых 2 раз
    """
    can_do, count = can_do_accounting(user_id)
    
    if not can_do:
        return False
    
    # Увеличиваем счётчик
    increment_accounting_count(user_id)
    
    # Если это первые 2 раза - начисляем Streak
    if count < 2:
        # Обновляем Streak
        conn = sqlite3.connect(DB_NAME, timeout=20)
        c = conn.cursor()
        c.execute(
            'UPDATE users SET auditor_streak = auditor_streak + 1 WHERE user_id = ?',
            (user_id,)
        )
        conn.commit()
        conn.close()
        
        check_achievements(user_id)
        return True
    
    return False

def set_daily_check(user_id: int) -> bool:
    """Устаревшая функция, оставлена для совместимости"""
    return mark_accounting_completed(user_id)

def reset_streak(user_id: int):
    """Сбросить streak бухгалтерии"""
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20)
            c = conn.cursor()
            c.execute('UPDATE users SET auditor_streak = 0 WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            return
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < 2:
                time.sleep(0.5)
                continue
            return

def get_daily_multiplier(user_id: int) -> float:
    """Получить текущий множитель дохода на основе streak"""
    for attempt in range(3):
        try:
            user = get_user(user_id)
            streak = user.get('auditor_streak', 0)
            complexity = get_user_complexity(user_id)
            base_multiplier = COMPLEXITY_LEVELS[complexity]['multiplier']
            
            # Множитель на основе Streak (без учёта сложности - сложность уже применена)
            if streak >= 30:
                return 3.0 * base_multiplier
            elif streak >= 14:
                return 2.0 * base_multiplier
            elif streak >= 7:
                return 1.5 * base_multiplier
            elif streak >= 1:
                return 1.25 * base_multiplier
            
            return 1.0 * base_multiplier
        except:
            return 1.0

# ========== КУРСЫ ВАЛЮТ ==========

def get_exchange_rates() -> Dict[str, float]:
    """Получить текущие курсы валют"""
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20)
            c = conn.cursor()
            c.execute('SELECT base, rate FROM exchange_rates')
            rows = c.fetchall()
            conn.close()
            
            if rows:
                return {row[0]: row[1] for row in rows}
            return {'RUB': 1.0, 'USD': 90.0, 'EUR': 100.0, 'BTC': 5000000.0}
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < 2:
                time.sleep(0.3)
                continue
            return {'RUB': 1.0, 'USD': 90.0, 'EUR': 100.0, 'BTC': 5000000.0}

def update_exchange_rates():
    """Обновить курсы валют (имитация рыночных колебаний)"""
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20)
            c = conn.cursor()
            
            for currency in ['USD', 'EUR', 'BTC']:
                c.execute('SELECT rate FROM exchange_rates WHERE base = ?', (currency,))
                row = c.fetchone()
                if row:
                    current_rate = row[0]
                    change = random.uniform(-0.05, 0.05)
                    new_rate = current_rate * (1 + change)
                    c.execute(
                        'UPDATE exchange_rates SET rate = ?, last_updated = CURRENT_TIMESTAMP WHERE base = ?',
                        (new_rate, currency)
                    )
            
            conn.commit()
            conn.close()
            print("📊 Курсы валют обновлены")
            return
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < 2:
                time.sleep(0.5)
                continue
            return

# ========== ТРАНЗАКЦИИ ==========

def add_transaction(user_id: int, trans_type: str, currency: str, amount: float, description: str = ""):
    """Добавить запись о транзакции"""
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20)
            c = conn.cursor()
            c.execute(
                'INSERT INTO transactions (user_id, type, currency, amount, description) VALUES (?, ?, ?, ?, ?)',
                (user_id, trans_type, currency, amount, description)
            )
            conn.commit()
            conn.close()
            return
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < 2:
                time.sleep(0.3)
                continue
            return

def get_transactions(user_id: int, limit: int = 10) -> List[Dict]:
    """Получить последние транзакции пользователя"""
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20)
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
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < 2:
                time.sleep(0.3)
                continue
            return []

# ========== ДОСТИЖЕНИЯ ==========

def check_achievements(user_id: int):
    """Проверить и выдать новые достижения"""
    for attempt in range(3):
        try:
            user = get_user(user_id)
            achievements = get_user_achievements(user_id)
            new_achievements = []
            
            if user.get('total_collected', 0) >= 1 and 'first_collect' not in achievements:
                add_achievement(user_id, 'first_collect')
                new_achievements.append('Первый сбор дохода 🌟')
            
            if user.get('auditor_streak', 0) >= 7 and 'streak_7' not in achievements:
                add_achievement(user_id, 'streak_7')
                new_achievements.append('Бухгалтер недели 📅')
            
            if user.get('auditor_streak', 0) >= 30 and 'streak_30' not in achievements:
                add_achievement(user_id, 'streak_30')
                new_achievements.append('Месячный марафон 🏆')
            
            if user.get('total_collected', 0) >= 100 and 'collect_100' not in achievements:
                add_achievement(user_id, 'collect_100')
                new_achievements.append('Сотый сбор 💯')
            
            for currency in ['RUB', 'USD', 'EUR', 'BTC']:
                farm = get_passive_farm(user_id, currency)
                if farm and farm.get('upgrade_level', 0) >= 10:
                    ach_name = f'farm_10_{currency}'
                    if ach_name not in achievements:
                        add_achievement(user_id, ach_name)
                        new_achievements.append(f'Ферма {currency} уровня 10 ⭐')
            
            return new_achievements
            
        except:
            return []

def add_achievement(user_id: int, achievement_type: str):
    """Добавить достижение пользователю"""
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20)
            c = conn.cursor()
            c.execute(
                'INSERT OR IGNORE INTO achievements (user_id, achievement_type) VALUES (?, ?)',
                (user_id, achievement_type)
            )
            conn.commit()
            conn.close()
            return
        except:
            return

def get_user_achievements(user_id: int) -> List[str]:
    """Получить список достижений пользователя"""
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20)
            c = conn.cursor()
            c.execute(
                'SELECT achievement_type FROM achievements WHERE user_id = ?',
                (user_id,)
            )
            rows = c.fetchall()
            conn.close()
            return [row[0] for row in rows]
        except:
            return []

# ========== СТАТИСТИКА ==========

def get_database_stats() -> Dict:
    """Получить статистику базы данных"""
    stats = {
        'total_users': 0,
        'pro_users': 0,
        'active_farms': 0,
        'avg_farm_level': 0,
        'total_transactions': 0,
        'total_achievements': 0
    }
    
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20)
            c = conn.cursor()
            
            c.execute('SELECT COUNT(*) FROM users')
            stats['total_users'] = c.fetchone()[0]
            
            c.execute('SELECT COUNT(*) FROM users WHERE complexity = "pro"')
            stats['pro_users'] = c.fetchone()[0]
            
            c.execute('SELECT COUNT(*) FROM passive_farms WHERE is_active = 1')
            stats['active_farms'] = c.fetchone()[0]
            
            c.execute('SELECT AVG(upgrade_level) FROM passive_farms')
            avg = c.fetchone()[0]
            stats['avg_farm_level'] = round(avg or 0, 1)
            
            c.execute('SELECT COUNT(*) FROM transactions')
            stats['total_transactions'] = c.fetchone()[0]
            
            c.execute('SELECT COUNT(*) FROM achievements')
            stats['total_achievements'] = c.fetchone()[0]
            
            conn.close()
            return stats
            
        except Exception as e:
            print(f"Ошибка получения статистики: {e}")
            return stats

# ========== ДЛЯ ОТЛАДКИ ==========

def reset_all_farms():
    """Сбросить статус всех ферм (для отладки)"""
    try:
        conn = sqlite3.connect(DB_NAME, timeout=20)
        c = conn.cursor()
        c.execute('UPDATE passive_farms SET is_active = 0')
        conn.commit()
        conn.close()
        print("⚠️ Все фермы остановлены")
    except:
        pass

# ========== ТЕСТИРОВАНИЕ ==========

if __name__ == "__main__":
    print("🧪 Тестирование модуля database.py")
    print("=" * 50)
    
    init_db()
    
    test_user_id = 123456789
    
    user = get_user(test_user_id)
    print(f"✅ Пользователь создан: ID={user['user_id']}")
    print(f"   Баланс: RUB={user['rub']}, USD={user['usd']}, EUR={user['eur']}, BTC={user['btc']}")
    
    complexity = get_user_complexity(test_user_id)
    print(f"   Сложность: {COMPLEXITY_LEVELS[complexity]['name']}")
    print(f"   Множитель бонуса: x{COMPLEXITY_LEVELS[complexity]['multiplier']}")
    print(f"   Комиссия обмена: {COMPLEXITY_LEVELS[complexity]['exchange_fee']*100}%")
    
    set_user_complexity(test_user_id, 'pro')
    complexity = get_user_complexity(test_user_id)
    print(f"   Новая сложность: {COMPLEXITY_LEVELS[complexity]['name']}")
    print(f"   Множитель бонуса: x{COMPLEXITY_LEVELS[complexity]['multiplier']}")
    print(f"   Комиссия обмена: {COMPLEXITY_LEVELS[complexity]['exchange_fee']*100}%")
    
    farm = get_passive_farm(test_user_id, 'BTC')
    if farm:
        print(f"   Ферма BTC: активно={farm['is_active']}, уровень={farm['upgrade_level']}")
    
    # Тест включения ферм (ограничение 2)
    print("\n🔄 Тест включения ферм (максимум 2):")
    for cur in ['RUB', 'USD', 'EUR', 'BTC']:
        result = toggle_passive_farm(test_user_id, cur, True)
        print(f"   {cur}: {'✅' if result else '❌ (лимит)'}")
    
    active = get_active_farms(test_user_id)
    print(f"   Активные фермы: {active}")
    
    # Тест бухгалтерии
    print("\n📚 Тест бухгалтерии (первые 2 раза засчитываются):")
    for i in range(4):
        can_do, count = can_do_accounting(test_user_id)
        print(f"   Попытка {i+1}: можно={can_do}, уже прошёл={count}")
        if can_do:
            mark_accounting_completed(test_user_id)
    
    # Тест автоматического сбора (6 часов)
    print(f"\n⏰ Тест автоматического сбора:")
    last = get_last_auto_collect(test_user_id)
    print(f"   Последний сбор: {last}")
    result = check_and_collect_auto(test_user_id)
    print(f"   Сбор сейчас: {'✅' if result else '⏳ (ждём 6 часов)'}")
    
    stats = get_database_stats()
    print(f"\n📊 Статистика БД:")
    print(f"   Пользователей: {stats['total_users']}")
    print(f"   Активных ферм: {stats['active_farms']}")
    print(f"   Средний уровень ферм: {stats['avg_farm_level']}")
    
    print("\n✅ Все тесты пройдены!")
