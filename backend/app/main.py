"""
AMASCI - Adaptive Supply Chain Intelligence Platform
=====================================================
FastAPI Application Entry Point

Enterprise-grade AI-powered supply chain risk intelligence
using Temporal Knowledge Graph Evolution (TPKE) and
GraphRAG-Guided Risk Reasoning.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse

from app.api.middleware import (
    CorrelationIdMiddleware,
    RequestTimingMiddleware,
    RequestLoggerMiddleware,
)
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.constants import API_V1_PREFIX
from app.core.events import on_startup, on_shutdown
from app.database.postgres import init_db, close_db
from app.database.neo4j import init_neo4j, close_neo4j
from app.exceptions.handlers import register_exception_handlers
from app.logging import setup_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager for startup/shutdown."""
    # --- Startup ---
    setup_logging()
    await init_db()
    await init_neo4j()
    await on_startup()
    yield
    # --- Shutdown ---
    await on_shutdown()
    await close_db()
    await close_neo4j()


def create_application() -> FastAPI:
    """Application factory pattern."""
    application = FastAPI(
        title="AMASCI - Supply Chain Intelligence Platform",
        description=(
            "Enterprise AI-powered supply chain risk intelligence using "
            "Temporal Knowledge Graph Evolution (TPKE) and "
            "GraphRAG-Guided Risk Reasoning."
        ),
        version=settings.app_version,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    # --- Middleware (order matters: last added = first executed) ---
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID", "X-Process-Time-Ms"],
    )
    application.add_middleware(GZipMiddleware, minimum_size=1000)
    application.add_middleware(RequestLoggerMiddleware)
    application.add_middleware(RequestTimingMiddleware)
    application.add_middleware(CorrelationIdMiddleware)

    # --- Exception Handlers ---
    register_exception_handlers(application)

    # --- Routers ---
    application.include_router(api_router, prefix=API_V1_PREFIX)

    return application


app = create_application()
