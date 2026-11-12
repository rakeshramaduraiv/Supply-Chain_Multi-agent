"""
scripts/bootstrap.py
=====================
Bootstrap the AMASCI system from a clean clone.

Steps (in order):
  1. Verify raw CSV exists and is not an LFS pointer
  2. Run create_holdout_actuals.py to produce actuals CSVs + manifest
  3. POST /api/v1/initialization/run (holdout filter, features, graph, training)
  4. Verify registry.json lists >= 3 active models
  5. Verify processed_master.parquet max date <= 2017-09-30
  6. Print preflight result

Usage:
    python scripts/bootstrap.py
    make bootstrap
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_CSV = DATA / "raw" / "DataCoSupplyChainDataset.csv"
ACTUALS_DIR = DATA / "actuals_real"
REGISTRY = DATA / "models" / "registry.json"
PARQUET = DATA / "uploads" / "processed_master.parquet"

LFS_MAGIC = b"version https://git-lfs.github.com/spec/v1"

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
INFO = "\033[34m→\033[0m"


def _is_lfs(path: Path) -> bool:
    try:
        return path.open("rb").read(len(LFS_MAGIC)) == LFS_MAGIC
    except Exception:
        return False


def step(n: int, label: str) -> None:
    print(f"\n{INFO} Step {n}: {label}")


def ok(msg: str) -> None:
    print(f"  {PASS} {msg}")


def fail(msg: str) -> None:
    print(f"  {FAIL} {msg}")
    sys.exit(1)


def warn(msg: str) -> None:
    print(f"  \033[33m!\033[0m {msg}")


# ── Step 1: Verify raw CSV ────────────────────────────────────────────────────
step(1, "Verify raw CSV")
if not RAW_CSV.exists():
    fail(
        f"{RAW_CSV} not found.\n"
        "  Download from https://doi.org/10.17632/8gx2fvg2k6.5\n"
        "  and place at backend/data/raw/DataCoSupplyChainDataset.csv"
    )
if _is_lfs(RAW_CSV):
    fail(
        f"{RAW_CSV} is a Git LFS pointer ({RAW_CSV.stat().st_size} bytes).\n"
        "  Run: git lfs install && git lfs pull"
    )
size_mb = round(RAW_CSV.stat().st_size / 1_048_576, 1)
ok(f"DataCoSupplyChainDataset.csv present ({size_mb} MB)")

# ── Step 2: Create holdout actuals ────────────────────────────────────────────
step(2, "Create holdout actuals (create_holdout_actuals.py)")
manifest = ACTUALS_DIR / "holdout_manifest.csv"
actuals_exist = all(
    (ACTUALS_DIR / f"{p.replace('-', '_')}_actual.csv").exists()
    for p in ["2017-10", "2017-11", "2017-12", "2018-01"]
)
if manifest.exists() and not _is_lfs(manifest) and actuals_exist:
    ok("holdout_manifest.csv and 4 actuals CSVs already present — skipping")
else:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "create_holdout_actuals.py")],
        cwd=str(ROOT),
        capture_output=False,
    )
    if result.returncode != 0:
        fail("create_holdout_actuals.py failed — see output above")
    ok("Holdout actuals created")

# Verify actuals
for period in ["2017-10", "2017-11", "2017-12", "2018-01"]:
    f = ACTUALS_DIR / f"{period.replace('-', '_')}_actual.csv"
    if not f.exists():
        fail(f"Missing actuals file: {f}")
    if _is_lfs(f):
        fail(f"{f.name} is still an LFS pointer — run: git lfs pull")
    size_kb = round(f.stat().st_size / 1024, 0)
    ok(f"{f.name}: {size_kb:.0f} KB")

# ── Step 3: Run initialization ────────────────────────────────────────────────
step(3, "Run initialization (POST /api/v1/initialization/run)")
init_marker = DATA / "models" / ".initialized"
if init_marker.exists() and REGISTRY.exists() and PARQUET.exists():
    ok("System already initialized — skipping (delete data/models/.initialized to force re-run)")
else:
    print("  Calling initialization endpoint (this may take 5-15 minutes)…")
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://localhost:8000/api/v1/initialization/run",
            method="POST",
            headers={"Content-Type": "application/json"},
            data=b"{}",
        )
        with urllib.request.urlopen(req, timeout=900) as resp:
            body = json.loads(resp.read())
        ok(f"Initialization complete: {body.get('status', 'ok')}")
    except Exception as e:
        warn(f"HTTP call failed: {e}")
        warn("If the backend is not running, start it first: make dev")
        warn("Then re-run: make bootstrap")
        sys.exit(1)

# ── Step 4: Verify registry ───────────────────────────────────────────────────
step(4, "Verify registry.json lists >= 3 active models")
if not REGISTRY.exists():
    fail(f"{REGISTRY} not found — initialization may have failed")
reg = json.loads(REGISTRY.read_text())
active = [v for v in reg.get("versions", []) if v.get("status") == "active"]
if len(active) < 3:
    fail(f"Only {len(active)} active model(s) in registry — expected >= 3")
ok(f"{len(active)} active models: {[v.get('intelligence_type') for v in active]}")

# ── Step 5: Verify processed_master.parquet ───────────────────────────────────
step(5, "Verify processed_master.parquet max date <= 2017-09-30")
if not PARQUET.exists():
    fail(f"{PARQUET} not found")
if _is_lfs(PARQUET):
    fail(f"{PARQUET} is an LFS pointer")
try:
    import pandas as pd
    df = pd.read_parquet(PARQUET)
    if "order_date" in df.columns:
        max_date = str(df["order_date"].max())[:10]
        if max_date > "2017-09-30":
            fail(f"processed_master.parquet max_date={max_date} exceeds 2017-09-30 — holdout leak!")
        ok(f"processed_master.parquet: {len(df):,} rows, max_date={max_date}")
    else:
        ok(f"processed_master.parquet: {len(df):,} rows (order_date column not found)")
except Exception as e:
    fail(f"Could not read parquet: {e}")

# ── Step 6: Print preflight ───────────────────────────────────────────────────
step(6, "Preflight check (GET /api/v1/cycle/preflight)")
try:
    import urllib.request
    with urllib.request.urlopen("http://localhost:8000/api/v1/cycle/preflight", timeout=30) as resp:
        pf = json.loads(resp.read())
    print(f"\n  Summary: {pf.get('summary')}")
    for c in pf.get("checks", []):
        icon = PASS if c["passed"] else FAIL
        print(f"  {icon} {c['name']}: {c['detail']}")
        if not c["passed"]:
            print(f"       Fix: {c['remedy']}")
    if pf.get("ready"):
        print(f"\n{PASS} System ready. Run: make dev && cd frontend && npm run dev")
    else:
        print(f"\n{FAIL} System not ready. Resolve blocking issues above.")
        sys.exit(1)
except Exception as e:
    warn(f"Could not reach preflight endpoint: {e}")
    warn("Start the backend first: make dev")
