"""Конфигурация планировщика."""

from urllib.parse import quote_plus

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Основные настройки планировщика.

    Наследуется от Pydantic BaseSettings для автоматической валидации и загрузки переменных окружения.
    """

    # --- Настройки, читаемые из .env ---

    # Настройки Telegram (для отправки уведомлений)
    BOT_TOKEN: str = Field(..., description="Токен бота")

    # Настройки логирования
    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # Имена переменных окружения не чувствительны к регистру
        extra="ignore",  # Игнорировать лишние переменные .env
    )


# Создаем глобальный экземпляр настроек
settings = Settings() # type: ignore[call-arg]