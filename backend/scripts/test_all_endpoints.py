"""
AMASCI Frontend Integration Test Script
=======================================
Hits every API endpoint that the React frontend calls,
reports status codes, and flags any failures.
"""
import asyncio
import httpx
import json
import sys
from datetime import datetime

BASE = "http://localhost:8000"

ENDPOINTS = [
    # Health
    ("GET",  "/api/v1/health",                    "Health Check"),
    # Dataset
    ("GET",  "/api/v1/dataset/summary",           "Dataset Summary"),
    ("GET",  "/api/v1/dataset/analytics",         "Dataset Analytics"),
    # Dashboard
    ("GET",  "/api/v1/dashboard",                 "Dashboard KPIs"),
    ("GET",  "/api/v1/dashboard/kpis",            "Dashboard KPIs v2"),
    ("GET",  "/api/v1/dashboard/forecast",        "Dashboard Forecast"),
    ("GET",  "/api/v1/dashboard/risk",            "Dashboard Risk"),
    ("GET",  "/api/v1/dashboard/graph",           "Dashboard Graph"),
    # ML
    ("GET",  "/api/v1/ml/models",                 "ML Models List"),
    ("GET",  "/api/v1/ml/status",                 "ML Status"),
    # Graph
    ("GET",  "/api/v1/graph/statistics",          "Graph Statistics"),
    ("GET",  "/api/v1/graph/nodes",               "Graph Nodes"),
    ("GET",  "/api/v1/graph/schema",              "Graph Schema"),
    ("GET",  "/api/v1/graph/subgraph",            "Graph Subgraph"),
    ("GET",  "/api/v1/graph/dashboard",           "Graph Dashboard"),
    # TPKE
    ("GET",  "/api/v1/tpke/status",               "TPKE Status"),
    ("GET",  "/api/v1/tpke/edges",                "TPKE Edges"),
    ("GET",  "/api/v1/tpke/summary",              "TPKE Summary"),
    ("GET",  "/api/v1/tpke/history",              "TPKE History"),
    # RCA
    ("GET",  "/api/v1/rca/statistics",            "RCA Statistics"),
    ("GET",  "/api/v1/rca/latest",                "RCA Latest"),
    ("GET",  "/api/v1/rca/history",               "RCA History"),
    # GraphRAG
    ("GET",  "/api/v1/graphrag/stats",            "GraphRAG Stats"),
    ("GET",  "/api/v1/graphrag/cache",            "GraphRAG Cache"),
    # Business
    ("GET",  "/api/v1/business/dashboard",        "Business Dashboard"),
    ("GET",  "/api/v1/business/system",           "Business System"),
    ("GET",  "/api/v1/business/forecast",         "Business Forecast"),
    ("GET",  "/api/v1/business/graph",            "Business Graph"),
    ("GET",  "/api/v1/business/analytics",        "Business Analytics"),
    ("GET",  "/api/v1/business/intelligence",     "Business Intelligence"),
    ("GET",  "/api/v1/business/incident",         "Business Incident"),
    ("GET",  "/api/v1/business/alerts",           "Business Alerts"),
    # Admin
    ("GET",  "/api/v1/admin/initialization/status","Admin Init Status"),
]


async def main():
    passed = 0
    failed = 0
    errors = []

    print("=" * 70)
    print(f"  AMASCI API INTEGRATION TEST — {datetime.now().isoformat()}")
    print("=" * 70)
    print()

    async with httpx.AsyncClient(base_url=BASE, timeout=15.0) as client:
        for method, path, label in ENDPOINTS:
            try:
                if method == "GET":
                    r = await client.get(path)
                else:
                    r = await client.post(path)

                status = r.status_code
                ok = 200 <= status < 400

                tag = "PASS" if ok else "FAIL"
                symbol = "[OK]" if ok else "[FAIL]"
                print(f"  {symbol} [{status}] {label:40s}  {path}")

                if ok:
                    passed += 1
                else:
                    failed += 1
                    body = r.text[:200]
                    errors.append((label, path, status, body))
            except Exception as e:
                failed += 1
                print(f"  [FAIL] [ERR] {label:40s}  {path}  -> {e}")
                errors.append((label, path, "EXCEPTION", str(e)[:200]))

    print()
    print("-" * 70)
    print(f"  TOTAL: {passed + failed}  |  PASSED: {passed}  |  FAILED: {failed}")
    print("-" * 70)

    if errors:
        print()
        print("  FAILURES:")
        for label, path, status, body in errors:
            print(f"    [{status}] {label}  ({path})")
            print(f"           {body}")
            print()

    # Exit with non-zero if failures
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
