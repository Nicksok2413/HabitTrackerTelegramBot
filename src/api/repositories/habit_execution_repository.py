"""Репозиторий для работы с моделью HabitExecution."""

from datetime import date
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.core.logging import api_log as log
from src.api.models import HabitExecution, HabitExecutionStatus
from src.api.repositories import BaseRepository
from src.api.schemas import HabitExecutionSchemaCreate, HabitExecutionSchemaUpdate


class HabitExecutionRepository(BaseRepository[HabitExecution, HabitExecutionSchemaCreate, HabitExecutionSchemaUpdate]):
    """
    Репозиторий для выполнения CRUD-операций с моделью HabitExecution.

    Наследует общие методы от BaseRepository и содержит специфичные для HabitExecution методы.
    """

    async def get_execution_by_id_with_habit(
        self, db_session: AsyncSession, *, execution_id: int
    ) -> HabitExecution | None:
        """
        Получает запись о выполнение привычки по ID с жадной загрузкой связанной привычки.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            execution_id (int): ID выполнения привычки.

        Returns:
            HabitExecution | None: Экземпляр выполнения с подгруженной привычкой или None.
        """
        log.debug(f"Получение выполнения (ID: {execution_id}) привычки с жадной загрузкой самой привычки.")
        statement = (
            select(self.model)
            .where(self.model.id == execution_id)
            .options(selectinload(self.model.habit))  # Подгружаем объект привычки в атрибут .habit
        )
        result = await db_session.execute(statement)
        execution_with_habit = result.scalar_one_or_none()

        if execution_with_habit:
            log.debug(f"Найдено выполнение (ID: {execution_id}) для привычки ID: {execution_with_habit.habit.id}.")
        else:
            log.debug(f"Выполнение (ID: {execution_id}) для привычки не найдено.")

        return execution_with_habit

    async def get_execution_by_habit_id_and_date(
        self, db_session: AsyncSession, *, habit_id: int, execution_date: date
    ) -> HabitExecution | None:
        """
        Получает запись о выполнении привычки по ID привычки и дате.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки.
            execution_date (date): Дата выполнения.

        Returns:
            HabitExecution | None: Экземпляр выполнения или None.
        """
        log.debug(f"Получение выполнения для привычки ID: {habit_id} на дату: {execution_date}")
        execution = await self.get_by_filter_first_or_none(
            db_session,
            self.model.habit_id == habit_id,
            self.model.execution_date == execution_date,
        )

        if execution:
            log.debug(f"Найдено выполнение (ID: {execution.id}) для привычки ID: {habit_id} на {execution_date}.")
        else:
            log.debug(f"Выполнение для привычки ID: {habit_id} на {execution_date} не найдено.")

        return execution

    async def get_executions_for_habit(
        self,
        db_session: AsyncSession,
        *,
        habit_id: int,
        status: HabitExecutionStatus | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[HabitExecution]:
        """
        Получает список выполнений для конкретной привычки с пагинацией и опциональными фильтрами.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки.
            status (HabitExecutionStatus | None): Фильтр по статусу выполнения.
            start_date (date | None): Начальная дата для фильтрации.
            end_date (date | None): Конечная дата для фильтрации.
            skip (int): Количество записей для пропуска.
            limit (int): Максимальное количество записей.

        Returns:
            Sequence[HabitExecution]: Список выполнений привычки.
        """
        log.debug(
            f"Получение выполнений для привычки ID: {habit_id} (status={status}, "
            f"start_date={start_date}, end_date={end_date}, skip={skip}, limit={limit})"
        )

        filters = [self.model.habit_id == habit_id]
        if status:
            filters.append(self.model.status == status)
        if start_date:
            filters.append(self.model.execution_date >= start_date)
        if end_date:
            filters.append(self.model.execution_date <= end_date)

        executions = await self.get_multi_by_filter(
            db_session,
            *filters,
            skip=skip,
            limit=limit,
            order_by=[self.model.execution_date.desc()],  # Сортировка по дате выполнения (сначала новые)
        )

        log.debug(f"Найдено {len(executions)} выполнений для привычки ID: {habit_id}.")
        return executions

    async def count_executions_for_habit(
        self,
        db_session: AsyncSession,
        *,
        habit_id: int,
        status: HabitExecutionStatus | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> int:
        """
        Подсчитывает количество выполнений для привычки с опциональными фильтрами.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки.
            status (HabitExecutionStatus | None): Фильтр по статусу выполнения.
            start_date (date | None): Начальная дата для фильтрации.
            end_date (date | None): Конечная дата для фильтрации.

        Returns:
            int: Количество выполнений.
        """
        log.debug(
            f"Подсчет выполнений для привычки ID: {habit_id} (status={status}, "
            f"start_date={start_date}, end_date={end_date})"
        )

        statement = select(func.count()).select_from(self.model)
        statement = statement.where(self.model.habit_id == habit_id)

        if status:
            statement = statement.where(self.model.status == status)
        if start_date:
            statement = statement.where(self.model.execution_date >= start_date)
        if end_date:
            statement = statement.where(self.model.execution_date <= end_date)

        result = await db_session.execute(statement)
        count = result.scalar_one()
        log.debug(f"Найдено {count} выполнений для привычки ID: {habit_id} по фильтрам.")
        return count

    async def get_last_n_executions(
        self, db_session: AsyncSession, *, habit_id: int, n_days: int
    ) -> Sequence[HabitExecution]:
        """
        Получает последние N записей о выполнении для привычки.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки.
            n_days (int): Количество последних дней/записей.

        Returns:
            Список экземпляров HabitExecution.
        """
        log.debug(f"Получение последних {n_days} выполнений для привычки ID: {habit_id}")

        executions = await self.get_multi_by_filter(
            db_session,
            self.model.habit_id == habit_id,
            limit=n_days,
            order_by=[self.model.execution_date.desc()],
        )

        log.debug(f"Найдено {len(executions)} из {n_days} последних выполнений для привычки ID: {habit_id}.")
        return executions
