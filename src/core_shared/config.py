"""Базовая конфигурация, общая для всех сервисов."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """
    Базовые настройки приложения.

    Наследуется от Pydantic BaseSettings для автоматической валидации и загрузки переменных окружения.
    Содержит общие поля для всех микросервисов и для Sentry.
    """

    # --- Общие метаданные ---
    PROJECT_NAME: str = "Habit Tracker Telegram Bot"
    API_VERSION: str = "0.1.0"

    # Настройки режима разработки/тестирования (для продакшен - False)
    DEVELOPMENT: bool = Field(default=False, description="Режим разработки/тестирования")

    # --- Sentry ---
    SENTRY_DSN: str | None = Field(
        default=None,
        description="Sentry DSN. Если не задан, мониторинг отключен.",
    )

    # Продакшен режим
    @property
    def PRODUCTION(self) -> bool:
        """Определяет, запущен ли сервис в продакшене."""
        # Считаем режим продакшеном, если не DEVELOPMENT (разработка/тестирование)
        return not self.DEVELOPMENT

    # Базовая конфигурация Pydantic
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # Имена переменных окружения не чувствительны к регистру
        extra="ignore",  # Игнорировать лишние переменные .env
    )
