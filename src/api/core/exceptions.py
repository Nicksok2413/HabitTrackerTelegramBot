"""
Модуль кастомных исключений и их обработчиков для FastAPI.

Этот модуль определяет базовые классы для HTTP исключений приложения,
а также конкретные исключения и функции-обработчики для них,
чтобы возвращать стандартизированные JSON-ответы клиенту.
"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .logging import api_log as log

# Словарь для маппинга статус-кодов в семантически верные типы ошибок
STATUS_CODE_TO_ERROR_TYPE = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "validation_error",
}


# --- Структура ответа об ошибке ---
class ErrorDetail(BaseModel):
    """
    Модель для детального описания ошибки в ответе.

    Attributes:
        type (str): Тип или код ошибки (например, "resource_not_found").
        msg (str): Человекочитаемое сообщение об ошибке.
        loc (list[str] | None): Опциональный список, указывающий на местоположение ошибки
             (например, ['body', 'field_name'] для ошибки валидации поля).
    """

    type: str = Field(..., description="Тип или код ошибки")
    msg: str = Field(..., description="Человекочитаемое сообщение об ошибке")
    loc: list[str] | None = Field(default=None, description="Локализация ошибки (например, поля в запросе)")


class ErrorResponse(BaseModel):
    """
    Стандартная модель ответа для ошибок.

    Содержит одно поле 'detail', которое является объектом ErrorDetail.
    """

    detail: ErrorDetail


# --- Базовое кастомное HTTP исключение ---
class AppExceptionBase(HTTPException):
    """
    Базовый класс для кастомных HTTP исключений приложения.

    Позволяет задать статус-код и детали ошибки по умолчанию.
    Автоматически формирует `detail` в виде словаря, соответствующего ErrorDetail.

    Attributes:
        status_code (int): HTTP статус-код для этого типа исключения.
        error_type (str): Строковый идентификатор типа ошибки.
        message (str): Сообщение об ошибке по умолчанию.
        loc (list[str] | None): Опциональная локализация ошибки.
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_type: str = "internal_server_error"
    message: str = "Произошла внутренняя ошибка сервера."
    loc: list[str] | None = None

    def __init__(
        self,
        message: str | None = None,
        error_type: str | None = None,
        status_code: int | None = None,
        loc: list[str] | None = None,
        headers: dict[str, str] | None = None,
    ):
        """
        Инициализирует экземпляр AppExceptionBase.

        Args:
            message (str | None): Конкретное сообщение об ошибке. Если None, используется self.message.
            error_type (str | None): Конкретный тип ошибки. Если None, используется self.error_type.
            status_code (int | None): Конкретный HTTP статус-код. Если None, используется self.status_code.
            loc (list[str] | None): Локализация ошибки. Если None, используется self.loc.
            headers (dict[str, str] | None): Дополнительные HTTP заголовки для ответа.
        """
        final_status_code = status_code if status_code is not None else self.status_code
        final_error_type = error_type if error_type is not None else self.error_type
        final_message = message if message is not None else self.message
        final_loc = loc if loc is not None else self.loc

        # Формируем detail как словарь, соответствующий ErrorDetail
        detail_content_dict = ErrorDetail(type=final_error_type, msg=final_message, loc=final_loc).model_dump()

        super().__init__(status_code=final_status_code, detail=detail_content_dict, headers=headers)


# --- Конкретные кастомные исключения ---


class NotFoundException(AppExceptionBase):
    """Исключение для случаев, когда ресурс не найден (404)."""

    status_code = status.HTTP_404_NOT_FOUND
    error_type = "resource_not_found"
    message = "Запрашиваемый ресурс не найден."


