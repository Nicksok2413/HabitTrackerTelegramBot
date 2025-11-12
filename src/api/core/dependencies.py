"""Зависимости FastAPI для аутентификации и авторизации."""

from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.models import Habit, HabitExecution, User
from src.api.repositories import (
    HabitExecutionRepository,
    HabitRepository,
    UserRepository,
)
from src.api.services import HabitExecutionService, HabitService, UserService

from .config import settings
from .database import get_db_session
from .exceptions import ForbiddenException, UnauthorizedException
from .logging import api_log as log
from .security import verify_and_decode_token

# --- Типизация для инъекции зависимостей ---

# Сессия базы данных
DBSession = Annotated[AsyncSession, Depends(get_db_session)]


# --- Фабрики Репозиториев ---


def get_habit_repository() -> HabitRepository:
    return HabitRepository(Habit)


def get_habit_execution_repository() -> HabitExecutionRepository:
    return HabitExecutionRepository(HabitExecution)


def get_user_repository() -> UserRepository:
    return UserRepository(User)


# Типизация для репозиториев
HabitRepo = Annotated[HabitRepository, Depends(get_habit_repository)]
HabitExecutionRepo = Annotated[HabitExecutionRepository, Depends(get_habit_execution_repository)]
UserRepo = Annotated[UserRepository, Depends(get_user_repository)]


# --- Фабрики Сервисов ---


def get_habit_service(repository: HabitRepo) -> HabitService:
    return HabitService(habit_repository=repository)


# HabitExecutionService зависит от HabitExecutionRepo и HabitRepo
def get_habit_execution_service(repository: HabitExecutionRepo, habit_repository: HabitRepo) -> HabitExecutionService:
    return HabitExecutionService(execution_repository=repository, habit_repository=habit_repository)


def get_user_service(repository: UserRepo) -> UserService:
    return UserService(user_repository=repository)


# Типизация для сервисов
HabitSvc = Annotated[HabitService, Depends(get_habit_service)]
HabitExecutionSvc = Annotated[HabitExecutionService, Depends(get_habit_execution_service)]
UserSvc = Annotated[UserService, Depends(get_user_service)]

# --- Зависимость для получения текущего пользователя ---

# Схема для API ключа бота
api_key_header_auth = APIKeyHeader(name="X-BOT-API-KEY", auto_error=False)


async def verify_bot_api_key(
    api_key: str | None = Security(api_key_header_auth),
) -> bool:
    """
    Проверяет API-ключ, отправляемый ботом.

    Используется для защиты эндпоинтов, к которым обращается только бот
    (например, для получения JWT пользователя).

    Args:
        api_key (str | None): API-ключ из заголовка X-BOT-API-KEY.

    Returns:
        bool: True, если ключ валиден.

    Raises:
        ForbiddenException: Если ключ отсутствует или невалиден.
    """
    if not api_key:
        log.warning("Попытка доступа к защищенному эндпоинту без X-BOT-API-KEY.")
        raise ForbiddenException(message="API ключ бота отсутствует.", error_type="bot_api_key_missing")

    if api_key != settings.API_BOT_SHARED_KEY:
        log.warning("Попытка доступа к защищенному эндпоинту с неверным X-BOT-API-KEY.")
        raise ForbiddenException(message="Неверный API ключ бота.", error_type="bot_api_key_invalid")

    return True


# Создаем зависимость, которую можно будет использовать в роутах для защиты эндпоинтов, предназначенных только для бота.
BotAPIKeyAuth = Annotated[bool, Depends(verify_bot_api_key)]


# --- Зависимость для получения текущего пользователя ---

# Схема для JWT Bearer токена
bearer_schema = HTTPBearer(auto_error=False)


async def get_current_user(
    db_session: DBSession,
    user_repo: UserRepo,
    token_credentials: HTTPAuthorizationCredentials | None = Security(bearer_schema),
) -> User:
    """
    Получает текущего аутентифицированного пользователя на основе JWT токена.

    Args:
        db_session (AsyncSession): Асинхронная сессия базы данных.
        user_repo (UserRepo): Экземпляр репозитория пользователей.
        token_credentials (HTTPAuthorizationCredentials | None): Учетные данные из заголовка Authorization.

    Returns:
        User: Экземпляр модели текущего пользователя.

    Raises:
        UnauthorizedException: Если токен отсутствует, невалиден или пользователь не найден.
    """
    if token_credentials is None or not token_credentials.credentials:
        log.debug("Отсутствует токен авторизации.")
        raise UnauthorizedException(message="Токен авторизации не предоставлен.")

    token = token_credentials.credentials

    # Используем функцию для верификации и декодирования
    # UnauthorizedException будет выброшен из verify_and_decode_token в случае проблем
    token_payload = verify_and_decode_token(token)

    # Получаем пользователя
    user = await user_repo.get_by_id(db_session, obj_id=token_payload.user_id)

    if user is None:
        log.warning(f"Пользователь с ID {token_payload.user_id} из токена не найден в БД.")
        raise UnauthorizedException(message="Пользователь не найден.", error_type="token_user_not_found")

    if not user.is_active:
        log.warning(f"Пользователь ID {user.id} неактивен, доступ запрещен.")
        raise ForbiddenException(message="Пользователь неактивен.", error_type="user_inactive")

    log.debug(f"Аутентифицирован пользователь: ID {user.id}, Telegram ID {user.telegram_id}")
    return user


# --- Типизация для инъекции текущего пользователя ---
CurrentUser = Annotated[User, Depends(get_current_user)]
