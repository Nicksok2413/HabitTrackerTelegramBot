"""
Задачи для планировщика.

Содержит логику отправки напоминаний пользователям о необходимости выполнить привычки.
"""

from collections import defaultdict

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import select, text, update

from src.api.core.database import db
from src.api.models import Habit, HabitExecution, HabitExecutionStatus, User
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

            # Группируем привычки по пользователю
            user_habits_map = defaultdict(list)  # Словарь: { user_obj: [habit1, habit2, ...] }

            # Итерируемся по привычкам и добавляем данные в словарь
            for habit in habits_to_remind:
                if habit.user and habit.user.telegram_id:
                    user_habits_map[habit.user].append(habit)

            # Итерируемся по словарю и асинхронно отправляем уведомления
            for user, user_habits in user_habits_map.items():

                # Формируем текст уведомления
                habits_names = []

                for habit in user_habits:
                    habits_names.append(f"• <b>{habit.name}</b>")

                notification = "⏰ <b>Напоминание!</b>\nПора выполнить следующие привычки:\n" + "\n".join(habits_names)

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


async def daily_maintenance() -> None:
    """
    Задача обслуживания: сброс стриков для пропущенных привычек.

    Сбрасывает current_streak в 0 для активных привычек, которые были пропущены вчера.
    Запускается раз в час, например, в XX:05 (так как часовые пояса разные, "полночь" наступает в разное время).

    Критерии сброса:
    1. Привычка активна.
    2. current_streak > 0.
    3. Нет выполнения (DONE) за "вчера" (по часовому поясу пользователя).
    """
    log.info("🧹 Запуск обслуживания (сброс стриков)...")

    async with db.session() as session:
        # Логика: найти все активные привычки, у которых current_streak > 0,
        # но нет записи о выполнении за "вчера" (по таймзоне юзера)

        try:
            # Конвертируем UTC время сервера в локальное время пользователя, используя его timezone

            # Функция `timezone(zone_name, timestamp)` специфична для PostgreSQL
            # Она конвертирует время из одной зоны в другую внутри SQL-запроса

            # SQL-выражение "Вчерашняя дата" для конкретного пользователя
            user_yesterday = text("(timezone(users.timezone, now())::date - 1)")

            # Подзапрос: существует ли запись 'DONE' для этой привычки на "вчера" (по времени юзера)
            has_done_yesterday = select(1).where(
                HabitExecution.habit_id == Habit.id,
                HabitExecution.status == HabitExecutionStatus.DONE,
                HabitExecution.execution_date == user_yesterday
            ).exists()

            # Находим ID привычек для сброса
            # Явно джойним User'а, чтобы выражение users.timezone сработало
            candidates_statement = (
                select(Habit.id)
                .join(User)
                .where(
                    Habit.is_active.is_(True),
                    Habit.current_streak > 0,
                    ~has_done_yesterday  # Если вчера не было выполнения (`~` - отрицание)
                )
            )

            result = await session.execute(candidates_statement)

            habit_ids_to_reset = result.scalars().all()

            if habit_ids_to_reset:
                # Массово обновляем привычки (сбрасываем стрик в 0)
                update_statement = (
                    update(Habit)
                    .where(Habit.id.in_(habit_ids_to_reset))
                    .values(current_streak=0)
                )

                await session.execute(update_statement)

                # Фиксируем изменения в базе данных
                await session.commit()

                log.info(f"📉 Сброшен стрик у {len(habit_ids_to_reset)} пропущенных привычек.")

            else:
                log.debug("Нет привычек для сброса стрика в этом часе.")

        except Exception as exc:
            # Логируем ошибку
            log.error(f"Ошибка при сбросе стриков: {exc}", exc_info=True)

            # Откатываем транзакцию, чтобы сохранить целостность данных
            await session.rollback()
