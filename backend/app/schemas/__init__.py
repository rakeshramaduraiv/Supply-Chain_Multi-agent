"""
AMASCI Base Schemas
====================
Standardized API response models used across all endpoints.
"""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    model_config = ConfigDict(from_attributes=True)

    success: bool = True
    message: str = "Operation completed successfully"
    data: T | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorDetail(BaseModel):
    """Error detail structure."""

    code: str
    message: str
    status_code: int
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    success: bool = False
    error: ErrorDetail
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    page: int = 1
    page_size: int = 50
    total_items: int = 0
    total_pages: int = 0
    has_next: bool = False
    has_previous: bool = False


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated API response."""

    success: bool = True
    message: str = "Data retrieved successfully"
    data: list[T] = []
    pagination: PaginationMeta
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str
    environment: str
    services: dict[str, str] = {}
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PipelineStatusResponse(BaseModel):
    """Pipeline execution status."""

    run_id: str
    status: str
    current_step: str | None = None
    completed_steps: list[str] = []
    progress_percent: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    step_timings: dict[str, float] = {}
    errors: list[str] = []
