"""
AMASCI RCA Engine
===================
Main orchestrator for Root Cause Analysis pipeline.
"""

import logging
from typing import Any

from app.graph.connection import Neo4jConnectionManager, get_connection_manager
from app.rca.causal_analysis import CausalAnalysisEngine, CausalAnalysisResult
from app.rca.dependency_ranking import DependencyRankingEngine, DependencyRankingResult
from app.rca.graph_traversal import GraphTraversalEngine, TraversalResult
from app.rca.path_analysis import PathAnalysisEngine, PathAnalysisResult
from app.rca.report_generator import RCAReport, ReportGenerator
from app.rca.risk_contribution import RiskContributionEngine, ContributionResult
from app.rca.utils import PerformanceTimer, RCAType, utc_now_iso

logger = logging.getLogger(__name__)


class RCAEngine:
    """
    Root Cause Analysis orchestration engine.

    Pipeline:
    1. Retrieve graph context (via GraphRAG)
    2. Extract subgraph around disrupted entity
    3. Traverse dependency graph (BFS/DFS)
    4. Rank contributing nodes (risk contribution formula)
    5. Calculate risk contribution scores
    6. Generate causal chain
    7. Generate structured RCA report

    Inputs:
    - GraphRAG context
    - Knowledge Graph (Neo4j)
    - Prediction results
    - TPKE inferred edges

    Outputs:
    - Structured RCA Report
    - Risk contribution ranking
    - Causal chain
    - Investigation paths
    """

    def __init__(self, connection: Neo4jConnectionManager | None = None):
        conn = connection or get_connection_manager()
        self._conn = conn
        self._traversal = GraphTraversalEngine(conn)
        self._contribution = RiskContributionEngine(conn)
        self._ranking = DependencyRankingEngine(conn)
        self._path_analysis = PathAnalysisEngine(conn)
        self._causal = CausalAnalysisEngine(conn)
        self._report_gen = ReportGenerator()

    async def analyze(
        self,
        target_id: str,
        target_label: str,
        rca_type: str,
        max_depth: int = 3,
        top_n: int = 10,
    ) -> RCAReport:
        """
        Execute the full RCA pipeline.

        Args:
            target_id: Node ID of the disrupted entity
            target_label: Label of the disrupted entity
            rca_type: Type of disruption (from RCAType enum)
            max_depth: Maximum traversal depth
            top_n: Number of top contributors to return

        Returns:
            Complete structured RCA report
        """
        with PerformanceTimer("rca_full_pipeline") as timer:
            # Step 1: Traverse dependency graph
            logger.info(f"[RCA] Starting analysis for {target_label}:{target_id} ({rca_type})")
            traversal = await self._traversal.bfs(target_id, max_depth=max_depth)

            # Step 2: Rank dependencies
            ranking_result = await self._ranking.rank_dependencies(
                target_id, target_label, max_depth=max_depth, top_n=top_n
            )

            # Step 3: Compute risk contributions
            candidate_nodes = [
                {
                    "node_id": n.node_id,
                    "label": n.label,
                    "properties": n.properties,
                }
                for n in traversal.visited_nodes[:50]
            ]
            contribution_result = await self._contribution.compute_contributions(
                target_id, target_label, candidate_nodes, rca_type, top_n=top_n
            )

            # Step 4: Causal chain analysis
            causal_result = await self._causal.analyze_causality(
                target_id, target_label, rca_type, max_chains=3
            )

            # Step 5: Path analysis
            path_result = await self._path_analysis.analyze_paths(
                target_id, target_label, max_paths=5
            )

            # Step 6: Generate report
            report = self._report_gen.generate_report(
                target_id=target_id,
                target_label=target_label,
                rca_type=rca_type,
                causal_result=causal_result,
                contribution_result=contribution_result,
                ranking_result=ranking_result,
                path_result=path_result,
                total_duration_ms=timer.duration_ms,
            )

        report.duration_ms = timer.duration_ms
        logger.info(
            f"[RCA] Analysis complete: {report.report_id} "
            f"({timer.duration_ms:.0f}ms, confidence={report.overall_confidence:.2f})"
        )
        return report

    async def get_subgraph(
        self, target_id: str, target_label: str, hops: int = 2
    ) -> dict[str, Any]:
        """Get the RCA-relevant subgraph around a disrupted entity."""
        traversal = await self._traversal.bfs(target_id, max_depth=hops)
        return traversal.to_dict()

    async def get_path(
        self, source_id: str, target_id: str
    ) -> dict[str, Any]:
        """Get shortest path between two nodes for RCA investigation."""
        traversal = await self._traversal.shortest_path(source_id, target_id)
        return traversal.to_dict()

    async def get_weighted_path(
        self, source_id: str, target_id: str
    ) -> dict[str, Any]:
        """Get weighted shortest path (minimum cost) between two nodes."""
        traversal = await self._traversal.weighted_shortest_path(source_id, target_id)
        return traversal.to_dict()
