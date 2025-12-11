"""
Главный файл запуска планировщика (Scheduler).

Отвечает за:
- Инициализацию подключения к БД.
- Настройку и запуск Apscheduler.
- Корректное завершение работы (Graceful Shutdown).
"""

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.api.core.database import db
from src.core_shared.logging_setup import setup_logger
from src.scheduler.config import settings
from src.scheduler.tasks import bot, daily_maintenance, send_reminders

# Настраиваем логгер
log = setup_logger("SchedulerMain", log_level_override=settings.LOG_LEVEL)


async def main() -> None:
    """Запуск сервиса планировщика."""
    log.info("⏳ Запуск сервиса планировщика (Scheduler Service)...")

    # Инициализируем подключение к базе данных
    try:
        await db.connect()
    except Exception as exc:
        log.critical(f"Не удалось подключиться к БД: {exc}")
        return

    # Настраиваем планировщик (AsyncIOScheduler работает поверх asyncio event loop)
    scheduler = AsyncIOScheduler()

    # Добавляем задачу отправки уведомлений пользователям
    # CronTrigger(second=0): запускать в начале каждой минуты (XX:XX:00)
    scheduler.add_job(
        send_reminders,
        trigger=CronTrigger(second=0),
        id="send_reminders_job",
        name="Ежеминутная проверка напоминаний о привычках",
        replace_existing=True,  # Перезаписывать задачу при перезапуске
    )

    # Добавляем Maintenance-задачу сброса стриков
    # CronTrigger(minute=5): запускать каждый час в 5-ю минуту (XX:05), чтобы обработать смену суток в любом поясе
    scheduler.add_job(
        daily_maintenance,
        trigger=CronTrigger(minute=5),
        id="maintenance_job",
        name="Сброс стриков у привычек, которые были пропущены вчера",
        replace_existing=True,  # Перезаписывать задачу при перезапуске
    )

    # Запускаем планировщик
    try:
        scheduler.start()
        log.info("✅ Планировщик (Scheduler) успешно запущен и работает. Нажмите Ctrl+C для выхода.")

        # Бесконечный цикл, чтобы сервис не завершился
        # Apscheduler работает в фоне, поэтому нужно удерживать event loop
        while True:
            await asyncio.sleep(3600)  # Спим по часу, просто чтобы процесс жил

    except (KeyboardInterrupt, SystemExit):
        log.info("Получен сигнал остановки (Ctrl+C) планировщика...")

    except Exception as exc:
        log.critical(f"Непредвиденное падение сервиса планировщика: {exc}", exc_info=True)

    finally:
        # Корректное завершение (Graceful Shutdown)
        log.info("🛑 Остановка сервиса планировщика...")

        # Останавливаем планировщик
        scheduler.shutdown()

        # Закрываем соединение с базой данных
        await db.disconnect()

        # Закрываем сессию бота
        await bot.session.close()

        log.info("Планировщик (Scheduler) остановлен корректно.")


if __name__ == "__main__":
    try:
        # Запускаем asyncio event loop
        asyncio.run(main())
    except KeyboardInterrupt:
        # Этот блок нужен, чтобы не видеть трейсбек asyncio при Ctrl+C до запуска main
        pass
