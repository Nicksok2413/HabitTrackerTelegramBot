from typing import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.database import get_db_session
from src.api.main import app

# --- ФИКСТУРЫ, СПЕЦИФИЧНЫЕ ДЛЯ ТЕСТИРОВАНИЯ API ---


@pytest.fixture(scope="function")
async def test_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Создает и предоставляет тестовый клиент FastAPI для каждого API-теста.

    Зависит от фикстуры `db_session` (которую pytest найдет в корневом conftest.py)
    для переопределения зависимости и обеспечения изоляции транзакций.
    """

    # Функция для переопределения зависимости `get_db_session` в приложении
    def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    # Применяем переопределение
    app.dependency_overrides[get_db_session] = override_get_db_session

    # Создаем асинхронный HTTP-клиент для взаимодействия с приложением
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    # Очищаем переопределение после теста
    del app.dependency_overrides[get_db_session]
