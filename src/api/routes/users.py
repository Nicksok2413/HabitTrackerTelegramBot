"""
Эндпоинты для работы с пользователями.
"""

from fastapi import APIRouter, status

from src.api.core.dependencies import CurrentUser, DBSession, UserSvc
from src.api.core.logging import api_log as log
from src.api.models import User
from src.api.schemas import UserSchemaRead, UserSchemaUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserSchemaRead,
    status_code=status.HTTP_200_OK,
    summary="Получение информации о текущем пользователе",
    description="Возвращает данные аутентифицированного пользователя на основе JWT токена.",
)
async def read_users_me(current_user: CurrentUser) -> User:
    """
    Возвращает информацию о текущем аутентифицированном пользователе.

    Зависимость `CurrentUser` обрабатывает аутентификацию и возвращает
    объект `User` из базы данных.
    """
    log.info(f"Запрос информации о текущем пользователе: ID {current_user.id}")
    return current_user


@router.patch(
    "/me",
    response_model=UserSchemaRead,
    status_code=status.HTTP_200_OK,
    summary="Обновление информации о текущем пользователе",
    description="Позволяет текущему аутентифицированному пользователю обновить свои данные.",
)
async def update_user_me(
    db_session: DBSession,
    current_user: CurrentUser,
    user_service: UserSvc,
    user_update_data: UserSchemaUpdate,
) -> User:
    """
    Обновляет данные текущего аутентифицированного пользователя.
    Использует `telegram_id` из `current_user` для поиска и обновления.
    """
    log.info(f"Обновление данных для пользователя ID: {current_user.id} (Telegram ID: {current_user.telegram_id})")

    updated_user = await user_service.update_user_by_telegram_id(
        db_session,
        telegram_id=current_user.telegram_id,  # Обновляем по telegram_id текущего пользователя
        user_update_data=user_update_data,
    )

    log.info(f"Данные пользователя ID {current_user.id} успешно обновлены.")
    return updated_user
