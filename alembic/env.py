import logging
import os
import socket
import sys

from urllib.parse import quote_plus

from alembic import context
from sqlalchemy import engine_from_config, pool

# Импортируем базовую модель SQLAlchemy
from src.api.models import Base  # Это подтянет все модели через __init__

from src.core_shared.logging_setup import setup_logger

# Настройка логирования

# Получаем базовый логгер Loguru
loguru_logger = setup_logger("Alembic")

class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger_opt = loguru_logger.bind(service_name="Alembic").opt(depth=depth, exception=record.exc_info)
        logger_opt.log(level, record.getMessage())

# Подменяем logging
logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)
# Отключаем лишний шум
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# Логгер для использования внутри этого файла
logger = loguru_logger.bind(service_name="Alembic")


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
# if config.config_file_name is not None:
#     fileConfig(config.config_file_name)

# Указываем Alembic на метаданные базовой модели
target_metadata = Base.metadata


# Функция для формирования URL базы данных
def get_database_url() -> str:
    """
    Читает переменные окружения и формирует URL базы данных.

    Raises:
        ValueError, если одна или несколько переменных окружения отсутствуют.
    """
    def get_env(key: str) -> str | None:
        val = os.getenv(key)
        return val.strip() if val else None

    db_user = get_env("DB_USER")
    db_password = get_env("DB_PASSWORD")
    db_host = get_env("DB_HOST")
    db_port = get_env("DB_PORT")
    db_name = get_env("DB_NAME")

    # Проверка, что все переменные установлены
    if not all([db_user, db_password, db_host, db_port, db_name]):
        raise ValueError("Одна или несколько переменных для подключения к БД отсутствуют.")


    try:
        db_ip = socket.gethostbyname(db_host)
        logger.info(f"DNS Check: Host '{db_host}' resolved to {db_ip}")
    except Exception as e:
        logger.critical(f"DNS Check FAILED: Host '{db_host}' could not be resolved. Error: {e}")
        raise
    # ------------------------------------

    # Кодируем учетные данные (URL Encode)
    # Это превращает 'p@ssword' в 'p%40ssword', что безопасно для строки подключения
    encoded_user = quote_plus(db_user)
    encoded_password = quote_plus(db_password)

    return f"postgresql+psycopg://{encoded_user}:{encoded_password}@{db_ip}:{db_port}/{db_name}"

# Сначала пытаемся получить URL базы данных из существующей конфигурации
# Это позволяет тестам в conftest.py переопределять его
current_db_url = config.get_alembic_option("sqlalchemy.url")

# Если URL базы данных не был установлен извне, формируем его из переменных окружения
if not current_db_url:
    try:
        current_db_url = get_database_url()
    except ValueError as exc:
        logger.error(f"Config Error: {exc}")
        sys.exit(1)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=current_db_url,
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
    connectable_config = config.get_section(config.config_ini_section, {})
    connectable_config["sqlalchemy.url"] = current_db_url

    # Создаем движок
    connectable = engine_from_config(
        connectable_config,
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
