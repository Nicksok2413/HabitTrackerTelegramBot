"""Модель SQLAlchemy для Habit (Привычка)."""

from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .habit_execution import HabitExecution
    from .user import User


class Habit(Base):
    """
    Представляет привычку пользователя.

    Attributes:
        id: Первичный ключ, идентификатор привычки (унаследован от Base).
        user_id: Внешний ключ, связывающий привычку с пользователем.
        name: Название привычки.
        description: Описание привычки (опционально).
        target_days: Количество дней, необходимое для закрепления привычки (например, 21).
        time_to_remind: Время дня для отправки напоминания.
        is_active: Флаг, активна ли привычка в данный момент (для трекинга).
        current_streak: Текущая непрерывная серия выполнений привычки.
        max_streak: Максимальная достигнутая непрерывная серия выполнений.
        created_at: Время создания записи (унаследовано от TimestampMixin).
        updated_at: Время последнего обновления записи (унаследовано от TimestampMixin).
        user: Связь с пользователем, которому принадлежит привычка.
        executions: Список выполнений этой привычки.
    """

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    target_days: Mapped[int] = mapped_column(Integer, nullable=False)
    time_to_remind: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False, index=True)
    current_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Связи
    user: Mapped["User"] = relationship(back_populates="habits")
    executions: Mapped[list["HabitExecution"]] = relationship(back_populates="habit", cascade="all, delete-orphan")
