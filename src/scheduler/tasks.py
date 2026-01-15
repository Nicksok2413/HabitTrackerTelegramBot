"""
Задачи для планировщика.

Генерирует события для Celery worker'ов и выполняет обслуживание БД.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select, text, update

from src.api.core.database import db
from src.api.models import Habit, HabitExecution, HabitExecutionStatus, User
from src.api.repositories import HabitRepository
from src.core_shared.logging_setup import setup_logger
from src.scheduler.config import settings
from src.worker.tasks import send_habit_notification_task

# Настраиваем логгер
log = setup_logger("SchedulerTasks", log_level_override=settings.LOG_LEVEL)


async def schedule_reminders() -> None:
    """
    Генератор задач для отправки напоминаний о привычках.

    Алгоритм работы:
    1. Получает список уникальных активных таймзон из БД.
    2. Для каждой таймзоны вычисляет текущее локальное время.
    3. Делает точечный запрос к БД для поиска привычек на это время.
    4. Отправляет задачи в очередь Celery (Redis).
    """
    log.info("🔍 Запуск проверки напоминаний...")

    # Используем асинхронный контекстный менеджер для сессии БД
    async with db.session() as session:
        # Репозиторий привычек
        habit_repo = HabitRepository(Habit)

        try:
            # Получаем список уникальных таймзон
            active_timezones = await habit_repo.get_active_timezones(db_session=session)

            # Текущее время сервера (всегда UTC)
            utc_now = datetime.now(timezone.utc)

            for timezone_name in active_timezones:
                try:
                    # Вычисляем локальное время
                    local_now = utc_now.astimezone(ZoneInfo(timezone_name))

                    # Нам нужны часы и минуты (ЧЧ:ММ:00)
                    target_time = local_now.time().replace(second=0, microsecond=0)
                    target_date = local_now.date()

                    # Получаем привычки, о которых нужно напомнить
                    habits_to_remind = await habit_repo.get_habits_for_notification(
                        db_session=session,
                        timezone=timezone_name,
                        target_time=target_time,
                        target_date=target_date,
                    )

                    if not habits_to_remind:
                        continue

                    log.info(
                        f"({timezone_name}) {target_time}: "
                        f"Найдено {len(habits_to_remind)} привычек для отправки уведомлений."
                    )

                    for habit in habits_to_remind:
                        if not habit.user.telegram_id:
                            continue

                        # Формируем уникальный ключ идемпотентности (ID привычки + Дата + Часы:Минуты)
                        idempotency_key = f"{habit.id}_{target_date.isoformat()}_{target_time.strftime('%H%M')}"

                        # Отправляем задачу в очередь Celery
                        send_habit_notification_task.delay(
                            chat_id=habit.user.telegram_id,
                            habit_name=habit.name,
                            idempotency_key=idempotency_key,
                        )  # .delay() - асинхронная отправка, возвращает управление мгновенно

                except ZoneInfoNotFoundError:
                    log.error(f"Неизвестная таймзона в БД: {timezone_name}")
                except Exception as exc:
                    log.error(f"Ошибка обработки таймзоны {timezone_name}: {exc}", exc_info=True)

        # Глобальная ошибка (например, отвал БД)
        except Exception as exc:
            log.error(f"💥 Критическая ошибка в schedule_reminders: {exc}", exc_info=True)


async def daily_maintenance() -> None:
    """
    Задача обслуживания: сброс стриков для пропущенных привычек.

    Сбрасывает current_streak в 0 для активных привычек, которые были пропущены вчера.
    Запускается раз в час, например, в XX:05 (так как часовые пояса разные, "полночь" наступает в разное время).

    Критерии сброса:
    1. Привычка активна.
    2. current_streak > 0.
    3. Нет выполнения (DONE) за "вчера" (по часовому поясу пользователя).
    4. Ещё нет выполнения (DONE) за "сегодня" (по часовому поясу пользователя).
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

            # SQL-выражение "Сегодняшняя дата" для конкретного пользователя
            user_today = text("timezone(users.timezone, now())::date")

            # Подзапрос: существует ли запись выполнения ('DONE') для этой привычки на "вчера" (по времени юзера)
            has_done_yesterday = (
                select(1)
                .where(
                    HabitExecution.habit_id == Habit.id,
                    HabitExecution.status == HabitExecutionStatus.DONE,
                    HabitExecution.execution_date == user_yesterday,
                )
                .exists()
            )

            # Подзапрос: существует ли запись выполнения ('DONE') для этой привычки на "сегодня" (по времени юзера)
            has_done_today = (
                select(1)
                .where(
                    HabitExecution.habit_id == Habit.id,
                    HabitExecution.status == HabitExecutionStatus.DONE,
                    HabitExecution.execution_date == user_today,
                )
                .exists()
            )

            # Находим ID привычек для сброса
            # Явно джойним User'а, чтобы выражения users.timezone сработали
            candidates_statement = (
                select(Habit.id)
                .join(User)
                .where(
                    Habit.is_active.is_(True),
                    Habit.current_streak > 0,
                    ~has_done_yesterday,  # Если вчера не было выполнения (`~` - отрицание)
                    ~has_done_today,  # И сегодня еще не было выполнения (`~` - отрицание)
                )
            )

            result = await session.execute(candidates_statement)

            habit_ids_to_reset = result.scalars().all()

            if habit_ids_to_reset:
                # Массово обновляем привычки (сбрасываем стрик в 0)
                update_statement = update(Habit).where(Habit.id.in_(habit_ids_to_reset)).values(current_streak=0)

                await session.execute(update_statement)

                # Фиксируем изменения
                await session.commit()

                log.info(f"📉 Сброшен стрик у {len(habit_ids_to_reset)} пропущенных привычек.")

            else:
                log.debug("Нет привычек для сброса стрика в этом часе.")

        except Exception as exc:
            # Логируем ошибку
            log.error(f"Ошибка при сбросе стриков: {exc}", exc_info=True)

            # Откатываем транзакцию, чтобы сохранить целостность данных
            await session.rollback()
