import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from di.composition import AppContext, get_context
from di.settings import Settings
from infrastructure.init import init_database
from web.auth.router import auth_router
from web.errors import register_exception_handlers
from web.router import game_router
from web.ws.router import ws_router

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).resolve().parent
STATIC_DIR = WEB_DIR / "static"
INDEX_FILE = STATIC_DIR / "index.html"


def create_app(
    settings: Settings | None = None,
    *,
    init_db: bool = True,
    context: AppContext | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owns_context = getattr(app.state, "context", None) is None
        if owns_context:
            app.state.context = AppContext(settings or Settings.from_env())

        app_context = app.state.context
        try:
            if init_db:
                await init_database(app_context.engine, app_context.session_factory)
            yield
        finally:
            if owns_context:
                await app_context.dispose()

    app = FastAPI(
        title="Игровой Сервер Крестики-Нолики",
        description="Чистая архитектура на FastAPI",
        version="1.0.0",
        lifespan=lifespan,
    )

    if context is not None:
        app.state.context = context

    register_exception_handlers(app)
    app.include_router(auth_router)
    app.include_router(game_router)
    app.include_router(ws_router)

    app.mount(
        "/static",
        StaticFiles(directory=STATIC_DIR, check_dir=False),
        name="static",
    )

    @app.get("/", include_in_schema=False, response_model=None)
    async def serve_frontend() -> FileResponse:
        if not INDEX_FILE.is_file():
            raise HTTPException(status_code=404, detail="index.html не найден")
        return FileResponse(INDEX_FILE)

    @app.get("/health", tags=["Сервис"], response_model=None)
    async def health(
        app_context: AppContext = Depends(get_context),
    ) -> dict[str, str] | JSONResponse:
        try:
            async with app_context.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception:
            logger.exception("Проверка здоровья базы данных не прошла")
            return JSONResponse(status_code=503, content={"status": "unavailable"})

        return {"status": "ok"}

    return app
