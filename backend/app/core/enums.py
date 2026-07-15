"""
AMASCI Enumerations
====================
System-wide enumeration types for type safety and consistency.
"""

from enum import Enum


class AppEnvironment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class DatasetType(str, Enum):
    HISTORICAL = "historical"
    ACTUALS = "actuals"
    SUPPLEMENTARY = "supplementary"


class DatasetStatus(str, Enum):
    UPLOADED = "uploaded"
    VALIDATING = "validating"
    VALIDATED = "validated"
    CLEANING = "cleaning"
    CLEANED = "cleaned"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    ARCHIVED = "archived"


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineStep(str, Enum):
    VALIDATION = "validation"
    CLEANING = "cleaning"
    FEATURE_ENGINEERING = "feature_engineering"
    TRAINING = "training"
    PREDICTION = "prediction"
    FORECASTING = "forecasting"
    GRAPH_CONSTRUCTION = "graph_construction"
    GRAPH_ANALYTICS = "graph_analytics"
    TPKE = "tpke"
    GRAPHRAG = "graphrag"
    ROOT_CAUSE = "root_cause"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class UserRole(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class ShippingMode(str, Enum):
    STANDARD = "Standard Class"
    FIRST = "First Class"
    SECOND = "Second Class"
    SAME_DAY = "Same Day"


class DeliveryStatus(str, Enum):
    ADVANCE = "Advance shipping"
    LATE = "Late delivery"
    ON_TIME = "Shipping on time"
    CANCELLED = "Shipping canceled"


class GraphNodeType(str, Enum):
    SUPPLIER = "Supplier"
    PRODUCT = "Product"
    WAREHOUSE = "Warehouse"
    SHIPMENT = "Shipment"
    CUSTOMER = "Customer"
    ORDER = "Order"
    MARKET = "Market"
    REGION = "Region"
    CALENDAR_EVENT = "CalendarEvent"


class GraphRelationType(str, Enum):
    SUPPLIES = "SUPPLIES"
    STORED_IN = "STORED_IN"
    SHIPS_VIA = "SHIPS_VIA"
    DELIVERED_TO = "DELIVERED_TO"
    PLACED = "PLACED"
    CONTAINS = "CONTAINS"
    INFLUENCES = "INFLUENCES"
    LOCATED_IN = "LOCATED_IN"
    BELONGS_TO = "BELONGS_TO"


class TPKEAction(str, Enum):
    EDGE_CREATED = "edge_created"
    EDGE_STRENGTHENED = "edge_strengthened"
    EDGE_DECAYED = "edge_decayed"
    EDGE_REMOVED = "edge_removed"


class ForecastStatus(str, Enum):
    GENERATED = "generated"
    COMPARED = "compared"
    EXPIRED = "expired"
