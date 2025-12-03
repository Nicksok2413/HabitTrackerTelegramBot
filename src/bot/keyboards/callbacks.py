"""
Определение структур CallbackData для Inline-кнопок.

Позволяет типизированно передавать параметры при нажатии кнопок.

Модуль использует aiogram.filters.callback_data для создания типизированных
объектов, которые сериализуются в строку (например, "habit:12:view") и
автоматически парсятся обратно в объект при нажатии кнопки.
"""

from aiogram.filters.callback_data import CallbackData


class HabitsNavigationCallback(CallbackData, prefix="habits_list"):
    """
    Данные для навигации по списку привычек (пагинация).

    Attributes:
        page (int): Номер страницы, которую нужно открыть (начиная с 0).
    """
    page: int


class HabitDetailCallback(CallbackData, prefix="habit_detail"):
    """
    Данные для просмотра конкретной привычки.

    Attributes:
        habit_id (int): ID привычки для просмотра.
        page (int): Номер страницы списка, с которой перешли (для кнопки "Назад").
    """
    habit_id: int
    page: int


class HabitActionCallback(CallbackData, prefix="habit_action"):
    """
    Данные, связанные с действиями над конкретной привычкой.

    Attributes:
        id (int): ID привычки.
        action (str): Тип действия.
            Возможные значения:
            - "view": Просмотр деталей привычки.
            - "done": Отметка выполнения.
            - "delete": Удаление привычки.
            - "confirm_delete": Подтверждение удаления.
        page (int): Номер страницы для возврата.
    """
    id: int
    action: str
    page: str


