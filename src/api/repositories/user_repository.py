"""Репозиторий для работы с моделью User."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.logging import api_log as log
from src.api.models import User
from src.api.repositories import BaseRepository
from src.api.schemas import UserSchemaCreate, UserSchemaUpdate


class UserRepository(BaseRepository[User, UserSchemaCreate, UserSchemaUpdate]):
    """
    Репозиторий для выполнения CRUD-операций с моделью User.

    Наследует общие методы от BaseRepository и содержит специфичные для User методы.
    """

    async def get_by_telegram_id(self, db_session: AsyncSession, *, telegram_id: int) -> User | None:
        """
        Получает пользователя по его Telegram ID.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            telegram_id (int): Уникальный идентификатор пользователя в Telegram.

        Returns:
            User | None: Экземпляр модели User или None, если пользователь не найден.
        """
        log.debug(f"Получение пользователя по Telegram ID: {telegram_id}")
        user = await self.get_by_filter_first_or_none(db_session, self.model.telegram_id == telegram_id)

        status = f"найден (ID: {user.id})" if user else "не найден"
        log.debug(f"Пользователь с Telegram ID {telegram_id} {status}.")

        return user

    async def get_by_username(self, db_session: AsyncSession, *, username: str) -> User | None:
        """
        Получает пользователя по его Username (если он есть).
        Учитывает, что Username может быть None, поэтому ищет только если передан.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            username (str): Имя пользователя в Telegram.

        Returns:
            User | None: Экземпляр модели User или None, если пользователь не найден.
        """
        if not username:  # Не ищем, если username не предоставлен или пустой
            return None

        log.debug(f"Получение пользователя по Username: {username}")
        user = await self.get_by_filter_first_or_none(db_session, self.model.username == username)

        status = f"найден (ID: {user.id})" if user else "не найден"
        log.debug(f"Пользователь с Username {username} {status}.")

        return user

    async def update_by_telegram_id(
        self, db_session: AsyncSession, *, telegram_id: int, obj_in: UserSchemaUpdate
    ) -> User | None:
        """
        Обновляет данные пользователя, найденного по Telegram ID.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            telegram_id (int): Telegram ID пользователя для обновления.
            obj_in (UserSchemaUpdate): Схема Pydantic с данными для обновления.

        Returns:
            User | None: Обновленный экземпляр User или None, если пользователь не найден.
        """
        log.debug(f"Обновление пользователя по Telegram ID: {telegram_id}")

        user_to_update = await self.get_by_telegram_id(db_session, telegram_id=telegram_id)

        if not user_to_update:
            return None

        return await super().update(db_session, db_obj=user_to_update, obj_in=obj_in)
