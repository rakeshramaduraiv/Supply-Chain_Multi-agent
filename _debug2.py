import os, sys
sys.path.insert(0, '/app')
os.chdir('/app')

from app.ml.registry import ModelRegistry
from app.ml.utils import IntelligenceType, FEATURE_CONFIGS, ModelTask
import numpy as np

r = ModelRegistry()
for it in [IntelligenceType.DEMAND, IntelligenceType.SUPPLIER, IntelligenceType.LOGISTICS]:
    v = r.get_latest_version(it)
    if v:
        print(f'{it.value}: features_used={v.features_used}')
        print(f'  metrics={v.metrics}')
