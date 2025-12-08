"""
Определение состояний FSM (Finite State Machine) для сценариев работы с профилем.
"""

from aiogram.fsm.state import State, StatesGroup


class ProfileEdit(StatesGroup):
    """
    Группа состояний для редактирования профиля.

    waiting_for_timezone: Ожидание ввода данных часового пояса.
    """

    waiting_for_timezone = State()
