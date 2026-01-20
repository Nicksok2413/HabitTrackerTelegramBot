from datetime import datetime, time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.models import Habit, User
from src.api.repositories import HabitRepository

# Помечаем все тесты в модуле как асинхронные
pytestmark = pytest.mark.asyncio


async def test_get_habits_for_notification(db_session: AsyncSession):
    """Проверяет, что репозиторий корректно находит привычки по времени и таймзоне."""
    repo = HabitRepository(Habit)

    # Создаем пользователя с таймзоной Asia/Yekaterinburg
    user = User(
        telegram_id=555,
        username="timezone_test_user",
        first_name="Test",
        last_name="User",
        timezone="Asia/Yekaterinburg",
    )

    db_session.add(user)
    await db_session.flush()

    # Создаем привычку на 09:00
    target_time = time(9, 0)

    habit = Habit(
        user_id=user.id,
        name="Morning Routine",
        time_to_remind=target_time,
        is_active=True,
        target_days=21,
    )

    db_session.add(habit)
    await db_session.commit()

    # Тест 1: Ищем по правильной таймзоне и времени -> должны найти
    # Важно: target_date нужна для проверки "не выполнено ли уже", но пока выполнений нет
    dummy_date = datetime.now().date()

    habits = await repo.get_habits_for_notification(
        db_session,
        timezone="Asia/Yekaterinburg",
        target_time=target_time,
        target_date=dummy_date
    )

    assert len(habits) == 1
    assert habits[0].id == habit.id

    # Тест 2: Ищем по неправильному времени -> пусто
    habits_wrong_time = await repo.get_habits_for_notification(
        db_session,
        timezone="Asia/Yekaterinburg",
        target_time=time(10, 0),  # Другое время
        target_date=dummy_date
    )

    assert len(habits_wrong_time) == 0

    # Тест 3: Ищем по неправильной таймзоне -> пусто
    habits_wrong_tz = await repo.get_habits_for_notification(
        db_session,
        timezone="Europe/Moscow",  # Другая зона
        target_time=target_time,
        target_date=dummy_date
    )

    assert len(habits_wrong_tz) == 0
