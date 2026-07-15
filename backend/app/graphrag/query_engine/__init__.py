"""
AMASCI GraphRAG Query Engine
===============================
Natural language to Cypher translation, entity resolution, and structured queries.
"""

import logging
import re
from typing import Any

from app.graph.connection import Neo4jConnectionManager, get_connection_manager
from app.graphrag.memory import get_query_cache
from app.graphrag.utils import PerformanceTimer

logger = logging.getLogger(__name__)

# Entity label mappings for NL resolution
ENTITY_KEYWORDS = {
    "supplier": "Supplier",
    "suppliers": "Supplier",
    "vendor": "Supplier",
    "product": "Product",
    "products": "Product",
    "category": "Product",
    "warehouse": "Warehouse",
    "warehouses": "Warehouse",
    "storage": "Warehouse",
    "shipment": "Shipment",
    "shipments": "Shipment",
    "shipping": "Shipment",
    "delivery": "Shipment",
    "customer": "Customer",
    "customers": "Customer",
    "order": "Order",
    "orders": "Order",
    "calendar": "CalendarEvent",
    "event": "CalendarEvent",
    "holiday": "CalendarEvent",
}

RELATIONSHIP_KEYWORDS = {
    "supplies": "SUPPLIES",
    "supply": "SUPPLIES",
    "stored": "STORED_IN",
    "stores": "STORED_IN",
    "ships": "SHIPS_VIA",
    "shipped": "SHIPS_VIA",
    "delivered": "DELIVERED_TO",
    "delivers": "DELIVERED_TO",
    "placed": "PLACED",
    "contains": "CONTAINS",
    "influences": "INFLUENCES",
}

QUERY_INTENT_PATTERNS = {
    "risk": r"(?:risk|risky|dangerous|critical|vulnerable)",
    "performance": r"(?:performance|efficient|efficiency|delay|late|slow)",
    "connection": r"(?:connect|related|linked|associated|neighbor)",
    "path": r"(?:path|route|reach|between|from.*to)",
    "top": r"(?:top|best|worst|highest|lowest|most|least)",
    "count": r"(?:how many|count|total|number of)",
}


