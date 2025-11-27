"""Сервис для работы с выполнениями привычек."""

from datetime import date
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.exceptions import BadRequestException, NotFoundException
from src.api.core.logging import api_log as log
from src.api.models import Habit, HabitExecution, HabitExecutionStatus, User
from src.api.repositories import HabitExecutionRepository
from src.api.schemas import HabitExecutionSchemaCreate, HabitExecutionSchemaUpdate

from .base_service import BaseService
from .habit_service import HabitService


class HabitExecutionService(
    BaseService[
        HabitExecution,
        HabitExecutionRepository,
        HabitExecutionSchemaCreate,
        HabitExecutionSchemaUpdate,
    ]
):
    """
    Сервис для управления выполнениями привычек (HabitExecution).

    Отвечает за создание, чтение, обновление записей о выполнении привычек,
    а также за связанную бизнес-логику, такую как обновление счетчиков серий (стриков) у родительской привычки.
    """

    def __init__(
        self,
        execution_repository: HabitExecutionRepository,
        habit_service: HabitService,  # Добавляем зависимость от HabitService
    ):
        """
        Инициализирует сервис выполнения привычек.

        Args:
            execution_repository (HabitExecutionRepository): Репозиторий для работы с выполнениями.
            habit_service (HabitService): Сервис для работы с привычками.
        """
        super().__init__(repository=execution_repository)
        self.habit_service = habit_service  # Сохраняем сервис привычек

    async def _get_habit_and_verify_access(
        self, db_session: AsyncSession, *, habit_id: int, current_user: User
    ) -> Habit:
        """
        Вспомогательный метод для получения привычки и проверки прав доступа пользователя.

        Проверяет, существует ли привычка, принадлежит ли она текущему пользователю
        и активна ли она.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки для проверки.
            current_user (User): Аутентифицированный пользователь.

        Returns:
            Habit: Экземпляр модели Habit, если все проверки пройдены.

        Raises:
            NotFoundException: Если привычка с указанным ID не найдена.
            ForbiddenException: Если привычка не принадлежит текущему пользователю.
            BadRequestException: Если привычка не активна.
        """

        # Проверяем существование привычки и её принадлежность текущему пользователю
        # Используем метод сервиса привычек
        habit = await self.habit_service.get_habit_by_id_for_user(
            db_session,
            habit_id=habit_id,
            current_user=current_user
        )

        # Если проверки прошли, значит привычка существует и принадлежит пользователю
        # Проверяем активна ли привычка
        if not habit.is_active:
            # Если привычка не активна, выбрасываем исключение
            raise BadRequestException(
                message=f"Привычка '{habit.name}' не активна.",
                error_type="habit_not_active",
            )

        # Возвращаем найденный объект привычки
        return habit

    async def _update_habit_streaks(
        self,
        *,
        habit: Habit,
        new_execution_status: HabitExecutionStatus,
        is_new_execution_for_today: bool = True,
        previous_execution_status: HabitExecutionStatus | None = None,
    ) -> bool:
        """
        Обновляет счетчики серий (стриков) для привычки на основе нового статуса выполнения.

        Предназначен для обработки выполнения *сегодняшнего дня*.

        Args:
            habit (Habit): Экземпляр привычки для обновления.
            new_execution_status (HabitExecutionStatus): Новый статус выполнения.
            is_new_execution_for_today (bool): Флаг, указывающий, относится ли это выполнение
                                               к сегодняшнему дню (влияет на логику стриков).
            previous_execution_status (HabitExecutionStatus | None): Предыдущий статус выполнения,
                                                                   если это обновление существующей записи.

        Returns:
            bool: True, если стрики были изменены, иначе False.
        """
        # Флаг изменения стриков
        streaks_changed = False

        # Если выполнение не относится к сегодняшнему дню, логируем и возвращаем False
        if not is_new_execution_for_today:
            log.debug(f"Стрики для привычки ID: {habit.id} не обновляются, так как выполнение не за сегодня.")
            return False

        log.debug(
            f"Обновление стриков для привычки ID: {habit.id}. Новый статус: {new_execution_status.value}, "
            f"предыдущий: {previous_execution_status.value if previous_execution_status else 'N/A'}"
        )

        # Увеличиваем стрик если новое выполнение "DONE"
        if new_execution_status == HabitExecutionStatus.DONE:
            # И если предыдущий статус не был "DONE" (PENDING или NOT_DONE)
            if previous_execution_status != HabitExecutionStatus.DONE:
                habit.current_streak += 1
                streaks_changed = True
                log.debug(f"Текущий стрик увеличен до {habit.current_streak} для привычки ID: {habit.id}.")

                # Если текущий стрик становится больше максимального, записываем его значение в максимальный
                if habit.current_streak > habit.max_streak:
                    habit.max_streak = habit.current_streak
                    log.debug(f"Новый максимальный стрик {habit.max_streak} для привычки ID: {habit.id}.")

        # Сбрасываем стрик, если привычка была отмечена как "NOT_DONE"
        elif new_execution_status == HabitExecutionStatus.NOT_DONE:
            # И до этого она не была уже "NOT_DONE"
            if habit.current_streak > 0 and (previous_execution_status != HabitExecutionStatus.NOT_DONE):
                habit.current_streak = 0
                streaks_changed = True
                log.debug(f"Текущий стрик сброшен для привычки ID: {habit.id}.")
        # Если статус SKIPPED или PENDING, current_streak не меняется.
        # Если было DONE, а стало SKIPPED, стрик не откатываем.

        return streaks_changed

    async def record_habit_execution(
        self,
        db_session: AsyncSession,
        *,
        habit_id: int,
        execution_in: HabitExecutionSchemaCreate,
        current_user: User,
        execution_date_override: date | None = None,
    ) -> HabitExecution:
        """
        Записывает или обновляет выполнение привычки на указанную дату (по умолчанию - сегодня).

        Если запись о выполнении на указанную дату уже существует, ее статус обновляется.
        В противном случае создается новая запись.
        Также обновляются счетчики текущей и максимальной серий (стриков) у привычки,
        если выполнение относится к сегодняшнему дню.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки, для которой фиксируется выполнение.
            execution_in (HabitExecutionSchemaCreate): Схема с новым статусом выполнения.
            current_user (User): Аутентифицированный пользователь, выполняющий действие.
            execution_date_override (date | None): Дата, на которую фиксируется выполнение.
                                                Если None, используется текущая дата (сегодня).
                                                Позволяет отмечать выполнение за прошлые дни.

        Returns:
            HabitExecution: Созданная или обновленная запись о выполнении привычки.

        Raises:
            NotFoundException: Если привычка с указанным ID не найдена.
            ForbiddenException: Если у пользователя нет прав на доступ к этой привычке.
            BadRequestException: Если привычка не активна.
        """
        target_date = execution_date_override if execution_date_override is not None else date.today()
        log.info(
            f"Запись выполнения для привычки ID: {habit_id} на {target_date} "
            f"пользователем ID: {current_user.id} со статусом {execution_in.status.value}"
        )

        habit = await self._get_habit_and_verify_access(db_session, habit_id=habit_id, current_user=current_user)

        existing_execution = await self.repository.get_execution_by_habit_id_and_date(
            db_session, habit_id=habit_id, execution_date=target_date
        )

        previous_status: HabitExecutionStatus | None = None

        if existing_execution:
            log.debug(f"Обновление существующей записи (ID: {existing_execution.id}) о выполнении на {target_date}")
            previous_status = existing_execution.status
            existing_execution.status = execution_in.status
            db_execution = existing_execution
            # await self.repository.add(db_session, db_obj=db_execution)  # Пометить как измененный
        else:
            log.debug(f"Создание новой записи о выполнении для привычки ID: {habit_id} на {target_date}")
            db_execution = self.repository.model(
                habit_id=habit_id,
                execution_date=target_date,
                status=execution_in.status,
            )
            # await self.repository.add(db_session, db_obj=db_execution)

        streaks_were_updated = await self._update_habit_streaks(
            habit=habit,
            new_execution_status=execution_in.status,
            is_new_execution_for_today=(target_date == date.today()),  # Обновляем стрики только для сегодняшнего дня
            previous_execution_status=previous_status,
        )

        try:
            await db_session.flush()
            await db_session.refresh(db_execution)
            if streaks_were_updated:  # Обновить привычку, если она была изменена
                await db_session.refresh(habit)
            await db_session.commit()
            log.info(
                f"Выполнение привычки ID {habit_id} на {target_date} (ID: {db_execution.id}) "
                f"успешно записано со статусом {execution_in.status.value}."
            )
        except Exception as exc:
            log.error(
                f"Ошибка при записи выполнения привычки ID: {habit_id}: {exc}",
                exc_info=True,
            )
            await db_session.rollback()
            raise

        return db_execution

    async def get_executions_for_habit_by_user(
        self,
        db_session: AsyncSession,
        *,
        habit_id: int,
        current_user: User,
        status: HabitExecutionStatus | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[HabitExecution]:
        """
        Получает список записей о выполнении для указанной привычки,
        принадлежащей текущему аутентифицированному пользователю.

        Позволяет фильтровать выполнения по статусу и временному диапазону,
        а также использовать пагинацию.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки, для которой запрашиваются выполнения.
            current_user (User): Аутентифицированный пользователь.
            status (HabitExecutionStatus | None): Опциональный фильтр по статусу выполнения.
            start_date (date | None): Опциональная начальная дата для фильтрации (включительно).
            end_date (date | None): Опциональная конечная дата для фильтрации (включительно).
            skip (int): Количество записей для пропуска.
            limit (int): Максимальное количество записей для возврата.

        Returns:
            Sequence[HabitExecution]: Список найденных записей о выполнении привычки.

        Raises:
            NotFoundException: Если привычка с указанным ID не найдена.
            ForbiddenException: Если у пользователя нет прав на доступ к этой привычке.
            BadRequestException: Если привычка не активна.
        """
        log.info(f"Получение выполнений для привычки ID: {habit_id} (пользователь ID: {current_user.id})")
        # Проверка, что привычка существует и принадлежит пользователю.
        await self._get_habit_and_verify_access(db_session, habit_id=habit_id, current_user=current_user)

        return await self.repository.get_executions_for_habit(
            db_session,
            habit_id=habit_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
        )

    async def get_execution_details(
        self, db_session: AsyncSession, *, execution_id: int, current_user: User
    ) -> HabitExecution:
        """
        Получает детали конкретной записи о выполнении привычки.

        Проверяет, что запись существует и что связанная с ней привычка
        принадлежит текущему аутентифицированному пользователю.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            execution_id (int): ID записи о выполнении.
            current_user (User): Аутентифицированный пользователь.

        Returns:
            HabitExecution: Экземпляр записи о выполнении.

        Raises:
            NotFoundException: Если запись о выполнении или связанная привычка не найдены.
            ForbiddenException: Если у пользователя нет прав на доступ к связанной привычке.
            BadRequestException: Если привычка не активна.
        """
        # Получаем выполнение
        execution = await self.repository.get_by_id(db_session, obj_id=execution_id)

        if not execution:
            raise NotFoundException(
                message=f"Запись о выполнении с ID {execution_id} не найдена.",
                error_type="execution_not_found",
            )

        # Проверяем доступ через связанную привычку
        # _get_habit_and_verify_access выбросит исключение, если что-то не так с привычкой
        await self._get_habit_and_verify_access(db_session, habit_id=execution.habit_id, current_user=current_user)

        log.debug(f"Детали выполнения ID: {execution_id} успешно получены.")
        return execution

    async def update_execution_status(
        self,
        db_session: AsyncSession,
        *,
        execution_id: int,
        status_in: HabitExecutionSchemaUpdate,
        current_user: User,
    ) -> HabitExecution:
        """
        Обновляет статус существующей записи о выполнении привычки.

        Проверяет права доступа пользователя к связанной привычке.
        Логика обновления стриков при изменении статуса выполнения за прошлые дни
        для MVP упрощена (стрики обновляются при фиксации сегодняшнего дня).

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            execution_id (int): ID записи о выполнении для обновления.
            status_in (HabitExecutionSchemaUpdate): Схема с новым статусом.
            current_user (User): Аутентифицированный пользователь.

        Returns:
            HabitExecution: Обновленная запись о выполнении.

        Raises:
            NotFoundException: Если запись о выполнении или связанная привычка не найдены.
            ForbiddenException: Если у пользователя нет прав на доступ к связанной привычке.
            BadRequestException: Если привычка не активна.
        """
        log.info(
            f"Обновление статуса выполнения ID: {execution_id} на {status_in.status.value} "
            f"пользователем ID: {current_user.id}"
        )

        execution_to_update = await self.get_execution_details(
            db_session,
            execution_id=execution_id,
            current_user=current_user,
        )

        if execution_to_update.status == status_in.status:
            log.debug(f"Статус выполнения ID: {execution_id} уже {status_in.status.value}, обновление не требуется.")
            return execution_to_update  # Статус не изменился, просто возвращаем

        previous_status = execution_to_update.status
        execution_to_update.status = status_in.status

        # Получаем привычку для возможного обновления стриков
        # get_execution_details уже вызвал _get_habit_and_verify_access,
        # который проверил, что привычка существует и принадлежит пользователю.
        # Поэтому здесь можем быть уверены, что привычка найдется.
        habit = await self.habit_service.get_by_id(db_session, obj_id=execution_to_update.habit_id)

        streaks_were_updated = await self._update_habit_streaks(
            habit=habit,
            new_execution_status=status_in.status,
            is_new_execution_for_today=(execution_to_update.execution_date == date.today()),
            previous_execution_status=previous_status,
        )

        try:
            await db_session.flush()
            await db_session.refresh(execution_to_update)
            if streaks_were_updated:
                await db_session.refresh(habit)
            await db_session.commit()
            log.info(f"Статус выполнения ID: {execution_id} успешно обновлен на {status_in.status.value}.")
        except Exception as exc:
            log.error(
                f"Ошибка при обновлении статуса выполнения ID: {execution_id}: {exc}",
                exc_info=True,
            )
            await db_session.rollback()
            raise

        return execution_to_update
