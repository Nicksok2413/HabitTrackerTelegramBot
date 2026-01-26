# Makefile - Единая точка входа для управления проектом

# .PHONY гарантирует, что make не будет путать эти команды с именами файлов
.PHONY: help install up down rebuild prune logs migrate revision lint format types test test-cov check

# Команда по умолчанию, которая будет вызвана при запуске `make`
default: help

help:
	@echo "Доступные команды:"
	@echo ""
	@echo "Установка зависимостей:"
	@echo "  install        - Установить Python зависимости"
	@echo ""
	@echo "Управление Docker окружением:"
	@echo "  up             - Запустить все сервисы в фоновом режиме"
	@echo "  down           - Остановить все сервисы"
	@echo "  rebuild        - Пересобрать образы и запустить сервисы"
	@echo "  prune          - Остановить сервисы и УДАЛИТЬ ВСЕ ДАННЫЕ (БД, логи)"
	@echo "  logs           - Показать логи всех сервисов"
	@echo ""
	@echo "Проверка качества кода и тесты:"
	@echo "  lint           - Проверить код линтером Ruff"
	@echo "  lint-fix       - Исправить код линтером Ruff"
	@echo "  format-check   - Проверить код форматтером Ruff"
	@echo "  format         - Отформатировать код форматтером Ruff"
	@echo "  types          - Проверить статическую типизацию mypy"
	@echo "  test           - Запустить тесты pytest"
	@echo "  test-cov       - Запустить тесты pytest с отчетом о покрытии кода"
	@echo "  check          - Запустить статический анализ (lint, format-check, types) последовательно"
	@echo "  check-all      - Запустить все проверки (lint, format-check, types, test) последовательно"
	@echo ""
	@echo "Управление миграциями базы данных:"
	@echo "  migrate        - Применить миграции Alembic"
	@echo "  revision       - Создать новый файл миграции Alembic. Пример: make revision m=\"Add user table\""


# ------------------------------------------------------------------------------
# Установка зависимостей
# ------------------------------------------------------------------------------
install:
	@echo "-> Установка зависимостей с помощью Poetry..."
	poetry install
	@echo "-> Зависимости успешно установлены."

# ------------------------------------------------------------------------------
# Управление Docker окружением
# ------------------------------------------------------------------------------
up:
	docker compose up -d

down:
	docker compose down

rebuild:
	@echo "-> Пересборка и запуск сервисов..."
	docker compose up -d --build
	@echo "-> Сервисы успешно пересобраны и запущены."

prune:
	@echo "ВНИМАНИЕ: Эта команда остановит контейнеры и УДАЛИТ ВСЕ ДАННЫЕ В ТОМАХ (volumes)."
	@read -p "Вы уверены, что хотите продолжить? [y/N] " confirm && \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		echo "-> Начинаем полную очистку..."; \
		echo " * Чистим основное окружение"; \
		docker compose down -v; \
		echo " * Чистим тестовое окружение"; \
		docker compose -f docker-compose.test.yml down -v; \
		echo "-> Окружение полностью очищено."; \
	else \
		echo "-> Очистка отменена."; \
	fi

logs:
	docker compose logs -f

# ------------------------------------------------------------------------------
# Проверка качества кода и тесты
# ------------------------------------------------------------------------------
lint:
	@echo "-> Проверка кода с помощью Ruff linter..."
	poetry run ruff check .

lint-fix:
	@echo "-> Исправление кода с помощью Ruff linter..."
	poetry run ruff check . --fix

format-check:
	@echo "-> Форматирование кода с помощью Ruff formatter..."
	poetry run ruff format . --check

format:
	@echo "-> Форматирование кода с помощью Ruff formatter..."
	poetry run ruff format .

types:
	@echo "-> Статическая проверка типов с помощью mypy..."
	poetry run mypy .

test:
	@echo "-> Запуск тестов pytest..."
	poetry run pytest

test-cov:
	@echo "-> Запуск тестов pytest с отчетом о покрытии..."
	poetry run pytest --cov=src/ --cov-report=term-missing --cov-report=html

check: lint format-check types
	@echo "-> Статический анализ (lint, format, types) успешно пройден!"

check-all: lint format-check types test
	@echo "-> Все проверки (включая тесты) успешно пройдены!"

# ------------------------------------------------------------------------------
# Управление миграциями БД
# ------------------------------------------------------------------------------
migrate:
	@echo "-> Применение миграций Alembic..."
	# Запускаем временный контейнер api-migrate
	docker compose run --rm api-migrate
	@echo "-> Миграции успешно применены."

revision:
	# Проверяем, что передано сообщение для миграции
	@if [ -z "$(m)" ]; then \
		echo "Ошибка: необходимо указать сообщение для миграции. Пример: make revision m=\"Your message\""; \
		exit 1; \
	fi

	@echo "-> Создание новой миграции..."
	docker compose run --rm api-migrate python -m alembic -c pyproject.toml revision --autogenerate -m "$(m)"
	@echo "-> Миграция успешно создана."
	@echo "-> Форматирование новой миграции..."
	make format
	@echo "-> Готово."
