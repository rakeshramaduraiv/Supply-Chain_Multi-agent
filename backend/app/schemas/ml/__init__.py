"""
AMASCI ML Schemas
==================
Pydantic models for ML API request/response contracts.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# --- Training Schemas ---

class TrainRequest(BaseModel):
    """Request to train a model."""
    intelligence_type: str = Field(..., description="One of: demand, inventory, supplier, logistics")
    dataset_version: str = Field(default="", description="Dataset version identifier")
    run_walk_forward: bool = Field(default=True, description="Run walk-forward validation")


class TrainAllRequest(BaseModel):
    """Request to train all models."""
    dataset_version: str = Field(default="", description="Dataset version identifier")
    run_walk_forward: bool = Field(default=True, description="Run walk-forward validation")


class TrainingMetricsSchema(BaseModel):
    """Training metrics response."""
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    roc_auc: float | None = None
    mae: float | None = None
    rmse: float | None = None
    mape: float | None = None
    r2: float | None = None
    n_samples: int = 0


class FeatureImportanceSchema(BaseModel):
    """Feature importance response."""
    feature_names: list[str] = []
    gain_importance: list[float] = []
    split_importance: list[float] = []
    top_features: list[dict[str, Any]] = []
    ranking: list[dict[str, Any]] = []


class WalkForwardFoldSchema(BaseModel):
    """Single walk-forward fold result."""
    fold_index: int
    train_size: int
    test_size: int
    metrics: dict[str, Any] = {}
    duration_ms: float = 0.0


class WalkForwardResultSchema(BaseModel):
    """Walk-forward validation result."""
    n_folds: int = 0
    aggregated_metrics: dict[str, Any] = {}
    total_duration_ms: float = 0.0
    best_fold_index: int = 0
    folds: list[WalkForwardFoldSchema] = []


class TrainingResultSchema(BaseModel):
    """Complete training result response."""
    intelligence_type: str
    version_id: str
    task: str
    metrics: dict[str, Any] = {}
    feature_importance: dict[str, Any] = {}
    walk_forward_result: dict[str, Any] | None = None
    confidence_summary: dict[str, Any] = {}
    training_duration_ms: float = 0.0
    n_training_samples: int = 0
    n_test_samples: int = 0
    features_used: list[str] = []
    hyperparameters: dict[str, Any] = {}


class TrainAllResultSchema(BaseModel):
    """Result of training all models."""
    results: dict[str, TrainingResultSchema] = {}
    total_duration_ms: float = 0.0


# --- Prediction Schemas ---

class PredictRequest(BaseModel):
    """Request for batch prediction."""
    intelligence_type: str = Field(..., description="One of: demand, inventory, supplier, logistics")
    version_id: str | None = Field(default=None, description="Model version (None = latest)")


class PredictionResultSchema(BaseModel):
    """Prediction result response."""
    intelligence_type: str
    model_version: str
    n_predictions: int = 0
    mean_confidence: float = 0.0
    prediction_time_ms: float = 0.0
    predictions: list[float] = []
    probabilities: list[float] | None = None
    confidence_scores: list[float] = []
    risk_levels: list[str] = []
    predictions_summary: dict[str, Any] = {}
    risk_distribution: dict[str, int] = {}
    metadata: dict[str, Any] = {}


# --- Forecast Schemas ---

class ForecastRequest(BaseModel):
    """Request for forecast generation."""
    intelligence_type: str = Field(..., description="One of: demand, inventory, supplier, logistics")
    horizon_months: int = Field(default=3, ge=1, le=12, description="Forecast horizon in months")
    version_id: str | None = Field(default=None, description="Model version (None = latest)")


class ForecastPeriodSchema(BaseModel):
    """Single forecast period."""
    period: str
    predicted_value: float
    confidence_score: float
    lower_bound: float
    upper_bound: float
    risk_level: str = ""


class ForecastResultSchema(BaseModel):
    """Complete forecast result response."""
    intelligence_type: str
    model_version: str
    forecast_horizon: int = 0
    mean_confidence: float = 0.0
    generation_time_ms: float = 0.0
    generated_at: str = ""
    forecast_periods: list[ForecastPeriodSchema] = []
    historical_periods: list[ForecastPeriodSchema] = []


# --- Model Registry Schemas ---

class ModelVersionSchema(BaseModel):
    """Model version metadata."""
    version_id: str
    intelligence_type: str
    task: str
    model_path: str
    created_at: str
    training_duration_ms: float = 0.0
    features_used: list[str] = []
    metrics: dict[str, Any] = {}
    dataset_version: str = ""
    hyperparameters: dict[str, Any] = {}
    n_training_samples: int = 0
    is_active: bool = True
    description: str = ""


class ModelListSchema(BaseModel):
    """List of all registered models."""
    models: dict[str, list[ModelVersionSchema]] = {}
    total_models: int = 0


# --- Evaluation Schemas ---

class EvaluateRequest(BaseModel):
    """Request for model evaluation."""
    intelligence_type: str = Field(..., description="One of: demand, inventory, supplier, logistics")
    version_id: str | None = Field(default=None, description="Model version (None = latest)")


class EvaluationResultSchema(BaseModel):
    """Model evaluation result."""
    intelligence_type: str
    model_version: str
    metrics: dict[str, Any] = {}
    confidence_summary: dict[str, Any] = {}
    n_samples: int = 0
    evaluation_time_ms: float = 0.0


# --- Training History ---

class TrainingHistoryEntry(BaseModel):
    """Single training history entry."""
    version_id: str
    intelligence_type: str
    created_at: str
    metrics: dict[str, Any] = {}
    training_duration_ms: float = 0.0
    n_training_samples: int = 0
    is_active: bool = True


class TrainingHistorySchema(BaseModel):
    """Training history response."""
    entries: list[TrainingHistoryEntry] = []
    total_entries: int = 0
