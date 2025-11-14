"""Конфигурация приложения."""

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
    API_HOST: str = "0.0.0.0"
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

    # URL основной БД
    DATABASE_URL: str = Field(..., description="Асинхронный URL для подключения к основной базе данных.")

    # URL тестовой БД (используется только в тестах)
    TEST_DATABASE_URL: str = Field(..., description="Асинхронный URL для подключения к тестовой базе данных.")

    # Настройки режима разработки/тестирования. Для продакшен должно быть False.
    DEVELOPMENT: bool = Field(default=False, description="Режим разработки/тестирования")

    # # Считаем режим продакшеном, если не DEVELOPMENT (разработка/тестирование)
    # PRODUCTION: bool = True if not DEVELOPMENT else False

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
    @computed_field
    def PRODUCTION(self) -> bool:
        # Считаем режим продакшеном, если не DEVELOPMENT (разработка/тестирование)
        return not self.DEVELOPMENT

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # Имена переменных окружения не чувствительны к регистру
        extra="ignore",  # Игнорировать лишние переменные окружения
    )


# Кэшированный экземпляр настроек
settings = Settings()  # type: ignore[call-arg]
