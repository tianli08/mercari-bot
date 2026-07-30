"""FastAPI application factory and ASGI application."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .. import database
from ..config import settings
from .errors import register_exception_handlers
from .routers import router as api_router

API_PREFIX = "/api/v1"


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        await database.db_client.ensure_indexes()
        yield
    finally:
        database.db_client.client.close()


def create_app() -> FastAPI:
    """Build and configure the marketplace monitor API application."""
    application = FastAPI(
        title="Marketplace Monitor API",
        version="0.1.0",
        lifespan=_lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix=API_PREFIX)
    register_exception_handlers(application)
    return application


app = create_app()
