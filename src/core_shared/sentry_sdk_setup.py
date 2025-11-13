"""Настройка Sentry SDK."""

from logging import ERROR, INFO  # Стандартные уровни логирования для Sentry
from typing import Protocol  # Используем Protocol для определения "контракта" настроек

from sentry_sdk import init as sentry_init
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.loguru import LoguruIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from .logging_setup import setup_logger


# Определяем протокол, описывающий, какие атрибуты мы ожидаем от объекта настроек
class SentrySettingsProtocol(Protocol):
    """Протокол для объекта настроек, используемых Sentry."""

    SENTRY_DSN: str | None
    PRODUCTION: bool
    PROJECT_NAME: str
    API_VERSION: str


# Используем этот протокол в сигнатуре функции инициализации Sentry SDK
def setup_sentry(settings: SentrySettingsProtocol, log_level: str) -> None:
    """
    Инициализирует Sentry SDK, если задан DSN.

    Определяет environment, sample rates и другие параметры на основе settings.

    Args:
        settings (SentrySettingsProtocol): Объект настроек.
        log_level (str): Уровень логирования.
    """
    # Создаем экземпляр логгера для Sentry
    sentry_log = setup_logger(service_name="SentrySetup", log_level_override=log_level)

    sentry_dsn = settings.SENTRY_DSN

    if not sentry_dsn:
        sentry_log.info("SENTRY_DSN не установлен, Sentry SDK не будет инициализирован.")
        return

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
