from datetime import date, timedelta
from aiogram import types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ButtonText, Emoji, MessageFormatter, Config
from database import DatabaseManager

# FSM состояния для админского календаря
class AdminCalendarFSM(StatesGroup):
    selecting_date = State()
    selecting_shift = State()
    selecting_vacancy = State()
    entering_count = State()

class AdminHandbookFSM(StatesGroup):
    editing = State()

class AdminBroadcastFSM(StatesGroup):
    waiting_text = State()

# --- Состояния для поиска пользователя ---
class AdminUserSearch(StatesGroup):
    waiting_user_search = State()

# --- Клавиатуры ---
def admin_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ButtonText.ADMIN_CALENDAR, callback_data="admin_calendar")],
        [InlineKeyboardButton(text=ButtonText.ADMIN_HANDBOOK, callback_data="admin_handbook")],
        [InlineKeyboardButton(text=ButtonText.ADMIN_CONFIRMATIONS, callback_data="admin_confirmations")],
        [InlineKeyboardButton(text=ButtonText.ADMIN_REPORTS, callback_data="admin_reports")],
        [InlineKeyboardButton(text=ButtonText.ADMIN_USERS, callback_data="admin_users")],
        [InlineKeyboardButton(text=ButtonText.ADMIN_BROADCAST, callback_data="admin_broadcast")]
    ])

def back_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ButtonText.BACK, callback_data="back_to_admin")]
    ])

def to_admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ButtonText.TO_MAIN, callback_data="back_to_admin")]
    ])

def calendar_days_keyboard(calendar_status, prefix="admin_cal_date"):
    today = date.today()
    keyboard = []
    for i in range(Config.CALENDAR_DAYS_AHEAD):
        d = today + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        status_info = calendar_status.get(date_str, {})
        btn_text = MessageFormatter.format_calendar_day(d, status_info)
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"{prefix}_{date_str}")])
    keyboard.append([InlineKeyboardButton(text=ButtonText.BACK, callback_data="back_to_admin")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def shift_keyboard(shifts, date_str):
    keyboard = [
        [InlineKeyboardButton(text=s['name'], callback_data=f"admin_shift_{date_str}_{s['id']}")]
        for s in shifts
    ]
    keyboard.append([InlineKeyboardButton(text=ButtonText.BACK, callback_data="admin_calendar")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def vacancy_keyboard(vacancies, date_str, shift_id):
    keyboard = [
        [InlineKeyboardButton(text=v['name'], callback_data=f"admin_vacancy_{date_str}_{shift_id}_{v['id']}")]
        for v in vacancies
    ]
    keyboard.append([InlineKeyboardButton(text=ButtonText.BACK, callback_data=f"admin_shift_back_{date_str}")])
    keyboard.append([InlineKeyboardButton(text=ButtonText.TO_MAIN, callback_data="back_to_admin")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def users_filter_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сегодня", callback_data="admin_users_filter_today")],
        [InlineKeyboardButton(text="Все", callback_data="admin_users_filter_all")],
        [InlineKeyboardButton(text=ButtonText.BACK, callback_data="back_to_admin")]
    ])

def user_action_keyboard(user):
    actions = []
    if user['is_banned']:
        actions.append(InlineKeyboardButton(text=ButtonText.UNBAN_USER, callback_data=f"admin_unban_{user['tg_id']}"))
    else:
        actions.append(InlineKeyboardButton(text=ButtonText.BAN_USER, callback_data=f"admin_ban_{user['tg_id']}"))
    if user['is_blocked']:
        actions.append(InlineKeyboardButton(text=ButtonText.UNBLOCK_USER, callback_data=f"admin_unblock_{user['tg_id']}"))
    else:
        actions.append(InlineKeyboardButton(text=ButtonText.BLOCK_USER, callback_data=f"admin_block_{user['tg_id']}"))
    actions.append(InlineKeyboardButton(text=ButtonText.BACK, callback_data="admin_users"))
    return InlineKeyboardMarkup(inline_keyboard=[actions])

def confirmation_keyboard(res_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ButtonText.CONFIRM, callback_data=f"admin_confirm_{res_id}"),
         InlineKeyboardButton(text=ButtonText.CANCEL, callback_data=f"admin_cancel_{res_id}")],
        #[InlineKeyboardButton(text=ButtonText.BACK, callback_data="admin_confirmations")]
    ])

def report_dates_keyboard(dates: list):
    """
    dates — список дат (datetime.date) по которым есть данные
    """
    from datetime import date, timedelta
    today = date.today()
    yesterday = today - timedelta(days=1)
    kb = []
    # Кнопки "Вчера" и "Сегодня"
    kb.append([
        InlineKeyboardButton(text="Вчера", callback_data=f"admin_report_date_{yesterday.isoformat()}"),
        InlineKeyboardButton(text="Сегодня", callback_data=f"admin_report_date_{today.isoformat()}")
    ])
    # Кнопки по датам из базы (до 7 дней)
    for d in dates:
        btn_text = d.strftime("%d.%m.%Y")
        kb.append([InlineKeyboardButton(text=btn_text, callback_data=f"admin_report_date_{d.isoformat()}")])
    kb.append([InlineKeyboardButton(text="Общий", callback_data="admin_report_overall")])
    kb.append([InlineKeyboardButton(text=ButtonText.BACK, callback_data="back_to_admin")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def report_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ButtonText.BACK, callback_data="admin_reports")],
        [InlineKeyboardButton(text=ButtonText.TO_MAIN, callback_data="back_to_admin")]
    ])

