from typing import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.database import get_db_session
from src.api.main import app

# --- ФИКСТУРЫ, СПЕЦИФИЧНЫЕ ДЛЯ ТЕСТИРОВАНИЯ API ---


@pytest_asyncio.fixture(scope="function")
async def test_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Создает и предоставляет тестовый клиент FastAPI для каждого API-теста.

    Зависит от фикстуры `db_session` (в корневом conftest.py)
    для переопределения зависимости get_db_session и обеспечения изоляции транзакций.
    """

    # Функция для переопределения зависимости `get_db_session` в приложении
    def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:  # type: ignore
        yield db_session

    # Применяем переопределение
    app.dependency_overrides[get_db_session] = override_get_db_session

    # Создаем транспорт для ASGI приложения
    transport = ASGITransport(app=app)

    # Создаем асинхронный HTTP-клиент с транспортом для взаимодействия с приложением
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    # Очищаем переопределение после теста
    del app.dependency_overrides[get_db_session]
