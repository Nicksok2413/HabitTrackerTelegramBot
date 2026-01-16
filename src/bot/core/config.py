"""Конфигурация Телеграм-бота."""

from pydantic import Field

from src.core_shared.config import AppSettings


class Settings(AppSettings):
    """
    Основные настройки бота.

    Наследуется от AppSettings.
    """

    # --- Настройки Telegram ---
    BOT_TOKEN: str = Field(..., description="Токен телеграм бота, полученный от BotFather")

    # --- Настройки подключения к Backend API ---
    # В Docker-сети hostname сервиса API - "api"
    # При локальном запуске вне докера может потребоваться http://localhost:8000
    API_BASE_URL: str = Field(default="http://api:8000", description="Базовый URL для подключения к Backend API")

    # Секретный ключ для межсервисной аутентификации (Бот -> API)
    # Используется для аутентификации бота на стороне API и чтобы бот мог запрашивать JWT токены от имени пользователей
    API_BOT_SHARED_KEY: str = Field(..., description="Ключ для аутентификации бота на стороне API")

    # Настройки логирования
    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования")

    # Формируем URL к API
    @property
    def API_V1_URL(self) -> str:
        """
        Возвращает полный URL к API v1.

        Пример: http://api:8000/api/v1
        """
        return f"{self.API_BASE_URL}/api/v1"


# Создаем глобальный экземпляр настроек
settings = Settings()  # type: ignore[call-arg]
