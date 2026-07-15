"""
AMASCI Graph Relationship Definitions
========================================
Relationship type schemas and property definitions.
"""

from dataclasses import dataclass, field
from typing import Any

from app.graph.utils import utc_now_iso


@dataclass
class BaseRelationship:
    """Base relationship with common properties."""
    rel_type: str
    source_id: str
    source_label: str
    target_id: str
    target_label: str
    relationship_strength: float = 1.0
    frequency: int = 1
    avg_delay: float = 0.0
    confidence: float = 1.0
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}

    @property
    def properties(self) -> dict[str, Any]:
        """Get relationship properties (excluding structural fields)."""
        exclude = {"rel_type", "source_id", "source_label", "target_id", "target_label"}
        return {k: v for k, v in self.__dict__.items() if k not in exclude and v is not None}


def create_supplies(source_id: str, source_label: str, target_id: str, target_label: str, **kwargs: Any) -> BaseRelationship:
    """Create a SUPPLIES relationship."""
    return BaseRelationship(rel_type="SUPPLIES", source_id=source_id, source_label=source_label, target_id=target_id, target_label=target_label, **kwargs)


def create_stored_in(source_id: str, source_label: str, target_id: str, target_label: str, **kwargs: Any) -> BaseRelationship:
    """Create a STORED_IN relationship."""
    return BaseRelationship(rel_type="STORED_IN", source_id=source_id, source_label=source_label, target_id=target_id, target_label=target_label, **kwargs)


def create_ships_via(source_id: str, source_label: str, target_id: str, target_label: str, **kwargs: Any) -> BaseRelationship:
    """Create a SHIPS_VIA relationship."""
    return BaseRelationship(rel_type="SHIPS_VIA", source_id=source_id, source_label=source_label, target_id=target_id, target_label=target_label, **kwargs)


def create_delivered_to(source_id: str, source_label: str, target_id: str, target_label: str, **kwargs: Any) -> BaseRelationship:
    """Create a DELIVERED_TO relationship."""
    return BaseRelationship(rel_type="DELIVERED_TO", source_id=source_id, source_label=source_label, target_id=target_id, target_label=target_label, **kwargs)


def create_placed(source_id: str, source_label: str, target_id: str, target_label: str, **kwargs: Any) -> BaseRelationship:
    """Create a PLACED relationship."""
    return BaseRelationship(rel_type="PLACED", source_id=source_id, source_label=source_label, target_id=target_id, target_label=target_label, **kwargs)


def create_contains(source_id: str, source_label: str, target_id: str, target_label: str, **kwargs: Any) -> BaseRelationship:
    """Create a CONTAINS relationship."""
    return BaseRelationship(rel_type="CONTAINS", source_id=source_id, source_label=source_label, target_id=target_id, target_label=target_label, **kwargs)


def create_influences(source_id: str, source_label: str, target_id: str, target_label: str, **kwargs: Any) -> BaseRelationship:
    """Create an INFLUENCES relationship."""
    return BaseRelationship(rel_type="INFLUENCES", source_id=source_id, source_label=source_label, target_id=target_id, target_label=target_label, **kwargs)


# Aliases for backward compatibility
SuppliesRelationship = BaseRelationship
StoredInRelationship = BaseRelationship
ShipsViaRelationship = BaseRelationship
DeliveredToRelationship = BaseRelationship
PlacedRelationship = BaseRelationship
ContainsRelationship = BaseRelationship
InfluencesRelationship = BaseRelationship
