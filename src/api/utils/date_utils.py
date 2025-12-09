"""Модуль вспомогательных утилит для работы с датами/таймзонами."""

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.api.core.logging import api_log as log

if TYPE_CHECKING:  # pragma: no cover
    from src.api.models import User


def get_today_date_for_user(user: "User") -> date:
    """
    Вычисляет текущую дату ("сегодня") с учетом часового пояса пользователя.

    Если часовой пояс пользователя некорректен, используется UTC.

    Args:
        user (User): habit (Habit): Экземпляр пользователя.

    Returns:
        date: Объект даты (YYYY-MM-DD), соответствующий "сегодня" для пользователя.
    """
    # Получаем текущее абсолютное время в UTC
    utc_now = datetime.now(timezone.utc)

    # Получаем строку часового пояса пользователя
    # Если поле пустое или None, используем UTC как дефолт
    user_timezone_str = user.timezone or "UTC"

    try:
        # Пытаемся создать объект информации о часовом поясе (IANA time zone)
        user_timezone = ZoneInfo(user_timezone_str)

    except ZoneInfoNotFoundError:
        # Если в записана несуществующая таймзона (например, опечатка),
        # не роняем запрос, а логируем проблему и откатываемся к UTC
        log.warning(
            f"Некорректный часовой пояс '{user_timezone_str}' у пользователя ID {user.id}. "
            "Используется UTC по умолчанию."
        )
        user_timezone = ZoneInfo("UTC")

    except Exception as exc:
        # Защита от любых других непредвиденных ошибок
        log.error(
            f"Непредвиденная ошибка при определении времени для пользователя ID {user.id}: {exc}", exc_info=True
        )
        user_timezone = ZoneInfo("UTC")

    # Конвертируем UTC время во время пользователя
    # Метод astimezone() создает новый объект datetime с тем же абсолютным моментом времени,
    # но с атрибутами year, month, day, hour, скорректированными под смещение таймзоны
    user_now = utc_now.astimezone(user_timezone)

    # Извлекаем и возвращаем дату "сегодня" для пользователя
    return user_now.date()