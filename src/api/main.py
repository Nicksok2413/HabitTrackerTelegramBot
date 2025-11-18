"""Основной файл приложения FastAPI для сервиса трекинга привычек.

Отвечает за:
- Создание и конфигурацию экземпляра FastAPI.
- Управление жизненным циклом приложения (подключение к БД).
- Регистрацию роутеров и обработчиков исключений.
- Предоставление эндпоинта для проверки работоспособности (health check).
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Response, status
from sqlalchemy import text

from src.api.core.config import settings
from src.api.core.database import db
from src.api.core.dependencies import DBSession
from src.api.core.exceptions import setup_exception_handlers
from src.api.core.logging import api_log as log
from src.api.routes import api_router
from src.core_shared.sentry_sdk_setup import setup_sentry

# Вызываем инициализацию Sentry, передавая настройки и уровень логирования
if settings.SENTRY_DSN:
    setup_sentry(settings, log_level=settings.LOG_LEVEL)


# Определяем lifespan для управления подключением к БД
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # pragma: no cover
    """
    Контекстный менеджер для управления жизненным циклом приложения.

    Выполняет подключение к базе данных при старте приложения
    и корректное отключение при его остановке.

    Args:
        app (FastAPI): Экземпляр приложения FastAPI.
    """
    log.info("Инициализация приложения...")
    try:
        await db.connect()
        yield
    except Exception as exc:
        # Логируем критическую ошибку, если подключение к БД не удалось при старте
        log.critical(f"Критическая ошибка при старте приложения: {exc}", exc_info=True)
        # Повторно вызываем исключение, чтобы приложение не запустилось в нерабочем состоянии
        raise exc
    finally:
        log.info("Остановка приложения...")
        await db.disconnect()
        log.info("Приложение остановлено.")


# Создаем экземпляр FastAPI
def create_app() -> FastAPI:
    """
    Создает и конфигурирует экземпляр приложения FastAPI.

    Returns:
        FastAPI: Сконфигурированный экземпляр приложения.
    """
    log.info(f"Создание экземпляра FastAPI для '{settings.PROJECT_NAME}@{settings.API_VERSION}'")
    log.info(f"Режим разработки: {settings.DEVELOPMENT}, Режим продакшена: {settings.PRODUCTION}")

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.API_VERSION,
        debug=settings.DEVELOPMENT,
        lifespan=lifespan,
        description="API для телеграм-бота по трекингу привычек",
    )

    # Настраиваем кастомные обработчики исключений
    setup_exception_handlers(app)
    log.info("Обработчики исключений настроены.")

    # Подключаем API роутер с префиксом /api
    log.info("Подключение API роутера...")
    app.include_router(api_router, prefix="/api")

    log.info(f"Приложение '{settings.PROJECT_NAME} {settings.API_VERSION}' сконфигурировано и готово к запуску.")
    return app


# Создаем основной экземпляр приложения
app = create_app()


@app.get(
    "/healthcheck",
    tags=["Health Check"],
    summary="Проверка работоспособности сервиса и его зависимостей",
    description=(
        "Проверяет, что API запущен и имеет доступ к базе данных. "
        "В случае недоступности базы данных возвращает HTTP статус 503."
    ),
)
async def health_check(
    response: Response,
    db_session: DBSession,
) -> dict[str, Any]:
    """
    Эндпоинт для проверки работоспособности сервиса.

    Args:
        response (Response): Объект ответа FastAPI для управления статус-кодом.
        db_session (DBSession): Зависимость, предоставляющая сессию БД.

    Returns:
        dict: Словарь со статусом API и его зависимостей.
    """
    is_db_ok = False

    try:
        # Выполняем простой и быстрый запрос к БД для проверки соединения
        await db_session.execute(text("SELECT 1"))
        is_db_ok = True
    except Exception:
        # Ошибка означает, что подключение к БД потеряно или неисправно
        is_db_ok = False

    # Формируем тело ответа
    response_body = {
        "api_status": "ok",
        "dependencies": {"database": "ok" if is_db_ok else "error"},
    }

    # Если база данных недоступна, меняем HTTP статус ответа на 503 Service Unavailable.
    # Это стандартная практика, которую понимают системы мониторинга и оркестрации (Docker, k8s).
    if not is_db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        log.warning("Health check провален: нет подключения к базе данных.")

    return response_body
