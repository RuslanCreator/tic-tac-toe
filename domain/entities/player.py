import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True, kw_only=True)
class Player:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    login: str


# import uuid
# from dataclasses import dataclass
# from enum import Enum
# from typing import Optional

# # Условный UUID компьютерного игрока. Компьютер не является записью в таблице
# # пользователей, но должен быть адресуем как "игрок" в состоянии игры
# # (например, чтобы указать, что ход или победа принадлежат компьютеру).
# COMPUTER_PLAYER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


# class GameStateType(str, Enum):
#     WAITING_FOR_PLAYERS = "waiting_for_players"
#     PLAYER_TURN = "player_turn"
#     DRAW = "draw"
#     WIN = "win"


# @dataclass
# class GameState:
#     type: GameStateType
#     player_id: Optional[uuid.UUID] = None

#     @classmethod
#     def waiting_for_players(cls) -> "GameState":
#         return cls(type=GameStateType.WAITING_FOR_PLAYERS)

#     @classmethod
#     def player_turn(cls, player_id: uuid.UUID) -> "GameState":
#         return cls(type=GameStateType.PLAYER_TURN, player_id=player_id)

#     @classmethod
#     def draw(cls) -> "GameState":
#         return cls(type=GameStateType.DRAW)

#     @classmethod
#     def win(cls, player_id: uuid.UUID) -> "GameState":
#         return cls(type=GameStateType.WIN, player_id=player_id)

#     def is_ended(self) -> bool:
#         return self.type in (GameStateType.DRAW, GameStateType.WIN)


# что структура класса, тип реализация?
