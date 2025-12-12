"""
Утилиты для обеспечения безопасности приложения, включая работу с JWT.
Используется библиотека PyJWT.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError, PyJWTError
from pydantic import ValidationError

from src.api.core.config import settings
from src.api.core.exceptions import UnauthorizedException
from src.api.core.logging import api_log as log
from src.api.schemas.auth_schema import TokenPayload


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """
    Создает JWT токен доступа.

    Args:
        data (dict): Данные для кодирования в payload токена (например, {'user_id': user.id}).
        expires_delta (timedelta | None): Время жизни токена. Если None, используется
                                          значение из настроек или дефолтное.

    Returns:
        str: Сгенерированный JWT токен.
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    # 'exp' должно быть Unix timestamp (int)
    to_encode.update({"exp": int(expire.timestamp())})

    log.debug(f"Создание JWT токена с payload: {to_encode} и временем истечения: {expire.isoformat()}")

    try:
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    except Exception as exc:
        log.error(f"Ошибка при кодировании JWT: {exc}", exc_info=True)
        raise RuntimeError("Не удалось создать токен доступа.") from exc

    return encoded_jwt


def verify_and_decode_token(token: str) -> TokenPayload:
    """
    Проверяет и декодирует JWT токен, возвращая его payload.

    Args:
        token (str): JWT токен для проверки.

    Returns:
        TokenPayload: Pydantic модель с данными из payload токена.

    Raises:
        UnauthorizedException: Если токен невалиден, истек или payload некорректен.
    """
    try:
        # PyJWT автоматически проверяет подпись и срок действия (exp)
        payload_dict = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        # Валидируем payload с помощью Pydantic схемы
        token_payload = TokenPayload(**payload_dict)

        # Проверяем, что user_id есть в payload
        if token_payload.user_id is None:
            log.warning("В payload токена отсутствует user_id.")
            raise UnauthorizedException(
                message="Отсутствует идентификатор пользователя в токене.",
                error_type="token_user_id_missing",
            )

    except ExpiredSignatureError:
        log.warning("Срок действия JWT токена истек.")
        raise UnauthorizedException(message="Срок действия токена истек.", error_type="token_expired") from None

    except InvalidTokenError as exc:
        # PyJWT выбрасывает InvalidTokenError для неверных подписей, форматов и т.д.
        log.warning(f"Невалидный токен: {exc}")
        raise UnauthorizedException(message="Невалидный токен.", error_type="invalid_token") from exc

    except PyJWTError as exc:
        # Базовый класс ошибок PyJWT
        log.warning(f"Ошибка обработки JWT: {exc}")
        raise UnauthorizedException(message="Ошибка авторизации.", error_type="jwt_error") from exc

    except ValidationError as exc:
        # Ошибка валидации Pydantic для TokenPayload
        log.warning(f"Ошибка валидации payload токена: {exc.errors()}")
        raise UnauthorizedException(
            message="Некорректные данные в токене.", error_type="invalid_token_payload"
        ) from exc

    except Exception as exc:
        # Непредвиденная ошибка при обработке токена
        log.error(f"Непредвиденная ошибка при обработке токена: {exc}", exc_info=True)
        raise UnauthorizedException(message="Ошибка обработки токена.", error_type="token_processing_error") from exc

    log.debug(f"Токен успешно верифицирован. Payload: {token_payload.model_dump_json()}")

    return token_payload
