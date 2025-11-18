"""Настройка подключения к базе данных с использованием SQLAlchemy."""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import settings
from .logging import api_log as log


class Database:
    """
    Менеджер подключений к базе данных.

    Отвечает за:
    - Инициализацию подключения
    - Управление пулом соединений
    - Создание сессий
    """

    def __init__(self) -> None:
        """Инициализирует менеджер с пустыми подключениями."""
        self.engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker[AsyncSession] | None = None

    async def connect(self, **kwargs: Any) -> None:
        """
        Устанавливает подключение к базе данных.

        Использует `DATABASE_URL` из настроек.

        Args:
            **kwargs: Дополнительные параметры для create_async_engine.

        Raises:
            RuntimeError: При неудачной проверке подключения.
        """
        self.engine = create_async_engine(
            str(settings.DATABASE_URL),
            echo=settings.DEVELOPMENT,  # Включаем логирование SQL запросов в режиме DEVELOPMENT
            pool_pre_ping=True,  # Проверять соединение перед использованием
            pool_recycle=3600,  # Переподключение каждый час
            **kwargs,
        )

        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,  # Управляем транзакциями явно
            autoflush=False,  # Управляем flush явно
        )

        await self._verify_connection()
        log.success("Подключение к базе данных установлено.")

    async def disconnect(self) -> None:
        """Корректное закрытие подключения к базе данных."""
        if self.engine:
            log.info("Закрытие подключения к базе данных...")
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None
            log.info("Подключение к базе данных успешно закрыто.")

    async def _verify_connection(self) -> None:
        """
        Проверяет работоспособность подключения к базе данных.

        Raises:
            RuntimeError: Если проверка подключения не удалась.
        """
        if not self.session_factory:
            raise RuntimeError("Фабрика сессий не инициализирована.")
        try:
            async with self.session_factory() as session:
                await session.execute(text("SELECT 1"))
            log.debug("Проверка подключения к БД прошла успешно.")
        except Exception as exc:
            log.critical(f"Ошибка подключения к базе данных: {exc}", exc_info=True)
            raise RuntimeError("Не удалось проверить подключение к БД.") from exc

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Асинхронный контекстный менеджер для работы с сессиями БД.

        Yields:
            AsyncSession: Экземпляр сессии БД.

        Raises:
            RuntimeError: При вызове до инициализации подключения (`db.connect`).
        """
        if not self.session_factory:
            raise RuntimeError(
                "База данных не инициализирована. Вызовите `await db.connect()` перед использованием сессий."
            )

        session: AsyncSession = self.session_factory()

        try:
            yield session
        except Exception as exc:
            log.error(
                f"Ошибка во время сессии БД, выполняется откат: {exc}",
                exc_info=settings.DEVELOPMENT,
            )  # Трейсбек только в DEVELOPMENT
            await session.rollback()
            raise
        finally:
            await session.close()


# Глобальный экземпляр менеджера БД
db = Database()


# Dependency для FastAPI
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Зависимость FastAPI для получения асинхронной сессии базы данных.

    Yields:
        AsyncSession: Сессия базы данных, управляемая через `db.session()`.
    """
    async with db.session() as session:
        yield session
