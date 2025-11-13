import asyncio
from typing import AsyncGenerator, Generator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from pytest_docker import DockerCompose
from sqlalchemy import text
from alembic.config import Config
from alembic import command

# --- Настройки ---
# Путь к docker-compose файлу, который будет использоваться для тестов.
DOCKER_COMPOSE_FILE = "docker-compose.yml"
# Указываем, что нужно использовать только сервис test-db
TEST_DB_SERVICE_NAME = "test-db"
# URL для тестовой Базы данных
TEST_DATABASE_URL = "postgresql+psycopg://test_user:test_password@localhost:5433/test_db"


# --- Фикстуры ---

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Создает экземпляр event loop для всей тестовой сессии."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def postgres_service(docker_compose: DockerCompose) -> AsyncGenerator:
    """
    Фикстура для запуска и ожидания готовности сервиса test-db.
    `docker_compose` - фикстура из pytest-docker.
    """
    engine = create_async_engine(TEST_DATABASE_URL)
    # Ожидаем, пока БД станет доступна
    # `docker_compose.read_logs` используется для ожидания
    docker_compose.execute(f"up -d {TEST_DB_SERVICE_NAME}")

    for _ in range(30):  # Попытки подключения в течение 30 секунд
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            print("✅ База данных для тестов готова.")
            break
        except Exception:
            await asyncio.sleep(1)
    else:
        pytest.fail("❌ Не удалось подключиться к тестовой базе данных.")

    yield

    # Останавливаем контейнер после тестов
    docker_compose.execute(f"down")
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def apply_migrations(postgres_service: None):
    """
    Применяет и откатывает миграции Alembic для тестовой БД.
    Запускается один раз за сессию.
    """
    alembic_cfg = Config("alembic.ini")

    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)

    print("\n⬆️ Применение миграций Alembic...")
    command.upgrade(alembic_cfg, "head")
    yield
    print("\n⬇️ Откат миграций Alembic...")
    command.downgrade(alembic_cfg, "base")


@pytest.fixture(scope="session")
async def test_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Создает асинхронную сессию для тестов.
    """
    engine = create_async_engine(TEST_DATABASE_URL)
    TestSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSessionLocal() as session:
        yield session

    await engine.dispose()


@pytest.fixture(scope="function")
async def test_client(test_db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Создает тестовый клиент FastAPI, который использует тестовую БД.
    """
    from src.api.main import app
    from src.api.core.database import get_db_session

    # Переопределяем зависимость get_db_session, чтобы она возвращала нашу тестовую сессию
    def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield test_db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client