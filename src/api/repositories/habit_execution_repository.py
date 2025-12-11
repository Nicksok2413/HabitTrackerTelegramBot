"""Репозиторий для работы с моделью HabitExecution."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.logging import api_log as log
from src.api.models import HabitExecution, HabitExecutionStatus
from src.api.repositories import BaseRepository
from src.api.schemas import HabitExecutionSchemaCreate, HabitExecutionSchemaUpdate


class HabitExecutionRepository(BaseRepository[HabitExecution, HabitExecutionSchemaCreate, HabitExecutionSchemaUpdate]):
    """
    Репозиторий для выполнения CRUD-операций с моделью HabitExecution.

    Наследует общие методы от BaseRepository и содержит специфичные для HabitExecution методы.
    """

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

    async def get_done_habit_ids_for_date(
        self, db_session: AsyncSession, *, habit_ids: list[int], check_date: date
    ) -> set[int]:
        """
        Возвращает множество ID привычек, которые были выполнены (DONE) в указанную дату.
        Используется для массовой проверки статусов списка привычек.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_ids (list[int]): Список с ID привычек.
            check_date (date): Дата, на которую выполняется поиск выполнений.

        Returns:
            set[int]: Множество ID привычек.
        """
        if not habit_ids:
            return set()

        log.debug(f"Получение множества ID привычек, выполненных на дату {check_date}, для привычек с ID: {habit_ids}")

        statement = select(self.model.habit_id).where(
            self.model.habit_id.in_(habit_ids),
            self.model.execution_date == check_date,
            self.model.status == HabitExecutionStatus.DONE,
        )

        result = await db_session.execute(statement)

        # Преобразуем в множество ID (set) для быстрого поиска
        habits_set = set(result.scalars().all())

        log.debug(f"Найдено {len(habits_set)} привычек выполненных на дату: {check_date}.")

        # Возвращаем множество
        return habits_set
