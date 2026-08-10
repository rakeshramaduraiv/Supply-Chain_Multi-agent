"""
backend/app/api/v1/endpoints/neo4j_explorer.py
"""
from __future__ import annotations
import asyncio, logging, os
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Query
from typing import Optional

logger   = logging.getLogger(__name__)
router   = APIRouter(tags=["Neo4j Explorer"])
_executor = ThreadPoolExecutor(max_workers=2)


def _run(cypher: str, params: dict = None):
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI",      "bolt://neo4j:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"),
              os.getenv("NEO4J_PASSWORD", "neo4j_dev_pass")),
    )
    try:
        with driver.session() as s:
            return [dict(r) for r in s.run(cypher, **(params or {}))]
    finally:
        driver.close()


# ── Overview ──────────────────────────────────────────────────────────────────

@router.get("/neo4j/overview")
async def neo4j_overview():
    def _sync():
        label_rows = _run("CALL db.labels() YIELD label RETURN label ORDER BY label")
        labels = {}
        for r in label_rows:
            lbl = r["label"]
            if lbl.startswith("_"):
                continue
            cnt = _run(f"MATCH (n:{lbl}) RETURN count(n) AS cnt")[0]["cnt"]
            labels[lbl] = cnt
        rel_rows = _run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType")
        rels = {}
        for r in rel_rows:
            rt  = r["relationshipType"]
            cnt = _run(f"MATCH ()-[r:{rt}]->() RETURN count(r) AS cnt")[0]["cnt"]
            rels[rt] = cnt
        return {"label_counts": labels, "rel_counts": rels,
                "total_nodes": sum(labels.values()), "total_edges": sum(rels.values())}
    try:
        return await asyncio.get_running_loop().run_in_executor(_executor, _sync)
    except Exception as e:
        logger.warning(f"neo4j_overview failed: {e}")
        return {"label_counts": {}, "rel_counts": {}, "total_nodes": 0, "total_edges": 0, "error": str(e)}


# ── Browse nodes by label ─────────────────────────────────────────────────────

@router.get("/neo4j/nodes/{label}")
async def get_nodes_by_label(
    label:   str,
    limit:   int           = Query(default=50, le=500),
    skip:    int           = Query(default=0,  ge=0),
    sort_by: Optional[str] = Query(default=None),
):
    def _sync():
        order = f"ORDER BY n.{sort_by} DESC" if sort_by else ""
        rows  = _run(f"""
            MATCH (n:{label})
            RETURN n, coalesce(n.node_id, n.entity_id, toString(id(n))) AS nid
            {order} SKIP $skip LIMIT $limit
        """, {"skip": skip, "limit": limit})
        total = _run(f"MATCH (n:{label}) RETURN count(n) AS cnt")[0]["cnt"]
        nodes = [{"id": r["nid"], "label": label, "properties": dict(r["n"])} for r in rows]
        return {"nodes": nodes, "total": total, "skip": skip, "limit": limit}
    try:
        return await asyncio.get_running_loop().run_in_executor(_executor, _sync)
    except Exception as e:
        logger.warning(f"get_nodes_by_label failed: {e}")
        return {"nodes": [], "total": 0, "error": str(e)}


# ── Node relationships ────────────────────────────────────────────────────────

@router.get("/neo4j/node/{node_id}/relationships")
async def get_node_relationships(node_id: str, limit: int = Query(default=100, le=500)):
    def _sync():
        rows = _run("""
            MATCH (n)-[r]-(m)
            WHERE coalesce(n.node_id, n.entity_id, toString(id(n))) = $nid
            RETURN type(r) AS rel_type,
                   labels(m)[0] AS target_label,
                   coalesce(m.node_id, m.entity_id, toString(id(m))) AS target_id,
                   properties(m) AS target_props,
                   properties(r) AS rel_props,
                   startNode(r) = n AS is_outgoing
            ORDER BY type(r)
            LIMIT $limit
        """, {"nid": node_id, "limit": limit})
        return {"node_id": node_id, "relationships": rows}
    try:
        return await asyncio.get_running_loop().run_in_executor(_executor, _sync)
    except Exception as e:
        logger.warning(f"get_node_relationships failed: {e}")
        return {"node_id": node_id, "relationships": [], "error": str(e)}


# ── Search ────────────────────────────────────────────────────────────────────

@router.get("/neo4j/search")
async def search_nodes(
    q:     str            = Query(..., min_length=1),
    label: Optional[str]  = Query(default=None),
    limit: int            = Query(default=50, le=200),
):
    def _sync():
        lf   = f":{label}" if label else ""
        rows = _run(f"""
            MATCH (n{lf})
            WHERE any(prop IN keys(n) WHERE toString(n[prop]) CONTAINS $q)
            RETURN coalesce(n.node_id, n.entity_id, toString(id(n))) AS id,
                   labels(n)[0] AS label, properties(n) AS props
            LIMIT $limit
        """, {"q": q, "limit": limit})
        return {"results": rows, "query": q}
    try:
        return await asyncio.get_running_loop().run_in_executor(_executor, _sync)
    except Exception as e:
        logger.warning(f"search_nodes failed: {e}")
        return {"results": [], "query": q, "error": str(e)}


# ── Subgraph ──────────────────────────────────────────────────────────────────

@router.get("/neo4j/subgraph")
async def get_subgraph(label: str = Query(...), limit: int = Query(default=80, le=300)):
    def _sync():
        n_rows = _run(f"""
            MATCH (n:{label})
            OPTIONAL MATCH (n)-[r]-()
            WITH n, count(r) AS deg
            RETURN coalesce(n.node_id, n.entity_id, toString(id(n))) AS id,
                   labels(n)[0] AS label, deg, properties(n) AS props
            LIMIT $limit
        """, {"limit": limit})
        e_rows = _run(f"""
            MATCH (n:{label})-[r]-(m)
            WHERE NOT m:{label} OR id(n) < id(m)
            RETURN coalesce(n.node_id, n.entity_id, toString(id(n))) AS source,
                   coalesce(m.node_id, m.entity_id, toString(id(m))) AS target,
                   type(r) AS type, labels(m)[0] AS target_label
            LIMIT $limit
        """, {"limit": limit * 2})
        return {
            "nodes": [{"id": r["id"], "label": r["label"], "degree": r["deg"], "properties": r["props"]} for r in n_rows],
            "edges": [{"source": r["source"], "target": r["target"], "type": r["type"], "target_label": r["target_label"]} for r in e_rows],
        }
    try:
        return await asyncio.get_running_loop().run_in_executor(_executor, _sync)
    except Exception as e:
        logger.warning(f"get_subgraph failed: {e}")
        return {"nodes": [], "edges": [], "error": str(e)}
