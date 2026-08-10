import asyncio, sys, os
sys.path.insert(0, '/app')
os.chdir('/app')

# Test Neo4j
try:
    from app.graph.connection import get_connection_manager
    async def test_neo4j():
        c = get_connection_manager()
        print('connecting...')
        await c.connect()
        print('connected')
        r = await c.execute_query('MATCH (n) RETURN count(n) AS cnt', {})
        print('nodes:', r)
        r2 = await c.execute_query('MATCH ()-[rel]->() RETURN count(rel) AS cnt', {})
        print('rels:', r2)
        labels = await c.execute_query('CALL db.labels() YIELD label RETURN label', {})
        print('labels:', labels)
    asyncio.run(test_neo4j())
except Exception as e:
    print('Neo4j error:', e)

# Test TPKE table
try:
    import psycopg2, os as _os
    conn = psycopg2.connect(
        host=_os.getenv('POSTGRES_HOST','postgres'),
        port=int(_os.getenv('POSTGRES_PORT',5432)),
        user=_os.getenv('POSTGRES_USER','amasci_user'),
        password=_os.getenv('POSTGRES_PASSWORD','amasci_dev_pass'),
        dbname=_os.getenv('POSTGRES_DB','amasci_db'),
    )
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
    print('tables:', [r[0] for r in cur.fetchall()])
    try:
        cur.execute("SELECT COUNT(*) FROM tpke_mutations")
        print('tpke_mutations rows:', cur.fetchone())
    except Exception as e:
        print('tpke_mutations error:', e)
    conn.close()
except Exception as e:
    print('Postgres error:', e)
