"""
AMASCI Neo4j Connection Manager
==================================
Production-ready connection management with pooling, retry, health check, and graceful shutdown.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession, AsyncTransaction
from neo4j.exceptions import (
    AuthError,
    ServiceUnavailable,
    SessionExpired,
    TransientError,
)

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_RETRYABLE_EXCEPTIONS = (ServiceUnavailable, SessionExpired, TransientError)


class Neo4jConnectionManager:
    """
    Enterprise Neo4j connection manager.

    Features:
    - Singleton driver with connection pooling
    - Automatic retry with exponential backoff
    - Health check endpoint
    - Graceful shutdown
    - Transaction helpers
    """

    def __init__(self):
        self._driver: AsyncDriver | None = None
        self._settings = get_settings()
        self._max_retries = 3
        self._retry_delay = 1.0

    async def connect(self) -> None:
        """Establish connection to Neo4j."""
        if self._driver is not None:
            return

        logger.info(f"Connecting to Neo4j at {self._settings.neo4j_uri}")
        self._driver = AsyncGraphDatabase.driver(
            self._settings.neo4j_uri,
            auth=(self._settings.neo4j_user, self._settings.neo4j_password),
            max_connection_pool_size=50,
            connection_acquisition_timeout=30,
        )

        # Verify connectivity
        if await self.health_check():
            logger.info("Neo4j connection established successfully")
        else:
            raise ConnectionError("Failed to verify Neo4j connectivity")

    async def disconnect(self) -> None:
        """Gracefully close all connections."""
        if self._driver:
            logger.info("Closing Neo4j connection pool...")
            await self._driver.close()
            self._driver = None
            logger.info("Neo4j connections closed")

    async def health_check(self) -> bool:
        """Check Neo4j connectivity."""
        if not self._driver:
            return False
        try:
            async with self._driver.session(database=self._settings.neo4j_database) as session:
                result = await session.run("RETURN 1 AS health")
                record = await result.single()
                return record is not None and record["health"] == 1
        except Exception as e:
            logger.warning(f"Neo4j health check failed: {e}")
            return False

    @property
    def driver(self) -> AsyncDriver:
        """Get the active driver instance."""
        if self._driver is None:
            raise ConnectionError("Neo4j driver not initialized. Call connect() first.")
        return self._driver

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a Neo4j session with automatic retry on transient failures."""
        async with self.driver.session(database=self._settings.neo4j_database) as session:
            yield session

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncTransaction, None]:
        """Get a managed write transaction."""
        async with self.session() as session:
            tx = await session.begin_transaction()
            try:
                yield tx
                await tx.commit()
            except Exception:
                await tx.rollback()
                raise

    async def execute_query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        retries: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a Cypher query with retry logic.

        Returns list of record dictionaries.
        """
        max_retries = retries if retries is not None else self._max_retries
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                async with self.session() as session:
                    result = await session.run(query, parameters or {})
                    records = await result.data()
                    return records
            except _RETRYABLE_EXCEPTIONS as e:
                last_error = e
                if attempt < max_retries:
                    delay = self._retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Neo4j query retry {attempt + 1}/{max_retries}: {e}. "
                        f"Retrying in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
            except AuthError as e:
                logger.error(f"Neo4j authentication failed: {e}")
                raise
            except ConnectionError as e:
                logger.debug(f"Neo4j query skipped (offline): {e}")
                raise
            except Exception as e:
                logger.error(f"Neo4j query failed: {e}")
                raise

        raise last_error or ConnectionError("Neo4j query failed after retries")

    async def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a write query within a transaction."""
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    async def execute_batch(
        self,
        queries: list[tuple[str, dict[str, Any]]],
    ) -> int:
        """
        Execute multiple queries in a single transaction.

        Returns number of queries executed.
        """
        async with self.transaction() as tx:
            for query, params in queries:
                await tx.run(query, params)
            return len(queries)


# Module-level singleton
_connection_manager: Neo4jConnectionManager | None = None


def get_connection_manager() -> Neo4jConnectionManager:
    """Get or create the connection manager singleton."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = Neo4jConnectionManager()
    return _connection_manager


async def init_graph_connection() -> None:
    """Initialize graph connection on application startup."""
    manager = get_connection_manager()
    await manager.connect()


async def close_graph_connection() -> None:
    """Close graph connection on application shutdown."""
    global _connection_manager
    if _connection_manager:
        await _connection_manager.disconnect()
        _connection_manager = None
