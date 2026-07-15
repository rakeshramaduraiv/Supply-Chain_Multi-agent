"""
AMASCI API v1 Router
=====================
Aggregates all v1 endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health
from app.api.v1.endpoints import ws
from app.api.v1.endpoints import data_engineering
from app.api.v1.endpoints import dataset_summary
from app.api.v1.endpoints.ml.router import router as ml_router
from app.graph.routes import router as graph_router
from app.graphrag.routes import router as graphrag_router
from app.rca.routes import router as rca_router
from app.dashboard.routes import router as dashboard_router
from app.initialization.routes import router as initialization_router
from app.tpke.routes import router as tpke_router
from app.api.v1.endpoints.business import router as business_router

api_router = APIRouter()

# --- Health & System ---
api_router.include_router(health.router, prefix="")
api_router.include_router(ws.router, prefix="")

# --- Data Engineering ---
api_router.include_router(data_engineering.router, prefix="/data")

# --- Dataset Summary (real DataCo values, no DB needed) ---
api_router.include_router(dataset_summary.router, prefix="")

# --- Machine Learning ---
api_router.include_router(ml_router, prefix="")

# --- Knowledge Graph ---
api_router.include_router(graph_router, prefix="")

# --- GraphRAG Intelligence ---
api_router.include_router(graphrag_router, prefix="")

# --- Root Cause Analysis ---
api_router.include_router(rca_router, prefix="")

# --- Dashboard Intelligence ---
api_router.include_router(dashboard_router, prefix="")

# --- Business Operations (Frontend-facing) ---
api_router.include_router(business_router, prefix="")

# --- TPKE Evolution ---
api_router.include_router(tpke_router, prefix="")

# --- Administration / Initialization ---
api_router.include_router(initialization_router, prefix="")
