"""
Генераторы Inline-клавиатур (кнопок под сообщениями).

Содержит функции для создания клавиатур списка привычек (с пагинацией),
детального просмотра и меню действий с конкретной привычкой.
"""

from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.keyboards.callbacks import HabitDetailCallback, HabitsNavigationCallback, HabitActionCallback


def get_habits_list_keyboard(habits: list[dict[str, Any]], page: int, has_next: bool) -> InlineKeyboardMarkup:
    """
    Генерирует клавиатуру со списком привычек и кнопками навигации.

    Args:
        habits (list): Список словарей с данными привычек.
        page (int): Номер текущей страницы (начиная с 0).
        has_next (bool): Флаг, указывающий, есть ли следующая страница.

    Returns:
        InlineKeyboardMarkup: Клавиатура списка.
    """
    builder = InlineKeyboardBuilder()

    # Генерируем кнопки для каждой привычки
    for habit in habits:
        # Визуальная индикация: огонек, если есть стрик > 0
        status_icon = "🔥" if habit.get("current_streak", 0) > 0 else "🔹"
        button_text = f"{status_icon} {habit['name']}"

        # При нажатии передаем ID и действие 'view'
        builder.button(text=button_text, callback_data=HabitDetailCallback(habit_id=habit["id"], page=page))

    # Настраиваем макет: каждая привычка на новой строке (1 колонка)
    builder.adjust(1)

    # Формируем ряд кнопок навигации (Pagination)
    nav_buttons = []

    # Кнопка "Назад", если это не первая страница
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=HabitsNavigationCallback(page=page - 1).pack())
        )

    # Индикатор страницы (неактивная кнопка)
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page + 1}", callback_data="noop"))

    # Кнопка "Вперед", если есть следующая страница
    if has_next:
        nav_buttons.append(
            InlineKeyboardButton(text="Вперед ➡️", callback_data=HabitsNavigationCallback(page=page + 1).pack())
        )

    # Добавляем ряд навигации в билдер, если кнопки есть
    if nav_buttons:
        builder.row(*nav_buttons)

    return builder.as_markup()


def get_habit_detail_keyboard(habit_id: int, page: int, is_done_today: bool = False) -> InlineKeyboardMarkup:
    """
    Генерирует клавиатуру для детального просмотра привычки.

    Включает кнопки действий (выполнить, отменить выполнение, удалить) и навигации (назад).

    Args:
        habit_id (int): ID привычки.
        page (int): Номер страницы списка для возврата.
        is_done_today (bool): Выполнена ли привычка сегодня.
                              Влияет на отображение кнопки выполнения.

    Returns:
        InlineKeyboardMarkup: Клавиатура с действиями.
    """
    builder = InlineKeyboardBuilder()

    # Кнопка выполнения
    if not is_done_today:
        builder.button(
            text="✅ Выполнить сегодня", callback_data=HabitActionCallback(habit_id=habit_id, page=page, action="done")
        )
    # Кнопка отмены выполнения
    else:
        builder.button(
            text="↩️ Отменить выполнение",
            callback_data=HabitActionCallback(habit_id=habit_id, page=page, action="set_pending"),
        )

    # Кнопка удаления
    builder.button(
        text="🗑 Удалить", callback_data=HabitActionCallback(habit_id=habit_id, page=page, action="request_delete")
    )

    # Кнопка возврата к списку
    builder.button(text="🔙 Назад к списку", callback_data=HabitsNavigationCallback(page=page).pack())

    # Настраиваем макет: каждая кнопка на новой строке (1 колонка)
    builder.adjust(1)

    return builder.as_markup()


def get_habit_delete_confirmation_keyboard(habit_id: int, page: int) -> InlineKeyboardMarkup:
    """
    Генерирует клавиатуру подтверждения удаления.

    Args:
        habit_id (int): ID привычки.
        page (int): Номер страницы списка для возврата.

    Returns:
        InlineKeyboardMarkup: Клавиатура с действиями.
    """
    builder = InlineKeyboardBuilder()

    # Кнопка подтверждения удаления
    builder.button(
        text="🔥 Да, удалить навсегда",
        callback_data=HabitActionCallback(habit_id=habit_id, page=page, action="confirm_delete"),
    )

    # Кнопка отмены удаления
    builder.button(
        text="❌ Нет, отмена",
        # Возвращаем пользователя к просмотру привычки ("view"), а не к списку
        callback_data=HabitActionCallback(habit_id=habit_id, page=page, action="view"),
    )

    # Настраиваем макет: каждая кнопка на новой строке (1 колонка)
    builder.adjust(1)

    return builder.as_markup()
