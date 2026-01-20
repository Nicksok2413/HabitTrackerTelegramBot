import pytest
from httpx import AsyncClient
from starlette import status

# Помечаем все тесты в модуле как асинхронные
pytestmark = pytest.mark.asyncio


async def test_mark_habit_done_and_check_streak(test_client: AsyncClient, user_auth_headers: dict[str, str]):
    """
    Сценарий:
    1. Создать привычку.
    2. Выполнить сегодня -> Стрик 1.
    3. Отменить выполнение -> Стрик 0.
    """
    # Создаем привычку
    payload = {
        "name": "Streak Test",
        "time_to_remind": "10:00",
        "target_days": 5,
    }

    response = await test_client.post("/api/v1/habits/", json=payload, headers=user_auth_headers)
    habit_id = response.json()["id"]

    # Выполняем (DONE)
    execution_response = await test_client.post(
        f"/api/v1/habits/{habit_id}/executions/",
        json={"status": "done"},
        headers=user_auth_headers
    )

    assert execution_response.status_code == status.HTTP_201_CREATED

    # Проверяем привычку (стрик должен стать 1)
    habit_response = await test_client.get(f"/api/v1/habits/{habit_id}", headers=user_auth_headers)

    assert habit_response.json()["current_streak"] == 1
    assert habit_response.json()["is_done_today"] is True

    # Отменяем (PENDING) - в API мы шлем статус pending для отмены
    await test_client.post(
        f"/api/v1/habits/{habit_id}/executions/",
        json={"status": "pending"},
        headers=user_auth_headers
    )

    # Проверяем привычку (стрик должен стать 0)
    habit_response = await test_client.get(f"/api/v1/habits/{habit_id}", headers=user_auth_headers)

    assert habit_response.json()["current_streak"] == 0
    assert habit_response.json()["is_done_today"] is False


async def test_streak_calculation_idempotency(test_client: AsyncClient, user_auth_headers: dict[str, str]):
    """Проверка идемпотентности: повторная отправка DONE не должна увеличивать стрик дважды."""
    # Создаем привычку
    payload = {
        "name": "Idempotency",
        "time_to_remind": "10:00",
    }

    response = await test_client.post("/api/v1/habits/", json=payload, headers=user_auth_headers)
    habit_id = response.json()["id"]

    # Выполняем 1 раз
    await test_client.post(
        f"/api/v1/habits/{habit_id}/executions/",
        json={"status": "done"},
        headers=user_auth_headers
    )

    # Выполняем 2 раз (тот же статус)
    await test_client.post(
        f"/api/v1/habits/{habit_id}/executions/",
        json={"status": "done"},
        headers=user_auth_headers
    )

    # Стрик всё равно должен быть 1
    habit_response = await test_client.get(f"/api/v1/habits/{habit_id}", headers=user_auth_headers)
    assert habit_response.json()["current_streak"] == 1
