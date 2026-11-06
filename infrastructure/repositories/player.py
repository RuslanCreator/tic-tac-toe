from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from application.errors import ConflictError
from application.ports.repositories import PlayerRepositoryInterface
from domain.entities.player import Player
from infrastructure.mappers.player import PlayerMapper
from infrastructure.model import PlayerDataModel


class PlayerRepository(PlayerRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, player: Player, password_hash: str) -> None:
        db_player = PlayerMapper.to_data(player)
        db_player.password_hash = password_hash
        try:
            await self._session.merge(db_player)
            await self._session.flush()
        except IntegrityError as e:
            raise ConflictError("Игрок с таким логином уже существует") from e

    async def get_by_login(self, login: str) -> tuple[Player, str] | None:
        query = select(PlayerDataModel).where(PlayerDataModel.login == login)
        db_player = await self._session.scalar(query)
        if not db_player:
            return None

        return PlayerMapper.to_domain(db_player), db_player.password_hash

    async def get_by_id(self, player_id: str) -> Player | None:
        query = select(PlayerDataModel).where(PlayerDataModel.id == player_id)
        db_player = await self._session.scalar(query)
        if not db_player:
            return None

        return PlayerMapper.to_domain(db_player)
