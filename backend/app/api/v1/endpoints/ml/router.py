"""
AMASCI ML API Router
=====================
Complete REST API for ML intelligence services.

Endpoints:
    POST /train              - Train a single intelligence model
    POST /train/all          - Train all intelligence models
    POST /predict            - Generate batch predictions
    POST /forecast           - Generate time-series forecast
    POST /model/evaluate     - Evaluate model on dataset
    GET  /models             - List all registered models
    GET  /models/latest      - Get latest model versions
    GET  /metrics/{type}     - Get metrics for intelligence type
    GET  /feature-importance/{type} - Get feature importance
    GET  /training-history   - Get training history
"""

import logging
import time
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.core.config import get_settings
from app.ml.forecasting import ForecastEngine
from app.ml.prediction import PredictionEngine, DemandAgent, InventoryAgent, SupplierAgent, LogisticsAgent
from app.ml.registry import ModelRegistry
from app.ml.training import TrainingOrchestrator
from app.ml.utils import FEATURE_CONFIGS, IntelligenceType
from app.api.v1.endpoints.ml import coordinator
from app.schemas import BaseResponse
from app.schemas.ml import (
    EvaluateRequest,
    EvaluationResultSchema,
    FeatureImportanceSchema,
    ForecastRequest,
    ForecastResultSchema,
    ModelListSchema,
    ModelVersionSchema,
    PredictRequest,
    PredictionResultSchema,
    TrainAllRequest,
    TrainAllResultSchema,
    TrainRequest,
    TrainingHistoryEntry,
    TrainingHistorySchema,
    TrainingResultSchema,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ml", tags=["Machine Learning"])

# --- Service Instances ---
_registry = ModelRegistry()
_orchestrator = TrainingOrchestrator(_registry)
_prediction_engine = PredictionEngine(_registry)
_forecast_engine = ForecastEngine(_registry)


def _resolve_intelligence_type(value: str) -> IntelligenceType:
    """Resolve string to IntelligenceType enum."""
    try:
        return IntelligenceType(value.lower())
    except ValueError:
        valid = [t.value for t in IntelligenceType]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid intelligence_type: '{value}'. Must be one of: {valid}",
        )


