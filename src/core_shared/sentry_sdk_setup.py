"""Централизованная настройка Sentry SDK."""

from logging import ERROR, INFO  # Стандартные уровни логирования для Sentry
from typing import Protocol  # Используем Protocol для определения "контракта" настроек

from sentry_sdk import init as sentry_init, set_tag
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.loguru import LoguruIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from sentry_sdk.integrations.threading import ThreadingIntegration

from src.core_shared.logging_setup import setup_logger

# Создаем экземпляр логгера для процесса настройки Sentry
sentry_log = setup_logger(service_name="SentrySetup")


# Определяем протокол, описывающий, какие атрибуты мы ожидаем от объекта настроек
class SentrySettingsProtocol(Protocol):
    """Протокол для объекта настроек, используемых Sentry."""

    SENTRY_DSN: str | None
    PROJECT_NAME: str
    API_VERSION: str

    @property
    def PRODUCTION(self) -> bool: ...


# Используем этот протокол в сигнатуре функции инициализации Sentry SDK
def setup_sentry(settings: SentrySettingsProtocol, service_name: str) -> None:
    """
    Инициализирует Sentry SDK, если задан DSN.

    Определяет environment, sample rates и другие параметры на основе settings.

    Args:
        settings (SentrySettingsProtocol): Объект настроек.
        service_name (str): Имя сервиса (API, Bot, Worker, Scheduler) для тегов.
    """

    sentry_dsn = settings.SENTRY_DSN

    if not sentry_dsn:
        sentry_log.warning(f"SENTRY_DSN не установлен. Мониторинг ошибок для {service_name} отключен.")
        return

    # --- Определяем параметры Sentry ---

    # Окружение (Environment)
    environment = "production" if settings.PRODUCTION else "development"

    # Частота семплирования для Performance Monitoring (Traces)
    # Установим 10% для production, 100% для development
    traces_sample_rate = 0.1 if settings.PRODUCTION else 1.0

    # Частота семплирования для Profiling аналогично трейсам
    profiles_sample_rate = 0.1 if settings.PRODUCTION else 1.0

    # Уровни логирования для интеграции
    log_level_breadcrumbs = INFO  # Уровень для breadcrumbs
    log_level_events = ERROR  # Уровень для событий/ошибок

    sentry_log.info(f"Инициализация Sentry для {service_name} (Env: {environment})...")

    try:
        sentry_init(
            dsn=sentry_dsn,
            environment=environment,
            release=f"{settings.PROJECT_NAME}@{settings.API_VERSION}",

            # Настройка производительности
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,

            # Интеграции
            integrations=[
                # HTTP клиент (используется в боте и клиентах)
                AioHttpIntegration(),
                # Асинхронность
                AsyncioIntegration(),
                # Работа с БД
                SqlalchemyIntegration(),
                # Starlette (База для FastAPI)
                StarletteIntegration(transaction_style="endpoint"),
                # FastAPI
                FastApiIntegration(transaction_style="endpoint"),
                # Loguru (перехват логов и отправка их как breadcrumbs/events)
                LoguruIntegration(level=log_level_breadcrumbs, event_level=log_level_events),
                # Celery
                CeleryIntegration(),
                # Логирование потоков (важно для Celery)
                ThreadingIntegration(propagate_hub=True),
            ],
        )

        # Устанавливаем тег сервиса после инициализации
        set_tag("service", service_name)

        sentry_log.success("Sentry SDK успешно инициализирован.")

    except Exception as exc:
        sentry_log.exception(f"Ошибка инициализации Sentry: {exc}")
