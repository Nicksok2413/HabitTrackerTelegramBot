"""
Перечисления (Enums) для бота.

Используются для избежания "магических строк" в callback_data и хендлерах.
"""

from enum import StrEnum

# Константа - заглушка
IGNORE_CALLBACK = "ignore"


class HabitAction(StrEnum):
    """Действия с привычкой."""

    VIEW = "view"  # Просмотр деталей
    DONE = "done"  # Выполнить
    SET_PENDING = "set_pending"  # Отменить выполнение
    REQUEST_DELETE = "req_del"  # Запрос удаления
    CONFIRM_DELETE = "conf_del"  # Подтверждение удаления


class ProfileAction(StrEnum):
    """Действия в профиле."""

    CHANGE_TIMEZONE = "change_tz"  # Сменить часовой пояс
