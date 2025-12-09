
import asyncio
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from src.api.core.database import db
from src.api.models import Habit
from src.api.repositories import HabitRepository, UserRepository
from src.api.schemas import UserSchemaUpdate
from src.scheduler.config import settings
from src.core_shared.logging_setup import setup_logger

# Настраиваем логгер
log = setup_logger("SchedulerTasks", log_level_override=settings.LOG_LEVEL)

# Инициализируем бота только для отправки сообщений
# Используем контекстный менеджер при отправке или создаем один раз глобально?
# В apscheduler лучше создавать внутри функции или передавать аргументом.
# Но создание Bot объекта легкое, создадим глобально для модуля.
bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def send_reminders() -> None:
    """
    Периодическая задача:
    1. Подключается к БД.
    2. Находит привычки, о которых нужно напомнить прямо сейчас.
    3. Отправляет сообщения пользователям.
    """
    log.info("🔍 Запуск проверки напоминаний...")

    # Создаем новую сессию БД для этой итерации
    async with db.session() as session:
        habit_repo = HabitRepository(Habit)
        user_repo = UserRepository(Habit.user)  # type: ignore (нам нужен репо для обновления флага блокировки)

        try:
            # Получаем привычки
            habits_to_remind = await habit_repo.get_habits_needing_notification(session)

            if not habits_to_remind:
                log.debug("Нет привычек для напоминания в эту минуту.")
                return

            log.info(f"Найдено {len(habits_to_remind)} привычек для напоминания.")

            # Отправляем уведомления (асинхронно, но можно пачками)
            for habit in habits_to_remind:
                user = habit.user

                if not user or not user.telegram_id:
                    continue

                text = (
                    f"⏰ <b>Напоминание!</b>\n\n"
                    f"Пора выполнить привычку: <b>{habit.name}</b>\n"
                    f"<i>{habit.description or ''}</i>"
                )

                try:
                    await bot.send_message(chat_id=user.telegram_id, text=text)
                    log.info(f"Отправлено напоминание пользователю {user.telegram_id} о привычке {habit.id}")

                except TelegramForbiddenError:
                    log.warning(f"Пользователь {user.telegram_id} заблокировал бота. Помечаем в БД.")

                    # Обновляем статус пользователя, чтобы не спамить БД запросами
                    await user_repo.update(
                        session,
                        db_obj=user,
                        obj_in=UserSchemaUpdate(is_bot_blocked=True)
                    )

                    await session.commit()

                except TelegramBadRequest as exc:
                    log.error(f"Ошибка Telegram при отправке пользователю {user.telegram_id}: {exc}")
                except Exception as exc:
                    log.error(f"Непредвиденная ошибка отправки: {exc}")

        except Exception as exc:
            log.error(f"Ошибка в цикле send_reminders: {exc}", exc_info=True)