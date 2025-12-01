"""
Конфигурация Телеграм-бота.

Определяет настройки, загружаемые из переменных окружения (.env),
и вычисляемые свойства, необходимые для работы приложения.
"""

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Основные настройки бота.

    Наследуется от Pydantic BaseSettings для автоматической валидации и загрузки переменных окружения.
    """

    # --- Настройки Telegram ---
    BOT_TOKEN: str = Field(..., description="Токен телеграм бота, полученный от BotFather")

    # --- Настройки подключения к Backend API ---
    # В Docker-сети hostname сервиса API - "api"
    # При локальном запуске вне докера может потребоваться http://localhost:8000
    API_BASE_URL: str = Field(
        default="http://api:8000",
        description="Базовый URL для подключения к Backend API"
    )

    # Секретный ключ для межсервисной аутентификации (Бот -> API)
    # Используется для аутентификации бота на стороне API и чтобы бот мог запрашивать JWT токены от имени пользователей
    API_BOT_SHARED_KEY: str = Field(..., description="Ключ для аутентификации бота на стороне API")

    # Настройки логирования
    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования")

    # Формируем URL к API
    @computed_field
    def API_V1_URL(self) -> str:
        """
        Возвращает полный URL к API v1.

        Пример: http://api:8000/api/v1
        """
        return f"{self.API_BASE_URL}/api/v1"

    # Конфигурация Pydantic
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # Имена переменных окружения не чувствительны к регистру
        extra="ignore",  # Игнорировать лишние переменные в .env
    )


# Создаем глобальный экземпляр настроек
settings = Settings()  # type: ignore