class QueryEngine:
    """
    GraphRAG query engine supporting natural language and structured queries.

    Provides:
    - Natural language query parsing
    - Cypher query generation
    - Entity resolution
    - Relationship resolution
    - Structured query execution
    """

    def __init__(self, connection: Neo4jConnectionManager | None = None):
        self._conn = connection or get_connection_manager()
        self._cache = get_query_cache()

    async def execute_natural_language(self, query: str) -> dict[str, Any]:
        """Parse and execute a natural language query against the graph."""
        cache_key = f"nlq:{query.lower().strip()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        with PerformanceTimer("execute_natural_language") as timer:
            # Parse intent and entities
            intent = self._detect_intent(query)
            entities = self._resolve_entities(query)
            relationships = self._resolve_relationships(query)

            # Generate Cypher
            cypher, params = self._generate_cypher(query, intent, entities, relationships)

            # Execute
            try:
                records = await self._conn.execute_query(cypher, params)
                result = {
                    "query": query,
                    "intent": intent,
                    "resolved_entities": entities,
                    "resolved_relationships": relationships,
                    "cypher": cypher,
                    "parameters": params,
                    "results": records,
                    "result_count": len(records),
                    "duration_ms": timer.duration_ms,
                }
            except Exception as e:
                logger.warning(f"NL query execution failed: {e}")
                result = {
                    "query": query,
                    "intent": intent,
                    "resolved_entities": entities,
                    "cypher": cypher,
                    "parameters": params,
                    "results": [],
                    "result_count": 0,
                    "error": str(e),
                    "duration_ms": timer.duration_ms,
                }

        self._cache.set(cache_key, result)
        return result

    async def execute_structured(
        self,
        label: str | None = None,
        node_id: str | None = None,
        rel_type: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Execute a structured query with explicit parameters."""
        with PerformanceTimer("execute_structured") as timer:
            if node_id and label:
                cypher = f"""
                    MATCH (n:{label} {{node_id: $node_id}})
                    OPTIONAL MATCH (n)-[r]-(m)
                    RETURN n {{.*}} AS entity,
                           collect({{
                               rel_type: type(r),
                               connected_id: m.node_id,
                               connected_label: labels(m)[0]
                           }})[0..$limit] AS connections
                """
                params: dict[str, Any] = {"node_id": node_id, "limit": limit}
            elif label and rel_type:
                cypher = f"""
                    MATCH (n:{label})-[r:{rel_type}]-(m)
                    RETURN n.node_id AS source_id, type(r) AS rel_type,
                           m.node_id AS target_id, labels(m)[0] AS target_label
                    LIMIT $limit
                """
                params = {"limit": limit}
            elif label:
                where_parts = []
                params = {"limit": limit}
                if filters:
                    for key, value in filters.items():
                        param_name = f"f_{key}"
                        where_parts.append(f"n.{key} = ${param_name}")
                        params[param_name] = value
                where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
                cypher = f"""
                    MATCH (n:{label})
                    {where_clause}
                    RETURN n {{.*}} AS node
                    LIMIT $limit
                """
            else:
                cypher = "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count"
                params = {}

            records = await self._conn.execute_query(cypher, params)

        return {
            "cypher": cypher,
            "parameters": params,
            "results": records,
            "result_count": len(records),
            "duration_ms": timer.duration_ms,
        }

    async def translate_to_cypher(self, query: str) -> dict[str, Any]:
        """Translate a natural language query to Cypher without executing."""
        intent = self._detect_intent(query)
        entities = self._resolve_entities(query)
        relationships = self._resolve_relationships(query)
        cypher, params = self._generate_cypher(query, intent, entities, relationships)
        return {
            "query": query,
            "intent": intent,
            "entities": entities,
            "relationships": relationships,
            "cypher": cypher,
            "parameters": params,
        }

    def resolve_entity(self, text: str) -> str | None:
        """Resolve a text fragment to a graph entity label."""
        text_lower = text.lower().strip()
        return ENTITY_KEYWORDS.get(text_lower)

    def resolve_relationship(self, text: str) -> str | None:
        """Resolve a text fragment to a relationship type."""
        text_lower = text.lower().strip()
        return RELATIONSHIP_KEYWORDS.get(text_lower)

    def _detect_intent(self, query: str) -> str:
        """Detect the primary intent of a query."""
        query_lower = query.lower()
        for intent, pattern in QUERY_INTENT_PATTERNS.items():
            if re.search(pattern, query_lower):
                return intent
        return "general"

    def _resolve_entities(self, query: str) -> list[str]:
        """Resolve all entity labels mentioned in a query."""
        resolved = []
        query_lower = query.lower()
        for keyword, label in ENTITY_KEYWORDS.items():
            if keyword in query_lower and label not in resolved:
                resolved.append(label)
        return resolved

    def _resolve_relationships(self, query: str) -> list[str]:
        """Resolve all relationship types mentioned in a query."""
        resolved = []
        query_lower = query.lower()
        for keyword, rel_type in RELATIONSHIP_KEYWORDS.items():
            if keyword in query_lower and rel_type not in resolved:
                resolved.append(rel_type)
        return resolved

    def _generate_cypher(
        self,
        query: str,
        intent: str,
        entities: list[str],
        relationships: list[str],
    ) -> tuple[str, dict[str, Any]]:
        """Generate Cypher query from parsed intent and entities."""
        params: dict[str, Any] = {"limit": 25}

        if intent == "count" and entities:
            label = entities[0]
            return f"MATCH (n:{label}) RETURN count(n) AS count", {}

        if intent == "risk" and entities:
            label = entities[0]
            return f"""
                MATCH (n:{label})
                WHERE coalesce(n.risk_score, n.late_delivery_rate, n.warehouse_risk, 0) > 0.5
                RETURN n {{.*}} AS node,
                       coalesce(n.risk_score, n.late_delivery_rate, n.warehouse_risk, 0) AS risk
                ORDER BY risk DESC
                LIMIT $limit
            """, params

        if intent == "top" and entities:
            label = entities[0]
            return f"""
                MATCH (n:{label})-[r]-()
                WITH n, count(r) AS connections
                RETURN n {{.*}} AS node, connections
                ORDER BY connections DESC
                LIMIT $limit
            """, params

        if intent == "path" and len(entities) >= 2:
            return """
                MATCH (a:%s), (b:%s)
                WITH a, b LIMIT 1
                MATCH path = shortestPath((a)-[*..5]-(b))
                RETURN [n IN nodes(path) | {node_id: n.node_id, label: labels(n)[0]}] AS path_nodes,
                       length(path) AS hops
            """ % (entities[0], entities[1]), {}

        if intent == "connection" and entities:
            label = entities[0]
            return f"""
                MATCH (n:{label})-[r]-(m)
                RETURN n.node_id AS source, type(r) AS rel_type,
                       m.node_id AS target, labels(m)[0] AS target_label
                LIMIT $limit
            """, params

        if intent == "performance" and entities:
            label = entities[0]
            return f"""
                MATCH (n:{label})
                RETURN n {{.*}} AS node
                ORDER BY coalesce(n.shipping_efficiency_score, n.supplier_reliability_score, 0) DESC
                LIMIT $limit
            """, params

        # Default: return nodes of first entity type
        if entities:
            label = entities[0]
            return f"MATCH (n:{label}) RETURN n {{.*}} AS node LIMIT $limit", params

        # Fallback: graph overview
        return """
            MATCH (n)
            RETURN labels(n)[0] AS label, count(n) AS count
            ORDER BY count DESC
        """, {}
