"""Репозиторий для работы с моделью Habit."""

from datetime import date, time
from typing import Any, Sequence

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.core.config import settings  # Для значения target_days по умолчанию
from src.api.core.logging import api_log as log
from src.api.models import Habit, HabitExecution, HabitExecutionStatus, User
from src.api.repositories import BaseRepository
from src.api.schemas import HabitSchemaCreate, HabitSchemaUpdate


class HabitRepository(BaseRepository[Habit, HabitSchemaCreate, HabitSchemaUpdate]):
    """
    Репозиторий для выполнения CRUD-операций с моделью Habit.

    Наследует общие методы от BaseRepository и содержит специфичные для Habit методы.
    """

    async def create_habit(
        self,
        db_session: AsyncSession,
        *,
        habit_in: HabitSchemaCreate,
        user_id: int,
    ) -> Habit:
        """
        Создает новую привычку для указанного пользователя.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_in (HabitSchemaCreate): Данные для создания привычки.
            user_id (int): ID аутентифицированного пользователя, создающего привычку.

        Returns:
            Habit: Созданная привычка.
        """

        # Конвертируем в словарь
        habit_in_data = habit_in.model_dump()

        # Устанавливаем target_days из настроек, если в переданных данных - None
        if not habit_in_data.get("target_days"):
            habit_in_data["target_days"] = settings.DAYS_TO_FORM_HABIT

        # Подготавливаем объект привычки
        habit_obj = self.model(**habit_in_data, user_id=user_id)

        # Добавляем объект привычки в сессию
        db_session.add(habit_obj)

        # Получаем ID и другие сгенерированные базой данных значения
        await db_session.flush()

        # Обновляем объект привычки из базы данных
        await db_session.refresh(habit_obj)

        # Возвращаем созданную привычку
        return habit_obj

    async def get_habit_by_id_with_executions(self, db_session: AsyncSession, *, habit_id: int) -> Habit | None:
        """
        Получает привычку по ID с жадной загрузкой ее выполнений.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки.

        Returns:
            Habit | None: Экземпляр привычки с подгруженными выполнениями или None.
        """
        log.info(f"Получение привычки ID: {habit_id} с жадной загрузкой ее выполнений.")
        statement = (
            select(self.model)
            .where(self.model.id == habit_id)
            .options(selectinload(self.model.executions))  # Жадная загрузка выполнений
        )
        result = await db_session.execute(statement)
        habit = result.scalar_one_or_none()

        status = "найдена" if habit else "не найдена"
        log.debug(f"Привычка (ID {habit_id}) с подгруженными выполнениями {status}.")

        return habit

    async def get_habit_by_id_for_update(self, db_session: AsyncSession, *, habit_id: int) -> Habit | None:
        """
        Получает привычку по ID для ее последующего обновления.

        Получает привычку по ID и блокирует строку от изменения другими транзакциями
        до конца текущей транзакции (SELECT ... FOR UPDATE).

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки.

        Returns:
            Habit | None: Экземпляр привычки или None.
        """
        statement = select(self.model).where(self.model.id == habit_id).with_for_update()
        result = await db_session.execute(statement)
        habit = result.scalar_one_or_none()

        status = "найдена" if habit else "не найдена"
        log.debug(f"Привычка (ID {habit_id}) для обновления {status}.")

        return habit

    async def get_habits_by_user_id(
        self,
        db_session: AsyncSession,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False,
    ) -> Sequence[Habit]:
        """
        Получает список привычек для указанного пользователя с пагинацией.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            user_id (int): ID пользователя, чьи привычки нужно получить.
            skip (int): Количество записей для пропуска.
            limit (int): Максимальное количество записей.
            active_only (bool): Если True, возвращает только активные привычки.

        Returns:
            Sequence[Habit]: Список привычек пользователя.
        """

        # Явно указываем тип списка: list[ColumnElement[bool]]
        # Это говорит mypy, что внутри лежат SQL-выражения, возвращающие булево значение (WHERE ...)
        filters: list[ColumnElement[bool]] = (
            [self.model.user_id == user_id, self.model.is_active.is_(True)]
            if active_only
            else [self.model.user_id == user_id]
        )
        # Сортировка по времени и имени если active_only == True, иначе сортировка по дате создания (сначала новые)
        # Явно указываем тип списка: list[ColumnElement[Any]]
        # .asc() и .desc() возвращают UnaryExpression, который совместим с ColumnElement
        order: list[ColumnElement[Any]] = (
            [self.model.time_to_remind.asc(), self.model.name.asc()] if active_only else [self.model.created_at.desc()]
        )

        habits = await self.get_multi_by_filter(
            db_session,
            *filters,
            skip=skip,
            limit=limit,
            order_by=order,
        )

        log.debug(f"Найдено {len(habits)} привычек для пользователя ID: {user_id}.")
        return habits

    async def get_active_timezones(self, db_session: AsyncSession) -> Sequence[str]:
        """
        Получает список уникальных часовых поясов пользователей, у которых есть активные привычки.

        Используется планировщиком.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.

        Returns:
            Sequence[str]: Список строк таймзон (например, ['UTC', 'Europe/Moscow']).
        """
        statement = (
            select(User.timezone)
            .join(Habit.user)
            .where(
                # Фильтры активности
                User.is_active.is_(True),  # Только активные юзеры
                User.is_bot_blocked.is_(False),  # Которые не заблочили бота
                Habit.is_active.is_(True)  # Только активные привычки
            )
            .distinct()  # Выбираем уникальные таймзоны
        )

        result = await db_session.execute(statement)

        return result.scalars().all()

    async def get_habits_for_notification(
        self,
        db_session: AsyncSession,
        timezone: str,
        target_time: time,
        target_date: date,
    ) -> Sequence[Habit]:
        """
        Находит активные привычки, которые еще не были выполнены,
        для отправки уведомлений в конкретном часовом поясе.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            timezone (str): Часовой пояс (например, 'Europe/Moscow').
            target_time (time): Время напоминания (ЧЧ:ММ:00).
            target_date (date): Локальная дата пользователя (для проверки выполнения).

        Returns:
            Sequence[Habit]: Список привычек пользователя, о выполнении которых нужно напомнить.
        """
        # Подзапрос: находим ID привычек, которые уже выполнены (DONE) на целевую дату
        has_done_execution = (
            select(1)
            .where(
                HabitExecution.habit_id == self.model.id,
                HabitExecution.status == HabitExecutionStatus.DONE,
                HabitExecution.execution_date == target_date,
            )
            .exists()
        )

        statement = (
            select(self.model)
            .join(self.model.user)
            .where(
                # Фильтры активности
                self.model.is_active.is_(True),  # Только активные привычки
                User.is_active.is_(True),  # Только активным юзерам
                User.is_bot_blocked.is_(False),  # Которые не заблочили бота
                # Фильтры по индексам
                User.timezone == timezone,
                self.model.time_to_remind == target_time,
                # Фильтр "еще не выполнены"
                ~has_done_execution
            )
            # Подгружаем юзера, чтобы знать telegram_id для отправки
            .options(selectinload(self.model.user))
        )

        result = await db_session.execute(statement)

        return result.scalars().all()
