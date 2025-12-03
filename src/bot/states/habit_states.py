"""
Определение состояний FSM (Finite State Machine) для сценариев работы с привычками.
"""

from aiogram.fsm.state import State, StatesGroup


class HabitCreation(StatesGroup):
    """
    Группа состояний для сценария создания новой привычки.

    Последовательность шагов:
    1. waiting_for_name: Ожидание ввода названия привычки.
    2. waiting_for_description: Ожидание ввода описания (или команды пропуска - /skip).
    3. waiting_for_time: Ожидание ввода времени напоминания (ЧЧ:ММ).
    """

    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_time = State()