import asyncio
import logging
from datetime import datetime
from os import getenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from database import DatabaseManager
from config import Config



# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=Config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = DatabaseManager()

from user_handlers import register_user_handlers
register_user_handlers(dp, db)

# FSM состояния
class UserRegistration(StatesGroup):
    waiting_fullname = State()
    waiting_phone = State()

class AdminCalendar(StatesGroup):
    selecting_date = State()
    selecting_vacancy = State()
    selecting_shift = State()
    entering_count = State()

class UserReservation(StatesGroup):
    selecting_date = State()
    selecting_vacancy = State()
    selecting_shift = State()
    confirming = State()

# Основные кнопки
def get_main_menu_keyboard(is_admin=False):
    """Главное меню с разными кнопками для админа и пользователя"""
    if is_admin:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Управление календарем", callback_data="admin_calendar")],
            [InlineKeyboardButton(text="📋 Управление справочником", callback_data="admin_handbook")],
            [InlineKeyboardButton(text="✅ Подтверждение записей", callback_data="admin_confirmations")],
            [InlineKeyboardButton(text="📊 Отчеты", callback_data="admin_reports")],
            [InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin_users")],
            [InlineKeyboardButton(text="📢 Рассылка уведомлений", callback_data="admin_broadcast")]
        ])
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Записаться на работу", callback_data="user_reserve")],
            [InlineKeyboardButton(text="✏️ Редактировать запись", callback_data="user_edit")],
            [InlineKeyboardButton(text="📖 Справочник", callback_data="user_handbook")],
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="user_refresh")]
        ])
    return keyboard

def get_back_keyboard():
    """Кнопка возврата"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])

def get_calendar_keyboard(year, month, reserved_dates=None):
    """Создание календаря на 7 дней вперед"""
    from datetime import date, timedelta
    
    keyboard = []
    today = date.today()
    
    for i in range(7):
        current_date = today + timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")
        
        # Проверяем, есть ли записи на эту дату
        status = ""
        if reserved_dates and date_str in reserved_dates:
            status = " ✅" if reserved_dates[date_str]['filled'] else " 🟡"
        
        button_text = f"{current_date.strftime('%d.%m')} ({current_date.strftime('%a')}){status}"
        keyboard.append([InlineKeyboardButton(
            text=button_text, 
            callback_data=f"date_{date_str}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Стартовая команда
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    
    # Проверяем регистрацию пользователя
    user = await db.get_user(user_id)
    
    if not user:
        # Новый пользователь - предлагаем регистрацию
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Зарегистрироваться", callback_data="register")],
            [InlineKeyboardButton(text="📖 Справочник", callback_data="user_handbook")]
        ])
        
        await message.answer(
            "👋 Добро пожаловать в бот приема на работу!\n\n"
            "Для начала работы необходимо зарегистрироваться.\n"
            "Справочник можно посмотреть без регистрации.",
            reply_markup=keyboard
        )
    else:
        # Проверяем статус пользователя
        if user['is_blocked']:
            await message.answer("❌ Ваш аккаунт заблокирован. Обратитесь к администратору.")
            return
        
        if user['is_banned']:
            await message.answer("⚠️ Ваш аккаунт забанен. Некоторые функции недоступны.")
        
        # Показываем главное меню
        is_admin = user['is_admin']
        welcome_text = "👨‍💼 Панель администратора" if is_admin else "👤 Главное меню"
        
        await message.answer(
            f"{welcome_text}\n\nВыберите действие:",
            reply_markup=get_main_menu_keyboard(is_admin)
        )

# Регистрация пользователя
@dp.callback_query(F.data == "register")
async def process_register(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 Регистрация\n\nВведите ваше полное имя (Фамилия Имя Отчество):",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(UserRegistration.waiting_fullname)

@dp.message(UserRegistration.waiting_fullname)
async def process_fullname(message: types.Message, state: FSMContext):
    full_name = message.text.strip()
    
    if len(full_name) < 5:
        await message.answer("❌ Пожалуйста, введите полное имя (минимум 5 символов):")
        return
    
    await state.update_data(full_name=full_name)
    await message.answer(
        "📱 Теперь введите ваш номер телефона в формате +7XXXXXXXXXX:",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(UserRegistration.waiting_phone)

@dp.message(UserRegistration.waiting_phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    
    # Простая валидация телефона
    if not phone.startswith('+7') or len(phone) != 12:
        await message.answer("❌ Неверный формат телефона. Введите в формате +7XXXXXXXXXX:")
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    full_name = data['full_name']
    
    # Сохраняем пользователя в БД
    user_id = message.from_user.id
    username = message.from_user.username or ""
    
    await db.register_user(user_id, full_name, phone, username)
    
    await message.answer(
        "✅ Регистрация успешно завершена!\n\n"
        f"Имя: {full_name}\n"
        f"Телефон: {phone}\n\n"
        "Теперь вы можете пользоваться всеми функциями бота.",
        reply_markup=get_main_menu_keyboard(False)
    )
    
    await state.clear()

# Обработка кнопки "Назад"
@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Зарегистрироваться", callback_data="register")],
            [InlineKeyboardButton(text="📖 Справочник", callback_data="user_handbook")]
        ])
        
        await callback.message.edit_text(
            "👋 Добро пожаловать в бот приема на работу!\n\n"
            "Для начала работы необходимо зарегистрироваться.\n"
            "Справочник можно посмотреть без регистрации.",
            reply_markup=keyboard
        )
    else:
        is_admin = user['is_admin']
        welcome_text = "👨‍💼 Панель администратора" if is_admin else "👤 Главное меню"
        
        await callback.message.edit_text(
            f"{welcome_text}\n\nВыберите действие:",
            reply_markup=get_main_menu_keyboard(is_admin)
        )

# Просмотр справочника
@dp.callback_query(F.data == "user_handbook")
async def show_handbook(callback: types.CallbackQuery):
    handbook_text = await db.get_handbook()
    
    if not handbook_text:
        handbook_text = "📖 Справочник пока не заполнен администратором."
    
    await callback.message.edit_text(
        f"📖 Справочник вакансий\n\n{handbook_text}",
        reply_markup=get_back_keyboard()
    )

# Команда /handbook для быстрого доступа к справочнику
@dp.message(Command("handbook"))
async def cmd_handbook(message: types.Message):
    handbook_text = await db.get_handbook()
    
    if not handbook_text:
        handbook_text = "📖 Справочник пока не заполнен администратором."
    
    await message.answer(f"📖 Справочник вакансий\n\n{handbook_text}")

# Запуск бота
async def main():
    try:
        # Инициализация базы данных
        await db.init_db()
        
        # Запуск поллинга
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())