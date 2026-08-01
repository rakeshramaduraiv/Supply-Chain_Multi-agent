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
from app.graph.prediction_integration.routes import router as prediction_integration_router
from app.api.v1.endpoints.business import router as business_router
from app.api.v1.endpoints import live_ops
from app.api.v1.endpoints import rca_investigation

from app.graphrag.context_builder.routes import router as context_builder_router
from app.graphrag.prompt_routes import router as prompt_composer_router
from app.graphrag.copilot_routes import router as copilot_router
from app.api.v1.endpoints.decision_routes import router as decision_router
from app.ml.agent_memory.routes import router as agent_memory_router

api_router = APIRouter()

# --- Health & System ---
api_router.include_router(health.router, prefix="")
api_router.include_router(ws.router, prefix="")
api_router.include_router(context_builder_router, prefix="")
api_router.include_router(prompt_composer_router, prefix="")
api_router.include_router(decision_router, prefix="")
api_router.include_router(agent_memory_router, prefix="")

# --- Data Engineering ---
api_router.include_router(data_engineering.router, prefix="/data")

# --- Dataset Summary (real DataCo values, no DB needed) ---
api_router.include_router(dataset_summary.router, prefix="")

# --- Machine Learning ---
api_router.include_router(ml_router, prefix="")

# --- Knowledge Graph ---
api_router.include_router(graph_router, prefix="")
api_router.include_router(prediction_integration_router, prefix="/graph")

# --- GraphRAG Intelligence ---
api_router.include_router(graphrag_router, prefix="")
api_router.include_router(copilot_router, prefix="")


# --- Root Cause Analysis ---
api_router.include_router(rca_router, prefix="")
api_router.include_router(rca_investigation.router, prefix="")

# --- Dashboard Intelligence ---
api_router.include_router(dashboard_router, prefix="")

# --- Business Operations (Frontend-facing) ---
api_router.include_router(business_router, prefix="")
api_router.include_router(live_ops.router, prefix="")

# --- TPKE Evolution ---
api_router.include_router(tpke_router, prefix="")

# --- Administration / Initialization ---
api_router.include_router(initialization_router, prefix="")
