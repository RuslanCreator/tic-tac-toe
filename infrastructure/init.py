import asyncio
import logging

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from domain.entities.player import BOT_PLAYER_ID
from infrastructure.model import Base, PlayerDataModel

logger = logging.getLogger(__name__)

BOT_LOGIN = "Computer"
BOT_PASSWORD_HASH = "bot_hash_disabled"


async def init_database(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    attempts: int = 10,
    delay_seconds: float = 1.0,
) -> None:
    """Создаёт таблицы и гарантирует наличие служебного игрока-бота.

    create_all не заменяет миграции, но для учебного проекта этого достаточно.
    Повторные попытки нужны, чтобы приложение пережило старт рядом с ещё
    поднимающейся базой данных.
    """
    for attempt in range(1, attempts + 1):
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            break
        except (OperationalError, OSError):
            if attempt == attempts:
                raise
            logger.warning(
                "База данных ещё не готова (попытка %s/%s)", attempt, attempts
            )
            await asyncio.sleep(delay_seconds)

    async with session_factory() as session:
        statement = (
            insert(PlayerDataModel)
            .values(
                id=BOT_PLAYER_ID,
                login=BOT_LOGIN,
                password_hash=BOT_PASSWORD_HASH,
            )
            .on_conflict_do_nothing()
        )
        await session.execute(statement)
        await session.commit()
