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
        #  Конвертируем в словарь
        habit_in_data = habit_in.model_dump()

        # Устанавливаем target_days из настроек, если в переданных данных - None
        if not habit_in_data.get("target_days"):
            habit_in_data["target_days"] = settings.DAYS_TO_FORM_HABIT

        # Создаем новый объект привычки
        habit_obj = self.repository.model(**habit_in_data, user_id=current_user.id)

        # Добавляем объект в сессию
        db_session.add(habit_obj)

        try:
            # Фиксируем транзакцию (бизнес-операция завершена успешно)
            await db_session.commit()

            # Обновляем данные из базы данных
            await db_session.refresh(habit_obj)

            # Логируем успех
            log.info(f"Привычка ID {habit_obj.id} для пользователя (ID: {current_user.id}) успешно создана.")
            # Возвращаем созданный объект привычки
            return habit_obj
        except Exception as exc:
            # При любой ошибке откатываем транзакцию, чтобы сохранить целостность данных
            await db_session.rollback()
            # Логируем ошибку и выбрасываем исключение
            log.error(f"Ошибка при создании привычки для пользователя ID: {current_user.id}: {exc}", exc_info=True)
            raise exc

    async def get_habit_by_id_for_user(self, db_session: AsyncSession, *, habit_id: int, current_user: User) -> Habit:
        """
        Получает привычку по ID, проверяя существует ли она и принадлежит ли текущему пользователю.

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
        # Проверка существования привычки
        # Если объект привычки не найден, будет выброшено исключение
        habit = await self.get_by_id(db_session, obj_id=habit_id)

        # Если объект привычки найден, проверяем его принадлежность текущему пользователю
        if habit.user_id != current_user.id:
            # Если пользователи не совпадают, логируем и выбрасываем исключение
            log.warning(f"Пользователь ID: {current_user.id} пытался получить доступ к чужой привычке ID: {habit_id}")
            raise ForbiddenException(
                message="У вас нет прав для доступа к этой привычке.",
                error_type="habit_access_forbidden",
            )

        # Возвращаем найденный объект привычки
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
        # Проверяем существование привычки и её принадлежность текущему пользователю
        await self.get_habit_by_id_for_user(db_session, habit_id=habit_id, current_user=current_user)

        # Если проверки прошли, значит привычка существует и принадлежит пользователю
        # Подгружаем привычку с выполнениями
        habit = await self.repository.get_habit_by_id_with_executions(db_session, habit_id=habit_id)

        # Если привычка с выполнениями не найдена, выбрасываем исключение
        if not habit:
            raise NotFoundException(
                message=f"Привычка (ID {habit_id}) с загруженными выполнениями не найдена.",
                error_type="habit_not_found",
            )

        # Возвращаем найденный объект привычки
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

        # Проверяем существование привычки и её принадлежность текущему пользователю
        habit_to_update = await self.get_habit_by_id_for_user(db_session, habit_id=habit_id, current_user=current_user)

        # Если проверки прошли, значит привычка существует и принадлежит пользователю
        # Обновляем объект привычки
        log.info(f"Обновление привычки ID: {habit_id} для пользователя ID: {current_user.id}")
        return await super().update(db_session, obj_id=habit_to_update.id, obj_in=habit_in)

    async def remove_habit_for_user(self, db_session: AsyncSession, *, habit_id: int, current_user: User) -> None:
        """
        Удаляет привычку, проверяя, что она принадлежит текущему пользователю.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки для удаления.
            current_user (User): Аутентифицированный пользователь.
        """
        # Проверяем существование привычки и её принадлежность текущему пользователю
        habit_to_remove = await self.get_habit_by_id_for_user(db_session, habit_id=habit_id, current_user=current_user)

        # Если проверки прошли, значит привычка существует и принадлежит пользователю
        # Удаляем объект привычки
        log.info(f"Удаление привычки ID: {habit_id} для пользователя ID: {current_user.id}")
        return await super().delete(db_session, obj_id=habit_to_remove.id)
