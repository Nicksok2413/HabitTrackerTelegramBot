"""Репозиторий для работы с моделью Habit."""

from typing import Any, Sequence

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.core.logging import api_log as log
from src.api.models import Habit
from src.api.repositories import BaseRepository
from src.api.schemas import HabitSchemaCreate, HabitSchemaUpdate


class HabitRepository(BaseRepository[Habit, HabitSchemaCreate, HabitSchemaUpdate]):
    """
    Репозиторий для выполнения CRUD-операций с моделью Habit.

    Наследует общие методы от BaseRepository и содержит специфичные для Habit методы.
    """

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
        log.debug(
            f"Получение привычек для пользователя ID: {user_id}, "
            f"skip={skip}, limit={limit}, active_only={active_only})"
        )

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

    async def get_habit_with_executions(self, db_session: AsyncSession, *, habit_id: int) -> Habit | None:
        """
        Получает привычку по ID вместе с ее выполнениями.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки.

        Returns:
            Habit | None: Экземпляр Habit с загруженными выполнениями или None.
        """
        statement = (
            select(self.model)
            .where(self.model.id == habit_id)
            .options(selectinload(self.model.executions))  # Жадная загрузка выполнений
        )
        result = await db_session.execute(statement)
        habit = result.scalar_one_or_none()

        status = "найдена" if habit else "не найдена"
        log.debug(f"Привычка (ID {habit_id}) с загруженными выполнениями {status}.")

        return habit


# Можно добавить методы для поиска привычек, у которых time_to_remind совпадает с текущим,
# для использования планировщиком, если планировщик будет обращаться к API,
# либо если логика планировщика будет в API сервисе.
# Если планировщик работает напрямую с БД, такие методы в API репозитории не понадобятся.
