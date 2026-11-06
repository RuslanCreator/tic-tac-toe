from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from application.errors import NotFoundError
from application.ports.repositories import GameSessionRepositoryInterface
from application.read_models import FinishedSessionInfo, WaitingSessionInfo
from domain.entities.game_session import GameSession, GameSessionState
from infrastructure.mappers.game_session import GameSessionMapper
from infrastructure.model import GameSessionDataModel, PlayerDataModel


class GameSessionRepository(GameSessionRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, game_session: GameSession) -> None:
        db_game_model = GameSessionMapper.to_data(game_session)
        self._session.add(db_game_model)

    async def update(self, game_session: GameSession) -> None:
        db_game_model = await self._session.get(GameSessionDataModel, game_session.id)
        if db_game_model is None:
            raise NotFoundError(f"Игровая сессия {game_session.id} не найдена")

        GameSessionMapper.update_data_model(
            source_entity=game_session, target_model=db_game_model
        )

    async def get_by_id(self, game_session_id: str) -> GameSession | None:
        query = select(GameSessionDataModel).where(
            GameSessionDataModel.id == game_session_id
        )
        result = await self._session.execute(query)
        db_game = result.scalar_one_or_none()

        return GameSessionMapper.to_domain(db_game) if db_game else None

    async def get_by_id_for_update(self, game_session_id: str) -> GameSession | None:
        query = (
            select(GameSessionDataModel)
            .where(GameSessionDataModel.id == game_session_id)
            .with_for_update()
        )
        result = await self._session.execute(query)
        db_game = result.scalar_one_or_none()

        return GameSessionMapper.to_domain(db_game) if db_game else None

    async def get_waiting_sessions(self) -> list[WaitingSessionInfo]:
        query = (
            select(GameSessionDataModel.id, PlayerDataModel.login)
            .join(
                PlayerDataModel, GameSessionDataModel.player_x_id == PlayerDataModel.id
            )
            .where(GameSessionDataModel.status == GameSessionState.WAITING.value)
        )
        result = await self._session.execute(query)

        return [
            WaitingSessionInfo(game_session_id=row["id"], creator_login=row["login"])
            for row in result.mappings()
        ]

    async def delete(self, game_session_id: str) -> None:
        query = delete(GameSessionDataModel).where(
            GameSessionDataModel.id == game_session_id
        )
        await self._session.execute(query)

    async def get_finished_by_player_id(
        self, player_id: str
    ) -> list[FinishedSessionInfo]:
        query = (
            select(GameSessionDataModel)
            .where(
                or_(
                    GameSessionDataModel.player_x_id == player_id,
                    GameSessionDataModel.player_o_id == player_id,
                ),
                GameSessionDataModel.status
                in [
                    GameSessionState.DRAW.value,
                    GameSessionState.WON_X.value,
                    GameSessionState.WON_O.value,
                ],
            )
            .order_by(GameSessionDataModel.created_at.desc())
        )
        result = await self._session.execute(query)

        return [self._to_finished_info(model, player_id) for model in result.scalars()]

    @staticmethod
    def _to_finished_info(
        model: GameSessionDataModel, player_id: str
    ) -> FinishedSessionInfo:
        status = GameSessionState(model.status)

        if status == GameSessionState.DRAW:
            result = "DRAW"
        elif (status == GameSessionState.WON_X and model.player_x_id == player_id) or (
            status == GameSessionState.WON_O and model.player_o_id == player_id
        ):
            result = "WIN"
        else:
            result = "LOSE"

        return FinishedSessionInfo(
            game_session_id=model.id,
            status=status,
            result=result,
            created_at=model.created_at,
        )
