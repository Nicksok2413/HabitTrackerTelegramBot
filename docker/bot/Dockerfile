# =================================================================
# Этап 1: "builder" - Среда для сборки зависимостей
# =================================================================
# Используем легковесный образ Python
FROM python:3.12-slim as builder

# Устанавливаем переменные окружения для Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    PIP_NO_CACHE_DIR=1

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

# Обновляем pip и устанавливаем Poetry
RUN pip install --upgrade pip && \
    pip install poetry

# Копируем файлы, определяющие зависимости
COPY pyproject.toml poetry.lock ./

# Устанавливаем зависимости
# --only main: не устанавливаем dev-зависимости (pytest, ruff и т.д.) в production-образ
RUN poetry install --only main --no-root

# =================================================================
# Этап 2: "runner" - Финальный, чистый образ для запуска бота
# =================================================================
# Используем легковесный образ Python
FROM python:3.12-slim

# Переменные окружения для Runtime
# Добавляем .venv в PATH, чтобы команды python/uvicorn/alembic работали напрямую
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# Устанавливаем рабочую директорию
WORKDIR /app

# Создаем группу с GID 1000 и непривилегированного пользователя с UID 1000
# Для безопасности, чтобы не запускать бота от root
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/sh -m appuser

# Копируем виртуальное окружение с зависимостями из этапа "builder"
COPY --from=builder /app/.venv /app/.venv

# Копируем код и сразу устанавливая правильного владельца
COPY --chown=appuser:appgroup ./src/bot ./src/bot
COPY --chown=appuser:appgroup ./src/core_shared ./src/core_shared

USER appuser

# Запускаем бота
CMD ["python", "src/bot/main.py"]