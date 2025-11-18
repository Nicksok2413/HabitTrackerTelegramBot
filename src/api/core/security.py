"""
Утилиты для обеспечения безопасности приложения, включая работу с JWT.
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from pydantic import ValidationError

from src.api.core.config import settings
from src.api.core.exceptions import UnauthorizedException
from src.api.core.logging import api_log as log
from src.api.schemas.auth_schema import TokenPayload

# --- Работа с JWT ---


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
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

    to_encode.update({"exp": int(expire.timestamp())})  # 'exp' должно быть Unix timestamp (int)

    log.debug(f"Создание JWT токена с payload: {to_encode} и временем истечения: {expire.isoformat()}")

    try:
        encoded_jwt: str = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    except Exception as exc:
        log.error(f"Ошибка при кодировании JWT: {exc}", exc_info=True)
        # В реальном приложении здесь может быть более специфическая обработка или re-raise
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
        payload_dict = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

        # Проверка наличия 'exp' и что токен не истек (хотя jwt.decode это тоже делает)
        # Это больше для явности и возможности кастомной обработки, если нужно.
        # jwt.decode выбросит ExpiredSignatureError, если токен истек.

        # Валидируем payload с помощью Pydantic схемы
        token_payload = TokenPayload(**payload_dict)

        if token_payload.user_id is None:  # Проверяем, что user_id есть в payload
            log.warning("В payload токена отсутствует user_id.")
            raise UnauthorizedException(
                message="Отсутствует идентификатор пользователя в токене.",
                error_type="token_user_id_missing",
            )

    except ExpiredSignatureError:
        log.warning("Срок действия JWT токена истек.")
        raise UnauthorizedException(message="Срок действия токена истек.", error_type="token_expired")
    except JWTError as exc:  # Общий класс ошибок JWT от python-jose
        log.warning(f"Ошибка декодирования/валидации JWT: {exc}")
        raise UnauthorizedException(message="Невалидный токен.", error_type="invalid_token")
    except ValidationError as exc:  # Ошибка валидации Pydantic для TokenPayload
        log.warning(f"Ошибка валидации payload токена: {exc.errors()}")
        raise UnauthorizedException(message="Некорректные данные в токене.", error_type="invalid_token_payload")
    except Exception as exc:  # Непредвиденная ошибка при обработке токена
        log.error(f"Непредвиденная ошибка при обработке токена: {exc}", exc_info=True)
        raise UnauthorizedException(message="Ошибка обработки токена.", error_type="token_processing_error")

    log.debug(f"Токен успешно верифицирован. Payload: {token_payload.model_dump_json()}")
    return token_payload