class BadRequestException(AppExceptionBase):
    """Исключение для неверных запросов (400)."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_type = "bad_request"
    message = "Неверный запрос."


class ForbiddenException(AppExceptionBase):
    """Исключение для отказа в доступе (403)."""

    status_code = status.HTTP_403_FORBIDDEN
    error_type = "access_forbidden"
    message = "Доступ запрещен."


class UnauthorizedException(AppExceptionBase):
    """
    Исключение для случаев, когда требуется аутентификация (401).

    Обычно используется, когда токен отсутствует или невалиден.
    По умолчанию добавляет заголовок 'WWW-Authenticate: Bearer'.
    """

    status_code = status.HTTP_401_UNAUTHORIZED
    error_type = "authentication_required"
    message = "Требуется аутентификация."

    def __init__(
        self,
        message: str | None = None,
        error_type: str | None = None,
        loc: list[str] | None = None,
        headers: dict[str, str] | None = None,
    ):
        """
        Инициализирует UnauthorizedException.

        Args:
            message (str | None): Сообщение об ошибке.
            error_type (str | None): Тип ошибки.
            loc (list[str] | None): Локализация ошибки.
            headers (dict[str, str] | None): HTTP заголовки. Если не указаны,
                                               добавляется 'WWW-Authenticate: Bearer'.
        """
        # Для 401 часто требуется заголовок WWW-Authenticate
        final_headers = headers or {"WWW-Authenticate": "Bearer"}

        super().__init__(
            message=message,
            error_type=error_type,
            status_code=self.status_code,  # status_code всегда 401 для этого исключения
            loc=loc,
            headers=final_headers,
        )


class ConflictException(AppExceptionBase):
    """Исключение для конфликтов (409), например, попытка создать уже существующий ресурс."""

    status_code = status.HTTP_409_CONFLICT
    error_type = "resource_conflict"
    message = "Конфликт ресурсов. Ресурс с такими данными уже существует."


# --- Обработчики исключений для FastAPI ---


async def app_exception_handler(request: Request, exc: AppExceptionBase) -> JSONResponse:
    """
    Обработчик для кастомных исключений, унаследованных от AppExceptionBase.

    Логирует ошибку и возвращает JSONResponse с деталями ошибки в стандартном формате.
    Детали ошибки берутся напрямую из атрибута `detail` исключения,
    который уже имеет нужную структуру словаря.

    Args:
        request (Request): Объект запроса FastAPI.
        exc (AppExceptionBase): Экземпляр кастомного исключения.

    Returns:
        JSONResponse: Ответ с соответствующим статус-кодом и телом ошибки.
    """
    detail_dict = exc.detail if isinstance(exc.detail, dict) else {"type": "unknown_app_error", "msg": str(exc.detail)}

    log.warning(
        f"AppException: {exc.status_code} {detail_dict.get('type', 'N/A')}: {detail_dict.get('msg', 'N/A')}. Path: {request.url.path}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail_dict},
        headers=getattr(exc, "headers", None),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Обработчик для стандартных HTTPException FastAPI.

    Логирует ошибку и пытается привести ее к стандартному формату ответа ErrorResponse.
    Это полезно для ошибок, генерируемых FastAPI (например, при валидации Pydantic).

    Args:
        request (Request): Объект запроса FastAPI.
        exc (HTTPException): Экземпляр стандартного HTTPException.

    Returns:
        JSONResponse: Ответ с соответствующим статус-кодом и телом ошибки.
    """
    log.warning(f"HTTPException: {exc.status_code} Detail: '{exc.detail}'. Path: {request.url.path}")

    # Получаем тип ошибки из маппинга, с дефолтным значением "http_error"
    error_type = STATUS_CODE_TO_ERROR_TYPE.get(exc.status_code, "http_error")
    error_msg = str(exc.detail)
    error_loc: list[str] | None = None  # По умолчанию loc нет для обычных HTTPException

    # Для ошибок валидации FastAPI (422), exc.detail часто является списком словарей
    # [{ "loc": ["body", "field"], "msg": "...", "type": "..."}]
    if exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY and isinstance(exc.detail, list):
        # Пытаемся извлечь первое сообщение и loc
        if len(exc.detail) > 0 and isinstance(exc.detail[0], dict):
            first_error = exc.detail[0]
            error_msg = first_error.get("msg", error_msg)

            # Преобразуем loc из кортежа/списка чисел/строк в список строк
            raw_loc = first_error.get("loc")

            if raw_loc:
                error_loc = [str(item) for item in raw_loc]

        elif isinstance(exc.detail, str):  # Если это простая строка
            error_msg = exc.detail

    error_detail_obj = ErrorDetail(type=error_type, msg=error_msg, loc=error_loc)
    content = ErrorResponse(detail=error_detail_obj).model_dump()

    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=getattr(exc, "headers", None),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Обработчик для всех остальных (непредвиденных) исключений.

    Логирует ошибку с полным трейсбэком и возвращает стандартизированный
    ответ 500 Internal Server Error.

    Args:
        request (Request): Объект запроса FastAPI.
        exc (Exception): Экземпляр непредвиденного исключения.

    Returns:
        JSONResponse: Ответ 500 Internal Server Error в стандартном формате.
    """
    log.exception(
        f"Unhandled Exception: {exc}. Path: {request.url.path}",
        exc_info=True,  # Всегда логируем полный трейсбек для непредвиденных ошибок
    )
    error_detail = ErrorDetail(
        type="unhandled_server_error",
        msg="На сервере произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.",
        loc=None,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(detail=error_detail).model_dump(),
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Регистрирует обработчики исключений в приложении FastAPI.

    Args:
        app (FastAPI): Экземпляр приложения FastAPI, к которому добавляются обработчики.
    """
    # Обработчик для наших кастомных ошибок (AppExceptionBase и наследники)
    app.add_exception_handler(AppExceptionBase, app_exception_handler)  # type: ignore[arg-type]
    # Обработчик для стандартных HTTPException FastAPI
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    # Обработчик для всех остальных непредвиденных исключений
    app.add_exception_handler(Exception, general_exception_handler)
