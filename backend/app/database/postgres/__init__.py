"""
AMASCI PostgreSQL Database Engine
===================================
Async SQLAlchemy engine, session factory, and dependency injection.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10,
    poolclass=NullPool if settings.app_env == "testing" else None,
)

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection for database sessions."""
    try:
        async with async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    except OSError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")


async def init_db() -> None:
    """Initialize database connection on startup."""
    logger.info("Initializing PostgreSQL connection...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: None)  # Test connection
        logger.info("PostgreSQL connection established successfully")
    except Exception as e:
        logger.critical(f"Failed to connect to PostgreSQL: {e}")
        logger.warning("Application will start without PostgreSQL. Database endpoints will return errors.")


async def close_db() -> None:
    """Close database connections on shutdown."""
    logger.info("Closing PostgreSQL connections...")
    await engine.dispose()
    logger.info("PostgreSQL connections closed")
