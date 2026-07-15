"""AMASCI Startup Health Check Script"""
import asyncio
import sys

async def check_postgres():
    """Test PostgreSQL connectivity with common credentials."""
    try:
        import asyncpg
    except ImportError:
        return "MISSING_PACKAGE", "asyncpg not installed"

    # Try common credential combinations
    creds = [
        ("postgres", "postgres", "postgres"),
        ("postgres", "password", "postgres"),
        ("postgres", "admin", "postgres"),
        ("amasci_user", "amasci_password", "amasci_db"),
        ("postgres", "postgres", "amasci_db"),
    ]

    for user, pwd, db in creds:
        try:
            conn = await asyncpg.connect(
                host="localhost", port=5432, user=user, password=pwd, database=db
            )
            version = await conn.fetchval("SELECT version()")
            await conn.close()
            return "CONNECTED", f"user={user} db={db} | {version[:60]}"
        except Exception:
            continue

    # Try without specific db
    for user, pwd, _ in creds:
        try:
            conn = await asyncpg.connect(
                host="localhost", port=5432, user=user, password=pwd, database="postgres"
            )
            version = await conn.fetchval("SELECT version()")
            await conn.close()
            return "CONNECTED_DEFAULT", f"user={user} db=postgres | {version[:60]}"
        except Exception:
            continue

    return "FAILED", "Could not connect with any common credentials"


def check_neo4j():
    """Test Neo4j connectivity."""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        return "MISSING_PACKAGE", "neo4j not installed"

    creds = [
        ("bolt://localhost:7687", "neo4j", "neo4j"),
        ("bolt://localhost:7687", "neo4j", "password"),
        ("bolt://localhost:7687", "neo4j", "neo4j_password"),
        ("bolt://localhost:7687", "neo4j", "admin"),
    ]

    for uri, user, pwd in creds:
        try:
            driver = GraphDatabase.driver(uri, auth=(user, pwd))
            with driver.session() as session:
                result = session.run("RETURN 1 AS n")
                result.single()
            driver.close()
            return "CONNECTED", f"uri={uri} user={user} password={pwd}"
        except Exception:
            try:
                driver.close()
            except:
                pass
            continue

    return "FAILED", "Could not connect with any common credentials"


if __name__ == "__main__":
    print("=" * 60)
    print("AMASCI CONNECTIVITY CHECK")
    print("=" * 60)

    # PostgreSQL
    print("\n[PostgreSQL]")
    pg_status, pg_detail = asyncio.run(check_postgres())
    print(f"  Status: {pg_status}")
    print(f"  Detail: {pg_detail}")

    # Neo4j
    print("\n[Neo4j]")
    neo_status, neo_detail = check_neo4j()
    print(f"  Status: {neo_status}")
    print(f"  Detail: {neo_detail}")

    print("\n" + "=" * 60)

    # Output for parsing
    print(f"\nPG_STATUS={pg_status}")
    print(f"PG_DETAIL={pg_detail}")
    print(f"NEO_STATUS={neo_status}")
    print(f"NEO_DETAIL={neo_detail}")
