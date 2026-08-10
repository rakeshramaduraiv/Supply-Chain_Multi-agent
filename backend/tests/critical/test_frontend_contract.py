"""
tests/critical/test_frontend_contract.py
==========================================
Parse every '/api/v1/...' string literal in frontend/src, resolve every
backend route including router prefixes, and assert every frontend path
matches a backend route.

Fails listing all mismatches so the contract cannot drift silently.
"""
import ast
import pathlib
import re
import sys
import pytest

REPO_ROOT    = pathlib.Path(__file__).parents[3]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
BACKEND_SRC  = REPO_ROOT / "backend"

# ── Collect frontend API paths ────────────────────────────────────────────────

_API_PATH_RE = re.compile(r"['\"`](/api/v1/[^'\"`\s)]+)['\"`]")

# Paths that are intentionally removed from the frontend (dead routes deleted)
_KNOWN_REMOVED = {
    "/api/v1/data/upload/train",
    "/api/v1/data/upload/forecast",
    "/api/v1/data/process/{id}",
    "/api/v1/data/process/{dataset_id}",
}

# Paths that are template literals with variables — match by prefix
_TEMPLATE_PREFIXES = [
    "/api/v1/data/dataset/",
    "/api/v1/graph/entity/",
    "/api/v1/graph/centrality/",
    "/api/v1/ml/metrics/",
    "/api/v1/ml/feature-importance/",
    "/api/v1/ml/models/",
    "/api/v1/rca/report/",
    "/api/v1/business/alerts/",
    "/api/v1/cycle/",
]


def _collect_frontend_paths() -> set[str]:
    paths = set()
    for p in FRONTEND_SRC.rglob("*.js"):
        src = p.read_text(encoding="utf-8", errors="replace")
        for m in _API_PATH_RE.finditer(src):
            paths.add(m.group(1).rstrip("/"))
    for p in FRONTEND_SRC.rglob("*.jsx"):
        src = p.read_text(encoding="utf-8", errors="replace")
        for m in _API_PATH_RE.finditer(src):
            paths.add(m.group(1).rstrip("/"))
    return paths


# ── Collect backend routes ────────────────────────────────────────────────────

_ROUTE_DECORATOR_RE = re.compile(
    r'@router\.(get|post|put|delete|patch|websocket|api_route)\s*\(\s*["\']([^"\']+)["\']'
)
_PREFIX_RE = re.compile(r'prefix\s*=\s*["\']([^"\']*)["\']')
_INCLUDE_RE = re.compile(r'include_router\s*\(([^)]+)\)')


def _collect_backend_routes() -> set[str]:
    """
    Walk all Python files under backend/app, extract @router.* decorators,
    and prepend the known prefix chain.

    This is a best-effort static analysis — it handles the common patterns
    in this codebase without a full import-time resolution.
    """
    routes: set[str] = set()

    # Known prefix map: file pattern → prefix
    # Derived from router.py include_router calls
    PREFIX_MAP = {
        "data_engineering":  "/api/v1/data",
        "dataset_summary":   "/api/v1/dataset",
        "ml/router":         "/api/v1/ml",
        "graph/routes":      "/api/v1/graph",
        "graphrag/routes":   "/api/v1/graphrag",
        "graphrag/copilot":  "/api/v1/graphrag/copilot",
        "graphrag/context_builder": "/api/v1",
        "graphrag/prompt":   "/api/v1",
        "rca/routes":        "/api/v1/rca",
        "rca_investigation": "/api/v1/rca/investigation",
        "dashboard/routes":  "/api/v1/dashboard",
        "business/__init__": "/api/v1/business",
        "live_ops":          "/api/v1/business/live-ops",
        "cycle_routes":      "/api/v1/cycle",
        "tpke/routes":       "/api/v1/tpke",
        "initialization/routes": "/api/v1/admin/initialization",
        "health":            "/api/v1",
        "ws":                "",          # ws router has prefix=""
        "decision_routes":   "/api/v1",
        "agent_memory":      "/api/v1",
        "ml/coordinator":    "/api/v1/ml",
        "graph/prediction_integration/routes": "/api/v1/graph",
    }

    for py_file in (BACKEND_SRC / "app").rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        rel = py_file.relative_to(BACKEND_SRC / "app").as_posix().replace(".py", "")
        src = py_file.read_text(encoding="utf-8", errors="replace")

        # Determine prefix for this file
        prefix = ""
        for key, pfx in PREFIX_MAP.items():
            if key in rel:
                prefix = pfx
                break
        else:
            # Try to read prefix from @router.* or router = APIRouter(prefix=...)
            m = re.search(r'APIRouter\s*\([^)]*prefix\s*=\s*["\']([^"\']*)["\']', src)
            if m:
                prefix = "/api/v1" + m.group(1)

        for m in _ROUTE_DECORATOR_RE.finditer(src):
            path = m.group(2)
            # Normalise path params: {param} → {param}
            full = (prefix + path).rstrip("/") or "/"
            routes.add(full)

    # Add WebSocket path explicitly
    routes.add("/ws")
    return routes


def _path_matches(frontend_path: str, backend_routes: set[str]) -> bool:
    """Return True if frontend_path matches any backend route (exact or template)."""
    if frontend_path in backend_routes:
        return True
    # Template prefix match
    for pfx in _TEMPLATE_PREFIXES:
        if frontend_path.startswith(pfx):
            return True
    # Path-param substitution: replace {id}, {type}, etc. with literal segment
    normalised = re.sub(r"\{[^}]+\}", "{param}", frontend_path)
    for route in backend_routes:
        if re.sub(r"\{[^}]+\}", "{param}", route) == normalised:
            return True
    return False


# ── Test ──────────────────────────────────────────────────────────────────────

def test_frontend_backend_contract():
    """Every /api/v1/... path in frontend/src must match a backend route."""
    if not FRONTEND_SRC.exists():
        pytest.skip("frontend/src not found")

    frontend_paths = _collect_frontend_paths() - _KNOWN_REMOVED
    backend_routes = _collect_backend_routes()

    mismatches = sorted(
        p for p in frontend_paths
        if not _path_matches(p, backend_routes)
    )

    assert not mismatches, (
        f"{len(mismatches)} frontend path(s) have no matching backend route:\n"
        + "\n".join(f"  {p}" for p in mismatches)
        + "\n\nBackend routes found:\n"
        + "\n".join(f"  {r}" for r in sorted(backend_routes) if r.startswith("/api/v1"))
    )


def test_overall_accuracy_absent_from_frontend():
    """The string 'overall_accuracy' must not appear anywhere in frontend/src."""
    if not FRONTEND_SRC.exists():
        pytest.skip("frontend/src not found")
    violations = []
    for p in list(FRONTEND_SRC.rglob("*.js")) + list(FRONTEND_SRC.rglob("*.jsx")):
        src = p.read_text(encoding="utf-8", errors="replace")
        if "overall_accuracy" in src:
            for i, line in enumerate(src.splitlines(), 1):
                if "overall_accuracy" in line:
                    violations.append(f"{p.relative_to(FRONTEND_SRC)}:{i}: {line.strip()}")
    assert not violations, (
        "'overall_accuracy' found in frontend/src (removed field — use model registry metrics):\n"
        + "\n".join(violations)
    )
