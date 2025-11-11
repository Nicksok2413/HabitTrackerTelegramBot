"""Основной файл приложения FastAPI для сервиса микроблогов."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.api.core.config import settings
from src.api.core.database import db
from src.api.core.dependencies import DBSession
from src.api.core.exceptions import setup_exception_handlers
from src.api.core.logging import api_log as log
from src.api.routes import api_router
from src.core_shared.sentry_sdk_setup import setup_sentry

# Вызываем инициализацию Sentry
if settings.SENTRY_DSN:
    setup_sentry()


# Определяем lifespan для управления подключением к БД
@asynccontextmanager
async def lifespan(app: FastAPI):  # pragma: no cover
    """
    Контекстный менеджер для управления жизненным циклом приложения.
    Выполняет подключение к БД при старте и отключение при завершении.
    """
    log.info("Инициализация приложения...")
    try:
        await db.connect()
        yield
    except Exception as exc:
        log.critical(f"Критическая ошибка при старте приложения: {exc}", exc_info=True)
        raise exc
    finally:
        log.info("Остановка приложения...")
        await db.disconnect()
        log.info("Приложение остановлено.")


# Создаем экземпляр FastAPI
def create_app() -> FastAPI:
    """Создает и конфигурирует экземпляр приложения FastAPI."""
    log.info(f"Создание экземпляра FastAPI для '{settings.PROJECT_NAME}@{settings.API_VERSION}'")
    log.info(f"Development={settings.DEVELOPMENT}, Production={settings.PRODUCTION}")

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.API_VERSION,
        debug=settings.DEVELOPMENT,
        lifespan=lifespan,
        description="Телеграм-бот для трекинга привычек",
    )

    # Настраиваем CORS (Cross-Origin Resource Sharing)
    # Позволяет фронтенду с другого домена обращаться к API
    if settings.DEVELOPMENT:  # type: ignore[truthy-function]
        allow_origins: list[str] = ["*"]  # Разрешаем все для разработки/тестирования
        log.warning("CORS настроен разрешать все источники (*). Не использовать в PRODUCTION!")
    else:  # pragma: no cover
        allow_origins = []  # По умолчанию запретить все, если не задано
        log.info(f"CORS настроен для PRODUCTION. Разрешенные источники: {allow_origins}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],  # Разрешить все стандартные методы (GET, POST, etc.)
        allow_headers=["*"],  # Разрешить все заголовки
    )

    # Настраиваем обработчики исключений
    setup_exception_handlers(app)
    log.info("Обработчики исключений настроены.")

    # Подключаем API роутер
    log.info("Подключение API роутера...")
    app.include_router(api_router, prefix="/api")

    log.info(f"Приложение '{settings.PROJECT_NAME} {settings.API_VERSION}' сконфигурировано и готово к запуску.")
    return app


# Создаем приложение
app = create_app()


@app.get("/healthcheck", tags=["Health Check"])
async def health_check(db_session: DBSession):
    """Проверяет работоспособность сервиса и его зависимостей."""
    try:
        # Проверяем доступность БД, выполняя простой и быстрый запрос
        await db_session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    return {"status": "ok", "dependencies": {"database": db_status}}
