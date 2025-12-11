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
