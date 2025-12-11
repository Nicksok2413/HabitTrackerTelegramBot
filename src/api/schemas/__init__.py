"""Инициализация модуля схем Pydantic."""

# Экспортируем Enum
from src.api.models import HabitExecutionStatus

from .base_schema import BaseSchema
from .habit_execution_schema import (
    HabitExecutionSchemaBase,
    HabitExecutionSchemaCreate,
    HabitExecutionSchemaRead,
    HabitExecutionSchemaUpdate,
)
from .habit_schema import (
    HabitSchemaBase,
    HabitSchemaCreate,
    HabitSchemaRead,
    HabitSchemaReadWithExecutions,
    HabitSchemaUpdate,
)
from .user_schema import (
    UserSchemaBase,
    UserSchemaCreate,
    UserSchemaRead,
    UserSchemaUpdate,
)

__all__ = [
    "BaseSchema",
    "UserSchemaBase",
    "UserSchemaCreate",
    "UserSchemaRead",
    "UserSchemaUpdate",
    "HabitSchemaBase",
    "HabitSchemaCreate",
    "HabitSchemaRead",
    "HabitSchemaReadWithExecutions",
    "HabitSchemaUpdate",
    "HabitExecutionSchemaBase",
    "HabitExecutionSchemaCreate",
    "HabitExecutionSchemaRead",
    "HabitExecutionSchemaUpdate",
    "HabitExecutionStatus",  # Экспорт Enum
]

# Выполняем model_rebuild для схем, которые могут иметь циклические зависимости
# с отложенными аннотациями типов (если бы они были активно использованы)
HabitSchemaReadWithExecutions.model_rebuild()
# UserSchemaRead.model_rebuild()
