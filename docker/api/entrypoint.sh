#!/bin/sh

# ==============================================================================
# Универсальный Entrypoint-скрипт для Backend-сервисов (API, Scheduler, Migrations)
# Выполняет команды, необходимые перед запуском основных процессов
# ==============================================================================

# Выход при ошибке (fail fast)
set -e

# Функция для проверки готовности БД
wait_for_db() {
    echo "-> (Entrypoint) Ожидание запуска PostgreSQL..."
    /app/.venv/bin/python << END
import os
import psycopg
import sys
import time

try:
    # Безопасно формируем строку подключения, которая корректно экранирует спецсимволы
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
        print("-> (Entrypoint) Не удалось подключиться к PostgreSQL после 30 секунд.")
        sys.exit(1)

    conn.close()

except KeyError as exc:
    print(f"-> (Entrypoint) Ошибка: переменная окружения {exc} не установлена.")
    sys.exit(1)
except Exception as exc:
    print(f"-> (Entrypoint) Произошла ошибка при проверке БД (psycopg3): {exc}")
    sys.exit(1)
END
}

# Ожидание БД
wait_for_db

# Указываем пользователя и группу, под которыми будет работать приложение
APP_USER=appuser
APP_GROUP=appgroup

# Устанавливаем права на логи
# Если папка logs существует, меняем владельца
# Делаем это под root перед понижением привилегий
if [ -d "/logs" ]; then
    echo "-> (Entrypoint) Выдача прав на /logs..."
    chown -R "${APP_USER}:${APP_GROUP}" /logs
    echo "-> (Entrypoint) Права установлены."
fi


# Анализируем команду, чтобы понять, что будет запущено
case "$@" in
  # Если в команде встречается слово "uvicorn", запускаем веб-сервер
  *"uvicorn"*)
    echo "-> (Entrypoint: API) Запуск основного приложения Uvicorn..."
    ;;
  # Если в команде встречается слово "alembic", работаем с миграциями
  *"alembic"*)
    echo "-> (Entrypoint: Alembic) Выполнение команды Alembic: $@"
    ;;
  # Если в команде встречается слово "scheduler", запускаем планировщик
  *"scheduler"*)
    echo "-> (Entrypoint: Scheduler) Запуск планировщика: $@"
    ;;
  # "*" - любой другой случай (например, запуск `bash` для отладки)
  *)
    echo "-> (Entrypoint) Запуск переданной команды: $@"
    ;;
esac

# Запускаем команду, переданную в контейнер, под пользователем appuser
exec su-exec "${APP_USER}" "$@"