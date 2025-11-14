import asyncio
from typing import AsyncGenerator, Generator

import psycopg
import pytest
import pytest_asyncio
from alembic.config import Config
from pytest_docker.plugin import Services as DockerServices
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from alembic import command
from src.api.core.config import settings

# --- ГЛОБАЛЬНЫЕ ФИКСТУРЫ ДЛЯ ВСЕГО ПРОЕКТА ---


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Создает и предоставляет asyncio event loop для всей тестовой сессии."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig) -> str:
    """Указывает pytest-docker путь к docker-compose.yml файлу."""
    return "docker-compose.yml"


def is_postgres_responsive(db_url: str) -> bool:
    """Вспомогательная функция для проверки доступности PostgreSQL."""
    try:
        conn = psycopg.connect(db_url.replace("+psycopg", ""), timeout=2)
        conn.close()
        return True
    except psycopg.OperationalError:
        return False


@pytest.fixture(scope="session")
def postgres_service(docker_compose_file: str, docker_services: DockerServices) -> None:
    """Запускает Docker-сервис 'test-db' и ожидает его полной готовности."""
    print("⏳ Ожидание запуска тестовой базы данных PostgreSQL...")
    docker_services.wait_until_responsive(
        timeout=30.0,
        pause=1.0,
        check=lambda: is_postgres_responsive(settings.TEST_DATABASE_URL),
    )
    print("✅ База данных для тестов готова.")


@pytest.fixture(scope="session", autouse=True)
def apply_migrations(postgres_service: None) -> Generator[None, None, None]:
    """
    Применяет и откатывает Alembic миграции для всей тестовой сессии.
    """
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.TEST_DATABASE_URL)

    print("\n⬆️  Применение миграций Alembic...")
    command.upgrade(alembic_cfg, "head")
    yield
    print("\n⬇️  Откат миграций Alembic...")
    command.downgrade(alembic_cfg, "base")


@pytest_asyncio.fixture(scope="session")
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Создает один асинхронный движок SQLAlchemy для всей сессии."""
    engine = create_async_engine(settings.TEST_DATABASE_URL)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def db_session_factory(async_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Создает фабрику асинхронных сессий для всей тестовой сессии."""
    return async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="function")
async def db_session(db_session_factory: async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncSession, None]:
    """
    Предоставляет изолированную транзакцию в БД для каждого теста.
    Эта фикстура может быть использована тестами API, планировщика и т.д.
    """
    # Создаем сессию из фабрики
    async with db_session_factory() as session:
        # Начинаем транзакцию
        await session.begin()
        try:
            # Передаем управление в тестовую функцию
            yield session
        finally:
            # Гарантированно откатываем транзакцию после завершения теста, даже если в нем произошла ошибка
            await session.rollback()
