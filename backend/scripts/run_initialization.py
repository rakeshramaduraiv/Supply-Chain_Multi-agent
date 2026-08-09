"""
run_initialization.py
---------------------
CLI entrypoint for AMASCI system initialization with Neo4j enrichment.

Usage (from repo root or backend/):
    python -m backend.scripts.run_initialization --force
    python -m scripts.run_initialization --force

--force   Delete data/models/.initialized before running so the pipeline
          executes even if a previous run completed.

Steps performed:
  1. Load .env.development explicitly BEFORE importing settings.
  2. Assert neo4j_password != config default (proves env file loaded).
  3. Ping Neo4j with RETURN 1 — abort if unreachable.
  4. Set ALLOW_ENRICHMENT_FALLBACK=False so enrichment failure aborts.
  5. Delete data/models/.initialized when --force is passed.
  6. Call InitializationService.execute() and print each step's status.
  7. Print graph_enriched flag and metrics from registry.json.
"""

import argparse
import asyncio
import io
import json
import os
import sys
from pathlib import Path

# Force UTF-8 stdout on Windows (cp1252 can't encode →, ─, etc.)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Locate repo root and backend dir ─────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent          # backend/scripts/
_BACKEND_DIR = _SCRIPT_DIR.parent                      # backend/
_REPO_ROOT   = _BACKEND_DIR.parent                     # supply-chain/

# Ensure backend/ is on sys.path so `app.*` imports resolve
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# ── Step 1: Load .env.development BEFORE importing settings ──────────────────
_ENV_FILE = _REPO_ROOT / ".env.development"
if not _ENV_FILE.exists():
    print(f"[ABORT] .env.development not found at {_ENV_FILE}", flush=True)
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("[ABORT] python-dotenv is not installed. Run: pip install python-dotenv", flush=True)
    sys.exit(1)

load_dotenv(_ENV_FILE, override=True)

# Force ALLOW_ENRICHMENT_FALLBACK=False for this run (Step 4)
os.environ["ALLOW_ENRICHMENT_FALLBACK"] = "false"

# ── Step 2: Import settings and assert credentials loaded ─────────────────────
from app.core.config import get_settings  # noqa: E402 — must be after load_dotenv

settings = get_settings()

_CONFIG_DEFAULT_PASSWORD = "neo4j_password"
if settings.neo4j_password == _CONFIG_DEFAULT_PASSWORD:
    print(
        "[ABORT] settings.neo4j_password is still the config default "
        f"('{_CONFIG_DEFAULT_PASSWORD}'). "
        f".env.development was not loaded correctly.\n"
        f"  Expected env file: {_ENV_FILE}\n"
        f"  NEO4J_PASSWORD in that file: neo4j_dev_pass",
        flush=True,
    )
    sys.exit(1)

print(f"[OK] Credentials loaded — neo4j_password != config default", flush=True)
print(f"     neo4j_uri      : {settings.neo4j_uri}", flush=True)
print(f"     neo4j_user     : {settings.neo4j_user}", flush=True)
print(f"     allow_enrichment_fallback: {settings.allow_enrichment_fallback}", flush=True)


# ── Step 3: Ping Neo4j ────────────────────────────────────────────────────────
async def _ping_neo4j() -> bool:
    from app.graph.connection import Neo4jConnectionManager
    mgr = Neo4jConnectionManager()
    try:
        await mgr.connect()
        ok = await mgr.health_check()
        await mgr.disconnect()
        return ok
    except Exception as e:
        print(f"[ABORT] Neo4j unreachable: {e}", flush=True)
        return False


print("\n[...] Pinging Neo4j...", flush=True)
reachable = asyncio.run(_ping_neo4j())
if not reachable:
    print(
        "[ABORT] Neo4j did not respond to RETURN 1.\n"
        "  Start it with: docker compose -f docker-compose.dev.yml up -d neo4j\n"
        "  Then re-run this script.",
        flush=True,
    )
    sys.exit(1)

print("[OK] Neo4j reachable", flush=True)


