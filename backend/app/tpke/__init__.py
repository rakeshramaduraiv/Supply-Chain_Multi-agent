"""
AMASCI TPKE — Temporal Pattern-Triggered Knowledge Graph Evolution
====================================================================
Novel algorithm: Dynamic graph evolution based on recurring temporal patterns
detected from forecast-vs-actual deviations.

Algorithm:
    w(e) = α·confidence(e) + β·frequency(e) + γ·temporal(e)
    where α + β + γ = 1

Pipeline:
    1. Ingest forecast results + actual uploads
    2. Detect temporal co-occurrence patterns (sliding window)
    3. Compute conditional probabilities between entities
    4. Filter by frequency threshold
    5. Apply edge decay to stale relationships
    6. Evolve graph: create/strengthen/decay/remove edges in Neo4j
    7. Persist TPKE history to PostgreSQL
    8. Return evolution report
"""

from app.tpke.engine import TPKEEngine
from app.tpke.pattern import PatternDetector
from app.tpke.edge_manager import EdgeManager

__all__ = ["TPKEEngine", "PatternDetector", "EdgeManager"]
