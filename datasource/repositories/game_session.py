from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from datasource.mappers.game_session import GameSessionMapper
from datasource.model import GameSessionDataModel, PlayerDataModel
from domain.entities.game_session import (
    GameSession,
    GameSessionState,
    WaitingSessionInfo,
)
from domain.interfaces import GameSessionRepositoryInterface


class GameSessionRepository(GameSessionRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, game_session: GameSession) -> None:
        db_game_model = GameSessionMapper.to_data(game_session)
        self._session.add(db_game_model)

    async def update(self, game_session: GameSession) -> None:
        db_game_model = await self._session.get(GameSessionDataModel, game_session.id)
        if db_game_model is None:
            raise ValueError(f"Игровая сессия {game_session.id} не найдена")

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

    # async def get_all_with_players(self) -> list[GameSessionDataModel]:
    #     query = select(GameSessionDataModel).options(
    #         selectinload(GameSessionDataModel.player_x),
    #         selectinload(GameSessionDataModel.player_o),
    #     )
    #     result = await self._session.execute(query)

    #     return result.scalars().all()

    # async def delete_old_games(self) -> None:
    #     # Запрос к БД: Удалить все игры, которые старше 365 дней
    #     # SQL: DELETE FROM games WHERE created_at < NOW() - INTERVAL '1 year'
    #     query = delete(GameSessionDataModel).where(
    #         GameSessionDataModel.created_at < func.now() - text("INTERVAL '1 year'")
    #     )
    #     await self._session.execute(query)


# For execute delete old games script

# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from fastapi import FastAPI
# from di.container import DatabaseFactory
# from datasource.repository import GameSessionRepository

# app = FastAPI()
# scheduler = AsyncIOScheduler()

# # Функция, которую планировщик будет дергать сам
# async def scheduled_cleanup():
#     # Открываем чистую сессию из фабрики
#     async with DatabaseFactory.get_session() as session:
#         repo = GameSessionRepository(session)
#         await repo.delete_old_games()

# @app.on_event("startup")
# async def start_scheduler():
#     # Настраиваем запуск каждый день в 3 часа ночи прямо внутри FastAPI
#     scheduler.add_job(scheduled_cleanup, "cron", hour=3, minute=0)
#     scheduler.start()
