"""Схемы Pydantic для модели User."""

from datetime import datetime

from pydantic import Field

from .base_schema import BaseSchema

# Импортируем схемы зависимостей, когда они будут созданы
# from src.api.schemas.habit_schema import HabitSchemaRead


class UserSchemaBase(BaseSchema):
    """Базовая схема для пользователя, содержит общие поля."""

    username: str | None = Field(
        None,
        max_length=100,
        description="Username пользователя в Telegram (может отсутствовать)",
    )
    first_name: str | None = Field(None, max_length=100, description="Имя пользователя в Telegram")
    last_name: str | None = Field(
        None,
        max_length=100,
        description="Фамилия пользователя в Telegram (может отсутствовать)",
    )


class UserSchemaCreate(UserSchemaBase):
    """Схема для создания нового пользователя (данные от Telegram)."""

    telegram_id: int = Field(..., gt=0, description="Уникальный идентификатор пользователя в Telegram")
    # username, first_name, last_name наследуются


class UserSchemaUpdate(BaseSchema):
    """
    Схема для обновления данных пользователя.
    Все поля опциональны.
    """

    username: str | None = Field(None, max_length=100, description="Новый Username пользователя в Telegram")
    first_name: str | None = Field(None, max_length=100, description="Новое имя пользователя")
    last_name: str | None = Field(None, max_length=100, description="Новая фамилия пользователя")
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

    # Если мы хотим возвращать привычки пользователя вместе с данными пользователя:
    # habits: list["HabitSchemaRead"] = [] # Важно: кавычки для отложенной аннотации


# Отложенное обновление ссылок для циклических зависимостей, если habits включены
# UserSchemaRead.model_rebuild()
