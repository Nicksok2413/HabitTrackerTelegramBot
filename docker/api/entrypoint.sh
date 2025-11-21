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

try:
    # Безопасно формируем строку подключения, , которая корректно экранирует спецсимволы
    conn_str = psycopg.conninfo.make_conninfo(
        dbname=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        host=os.environ.get("DB_HOST"),
        port=os.environ.get("DB_PORT"),
    )

    conn = None
    print("Попытка подключения к БД...")

    for attempt in range(30):
        try:
            conn = psycopg.connect(conn_str, connect_timeout=2)
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

# Указываем пользователя и группу, под которыми будет работать приложение
APP_USER=appuser
APP_GROUP=appgroup

# Устанавливаем права на тома логов и миграций
echo "-> (API Entrypoint) Выдача прав на /app/logs..."
# Используем chown для изменения владельца точки монтирования тома
# Это нужно делать от root перед понижением привилегий
chown -R "${APP_USER}:${APP_GROUP}" /logs

# Миграции (если папка существует, отдаем её пользователю)
# Это позволит Alembic создавать файлы версий
if [ -d "/app/alembic/versions" ]; then
    echo "-> (API Entrypoint) Выдача прав на /app/alembic/versions..."
    chown -R "${APP_USER}:${APP_GROUP}" /app/alembic/versions
fi

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