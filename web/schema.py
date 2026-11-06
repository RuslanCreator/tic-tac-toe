import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from domain.entities.game_session import GameMode, GameSessionState


class MoveRequest(BaseModel):
    row: int = Field(..., ge=0, description="Индекс строки (0-N)")
    col: int = Field(..., ge=0, description="Индекс колонки (0-N)")


class GameResponse(BaseModel):
    game_session_id: uuid.UUID = Field(..., description="ID игровой сессии")
    mode: GameMode = Field(..., description="Режим игры: PvE или PvP")
    status: GameSessionState = Field(..., description="Технический статус")
    status_text: str = Field(..., description="Текстовый статус для игрока")
    board: list[str] = Field(
        ..., description="Текущее состояние доски в виде плоского списка строк"
    )
    grid_size: int = Field(..., description="Размер игрового поля")
    player_x_id: str | None = Field(..., description="ID игрока за X")
    player_o_id: str | None = Field(..., description="ID игрока за O")
    current_player_id: str | None = Field(
        ..., description="ID игрока, который должен ходить"
    )
    is_finished: bool = Field(..., description="Завершена ли игра")


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
    player_id: uuid.UUID = Field(..., description="ID игрока")
    login: str = Field(..., description="Логин игрока")


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


class FinishedSessionItem(BaseModel):
    game_session_id: uuid.UUID = Field(..., description="ID игровой сессии")
    result: Literal["WIN", "DRAW", "LOSE"] = Field(
        ..., description="Результат для текущего игрока"
    )
    created_at: datetime = Field(..., description="Дата создания игры")


class FinishedSessionsResponse(BaseModel):
    sessions: list[FinishedSessionItem] = Field(
        ..., description="Завершённые игры игрока"
    )
