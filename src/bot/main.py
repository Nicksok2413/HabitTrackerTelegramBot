"""
Главный файл запуска Telegram бота.

Отвечает за:
1. Инициализацию Bot и Dispatcher.
2. Настройку логирования.
3. Регистрацию зависимостей (API Client).
4. Подключение роутеров (Handlers).
5. Запуск процесса Polling.
"""

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from src.bot.core.config import settings
from src.bot.handlers import commands
from src.bot.services.api_client import HabitTrackerClient
from src.core_shared.logging_setup import setup_logger

# Настраиваем логгер
log = setup_logger("BotMain", log_level_override=settings.LOG_LEVEL)


async def main():
    """Асинхронная точка входа."""
    log.info("🚀 Запуск Telegram бота...")

    # 1. Инициализация бота
    # parse_mode=ParseMode.HTML позволяет использовать HTML теги в сообщениях (<b>, <i>, <a href>)
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # 2. Инициализация диспетчера
    # Диспетчер обрабатывает входящие обновления и маршрутизирует их в хендлеры
    dp = Dispatcher()

    # 3. Инициализация API клиента
    # Создаем экземпляр клиента, который будет жить пока живет бот
    api_client = HabitTrackerClient()

    # 4. Внедрение зависимостей (Dependency Injection)
    # Передаем api_client в workflow_data диспетчера.
    # Теперь любой хендлер может запросить аргумент `api_client` и получить этот экземпляр.
    dp["api_client"] = api_client

    # 5. Регистрация роутеров (хендлеров)
    # Порядок важен! Специфичные хендлеры должны быть выше общих.
    dp.include_router(commands.router)
    # dp.include_router(habits.router) # Добавим позже

    try:
        # Удаляем вебхук и очищаем очередь обновлений, накопившихся пока бот спал
        await bot.delete_webhook(drop_pending_updates=True)

        log.info("Бот запущен и готов к работе (Polling mode).")

        # 6. Запуск поллинга (бесконечный цикл получения обновлений)
        await dp.start_polling(bot)

    except Exception as e:
        log.exception(f"Критическая ошибка при работе бота: {e}")

    finally:
        # 7. Корректное завершение (Graceful Shutdown)
        log.info("Остановка бота...")

        # Закрываем сессию API клиента
        await api_client.close()
        # Закрываем сессию бота
        await bot.session.close()

        log.info("Бот остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        # Обработка Ctrl+C в терминале
        log.info("Бот остановлен вручную.")