# ── Argument parsing ──────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="AMASCI initialization CLI")
parser.add_argument(
    "--force",
    action="store_true",
    help="Delete .initialized sentinel so the pipeline runs unconditionally",
)
args = parser.parse_args()


# ── Step 5: Delete .initialized if --force ───────────────────────────────────
_INITIALIZED_SENTINEL = Path(settings.model_dir) / ".initialized"
if args.force and _INITIALIZED_SENTINEL.exists():
    _INITIALIZED_SENTINEL.unlink()
    print(f"[OK] Deleted {_INITIALIZED_SENTINEL}", flush=True)
elif not args.force and _INITIALIZED_SENTINEL.exists():
    print(
        f"[WARN] {_INITIALIZED_SENTINEL} exists. Pass --force to re-run initialization.",
        flush=True,
    )
    # Still proceed — let the service decide


# ── Step 6: Run InitializationService ────────────────────────────────────────
print("\n[...] Running InitializationService.execute()...\n", flush=True)

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    stream=sys.stdout,
)

from app.initialization.service import InitializationService  # noqa: E402

async def _run_init() -> dict:
    svc = InitializationService()
    return await svc.execute()

result = asyncio.run(_run_init())

print("\n── Initialization result ──────────────────────────────────────────", flush=True)
print(f"  status : {result.get('status')}", flush=True)
if result.get("error"):
    print(f"  error  : {result['error']}", flush=True)

for step_name, step_data in result.get("steps", {}).items():
    status = step_data.get("status", "?")
    dur    = step_data.get("duration_ms", 0)
    reason = f"  ({step_data['reason']})" if step_data.get("reason") else ""
    print(f"  step [{step_name:25s}]  {status:12s}  {dur:8.1f} ms{reason}", flush=True)

if result.get("status") != "completed":
    print("\n[ABORT] Initialization did not complete — see errors above.", flush=True)
    sys.exit(1)


# ── Step 7: Print graph_enriched + metrics from registry.json ────────────────
_REGISTRY_PATH = Path(settings.model_dir) / "registry.json"
if not _REGISTRY_PATH.exists():
    print(f"\n[WARN] registry.json not found at {_REGISTRY_PATH}", flush=True)
    sys.exit(0)

registry = json.loads(_REGISTRY_PATH.read_text())

print("\n── Registry summary ───────────────────────────────────────────────", flush=True)

graph_enriched_summary: dict[str, bool] = {}
metrics_summary: dict[str, dict] = {}

for intel_type, versions in registry.items():
    if not versions:
        continue
    latest = versions[-1]
    ge     = latest.get("graph_enriched", False)
    m      = latest.get("metrics", {})
    graph_enriched_summary[intel_type] = ge
    metrics_summary[intel_type] = m

    r2   = m.get("r2_score",  m.get("r2",  None))
    mape = m.get("mape",      None)
    auc  = m.get("roc_auc",   m.get("auc", None))
    f1   = m.get("f1_score",  m.get("f1",  None))

    metric_str = ""
    if r2   is not None: metric_str += f"  r2={r2:.4f}"
    if mape is not None: metric_str += f"  mape={mape:.2f}%"
    if auc  is not None: metric_str += f"  auc={auc:.4f}"
    if f1   is not None: metric_str += f"  f1={f1:.4f}"

    print(
        f"  {intel_type:12s}  graph_enriched={str(ge):5s}{metric_str}",
        flush=True,
    )

# The two lines the prompt asks for
print("\n── Two-line summary ───────────────────────────────────────────────", flush=True)
ge_str = ", ".join(f"{k}: {v}" for k, v in graph_enriched_summary.items())
print(f"graph_enriched: {{{ge_str}}}", flush=True)

metric_parts = []
for intel_type, m in metrics_summary.items():
    r2  = m.get("r2_score", m.get("r2",  None))
    auc = m.get("roc_auc",  m.get("auc", None))
    if r2  is not None: metric_parts.append(f"{intel_type} r2 {r2:.4f}")
    if auc is not None: metric_parts.append(f"{intel_type} auc {auc:.4f}")
print(f"metrics:        {', '.join(metric_parts)}", flush=True)
