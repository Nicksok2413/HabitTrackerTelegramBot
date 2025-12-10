"""
Задачи для планировщика.

Содержит логику отправки напоминаний пользователям о необходимости выполнить привычки.
"""

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.api.core.database import db
from src.api.models import Habit, User
from src.api.repositories import HabitRepository, UserRepository
from src.core_shared.logging_setup import setup_logger
from src.scheduler.config import settings

# Настраиваем логгер
log = setup_logger("SchedulerTasks", log_level_override=settings.LOG_LEVEL)

# Создаем бота глобально для модуля (он нужен только для отправки сообщений)
bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def send_reminders() -> None:
    """
    Периодическая задача для отправки напоминаний о привычках.

    Алгоритм работы:
    1. Открывает сессию базы данных.
    2. Находит активные привычки, время напоминания которых (в часовом поясе пользователя)
       совпадает с текущим временем сервера (UTC).
    3. Отправляет сообщения пользователям в Telegram.
    4. Обрабатывает ошибки (например, если пользователь заблокировал бота).
    """
    log.info("🔍 Запуск задачи проверки напоминаний...")

    # Используем асинхронный контекстный менеджер для сессии БД
    async with db.session() as session:
        # Репозиторий привычек
        habit_repo = HabitRepository(Habit)

        # Репозиторий пользователей нужен для обновления статуса блокировки бота
        user_repo = UserRepository(User)

        try:
            # Получаем привычки, о которых нужно напомнить прямо сейчас
            habits_to_remind = await habit_repo.get_habits_needing_notification(db_session=session)

            if not habits_to_remind:
                log.debug("Нет привычек для напоминания в эту минуту.")
                return

            log.info(f"Найдено {len(habits_to_remind)} привычек для отправки уведомлений.")

            # Итерируемся по привычкам и асинхронно отправляем уведомления
            for habit in habits_to_remind:
                user = habit.user

                # Формируем текст уведомления
                habit_description = f"\n<i>{habit.description}</i>" if habit.description else ""

                notification = (
                    f"⏰ <b>Напоминание!</b>\n\nПора выполнить привычку: <b>{habit.name}</b>{habit_description}"
                )

                try:
                    # Отправляем уведомление
                    await bot.send_message(chat_id=user.telegram_id, text=notification)
                    log.info(f"✅ Напоминание отправлено пользователю {user.telegram_id} (Habit ID: {habit.id})")

                except TelegramForbiddenError:
                    # Пользователь заблокировал бота
                    log.warning(f"🚫 Пользователь {user.telegram_id} заблокировал бота. Обновляем статус в БД.")

                    # Обновляем флаг is_bot_blocked пользователя, чтобы больше не пытаться отправлять ему уведомления
                    # И не спамить БД запросами
                    await user_repo.update(session, db_obj=user, obj_in={"is_bot_blocked": True})

                    # Фиксируем изменение статуса пользователя
                    await session.commit()

                except TelegramBadRequest as exc:
                    # Ошибки валидации со стороны Telegram (например, чат не найден)
                    log.error(f"❌ Ошибка Telegram API при отправке пользователю {user.telegram_id}: {exc}")
                except Exception as exc:
                    # Любые другие ошибки при отправке конкретного сообщения не должны прерывать цикл
                    log.error(f"❌ Непредвиденная ошибка при отправке (User: {user.telegram_id}): {exc}")

        except Exception as exc:
            # Глобальная ошибка в задаче (например, отвал БД)
            log.error(f"💥 Критическая ошибка в цикле send_reminders: {exc}", exc_info=True)
