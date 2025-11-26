"""Сервис для работы с пользователями."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.exceptions import NotFoundException
from src.api.core.logging import api_log as log
from src.api.models import User
from src.api.repositories import UserRepository
from src.api.schemas import UserSchemaCreate, UserSchemaUpdate

from .base_service import BaseService


class UserService(BaseService[User, UserRepository, UserSchemaCreate, UserSchemaUpdate]):
    """
    Сервис для управления пользователями.

    Отвечает за создание, чтение, обновление записей о пользователях.
    """

    def __init__(self, user_repository: UserRepository):
        """
        Инициализирует сервис для репозитория UserRepository.

        Args:
            user_repository (UserRepository): Репозиторий для работы с пользователями.
        """
        super().__init__(repository=user_repository)

    async def get_user_by_telegram_id(self, db_session: AsyncSession, *, telegram_id: int) -> User | None:
        """
        Получает пользователя по Telegram ID.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            telegram_id (int): Telegram ID пользователя.

        Returns:
            User | None: Объект пользователя или None, если не найден.
        """
        return await self.repository.get_by_telegram_id(db_session, telegram_id=telegram_id)

    async def get_user_by_username(self, db_session: AsyncSession, *, username: str) -> User | None:
        """
        Получает пользователя по его Username (если он есть).

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            username (str): Имя пользователя в Telegram.

        Returns:
            User | None: Объект пользователя или None, если не найден.
        """
        return await self.repository.get_by_username(db_session, username=username)

    async def get_or_create_user(self, db_session: AsyncSession, *, user_in: UserSchemaCreate) -> User:
        """
        Получает существующего пользователя по Telegram ID или создает нового, если он не найден.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            user_in (UserSchemaCreate): Данные пользователя для поиска или создания.

        Returns:
            User: Существующий или созданный пользователь.
        """
        # Проверяем существования пользователя
        existing_user = await self.repository.get_by_telegram_id(db_session, telegram_id=user_in.telegram_id)

        # Если пользователь существует, возвращаем его
        if existing_user:
            return existing_user

        # Если пользователя нет, создаем нового пользователя
        return await super().create(db_session, obj_in=user_in)

    async def update_user_by_telegram_id(
        self,
        db_session: AsyncSession,
        *,
        telegram_id: int,
        user_update_data: UserSchemaUpdate,
    ) -> User:
        """
        Обновляет данные пользователя по его Telegram ID.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            telegram_id (int): Telegram ID пользователя.
            user_update_data (UserSchemaUpdate): Данные для обновления.

        Returns:
            User: Обновленный объект пользователя.

        Raises:
            NotFoundException: Если пользователь с указанным Telegram ID не найден.
        """
        # Проверяем существования пользователя
        user_to_update = await self.repository.get_by_telegram_id(db_session, telegram_id=telegram_id)

        # Если пользователя нет, выбрасываем ошибку
        if not user_to_update:
            raise NotFoundException(
                message=f"Пользователь с Telegram ID {telegram_id} не найден.",
                error_type="user_not_found",
            )

        # Обновляем пользователя
        return await super().update(db_session, obj_id=user_to_update.id, obj_in=user_update_data)

    # Другие специфичные для пользователя методы, если нужны...
    # Например, деактивация пользователя, проверка блокировки бота и т.д.
