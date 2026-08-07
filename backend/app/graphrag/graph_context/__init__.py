"""
AMASCI GraphRAG Graph Context Service
========================================
Primary abstraction layer for all GraphRAG operations.
The rest of the project MUST interact with GraphRAG ONLY through this service.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from app.graph.connection import Neo4jConnectionManager, get_connection_manager
from app.graphrag.context_builder import ContextBuilder, StructuredContext
from app.graphrag.dependency_analysis import DependencyAnalyzer, DependencyResult, ImpactPropagation
from app.graphrag.embeddings import EmbeddingEngine
from app.graphrag.langchain import GraphRAGChain
from app.graphrag.memory import get_context_cache
from app.graphrag.query_engine import QueryEngine
from app.graphrag.retrieval import RetrievalEngine
from app.graphrag.subgraph import SubgraphEngine, SubgraphResult
from app.graphrag.utils import PerformanceTimer, utc_now_iso

logger = logging.getLogger(__name__)


class GraphContextService:
    """
    Primary abstraction layer for GraphRAG Intelligence.

    All external modules MUST use this service to access graph reasoning.
    Internal implementation (LangChain, embeddings, etc.) is hidden.

    Supports future replacement with Microsoft GraphRAG or LlamaIndex
    by maintaining a stable public interface.
    """

    def __init__(self, connection: Neo4jConnectionManager | None = None):
        conn = connection or get_connection_manager()
        self._retrieval = RetrievalEngine(conn)
        self._subgraph = SubgraphEngine(conn)
        self._dependency = DependencyAnalyzer(conn)
        self._context_builder = ContextBuilder(conn)
        self._embeddings = EmbeddingEngine()
        self._query_engine = QueryEngine(conn)
        self._chain = GraphRAGChain()
        self._cache = get_context_cache()
        self._history: list[dict[str, Any]] = []
        # Issue #5: TTL cache for get_agent_context (1-hour TTL)
        self._agent_ctx_cache: dict[tuple[str, str], tuple[dict, datetime]] = {}
        self._agent_ctx_ttl = timedelta(hours=1)
        # Issue #13: cold-start flag (set True once ACTIVE TPKE edges exist)
        self._warm_started: bool | None = None  # None = not yet checked

    # --- Context Retrieval (Primary Interface) ---

    async def get_context(
        self, entity_id: str, entity_label: str, context_type: str = "general"
    ) -> dict[str, Any]:
        """
        Get structured graph context for an entity.

        context_type: general | supplier | product | warehouse | shipment | forecast | risk
        """
        with PerformanceTimer(f"get_context({context_type})") as timer:
            if context_type == "supplier":
                ctx = await self._context_builder.build_supplier_context(entity_id)
            elif context_type == "product":
                ctx = await self._context_builder.build_product_context(entity_id)
            elif context_type == "warehouse":
                ctx = await self._context_builder.build_warehouse_context(entity_id)
            elif context_type == "shipment":
                ctx = await self._context_builder.build_shipment_context(entity_id)
            elif context_type == "forecast":
                ctx = await self._context_builder.build_forecast_context(entity_id, entity_label)
            elif context_type == "risk":
                ctx = await self._context_builder.build_risk_context(entity_id, entity_label)
            else:
                ctx = await self._build_general_context(entity_id, entity_label)

        result = ctx.to_dict()
        result["duration_ms"] = timer.duration_ms
        self._record_history("get_context", entity_id, context_type, timer.duration_ms)
        return result

    async def get_unified_context(
        self, entity_id: str, entity_label: str, query: str = ""
    ) -> dict[str, Any]:
        """Get 6-module unified context payload synthesized from 5 platform layers."""
        with PerformanceTimer("get_unified_context") as timer:
            from app.graphrag.context_builder.service import ContextBuilderService
            service = ContextBuilderService(self._retrieval._conn)
            payload = await service.build_unified_context(entity_id, entity_label, query)
            res = payload.to_dict()
        res["duration_ms"] = timer.duration_ms
        return res

    async def get_forecast_context(
        self, entity_id: str, entity_label: str
    ) -> dict[str, Any]:
        """Get graph-aware context for forecasting intelligence."""
        ctx = await self._context_builder.build_forecast_context(entity_id, entity_label)
        return ctx.to_dict()

    async def get_agent_context(
        self, category: str, region: str
    ) -> dict[str, Any]:
        """
        Returns a FLAT numeric context dict for direct ML feature injection.

        Issue #5: Results are cached per (category, region) for 1 hour.
        Issue #13: On cold start (no ACTIVE TPKE edges), TPKE-inferred edge
                   queries are skipped and a _cold_start flag is set.

        Every value is null-safe. Never returns None.
        """
        # ── Issue #5: TTL cache check ────────────────────────────────────────────
        cache_key = (category, region)
        if cache_key in self._agent_ctx_cache:
            cached_ctx, cached_at = self._agent_ctx_cache[cache_key]
            if datetime.now() - cached_at < self._agent_ctx_ttl:
                return cached_ctx

        # ── Issue #13: Cold-start check (lazy, cached after first query) ───────────
        if self._warm_started is None:
            try:
                warm_check = await self._retrieval._conn.execute_query(
                    "MATCH ()-[r:TPKE_INFERRED {status: 'ACTIVE'}]->() "
                    "RETURN count(r) AS cnt LIMIT 1"
                )
                self._warm_started = bool(warm_check and warm_check[0].get("cnt", 0) > 0)
            except Exception:
                self._warm_started = False
            if not self._warm_started:
                logger.info("GraphRAG cold start: no ACTIVE TPKE edges yet")

        cypher = """
        MATCH (p:Product {category: $category})
        OPTIONAL MATCH (s:Supplier)-[rs:SUPPLIES]->(p)
        OPTIONAL MATCH (p)-[:STORED_IN]->(w:Warehouse {location_region: $region})
        OPTIONAL MATCH (w)-[:SHIPS_VIA]->(sh:Shipment)
        OPTIONAL MATCH (ce:CalendarEvent)-[:INFLUENCES]->(p)
        OPTIONAL MATCH (ce2:CalendarEvent)-[r2:TPKE_INFERRED {status: 'ACTIVE'}]->(p)
            WHERE r2.relationship_type = 'SEASONAL_STOCKOUT_RISK'
        OPTIONAL MATCH (p)-[r3:TPKE_INFERRED {status: 'ACTIVE'}]->(sup2:Supplier)
            WHERE r3.relationship_type = 'DEMAND_SPIKE_AMPLIFIES_SUPPLIER_RISK'
        RETURN
            p.demand_volatility            AS demand_volatility,
            p.demand_trend_slope           AS demand_trend_slope,
            avg(s.reliability_score)       AS avg_supplier_reliability,
            avg(s.avg_delay_days)          AS avg_supplier_delay,
            w.avg_inventory_stress         AS inventory_stress,
            w.avg_days_to_reorder          AS days_to_reorder,
            avg(sh.shipping_delay)         AS avg_shipping_delay,
            collect(DISTINCT ce.event_name)[..3]  AS upcoming_events,
            collect(DISTINCT ce2.event_name)[..2] AS holiday_risk_events,
            count(DISTINCT sup2)           AS amplified_supplier_count
        LIMIT 1
        """

        try:
            records = await self._retrieval._conn.execute_query(
                cypher, {"category": category, "region": region}
            )
        except Exception as e:
            logger.warning(f"Agent context query failed for {category}/{region}: {e}")
            return self._default_agent_context(category, region)

        if not records:
            return self._default_agent_context(category, region)

        r = records[0]

        def _f(key: str, default: float) -> float:
            val = r.get(key)
            if val is None:
                return default
            try:
                f = float(val)
                if f != f or f in (float("inf"), float("-inf")):
                    return default
                return f
            except (TypeError, ValueError):
                return default

        def _list(key: str) -> list:
            val = r.get(key) or []
            return [v for v in val if v]

        upcoming     = _list("upcoming_events")
        holiday_risk = _list("holiday_risk_events")
        amplified    = int(r.get("amplified_supplier_count") or 0)

        result = {
            "summary": (
                f"'{category}' / '{region}': "
                f"supplier_reliability={_f('avg_supplier_reliability', 0.5):.3f}, "
                f"inventory_stress={_f('inventory_stress', 0.5):.3f}, "
                f"shipping_delay={_f('avg_shipping_delay', 0.0):.1f}d, "
                f"events={len(upcoming)}, tpke_edges={len(holiday_risk) + amplified}"
            ),
            "avg_supplier_reliability": _f("avg_supplier_reliability", 0.5),
            "avg_supplier_delay":       _f("avg_supplier_delay", 0.0),
            "inventory_stress":         _f("inventory_stress", 0.5),
            "days_to_reorder":          _f("days_to_reorder", 7.0),
            "avg_shipping_delay":       _f("avg_shipping_delay", 0.0),
            "demand_volatility":        _f("demand_volatility", 0.3),
            "demand_trend_slope":       _f("demand_trend_slope", 0.0),
            "upcoming_events":          upcoming,
            "holiday_risk_events":      holiday_risk,
            "amplified_supplier_count": amplified,
            "entities":                 [dict(r)],
            "_cold_start":              not self._warm_started,
        }

        # ── Issue #5: Store in TTL cache ────────────────────────────────────────────
        self._agent_ctx_cache[cache_key] = (result, datetime.now())
        return result

    def mark_warm_start(self) -> None:
        """Call after first ACTIVE TPKE edges are created (Issue #13)."""
        self._warm_started = True
        self._agent_ctx_cache.clear()  # Invalidate cache so next call reads TPKE edges
        logger.info("GraphRAG transitioned to warm start: TPKE edges now active")

    def clear_agent_context_cache(self) -> None:
        """Manually invalidate the agent context TTL cache (Issue #5)."""
        self._agent_ctx_cache.clear()

    @staticmethod
    def _default_agent_context(category: str, region: str) -> dict[str, Any]:
        """Neutral defaults. Never returns None — agents must not crash."""
        return {
            "summary": f"No graph context for '{category}' / '{region}'",
            "avg_supplier_reliability": 0.5,
            "avg_supplier_delay":       0.0,
            "inventory_stress":         0.5,
            "days_to_reorder":          7.0,
            "avg_shipping_delay":       0.0,
            "demand_volatility":        0.3,
            "demand_trend_slope":       0.0,
            "upcoming_events":          [],
            "holiday_risk_events":      [],
            "amplified_supplier_count": 0,
            "entities":                 [],
        }

    async def get_risk_context(
        self, entity_id: str, entity_label: str
    ) -> dict[str, Any]:
        """Get risk reasoning context."""
        ctx = await self._context_builder.build_risk_context(entity_id, entity_label)
        return ctx.to_dict()

    async def get_root_cause_context(
        self, entity_id: str, entity_label: str, issue_type: str
    ) -> dict[str, Any]:
        """Get context for root cause analysis support."""
        ctx = await self._context_builder.build_root_cause_context(
            entity_id, entity_label, issue_type
        )
        return ctx.to_dict()

    # --- Query Interface ---

    async def query(self, query_text: str) -> dict[str, Any]:
        """Execute query through the 12-stage Enterprise GraphRAG Pipeline."""
        with PerformanceTimer("enterprise_graphrag_pipeline") as timer:
            from app.graphrag.pipeline import EnterpriseGraphRAGPipeline
            pipeline = EnterpriseGraphRAGPipeline(self._retrieval._conn)
            pipeline_res = await pipeline.execute(query_text)
            result = pipeline_res.to_dict()

        result["total_duration_ms"] = timer.duration_ms
        self._record_history("query", query_text, result.get("intent", "general"), timer.duration_ms)
        return result

    async def query_structured(
        self,
        label: str | None = None,
        node_id: str | None = None,
        rel_type: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Execute a structured query."""
        return await self._query_engine.execute_structured(
            label=label, node_id=node_id, rel_type=rel_type, filters=filters, limit=limit
        )

    # --- Subgraph Interface ---

    async def get_subgraph(
        self, entity_id: str, entity_label: str, hops: int = 2
    ) -> dict[str, Any]:
        """Get subgraph around an entity."""
        with PerformanceTimer("get_subgraph") as timer:
            result = await self._subgraph.extract_subgraph(entity_id, entity_label, hops)

        output = result.to_dict()
        output["duration_ms"] = timer.duration_ms

        # Generate subgraph embedding
        if result.nodes:
            output["embedding"] = self._embeddings.embed_subgraph(result.nodes, result.edges)

        self._record_history("get_subgraph", entity_id, entity_label, timer.duration_ms)
        return output

    # --- Dependency Interface ---

    async def get_dependencies(
        self, entity_id: str, entity_label: str, max_depth: int = 3
    ) -> dict[str, Any]:
        """Get full dependency analysis for an entity."""
        with PerformanceTimer("get_dependencies") as timer:
            result = await self._dependency.analyze_dependencies(entity_id, entity_label, max_depth)

        output = result.to_dict()
        output["duration_ms"] = timer.duration_ms
        self._record_history("get_dependencies", entity_id, entity_label, timer.duration_ms)
        return output

    async def get_impact_propagation(
        self, entity_id: str, entity_label: str, initial_risk: float = 1.0
    ) -> dict[str, Any]:
        """Simulate impact propagation from an entity."""
        result = await self._dependency.propagate_impact(entity_id, entity_label, initial_risk)
        return result.to_dict()

    # --- Embedding Interface ---

    def get_entity_embedding(self, label: str, properties: dict[str, Any]) -> list[float]:
        """Get embedding vector for an entity."""
        return self._embeddings.embed_node(label, properties)

    def get_context_embedding(self, context: dict[str, Any]) -> list[float]:
        """Get embedding vector for a context object."""
        return self._embeddings.embed_context(context)

    def compute_similarity(self, embedding_a: list[float], embedding_b: list[float]) -> float:
        """Compute cosine similarity between two embeddings."""
        return self._embeddings.compute_similarity(embedding_a, embedding_b)

    # --- LLM Chain Interface ---

    def get_llm_prompt(
        self, entity_id: str, entity_label: str, context: dict[str, Any], chain_type: str = "context"
    ) -> dict[str, Any]:
        """Get LLM-ready prompt with graph context injected."""
        if chain_type == "context":
            return self._chain.build_context_chain(entity_id, entity_label, context)
        elif chain_type == "risk":
            return self._chain.build_risk_chain(
                entity_id, entity_label,
                context.get("issue_type", "general"),
                context.get("entity_state", {}),
                context.get("potential_causes", []),
                context.get("risk_neighborhood", {}),
            )
        elif chain_type == "forecast":
            return self._chain.build_forecast_chain(
                entity_id, entity_label,
                context.get("demand_signals", {}),
                context.get("supply_chain_context", {}),
                context.get("calendar_events", []),
                context.get("graph_features", {}),
            )
        return self._chain.build_context_chain(entity_id, entity_label, context)

    # --- Cache Interface ---

    def get_cache_statistics(self) -> dict[str, Any]:
        """Get cache performance statistics."""
        return self._cache.get_statistics()

    def invalidate_cache(self, prefix: str | None = None) -> int:
        """Invalidate cache entries."""
        if prefix:
            return self._cache.invalidate_prefix(prefix)
        self._cache.clear()
        return -1

    # --- History Interface ---

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent operation history."""
        return self._history[-limit:]

    def get_statistics(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "total_operations": len(self._history),
            "cache": self._cache.get_statistics(),
            "operation_breakdown": self._compute_operation_breakdown(),
        }

    # --- Internal ---

    async def _build_general_context(
        self, entity_id: str, entity_label: str
    ) -> StructuredContext:
        """Build general context when no specific type is requested."""
        entity = await self._retrieval.retrieve_entity(entity_id, entity_label)
        if not entity:
            return StructuredContext(
                context_type="general", entity_id=entity_id, entity_label=entity_label
            )

        relationships = await self._retrieval.retrieve_relationships(entity_id, entity_label)
        subgraph = await self._subgraph.extract_subgraph(entity_id, entity_label, hops=1)

        context = {
            "entity": entity,
            "relationships": relationships[:20],
            "subgraph_summary": {
                "node_count": subgraph.node_count,
                "edge_count": subgraph.edge_count,
                "risk_summary": subgraph.risk_summary,
            },
        }

        return StructuredContext(
            context_type="general",
            entity_id=entity_id,
            entity_label=entity_label,
            context=context,
            metadata={"relationship_count": len(relationships)},
        )

    def _record_history(
        self, operation: str, entity_id: str, detail: str, duration_ms: float
    ) -> None:
        """Record operation in history."""
        self._history.append({
            "operation": operation,
            "entity_id": entity_id,
            "detail": detail,
            "duration_ms": round(duration_ms, 2),
            "timestamp": utc_now_iso(),
        })
        # Keep history bounded
        if len(self._history) > 1000:
            self._history = self._history[-500:]

    def _compute_operation_breakdown(self) -> dict[str, int]:
        """Compute operation type counts."""
        breakdown: dict[str, int] = {}
        for entry in self._history:
            op = entry["operation"]
            breakdown[op] = breakdown.get(op, 0) + 1
        return breakdown
