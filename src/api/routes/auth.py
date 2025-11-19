"""
Эндпоинты для аутентификации.

Предоставляет маршрут для получения JWT токена пользователя на основе Telegram ID.
Этот эндпоинт предназначен для вызова ботом.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.core.dependencies import (
    DBSession,
    UserSvc,
    verify_bot_api_key,
)
from src.api.core.logging import api_log as log
from src.api.core.security import create_access_token
from src.api.schemas.auth_schema import BotLoginRequest, Token
from src.api.schemas.user_schema import UserSchemaCreate

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
    dependencies=[Depends(verify_bot_api_key)],  # Защищаем все эндпоинты в этом роутере ключом бота
)


@router.post(
    "/token",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Получение JWT токена для пользователя",
    description=(
        "Бот отправляет данные пользователя Telegram (ID, username и т.д.). "
        "Сервис находит или создает пользователя в БД и возвращает JWT токен доступа."
    ),
)
async def login_for_access_token(
    request_data: BotLoginRequest,
    db_session: DBSession,
    user_service: UserSvc,
) -> Token:
    """
    Обрабатывает запрос от бота на получение JWT токена.

    1.  Принимает данные пользователя Telegram.
    2.  Использует `UserService` для получения или создания пользователя.
    3.  Создает JWT токен на основе `user.id`.
    4.  Возвращает токен.

    Этот эндпоинт защищен API-ключом бота.
    """
    log.info(f"Запрос на токен для Telegram ID: {request_data.telegram_id}, Username: {request_data.username or 'N/A'}")

    # Подготовка данных для создания/обновления пользователя
    user_create_schema = UserSchemaCreate(
        telegram_id=request_data.telegram_id,
        username=request_data.username,
        first_name=request_data.first_name,
        last_name=request_data.last_name,
        # is_active и is_bot_blocked будут по умолчанию из модели User
    )

    # Получаем или создаем пользователя
    user = await user_service.get_or_create_user(db_session, user_in=user_create_schema)

    if not user.is_active:
        log.warning(f"Попытка входа неактивного пользователя: Telegram ID {user.telegram_id}")
        # Вместо ForbiddenException, можно использовать HTTPException, т.к. это специфичная логика входа
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь неактивен и не может войти.",
        )

    # Создаем JWT токен
    access_token = create_access_token(data={"user_id": user.id})

    log.info(f"Токен успешно создан для пользователя ID: {user.id} (Telegram ID: {user.telegram_id})")
    # Добавляем noqa: S106, чтобы заглушить ложное срабатывание
    return Token(access_token=access_token, token_type="bearer")  # noqa: S106
