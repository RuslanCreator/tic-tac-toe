import uuid

from pydantic import BaseModel, ConfigDict, Field


class MoveRequest(BaseModel):
    row: int = Field(..., ge=0, description="Индекс строки (0-N)")
    col: int = Field(..., ge=0, description="Индекс колонки (0-N)")


class GameResponse(BaseModel):
    game_session_id: uuid.UUID = Field(..., description="ID игровой сессии")
    status: str = Field(..., description="Технический статус")
    status_text: str = Field(..., description="Текстовый статус для игрока")
    board: list[str] = Field(
        ..., description="Текущее состояние доски в виде плоского списка строк"
    )


class LoginRequest(BaseModel):
    login: str = Field(..., min_length=3, max_length=25, description="Логин игрока")
    password: str = Field(
        ..., min_length=6, max_length=255, description="Пароль игрока"
    )


class SignUpRequest(LoginRequest):
    pass


class AuthResponse(BaseModel):
    access_token: str = Field(..., description="JWT токен доступа")
    token_type: str = Field("bearer", description="Тип токена (всегда bearer)")


class WaitingSessionItem(BaseModel):
    game_session_id: uuid.UUID = Field(..., description="ID открытой игровой сессии")
    creator_login: str = Field(..., description="Логин создателя матча")


class AvailableSessionsResponse(BaseModel):
    sessions: list[WaitingSessionItem] = Field(
        ..., description="Список доступных лобби"
    )


class UserResponse(BaseModel):
    id: uuid.UUID = Field(..., description="Уникальный UUID пользователя")
    login: str = Field(..., description="Имя пользователя (логин)")

    model_config = ConfigDict(from_attributes=True)
