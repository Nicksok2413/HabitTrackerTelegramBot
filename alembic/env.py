import logging
import os

from alembic import context

# Импортируем Loguru
from loguru import logger

from sqlalchemy import engine_from_config, pool

# Импортируем базовую модель SQLAlchemy
from src.api.models import Base  # Это подтянет все модели через __init__

# Импортируем кастомный настройщик логирования
from src.core_shared.logging_setup import setup_logger


# --- Настройка логирования ---

class InterceptHandler(logging.Handler):
    """Перехватывает логи стандартного модуля logging и перенаправляет их в Loguru."""
    def emit(self, record):
        # Получаем соответствующий уровень логгера Loguru
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Ищем, откуда был вызван лог, чтобы правильно отобразить stack trace
        frame, depth = logging.currentframe(), 2

        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

# Настраиваем Loguru (создаем файлы логов в /logs/alembic_...)
# Используем функцию из core_shared, которая настроит ротацию, форматирование и файлы
setup_logger(service_name="Alembic")

# Подменяем стандартный logging на перехватчик
logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO)
# Можно отключить лишний шум от некоторых библиотек, если нужно
# logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


# --- Конфигурируем Alembic ---

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Указываем Alembic на метаданные базовой модели
target_metadata = Base.metadata

# Функция для формирования URL базы данных
def get_database_url() -> str:
    """
    Читает переменные окружения и формирует URL для базы данных.

    Raises:
        ValueError, если одна или несколько переменных окружения отсутствуют.
    """
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")

    # Проверка, что все переменные установлены
    if not all([db_user, db_password, db_host, db_port, db_name]):
        raise ValueError("Одна или несколько переменных для подключения к БД отсутствуют.")

    return f"postgresql+psycopg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

# Сначала пытаемся получить URL из существующей конфигурации (это позволяет тестам в conftest.py переопределять его)
# Используем метод get_alembic_option вместо get_main_option (метод умеет читать и INI, и TOML)
db_url = config.get_alembic_option("sqlalchemy.url")

# Если URL не был установлен извне, формируем его из переменных окружения
if db_url is None:
    # Формируем URL базы данных
    db_url = get_database_url()
    # Устанавливаем значение URL базы данных
    config.set_main_option("sqlalchemy.url", db_url)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # Гарантированно добавляем URL, который вычислили выше
    # Берем его снова через get_alembic_option для единообразия
    url = config.get_alembic_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Собираем конфигурацию вручную для надежности
    # Получаем секцию как словарь (может быть пустым или неполным при использовании TOML)
    configuration = config.get_section(config.config_ini_section, {})

    # Гарантированно добавляем URL, который вычислили выше
    # Берем его снова через get_alembic_option для единообразия
    url = config.get_alembic_option("sqlalchemy.url")

    if url:
        configuration["sqlalchemy.url"] = url

    # Создаем движок
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
