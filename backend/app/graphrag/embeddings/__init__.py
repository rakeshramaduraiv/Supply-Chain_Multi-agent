"""
AMASCI GraphRAG Embeddings
=============================
Node, relationship, subgraph, and context embeddings for vector similarity.
Supports future vector database integration.
"""

import hashlib
import logging
import math
from typing import Any

from app.graphrag.memory import get_embedding_cache
from app.graphrag.utils import build_node_signature, flatten_properties, PerformanceTimer

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 64


class EmbeddingEngine:
    """
    Graph embedding engine for GraphRAG.

    Generates lightweight deterministic embeddings from graph structure and properties.
    Uses feature hashing for consistent dimensionality without external ML models.

    Supports:
    - Node embeddings (property-based)
    - Relationship embeddings (type + properties)
    - Subgraph embeddings (aggregated node embeddings)
    - Context embeddings (structured context → vector)
    - Future vector DB integration via standard interface
    """

    def __init__(self, dimension: int = EMBEDDING_DIM):
        self._dim = dimension
        self._cache = get_embedding_cache()

    def embed_node(self, label: str, properties: dict[str, Any]) -> list[float]:
        """Generate embedding for a single node."""
        node_id = properties.get("node_id", "")
        cache_key = f"emb:node:{node_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        signature = build_node_signature(label, properties)
        embedding = self._hash_embed(signature)

        # Incorporate numeric properties as signal
        numeric_features = self._extract_numeric_features(properties)
        if numeric_features:
            for i, val in enumerate(numeric_features[:self._dim // 2]):
                idx = (self._dim // 2) + (i % (self._dim // 2))
                embedding[idx] = val

        embedding = self._normalize(embedding)
        self._cache.set(cache_key, embedding)
        return embedding

    def embed_relationship(
        self, rel_type: str, properties: dict[str, Any], source_label: str = "", target_label: str = ""
    ) -> list[float]:
        """Generate embedding for a relationship."""
        signature = f"[REL:{rel_type}] {source_label}->{target_label}"
        for key, value in sorted(properties.items()):
            if key not in ("created_at", "updated_at"):
                signature += f" | {key}={value}"

        embedding = self._hash_embed(signature)
        numeric_features = self._extract_numeric_features(properties)
        if numeric_features:
            for i, val in enumerate(numeric_features[:self._dim // 4]):
                idx = (3 * self._dim // 4) + (i % (self._dim // 4))
                embedding[idx] = val

        return self._normalize(embedding)

    def embed_subgraph(self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[float]:
        """Generate embedding for a subgraph by aggregating node embeddings."""
        if not nodes:
            return [0.0] * self._dim

        # Aggregate node embeddings (mean pooling)
        aggregated = [0.0] * self._dim
        for node in nodes:
            label = node.get("label", node.get("_label", "Unknown"))
            props = node.get("props", node.get("properties", node))
            node_emb = self.embed_node(label, props)
            for i in range(self._dim):
                aggregated[i] += node_emb[i]

        count = len(nodes)
        aggregated = [v / count for v in aggregated]

        # Add structural features
        structural = self._structural_features(len(nodes), len(edges))
        for i, val in enumerate(structural):
            idx = i % self._dim
            aggregated[idx] = (aggregated[idx] + val) / 2.0

        return self._normalize(aggregated)

    def embed_context(self, context: dict[str, Any]) -> list[float]:
        """Generate embedding for a structured context object."""
        cache_key = f"emb:ctx:{hashlib.md5(str(sorted(context.items())).encode()).hexdigest()[:12]}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        flat = flatten_properties(context)
        signature = " | ".join(f"{k}={v}" for k, v in sorted(flat.items()) if v is not None)
        embedding = self._hash_embed(signature)

        numeric_features = self._extract_numeric_features(flat)
        if numeric_features:
            for i, val in enumerate(numeric_features[:self._dim // 2]):
                idx = (self._dim // 2) + (i % (self._dim // 2))
                embedding[idx] = val

        embedding = self._normalize(embedding)
        self._cache.set(cache_key, embedding)
        return embedding

    def compute_similarity(self, embedding_a: list[float], embedding_b: list[float]) -> float:
        """Compute cosine similarity between two embeddings."""
        if len(embedding_a) != len(embedding_b):
            return 0.0
        dot = sum(a * b for a, b in zip(embedding_a, embedding_b))
        norm_a = math.sqrt(sum(a * a for a in embedding_a))
        norm_b = math.sqrt(sum(b * b for b in embedding_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def find_similar_nodes(
        self,
        query_embedding: list[float],
        candidate_nodes: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[tuple[dict[str, Any], float]]:
        """Find top-K most similar nodes to a query embedding."""
        scored = []
        for node in candidate_nodes:
            label = node.get("label", node.get("_label", "Unknown"))
            props = node.get("props", node.get("properties", node))
            node_emb = self.embed_node(label, props)
            similarity = self.compute_similarity(query_embedding, node_emb)
            scored.append((node, similarity))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def _hash_embed(self, text: str) -> list[float]:
        """Generate a deterministic embedding via feature hashing."""
        embedding = [0.0] * self._dim
        for i, char in enumerate(text):
            idx = (ord(char) * (i + 1)) % self._dim
            sign = 1.0 if (ord(char) + i) % 2 == 0 else -1.0
            embedding[idx] += sign * (1.0 / (1.0 + i * 0.01))
        return embedding

    def _extract_numeric_features(self, props: dict[str, Any]) -> list[float]:
        """Extract and normalize numeric features from properties."""
        numerics = []
        for value in props.values():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                # Sigmoid normalization to [0, 1]
                normalized = 1.0 / (1.0 + math.exp(-float(value) * 0.1))
                numerics.append(normalized)
        return numerics

    def _structural_features(self, node_count: int, edge_count: int) -> list[float]:
        """Compute structural features for subgraph embedding."""
        density = edge_count / max(node_count * (node_count - 1), 1)
        avg_degree = (2 * edge_count) / max(node_count, 1)
        return [
            1.0 / (1.0 + math.exp(-node_count * 0.1)),
            1.0 / (1.0 + math.exp(-edge_count * 0.05)),
            density,
            1.0 / (1.0 + math.exp(-avg_degree)),
        ]

    def _normalize(self, embedding: list[float]) -> list[float]:
        """L2 normalize an embedding vector."""
        norm = math.sqrt(sum(v * v for v in embedding))
        if norm == 0:
            return embedding
        return [v / norm for v in embedding]
