"""Настройка Sentry SDK."""

from logging import ERROR, INFO  # Стандартные уровни логирования для Sentry

from sentry_sdk import init as sentry_init
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.loguru import LoguruIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from src.api.core.config import settings

from .logging_setup import setup_logger

# Получаем экземпляр логгера для этого модуля
sentry_log = setup_logger(service_name="SentrySetup", log_level_override=settings.LOG_LEVEL)


def setup_sentry():
    """
    Инициализирует Sentry SDK, если задан DSN.
    Определяет environment, sample rates и другие параметры на основе settings.
    """
    sentry_dsn = settings.SENTRY_DSN

    # --- Определяем параметры Sentry ---

    # Окружение (Environment)
    environment = "production" if settings.PRODUCTION else "development"

    # Частота семплирования для Performance Monitoring (Traces)
    # Установим 10% для production, 100% для development
    traces_sample_rate = 0.1 if environment == "production" else 1.0

    # Частота семплирования для Profiling аналогично трейсам
    profiles_sample_rate = 0.1 if environment == "production" else 1.0

    # Уровни логирования для интеграции
    log_level_breadcrumbs = INFO  # Уровень для breadcrumbs
    log_level_events = ERROR  # Уровень для событий/ошибок

    sentry_log.info(
        f"Инициализация Sentry SDK. DSN: {'***' + sentry_dsn[-6:]}, "
        f"Environment: {environment}, "
        f"Traces Rate: {traces_sample_rate}, "
        f"Profiles Rate: {profiles_sample_rate}"
    )

    try:
        sentry_init(
            dsn=sentry_dsn,
            integrations=[
                StarletteIntegration(transaction_style="endpoint"),
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                LoguruIntegration(level=log_level_breadcrumbs, event_level=log_level_events),
            ],
            environment=environment,
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,
            release=f"{settings.PROJECT_NAME}@{settings.API_VERSION}",
        )
        sentry_log.info("Sentry SDK успешно инициализирован.")
    except Exception as exc:
        sentry_log.exception(f"Ошибка инициализации Sentry SDK: {exc}")
