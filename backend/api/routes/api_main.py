import traceback

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from api import app, logger
from api.routes.attachments import router as attachments_router
from api.routes.app_home import router as app_home_router
from api.routes.containers import router as containers_router
from api.routes.emails import router as emails_router
from api.routes.exceptions import router as exceptions_router
from api.routes.gmail_connections import router as gmail_connections_router
from api.routes.health import router as health_router
from api.routes.ingest import router as ingest_router
from api.routes.manual_ingest import router as manual_ingest_router
from api.routes.sync_jobs import router as sync_jobs_router

app.include_router(health_router)
app.include_router(app_home_router)
app.include_router(attachments_router)
app.include_router(gmail_connections_router)
app.include_router(sync_jobs_router)
app.include_router(ingest_router)
app.include_router(manual_ingest_router)
app.include_router(containers_router)
app.include_router(emails_router)
app.include_router(exceptions_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = []
    for error in exc.errors():
        loc = " -> ".join(str(part) for part in error["loc"] if part != "body")
        errors.append({"field": loc, "message": error["msg"], "type": error["type"]})
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error", "errors": errors},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def _safe_db_message(exc: DBAPIError) -> str:
    message = str(exc.orig) if exc.orig else str(exc)
    return message.splitlines()[0]


@app.exception_handler(DBAPIError)
async def dbapi_exception_handler(request: Request, exc: DBAPIError) -> JSONResponse:
    logger.error(
        "DBAPIError on %s %s:\n%s", request.method, request.url, traceback.format_exc()
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Database error", "error": _safe_db_message(exc)},
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    logger.error(
        "SQLAlchemyError on %s %s:\n%s",
        request.method,
        request.url,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Database error", "error": str(exc)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception on %s %s:\n%s",
        request.method,
        request.url,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc),
            "type": type(exc).__name__,
        },
    )
