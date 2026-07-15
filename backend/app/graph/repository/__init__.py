"""
AMASCI Graph Repository
=========================
CRUD operations for nodes and relationships against Neo4j.
"""

import logging
from typing import Any

from app.graph.connection import Neo4jConnectionManager
from app.graph.utils import utc_now_iso

logger = logging.getLogger(__name__)


class GraphRepository:
    """
    Data access layer for Knowledge Graph operations.

    Provides:
    - Create/Update/Delete nodes
    - Create/Update/Delete relationships
    - Fetch entity by ID
    - Fetch subgraph (neighborhood)
    - Query nodes by label with filters
    """

    def __init__(self, connection: Neo4jConnectionManager):
        self._conn = connection

    # --- Node Operations ---

    async def create_node(self, label: str, properties: dict[str, Any]) -> dict[str, Any] | None:
        """Create a node with MERGE (upsert)."""
        props_copy = {**properties, "updated_at": utc_now_iso()}
        if "created_at" not in props_copy:
            props_copy["created_at"] = utc_now_iso()

        set_clause = ", ".join(f"n.{k} = ${k}" for k in props_copy)
        query = f"""
            MERGE (n:{label} {{node_id: $node_id}})
            SET {set_clause}
            RETURN n {{.*}} AS node
        """
        records = await self._conn.execute_write(query, props_copy)
        return records[0]["node"] if records else None

    async def update_node(self, label: str, node_id: str, properties: dict[str, Any]) -> dict[str, Any] | None:
        """Update properties on an existing node."""
        props_copy = {**properties, "updated_at": utc_now_iso(), "node_id": node_id}
        set_clause = ", ".join(f"n.{k} = ${k}" for k in props_copy if k != "node_id")
        query = f"""
            MATCH (n:{label} {{node_id: $node_id}})
            SET {set_clause}
            RETURN n {{.*}} AS node
        """
        records = await self._conn.execute_write(query, props_copy)
        return records[0]["node"] if records else None

    async def delete_node(self, label: str, node_id: str) -> bool:
        """Delete a node and its relationships."""
        query = f"""
            MATCH (n:{label} {{node_id: $node_id}})
            DETACH DELETE n
            RETURN count(n) AS cnt
        """
        records = await self._conn.execute_write(query, {"node_id": node_id})
        deleted = records[0]["cnt"] > 0 if records else False
        if deleted:
            logger.info(f"Deleted {label} node: {node_id}")
        return deleted

    async def get_node(self, label: str, node_id: str) -> dict[str, Any] | None:
        """Fetch a single node by ID."""
        query = f"""
            MATCH (n:{label} {{node_id: $node_id}})
            RETURN n {{.*}} AS node
        """
        records = await self._conn.execute_query(query, {"node_id": node_id})
        return records[0]["node"] if records else None

    async def get_nodes(
        self, label: str, limit: int = 100, offset: int = 0, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Fetch nodes by label with optional filters."""
        where_parts = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if filters:
            for key, value in filters.items():
                param_name = f"f_{key}"
                where_parts.append(f"n.{key} = ${param_name}")
                params[param_name] = value

        where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        query = f"""
            MATCH (n:{label})
            {where_clause}
            RETURN n {{.*}} AS node
            ORDER BY n.node_id
            SKIP $offset LIMIT $limit
        """
        records = await self._conn.execute_query(query, params)
        return [r["node"] for r in records]

    # --- Relationship Operations ---

    async def create_relationship(
        self,
        source_label: str,
        source_id: str,
        target_label: str,
        target_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Create or update a relationship."""
        props = properties or {}
        props["updated_at"] = utc_now_iso()
        if "created_at" not in props:
            props["created_at"] = utc_now_iso()

        set_clause = ", ".join(f"r.{k} = ${k}" for k in props)
        query = f"""
            MATCH (a:{source_label} {{node_id: $source_id}})
            MATCH (b:{target_label} {{node_id: $target_id}})
            MERGE (a)-[r:{rel_type}]->(b)
            SET {set_clause}
            RETURN type(r) AS rel_type, r {{.*}} AS props
        """
        params = {"source_id": source_id, "target_id": target_id, **props}
        records = await self._conn.execute_write(query, params)
        return records[0] if records else None

    async def update_relationship(
        self,
        source_label: str,
        source_id: str,
        target_label: str,
        target_id: str,
        rel_type: str,
        properties: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Update relationship properties."""
        props = {**properties, "updated_at": utc_now_iso()}
        set_clause = ", ".join(f"r.{k} = ${k}" for k in props)
        query = f"""
            MATCH (a:{source_label} {{node_id: $source_id}})-[r:{rel_type}]->(b:{target_label} {{node_id: $target_id}})
            SET {set_clause}
            RETURN type(r) AS rel_type, r {{.*}} AS props
        """
        params = {"source_id": source_id, "target_id": target_id, **props}
        records = await self._conn.execute_write(query, params)
        return records[0] if records else None

    async def delete_relationship(
        self,
        source_label: str,
        source_id: str,
        target_label: str,
        target_id: str,
        rel_type: str,
    ) -> bool:
        """Delete a specific relationship."""
        query = f"""
            MATCH (a:{source_label} {{node_id: $source_id}})-[r:{rel_type}]->(b:{target_label} {{node_id: $target_id}})
            DELETE r
            RETURN count(r) AS cnt
        """
        records = await self._conn.execute_write(query, {"source_id": source_id, "target_id": target_id})
        return records[0]["cnt"] > 0 if records else False

    async def get_relationships(
        self, label: str, node_id: str, direction: str = "both"
    ) -> list[dict[str, Any]]:
        """Get all relationships for a node."""
        if direction == "outgoing":
            query = f"""
                MATCH (n:{label} {{node_id: $node_id}})-[r]->(m)
                RETURN type(r) AS rel_type, r {{.*}} AS props,
                       m.node_id AS target_id, labels(m)[0] AS target_label
            """
        elif direction == "incoming":
            query = f"""
                MATCH (m)-[r]->(n:{label} {{node_id: $node_id}})
                RETURN type(r) AS rel_type, r {{.*}} AS props,
                       m.node_id AS source_id, labels(m)[0] AS source_label
            """
        else:
            query = f"""
                MATCH (n:{label} {{node_id: $node_id}})-[r]-(m)
                RETURN type(r) AS rel_type, r {{.*}} AS props,
                       m.node_id AS connected_id, labels(m)[0] AS connected_label
            """
        records = await self._conn.execute_query(query, {"node_id": node_id})
        return records

    # --- Subgraph Operations ---

    async def fetch_subgraph(
        self, node_id: str, max_hops: int = 2, limit: int = 50
    ) -> dict[str, Any]:
        """Fetch a subgraph around a node (ego network)."""
        query = f"""
            MATCH path = (center {{node_id: $node_id}})-[*1..{max_hops}]-(neighbor)
            WITH center, neighbor, relationships(path) AS rels
            LIMIT $limit
            RETURN
                center {{.*}} AS center_node,
                collect(DISTINCT neighbor {{.*, label: labels(neighbor)[0]}}) AS neighbors,
                collect(DISTINCT {{
                    type: type(rels[0]),
                    source: startNode(rels[0]).node_id,
                    target: endNode(rels[0]).node_id
                }}) AS edges
        """
        records = await self._conn.execute_query(query, {"node_id": node_id, "limit": limit})
        if not records:
            return {"center_node": None, "neighbors": [], "edges": []}
        return records[0]

    async def fetch_entity(self, node_id: str) -> dict[str, Any] | None:
        """Fetch an entity with its immediate relationships."""
        query = """
            MATCH (n {node_id: $node_id})
            OPTIONAL MATCH (n)-[r]-(m)
            RETURN n {.*, label: labels(n)[0]} AS entity,
                   collect(DISTINCT {
                       rel_type: type(r),
                       connected_id: m.node_id,
                       connected_label: labels(m)[0],
                       direction: CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END
                   }) AS connections
        """
        records = await self._conn.execute_query(query, {"node_id": node_id})
        if not records:
            return None
        return {
            "entity": records[0]["entity"],
            "connections": records[0]["connections"],
        }
