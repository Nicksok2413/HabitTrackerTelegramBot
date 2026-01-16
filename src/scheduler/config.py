"""Конфигурация планировщика."""

from pydantic import Field

from src.core_shared.config import AppSettings


class Settings(AppSettings):
    """
    Основные настройки планировщика.

    Наследуется от AppSettings.
    """

    # --- Настройки, читаемые из .env ---

    # Настройки Telegram (для отправки уведомлений)
    BOT_TOKEN: str = Field(..., description="Токен бота")

    # Настройки логирования
    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования")


# Создаем глобальный экземпляр настроек
settings = Settings()  # type: ignore[call-arg]
