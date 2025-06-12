import pyodbc
import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from config import Config

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.connection_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={Config.DB_SERVER};"
            f"DATABASE={Config.DB_NAME};"
            f"UID={Config.DB_USER};"
            f"PWD={Config.DB_PASSWORD};"
            f"TrustServerCertificate=yes;"
        )
        self._handbook_text = ""  # Временное хранение справочника
    
    async def init_db(self):
        """Инициализация подключения к БД"""
        try:
            # Проверяем подключение
            conn = pyodbc.connect(self.connection_string)
            conn.close()
            logger.info("✅ Подключение к базе данных успешно")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к БД: {e}")
            raise
    
    def _execute_query(self, query: str, params: tuple = None, fetch: bool = False):
        """Выполнение SQL запроса"""
        try:
            conn = pyodbc.connect(self.connection_string)
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if fetch:
                if query.strip().upper().startswith('SELECT'):
                    columns = [column[0] for column in cursor.description]
                    rows = cursor.fetchall()
                    result = [dict(zip(columns, row)) for row in rows]
                else:
                    result = cursor.fetchone()
            else:
                result = None
                conn.commit()
            
            conn.close()
            return result
            
        except pyodbc.Error as e:
            logger.error(f"Ошибка выполнения запроса: {e}")
            logger.error(f"Запрос: {query}")
            logger.error(f"Параметры: {params}")
            raise
    
    # === ПОЛЬЗОВАТЕЛИ ===
    
    async def get_user(self, tg_id: int) -> Optional[Dict]:
        """Получение пользователя по Telegram ID"""
        query = """
        SELECT tg_id, full_name, phone, username, is_admin, is_banned, is_blocked, date_of_reg
        FROM Users 
        WHERE tg_id = ?
        """
        result = self._execute_query(query, (tg_id,), fetch=True)
        return result[0] if result else None
    
    async def register_user(self, tg_id: int, full_name: str, phone: str, username: str):
        """Регистрация нового пользователя"""
        query = """
        INSERT INTO Users (tg_id, full_name, phone, username, is_admin, is_banned, is_blocked, date_of_reg)
        VALUES (?, ?, ?, ?, 0, 0, 0, ?)
        """
        self._execute_query(query, (tg_id, full_name, phone, username, datetime.now()))
        logger.info(f"Зарегистрирован новый пользователь: {full_name} ({tg_id})")
    
    async def get_all_users(self) -> List[Dict]:
        """Получение всех пользователей"""
        query = """
        SELECT u.tg_id, u.full_name, u.phone, u.username, u.is_admin, u.is_banned, u.is_blocked, u.date_of_reg,
               CASE WHEN r.id IS NOT NULL THEN 1 ELSE 0 END as has_reservation
        FROM Users u
        LEFT JOIN tb_Reservation r ON u.tg_id = r.id_user 
        ORDER BY u.date_of_reg DESC
        """
        return self._execute_query(query, fetch=True) or []
    
    async def update_user_status(self, tg_id: int, is_banned: bool = None, is_blocked: bool = None):
        """Обновление статуса пользователя"""
        updates = []
        params = []
        
        if is_banned is not None:
            updates.append("is_banned = ?")
            params.append(1 if is_banned else 0)
        
        if is_blocked is not None:
            updates.append("is_blocked = ?")
            params.append(1 if is_blocked else 0)
        
        if updates:
            params.append(tg_id)
            query = f"UPDATE Users SET {', '.join(updates)} WHERE tg_id = ?"
            self._execute_query(query, tuple(params))
    
    # === СПРАВОЧНИКИ ===
    
    async def get_vacancies(self) -> List[Dict]:
        """Получение всех вакансий"""
        query = "SELECT id, name FROM spr_Vacancies ORDER BY name"
        return self._execute_query(query, fetch=True) or []
    
    async def get_shifts(self) -> List[Dict]:
        """Получение всех смен"""
        query = "SELECT id, name FROM spr_Shifts ORDER BY name"
        return self._execute_query(query, fetch=True) or []
    
    async def add_vacancy(self, name: str) -> int:
        """Добавление новой вакансии"""
        query = "INSERT INTO spr_Vacancies (name) OUTPUT INSERTED.id VALUES (?)"
        result = self._execute_query(query, (name,), fetch=True)
        return result['id'] if result else None
    
    async def add_shift(self, name: str) -> int:
        """Добавление новой смены"""
        query = "INSERT INTO spr_Shifts (name) OUTPUT INSERTED.id VALUES (?)"
        result = self._execute_query(query, (name,), fetch=True)
        return result['id'] if result else None
    
    async def delete_vacancy(self, vacancy_id: int):
        """Удаление вакансии"""
        query = "DELETE FROM spr_Vacancies WHERE id = ?"
        self._execute_query(query, (vacancy_id,))
    
    async def delete_shift(self, shift_id: int):
        """Удаление смены"""
        query = "DELETE FROM spr_Shifts WHERE id = ?"
        self._execute_query(query, (shift_id,))
    
    # === ПЛАНИРОВАНИЕ РАБОТЫ ===
    
    async def add_need_workers(self, work_date: date, shift_id: int, vacancy_id: int, need_count: int):
        """Добавление потребности в работниках"""
        # Проверяем, существует ли уже запись
        check_query = """
        SELECT id FROM tb_NeedWorkers 
        WHERE date = ? AND id_shift = ? AND id_vacancy = ?
        """
        existing = self._execute_query(check_query, (work_date, shift_id, vacancy_id), fetch=True)
        
        if existing:
            # Обновляем существующую запись
            update_query = """
            UPDATE tb_NeedWorkers 
            SET need_count = ? 
            WHERE date = ? AND id_shift = ? AND id_vacancy = ?
            """
            self._execute_query(update_query, (need_count, work_date, shift_id, vacancy_id))
        else:
            # Создаем новую запись
            insert_query = """
            INSERT INTO tb_NeedWorkers (date, id_shift, id_vacancy, need_count)
            VALUES (?, ?, ?, ?)
            """
            self._execute_query(insert_query, (work_date, shift_id, vacancy_id, need_count))
    
    async def get_need_workers(self, start_date: date = None, end_date: date = None) -> List[Dict]:
        """Получение потребности в работниках"""
        if not start_date:
            start_date = date.today()
        if not end_date:
            end_date = start_date + timedelta(days=7)
        
        query = """
        SELECT nw.id, nw.date, nw.need_count,
               v.name as vacancy_name, s.name as shift_name,
               nw.id_vacancy, nw.id_shift
        FROM tb_NeedWorkers nw
        INNER JOIN spr_Vacancies v ON nw.id_vacancy = v.id
        INNER JOIN spr_Shifts s ON nw.id_shift = s.id
        WHERE nw.date >= ? AND nw.date <= ?
        ORDER BY nw.date, s.name, v.name
        """
        return self._execute_query(query, (start_date, end_date), fetch=True) or []
    
    async def get_available_slots(self, work_date: date) -> List[Dict]:
        """Получение доступных слотов для записи на определенную дату"""
        query = """
        SELECT nw.id, nw.date, nw.need_count, nw.id_vacancy, nw.id_shift,
               v.name as vacancy_name, s.name as shift_name,
               ISNULL(r.reserved_count, 0) as reserved_count,
               (nw.need_count - ISNULL(r.reserved_count, 0)) as available_count
        FROM tb_NeedWorkers nw
        INNER JOIN spr_Vacancies v ON nw.id_vacancy = v.id
        INNER JOIN spr_Shifts s ON nw.id_shift = s.id
        LEFT JOIN (
            SELECT id_vacancy, id_shift, date_reservation, COUNT(*) as reserved_count
            FROM tb_Reservation
            WHERE date_reservation = ?
            GROUP BY id_vacancy, id_shift, date_reservation
        ) r ON nw.id_vacancy = r.id_vacancy AND nw.id_shift = r.id_shift AND nw.date = r.date_reservation
        WHERE nw.date = ? AND (nw.need_count - ISNULL(r.reserved_count, 0)) > 0
        ORDER BY s.name, v.name
        """
        return self._execute_query(query, (work_date, work_date), fetch=True) or []
    
    # === РЕЗЕРВАЦИИ ===
    
    async def make_reservation(self, user_id: int, work_date: date, shift_id: int, vacancy_id: int) -> Optional[int]:
        """Создание резервации"""
        # Проверяем, нет ли уже записи пользователя на эту дату
        check_query = """
        SELECT id FROM tb_Reservation 
        WHERE id_user = ? AND date_reservation = ?
        """
        existing = self._execute_query(check_query, (user_id, work_date), fetch=True)
        
        if existing:
            return None  # Пользователь уже записан на эту дату
        
        # Проверяем доступность места
        slots = await self.get_available_slots(work_date)
        available_slot = next((s for s in slots if s['id_shift'] == shift_id and s['id_vacancy'] == vacancy_id), None)
        
        if not available_slot or available_slot['available_count'] <= 0:
            return None  # Нет свободных мест
        
        # Создаем резервацию
        query = """
        INSERT INTO tb_Reservation (date_time_event, date_reservation, id_user, id_shift, id_vacancy)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?)
        """
        result = self._execute_query(query, (datetime.now(), work_date, user_id, shift_id, vacancy_id), fetch=True)
        return result['id'] if result else None
    
    async def get_user_reservations(self, user_id: int) -> List[Dict]:
        """Получение резерваций пользователя"""
        query = """
        SELECT r.id, r.date_time_event, r.date_reservation,
               v.name as vacancy_name, s.name as shift_name,
               r.id_vacancy, r.id_shift
        FROM tb_Reservation r
        INNER JOIN spr_Vacancies v ON r.id_vacancy = v.id
        INNER JOIN spr_Shifts s ON r.id_shift = s.id
        WHERE r.id_user = ? AND r.date_reservation >= ?
        ORDER BY r.date_reservation
        """
        return self._execute_query(query, (user_id, date.today()), fetch=True) or []
    
    async def delete_reservation(self, reservation_id: int):
        """Удаление резервации"""
        query = "DELETE FROM tb_Reservation WHERE id = ?"
        self._execute_query(query, (reservation_id,))
    
    async def get_pending_reservations(self) -> List[Dict]:
        """Получение неподтвержденных резерваций для админа"""
        query = """
        SELECT r.id, r.date_time_event, r.date_reservation,
               u.full_name, u.phone, u.tg_id,
               v.name as vacancy_name, s.name as shift_name
        FROM tb_Reservation r
        INNER JOIN Users u ON r.id_user = u.tg_id
        INNER JOIN spr_Vacancies v ON r.id_vacancy = v.id
        INNER JOIN spr_Shifts s ON r.id_shift = s.id
        WHERE r.date_reservation >= ?
        ORDER BY r.date_time_event
        """
        return self._execute_query(query, (date.today(),), fetch=True) or []
    
    # === СТАТИСТИКА ===
    
    async def get_statistics(self, start_date: date = None, end_date: date = None) -> List[Dict]:
        """Получение статистики по резервациям"""
        if not start_date:
            start_date = date.today()
        if not end_date:
            end_date = start_date + timedelta(days=7)
        
        query = """
        SELECT nw.date, v.name as vacancy_name, s.name as shift_name,
               nw.need_count, 
               ISNULL(r.reserved_count, 0) as reserved_count,
               CASE 
                   WHEN nw.need_count > 0 THEN CAST(ISNULL(r.reserved_count, 0) * 100.0 / nw.need_count AS DECIMAL(5,2))
                   ELSE 0 
               END as fill_percentage
        FROM tb_NeedWorkers nw
        INNER JOIN spr_Vacancies v ON nw.id_vacancy = v.id
        INNER JOIN spr_Shifts s ON nw.id_shift = s.id
        LEFT JOIN (
            SELECT id_vacancy, id_shift, date_reservation, COUNT(*) as reserved_count
            FROM tb_Reservation
            WHERE date_reservation >= ? AND date_reservation <= ?
            GROUP BY id_vacancy, id_shift, date_reservation
        ) r ON nw.id_vacancy = r.id_vacancy AND nw.id_shift = r.id_shift AND nw.date = r.date_reservation
        WHERE nw.date >= ? AND nw.date <= ?
        ORDER BY nw.date, s.name, v.name
        """
        return self._execute_query(query, (start_date, end_date, start_date, end_date), fetch=True) or []
    
    # === СПРАВОЧНИК ===
    
    async def set_handbook(self, text: str):
        """Установка текста справочника"""
        self._handbook_text = text
        logger.info("Справочник обновлен")
    
    async def get_handbook(self) -> str:
        """Получение текста справочника"""
        return self._handbook_text
    
    # === УТИЛИТЫ ===
    
    async def get_calendar_status(self) -> Dict[str, Dict]:
        """Получение статуса календаря на 7 дней"""
        today = date.today()
        end_date = today + timedelta(days=7)
        
        need_workers = await self.get_need_workers(today, end_date)
        calendar_status = {}
        
        for nw in need_workers:
            date_str = nw['date'].strftime('%Y-%m-%d')
            if date_str not in calendar_status:
                calendar_status[date_str] = {'filled': False, 'total_needed': 0, 'total_reserved': 0}
            
            # Получаем количество зарезервированных мест для этой даты/смены/вакансии
            query = """
            SELECT COUNT(*) as reserved_count
            FROM tb_Reservation
            WHERE date_reservation = ? AND id_shift = ? AND id_vacancy = ?
            """
            reserved_result = self._execute_query(query, (nw['date'], nw['id_shift'], nw['id_vacancy']), fetch=True)
            reserved_count = reserved_result[0]['reserved_count'] if reserved_result else 0
            
            calendar_status[date_str]['total_needed'] += nw['need_count']
            calendar_status[date_str]['total_reserved'] += reserved_count
            
            # Проверяем заполненность
            if reserved_count >= nw['need_count']:
                calendar_status[date_str]['filled'] = True
        
        return calendar_status