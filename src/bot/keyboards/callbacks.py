"""
Определение структур CallbackData для Inline-кнопок.

Позволяет типизированно передавать параметры при нажатии кнопок.

Модуль использует aiogram.filters.callback_data для создания типизированных
объектов, которые сериализуются в строку (например, "habit:12:view") и
автоматически парсятся обратно в объект при нажатии кнопки.
"""

from aiogram.filters.callback_data import CallbackData

from src.bot.core.enums import HabitAction, ProfileAction


class ProfileActionCallback(CallbackData, prefix="profile"):
    """
    Данные, связанные с действиями в профиле.

    Attributes:
        action (ProfileAction): Тип действия.
            Возможные значения:
            - "change_tz": Изменить часовой пояс.
    """

    action: ProfileAction


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
        habit_id (int): ID привычки.
        page (int): Номер страницы списка, с которой перешли (для кнопки "Назад").
    """

    habit_id: int
    page: int


class HabitActionCallback(CallbackData, prefix="habit_action"):
    """
    Данные, связанные с действиями над конкретной привычкой.

    Attributes:
        habit_id (int): ID привычки.
        page (int): Номер страницы списка, с которой перешли (для кнопки "Назад").
        action (HabitAction): Тип действия.
            Возможные значения:
            - "view": Просмотр деталей привычки.
            - "done": Отметка 'Выполнить сегодня'.
            - "set_pending": Отмена выполнения.
            - "req_del": Запрос на удаление привычки.
            - "conf_del": Подтверждение удаления привычки.
    """

    habit_id: int
    page: int
    action: HabitAction
