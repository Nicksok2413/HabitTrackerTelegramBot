"""
Определение состояний FSM (Finite State Machine) для сценариев работы с привычками.
"""

from aiogram.fsm.state import State, StatesGroup


class HabitCreation(StatesGroup):
    """
    Группа состояний для сценария создания новой привычки.

    Последовательность шагов (Wizard pattern):
    1. waiting_for_name: Ожидание ввода названия привычки.
    2. waiting_for_description: Ожидание ввода описания или команды пропуска - /skip.
    3. waiting_for_target_days: Ожидание ввода цели - количества дней или команды пропуска - /skip.
    4. waiting_for_time: Ожидание ввода времени напоминания (ЧЧ:ММ).
    """

    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_target_days = State()
    waiting_for_time = State()


class HabitEditing(StatesGroup):
    """
    Группа состояний для редактирования привычки.

    Состояния при нажатии определенных кнопок (Menu-based editing):
    - waiting_for_name: Ожидание ввода нового названия привычки или команды пропуска - /skip.
    - waiting_for_description: Ожидание ввода нового описания или команды пропуска - /skip.
    - waiting_for_target_days: Ожидание ввода новой цели - количества дней или команды пропуска - /skip.
    - waiting_for_time: Ожидание ввода нового времени напоминания (ЧЧ:ММ) или команды пропуска - /skip.
    """
    waiting_for_new_name = State()
    waiting_for_new_description = State()
    waiting_for_new_target_days = State()
    waiting_for_new_time = State()