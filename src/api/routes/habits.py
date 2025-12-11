"""
Эндпоинты для управления привычками (Habits).
"""

from typing import Annotated, Sequence

from fastapi import APIRouter, Query, status

from src.api.core.dependencies import CurrentUser, DBSession, HabitSvc
from src.api.models import Habit
from src.api.schemas import (
    HabitSchemaCreate,
    HabitSchemaRead,
    HabitSchemaReadWithExecutions,
    HabitSchemaUpdate,
)

router = APIRouter(prefix="/habits", tags=["Habits"])


@router.post(
    "/",
    response_model=HabitSchemaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создание новой привычки",
    description="Создает новую привычку для пользователя.",
)
async def create_habit(
    db_session: DBSession,
    current_user: CurrentUser,
    habit_service: HabitSvc,
    habit_in: HabitSchemaCreate,
) -> Habit:
    """
    Создает новую привычку для текущего пользователя.

    Args:
        db_session: Асинхронная сессия базы данных.
        current_user: Аутентифицированный пользователь.
        habit_service: Сервис для работы с привычками.
        habit_in: Данные для создания привычки (название, описание, цель и т.д.).

    Returns:
        Habit: Созданный объект привычки.
    """

    return await habit_service.create_habit_for_user(db_session, habit_in=habit_in, current_user=current_user)


@router.get(
    "/",
    response_model=Sequence[HabitSchemaRead],
    status_code=status.HTTP_200_OK,
    summary="Получение списка привычек пользователя",
    description="Возвращает список всех привычек (или только активных) для пользователя.",
)
async def get_habits(
    db_session: DBSession,
    current_user: CurrentUser,
    habit_service: HabitSvc,
    skip: Annotated[int, Query(ge=0, description="Количество записей для пропуска (пагинация)")] = 0,
    limit: Annotated[int, Query(ge=1, le=200, description="Максимальное количество записей (пагинация)")] = 100,
    active_only: Annotated[
        bool,
        Query(description="Вернуть только активные привычки"),
    ] = True,
) -> Sequence[HabitSchemaRead]:
    """
    Получает список привычек текущего пользователя с поддержкой пагинации.

    В ответе для каждой привычки вычисляется поле `is_done_today`.

    Args:
        db_session: Асинхронная сессия базы данных.
        current_user: Аутентифицированный пользователь.
        habit_service: Сервис для работы с привычками.
        skip: Количество записей для пропуска.
        limit: Максимальное количество записей.
        active_only: Фильтр: если True, возвращает только активные (не архивные) привычки.

    Returns:
        Sequence[HabitSchemaRead]: Список привычек пользователя.
    """

    return await habit_service.get_habits_for_user(
        db_session,
        current_user=current_user,
        skip=skip,
        limit=limit,
        active_only=active_only,
    )


@router.get(
    "/{habit_id}/details",
    response_model=HabitSchemaReadWithExecutions,
    status_code=status.HTTP_200_OK,
    summary="Получение конкретной привычки по ID вместе с ее выполнениями",
    description="Возвращает детали привычки (включая выполнения), если она принадлежит пользователю.",
)
async def get_habit_details(
    db_session: DBSession,
    current_user: CurrentUser,
    habit_service: HabitSvc,
    habit_id: int,
) -> Habit:
    """
    Получает полную информацию о привычке, включая историю выполнений.

    Проверяет, принадлежит ли привычка текущему пользователю.

    Args:
        db_session: Асинхронная сессия базы данных.
        current_user: Аутентифицированный пользователь.
        habit_service: Сервис для работы с привычками.
        habit_id: ID запрашиваемой привычки.

    Returns:
        Habit: Объект привычки с подгруженным полем `executions`.

    Raises:
        NotFoundException: Если привычка не найдена.
        ForbiddenException: Если привычка принадлежит другому пользователю.
    """

    return await habit_service.get_habit_with_executions_for_user(
        db_session, habit_id=habit_id, current_user=current_user
    )


@router.patch(
    "/{habit_id}",
    response_model=HabitSchemaRead,
    status_code=status.HTTP_200_OK,
    summary="Обновление привычки по ID",
    description="Частично обновляет данные привычки (PATCH), если она принадлежит пользователю.",
)
async def update_habit(
    db_session: DBSession,
    current_user: CurrentUser,
    habit_service: HabitSvc,
    habit_id: int,
    habit_in: HabitSchemaUpdate,
) -> Habit:
    """
    Частично обновляет данные существующей привычки.

    Args:
        db_session: Асинхронная сессия базы данных.
        current_user: Аутентифицированный пользователь.
        habit_service: Сервис для работы с привычками.
        habit_id: ID обновляемой привычки.
        habit_in: Объект с обновляемыми полями (все поля опциональны).

    Returns:
        Habit: Обновленный объект привычки.

    Raises:
        NotFoundException: Если привычка не найдена.
        ForbiddenException: Если привычка принадлежит другому пользователю.
    """

    return await habit_service.update_habit_for_user(
        db_session,
        habit_id=habit_id,
        habit_in=habit_in,
        current_user=current_user,
    )


@router.delete(
    "/{habit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удаление привычки по ID",
    description="Удаляет привычку, если она принадлежит пользователю.",
)
async def delete_habit(
    db_session: DBSession,
    current_user: CurrentUser,
    habit_service: HabitSvc,
    habit_id: int,
) -> None:  # Возвращаем None, так как статус 204 No Content
    """
    Удаляет привычку и всю связанную с ней историю выполнений.

    Args:
        db_session: Асинхронная сессия базы данных.
        current_user: Аутентифицированный пользователь.
        habit_service: Сервис для работы с привычками.
        habit_id: ID удаляемой привычки.

    Raises:
        NotFoundException: Если привычка не найдена.
        ForbiddenException: Если привычка принадлежит другому пользователю.
    """

    await habit_service.remove_habit_for_user(db_session, habit_id=habit_id, current_user=current_user)

    return None  # Для статуса 204 тело ответа должно быть пустым
