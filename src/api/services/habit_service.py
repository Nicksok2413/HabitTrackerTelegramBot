"""Сервис для работы с привычками."""

from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.config import settings  # Для значения target_days по умолчанию
from src.api.core.exceptions import ForbiddenException, NotFoundException
from src.api.core.logging import api_log as log
from src.api.models import Habit, User
from src.api.repositories import HabitRepository
from src.api.schemas import HabitSchemaCreate, HabitSchemaUpdate

from .base_service import BaseService


class HabitService(BaseService[Habit, HabitRepository, HabitSchemaCreate, HabitSchemaUpdate]):
    """
    Сервис для управления привычками.

    Отвечает за создание, чтение, обновление и удаление записей о привычках.
    """

    def __init__(self, habit_repository: HabitRepository):
        """
        Инициализирует сервис для репозитория HabitRepository.

        Args:
            habit_repository (HabitRepository): Репозиторий для работы с привычками.
        """
        super().__init__(repository=habit_repository)

    async def create_habit_for_user(
        self,
        db_session: AsyncSession,
        *,
        habit_in: HabitSchemaCreate,
        current_user: User,
    ) -> Habit:
        """
        Создает новую привычку для указанного пользователя.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_in (HabitSchemaCreate): Данные для создания привычки.
            current_user (User): Аутентифицированный пользователь, создающий привычку.

        Returns:
            Habit: Созданная привычка.
        """
        log.info(f"Создание привычки '{habit_in.name}' для пользователя ID: {current_user.id}")

        # Устанавливаем target_days из настроек, если не передано в схеме
        target_days = habit_in.target_days if habit_in.target_days is not None else settings.DAYS_TO_FORM_HABIT

        # Создаем объект модели Habit напрямую, чтобы добавить user_id и настроенный target_days
        # BaseRepository.create ожидает схему, а нам нужно добавить user_id
        habit_model_data = habit_in.model_dump(
            exclude_unset=True, exclude={"target_days"}
        )  # Исключаем target_days, если он None

        db_habit = self.repository.model(
            **habit_model_data,
            user_id=current_user.id,
            target_days=target_days,  # Используем рассчитанное значение
        )

        # await self.repository.add(db_session, db_obj=db_habit)

        try:
            await db_session.flush()
            await db_session.refresh(db_habit)
            await db_session.commit()
            log.info(f"Привычка (ID: {db_habit.id}) успешно создана для пользователя ID: {current_user.id}.")
        except Exception as exc:
            log.error(
                f"Ошибка при создании привычки для пользователя ID: {current_user.id}: {exc}",
                exc_info=True,
            )
            await db_session.rollback()
            raise
        return db_habit

    async def get_habit_by_id_for_user(self, db_session: AsyncSession, *, habit_id: int, current_user: User) -> Habit:
        """
        Получает привычку по ID, проверяя, что она принадлежит текущему пользователю.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки.
            current_user (User): Аутентифицированный пользователь.

        Returns:
            Habit: Найденная привычка.

        Raises:
            NotFoundException: Если привычка не найдена.
            ForbiddenException: Если привычка не принадлежит пользователю.
        """
        log.info(f"Получение привычки ID: {habit_id} для пользователя ID: {current_user.id}")
        habit = await self.repository.get_by_id(db_session, obj_id=habit_id)

        if not habit:
            raise NotFoundException(
                message=f"Привычка с ID {habit_id} не найдена.",
                error_type="habit_not_found",
            )

        if habit.user_id != current_user.id:
            log.warning(f"Пользователь ID: {current_user.id} пытался получить доступ к чужой привычке ID: {habit_id}")
            raise ForbiddenException(
                message="У вас нет прав для доступа к этой привычке.",
                error_type="habit_access_forbidden",
            )

        return habit

    async def get_habit_with_executions_for_user(
        self, db_session: AsyncSession, *, habit_id: int, current_user: User
    ) -> Habit:
        """
        Получает привычку по ID с выполнениями, проверяя принадлежность пользователю.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки.
            current_user (User): Аутентифицированный пользователь.

        Returns:
            Habit: Найденная привычка с выполнениями.

        Raises:
            NotFoundException: Если привычка не найдена.
            ForbiddenException: Если привычка не принадлежит пользователю.
        """
        # Проверяем существование привычки и её принадлежность текущему пользователю.
        await self.get_habit_by_id_for_user(db_session, habit_id=habit_id, current_user=current_user)

        # Если мы здесь, значит ошибок не было (привычка существует и принадлежит пользователю).
        # Теперь подгружаем привычку с выполнениями.
        log.info(f"Получение привычки ID: {habit_id} с выполнениями для пользователя ID: {current_user.id}")
        habit = await self.repository.get_habit_with_executions(db_session, habit_id=habit_id)

        if not habit:
            raise NotFoundException(
                message=f"Привычка с ID {habit_id} не найдена.",
                error_type="habit_not_found",
            )

        return habit

    async def get_habits_for_user(
        self,
        db_session: AsyncSession,
        *,
        current_user: User,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False,
    ) -> Sequence[Habit]:
        """
        Получает список привычек для текущего пользователя с пагинацией.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            current_user (User): Аутентифицированный пользователь.
            skip (int): Количество записей для пропуска.
            limit (int): Максимальное количество записей.
            active_only (bool): Если True, возвращает только активные привычки.

        Returns:
            Sequence[Habit]: Список привычек пользователя.
        """
        log.info(f"Получение привычек для пользователя ID: {current_user.id} (active_only={active_only})")

        return await self.repository.get_habits_by_user_id(
            db_session,
            user_id=current_user.id,
            skip=skip,
            limit=limit,
            active_only=active_only,
        )

    async def update_habit_for_user(
        self,
        db_session: AsyncSession,
        *,
        habit_id: int,
        habit_in: HabitSchemaUpdate,
        current_user: User,
    ) -> Habit:
        """
        Обновляет привычку, проверяя, что она принадлежит текущему пользователю.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки для обновления.
            habit_in (HabitSchemaUpdate): Данные для обновления.
            current_user (User): Аутентифицированный пользователь.

        Returns:
            Habit: Обновленная привычка.
        """
        log.info(f"Обновление привычки ID: {habit_id} для пользователя ID: {current_user.id}")
        habit_to_update = await self.get_habit_by_id_for_user(db_session, habit_id=habit_id, current_user=current_user)

        # Используем метод update из BaseService
        return await super().update(db_session, obj_id=habit_to_update.id, obj_in=habit_in)

    async def remove_habit_for_user(
        self, db_session: AsyncSession, *, habit_id: int, current_user: User
    ) -> Habit | None:
        """
        Удаляет привычку, проверяя, что она принадлежит текущему пользователю.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки для удаления.
            current_user (User): Аутентифицированный пользователь.

        Returns:
            Habit | None: Удаленная привычка.
        """
        log.info(f"Удаление привычки ID: {habit_id} для пользователя ID: {current_user.id}")
        habit_to_remove = await self.get_habit_by_id_for_user(db_session, habit_id=habit_id, current_user=current_user)

        # Используем метод remove из BaseService
        return await super().delete(db_session, obj_id=habit_to_remove.id)
