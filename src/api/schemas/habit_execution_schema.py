"""Схемы Pydantic для модели HabitExecution."""

from datetime import date, datetime

from pydantic import Field

from src.api.models import HabitExecutionStatus  # Импортируем Enum

from .base_schema import BaseSchema


class HabitExecutionSchemaBase(BaseSchema):
    """Базовая схема для выполнения привычки."""

    execution_date: date = Field(..., description="Дата, на которую зафиксировано выполнение")
    status: HabitExecutionStatus = Field(..., description="Статус выполнения привычки")


class HabitExecutionSchemaCreate(BaseSchema):  # Не наследуем от HabitExecutionSchemaBase
    """Схема для создания (фиксации) новой записи о выполнении привычки."""

    # habit_id будет браться из path parameter эндпоинта
    # execution_date будет установлена сервером как текущая дата
    status: HabitExecutionStatus = Field(
        ...,
        description="Статус выполнения на сегодня (например, DONE, NOT_DONE, SKIPPED)",
    )


class HabitExecutionSchemaUpdate(BaseSchema):
    """
    Схема для обновления статуса выполнения привычки.
    Только статус может быть изменен.
    """

    status: HabitExecutionStatus = Field(..., description="Новый статус выполнения привычки")


class HabitExecutionSchemaRead(HabitExecutionSchemaBase):
    """Схема для чтения данных о выполнении привычки (ответа API)."""

    id: int = Field(..., description="ID записи о выполнении")
    habit_id: int = Field(..., description="ID привычки, к которой относится выполнение")
    # execution_date и status наследуются
    created_at: datetime = Field(..., description="Время создания записи о выполнении")
    updated_at: datetime = Field(..., description="Время последнего обновления записи о выполнении")
