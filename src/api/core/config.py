"""Конфигурация приложения."""

from urllib.parse import quote_plus

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Основные настройки приложения."""

    # --- Статические настройки ---

    # Название приложения
    PROJECT_NAME: str = "Habit Tracker Telegram Bot"
    # Версия API
    API_VERSION: str = "0.1.0"
    # Хост API
    API_HOST: str = "0.0.0.0"  # noqa: S104 - 0.0.0.0 необходимо для Docker контейнера
    # Порт API
    API_PORT: int = 8000
    # URL для внутреннего взаимодействия бот -> API
    API_BASE_URL: str = "http://api:8000"
    # Алгоритм подписи JWT
    JWT_ALGORITHM: str = "HS256"
    # Срок годности JWT токена в минутах
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

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

    # Настройки режима разработки/тестирования (для продакшен - False)
    DEVELOPMENT: bool = Field(default=False, description="Режим разработки/тестирования")

    # Настройки безопасности
    API_BOT_SHARED_KEY: str = Field(..., description="Ключ для аутентификации бота на стороне API")
    BOT_TOKEN: str = Field(..., description="Токен бота")
    JWT_SECRET_KEY: str = Field(..., description="JWT")

    # Бизнес-константы проекта
    DAYS_TO_FORM_HABIT: int = Field(
        default=21,
        description="Количество дней, необходимое для формирования привычки",
    )

    # Настройки логирования
    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования")

    # Настройки Sentry
    SENTRY_DSN: str | None = Field(
        default=None,
        description="Sentry DSN для включения интеграции. Если None, Sentry отключен.",
    )

    # --- Вычисляемые поля ---

    # Продакшен режим
    @property
    def PRODUCTION(self) -> bool:
        # Считаем режим продакшеном, если не DEVELOPMENT (разработка/тестирование)
        return not self.DEVELOPMENT

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
        extra="ignore",  # Игнорировать лишние переменные  .env
    )


# Создаем глобальный экземпляр настроек
settings = Settings()  # type: ignore[call-arg]
