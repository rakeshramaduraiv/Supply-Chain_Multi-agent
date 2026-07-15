"""
AMASCI Database Initialization Script
=======================================
Creates database schema and applies initial constraints.

Usage:
    python -m scripts.init_db
"""

import asyncio
import logging

from app.core.config import get_settings
from app.database.postgres import engine
from app.database.neo4j import get_neo4j_session
from app.models.base import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


async def init_postgres() -> None:
    """Create all PostgreSQL tables."""
    logger.info("Creating PostgreSQL tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("PostgreSQL tables created successfully")


async def init_neo4j_constraints() -> None:
    """Create Neo4j constraints and indexes."""
    logger.info("Creating Neo4j constraints...")

    constraints = [
        "CREATE CONSTRAINT supplier_id IF NOT EXISTS FOR (s:Supplier) REQUIRE s.supplier_id IS UNIQUE",
        "CREATE CONSTRAINT product_id IF NOT EXISTS FOR (p:Product) REQUIRE p.product_id IS UNIQUE",
        "CREATE CONSTRAINT warehouse_id IF NOT EXISTS FOR (w:Warehouse) REQUIRE w.warehouse_id IS UNIQUE",
        "CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (c:Customer) REQUIRE c.customer_id IS UNIQUE",
        "CREATE CONSTRAINT order_id IF NOT EXISTS FOR (o:Order) REQUIRE o.order_id IS UNIQUE",
        "CREATE CONSTRAINT market_id IF NOT EXISTS FOR (m:Market) REQUIRE m.market_id IS UNIQUE",
        "CREATE CONSTRAINT region_id IF NOT EXISTS FOR (r:Region) REQUIRE r.region_id IS UNIQUE",
    ]

    indexes = [
        "CREATE INDEX supplier_risk IF NOT EXISTS FOR (s:Supplier) ON (s.risk_score)",
        "CREATE INDEX product_risk IF NOT EXISTS FOR (p:Product) ON (p.risk_score)",
        "CREATE INDEX order_date IF NOT EXISTS FOR (o:Order) ON (o.order_date)",
        "CREATE INDEX market_name IF NOT EXISTS FOR (m:Market) ON (m.name)",
    ]

    async with get_neo4j_session() as session:
        for constraint in constraints:
            try:
                await session.run(constraint)
            except Exception as e:
                logger.warning(f"Constraint may already exist: {e}")

        for index in indexes:
            try:
                await session.run(index)
            except Exception as e:
                logger.warning(f"Index may already exist: {e}")

    logger.info("Neo4j constraints and indexes created successfully")


async def main() -> None:
    """Run all initialization tasks."""
    logger.info("=" * 60)
    logger.info("AMASCI Database Initialization")
    logger.info("=" * 60)

    await init_postgres()
    await init_neo4j_constraints()

    logger.info("=" * 60)
    logger.info("Initialization complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
