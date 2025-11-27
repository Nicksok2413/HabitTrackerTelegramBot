"""
Эндпоинты для управления выполнениями привычек (HabitExecutions).
"""

from datetime import date
from typing import Sequence

from fastapi import APIRouter, HTTPException, Path, Query, status

from src.api.core.dependencies import CurrentUser, DBSession, HabitExecutionSvc
from src.api.core.exceptions import ForbiddenException
from src.api.core.logging import api_log as log
from src.api.models import HabitExecution, HabitExecutionStatus
from src.api.schemas.habit_execution_schema import (
    HabitExecutionSchemaCreate,
    HabitExecutionSchemaRead,
)

router = APIRouter(
    prefix="/habits/{habit_id}/executions",  # Вложенный ресурс
    tags=["Habit Executions"],
)

# Параметр пути для всех эндпоинтов в этом роутере
HabitIDPath = Path(..., title="ID Привычки", description="Идентификатор родительской привычки", gt=0)


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
    Фиксирует выполнение привычки на *сегодняшний день*.

    - `habit_id` берется из пути.
    - Статус выполнения (`DONE`, `NOT_DONE`) передается в теле.
    - Сервис проверяет права доступа и активность привычки.
    - Обновляет или создает запись `HabitExecution` на сегодня.
    - Обновляет `current_streak` и `max_streak` у привычки.
    """
    log.info(
        f"Пользователь ID: {current_user.id} фиксирует выполнение привычки ID: {habit_id} "
        f"на сегодня со статусом: {execution_in.status.value}"
    )
    # execution_date_override не передаем, сервис использует date.today() по умолчанию
    return await execution_service.record_habit_execution(
        db_session,
        habit_id=habit_id,
        execution_in=execution_in,
        current_user=current_user,
    )


@router.post(
    "/{execution_date_str}",
    response_model=HabitExecutionSchemaRead,
    status_code=status.HTTP_201_CREATED,  # Может быть 200 если обновляем
    summary="Запись выполнения привычки на указанную дату",
    description=(
        "Создает или обновляет запись о выполнении привычки для текущего пользователя "
        "на указанную дату (формат YYYY-MM-DD). Стрики обновляются только для сегодняшней даты."
    ),
    responses={
        status.HTTP_200_OK: {"description": "Запись о выполнении успешно обновлена"},
        status.HTTP_201_CREATED: {"description": "Запись о выполнении успешно создана"},
    },
)
async def record_habit_execution_on_date(
    db_session: DBSession,
    current_user: CurrentUser,
    execution_service: HabitExecutionSvc,
    execution_in: HabitExecutionSchemaCreate,
    habit_id: int = HabitIDPath,
    execution_date_str: str = Path(
        ...,
        title="Дата выполнения",
        description="Дата в формате YYYY-MM-DD",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
) -> HabitExecution:
    """
    Фиксирует выполнение привычки на *указанную дату*.

    - `habit_id` и `execution_date_str` (YYYY-MM-DD) берутся из пути.
    - Статус выполнения передается в теле.
    - Сервис проверяет права доступа и активность привычки.
    - Обновляет или создает запись `HabitExecution` на указанную дату.
    - Стрики привычки обновляются только если `execution_date_str` это сегодня.
    """
    try:
        execution_date = date.fromisoformat(execution_date_str)
    except ValueError:
        log.warning(f"Неверный формат даты: {execution_date_str}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат даты. Используйте YYYY-MM-DD.",
        ) from None

    log.info(
        f"Пользователь ID: {current_user.id} фиксирует выполнение привычки ID: {habit_id} "
        f"на дату: {execution_date} со статусом: {execution_in.status.value}"
    )

    # Определяем, была ли запись создана или обновлена для корректного статус-кода (хотя FastAPI это не умеет динамически)
    # Для простоты, можно всегда возвращать 200 или 201, или использовать response_class=JSONResponse и выставлять статус-код вручную.
    # Но Pydantic модели в response_model не позволяют легко менять статус-код.
    # Для MVP оставим как есть, FastAPI вернет 201 (из декоратора).
    return await execution_service.record_habit_execution(
        db_session,
        habit_id=habit_id,
        execution_in=execution_in,
        current_user=current_user,
        execution_date_override=execution_date,
    )


@router.get(
    "/",
    response_model=list[HabitExecutionSchemaRead],
    status_code=status.HTTP_200_OK,
    summary="Получение списка выполнений для привычки",
    description="Возвращает историю выполнений для указанной привычки.",
)
async def read_habit_executions(
    db_session: DBSession,
    current_user: CurrentUser,
    execution_service: HabitExecutionSvc,
    start_date: date | None = Query(None, description="Начальная дата для фильтрации (ГГГГ-ММ-ДД)"),
    end_date: date | None = Query(None, description="Конечная дата для фильтрации (ГГГГ-ММ-ДД)"),
    status_filter: str | None = Query(None, alias="status", description="Фильтр по статусу выполнения"),
    skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
    limit: int = Query(100, ge=1, le=200, description="Максимальное количество записей"),
    habit_id: int = HabitIDPath,
) -> Sequence[HabitExecution]:
    """
    Получает список всех выполнений для конкретной привычки.

    - Проверяет права доступа к родительской привычке.
    - Поддерживает фильтрацию по дате (`start_date`, `end_date`) и статусу.
    - Поддерживает пагинацию (`skip`, `limit`).
    """
    log.info(f"Пользователь ID: {current_user.id} запрашивает выполнения для привычки ID: {habit_id}")

    execution_status_enum = None
    if status_filter:
        try:
            execution_status_enum = HabitExecutionStatus(status_filter.lower())
        except ValueError:
            log.warning(f"Неверный статус фильтра для выполнений: {status_filter}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неверный статус фильтра: {status_filter}",
            ) from None

    return await execution_service.get_executions_for_habit_by_user(
        db_session,
        habit_id=habit_id,
        current_user=current_user,
        status=execution_status_enum,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{execution_id}",
    response_model=HabitExecutionSchemaRead,
    status_code=status.HTTP_200_OK,
    summary="Получение деталей конкретного выполнения",
    description="Возвращает детали одной записи о выполнении привычки.",
)
async def read_habit_execution_details(
    db_session: DBSession,
    current_user: CurrentUser,
    execution_service: HabitExecutionSvc,
    execution_id: int = Path(..., title="ID Выполнения", gt=0),
    habit_id: int = HabitIDPath,  # Для проверки контекста, хотя execution_id уникален
) -> HabitExecution:
    """
    Получает детали конкретного выполнения привычки.

    - Проверяет, что `execution_id` относится к `habit_id` (через сервис)
      и что пользователь имеет доступ.
    """
    log.info(
        f"Пользователь ID: {current_user.id} запрашивает детали выполнения ID: {execution_id} для привычки ID: {habit_id}"
    )
    # Сервис get_execution_details должен проверить, что execution принадлежит habit_id и current_user
    execution = await execution_service.get_execution_details(
        db_session, execution_id=execution_id, current_user=current_user
    )
    # Дополнительная проверка, что выполнение относится к указанной в пути привычке
    if execution.habit_id != habit_id:
        log.warning(f"Выполнение ID {execution_id} не принадлежит привычке ID {habit_id}.")
        raise ForbiddenException(message="Выполнение не относится к указанной привычке.")  # Или NotFound
    return execution


# @router.put(
#     "/{execution_id}",
#     response_model=HabitExecutionSchemaRead,
#     status_code=status.HTTP_200_OK,
#     summary="Обновление статуса выполнения привычки",
#     description="Позволяет изменить статус существующей записи о выполнении (например, с PENDING на DONE).",
# )
# async def update_habit_execution_status(
#     db_session: DBSession,
#     current_user: CurrentUser,
#     execution_service: HabitExecutionSvc,
#     status_in: HabitExecutionSchemaUpdate,
#     execution_id: int = Path(..., title="ID Выполнения", gt=0),
#     habit_id: int = HabitIDPath,  # Для проверки контекста
# ) -> HabitExecution:
#     """
#     Обновляет статус конкретного выполнения привычки.
#
#     - Проверяет права доступа и принадлежность выполнения к привычке и пользователю.
#     - Стрики обновляются, если изменяется выполнение за сегодняшний день.
#     """
#     log.info(
#         f"Пользователь ID: {current_user.id} обновляет статус выполнения ID: {execution_id} "
#         f"(привычка ID: {habit_id}) на {status_in.status.value}"
#     )
#     # Сначала получаем выполнение, чтобы убедиться, что оно принадлежит нужной привычке
#     # Это будет сделано внутри `get_execution_details`, который вызывается в `update_execution_status` сервиса
#     # Но для явной проверки на уровне роутера можно сделать так:
#     temp_execution = await execution_service.get_execution_details(
#         db_session, execution_id=execution_id, current_user=current_user
#     )
#     if temp_execution.habit_id != habit_id:
#         log.warning(f"Попытка обновить выполнение ID {execution_id}, которое не принадлежит привычке ID {habit_id}.")
#         raise ForbiddenException(message="Выполнение не относится к указанной привычке.")
#
#     return await execution_service.update_execution_status(
#         db_session,
#         execution_id=execution_id,
#         status_in=status_in,
#         current_user=current_user,
#     )
