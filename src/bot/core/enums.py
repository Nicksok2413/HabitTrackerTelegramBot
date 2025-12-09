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

    # --- Действия для редактирования привычки ---
    OPEN_EDIT_MENU = "open_edit"  # Открыть меню редактирования
    EDIT_NAME = "edit_name"  # Редактировать название
    EDIT_DESC = "edit_desc"  # Редактировать описание
    EDIT_TIME = "edit_time"  # Редактировать время
    EDIT_DAYS = "edit_days"  # Редактировать цель


class ProfileAction(StrEnum):
    """Действия в профиле."""

    CHANGE_TIMEZONE = "change_tz"  # Сменить часовой пояс
