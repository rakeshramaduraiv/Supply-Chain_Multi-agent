"""
AMASCI Root Cause Analysis Intelligence Layer
================================================
Graph-driven root cause reasoning engine for supply chain disruptions.

Architecture:
    RCA Engine (orchestrator)
        ├── Graph Traversal (BFS, DFS, shortest path, k-hop)
        ├── Causal Analysis (causal chain construction)
        ├── Risk Contribution (weighted scoring)
        ├── Dependency Ranking (critical node identification)
        ├── Path Analysis (critical path, bottleneck detection)
        └── Report Generator (structured JSON reports)

Inputs: GraphRAG Context, Knowledge Graph, Prediction Results, TPKE Edges
Outputs: Structured RCA Reports with ranked causes and investigation paths
"""

from app.rca.engine import RCAEngine

__all__ = ["RCAEngine"]
