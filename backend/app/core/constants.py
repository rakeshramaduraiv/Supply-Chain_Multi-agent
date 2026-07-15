"""
AMASCI Constants
=================
System-wide constant values.
"""

# --- DataCo Schema Reference ---
REQUIRED_COLUMNS = [
    "Order Id",
    "order date (DateOrders)",
    "shipping date (DateOrders)",
    "Days for shipping (real)",
    "Days for shipment (scheduled)",
    "Late_delivery_risk",
    "Delivery Status",
    "Shipping Mode",
    "Category Name",
    "Product Name",
    "Product Price",
    "Order Region",
    "Order Country",
    "Order City",
    "Market",
    "Customer Id",
    "Customer Segment",
    "Order Item Quantity",
    "Sales",
    "Order Profit Per Order",
    "Order Item Discount",
    "Order Item Product Price",
    "Order Item Total",
    "Benefit per order",
    "Sales per customer",
    "Department Name",
    "Latitude",
    "Longitude",
]

OPTIONAL_COLUMNS = [
    "Customer Fname",
    "Customer Lname",
    "Customer Email",
    "Customer Password",
    "Customer Street",
    "Customer Zipcode",
    "Product Status",
    "Product Image",
    "Order Zipcode",
    "Product Card Id",
    "Product Category Id",
    "Category Id",
    "Department Id",
    "Customer City",
    "Customer Country",
    "Customer State",
    "Order State",
    "Order Status",
    "Type",
    "Product Description",
]

# --- Validation Thresholds ---
MAX_NULL_RATIO_REQUIRED = 0.40
MAX_NULL_RATIO_ROW = 0.60
MAX_NULL_RATIO_TARGET = 0.0
MAX_NULL_RATIO_DATE = 0.05
MIN_ROW_COUNT = 1000
MAX_CATEGORY_CARDINALITY_RATIO = 0.50

# --- ML Constants ---
TARGET_COLUMN = "Late_delivery_risk"
RANDOM_STATE = 42
TEST_SIZE = 0.2
WALK_FORWARD_SPLITS = 5

# --- Risk Score Thresholds ---
RISK_LOW_THRESHOLD = 0.25
RISK_MEDIUM_THRESHOLD = 0.50
RISK_HIGH_THRESHOLD = 0.75

# --- TPKE Constants ---
TPKE_MIN_EDGE_WEIGHT = 0.1
TPKE_MAX_EDGE_WEIGHT = 1.0
TPKE_PATTERN_MIN_OCCURRENCES = 3

# --- Graph Constants ---
GRAPH_MAX_HOPS = 3
GRAPH_RISK_PROPAGATION_DECAY = 0.7

# --- API Constants ---
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500
API_V1_PREFIX = "/api/v1"
