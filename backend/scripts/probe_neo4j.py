import asyncio, sys
from app.graph.connection import Neo4jConnectionManager

async def probe():
    conn = Neo4jConnectionManager()
    await conn.connect()
    try:
        for label, q in [
            ("Supplier count",    "MATCH (s:Supplier) RETURN count(s) AS n"),
            ("Warehouse count",   "MATCH (w:Warehouse) RETURN count(w) AS n"),
            ("Shipment count",    "MATCH (s:Shipment) RETURN count(s) AS n"),
            ("RISK_CORRELATED",   "MATCH ()-[r:RISK_CORRELATED]->() RETURN count(r) AS n"),
            ("SHIPS_VIA",         "MATCH ()-[r:SHIPS_VIA]->() RETURN count(r) AS n"),
            ("CO_FAILS_WITH",     "MATCH ()-[r:CO_FAILS_WITH]->() RETURN count(r) AS n"),
            ("SUPPLIES",          "MATCH ()-[r:SUPPLIES]->() RETURN count(r) AS n"),
            ("STORED_IN",         "MATCH ()-[r:STORED_IN]->() RETURN count(r) AS n"),
        ]:
            r = await conn.execute_query(q)
            print(f"{label}: {r[0]['n'] if r else 'ERR'}", flush=True)

        r = await conn.execute_query("MATCH (s:Supplier) RETURN keys(s) AS k LIMIT 1")
        print("Supplier keys:", r[0]['k'] if r else 'NONE', flush=True)
        r = await conn.execute_query("MATCH (w:Warehouse) RETURN keys(w) AS k LIMIT 1")
        print("Warehouse keys:", r[0]['k'] if r else 'NONE', flush=True)
        r = await conn.execute_query("MATCH (s:Shipment) RETURN keys(s) AS k LIMIT 1")
        print("Shipment keys:", r[0]['k'] if r else 'NONE', flush=True)

        r = await conn.execute_query(
            "MATCH (s:Supplier) RETURN s.department AS d, s.category AS cat, "
            "s.reliability_score AS rel, s.node_id AS nid LIMIT 10"
        )
        print("Supplier samples:", flush=True)
        for row in r:
            print(" ", dict(row), flush=True)

        r = await conn.execute_query(
            "MATCH (s:Supplier) RETURN distinct s.department AS d"
        )
        print("Distinct Supplier.department:", [row['d'] for row in r], flush=True)

        r = await conn.execute_query(
            "MATCH (s:Supplier) RETURN distinct s.category AS c"
        )
        print("Distinct Supplier.category:", [row['c'] for row in r][:20], flush=True)

    finally:
        await conn.disconnect()

asyncio.run(probe())
print("DONE", flush=True)