def _load_processed_dataset() -> pd.DataFrame:
    """Load the processed master dataset from disk (parquet preferred, CSV fallback)."""
    settings = get_settings()
    data_dir = Path(settings.upload_dir)

    # Primary: parquet saved by initialization pipeline
    parquet_path = data_dir / "processed_master.parquet"
    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)
        logger.info(f"Loaded dataset: processed_master.parquet ({len(df)} rows)")
        return df

    # Fallback: any parquet
    parquet_candidates = sorted(data_dir.glob("*.parquet"), key=lambda p: p.stat().st_mtime, reverse=True)
    if parquet_candidates:
        df = pd.read_parquet(parquet_candidates[0])
        logger.info(f"Loaded dataset: {parquet_candidates[0].name} ({len(df)} rows)")
        return df

    # Last resort: CSV
    csv_candidates = sorted(data_dir.glob("*_processed.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not csv_candidates:
        csv_candidates = sorted(data_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not csv_candidates:
        raise HTTPException(
            status_code=404,
            detail="No processed dataset found. Place DataCoSupplyChainDataset.csv in data/raw/ and restart.",
        )

    df = pd.read_csv(csv_candidates[0])
    logger.info(f"Loaded dataset: {csv_candidates[0].name} ({len(df)} rows)")
    return df


# ============================================================
# TRAINING ENDPOINTS
# ============================================================

@router.post("/train", response_model=BaseResponse[TrainingResultSchema])
async def train_model(request: TrainRequest):
    """Train a single intelligence model."""
    intel_type = _resolve_intelligence_type(request.intelligence_type)

    try:
        df = _load_processed_dataset()
        result = _orchestrator.train_single(
            df=df,
            intelligence_type=intel_type,
            dataset_version=request.dataset_version,
        )
        await broadcast_event("Forecast Generated", {"intelligence_type": request.intelligence_type})

        return BaseResponse(
            data=TrainingResultSchema(**result.to_dict()),
            message=f"Model trained successfully: {intel_type.value}",
        )
    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@router.post("/train/all", response_model=BaseResponse[TrainAllResultSchema])
async def train_all_models(request: TrainAllRequest):
    """Train all intelligence models."""
    start = time.perf_counter()

    try:
        df = _load_processed_dataset()
        results = _orchestrator.train_all(df, dataset_version=request.dataset_version)

        result_schemas = {
            k: TrainingResultSchema(**v.to_dict()) for k, v in results.items()
        }
        total_ms = (time.perf_counter() - start) * 1000

        await broadcast_event("Forecast Generated", {"all": True})

        return BaseResponse(
            data=TrainAllResultSchema(results=result_schemas, total_duration_ms=total_ms),
            message="All models trained successfully",
        )
    except Exception as e:
        logger.error(f"Training all failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@router.post("/train/upload", response_model=BaseResponse[TrainingResultSchema])
async def train_with_upload(
    intelligence_type: str = Query(...),
    file: UploadFile = File(...),
    dataset_version: str = Query(default=""),
):
    """Train a model with an uploaded CSV file."""
    intel_type = _resolve_intelligence_type(intelligence_type)

    try:
        content = await file.read()
        from io import BytesIO
        df = pd.read_csv(BytesIO(content))

        result = _orchestrator.train_single(
            df=df,
            intelligence_type=intel_type,
            dataset_version=dataset_version,
        )
        return BaseResponse(
            data=TrainingResultSchema(**result.to_dict()),
            message=f"Model trained from upload: {intel_type.value}",
        )
    except Exception as e:
        logger.error(f"Training with upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


# ============================================================
# PREDICTION ENDPOINTS
# ============================================================

@router.post("/predict", response_model=BaseResponse[PredictionResultSchema])
async def predict(request: PredictRequest, file: UploadFile = File(...)):
    """Generate batch predictions from uploaded CSV."""
    intel_type = _resolve_intelligence_type(request.intelligence_type)

    try:
        content = await file.read()
        from io import BytesIO
        df = pd.read_csv(BytesIO(content))

        agent_map = {
            IntelligenceType.DEMAND: DemandAgent(_registry),
            IntelligenceType.INVENTORY: InventoryAgent(_registry),
            IntelligenceType.SUPPLIER: SupplierAgent(_registry),
            IntelligenceType.LOGISTICS: LogisticsAgent(_registry),
        }
        agent = agent_map[intel_type]
        result = agent.predict(df, request.version_id)
        await auto_sync_predictions(df)

        return BaseResponse(
            data=PredictionResultSchema(
                intelligence_type=result.intelligence_type,
                model_version=result.model_version,
                n_predictions=result.n_predictions,
                mean_confidence=result.mean_confidence,
                prediction_time_ms=result.prediction_time_ms,
                predictions=result.predictions,
                probabilities=result.probabilities,
                confidence_scores=result.confidence_scores,
                risk_levels=result.risk_levels,
                predictions_summary=result.to_dict().get("predictions_summary", {}),
                risk_distribution=result.to_dict().get("risk_distribution", {}),
                metadata=result.metadata,
            ),
            message=f"Predictions generated: {result.n_predictions} records",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Prediction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/predict/dataset", response_model=BaseResponse[PredictionResultSchema])
async def predict_from_dataset(request: PredictRequest):
    """Generate predictions using the stored processed dataset."""
    intel_type = _resolve_intelligence_type(request.intelligence_type)

    try:
        df = _load_processed_dataset()
        agent_map = {
            IntelligenceType.DEMAND: DemandAgent(_registry),
            IntelligenceType.INVENTORY: InventoryAgent(_registry),
            IntelligenceType.SUPPLIER: SupplierAgent(_registry),
            IntelligenceType.LOGISTICS: LogisticsAgent(_registry),
        }
        agent = agent_map[intel_type]
        result = agent.predict(df, request.version_id)
        await auto_sync_predictions(df)

        return BaseResponse(
            data=PredictionResultSchema(
                intelligence_type=result.intelligence_type,
                model_version=result.model_version,
                n_predictions=result.n_predictions,
                mean_confidence=result.mean_confidence,
                prediction_time_ms=result.prediction_time_ms,
                predictions=result.predictions[:1000],  # Limit response size
                probabilities=result.probabilities[:1000] if result.probabilities else None,
                confidence_scores=result.confidence_scores[:1000],
                risk_levels=result.risk_levels[:1000],
                predictions_summary=result.to_dict().get("predictions_summary", {}),
                risk_distribution=result.to_dict().get("risk_distribution", {}),
                metadata=result.metadata,
            ),
            message=f"Predictions generated: {result.n_predictions} records",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Prediction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


# ============================================================
# FORECAST ENDPOINTS
# ============================================================

@router.post("/forecast", response_model=BaseResponse[ForecastResultSchema])
async def generate_forecast(request: ForecastRequest):
    """Generate time-series forecast."""
    intel_type = _resolve_intelligence_type(request.intelligence_type)

    try:
        df = _load_processed_dataset()
        result = _forecast_engine.forecast_monthly(
            df=df,
            intelligence_type=intel_type,
            horizon_months=request.horizon_months,
            version_id=request.version_id,
        )

        await broadcast_event("Forecast Generated", {"intelligence_type": request.intelligence_type})
        await auto_sync_predictions(df)

        return BaseResponse(
            data=ForecastResultSchema(**result.to_dict()),
            message=f"Forecast generated: {request.horizon_months} months ahead",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Forecast failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Forecast failed: {str(e)}")


# ============================================================
# MODEL EVALUATION ENDPOINTS
# ============================================================

@router.post("/model/evaluate", response_model=BaseResponse[EvaluationResultSchema])
async def evaluate_model(request: EvaluateRequest):
    """Evaluate a model on the stored dataset."""
    intel_type = _resolve_intelligence_type(request.intelligence_type)

    try:
        start = time.perf_counter()
        df = _load_processed_dataset()

        from app.ml.confidence import (
            compute_classification_confidence,
            compute_regression_confidence,
        )
        from app.ml.metrics import (
            compute_classification_metrics,
            compute_regression_metrics,
        )
        from app.ml.utils import ModelTask, chronological_split, prepare_features

        feature_config = FEATURE_CONFIGS[intel_type]
        _, test_df = chronological_split(df, train_ratio=0.8)
        X_test, y_test = prepare_features(test_df, feature_config)

        model = _registry.load_model(intel_type, request.version_id)
        version = _registry.get_version(intel_type, request.version_id)

        y_pred = model.predict(X_test)

        if feature_config.task == ModelTask.CLASSIFICATION:
            y_prob = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else None
            metrics = compute_classification_metrics(y_test.values, y_pred, y_prob).to_dict()
            conf = compute_classification_confidence(y_prob, y_test.values) if y_prob is not None else None
        else:
            metrics = compute_regression_metrics(y_test.values, y_pred).to_dict()
            conf = compute_regression_confidence(y_pred, y_test.values)

        eval_time = (time.perf_counter() - start) * 1000

        return BaseResponse(
            data=EvaluationResultSchema(
                intelligence_type=intel_type.value,
                model_version=version.version_id if version else "unknown",
                metrics=metrics,
                confidence_summary=conf.to_dict() if conf else {},
                n_samples=len(X_test),
                evaluation_time_ms=eval_time,
            ),
            message="Model evaluation complete",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Evaluation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


# ============================================================
# MODEL REGISTRY ENDPOINTS
# ============================================================

@router.get("/models", response_model=BaseResponse[ModelListSchema])
async def list_models():
    """List all registered models."""
    all_models = _registry.list_all_models()
    total = sum(len(v) for v in all_models.values())

    model_schemas: dict[str, list[ModelVersionSchema]] = {}
    for key, versions in all_models.items():
        model_schemas[key] = [ModelVersionSchema(**v) for v in versions]

    return BaseResponse(
        data=ModelListSchema(models=model_schemas, total_models=total),
        message=f"Found {total} registered models",
    )


@router.get("/models/latest", response_model=BaseResponse[dict[str, ModelVersionSchema | None]])
async def get_latest_models():
    """Get the latest active model for each intelligence type."""
    latest: dict[str, ModelVersionSchema | None] = {}

    for intel_type in IntelligenceType:
        version = _registry.get_latest_version(intel_type)
        if version:
            latest[intel_type.value] = ModelVersionSchema(**version.to_dict())
        else:
            latest[intel_type.value] = None

    return BaseResponse(data=latest, message="Latest model versions retrieved")


@router.get("/metrics/{intelligence_type}", response_model=BaseResponse[dict[str, Any]])
async def get_model_metrics(intelligence_type: str):
    """Get metrics for the latest model of an intelligence type."""
    intel_type = _resolve_intelligence_type(intelligence_type)
    version = _registry.get_latest_version(intel_type)

    if not version:
        raise HTTPException(
            status_code=404,
            detail=f"No model found for {intelligence_type}",
        )

    return BaseResponse(
        data={
            "intelligence_type": intel_type.value,
            "version_id": version.version_id,
            "metrics": version.metrics,
            "created_at": version.created_at,
        },
        message="Model metrics retrieved",
    )


@router.get("/feature-importance/{intelligence_type}", response_model=BaseResponse[FeatureImportanceSchema])
async def get_feature_importance(intelligence_type: str):
    """Get feature importance for the latest model."""
    intel_type = _resolve_intelligence_type(intelligence_type)

    try:
        from app.ml.feature_importance import compute_feature_importance

        model = _registry.load_model(intel_type)
        version = _registry.get_latest_version(intel_type)
        features = version.features_used if version else []

        result = compute_feature_importance(model, features)
        return BaseResponse(
            data=FeatureImportanceSchema(**result.to_dict()),
            message="Feature importance computed",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Feature importance failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/training-history", response_model=BaseResponse[TrainingHistorySchema])
async def get_training_history(
    intelligence_type: str | None = Query(default=None),
):
    """Get training history, optionally filtered by intelligence type."""
    entries: list[TrainingHistoryEntry] = []

    if intelligence_type:
        intel_type = _resolve_intelligence_type(intelligence_type)
        versions = _registry.list_versions(intel_type)
    else:
        versions = []
        for intel_type in IntelligenceType:
            versions.extend(_registry.list_versions(intel_type))

    for v in versions:
        entries.append(TrainingHistoryEntry(
            version_id=v.version_id,
            intelligence_type=v.intelligence_type,
            created_at=v.created_at,
            metrics=v.metrics,
            training_duration_ms=v.training_duration_ms,
            n_training_samples=v.n_training_samples,
            is_active=v.is_active,
        ))

    # Sort by creation date descending
    entries.sort(key=lambda e: e.created_at, reverse=True)

    return BaseResponse(
        data=TrainingHistorySchema(entries=entries, total_entries=len(entries)),
        message=f"Training history: {len(entries)} entries",
    )


router.include_router(coordinator.router)
