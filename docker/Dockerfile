# ==================================================================================
# 1. "builder": Общая стадия для сборки зависимостей и утилит
# ==================================================================================
FROM python:3.12-slim AS builder

# Устанавливаем переменные окружения для Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    PIP_NO_CACHE_DIR=1

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости:
# - build-essential, wget, ca-certificates: для компиляции su-exec
# `rm -rf /var/lib/apt/lists/*` — удаляем списки пакетов для уменьшения размера образа
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential wget ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Компилируем su-exec — утилиту для безопасного понижения привилегий с root до обычного пользователя
RUN wget -O su-exec.tar.gz https://github.com/ncopa/su-exec/archive/master.tar.gz && \
    tar -xzf su-exec.tar.gz && \
    cd su-exec-master && \
    make && \
    cp su-exec /usr/local/bin/su-exec && \
    cd / && \
    rm -rf su-exec.tar.gz su-exec-master

# Обновляем pip и устанавливаем Poetry
RUN pip install --upgrade pip && pip install poetry

# Копируем файлы зависимостей
COPY pyproject.toml poetry.lock ./

# Устанавливаем зависимости
# --only main: не устанавливаем dev-зависимости (pytest, ruff и т.д.) в production-образ
RUN poetry install --only main --no-root


# ==================================================================================
# 2. "base-runner": Общая база для запуска
# ==================================================================================
FROM python:3.12-slim AS base-runner

# Переменные окружения для Runtime
# Добавляем .venv в PATH, чтобы команды python/uvicorn/alembic работали напрямую
# Явно задаем HOME
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/app/.venv \
    PYTHONPATH="/app" \
    PATH="/app/.venv/bin:$PATH" \
    HOME="/home/appuser"

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем runtime-зависимости:
# - libpq-dev: для работы драйвера psycopg
# `rm -rf /var/lib/apt/lists/*` — удаляем списки пакетов для уменьшения размера образа
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Создаем группу с GID 1000 и непривилегированного пользователя с UID 1000
# Для безопасности, чтобы не запускать приложение от root
# Для решения проблем с правами доступа к volumes (миграции)
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/sh -m appuser

# Копируем скомпилированный `su-exec` и виртуальное окружение с зависимостями из этапа "builder"
COPY --from=builder /usr/local/bin/su-exec /usr/local/bin/su-exec
COPY --from=builder /app/.venv /app/.venv

# Общий код ядра
COPY --chown=appuser:appgroup ./src/core_shared ./src/core_shared


# ==================================================================================
# 3. "api": Финальный образ для API
# ==================================================================================
FROM base-runner AS api

# Копируем entrypoint-скрипт (специфичный для API) и устанавливаем ему права на выполнение
COPY ./docker/api/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Копируем код API и миграций
COPY --chown=appuser:appgroup ./src/api ./src/api
COPY --chown=appuser:appgroup ./migrations ./migrations
COPY --chown=appuser:appgroup ./pyproject.toml ./pyproject.toml

# Меняем владельца рабочей директории на appuser
RUN chown appuser:appgroup /app

# Сообщаем Docker, что контейнер будет слушать порт 8000
EXPOSE 8000

# Устанавливаем скрипт как точку входа (он будет выполнен перед основной командой контейнера)
ENTRYPOINT ["/entrypoint.sh"]

# Дефолтная команда (для самодостаточности контейнера)
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]


# ==================================================================================
# 4. "bot": Финальный образ для Телеграм-бота
# ==================================================================================
FROM base-runner AS bot

# Копируем entrypoint-скрипт (специфичный для бота) и устанавливаем ему права на выполнение
COPY ./docker/bot/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Копируем код бота
COPY --chown=appuser:appgroup ./src/bot ./src/bot

# Меняем владельца рабочей директории на appuser
RUN chown appuser:appgroup /app

# Устанавливаем скрипт как точку входа (он будет выполнен перед основной командой контейнера)
ENTRYPOINT ["/entrypoint.sh"]

# Дефолтная команда (для самодостаточности контейнера)
CMD ["python", "src/bot/main.py"]

# ==================================================================================
# 5. "scheduler": Финальный образ для планировщика
# ==================================================================================
FROM base-runner AS scheduler

# Копируем entrypoint-скрипт от API (планировщику тоже нужно ждать БД) и устанавливаем ему права на выполнение
COPY ./docker/api/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Копируем код API (планировщик использует модели и репозитории из src.api) и код планировщика
COPY --chown=appuser:appgroup ./src/api ./src/api
COPY --chown=appuser:appgroup ./src/scheduler ./src/scheduler

# Меняем владельца рабочей директории на appuser
RUN chown appuser:appgroup /app

# Устанавливаем скрипт как точку входа (он будет выполнен перед основной командой контейнера)
ENTRYPOINT ["/entrypoint.sh"]

# Дефолтная команда (для самодостаточности контейнера)
CMD ["python", "src/scheduler/main.py"]