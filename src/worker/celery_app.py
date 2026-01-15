"""
Инициализация приложения Celery.

Определяет настройки брокера, сериализации и лимитов.
"""

from celery import Celery
from src.api.core.config import settings

# Создаем экземпляр приложения
celery_app = Celery(
    "habit_tracker_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Обновляем конфигурацию
celery_app.conf.update(
    # Формат передачи данных
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Часовой пояс
    timezone="UTC",
    enable_utc=True,
    # Обработка потери соединения с брокером при старте
    broker_connection_retry_on_startup=True,
    # Глобальный Rate Limit
    task_default_rate_limit="30/s",
)

# Автоматически находим и регистрируем задачи в модуле tasks
celery_app.autodiscover_tasks(["src.worker.tasks"])
