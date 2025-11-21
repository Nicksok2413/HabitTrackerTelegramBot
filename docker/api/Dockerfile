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

# Устанавливаем Poetry
RUN pip install --upgrade pip && \
    pip install poetry

# Копируем только файлы, определяющие зависимости
COPY pyproject.toml poetry.lock ./

# Устанавливаем зависимости
# --no-dev: не устанавливаем зависимости для разработки (pytest, ruff и т.д.) в production-образ
RUN poetry install --only main --no-root

# =================================================================
# Этап 2: "runner" - Финальный, чистый образ для запуска приложения
# =================================================================
# Используем легковесный образ Python
FROM python:3.12-slim

# Стандартные переменные окружения для Python в Docker
# Весь вывод (print, логи) будет сразу отправляться в консоль Docker
ENV PYTHONUNBUFFERED 1
# Не создавать .pyc файлы
ENV PYTHONDONTWRITEBYTECODE 1
# Добавляем виртуальное окружение в PATH
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем только те системные пакеты, которые необходимы для работы приложения:
# - libpq-dev: для работы драйвера psycopg
# `rm -rf /var/lib/apt/lists/*` — удаляем списки пакетов для уменьшения размера образа
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Копируем скомпилированный `su-exec` из этапа "builder"
COPY --from=builder /usr/local/bin/su-exec /usr/local/bin/su-exec

# Копируем виртуальное окружение с зависимостями из этапа "builder"
COPY --from=builder /app/.venv /app/.venv

# Копируем entrypoint-скрипт
COPY ./docker/api/entrypoint.sh /entrypoint.sh

# Устанавливаем права на выполнение entrypoint-скрипта
RUN chmod +x /entrypoint.sh

# Создаем системную группу `appgroup` и системного non-root пользователя `appuser`, чтобы не запускать приложение от root
# `--no-create-home` — не создавать домашнюю директорию
RUN addgroup --system appgroup && adduser --system --ingroup appgroup --no-create-home appuser

# Меняем владельца рабочей директории на appuser
RUN chown appuser:appgroup /app

# Копируем файлы, нужные для API и миграций, сразу устанавливая правильного владельца
COPY --chown=appuser:appgroup pyproject.toml ./
COPY --chown=appuser:appgroup ./alembic ./alembic
COPY --chown=appuser:appgroup ./src/api ./src/api
COPY --chown=appuser:appgroup ./src/core_shared ./src/core_shared

# Сообщаем Docker, что контейнер будет слушать порт 8000
EXPOSE 8000

# Устанавливаем скрипт как точку входа (он будет выполнен перед основной командой контейнера)
ENTRYPOINT ["/entrypoint.sh"]
