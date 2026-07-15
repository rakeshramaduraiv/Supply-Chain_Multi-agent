"""
AMASCI Neo4j Database Driver
==============================
Neo4j connection management and session handling.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_driver: AsyncDriver | None = None


async def get_neo4j_driver() -> AsyncDriver:
    """Get or create the Neo4j driver singleton."""
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            max_connection_pool_size=50,
        )
    return _driver


@asynccontextmanager
async def get_neo4j_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection for Neo4j sessions."""
    driver = await get_neo4j_driver()
    async with driver.session(database=settings.neo4j_database) as session:
        yield session


async def init_neo4j() -> None:
    """Initialize Neo4j connection on startup."""
    logger.info("Initializing Neo4j connection...")
    try:
        driver = await get_neo4j_driver()
        async with driver.session(database=settings.neo4j_database) as session:
            result = await session.run("RETURN 1 AS connected")
            record = await result.single()
            if record and record["connected"] == 1:
                logger.info("Neo4j connection established successfully")
    except Exception as e:
        logger.critical(f"Failed to connect to Neo4j: {e}")
        logger.warning("Application will start without Neo4j. Graph endpoints will return errors.")


async def close_neo4j() -> None:
    """Close Neo4j connections on shutdown."""
    global _driver
    if _driver:
        logger.info("Closing Neo4j connections...")
        await _driver.close()
        _driver = None
        logger.info("Neo4j connections closed")
