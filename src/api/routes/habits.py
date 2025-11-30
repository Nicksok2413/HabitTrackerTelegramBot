"""
Эндпоинты для управления привычками (Habits).
"""

from typing import Sequence

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
    Создает новую привычку.

    - Принимает данные привычки в теле запроса.
    - Использует `HabitService` для создания привычки, связывая ее с `current_user`.
    - `target_days` может быть передан или будет взят из настроек по умолчанию.
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
    skip: int = Query(0, ge=0, description="Количество записей для пропуска (пагинация)"),
    limit: int = Query(100, ge=1, le=200, description="Максимальное количество записей (пагинация)"),
    # Параметр для фильтрации активных привычек
    active_only: bool = Query(False, description="Вернуть только активные привычки"),
) -> Sequence[Habit]:
    """
    Получает список привычек для текущего пользователя.

    - Поддерживает пагинацию (`skip`, `limit`).
    - Позволяет фильтровать только активные привычки (`active_only`).
    """

    return await habit_service.get_habits_for_user(
        db_session,
        current_user=current_user,
        skip=skip,
        limit=limit,
        active_only=active_only,
    )


@router.get(
    "/{habit_id}",
    response_model=HabitSchemaRead,
    status_code=status.HTTP_200_OK,
    summary="Получение конкретной привычки по ID",
    description="Возвращает привычку, если она принадлежит пользователю.",
)
async def get_habit(
    db_session: DBSession,
    current_user: CurrentUser,
    habit_service: HabitSvc,
    habit_id: int,
) -> Habit:
    """
    Получает детали одной привычки по ее ID.

    Проверяет, что привычка принадлежит `current_user`.
    """

    return await habit_service.get_habit_by_id_for_user(db_session, habit_id=habit_id, current_user=current_user)


@router.get(
    "/habits/{habit_id}/details",
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
    Получает детали одной привычки вместе с ее выполнениями по ее ID.

    Проверяет, что привычка принадлежит `current_user`.
    """

    return await habit_service.get_habit_with_executions_for_user(
        db_session, habit_id=habit_id, current_user=current_user
    )


@router.put(
    "/{habit_id}",
    response_model=HabitSchemaRead,
    status_code=status.HTTP_200_OK,
    summary="Обновление привычки по ID",
    description="Обновляет данные привычки, если она принадлежит пользователю.",
)
async def update_habit(
    db_session: DBSession,
    current_user: CurrentUser,
    habit_service: HabitSvc,
    habit_id: int,
    habit_in: HabitSchemaUpdate,
) -> Habit:
    """
    Обновляет существующую привычку.

    - Принимает ID привычки и данные для обновления.
    - Проверяет принадлежность привычки `current_user`.
    - Обновляет только переданные поля (частичное обновление).
    """

    return await habit_service.update_habit_for_user(
        db_session,
        habit_id=habit_id,
        habit_in=habit_in,
        current_user=current_user,
    )


@router.delete(
    "/{habit_id}",
    status_code=status.HTTP_204_NO_CONTENT,  # Успешное удаление обычно возвращает 204
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
    Удаляет привычку.

    - Принимает ID привычки.
    - Проверяет принадлежность привычки `current_user`.
    """

    await habit_service.remove_habit_for_user(db_session, habit_id=habit_id, current_user=current_user)

    return None  # Для статуса 204 тело ответа должно быть пустым
