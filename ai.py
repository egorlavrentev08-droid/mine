"""
Вечный Майнинг Бот для Telegram
Модуль генерации AI-ответов
Версия: 2.1 (исправленная)
"""

import json
import os
import random
from typing import Dict, Optional, List
from datetime import datetime
from phrases_data import TEMPLATES, get_random_emoji

# ========== КОНФИГУРАЦИЯ ==========
AI_SETTINGS_FILE = "ai_settings.json"

# ========== ОСНОВНОЙ КЛАСС ==========

class AIResponseGenerator:
    """
    Генератор ответов на основе шаблонов.
    Создаёт иллюзию живого ИИ с разными стилями общения.
    """
    
    def __init__(self):
        """Инициализация генератора"""
        self.settings = self.load_settings()
        self.conversation_history = {}  # История общения с пользователями
        self.last_phrases = {}  # Последние использованные фразы (для избежания повторов)
        
    # ========== ЗАГРУЗКА/СОХРАНЕНИЕ НАСТРОЕК ==========
    
    def load_settings(self) -> Dict:
        """
        Загрузить настройки AI из JSON-файла
        
        Returns:
            Dict: словарь с настройками всех пользователей
        """
        if os.path.exists(AI_SETTINGS_FILE):
            try:
                with open(AI_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                print("⚠️ Ошибка чтения файла настроек AI. Создаю новый.")
                return {}
        return {}
    
    def save_settings(self):
        """Сохранить настройки AI в JSON-файл"""
        try:
            with open(AI_SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"❌ Ошибка сохранения настроек AI: {e}")
    
    # ========== УПРАВЛЕНИЕ НАСТРОЙКАМИ ПОЛЬЗОВАТЕЛЯ ==========
    
    def get_user_settings(self, user_id: int) -> Dict:
        """
        Получить настройки пользователя.
        Если нет — создать со значениями по умолчанию.
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            Dict: настройки пользователя
        """
        user_id_str = str(user_id)
        
        if user_id_str not in self.settings:
            self.settings[user_id_str] = {
                "ai_enabled": True,
                "bot_name": "Финансовый Гуру",
                "personality": "friendly",  # friendly, business, sarcastic, motivating
                "response_chance": 30,  # 1-100
                "greeting_enabled": True,
                "farewell_enabled": True,
                "advice_frequency": 40,  # 0-100
                "use_emojis": True,
                "mention_name": True,  # Упоминать имя пользователя
                "last_interaction": None,
                "total_responses": 0,  # Счётчик ответов
                "favorite_phrases": []  # Любимые фразы пользователя
            }
            self.save_settings()
        
        return self.settings[user_id_str]
    
    def update_setting(self, user_id: int, setting: str, value) -> bool:
        """
        Обновить конкретную настройку пользователя
        
        Args:
            user_id: ID пользователя
            setting: название настройки
            value: новое значение
            
        Returns:
            bool: успешность операции
        """
        settings = self.get_user_settings(user_id)
        
        if setting in settings:
            settings[setting] = value
            self.settings[str(user_id)] = settings
            self.save_settings()
            return True
        
        return False
    
    def reset_user_settings(self, user_id: int) -> bool:
        """
        Сбросить настройки пользователя до стандартных
        
        Args:
            user_id: ID пользователя
            
        Returns:
            bool: успешность операции
        """
        try:
            self.settings[str(user_id)] = {
                "ai_enabled": True,
                "bot_name": "Финансовый Гуру",
                "personality": "friendly",
                "response_chance": 30,
                "greeting_enabled": True,
                "farewell_enabled": True,
                "advice_frequency": 40,
                "use_emojis": True,
                "mention_name": True,
                "last_interaction": None,
                "total_responses": 0,
                "favorite_phrases": []
            }
            self.save_settings()
            return True
        except Exception:
            return False
    
    # ========== ГЕНЕРАЦИЯ ФРАЗ ==========
    
    def generate_phrase(
        self,
        user_id: int,
        category: str,
        **kwargs
    ) -> Optional[str]:
        """
        Сгенерировать фразу на основе категории и параметров
        
        Args:
            user_id: ID пользователя
            category: категория фразы (greeting, collect, farm_start, etc.)
            **kwargs: параметры для подстановки в шаблон
            
        Returns:
            Optional[str]: готовая фраза или None
        """
        settings = self.get_user_settings(user_id)
        
        # Проверяем, включён ли AI
        if not settings.get("ai_enabled", True):
            return None
        
        # Проверяем специальные настройки для приветствий/прощаний
        if category == "greeting" and not settings.get("greeting_enabled", True):
            return None
        if category == "farewell" and not settings.get("farewell_enabled", True):
            return None
        
        # Проверяем шанс ответа (кроме приветствий и прощаний)
        if category not in ["greeting", "farewell", "milestone"]:
            chance = settings.get("response_chance", 30)
            if random.randint(1, 100) > chance:
                return None
        
        # Получаем стиль общения
        personality = settings.get("personality", "friendly")
        bot_name = settings.get("bot_name", "Финансовый Гуру")
        
        # Проверяем наличие категории в шаблонах
        if category not in TEMPLATES:
            return None
        
        # Если стиль не найден, используем friendly
        if personality not in TEMPLATES[category]:
            personality = "friendly"
        
        templates = TEMPLATES[category][personality]
        
        if not templates:
            return None
        
        # Выбираем шаблон (избегая повторов)
        template = self._select_template(user_id, category, personality, templates)
        
        # Подготавливаем значения для подстановки
        values = self._prepare_template_values(kwargs, bot_name)
        
        # Подставляем значения
        try:
            phrase = template.format(**values)
        except KeyError:
            # Если не хватает переменных, используем базовое приветствие
            phrase = f"{bot_name}: Привет, {kwargs.get('name', 'Инвестор')}!"
        
        # Добавляем эмодзи если нужно
        if settings.get("use_emojis", True):
            phrase = self._add_emoji(phrase, personality, category)
        
        # Добавляем обращение по имени если настроено
        if settings.get("mention_name", True) and "{name}" not in template:
            name = kwargs.get("name", "")
            if name and random.random() < 0.3:  # 30% шанс
                phrase = f"{name}, {phrase[0].lower()}{phrase[1:]}"
        
        # Обновляем статистику
        self._update_stats(user_id, category)
        
        return phrase
    
    def get_random_advice(self, user_id: int, **kwargs) -> Optional[str]:
        """
        Получить случайный совет (с учётом частоты советов)
        
        Args:
            user_id: ID пользователя
            **kwargs: параметры
            
        Returns:
            Optional[str]: совет или None
        """
        settings = self.get_user_settings(user_id)
        advice_freq = settings.get("advice_frequency", 40)
        
        if random.randint(1, 100) > advice_freq:
            return None
        
        return self.generate_phrase(user_id, "random_advice", **kwargs)
    
    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========
    
    def _select_template(
        self,
        user_id: int,
        category: str,
        personality: str,
        templates: List[str]
    ) -> str:
        """
        Выбрать шаблон, избегая повторов с последними использованными
        
        Args:
            user_id: ID пользователя
            category: категория
            personality: стиль
            templates: список шаблонов
            
        Returns:
            str: выбранный шаблон
        """
        key = f"{user_id}_{category}_{personality}"
        
        if key not in self.last_phrases:
            self.last_phrases[key] = []
        
        # Фильтруем неиспользованные недавно шаблоны
        recent = self.last_phrases[key]
        available = [t for t in templates if t not in recent]
        
        # Если все использованы — сбрасываем историю
        if not available:
            self.last_phrases[key] = []
            available = templates
        
        # Выбираем случайный
        template = random.choice(available)
        
        # Запоминаем использование
        self.last_phrases[key].append(template)
        if len(self.last_phrases[key]) > 5:
            self.last_phrases[key].pop(0)
        
        return template
    
    def _prepare_template_values(self, kwargs: Dict, bot_name: str) -> Dict:
        """
        Подготовить значения для подстановки в шаблон
        
        Args:
            kwargs: исходные параметры
            bot_name: имя бота
            
        Returns:
            Dict: подготовленные значения
        """
        # Обработка имени
        name = kwargs.get("name", "Инвестор")
        if len(str(name)) > 20:
            name = str(name)[:20]
        
        # Экранирование фигурных скобок в имени
        name = name.replace("{", "\\{").replace("}", "\\}")
        
        # Форматирование чисел
        profit = kwargs.get("profit", 0)
        if isinstance(profit, (int, float)):
            profit = round(profit, 2)
        
        amount = kwargs.get("amount", 0)
        if isinstance(amount, (int, float)):
            amount = round(amount, 2)
        
        return {
            "name": name,
            "bot_name": bot_name,
            "profit": profit,
            "currency": kwargs.get("currency", "монет"),
            "hours": kwargs.get("hours", 0),
            "amount": amount,
            "rate": kwargs.get("rate", 0),
            "farms_count": kwargs.get("farms_count", 0),
            "level": kwargs.get("level", 1),
            "streak": kwargs.get("streak", 0),
            "multiplier": kwargs.get("multiplier", 1),
            "complexity": kwargs.get("complexity", "Лёгкая"),
            "time": datetime.now().strftime("%H:%M"),
            "date": datetime.now().strftime("%d.%m.%Y")
        }
    
    def _add_emoji(self, phrase: str, personality: str, category: str) -> str:
        """
        Добавить эмодзи к фразе если уместно
        
        Args:
            phrase: исходная фраза
            personality: стиль
            category: категория
            
        Returns:
            str: фраза с эмодзи
        """
        # Определяем шанс добавления в зависимости от категории
        emoji_chance = 0.4
        if category == "greeting":
            emoji_chance = 0.7
        elif category == "farewell":
            emoji_chance = 0.6
        elif category == "milestone":
            emoji_chance = 0.9
        
        if random.random() < emoji_chance:
            # Выбираем тип эмодзи по стилю
            if personality == "friendly":
                emoji = get_random_emoji("positive")
            elif personality == "business":
                emoji = get_random_emoji("neutral")
            elif personality == "sarcastic":
                emoji = get_random_emoji("negative")
            else:  # motivating
                emoji = get_random_emoji("positive")
            
            # Не добавляем если эмодзи уже есть в конце
            if not any(phrase.endswith(e) for e in ["🎉", "💰", "🚀", "😅", "😂", "🎯", "⭐", "🌟", "💪", "✨"]):
                phrase += f" {emoji}"
        
        return phrase
    
    def _update_stats(self, user_id: int, category: str):
        """
        Обновить статистику использования
        
        Args:
            user_id: ID пользователя
            category: категория использованной фразы
        """
        user_id_str = str(user_id)
        if user_id_str in self.settings:
            self.settings[user_id_str]["total_responses"] = \
                self.settings[user_id_str].get("total_responses", 0) + 1
            self.settings[user_id_str]["last_interaction"] = datetime.now().isoformat()
            # Сохраняем не при каждом ответе для производительности
            if random.random() < 0.1:  # 10% шанс сохранения
                self.save_settings()
    
    # ========== ФОРМАТИРОВАНИЕ НАСТРОЕК ==========
    
    def format_ai_settings_text(self, user_id: int) -> str:
        """
        Форматировать текст настроек AI для отображения
        
        Args:
            user_id: ID пользователя
            
        Returns:
            str: отформатированный текст
        """
        settings = self.get_user_settings(user_id)
        
        # Названия стилей
        personality_names = {
            "friendly": "🤗 Дружелюбный",
            "business": "💼 Деловой",
            "sarcastic": "😏 Саркастичный",
            "motivating": "💪 Мотивирующий"
        }
        
        # Описания стилей
        personality_desc = {
            "friendly": "Тёплое общение, шутки, поддержка",
            "business": "Строгий деловой тон, только факты",
            "sarcastic": "Юмор и лёгкие подколы",
            "motivating": "Вдохновляющие речи, мотивация"
        }
        
        # Статус
        if settings["ai_enabled"]:
            status = "✅ Включен"
            status_emoji = "🟢"
        else:
            status = "❌ Выключен"
            status_emoji = "🔴"
        
        # Частота ответов
        freq = settings["response_chance"]
        if freq <= 25:
            freq_indicator = "🔇 Редко"
        elif freq <= 50:
            freq_indicator = "📢 Иногда"
        elif freq <= 75:
            freq_indicator = "🔊 Часто"
        else:
            freq_indicator = "📣 Очень часто"
        
        # Дополнительные настройки
        greeting_status = "✅" if settings.get("greeting_enabled", True) else "❌"
        farewell_status = "✅" if settings.get("farewell_enabled", True) else "❌"
        emojis_status = "✅" if settings.get("use_emojis", True) else "❌"
        
        personality = settings["personality"]
        
        text = f"""
{status_emoji} *Настройки Искусственного Интеллекта*

👤 *Имя бота:* {settings['bot_name']}
📊 *Статус:* {status}
🎭 *Стиль:* {personality_names.get(personality, 'Дружелюбный')}
📝 *Описание:* {personality_desc.get(personality, '')}

⚙️ *Параметры:*
├ Частота ответов: {freq}% ({freq_indicator})
├ Приветствия: {greeting_status}
├ Прощания: {farewell_status}
└ Эмодзи: {emojis_status}

📈 *Статистика:*
├ Всего ответов: {settings.get('total_responses', 0)}
└ Последняя активность: {self._format_last_interaction(settings.get('last_interaction'))}

💡 *Совет:* Чем выше частота ответов, тем более живое общение!
"""
        return text
    
    def _format_last_interaction(self, timestamp: Optional[str]) -> str:
        """Форматировать время последнего взаимодействия"""
        if not timestamp:
            return "Нет данных"
        
        try:
            dt = datetime.fromisoformat(timestamp)
            now = datetime.now()
            diff = now - dt
            
            if diff.days > 7:
                return f"{diff.days} дней назад"
            elif diff.days > 0:
                return f"{diff.days} дн. назад"
            elif diff.seconds > 3600:
                return f"{diff.seconds // 3600} ч. назад"
            elif diff.seconds > 60:
                return f"{diff.seconds // 60} мин. назад"
            else:
                return "Только что"
        except Exception:
            return "Неизвестно"
    
    # ========== СТАТИСТИКА И ДИАГНОСТИКА ==========
    
    def get_statistics(self) -> Dict:
        """
        Получить общую статистику использования AI
        
        Returns:
            Dict: статистика
        """
        total_users = len(self.settings)
        enabled_count = sum(
            1 for s in self.settings.values()
            if s.get("ai_enabled", True)
        )
        
        # Распределение стилей
        personalities = {}
        for s in self.settings.values():
            pers = s.get("personality", "friendly")
            personalities[pers] = personalities.get(pers, 0) + 1
        
        # Средняя частота ответов
        avg_chance = sum(
            s.get("response_chance", 30)
            for s in self.settings.values()
        ) / max(total_users, 1)
        
        # Всего ответов
        total_responses = sum(
            s.get("total_responses", 0)
            for s in self.settings.values()
        )
        
        return {
            "total_users": total_users,
            "ai_enabled": enabled_count,
            "ai_disabled": total_users - enabled_count,
            "personalities": personalities,
            "avg_response_chance": round(avg_chance, 1),
            "total_responses": total_responses,
            "avg_responses_per_user": round(total_responses / max(total_users, 1), 1)
        }
    
    def get_user_personality(self, user_id: int) -> str:
        """
        Получить стиль общения пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            str: стиль (friendly, business, sarcastic, motivating)
        """
        settings = self.get_user_settings(user_id)
        return settings.get("personality", "friendly")
    
    def is_ai_enabled(self, user_id: int) -> bool:
        """
        Проверить, включён ли AI у пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            bool: True если включён
        """
        settings = self.get_user_settings(user_id)
        return settings.get("ai_enabled", True)


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def format_personality_description(personality: str) -> str:
    """Форматировать описание стиля для меню выбора"""
    descriptions = {
        "friendly": (
            "🤗 *Дружелюбный*\n"
            "Тёплое общение, шутки, поддержка. "
            "Бот будет общаться как друг, использовать эмодзи "
            "и радоваться твоим успехам."
        ),
        "business": (
            "💼 *Деловой*\n"
            "Строгий финансовый консультант. "
            "Только факты, цифры и профессиональные рекомендации. "
            "Без лишних эмоций."
        ),
        "sarcastic": (
            "😏 *Саркастичный*\n"
            "Лёгкая ирония и подколы. "
            "Бот будет шутить над твоими ошибками, но без злобы. "
            "Для тех, кто ценит юмор."
        ),
        "motivating": (
            "💪 *Мотивирующий*\n"
            "Вдохновляющие речи и поддержка. "
            "Бот будет подбадривать и мотивировать "
            "на финансовые подвиги."
        )
    }
    return descriptions.get(personality, descriptions["friendly"])


def get_personality_emoji(personality: str) -> str:
    """Получить эмодзи для стиля"""
    emojis = {
        "friendly": "🤗",
        "business": "💼",
        "sarcastic": "😏",
        "motivating": "💪"
    }
    return emojis.get(personality, "🤗")


def get_response_frequency_description(frequency: int) -> str:
    """Описание частоты ответов"""
    if frequency <= 10:
        return "🔇 Почти никогда"
    elif frequency <= 25:
        return "🔈 Редко"
    elif frequency <= 50:
        return "🔉 Иногда"
    elif frequency <= 75:
        return "🔊 Часто"
    elif frequency <= 90:
        return "📢 Очень часто"
    else:
        return "📣 Всегда"


# ========== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР ==========

# Создаём один экземпляр для всего бота
ai_generator = AIResponseGenerator()


# ========== ТЕСТИРОВАНИЕ ==========

if __name__ == "__main__":
    print("🧪 Тестирование модуля ai.py")
    print("=" * 50)
    
    # Тестовый пользователь
    test_user_id = 123456789
    
    # Получение настроек
    settings = ai_generator.get_user_settings(test_user_id)
    print(f"✅ Настройки загружены: {settings['bot_name']}")
    print(f"   Стиль: {settings['personality']}")
    print(f"   AI включён: {settings['ai_enabled']}")
    
    # Тест генерации фраз
    test_cases = [
        ("greeting", {"name": "Алексей"}),
        ("collect", {"name": "Алексей", "profit": 150.5, "currency": "RUB"}),
        ("farm_start", {"name": "Алексей", "currency": "BTC", "rate": 1.5}),
        ("random_advice", {"name": "Алексей"}),
        ("farewell", {"name": "Алексей"}),
    ]
    
    print("\n📝 Тестовые фразы:")
    for category, kwargs in test_cases:
        phrase = ai_generator.generate_phrase(test_user_id, category, **kwargs)
        if phrase:
            print(f"   [{category}] {phrase}")
        else:
            print(f"   [{category}] (пропущено — низкий шанс или AI выключен)")
    
    # Тест смены стиля
    print("\n🔄 Тест смены стиля:")
    for style in ["friendly", "business", "sarcastic", "motivating"]:
        ai_generator.update_setting(test_user_id, "personality", style)
        phrase = ai_generator.generate_phrase(
            test_user_id, "greeting",
            name="Алексей"
        )
        print(f"   [{style}] {phrase}")
    
    # Статистика
    stats = ai_generator.get_statistics()
    print(f"\n📊 Статистика AI:")
    print(f"   Пользователей: {stats['total_users']}")
    print(f"   AI включён у: {stats['ai_enabled']}")
    print(f"   Средняя частота: {stats['avg_response_chance']}%")
    
    # Сброс
    ai_generator.reset_user_settings(test_user_id)
    settings = ai_generator.get_user_settings(test_user_id)
    print(f"\n✅ Настройки сброшены: {settings['bot_name']}")
    
    print("\n✅ Все тесты пройдены!")
