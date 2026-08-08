import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
import logging; logging.basicConfig(level=logging.WARNING)
import pandas as pd
from app.ml.training import BaseTrainer
from app.ml.utils import IntelligenceType

df = pd.read_parquet("data/uploads/processed_master.parquet")
t = BaseTrainer()
r = t.train(df, IntelligenceType.DEMAND, run_walk_forward=False)
print("metrics keys:", list(r.metrics.keys()))
print("metrics:", r.metrics)
