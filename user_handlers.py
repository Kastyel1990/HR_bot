from datetime import date, timedelta
from aiogram import types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config import ButtonText, Emoji, MessageFormatter
from database import DatabaseManager

# Функции для создания клавиатур
def create_date_keyboard(available_dates: dict, prefix: str = "user_date") -> InlineKeyboardMarkup:
    """Создание клавиатуры с датами"""
    keyboard = []
    today = date.today()
    
    for i in range(7):
        current_date = today + timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")
        
        # Проверяем доступность даты
        if date_str in available_dates:
            status_emoji = Emoji.PARTIAL if available_dates[date_str]['available_count'] > 0 else Emoji.BUSY
            button_text = MessageFormatter.format_calendar_day(current_date) + f" {status_emoji}"
        else:
            button_text = MessageFormatter.format_calendar_day(current_date) + f" {Emoji.ERROR}"
            continue  # Пропускаем даты без вакансий
        
        keyboard.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"{prefix}_{date_str}"
        )])
    
    keyboard.append([InlineKeyboardButton(text=ButtonText.REFRESH, callback_data="user_refresh")])
    keyboard.append([InlineKeyboardButton(text=ButtonText.BACK, callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_vacancy_keyboard(vacancies: list, date_str: str, prefix: str = "user_vacancy") -> InlineKeyboardMarkup:
    """Создание клавиатуры с вакансиями"""
    keyboard = []
    
    for vacancy in vacancies:
        button_text = f"{vacancy['vacancy_name']} ({vacancy['available_count']} мест)"
        keyboard.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"{prefix}_{date_str}_{vacancy['id_vacancy']}"
        )])
    
    keyboard.append([InlineKeyboardButton(text=ButtonText.BACK, callback_data="user_reserve")])
    keyboard.append([InlineKeyboardButton(text=ButtonText.TO_MAIN, callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_shift_keyboard(shifts: list, date_str: str, vacancy_id: int, prefix: str = "user_shift") -> InlineKeyboardMarkup:
    """Создание клавиатуры со сменами"""
    keyboard = []
    
    for shift in shifts:
        button_text = f"{shift['shift_name']} ({shift['available_count']} мест)"
        keyboard.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"{shift}_{date_str}_{vacancy_id}_{shift['id_shift']}"
        )])
    
    keyboard.append([InlineKeyboardButton(text=ButtonText.BACK, callback_data=f"user_vacancy_{date_str}")])
    keyboard.append([InlineKeyboardButton(text=ButtonText.TO_MAIN, callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_confirmation_keyboard(date_str: str, vacancy_id: int, shift_id: int) -> InlineKeyboardMarkup:
    """Создание клавиатуры подтверждения"""
    keyboard = [
        [InlineKeyboardButton(
            text=f"{Emoji.SUCCESS} Подтвердить запись",
            callback_data=f"user_confirm_{date_str}_{vacancy_id}_{shift_id}"
        )],
        [InlineKeyboardButton(
            text=ButtonText.BACK,
            callback_data=f"user_shift_{date_str}_{vacancy_id}"
        )],
        [InlineKeyboardButton(
            text=ButtonText.TO_MAIN,
            callback_data="back_to_main"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_user_reservations_keyboard(reservations: list) -> InlineKeyboardMarkup:
    """Создание клавиатуры с резервациями пользователя"""
    keyboard = []
    
    for reservation in reservations:
        date_str = reservation['date_reservation'].strftime('%Y-%m-%d')
        button_text = f"{reservation['date_reservation'].strftime('%d.%m')} - {reservation['vacancy_name']} ({reservation['shift_name']})"
        keyboard.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"user_edit_reservation_{reservation['id']}"
        )])
    
    if not reservations:
        keyboard.append([InlineKeyboardButton(
            text="📝 Сделать новую запись",
            callback_data="user_reserve"
        )])
    
    keyboard.append([InlineKeyboardButton(text=ButtonText.BACK, callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Обработчики пользовательских действий
async def handle_user_reserve(callback: types.CallbackQuery, db: DatabaseManager):
    """Начало процесса записи пользователя"""
    user_id = callback.from_user.id
    
    # Проверяем регистрацию
    user = await db.get_user(user_id)
    if not user:
        await callback.answer("❌ Сначала необходимо зарегистрироваться!")
        return
    
    if user['is_blocked']:
        await callback.answer("❌ Ваш аккаунт заблокирован.")
        return
    
    if user['is_banned']:
        await callback.answer("⚠️ Ваш аккаунт забанен. Функция недоступна.")
        return
    
    # Получаем доступные даты
    available_dates = {}
    today = date.today()
    
    for i in range(7):
        current_date = today + timedelta(days=i)
        slots = await db.get_available_slots(current_date)
        
        if slots:
            date_str = current_date.strftime("%Y-%m-%d")
            total_available = sum(slot['available_count'] for slot in slots)
            available_dates[date_str] = {'available_count': total_available}
    
    if not available_dates:
        await callback.message.edit_text(
            f"{Emoji.INFO} К сожалению, на ближайшие 7 дней нет доступных вакансий.\n\n"
            "Попробуйте обновить позже или обратитесь к администратору.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=ButtonText.REFRESH, callback_data="user_reserve")],
                [InlineKeyboardButton(text=ButtonText.BACK, callback_data="back_to_main")]
            ])
        )
        return
    
    await callback.message.edit_text(
        f"{Emoji.CALENDAR} Выберите дату для записи:\n\n"
        f"{Emoji.SUCCESS} - есть свободные места\n"
        f"{Emoji.PARTIAL} - места ограничены\n"
        f"{Emoji.BUSY} - мест нет",
        reply_markup=create_date_keyboard(available_dates)
    )

async def handle_user_date_selection(callback: types.CallbackQuery, db: DatabaseManager):
    """Обработка выбора даты"""
    date_str = callback.data.split('_')[-1]
    selected_date = date.fromisoformat(date_str)
    
    # Получаем доступные вакансии на выбранную дату
    slots = await db.get_available_slots(selected_date)
    
    if not slots:
        await callback.answer("❌ На выбранную дату нет доступных мест!")
        return
    
    # Группируем по вакансиям
    vacancies = {}
    for slot in slots:
        if slot['id_vacancy'] not in vacancies:
            vacancies[slot['id_vacancy']] = {
                'id_vacancy': slot['id_vacancy'],
                'vacancy_name': slot['vacancy_name'],
                'available_count': 0
            }
        vacancies[slot['id_vacancy']]['available_count'] += slot['available_count']
    
    vacancy_list = list(vacancies.values())
    
    await callback.message.edit_text(
        f"{Emoji.REGISTER} Запись на {selected_date.strftime('%d.%m.%Y')}\n\n"
        "Выберите должность:",
        reply_markup=create_vacancy_keyboard(vacancy_list, date_str)
    )

async def handle_user_vacancy_selection(callback: types.CallbackQuery, db: DatabaseManager):
    """Обработка выбора вакансии"""
    parts = callback.data.split('_')
    date_str = parts[-2]
    vacancy_id = int(parts[-1])
    
    selected_date = date.fromisoformat(date_str)
    
    # Получаем доступные смены для выбранной вакансии
    slots = await db.get_available_slots(selected_date)
    available_shifts = [
        slot for slot in slots 
        if slot['id_vacancy'] == vacancy_id and slot['available_count'] > 0
    ]
    
    if not available_shifts:
        await callback.answer("❌ На выбранную вакансию нет доступных смен!")
        return
    
    # Получаем название вакансии
    vacancy_name = available_shifts[0]['vacancy_name']
    
    await callback.message.edit_text(
        f"{Emoji.REGISTER} Запись на {selected_date.strftime('%d.%m.%Y')}\n"
        f"Должность: {vacancy_name}\n\n"
        "Выберите смену:",
        reply_markup=create_shift_keyboard(available_shifts, date_str, vacancy_id)
    )

async def handle_user_shift_selection(callback: types.CallbackQuery, db: DatabaseManager):
    """Обработка выбора смены"""
    parts = callback.data.split('_')
    date_str = parts[-3]
    vacancy_id = int(parts[-2])
    shift_id = int(parts[-1])
    
    selected_date = date.fromisoformat(date_str)
    
    # Получаем информацию о выбранном слоте
    slots = await db.get_available_slots(selected_date)
    selected_slot = next(
        (slot for slot in slots 
         if slot['id_vacancy'] == vacancy_id and slot['id_shift'] == shift_id),
        None
    )
    
    if not selected_slot or selected_slot['available_count'] <= 0:
        await callback.answer("❌ Выбранное место уже занято!")
        return
    
    # Формируем сообщение подтверждения
    confirmation_text = f"""
{Emoji.SUCCESS} Подтверждение записи

📅 Дата: {selected_date.strftime('%d.%m.%Y (%A)')}
👔 Должность: {selected_slot['vacancy_name']}
🕐 Смена: {selected_slot['shift_name']}
📊 Доступно мест: {selected_slot['available_count']}

Подтвердить запись?
    """
    
    await callback.message.edit_text(
        confirmation_text,
        reply_markup=create_confirmation_keyboard(date_str, vacancy_id, shift_id)
    )

async def handle_user_confirmation(callback: types.CallbackQuery, db: DatabaseManager):
    """Подтверждение записи пользователя"""
    parts = callback.data.split('_')
    date_str = parts[-3]
    vacancy_id = int(parts[-2])
    shift_id = int(parts[-1])
    
    user_id = callback.from_user.id
    selected_date = date.fromisoformat(date_str)
    
    # Проверяем, нет ли уже записи пользователя на эту дату
    existing_reservations = await db.get_user_reservations(user_id)
    if any(res['date_reservation'] == selected_date for res in existing_reservations):
        await callback.answer("❌ У вас уже есть запись на эту дату!")
        return
    
    # Создаем резервацию
    reservation_id = await db.make_reservation(user_id, selected_date, shift_id, vacancy_id)
    
    if not reservation_id:
        await callback.message.edit_text(
            f"{Emoji.ERROR} Не удалось создать запись!\n\n"
            "Возможные причины:\n"
            "• Места уже заняты\n"
            "• У вас уже есть запись на эту дату\n\n"
            "Попробуйте выбрать другое время или обновите информацию.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="user_reserve")],
                [InlineKeyboardButton(text=ButtonText.TO_MAIN, callback_data="back_to_main")]
            ])
        )
        return
    
    # Получаем информацию о созданной записи
    slots = await db.get_available_slots(selected_date)
    selected_slot = next(
        (slot for slot in slots 
         if slot['id_vacancy'] == vacancy_id and slot['id_shift'] == shift_id),
        None
    )
    
    success_text = f"""
{Emoji.SUCCESS} Запись успешно создана!

📅 Дата: {selected_date.strftime('%d.%m.%Y (%A)')}
👔 Должность: {selected_slot['vacancy_name']}
🕐 Смена: {selected_slot['shift_name']}
🆔 Номер записи: {reservation_id}

{Emoji.INFO} Администратор свяжется с вами для подтверждения.
До подтверждения вы можете редактировать запись.
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать запись", callback_data="user_edit")],
        [InlineKeyboardButton(text="📝 Записаться еще", callback_data="user_reserve")],
        [InlineKeyboardButton(text=ButtonText.TO_MAIN, callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(success_text, reply_markup=keyboard)
    
    # TODO: Отправить уведомление администратору о новой записи

async def handle_user_edit_reservations(callback: types.CallbackQuery, db: DatabaseManager):
    """Показ списка записей пользователя для редактирования"""
    user_id = callback.from_user.id
    
    reservations = await db.get_user_reservations(user_id)
    
    if not reservations:
        await callback.message.edit_text(
            f"{Emoji.INFO} У вас нет активных записей.\n\n"
            "Хотите записаться на работу?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Записаться", callback_data="user_reserve")],
                [InlineKeyboardButton(text=ButtonText.BACK, callback_data="back_to_main")]
            ])
        )
        return
    
    reservations_text = f"{Emoji.INFO} Ваши записи:\n\n"
    for i, reservation in enumerate(reservations, 1):
        reservations_text += f"{i}. {MessageFormatter.format_reservation(reservation)}\n\n"
    
    reservations_text += "Выберите запись для редактирования:"
    
    await callback.message.edit_text(
        reservations_text,
        reply_markup=create_user_reservations_keyboard(reservations)
    )

async def handle_edit_specific_reservation(callback: types.CallbackQuery, db: DatabaseManager):
    """Редактирование конкретной записи"""
    reservation_id = int(callback.data.split('_')[-1])
    
    # Получаем информацию о записи
    user_id = callback.from_user.id
    reservations = await db.get_user_reservations(user_id)
    reservation = next((r for r in reservations if r['id'] == reservation_id), None)
    
    if not reservation:
        await callback.answer("❌ Запись не найдена!")
        return
    
    edit_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🗑️ Отменить запись",
            callback_data=f"user_cancel_reservation_{reservation_id}"
        )],
        [InlineKeyboardButton(
            text="📅 Изменить дату",
            callback_data=f"user_change_date_{reservation_id}"
        )],
        [InlineKeyboardButton(
            text="👔 Изменить должность",
            callback_data=f"user_change_vacancy_{reservation_id}"
        )],
        [InlineKeyboardButton(
            text="🕐 Изменить смену",
            callback_data=f"user_change_shift_{reservation_id}"
        )],
        [InlineKeyboardButton(text=ButtonText.BACK, callback_data="user_edit")],
        [InlineKeyboardButton(text=ButtonText.TO_MAIN, callback_data="back_to_main")]
    ])
    
    edit_text = f"""
✏️ Редактирование записи

{MessageFormatter.format_reservation(reservation)}

Что хотите изменить?
    """
    
    await callback.message.edit_text(edit_text, reply_markup=edit_keyboard)

async def handle_cancel_reservation(callback: types.CallbackQuery, db: DatabaseManager):
    """Отмена записи пользователя"""
    reservation_id = int(callback.data.split('_')[-1])
    
    # Подтверждение отмены
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{Emoji.ERROR} Да, отменить запись",
            callback_data=f"user_confirm_cancel_{reservation_id}"
        )],
        [InlineKeyboardButton(
            text=ButtonText.BACK,
            callback_data=f"user_edit_reservation_{reservation_id}"
        )]
    ])
    
    await callback.message.edit_text(
        f"{Emoji.WARNING} Подтверждение отмены\n\n"
        "Вы действительно хотите отменить запись?\n"
        "Это действие нельзя будет отменить.",
        reply_markup=confirm_keyboard
    )

async def handle_confirm_cancel_reservation(callback: types.CallbackQuery, db: DatabaseManager):
    """Подтверждение отмены записи"""
    reservation_id = int(callback.data.split('_')[-1])
    
    try:
        await db.delete_reservation(reservation_id)
        
        await callback.message.edit_text(
            f"{Emoji.SUCCESS} Запись успешно отменена!\n\n"
            "Вы можете создать новую запись в любое время.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Записаться снова", callback_data="user_reserve")],
                [InlineKeyboardButton(text=ButtonText.TO_MAIN, callback_data="back_to_main")]
            ])
        )
    except Exception as e:
        await callback.message.edit_text(
            f"{Emoji.ERROR} Ошибка при отмене записи!\n\n"
            "Попробуйте позже или обратитесь к администратору.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=ButtonText.BACK, callback_data="user_edit")],
                [InlineKeyboardButton(text=ButtonText.TO_MAIN, callback_data="back_to_main")]
            ])
        )

async def handle_user_refresh(callback: types.CallbackQuery, db: DatabaseManager):
    """Обновление информации для пользователя"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден!")
        return
    
    # Возвращаемся в главное меню с обновленной информацией
    is_admin = user['is_admin']
    welcome_text = "👨‍💼 Панель администратора" if is_admin else "👤 Главное меню"
    
    await callback.message.edit_text(
        f"{welcome_text}\n\n🔄 Информация обновлена\n\nВыберите действие:",
        reply_markup=get_main_menu_keyboard(is_admin)
    )

# Дополнительные утилиты
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

# Регистрация обработчиков (для использования в main.py)
def register_user_handlers(dp, db: DatabaseManager):
    """Регистрация всех обработчиков пользователей"""
    
    # Основные пользовательские действия
    @dp.callback_query(F.data == "user_reserve")
    async def user_reserve_callback(callback: types.CallbackQuery):
        await handle_user_reserve(callback, db)
    
    @dp.callback_query(F.data.startswith("user_date_"))
    async def user_date_callback(callback: types.CallbackQuery):
        await handle_user_date_selection(callback, db)
    
    @dp.callback_query(F.data.startswith("user_vacancy_"))
    async def user_vacancy_callback(callback: types.CallbackQuery):
        await handle_user_vacancy_selection(callback, db)
    
    @dp.callback_query(F.data.startswith("user_shift_"))
    async def user_shift_callback(callback: types.CallbackQuery):
        await handle_user_shift_selection(callback, db)
    
    @dp.callback_query(F.data.startswith("user_confirm_"))
    async def user_confirm_callback(callback: types.CallbackQuery):
        if callback.data.startswith("user_confirm_cancel_"):
            await handle_confirm_cancel_reservation(callback, db)
        else:
            await handle_user_confirmation(callback, db)
    
    # Редактирование записей
    @dp.callback_query(F.data == "user_edit")
    async def user_edit_callback(callback: types.CallbackQuery):
        await handle_user_edit_reservations(callback, db)
    
    @dp.callback_query(F.data.startswith("user_edit_reservation_"))
    async def user_edit_specific_callback(callback: types.CallbackQuery):
        await handle_edit_specific_reservation