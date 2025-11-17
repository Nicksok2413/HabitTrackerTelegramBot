#!/bin/sh

# ==============================================================================
# Entrypoint-скрипт для API-контейнера
# Выполняет команды, необходимые перед запуском основного процесса
# ==============================================================================

# Выход при ошибке (fail fast)
set -e

# Функция для проверки готовности БД
wait_for_db() {
    echo "-> (API Entrypoint) Ожидание запуска PostgreSQL..."
    python << END
import os
import psycopg
import sys
import time

db_url = (
    f"dbname={os.environ['DB_NAME']} "
    f"user={os.environ['DB_USER']} "
    f"password={os.environ['DB_PASSWORD']} "
    f"host={os.environ['DB_HOST']} "
    f"port={os.environ['DB_PORT']}"
)

try:
    conn = None
    print("Попытка подключения к БД...")

    for attempt in range(30):
        try:
            conn = psycopg.connect(db_url, connect_timeout=2)
            print(f"   Попытка {attempt+1}/30: PostgreSQL запущен - соединение установлено.")
            break
        except psycopg.OperationalError as exc:
            print(f"   Попытка {attempt+1}/30: PostgreSQL недоступен, ожидание... ({exc})")
            time.sleep(1)

    if conn is None:
        print("-> (API Entrypoint) Не удалось подключиться к PostgreSQL после 30 секунд.")
        sys.exit(1)

    conn.close()

except KeyError as exc:
    print(f"-> (API Entrypoint) Ошибка: переменная окружения {exc} не установлена.")
    sys.exit(1)
except Exception as exc:
    print(f"-> (API Entrypoint) Произошла ошибка при проверке БД (psycopg3): {exc}")
    sys.exit(1)
END
}

# Ожидание БД
wait_for_db

# Установка прав на том логов
# Указываем пользователя и группу, под которыми будет работать приложение
APP_USER=appuser
APP_GROUP=appgroup
echo "-> (API Entrypoint) Установка владельца для /logs на ${APP_USER}:${APP_GROUP}..."
# Используем chown для изменения владельца точки монтирования тома
# Это нужно делать от root перед понижением привилегий
chown -R "${APP_USER}:${APP_GROUP}" /logs
echo "-> (API Entrypoint) Права установлены."


# Анализируем первый аргумент (`$1`), чтобы понять, что будет запущено
case "$1" in
  # Если первый аргумент - "uvicorn", запускаем веб-сервер
  "uvicorn")
    echo "-> (API Entrypoint) Запуск основного приложения Uvicorn..."
    ;;
  # Если первый аргумент - "alembic", работаем с миграциями
  "alembic")
    echo "-> (API Entrypoint) Выполнение команды Alembic: $@"
    ;;
  # "*" - любой другой случай (например, запуск `bash` для отладки)
  *)
    echo "-> (API Entrypoint) Запуск переданной команды: $@"
    ;;
esac

# Запускаем команду, переданную в контейнер
exec su-exec "${APP_USER}" "$@"