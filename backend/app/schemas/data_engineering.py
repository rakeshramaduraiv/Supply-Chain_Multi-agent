"""
AMASCI Data Engineering Schemas
==================================
Pydantic models for upload, validation, cleaning, and profiling API contracts.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# --- Upload Schemas ---

class UploadResponse(BaseModel):
    """Response after successful dataset upload."""

    model_config = ConfigDict(from_attributes=True)

    dataset_id: str
    version: int
    filename: str
    dataset_type: str
    file_hash: str
    file_size_mb: float
    row_count: int
    column_count: int
    columns: list[str]
    status: str
    uploaded_at: str


class DatasetInfo(BaseModel):
    """Dataset metadata summary."""

    dataset_id: str
    version: int
    filename: str
    dataset_type: str
    status: str
    row_count: int
    column_count: int
    file_size_mb: float
    uploaded_at: str
    quality_score: float | None = None


# --- Validation Schemas ---

class ColumnValidationSchema(BaseModel):
    """Validation result for a single column."""

    name: str
    present: bool
    dtype: str
    null_count: int
    null_percent: float
    unique_count: int
    is_required: bool
    issues: list[str] = []


class ValidationReportSchema(BaseModel):
    """Complete validation report."""

    is_valid: bool
    quality_score: float
    row_count: int
    column_count: int
    schema_info: dict[str, Any] = Field(alias="schema")
    duplicates: dict[str, Any]
    null_percent: float
    date_issues: list[str]
    business_rule_violations: list[str]
    warnings: list[str]
    errors: list[str]


# --- Cleaning Schemas ---

class CleaningReportSchema(BaseModel):
    """Cleaning operation report."""

    rows_before: int
    rows_after: int
    rows_removed: int
    duplicates_removed: int
    nulls_imputed: dict[str, int]
    dates_fixed: int
    negatives_fixed: int
    categories_normalized: int
    operations_count: int
    operations: list[str]


# --- Transformation Schemas ---

class TransformationReportSchema(BaseModel):
    """Transformation operation report."""

    columns_added: list[str]
    columns_removed: list[str]
    aggregations_created: list[str]
    operations_count: int


# --- Profiling Schemas ---

class DatasetSummarySchema(BaseModel):
    """High-level dataset summary."""

    row_count: int
    column_count: int
    memory_mb: float
    numeric_columns: int
    categorical_columns: int
    datetime_columns: int
    total_null_cells: int
    total_null_percent: float
    duplicate_rows: int


class ColumnProfileSchema(BaseModel):
    """Per-column profile."""

    name: str
    dtype: str
    null_count: int
    null_percent: float
    unique_count: int
    unique_percent: float
    mean: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    q25: float | None = None
    q50: float | None = None
    q75: float | None = None
    top_values: dict[str, int] | None = None


class OutlierInfoSchema(BaseModel):
    """Outlier detection result for a column."""

    column: str
    outlier_count: int
    outlier_percent: float
    lower_bound: float
    upper_bound: float
    iqr: float


class ProfileResponseSchema(BaseModel):
    """Complete dataset profile response."""

    summary: DatasetSummarySchema
    columns: list[ColumnProfileSchema]
    missing_values: dict[str, Any]
    duplicates: dict[str, Any]
    outliers: list[OutlierInfoSchema]
    correlations: list[dict[str, Any]]
    target_distribution: dict[str, Any]


# --- Pipeline Schemas ---

class PipelineResultSchema(BaseModel):
    """Complete pipeline execution result."""

    dataset_id: str
    status: str
    started_at: str
    completed_at: str
    total_duration_ms: float
    row_count_raw: int
    row_count_clean: int
    row_count_final: int
    column_count_final: int
    validation: dict[str, Any]
    cleaning: dict[str, Any]
    transformation: dict[str, Any]
    profile: dict[str, Any]
    errors: list[str]


# --- Dataset History ---

class DatasetHistoryItem(BaseModel):
    """Single entry in dataset history."""

    dataset_id: str
    version: int
    filename: str
    dataset_type: str
    status: str
    row_count: int
    quality_score: float | None = None
    uploaded_at: str


class DatasetHistoryResponse(BaseModel):
    """Dataset upload history."""

    total: int
    datasets: list[DatasetHistoryItem]
