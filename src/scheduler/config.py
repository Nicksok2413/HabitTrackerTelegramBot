"""Конфигурация планировщика."""

from urllib.parse import quote_plus

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

class SchedulerSettings(BaseSettings):
    """
    Основные настройки планировщика.

    Наследуется от Pydantic BaseSettings для автоматической валидации и загрузки переменных окружения.
    """

    # --- Настройки, читаемые из .env ---

    # Настройки БД
    DB_NAME: str = Field(default="habit_tracker_db", description="Название базы данных")
    DB_USER: str = Field(default="habit_tracker_user", description="Имя пользователя базы данных")
    DB_PASSWORD: str = Field(..., description="Пароль пользователя базы данных")
    DB_HOST: str = Field(
        default="db",
        description="Имя хоста базы данных (название сервиса в Docker)",
    )
    DB_PORT: int = Field(default=5432, description="Порт хоста базы данных")

    # Настройки Telegram (для отправки уведомлений)
    BOT_TOKEN: str = Field(..., description="Токен бота")

    # Настройки логирования
    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования")

    # Формируем URL основной базы данных
    @computed_field(repr=False)
    def DATABASE_URL(self) -> str:
        """Собирает URL для SQLAlchemy."""

        # Экранируем пользователя и пароль, чтобы спецсимволы не ломали URL
        encoded_user = quote_plus(self.DB_USER)
        encoded_password = quote_plus(self.DB_PASSWORD)

        return f"postgresql+psycopg://{encoded_user}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # Имена переменных окружения не чувствительны к регистру
        extra="ignore",  # Игнорировать лишние переменные .env
    )


# Создаем глобальный экземпляр настроек
settings = SchedulerSettings() # type: ignore[call-arg]