# --- Основные обработчики ---
def register_admin_handlers(dp, db: DatabaseManager):
    # Главное меню админа
    @dp.callback_query(F.data == "back_to_admin")
    async def back_to_admin_menu(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.message.edit_text(Config.ADMIN_WELCOME_MESSAGE, reply_markup=admin_main_menu())

    # --- Управление календарем ---
    @dp.callback_query(F.data == "admin_calendar")
    async def admin_calendar(callback: types.CallbackQuery, state: FSMContext):
        calendar_status = await db.get_calendar_status()
        await callback.message.edit_text(
            f"{Emoji.CALENDAR} Календарь (на 7 дней)\nВыберите день:",
            reply_markup=calendar_days_keyboard(calendar_status)
        )
        await state.set_state(AdminCalendarFSM.selecting_date)

    @dp.callback_query(F.data.startswith("admin_cal_date_"))
    async def admin_calendar_date(callback: types.CallbackQuery, state: FSMContext):
        date_str = callback.data.replace("admin_cal_date_", "")
        shifts = await db.get_shifts()
        await state.update_data(selected_date=date_str)
        await callback.message.edit_text(
            f"{Emoji.CALENDAR} {date_str}: выберите смену",
            reply_markup=shift_keyboard(shifts, date_str)
        )
        await state.set_state(AdminCalendarFSM.selecting_shift)

    @dp.callback_query(F.data.startswith("admin_shift_back_"))
    async def admin_shift_back(callback: types.CallbackQuery, state: FSMContext):
        date_str = callback.data.replace("admin_shift_back_", "")
        shifts = await db.get_shifts()
        await state.update_data(selected_date=date_str)
        await callback.message.edit_text(
            f"{Emoji.CALENDAR} {date_str}: выберите смену",
            reply_markup=shift_keyboard(shifts, date_str)
        )
        await state.set_state(AdminCalendarFSM.selecting_shift)

    @dp.callback_query(F.data.startswith("admin_shift_"))
    async def admin_calendar_shift(callback: types.CallbackQuery, state: FSMContext):
        # admin_shift_{date_str}_{shift_id}
        parts = callback.data.split("_")
        if len(parts) == 4:
            _, _, date_str, shift_id = parts
            try:
                shift_id = int(shift_id)
            except ValueError:
                await callback.answer("Ошибка формата смены.")
                return
            await state.update_data(selected_shift=shift_id)
            vacancies = await db.get_vacancies()
            await callback.message.edit_text(
                "Выберите должность (вакансию):",
                reply_markup=vacancy_keyboard(vacancies, date_str, shift_id)
            )
            await state.set_state(AdminCalendarFSM.selecting_vacancy)
        else:
            await callback.answer("Ошибка перехода. Повторите выбор.")

    @dp.callback_query(F.data.startswith("admin_vacancy_"))
    async def admin_calendar_vacancy(callback: types.CallbackQuery, state: FSMContext):
        # admin_vacancy_{date_str}_{shift_id}_{vacancy_id}
        _, _, date_str, shift_id, vacancy_id = callback.data.split("_")
        await state.update_data(selected_vacancy=int(vacancy_id))
        # Вводим число работников — без клавиатуры!
        await callback.message.edit_text(
            "Введите нужное количество работников:"
        )
        await state.set_state(AdminCalendarFSM.entering_count)

    @dp.message(AdminCalendarFSM.entering_count)
    async def admin_calendar_count(message: types.Message, state: FSMContext):
        data = await state.get_data()
        try:
            count = int(message.text.strip())
        except Exception:
            await message.answer("Введите целое число:")
            return
        date_str = data['selected_date']
        shift_id = data['selected_shift']
        vacancy_id = data['selected_vacancy']
        await db.add_need_workers(date.fromisoformat(date_str), shift_id, vacancy_id, count)
        # После добавления — снова показать меню выбора вакансии для этой смены
        vacancies = await db.get_vacancies()
        await message.answer(
            f"{Emoji.SUCCESS} Данные обновлены. Хотите добавить по другой должности?",
            reply_markup=vacancy_keyboard(vacancies, date_str, shift_id)
        )
        await state.set_state(AdminCalendarFSM.selecting_vacancy)

    # --- Управление справочником ---
    @dp.callback_query(F.data == "admin_handbook")
    async def admin_handbook_edit(callback: types.CallbackQuery, state: FSMContext):
        text = await db.get_handbook()
        await callback.message.edit_text(
            f"{Emoji.HANDBOOK} Текущий справочник:\n\n{text}\n\n"
            "✏️ Введите новый текст справочника:",
            reply_markup=back_menu()
        )
        await state.set_state(AdminHandbookFSM.editing)

    @dp.message(AdminHandbookFSM.editing)
    async def admin_handbook_save(message: types.Message, state: FSMContext):
        text = message.text.strip()
        await db.set_handbook(text)
        await message.answer(f"{Emoji.SUCCESS} Справочник обновлен.", reply_markup=to_admin_menu())
        await state.clear()

    # --- Подтверждение резерваций ---
    @dp.callback_query(F.data == "admin_confirmations")
    async def admin_confirmations(callback: types.CallbackQuery):
        pending = await db.get_pending_reservations()
        if not pending:
            await callback.message.edit_text(f"{Emoji.SUCCESS} Нет неподтвержденных резерваций.", reply_markup=to_admin_menu())
            return
        for r in pending:
            await callback.message.delete()
            msg = (
                f"{Emoji.INFO} Новая резервация\n"
                f"{MessageFormatter.format_reservation(r)}\n\n"
                f"👤 {r['full_name']} / {r['phone']}\n"
            )
            await callback.message.answer(msg, reply_markup=confirmation_keyboard(r['id']))

    @dp.callback_query(F.data.startswith("admin_confirm_"))
    async def admin_confirm_confirm(callback: types.CallbackQuery):
        res_id = int(callback.data.split("_")[-1])
        await db.confirm_reservation(res_id)
        await callback.answer("Запись подтверждена.")
        await callback.message.edit_text(f"{Emoji.SUCCESS} Запись подтверждена.", reply_markup=to_admin_menu())

    @dp.callback_query(F.data.startswith("admin_cancel_"))
    async def admin_confirm_cancel(callback: types.CallbackQuery):
        res_id = int(callback.data.split("_")[-1])
        await db.delete_reservation(res_id)
        await callback.answer("Запись отменена и удалена.")
        await callback.message.edit_text(f"{Emoji.ERROR} Запись отменена.", reply_markup=to_admin_menu())

    # --- Пользователи ---
    @dp.callback_query(F.data == "admin_users")
    async def admin_users(callback: types.CallbackQuery, state: FSMContext):
        users = await db.get_all_users()
        text = f"{Emoji.USERS} Все пользователи:\n"
        for u in users[:10]:  # показываем первые 10 для информации
            text += MessageFormatter.format_user_info(u) + "\n\n"
        text += "Для подробной работы введите ФИО, ID или номер телефона пользователя."
        await callback.message.edit_text(text, reply_markup=users_filter_keyboard())
        await state.set_state(AdminUserSearch.waiting_user_search)

    @dp.message(AdminUserSearch.waiting_user_search)
    async def admin_find_user(message: types.Message, state: FSMContext):
        query = message.text.strip()
        users = await db.get_all_users()
        found_users = []

        # ID (цифры)
        if query.isdigit():
            found_users = [u for u in users if str(u['tg_id']) == query or (u.get('phone') and query in u['phone'])]
        else:
            # Поиск по ФИО (без учета регистра)
            found_users = [u for u in users if query.lower() in u['full_name'].lower()]
            # Поиск по телефону
            if not found_users:  # ищем по телефону только если не нашли по ФИО
                found_users = [u for u in users if u.get('phone') and query in u['phone']]

        # Убираем дубликаты по tg_id
        unique_users = {u['tg_id']: u for u in found_users}.values()

        if not unique_users:
            await message.answer("Пользователь не найден. Попробуйте еще раз или введите другие данные.")
            return

        if len(unique_users) > 1:
            txt = "Найдено несколько пользователей:\n\n"
            for u in list(unique_users)[:5]:  # показываем максимум 5
                txt += f"👤 {u['full_name']}\n📱 ID: {u['tg_id']}\n📞 Тел: {u.get('phone', 'не указан')}\n\n"
            txt += "Уточните данные или введите точный ID."
            await message.answer(txt)
            return

        # Один пользователь найден
        user = list(unique_users)[0]
        info = MessageFormatter.format_user_info(user)
        await message.answer(
            info,
            reply_markup=user_action_keyboard(user)
        )
        await state.clear()

    @dp.callback_query(F.data.startswith("admin_users_filter_"))

    async def admin_users_filtered(callback: types.CallbackQuery, state: FSMContext):
        filter_type = callback.data.split("_")[-1]
        users = await db.get_all_users()
        today = date.today()

        if filter_type == "today":
            users = [u for u in users if u['date_of_reg'].date() == today]

        text = f"{Emoji.USERS} Пользователи ({filter_type}):\n\n"
        for u in users[:10]:
            text += MessageFormatter.format_user_info(u) + "\n\n"

        if len(users) > 10:
            text += f"... и еще {len(users) - 10} пользователей\n\n"

        text += "Для поиска конкретного пользователя введите ФИО, ID или номер телефона."
        await callback.message.edit_text(text, reply_markup=users_filter_keyboard())
        await state.set_state(AdminUserSearch.waiting_user_search)

    @dp.callback_query(F.data.startswith("admin_ban_"))
    async def admin_ban(callback: types.CallbackQuery):
        tg_id = int(callback.data.split("_")[-1])
        await db.update_user_status(tg_id, is_banned=True)
        await callback.answer("Пользователь забанен.")
        await callback.message.edit_reply_markup(reply_markup=user_action_keyboard({'tg_id': tg_id, 'is_banned': True, 'is_blocked': False}))

    @dp.callback_query(F.data.startswith("admin_unban_"))
    async def admin_unban(callback: types.CallbackQuery):
        tg_id = int(callback.data.split("_")[-1])
        await db.update_user_status(tg_id, is_banned=False)
        await callback.answer("Пользователь разбанен.")
        await callback.message.edit_reply_markup(reply_markup=user_action_keyboard({'tg_id': tg_id, 'is_banned': False, 'is_blocked': False}))

    @dp.callback_query(F.data.startswith("admin_block_"))
    async def admin_block(callback: types.CallbackQuery):
        tg_id = int(callback.data.split("_")[-1])
        await db.update_user_status(tg_id, is_blocked=True)
        await callback.answer("Пользователь заблокирован.")
        await callback.message.edit_reply_markup(reply_markup=user_action_keyboard({'tg_id': tg_id, 'is_banned': False, 'is_blocked': True}))

    @dp.callback_query(F.data.startswith("admin_unblock_"))
    async def admin_unblock(callback: types.CallbackQuery):
        tg_id = int(callback.data.split("_")[-1])
        await db.update_user_status(tg_id, is_blocked=False)
        await callback.answer("Пользователь разблокирован.")
        await callback.message.edit_reply_markup(reply_markup=user_action_keyboard({'tg_id': tg_id, 'is_banned': False, 'is_blocked': False}))

    # --- Отчеты ---
    @dp.callback_query(F.data == "admin_reports")
    async def admin_reports_menu(callback: types.CallbackQuery):
        date_list = await db.get_dates_reservation()
        kb = report_dates_keyboard(date_list)
        await callback.message.edit_text(
            f"{Emoji.STATS} Выберите дату для отчёта:",
            reply_markup=kb
        )

    @dp.callback_query(F.data == "admin_report_overall")
    async def admin_report_overall(callback: types.CallbackQuery):
        # Текущий общий отчет (за 7 дней)
        stats = await db.get_statistics()
        if not stats:
            await callback.message.edit_text("Нет данных для отчета.", reply_markup=to_admin_menu())
            return
        text = f"{Emoji.STATS} Общий отчет (за 7 дней):\n"
        for s in stats:
            text += MessageFormatter.format_statistics_item(s) + "\n"
        await callback.message.edit_text(text, reply_markup=report_back_keyboard())

    @dp.callback_query(F.data.startswith("admin_report_date_"))
    async def admin_report_by_date(callback: types.CallbackQuery):
        date_str = callback.data.replace("admin_report_date_", "")
        try:
            report_date = date.fromisoformat(date_str)
        except Exception:
            await callback.answer("Неверный формат даты.")
            return
        # Получаем статистику только за выбранную дату
        stats = await db.get_statistics(start_date=report_date, end_date=report_date)
        if not stats:
            await callback.message.edit_text(
                f"Нет данных для отчета за {report_date.strftime('%d.%m.%Y')}.",
                reply_markup=to_admin_menu()
            )
            return
        text = f"{Emoji.STATS} Отчет за {report_date.strftime('%d.%m.%Y')}:\n"
        for s in stats:
            text += MessageFormatter.format_statistics_item(s) + "\n"
        await callback.message.edit_text(text, reply_markup=report_back_keyboard())

    # @dp.callback_query(F.data == "admin_reports")
    # async def admin_reports(callback: types.CallbackQuery):
    #     stats = await db.get_statistics()
    #     if not stats:
    #         await callback.message.edit_text("Нет данных для отчета.", reply_markup=to_admin_menu())
    #         return
    #     text = f"{Emoji.STATS} Статистика (за 7 дней):\n"
    #     for s in stats:
    #         text += MessageFormatter.format_statistics_item(s) + "\n"
    #     await callback.message.edit_text(text, reply_markup=to_admin_menu())

    # --- Рассылка ---
    @dp.callback_query(F.data == "admin_broadcast")
    async def admin_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
        await callback.message.edit_text("Введите текст для рассылки всем пользователям:", reply_markup=back_menu())
        await state.set_state(AdminBroadcastFSM.waiting_text)

    @dp.message(AdminBroadcastFSM.waiting_text)
    async def admin_broadcast_send(message: types.Message, state: FSMContext):
        text = message.text.strip()
        users = await db.get_all_users()
        count = 0
        for u in users:
            try:
                await message.bot.send_message(u['tg_id'], f"📢 {text}")
                count += 1
            except Exception:
                continue
        await message.answer(f"Рассылка завершена. Отправлено {count} сообщений.", reply_markup=to_admin_menu())
        await state.clear()

    # --- Навигация назад ---
    @dp.callback_query(F.data == "back_to_admin")
    async def back_admin(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.message.edit_text(Config.ADMIN_WELCOME_MESSAGE, reply_markup=admin_main_menu())