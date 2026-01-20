import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.api.models import Habit, User

# Помечаем все тесты в модуле как асинхронные
pytestmark = pytest.mark.asyncio


async def test_create_habit(
        test_client: AsyncClient,
        user_auth_headers: dict[str, str],
        db_session: AsyncSession
):
    """Тест создания новой привычки."""
    payload = {
        "name": "Drink Water",
        "description": "2 liters per day",
        "time_to_remind": "09:00",
        "target_days": 30,
    }

    response = await test_client.post("/api/v1/habits/", json=payload, headers=user_auth_headers)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["current_streak"] == 0

    # Проверяем в БД
    statement = select(Habit).where(Habit.name == "Drink Water")
    result = await db_session.execute(statement)
    habit = result.scalar_one_or_none()
    assert habit is not None


async def test_get_habits_list(test_client: AsyncClient, user_auth_headers: dict[str, str]):
    """Тест получения списка привычек (должен быть пуст сначала, потом 1)."""
    # Сначала список пуст
    response = await test_client.get("/api/v1/habits/", headers=user_auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 0

    # Создаем привычку
    payload = {
        "name": "Test Habit",
        "time_to_remind": "10:00",
    }

    await test_client.post("/api/v1/habits/", json=payload, headers=user_auth_headers)

    # Теперь список содержит 1 элемент
    response = await test_client.get("/api/v1/habits/", headers=user_auth_headers)
    assert len(response.json()) == 1
    assert response.json()[0]["is_done_today"] is False  # Проверка вычисляемого поля


async def test_delete_habit(test_client: AsyncClient, user_auth_headers: dict[str, str]):
    """Тест удаления привычки."""
    # Создаем привычку
    payload = {
        "name": "To Delete",
        "time_to_remind": "10:00",
    }

    create_response = await test_client.post("/api/v1/habits/", json=payload, headers=user_auth_headers)
    habit_id = create_response.json()["id"]

    # Удаляем привычку
    delete_response = await test_client.delete(f"/api/v1/habits/{habit_id}", headers=user_auth_headers)
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    # Проверяем, что привычку получить нельзя (404)
    get_response = await test_client.get(f"/api/v1/habits/{habit_id}", headers=user_auth_headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND


async def test_security_cannot_delete_others_habit(
        test_client: AsyncClient,
        user_auth_headers: dict[str, str],
        another_user: User,  # фикстура другого юзера
        db_session: AsyncSession
):
    """
    Security Test: Пользователь А не может удалить привычку Пользователя Б.
    """
    # Создаем привычку для "другого юзера" напрямую через БД
    habit = Habit(
        user_id=another_user.id,
        name="Secret Habit",
        target_days=21,
        time_to_remind="10:00",
    )
    db_session.add(habit)
    await db_session.commit()
    await db_session.refresh(habit)

    # Пытаемся удалить её, используя токены "первого юзера"
    response = await test_client.delete(f"/api/v1/habits/{habit.id}", headers=user_auth_headers)

    # Ожидаем 403 Forbidden
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Убедимся, что привычка все еще в БД
    statement = select(Habit).where(Habit.id == habit.id)
    result = await db_session.execute(statement)
    assert result.scalar_one_or_none() is not None
