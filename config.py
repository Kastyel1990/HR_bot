import os
from typing import Optional

class Config:
    """Конфигурация приложения"""
    
    # Токен бота Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    
    # Настройки базы данных MSSQL
    DB_SERVER: str = os.getenv("DB_SERVER", "localhost")
    DB_NAME: str = os.getenv("DB_NAME", "WorkBot")
    DB_USER: str = os.getenv("DB_USER", "sa")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "your_password")
    
    # Настройки бота
    MAX_RESERVATIONS_PER_USER: int = 1  # Максимум записей на одну дату
    CALENDAR_DAYS_AHEAD: int = 7  # Количество дней календаря вперед
    
    # Сообщения
    WELCOME_MESSAGE = """
👋 Добро пожаловать в бот приема на работу!

Здесь вы можете:
• Записаться на работу
• Просмотреть справочник вакансий
• Управлять своими записями

Для начала работы необходимо зарегистрироваться.
    """
    
    ADMIN_WELCOME_MESSAGE = """
👨‍💼 Панель администратора

Доступные функции:
• Управление календарем работы
• Редактирование справочника
• Подтверждение записей
• Просмотр отчетов и статистики
• Управление пользователями
    """
    
    REGISTRATION_SUCCESS = """
✅ Регистрация успешно завершена!

Теперь вы можете пользоваться всеми функциями бота.
    """
    
    # Валидация конфигурации
    @classmethod
    def validate(cls) -> bool:
        """Проверка корректности конфигурации"""
        if cls.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            print("❌ Не установлен токен бота! Установите переменную окружения BOT_TOKEN")
            return False
        
        if not all([cls.DB_SERVER, cls.DB_NAME, cls.DB_USER, cls.DB_PASSWORD]):
            print("❌ Не все параметры базы данных настроены!")
            return False
        
        return True

# Эмодзи для интерфейса
class Emoji:
    # Основные действия
    REGISTER = "📝"
    CALENDAR = "📅"
    HANDBOOK = "📖"
    STATS = "📊"
    USERS = "👥"
    SETTINGS = "⚙️"
    
    # Статусы
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    
    # Навигация
    BACK = "⬅️"
    FORWARD = "➡️"
    HOME = "🏠"
    REFRESH = "🔄"
    
    # Роли
    ADMIN = "👨‍💼"
    USER = "👤"
    
    # Состояния
    AVAILABLE = "🟢"
    BUSY = "🔴"
    PARTIAL = "🟡"
    
    # Действия с пользователями
    BAN = "🚫"
    UNBAN = "✅"
    BLOCK = "🔒"
    UNBLOCK = "🔓"

# Тексты кнопок
class ButtonText:
    # Основное меню пользователя
    USER_RESERVE = f"{Emoji.REGISTER} Записаться на работу"
    USER_EDIT = f"✏️ Редактировать запись"
    USER_HANDBOOK = f"{Emoji.HANDBOOK} Справочник"
    USER_REFRESH = f"{Emoji.REFRESH} Обновить"
    
    # Основное меню админа
    ADMIN_CALENDAR = f"{Emoji.CALENDAR} Управление календарем"
    ADMIN_HANDBOOK = f"{Emoji.HANDBOOK} Управление справочником"
    ADMIN_CONFIRMATIONS = f"{Emoji.SUCCESS} Подтверждение записей"
    ADMIN_REPORTS = f"{Emoji.STATS} Отчеты"
    ADMIN_USERS = f"{Emoji.USERS} Управление пользователями"
    ADMIN_BROADCAST = "📢 Рассылка уведомлений"
    
    # Навигация
    BACK = f"{Emoji.BACK} Назад"
    TO_MAIN = f"{Emoji.HOME} В главное меню"
    REFRESH = f"{Emoji.REFRESH} Обновить"
    
    # Действия
    CONFIRM = f"{Emoji.SUCCESS} Подтвердить"
    CANCEL = f"{Emoji.ERROR} Отменить"
    EDIT = "✏️ Редактировать"
    DELETE = "🗑️ Удалить"
    
    # Управление пользователями
    BAN_USER = f"{Emoji.BAN} Забанить"
    UNBAN_USER = f"{Emoji.UNBAN} Разбанить"
    BLOCK_USER = f"{Emoji.BLOCK} Заблокировать"
    UNBLOCK_USER = f"{Emoji.UNBLOCK} Разблокировать"

# Форматирование сообщений
class MessageFormatter:
    @staticmethod
    def format_user_info(user: dict) -> str:
        """Форматирование информации о пользователе"""
        status_icons = []
        if user.get('is_admin'):
            status_icons.append(f"{Emoji.ADMIN} Админ")
        if user.get('is_banned'):
            status_icons.append(f"{Emoji.BAN} Забанен")
        if user.get('is_blocked'):
            status_icons.append(f"{Emoji.BLOCK} Заблокирован")
        
        status = " | ".join(status_icons) if status_icons else f"{Emoji.USER} Пользователь"
        
        return f"""
👤 {user['full_name']}
📱 {user['phone']}
🆔 @{user.get('username', 'без username')}
📅 Регистрация: {user['date_of_reg'].strftime('%d.%m.%Y')}
📊 Статус: {status}
        """.strip()
    
    @staticmethod
    def format_reservation(reservation: dict) -> str:
        """Форматирование информации о резервации"""
        return f"""
📅 Дата: {reservation['date_reservation'].strftime('%d.%m.%Y')}
👔 Должность: {reservation['vacancy_name']}
🕐 Смена: {reservation['shift_name']}
⏰ Время записи: {reservation['date_time_event'].strftime('%d.%m.%Y %H:%M')}
        """.strip()
    
    @staticmethod
    def format_statistics_item(stat: dict) -> str:
        """Форматирование элемента статистики"""
        fill_percentage = stat['fill_percentage']
        status_emoji = Emoji.SUCCESS if fill_percentage >= 100 else Emoji.PARTIAL if fill_percentage > 0 else Emoji.ERROR
        
        return f"""
{status_emoji} {stat['shift_name']} - {stat['vacancy_name']}
План: {stat['need_count']} | Записано: {stat['reserved_count']} | {fill_percentage}%
        """.strip()
    
    @staticmethod
    def format_calendar_day(date_obj, status_info=None) -> str:
        """Форматирование дня календаря"""
        day_name = {
            0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 
            4: "Пт", 5: "Сб", 6: "Вс"
        }[date_obj.weekday()]
        
        status_emoji = ""
        if status_info:
            if status_info.get('filled'):
                status_emoji = f" {Emoji.SUCCESS}"
            elif status_info.get('total_reserved', 0) > 0:
                status_emoji = f" {Emoji.PARTIAL}"
        
        return f"{date_obj.strftime('%d.%m')} ({day_name}){status_emoji}"