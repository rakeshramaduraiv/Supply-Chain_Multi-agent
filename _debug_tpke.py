import psycopg2, os
conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST','postgres'),
    port=int(os.getenv('POSTGRES_PORT',5432)),
    user=os.getenv('POSTGRES_USER','amasci_user'),
    password=os.getenv('POSTGRES_PASSWORD','amasci_dev_pass'),
    dbname=os.getenv('POSTGRES_DB','amasci_db'),
)
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='tpke_logs' ORDER BY ordinal_position")
print('tpke_logs columns:', cur.fetchall())
cur.execute("SELECT COUNT(*) FROM tpke_logs")
print('tpke_logs count:', cur.fetchone())
cur.execute("SELECT * FROM tpke_logs LIMIT 3")
print('sample:', cur.fetchall())

# Also check ablation_runs
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='ablation_runs' ORDER BY ordinal_position")
print('ablation_runs columns:', cur.fetchall())
cur.execute("SELECT COUNT(*) FROM ablation_runs")
print('ablation_runs count:', cur.fetchone())
cur.execute("SELECT * FROM ablation_runs LIMIT 3")
print('ablation sample:', cur.fetchall())
conn.close()
