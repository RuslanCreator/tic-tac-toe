import uuid
from dataclasses import dataclass, field

# Компьютерный игрок хранится в БД как обычный игрок с фиксированным id.
# Это позволяет не добавлять отдельную колонку "режим игры": PvE определяется
# по тому, что за нолики играет бот.
BOT_PLAYER_ID = "bot"


@dataclass(frozen=True, kw_only=True)
class Player:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    login: str
