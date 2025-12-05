"""
Клиент для взаимодействия с Backend API.

Этот модуль предоставляет высокоуровневый интерфейс для общения с API.
Бот использует этот клиент для всех операций с данными.
"""

from typing import Any

import httpx
from aiogram.types import User as TelegramUser

from src.bot.core.config import settings
from src.core_shared.logging_setup import setup_logger

# Настраиваем логгер
log = setup_logger("ApiClient", log_level_override=settings.LOG_LEVEL)


class APIClientError(Exception):
    """
    Базовое исключение для ошибок, возникающих при работе с API.
    Используется для того, чтобы не пробрасывать httpx exceptions в логику бота.
    """

    pass


class HabitTrackerClient:
    """
    Асинхронный HTTP-клиент для API Трекера Привычек.

    Обеспечивает:
    - Аутентификацию пользователя (получение JWT).
    - Выполнение запросов к защищенным эндпоинтам.
    - Обработку сетевых ошибок.
    """

    def __init__(self):
        """Инициализирует клиент с базовым URL и настройками таймаута."""
        self.base_url = settings.API_V1_URL
        self.shared_key = settings.API_BOT_SHARED_KEY

        # Создаем клиента httpx
        # Используем один клиент на время жизни бота для connection pooling (как синглтон в рамках приложения бота)
        self.http_client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=10.0,  # Таймаут 10 секунд на запрос
        )

    async def close(self):
        """Корректно закрывает сессию HTTP-клиента."""
        await self.http_client.aclose()

    async def _get_user_token(self, tg_user: TelegramUser) -> str:
        """
        Получает JWT токен доступа для конкретного пользователя Telegram.

        Если пользователь заходит впервые, API автоматически создаст его
        в базе данных на основе переданных данных.

        Args:
            tg_user (TelegramUser): Объект пользователя из aiogram.

        Returns:
            str: JWT Access Token.

        Raises:
            APIClientError: Если не удалось получить токен.
        """
        # Формируем данные для входа/регистрации, соответствующие схеме BotLoginRequest
        payload = {
            "telegram_id": tg_user.id,
            "username": tg_user.username,
            "first_name": tg_user.first_name,
            "last_name": tg_user.last_name,
            # Можно передать timezone, если мы её знаем (пока нет)
        }

        # Аутентифицируем запрос от имени Бота с помощью секретного ключа
        headers = {"X-BOT-API-KEY": self.shared_key}

        try:
            response = await self.http_client.post("/auth/token", json=payload, headers=headers)

            # Если статус ответа 4xx или 5xx, выбрасываем исключение
            response.raise_for_status()

            # Парсим JSON и забираем токен
            data = response.json()
            return data["access_token"]

        except httpx.HTTPStatusError as exc:
            log.error(f"API вернул ошибку при получении токена: {exc.response.status_code} - {exc.response.text}")
            raise APIClientError(f"Ошибка авторизации в API: {exc.response.status_code}")
        except httpx.RequestError as exc:
            log.error(f"Сетевая ошибка при запросе токена: {exc}")
            raise APIClientError("API недоступен (сетевая ошибка).")
        except Exception as exc:
            log.error(f"Непредвиденная ошибка в _get_user_token: {exc}", exc_info=True)
            raise APIClientError("Внутренняя ошибка клиента.")

    async def _request(
        self,
        method: str,
        endpoint: str,
        tg_user: TelegramUser,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """
        Внутренний метод для выполнения авторизованного запроса к API.

        1. Получает JWT токен для пользователя.
        2. Добавляет заголовок Authorization.
        3. Выполняет запрос.
        4. Обрабатывает ошибки.

        Args:
            method (str): HTTP метод ("GET", "POST", etc).
            endpoint (str): Путь API (например, "/habits/").
            tg_user (TelegramUser): Пользователь Telegram (для контекста запроса).
            json (dict | None): Тело запроса (для POST/PUT/PATCH).
            params (dict | None): Query параметры (для GET).

        Returns:
            Any: Данные ответа (обычно dict или list).
        """
        try:
            # Получаем токен (в будущем здесь можно добавить кэширование токена в Redis/Memory)
            token = await self._get_user_token(tg_user)

            # Формируем заголовки
            headers = {"Authorization": f"Bearer {token}"}

            # Выполняем запрос
            log.debug(f"API Request: {method} {endpoint} | User: {tg_user.id}")
            response = await self.http_client.request(method, endpoint, json=json, params=params, headers=headers)

            # Если статус ответа 4xx или 5xx, выбрасываем исключение
            response.raise_for_status()

            # Если ответ пустой (204 No Content), возвращаем None
            if response.status_code == 204:
                return None

            return response.json()

        except APIClientError:
            # Если ошибка произошла на этапе получения токена, просто пробрасываем её
            raise
        except httpx.HTTPStatusError as exc:
            log.warning(f"API вернул ошибку {exc.response.status_code} на {method} {endpoint}: {exc.response.text}")
            # Здесь можно добавить разбор ошибок валидации API, если нужно (например 404 или 400)
            raise APIClientError(f"Ошибка запроса к API: {exc.response.status_code}")
        except httpx.RequestError as exc:
            log.error(f"Ошибка сети на {method} {endpoint}: {exc}")
            raise APIClientError("Ошибка сети при обращении к API.")
        except Exception as exc:
            log.error(f"Непредвиденная ошибка API клиента: {exc}", exc_info=True)
            raise APIClientError("Неизвестная ошибка клиента API.")

    # --- Публичные методы API (Бизнес-логика) ---

    async def get_my_habits(
        self, tg_user: TelegramUser, skip: int = 0, limit: int = 100, active_only: bool = False
    ) -> list[dict[str, Any]]:
        """
        Получает список привычек текущего пользователя.

        Использует эндпоинт GET /habits/.

        Args:
            tg_user (TelegramUser): Пользователь Telegram.
            skip (int): Пагинация (пропустить).
            limit (int): Пагинация (лимит).
            active_only (bool): Фильтр по активным привычкам.

        Returns:
            list (dict[str, Any]): список JSON-объектов привычек пользователя.
        """
        params = {
            "skip": skip,
            "limit": limit,
            "active_only": str(active_only).lower(),  # API ожидает 'true'/'false'
        }
        return await self._request("GET", "/habits/", tg_user, params=params)

    async def get_habit_details(self, tg_user: TelegramUser, habit_id: int) -> dict[str, Any]:
        """
        Получает полную информацию о привычке, включая историю выполнений.

        Использует эндпоинт GET /habits/{id}/details.

        Args:
            tg_user (TelegramUser): Пользователь Telegram.
            habit_id (int): ID привычки.

        Returns:
            dict[str, Any]: Словарь с данными привычки (с полем 'executions').
        """
        return await self._request("GET", f"/habits/habits/{habit_id}/details", tg_user)

    async def create_habit(
        self,
        tg_user: TelegramUser,
        name: str,
        time_to_remind: str,
        description: str | None = None,
        target_days: int | None = None,
    ) -> dict[str, Any]:
        """
        Создает новую привычку.

        Использует эндпоинт POST /habits/.

        Args:
            tg_user (TelegramUser): Пользователь Telegram.
            name (str): Название привычки.
            time_to_remind (str): Время напоминания (ЧЧ:MM).
            description (str | None): Описание (опционально).
            target_days (int | None): Целевое кол-во дней (опционально).

        Returns:
            dict[str, Any]: JSON-объект привычки.
        """
        payload = {
            "name": name,
            "time_to_remind": time_to_remind,
            "description": description,
            "target_days": target_days,
        }
        return await self._request("POST", "/habits/", tg_user, json=payload)

    async def change_habit_status(self, tg_user: TelegramUser, habit_id: int, status: str = "done") -> dict[str, Any]:
        """
        Фиксирует выполнение или отмену выполнения привычки на сегодняшний день.

        Использует эндпоинт POST /habits/{id}/executions/.

        Args:
            tg_user (TelegramUser): Пользователь Telegram.
            habit_id (int): ID привычки.
            status (str): Статус выполнения/отмены выполнения ("done", "pending"). По умолчанию "done".

        Returns:
            dict[str, Any]: Словарь с данными объекта созданного выполнения.
        """
        payload = {"status": status}

        return await self._request("POST", f"/habits/{habit_id}/executions/", tg_user, json=payload)

    async def delete_habit(self, tg_user: TelegramUser, habit_id: int) -> None:
        """
        Удаляет привычку.

        Использует эндпоинт DELETE /habits/{id}.

        Args:
            tg_user (TelegramUser): Пользователь Telegram.
            habit_id (int): ID привычки.
        """
        await self._request("DELETE", f"/habits/{habit_id}", tg_user)