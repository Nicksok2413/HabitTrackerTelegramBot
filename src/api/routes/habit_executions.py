"""
Эндпоинты для управления выполнениями привычек (HabitExecutions).
"""

from fastapi import APIRouter, Path, status

from src.api.core.dependencies import CurrentUser, DBSession, HabitExecutionSvc
from src.api.models import HabitExecution
from src.api.schemas.habit_execution_schema import (
    HabitExecutionSchemaCreate,
    HabitExecutionSchemaRead,
)

router = APIRouter(
    prefix="/habits/{habit_id}/executions",  # Вложенный ресурс
    tags=["Habit Executions"],
)

# Параметр пути для эндпоинтов в этом роутере
HabitIDPath = Path(..., title="ID привычки", description="Идентификатор родительской привычки", gt=0)


@router.post(
    "/",
    response_model=HabitExecutionSchemaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Запись выполнения привычки на сегодня",
    description=(
        "Создает или обновляет запись о выполнении привычки для текущего пользователя "
        "на сегодняшнюю дату. Обновляет стрики привычки."
    ),
)
async def record_today_habit_execution(
    db_session: DBSession,
    current_user: CurrentUser,
    execution_service: HabitExecutionSvc,
    execution_in: HabitExecutionSchemaCreate,
    habit_id: int = HabitIDPath,
) -> HabitExecution:
    """
    Фиксирует выполнение или изменение статуса привычки на *текущий день*.

    Если запись за сегодня уже есть — обновляет статус.
    Если записи нет — создает новую.
    Автоматически пересчитывает серию выполнений (streaks).

    Args:
        db_session: Асинхронная сессия базы данных.
        current_user: Аутентифицированный пользователь.
        execution_service: Сервис выполнений.
        execution_in: Данные для записи (статус DONE/NOT_DONE/PENDING).
        habit_id: ID привычки (из URL).

    Returns:
        HabitExecution: Созданная или обновленная запись выполнения.

    Raises:
        NotFoundException: Если привычка не найдена.
        ForbiddenException: Если нет прав доступа.
        BadRequestException: Если привычка не активна.
    """

    return await execution_service.record_habit_execution(
        db_session,
        habit_id=habit_id,
        execution_in=execution_in,
        current_user=current_user,
    )
