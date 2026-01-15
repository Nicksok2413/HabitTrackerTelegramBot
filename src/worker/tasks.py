"""
Фоновые задачи Celery.

Содержит логику отправки сообщений в Telegram и служебные задачи.
"""

from typing import Any

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from asgiref.sync import async_to_sync
from celery.utils.log import get_task_logger
from redis import Redis

from src.api.core.config import settings
from src.api.core.database import db
from src.api.models import User
from src.api.repositories import UserRepository
from src.worker.celery_app import celery_app

# Специальный логгер для Celery задач
logger = get_task_logger(__name__)

# Клиент Redis для механизма блокировок (Idempotency Lock)
redis_client = Redis.from_url(settings.REDIS_URL)


async def _send_telegram_message_async(chat_id: int, text: str) -> None:
    """
    Асинхронная функция отправки сообщения.
    Создает локальный экземпляр бота, отправляет сообщение и закрывает сессию.

    Args:
        chat_id (int): ID чата/пользователя.
        text (str): Текст сообщения (HTML).
    """
    # Создаем бота внутри задачи
    # В Celery каждый процесс живет долго, но задачи изолированы
    # Менеджер контекста автоматически закроет сессию aiohttp
    async with Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)) as bot:
        await bot.send_message(chat_id=chat_id, text=text)


async def _block_user_async(telegram_id: int) -> None:
    """
    Асинхронная функция изменения пользователя в БД.
    Меняет значение поля "is_bot_blocked" на True (пользователь заблокировал бота).

    Используется как fallback, когда Telegram API возвращает ошибку Forbidden.
    Поскольку Celery-воркер работает отдельно от FastAPI, здесь необходимо
    явно управлять жизненным циклом подключения к БД.

    Args:
        telegram_id (int): Telegram ID пользователя.
    """
    # Явно устанавливаем соединение с БД
    # В FastAPI это делает lifespan, но в Celery мы должны сделать это сами
    # Это создаст engine и session_factory
    await db.connect()

    try:
        # Открываем сессию
        async with db.session() as session:
            user_repo = UserRepository(User)

            # Ищем пользователя
            user = await user_repo.get_by_telegram_id(session, telegram_id=telegram_id)

            if user:
                # Обновляем флаг is_bot_blocked пользователя, чтобы больше не пытаться отправлять ему уведомления
                await user_repo.update(session, db_obj=user, obj_in={"is_bot_blocked": True})

                # Фиксируем изменение пользователя
                await session.commit()
                logger.info(f"Пользователю (telegram_id: {telegram_id}) изменен флаг `is_bot_blocked=True`.")

            else:
                logger.warning(f"Пользователь (telegram_id: {telegram_id}) не найден в БД.")

    except Exception as exc:
        # Логируем ошибку, но не роняем воркер
        logger.error(f"Ошибка при изменении флага `is_bot_blocked=True` пользователя {telegram_id}: {exc}")

    finally:
        # Закрываем соединение
        await db.disconnect()


@celery_app.task(
    bind=True,  # Дает доступ к экземпляру задачи (self)
    rate_limit="25/s",  # Rate Limit на уровне задачи (Telegram разрешает ~30)
    max_retries=3,  # Количество попыток при ошибке
    default_retry_delay=5,  # Пауза между попытками
    acks_late=True,  # Подтверждать задачу только после выполнения
)
def send_habit_notification_task(self: Any, chat_id: int, habit_name: str, idempotency_key: str) -> str:
    """
    Задача отправки уведомления о привычке.

    Реализует паттерн идемпотентности через Redis: гарантирует, что
    одно и то же уведомление не уйдет дважды даже при сбоях воркера.

    Args:
        chat_id: Telegram ID пользователя.
        habit_name: Название привычки.
        idempotency_key: Уникальный ключ (habit_id + timestamp).
    """
    # Пытаемся установить ключ в Redis (идемпотентность)
    lock_acquired = redis_client.set(
        f"lock:notification:{idempotency_key}",
        "sent",
        nx=True,  # Not Exists - запишет только если ключа нет
        ex=86400,  # TTL - ключ протухнет через 24 часа (для автоочистки)
    )

    if not lock_acquired:
        logger.info(f"Повторное уведомление пропущено. Ключ: {idempotency_key}")
        return "Пропущено (дубликат)"

    # Формируем текст уведомления
    notification = f"⏰ <b>Напоминание!</b>\nПора выполнить привычку: <b>{habit_name}</b>"

    try:
        # Запускаем асинхронный код в синхронном окружении Celery
        async_to_sync(_send_telegram_message_async)(chat_id=chat_id, text=notification)
        logger.info(f"✅ Напоминание отправлено пользователю (telegram_id: {chat_id}, habit_name: {habit_name})")
        return "Отправлено"

    except TelegramRetryAfter as exc:
        # Если Telegram просит подождать (429 Too Many Requests)
        logger.warning(f"Ограничение количества запросов в Telegram. Ожидание {exc.retry_after} сек.")
        # Ретраим задачу через указанное время
        raise self.retry(exc=exc, countdown=exc.retry_after)

    except TelegramForbiddenError:
        # Пользователь заблокировал бота
        logger.warning(f"🚫 Пользователь (telegram_id: {chat_id}) заблокировал бота.")
        # Запускаем задачу для обновления "is_bot_blocked" пользователя в БД
        async_to_sync(_block_user_async)(telegram_id=chat_id)
        return "Пользователь заблокировал бота"

    except TelegramBadRequest as exc:
        # Ошибки валидации со стороны Telegram
        logger.error(f"❌ Ошибка Telegram API при отправке пользователю (telegram_id: {chat_id}): {exc}")
        return "Ошибка Telegram API"

    except Exception as exc:
        logger.error(f"❌ Непредвиденная ошибка при отправке напоминания пользователю (telegram_id: {chat_id}): {exc}")
        # В случае неизвестной ошибки, не удаляем лок, чтобы не спамить пользователя
        raise self.retry(exc=exc)
