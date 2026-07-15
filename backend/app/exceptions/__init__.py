"""
AMASCI Exception Hierarchy
============================
Centralized custom exceptions for all modules.
"""

from typing import Any


class AmasciBaseException(Exception):
    """Base exception for all AMASCI errors."""

    def __init__(
        self,
        message: str = "An internal error occurred",
        error_code: str = "INTERNAL_ERROR",
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


# --- Upload Exceptions ---
class UploadException(AmasciBaseException):
    """Base exception for upload operations."""
    pass


class FileTooLargeException(UploadException):
    def __init__(self, size_mb: float, max_mb: int):
        super().__init__(
            message=f"File size {size_mb:.1f}MB exceeds maximum {max_mb}MB",
            error_code="FILE_TOO_LARGE",
            details={"size_mb": size_mb, "max_mb": max_mb},
        )


class InvalidFileFormatException(UploadException):
    def __init__(self, filename: str):
        super().__init__(
            message=f"Invalid file format: {filename}. Only CSV files are accepted.",
            error_code="INVALID_FORMAT",
            details={"filename": filename},
        )


class EmptyDatasetException(UploadException):
    def __init__(self):
        super().__init__(
            message="Uploaded dataset is empty",
            error_code="EMPTY_DATASET",
        )


# --- Validation Exceptions ---
class ValidationException(AmasciBaseException):
    """Base exception for validation operations."""
    pass


class SchemaValidationException(ValidationException):
    def __init__(self, missing_columns: list[str]):
        super().__init__(
            message=f"Schema validation failed. Missing critical columns: {missing_columns}",
            error_code="SCHEMA_INVALID",
            details={"missing_columns": missing_columns},
        )


class DataQualityException(ValidationException):
    def __init__(self, quality_score: float, issues: list[str]):
        super().__init__(
            message=f"Data quality below threshold. Score: {quality_score:.2f}",
            error_code="QUALITY_FAILED",
            details={"quality_score": quality_score, "issues": issues},
        )


class InsufficientDataException(ValidationException):
    def __init__(self, row_count: int, min_required: int):
        super().__init__(
            message=f"Insufficient data: {row_count} rows. Minimum required: {min_required}",
            error_code="INSUFFICIENT_DATA",
            details={"row_count": row_count, "min_required": min_required},
        )


# --- ML Exceptions ---
class MLException(AmasciBaseException):
    """Base exception for ML operations."""
    pass


class ModelNotFoundException(MLException):
    def __init__(self, model_version: str):
        super().__init__(
            message=f"Model version '{model_version}' not found",
            error_code="MODEL_NOT_FOUND",
            details={"model_version": model_version},
        )


class TrainingFailedException(MLException):
    def __init__(self, reason: str):
        super().__init__(
            message=f"Model training failed: {reason}",
            error_code="TRAINING_FAILED",
            details={"reason": reason},
        )


class PredictionFailedException(MLException):
    def __init__(self, reason: str):
        super().__init__(
            message=f"Prediction failed: {reason}",
            error_code="PREDICTION_FAILED",
            details={"reason": reason},
        )


# --- Graph Exceptions ---
class GraphException(AmasciBaseException):
    """Base exception for graph operations."""
    pass


class GraphConnectionException(GraphException):
    def __init__(self):
        super().__init__(
            message="Failed to connect to Neo4j database",
            error_code="GRAPH_CONNECTION_FAILED",
        )


class GraphConstructionException(GraphException):
    def __init__(self, reason: str):
        super().__init__(
            message=f"Knowledge Graph construction failed: {reason}",
            error_code="GRAPH_BUILD_FAILED",
            details={"reason": reason},
        )


class GraphQueryException(GraphException):
    def __init__(self, query_type: str, reason: str):
        super().__init__(
            message=f"Graph query failed ({query_type}): {reason}",
            error_code="GRAPH_QUERY_FAILED",
            details={"query_type": query_type, "reason": reason},
        )


# --- TPKE Exceptions ---
class TPKEException(AmasciBaseException):
    """Base exception for TPKE operations."""
    pass


class TPKEPatternDetectionException(TPKEException):
    def __init__(self, reason: str):
        super().__init__(
            message=f"TPKE pattern detection failed: {reason}",
            error_code="TPKE_DETECTION_FAILED",
            details={"reason": reason},
        )


# --- Forecast Exceptions ---
class ForecastException(AmasciBaseException):
    """Base exception for forecast operations."""
    pass


class ForecastGenerationException(ForecastException):
    def __init__(self, reason: str):
        super().__init__(
            message=f"Forecast generation failed: {reason}",
            error_code="FORECAST_FAILED",
            details={"reason": reason},
        )


class NoForecastAvailableException(ForecastException):
    def __init__(self, dataset_id: str):
        super().__init__(
            message=f"No forecast available for dataset {dataset_id}",
            error_code="NO_FORECAST",
            details={"dataset_id": dataset_id},
        )


# --- Database Exceptions ---
class DatabaseException(AmasciBaseException):
    """Base exception for database operations."""
    pass


class RecordNotFoundException(DatabaseException):
    def __init__(self, entity: str, identifier: str):
        super().__init__(
            message=f"{entity} with id '{identifier}' not found",
            error_code="NOT_FOUND",
            details={"entity": entity, "identifier": identifier},
        )


# --- Auth Exceptions ---
class AuthException(AmasciBaseException):
    """Base exception for authentication."""
    pass


class InvalidCredentialsException(AuthException):
    def __init__(self):
        super().__init__(
            message="Invalid email or password",
            error_code="INVALID_CREDENTIALS",
        )


class InsufficientPermissionsException(AuthException):
    def __init__(self, required_permission: str):
        super().__init__(
            message=f"Insufficient permissions. Required: {required_permission}",
            error_code="FORBIDDEN",
            details={"required_permission": required_permission},
        )


class TokenExpiredException(AuthException):
    def __init__(self):
        super().__init__(
            message="Access token has expired",
            error_code="TOKEN_EXPIRED",
        )


# --- GraphRAG Exceptions ---
class GraphRAGException(AmasciBaseException):
    """Base exception for GraphRAG operations."""
    pass


class GraphRAGRetrievalException(GraphRAGException):
    def __init__(self, entity_id: str, reason: str):
        super().__init__(
            message=f"GraphRAG retrieval failed for '{entity_id}': {reason}",
            error_code="GRAPHRAG_RETRIEVAL_FAILED",
            details={"entity_id": entity_id, "reason": reason},
        )


class GraphRAGContextException(GraphRAGException):
    def __init__(self, context_type: str, reason: str):
        super().__init__(
            message=f"GraphRAG context generation failed ({context_type}): {reason}",
            error_code="GRAPHRAG_CONTEXT_FAILED",
            details={"context_type": context_type, "reason": reason},
        )


class GraphRAGEmbeddingException(GraphRAGException):
    def __init__(self, reason: str):
        super().__init__(
            message=f"GraphRAG embedding generation failed: {reason}",
            error_code="GRAPHRAG_EMBEDDING_FAILED",
            details={"reason": reason},
        )


class GraphRAGQueryException(GraphRAGException):
    def __init__(self, query: str, reason: str):
        super().__init__(
            message=f"GraphRAG query failed: {reason}",
            error_code="GRAPHRAG_QUERY_FAILED",
            details={"query": query, "reason": reason},
        )


# --- RCA Exceptions ---
class RCAException(AmasciBaseException):
    """Base exception for RCA operations."""
    pass


class RCATraversalException(RCAException):
    def __init__(self, entity_id: str, reason: str):
        super().__init__(
            message=f"RCA graph traversal failed for '{entity_id}': {reason}",
            error_code="RCA_TRAVERSAL_FAILED",
            details={"entity_id": entity_id, "reason": reason},
        )


class RCAAnalysisException(RCAException):
    def __init__(self, rca_type: str, reason: str):
        super().__init__(
            message=f"RCA analysis failed ({rca_type}): {reason}",
            error_code="RCA_ANALYSIS_FAILED",
            details={"rca_type": rca_type, "reason": reason},
        )


class RCAEntityNotFoundException(RCAException):
    def __init__(self, entity_id: str):
        super().__init__(
            message=f"RCA target entity '{entity_id}' not found in graph",
            error_code="RCA_ENTITY_NOT_FOUND",
            details={"entity_id": entity_id},
        )


# --- Pipeline Exceptions ---
class PipelineException(AmasciBaseException):
    """Base exception for pipeline operations."""
    pass


class PipelineStepFailedException(PipelineException):
    def __init__(self, step: str, reason: str):
        super().__init__(
            message=f"Pipeline step '{step}' failed: {reason}",
            error_code="PIPELINE_STEP_FAILED",
            details={"step": step, "reason": reason},
        )
