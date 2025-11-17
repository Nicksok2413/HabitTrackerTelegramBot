#!/bin/sh

# ==============================================================================
# Entrypoint-скрипт для API-контейнера.
# Выполняет команды, необходимые перед запуском основного процесса.
# ==============================================================================

set -e # Выход при ошибке (fail fast)

# Функция для проверки готовности БД
wait_for_db() {
    echo "-> (API Entrypoint) Ожидание запуска PostgreSQL..."
    python << END
import os
import psycopg
import sys
import time

try:
    conn = None
    print("Попытка подключения к БД...")

    for attempt in range(30):
        try:
            conn = psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=2)
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

# Применяем миграции Alembic
echo "-> (API Entrypoint) Применение миграций Alembic..."
su-exec "${APP_USER}" alembic upgrade head

# Запускаем основное приложение Uvicorn
echo "-> (API Entrypoint) Запуск основного приложения Uvicorn..."
exec su-exec "${APP_USER}" "$@"