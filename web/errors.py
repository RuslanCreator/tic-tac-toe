from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from application.errors import (
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from domain.errors import DomainError

_STATUS_BY_ERROR: dict[type[Exception], int] = {
    ValidationError: 400,
    DomainError: 400,
    AuthenticationError: 401,
    ForbiddenError: 403,
    NotFoundError: 404,
    ConflictError: 409,
}


def _make_handler(status_code: int):
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


def register_exception_handlers(app: FastAPI) -> None:
    for error_type, status_code in _STATUS_BY_ERROR.items():
        app.add_exception_handler(error_type, _make_handler(status_code))
