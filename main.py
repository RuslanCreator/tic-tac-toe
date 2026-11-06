from contextlib import asynccontextmanager
from pathlib import Path

import aiofiles
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from di.composition import AppContext
from di.settings import Settings
from infrastructure.model import Base, PlayerDataModel
from web.auth.router import auth_router
from web.errors import register_exception_handlers
from web.router import game_router
from web.ws.router import ws_router

BASE_DIR = Path(__file__).resolve().parent
HTML_FILE_PATH = BASE_DIR / "web" / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    context = AppContext(Settings.from_env())
    app.state.context = context

    try:
        async with context.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with context.session_factory() as session:
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
    finally:
        await context.dispose()


app = FastAPI(
    title="Игровой Сервер Крестики-Нолики",
    description="Чистая архитектура на FastAPI",
    version="1.0.0",
    lifespan=lifespan,
)
register_exception_handlers(app)
app.include_router(auth_router)
app.include_router(game_router)
app.include_router(ws_router)


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
