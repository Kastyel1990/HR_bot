from datetime import date, timedelta
from aiogram import types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ButtonText, Emoji, MessageFormatter, Config
from database import DatabaseManager

# FSM состояния для админа
class AdminCalendarFSM(StatesGroup):
    selecting_date = State()
    selecting_vacancy = State()
    selecting_shift = State()
    entering_count = State()

class AdminHandbookFSM(StatesGroup):
    editing = State()

class AdminBroadcastFSM(StatesGroup):
    waiting_text = State()

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

def needworkers_edit_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ButtonText.BACK, callback_data="admin_calendar")],
        [InlineKeyboardButton(text=ButtonText.TO_MAIN, callback_data="back_to_admin")]
    ])

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
        [InlineKeyboardButton(text=ButtonText.BACK, callback_data="admin_confirmations")]
    ])

# --- Админские обработчики ---
def register_admin_handlers(dp, db: DatabaseManager):
    # Главное меню админа
    @dp.callback_query(F.data == "back_to_admin")
    async def back_to_admin_menu(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.message.edit_text(Config.ADMIN_WELCOME_MESSAGE, reply_markup=admin_main_menu())

    @dp.callback_query(F.data == "admin_calendar")
    async def admin_calendar(callback: types.CallbackQuery, state: FSMContext):
        calendar_status = await db.get_calendar_status()
        await callback.message.edit_text(
            f"{Emoji.CALENDAR} Календарь (на 7 дней)\n"
            "Выберите день для редактирования:",
            reply_markup=calendar_days_keyboard(calendar_status)
        )

    @dp.callback_query(F.data.startswith("admin_cal_date_"))
    async def admin_calendar_date(callback: types.CallbackQuery, state: FSMContext):
        date_str = callback.data.split("_")[-1]
        work_date = date.fromisoformat(date_str)
        # Получаем слоты на день
        slots = await db.get_need_workers(work_date, work_date)
        text = f"{Emoji.CALENDAR} {work_date.strftime('%d.%m.%Y')}:\n"
        if not slots:
            text += "Нет данных о потребности. Можно добавить."
        else:
            for s in slots:
                text += f"{Emoji.INFO} {s['shift_name']} / {s['vacancy_name']}: {s['need_count']} чел.\n"
        # Выбор действия
        vacancies = await db.get_vacancies()
        shifts = await db.get_shifts()
        # Кнопки для добавления
        keyboard = []
        for v in vacancies:
            for s in shifts:
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"{v['name']} / {s['name']}",
                        callback_data=f"admin_edit_need_{date_str}_{s['id']}_{v['id']}"
                    )
                ])
        keyboard.append([InlineKeyboardButton(text=ButtonText.BACK, callback_data="admin_calendar")])
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

    @dp.callback_query(F.data.startswith("admin_edit_need_"))
    async def admin_edit_need(callback: types.CallbackQuery, state: FSMContext):
        # admin_edit_need_{date}_{shift_id}_{vacancy_id}
        _, _, _, date_str, shift_id, vacancy_id = callback.data.split("_")
        await state.update_data(edit_date=date_str, edit_shift=int(shift_id), edit_vacancy=int(vacancy_id))
        await callback.message.edit_text(
            f"Введите нужное количество работников для {date_str}, смена {shift_id}, вакансия {vacancy_id}:",
            reply_markup=needworkers_edit_keyboard()
        )
        await state.set_state(AdminCalendarFSM.entering_count)

    @dp.message(AdminCalendarFSM.entering_count)
    async def process_edit_need_count(message: types.Message, state: FSMContext):
        data = await state.get_data()
        try:
            count = int(message.text.strip())
            date_str, shift_id, vacancy_id = data['edit_date'], data['edit_shift'], data['edit_vacancy']
        except Exception:
            await message.answer("Введите целое число!", reply_markup=needworkers_edit_keyboard())
            return
        await db.add_need_workers(date.fromisoformat(date_str), shift_id, vacancy_id, count)
        await message.answer(f"{Emoji.SUCCESS} Данные обновлены.", reply_markup=to_admin_menu())
        await state.clear()

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
            msg = (
                f"{Emoji.INFO} Новая резервация\n"
                f"{MessageFormatter.format_reservation(r)}\n\n"
                f"👤 {r['full_name']} / {r['phone']}\n"
            )
            await callback.message.answer(msg, reply_markup=confirmation_keyboard(r['id']))

    @dp.callback_query(F.data.startswith("admin_confirm_"))
    async def admin_confirm_confirm(callback: types.CallbackQuery):
        res_id = int(callback.data.split("_")[-1])
        # В реальном проекте тут меняется статус резервации и уведомляется пользователь (пока просто удалим)
        await db.delete_reservation(res_id)
        await callback.answer("Запись подтверждена и удалена из очереди.")
        await callback.message.edit_text(f"{Emoji.SUCCESS} Запись подтверждена.", reply_markup=to_admin_menu())

    @dp.callback_query(F.data.startswith("admin_cancel_"))
    async def admin_confirm_cancel(callback: types.CallbackQuery):
        res_id = int(callback.data.split("_")[-1])
        await db.delete_reservation(res_id)
        await callback.answer("Запись отменена и удалена.")
        await callback.message.edit_text(f"{Emoji.ERROR} Запись отменена.", reply_markup=to_admin_menu())

    # --- Пользователи ---
    @dp.callback_query(F.data == "admin_users")
    async def admin_users(callback: types.CallbackQuery):
        users = await db.get_all_users()
        text = f"{Emoji.USERS} Все пользователи:\n"
        for u in users[:10]:
            text += MessageFormatter.format_user_info(u) + "\n\n"
        text += "Для подробной работы выберите фильтр или пользователя."
        await callback.message.edit_text(text, reply_markup=users_filter_keyboard())

    @dp.callback_query(F.data.startswith("admin_users_filter_"))
    async def admin_users_filtered(callback: types.CallbackQuery):
        filter_type = callback.data.split("_")[-1]
        users = await db.get_all_users()
        today = date.today()
        if filter_type == "today":
            users = [u for u in users if u['date_of_reg'].date() == today]
        # Можно добавить фильтры по дате, наличию записи и т.д.
        text = f"{Emoji.USERS} Пользователи ({filter_type}):\n"
        for u in users[:10]:
            text += MessageFormatter.format_user_info(u) + "\n\n"
        await callback.message.edit_text(text, reply_markup=users_filter_keyboard())

    # Действия с конкретным пользователем
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
    async def admin_reports(callback: types.CallbackQuery):
        stats = await db.get_statistics()
        if not stats:
            await callback.message.edit_text("Нет данных для отчета.", reply_markup=to_admin_menu())
            return
        text = f"{Emoji.STATS} Статистика (за 7 дней):\n"
        for s in stats:
            text += MessageFormatter.format_statistics_item(s) + "\n"
        await callback.message.edit_text(text, reply_markup=to_admin_menu())

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