"""Bootstrap CumulativeStore and verify period.py."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
import logging; logging.basicConfig(level=logging.WARNING)

from app.store.cumulative import CumulativeStore
from app.core.period import current_data_end, next_period, cycle_status

print("Bootstrapping CumulativeStore...")
store = CumulativeStore()
summary = store.summary()
print(f"  base_exists: {summary['base_exists']}")
print(f"  total_rows:  {summary['total_rows']}")
print(f"  data_end:    {summary['data_end']}")
print(f"  periods:     {summary['periods']}")

print("\nPeriod module:")
print(f"  current_data_end(): {current_data_end()}")
print(f"  next_period():      {next_period()}")
print(f"  cycle_status():     {cycle_status()}")

# Verify load_cumulative works
print("\nLoading cumulative...")
df = store.load_cumulative()
print(f"  {len(df)} rows, {len(df.columns)} columns")
print("PASS")
