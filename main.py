from contextlib import asynccontextmanager
from pathlib import Path

import aiofiles
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sqlalchemy import select, text

from datasource.model import Base, PlayerDataModel
from di.container import infra_container
from web.auth_router import auth_router
from web.router import game_router

BASE_DIR = Path(__file__).resolve().parent
HTML_FILE_PATH = BASE_DIR / "web" / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with infra_container.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Временный костыль для тестов: очищаем игры при каждом старте uvicorn
        await conn.execute(text("TRUNCATE TABLE game_sessions CASCADE;"))

    async with infra_container.session_factory() as session:
        bot_exists = await session.scalar(
            select(PlayerDataModel).where(PlayerDataModel.id == "bot")
        )
        if not bot_exists:
            session.add(
                PlayerDataModel(
                    id="bot",
                    login="Computer",
                    password_hash="bot_hash_disabled",
                )
            )

        await session.commit()

    yield

    await infra_container.engine.dispose()


app = FastAPI(
    title="Игровой Сервер Крестики-Нолики",
    description="Чистая архитектура на FastAPI",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(auth_router)
app.include_router(game_router)


@app.get("/", response_class=HTMLResponse, tags=["Frontend"])
async def serve_frontend():
    try:
        async with aiofiles.open(HTML_FILE_PATH, mode="r", encoding="utf-8") as file:
            html_content = await file.read()
        return HTMLResponse(content=html_content, status_code=200)

    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Ошибка: Файл index.html не найден на сервере!</h1>",
            status_code=404,
        )


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
