import os, sys
sys.path.insert(0, '/app')
os.chdir('/app')

from app.core.config import get_settings
from pathlib import Path
s = get_settings()
p = Path(s.upload_dir) / 'processed_master.parquet'
print('parquet path:', p, 'exists:', p.exists())

import pandas as pd
df = pd.read_parquet(p)
print('shape:', df.shape)

from app.ml.registry import ModelRegistry
from app.ml.utils import IntelligenceType, FEATURE_CONFIGS, ModelTask
r = ModelRegistry()
for it in [IntelligenceType.DEMAND, IntelligenceType.SUPPLIER, IntelligenceType.LOGISTICS]:
    v = r.get_latest_version(it)
    print(f'{it.value}: version={v is not None}', v.version_id if v else '')

# Try ablation
from app.ml.utils import chronological_split, prepare_features
_, test_df = chronological_split(df, train_ratio=0.8)
print('test_df shape:', test_df.shape)

for it in [IntelligenceType.DEMAND, IntelligenceType.SUPPLIER, IntelligenceType.LOGISTICS]:
    v = r.get_latest_version(it)
    if not v:
        print(f'{it.value}: no version'); continue
    try:
        model = r.load_model(it)
        fc = FEATURE_CONFIGS[it]
        X_test, y_test = prepare_features(test_df, fc)
        print(f'{it.value}: X_test={X_test.shape}, task={fc.task}')
        y_pred = model.predict(X_test)
        print(f'{it.value}: predict OK, sample={y_pred[:3]}')
    except Exception as e:
        print(f'{it.value}: ERROR {e}')

# Neo4j graph
try:
    import asyncio
    from app.graph.connection import get_connection_manager
    conn = get_connection_manager()
    async def test():
        rows = await conn.execute_query("MATCH (n) RETURN count(n) AS cnt", {})
        return rows
    result = asyncio.run(test())
    print('neo4j node count:', result)
except Exception as e:
    print('neo4j error:', e)
