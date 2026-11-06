from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from domain.entities.game_session import GameSessionState


@dataclass(frozen=True)
class WaitingSessionInfo:
    """Легковесная read-модель для списка открытых лобби."""

    game_session_id: str
    creator_login: str


@dataclass(frozen=True)
class FinishedSessionInfo:
    game_session_id: str
    status: GameSessionState
    result: Literal["WIN", "DRAW", "LOSE"]
    created_at: datetime
