"""Схемы Pydantic для модели User."""

from datetime import datetime

from pydantic import Field

from .base_schema import BaseSchema


class UserSchemaBase(BaseSchema):
    """Базовая схема для пользователя."""

    username: str | None = Field(
        None,
        max_length=100,
        description="Username пользователя в Telegram (может отсутствовать)",
    )
    first_name: str | None = Field(
        None, max_length=100, description="Имя пользователя в Telegram (может отсутствовать)"
    )
    last_name: str | None = Field(
        None,
        max_length=100,
        description="Фамилия пользователя в Telegram (может отсутствовать)",
    )
    timezone: str = Field("UTC", max_length=50, description="Часовой пояс (например, Europe/Moscow)")
    # Валидатор для часового пояса можно добавить позже, используя pytzone


class UserSchemaCreate(UserSchemaBase):
    """Схема для создания нового пользователя (данные от Telegram)."""

    telegram_id: int = Field(..., gt=0, description="Уникальный идентификатор пользователя в Telegram")
    # Остальные поля наследуются и являются опциональными или имеют значения по умолчанию


class UserSchemaUpdate(BaseSchema):
    """
    Схема для обновления данных пользователя.
    Все поля опциональны.
    """

    username: str | None = Field(None, max_length=100, description="Новый Username пользователя в Telegram")
    first_name: str | None = Field(None, max_length=100, description="Новое имя пользователя")
    last_name: str | None = Field(None, max_length=100, description="Новая фамилия пользователя")
    timezone: str | None = Field(None, max_length=50, description="Новый часовой пояс пользователя")
    is_active: bool | None = Field(None, description="Статус активности пользователя")
    is_bot_blocked: bool | None = Field(None, description="Статус блокировки бота пользователем")


class UserSchemaRead(UserSchemaBase):
    """Схема для чтения данных пользователя (ответа API)."""

    id: int = Field(..., description="Внутренний ID пользователя")
    telegram_id: int = Field(..., description="Уникальный идентификатор пользователя в Telegram")
    is_active: bool = Field(..., description="Статус активности пользователя")
    is_bot_blocked: bool = Field(..., description="Статус блокировки бота пользователем")
    created_at: datetime = Field(..., description="Время создания записи пользователя")
    updated_at: datetime = Field(..., description="Время последнего обновления записи пользователя")

    # Если нужно возвращать привычки пользователя вместе с его данными:
    # habits: list["HabitSchemaRead"] = Field(default_factory=list)
