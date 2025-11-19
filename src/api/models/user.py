"""Модель SQLAlchemy для User (Пользователь)."""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .habit import Habit


class User(Base):
    """
    Представляет пользователя Telegram в приложении.

    Attributes:
        id: Первичный ключ, внутренний идентификатор пользователя (унаследован от Base).
        telegram_id: Уникальный идентификатор пользователя в Telegram.
        username: Username пользователя в Telegram (может быть None).
        first_name: Имя пользователя в Telegram (может быть None).
        last_name: Фамилия пользователя в Telegram (может быть None).
        is_active: Флаг, активен ли пользователь в системе.
        is_bot_blocked: Флаг, заблокировал ли пользователь бота.
        created_at: Время создания записи (унаследовано от TimestampMixin).
        updated_at: Время последнего обновления записи (унаследовано от TimestampMixin).
        habits: Список привычек, созданных пользователем.
    """

    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(100), index=True)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_bot_blocked: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Связи
    habits: Mapped[list["Habit"]] = relationship(back_populates="user", cascade="all, delete-orphan")
