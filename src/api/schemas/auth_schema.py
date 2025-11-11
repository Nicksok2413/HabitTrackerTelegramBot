"""Схемы Pydantic для аутентификации."""

from pydantic import BaseModel, Field

from .base_schema import BaseSchema


class Token(BaseSchema):
    """Схема для JWT токена."""

    access_token: str = Field(..., description="JWT токен доступа")
    token_type: str = Field(default="bearer", description="Тип токена (всегда 'bearer')")


class TokenPayload(BaseModel):
    """
    Схема для данных (payload), закодированных в JWT.
    Содержит ID пользователя и может содержать время истечения (exp).
    """

    user_id: int = Field(..., description="ID пользователя (внутренний)")
    exp: int | None = Field(None, description="Время истечения токена (Unix timestamp)")
    # Можно добавить другие поля, если они нужны в payload, например, 'sub' (subject)
    # sub: str | None = Field(None, description="Subject - обычно email или username")


class BotLoginRequest(BaseModel):
    """Схема запроса от бота для получения JWT токена пользователя."""

    telegram_id: int = Field(..., gt=0, description="Telegram ID пользователя")
    username: str | None = Field(None, max_length=100, description="Username пользователя (если есть)")
    first_name: str | None = Field(None, max_length=100, description="Имя пользователя")
    last_name: str | None = Field(None, max_length=100, description="Фамилия пользователя (если есть)")
