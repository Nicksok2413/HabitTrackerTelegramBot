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

# Устанавливаем системные зависимости, которые нужны только для сборки:
# - build-essential, wget, ca-certificates: для компиляции su-exec
# `rm -rf /var/lib/apt/lists/*` — удаляем списки пакетов
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Компилируем su-exec — утилиту для безопасного понижения привилегий с root до обычного пользователя
RUN wget -O su-exec.tar.gz https://github.com/ncopa/su-exec/archive/master.tar.gz && \
    tar -xzf su-exec.tar.gz && \
    cd su-exec-master && \
    make && \
    cp su-exec /usr/local/bin/su-exec && \
    cd / && \
    rm -rf su-exec.tar.gz su-exec-master

# Обновляем pip и устанавливаем Poetry
RUN pip install --upgrade pip && \
    pip install poetry

# Копируем файлы, определяющие зависимости
COPY pyproject.toml poetry.lock ./

# Устанавливаем зависимости
# --only main: не устанавливаем dev-зависимости (pytest, ruff и т.д.) в production-образ
RUN poetry install --only main --no-root

# =================================================================
# Этап 2: "runner" - Финальный, чистый образ для запуска приложения
# =================================================================
# Используем легковесный образ Python
FROM python:3.12-slim

# Переменные окружения для Runtime
ENV PYTHONUNBUFFERED 1 \
    PYTHONDONTWRITEBYTECODE 1 \
    # Добавляем .venv в PATH, чтобы команды python/uvicorn/alembic работали напрямую
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# Устанавливаем рабочую директорию
WORKDIR /app

# Создаем группу с GID 1000 и непривилегированного пользователя с UID 1000
# Для безопасности, чтобы не запускать приложение от root
# Для решения проблемы с правами доступа к volumes (миграции) и кэшами
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/sh -m appuser

# Явно задаем HOME, чтобы инструменты (Ruff, Python) знали, где хранить кэш
ENV HOME=/home/appuser

# Устанавливаем только те системные пакеты, которые необходимы для работы приложения:
# - libpq-dev: для работы драйвера psycopg
# `rm -rf /var/lib/apt/lists/*` — удаляем списки пакетов для уменьшения размера образа
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Копируем скомпилированный `su-exec` и виртуальное окружение с зависимостями из этапа "builder"
COPY --from=builder /usr/local/bin/su-exec /usr/local/bin/su-exec
COPY --from=builder /app/.venv /app/.venv

# Копируем entrypoint-скрипт и устанавливаем ему права на выполнение
COPY ./docker/api/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Создаем директорию для логов и устанавливаем владельца
# Эта директория будет перекрыта томом, но полезно иметь ее с правильными правами в образе (для Self-Contained Image)
RUN mkdir /logs && chown appuser:appgroup /logs

# Меняем владельца рабочей директории на appuser
RUN chown appuser:appgroup /app

# Копируем файлы, нужные для API и миграций, сразу устанавливая правильного владельца
COPY --chown=appuser:appgroup ./alembic ./alembic
COPY --chown=appuser:appgroup ./pyproject.toml ./pyproject.toml
COPY --chown=appuser:appgroup ./src/api ./src/api
COPY --chown=appuser:appgroup ./src/core_shared ./src/core_shared

# Сообщаем Docker, что контейнер будет слушать порт 8000
EXPOSE 8000

# Устанавливаем скрипт как точку входа (он будет выполнен перед основной командой контейнера)
ENTRYPOINT ["/entrypoint.sh"]
