# ML Intelligence Layer - Developer Documentation

## Architecture Overview

The ML Intelligence Layer implements four independent intelligence services for supply chain prediction and forecasting. It follows Clean Architecture with strict separation of concerns.

```
app/ml/
├── training/          # Model training pipelines
├── prediction/        # Real-time & batch prediction engines
├── forecasting/       # Time-series forecasting
├── validation/        # Walk-forward validation framework
├── registry/          # Model versioning & lifecycle
├── metrics/           # Evaluation metrics (regression + classification)
├── feature_importance/# Feature ranking & analysis
├── confidence/        # Prediction confidence estimation
└── utils/             # Shared constants, feature configs, helpers
```

## Intelligence Services

| Service | Model | Task | Target |
|---------|-------|------|--------|
| Demand | LightGBM Regressor | Regression | 7-Day Demand (Order Item Quantity) |
| Inventory | LightGBM Classifier | Classification | Stockout Prediction (Late_delivery_risk) |
| Supplier | RandomForest Classifier | Classification | Late Delivery Risk |
| Logistics | LightGBM Classifier | Classification | Route Delay Risk (Late_delivery_risk) |

## Training Pipeline

```
Dataset Loading → Feature Selection → Chronological Split → Walk-Forward Validation
    → Final Training → Evaluation → Feature Importance → Confidence → Model Save
```

### Usage

```python
from app.ml.training import TrainingOrchestrator
from app.ml.registry import ModelRegistry
from app.ml.utils import IntelligenceType

registry = ModelRegistry()
orchestrator = TrainingOrchestrator(registry)

# Train all models
results = orchestrator.train_all(df, dataset_version="v1.0")

# Train single model
result = orchestrator.train_single(df, IntelligenceType.DEMAND)
```

## Walk-Forward Validation

Expanding window cross-validation that respects temporal ordering:

```
[====TRAIN====][TEST]
[======TRAIN======][TEST]
[========TRAIN========][TEST]
[==========TRAIN==========][TEST]
[============TRAIN============][TEST]
```

```python
from app.ml.validation import WalkForwardValidator
from app.ml.utils import FEATURE_CONFIGS, IntelligenceType

validator = WalkForwardValidator(n_splits=5)
result = validator.validate(
    df=df,
    feature_config=FEATURE_CONFIGS[IntelligenceType.INVENTORY],
    model_factory=lambda: LGBMClassifier(n_estimators=100, verbose=-1),
)
print(result.aggregated_metrics)
```

## Prediction Engine

```python
from app.ml.prediction import PredictionEngine

engine = PredictionEngine(registry)

# Batch prediction
result = engine.predict(df, IntelligenceType.SUPPLIER)
print(f"Predictions: {result.n_predictions}, Confidence: {result.mean_confidence:.2f}")

# Single record
record = {"Days for shipping (real)": 5, "Sales": 200.0, ...}
pred = engine.predict_single(record, IntelligenceType.SUPPLIER)
print(f"Risk: {pred.risk_level}, Confidence: {pred.confidence:.2f}")
```

## Forecasting Engine

```python
from app.ml.forecasting import ForecastEngine

engine = ForecastEngine(registry)
result = engine.forecast_monthly(df, IntelligenceType.INVENTORY, horizon_months=3)

for period in result.forecast_periods:
    print(f"{period.period}: {period.predicted_value:.2f} "
          f"[{period.lower_bound:.2f}, {period.upper_bound:.2f}] "
          f"conf={period.confidence_score:.2f}")
```

## Model Registry

```python
from app.ml.registry import ModelRegistry
from app.ml.utils import IntelligenceType

registry = ModelRegistry()

# List all models
all_models = registry.list_all_models()

# Get latest version
version = registry.get_latest_version(IntelligenceType.DEMAND)

# Load model
model = registry.load_model(IntelligenceType.DEMAND)

# Rollback
registry.rollback(IntelligenceType.DEMAND, "demand_v_20240101_abc123")
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/ml/train` | Train single intelligence model |
| POST | `/api/v1/ml/train/all` | Train all intelligence models |
| POST | `/api/v1/ml/train/upload` | Train with uploaded CSV |
| POST | `/api/v1/ml/predict` | Batch prediction from uploaded CSV |
| POST | `/api/v1/ml/predict/dataset` | Predict using stored dataset |
| POST | `/api/v1/ml/forecast` | Generate time-series forecast |
| POST | `/api/v1/ml/model/evaluate` | Evaluate model on holdout |
| GET | `/api/v1/ml/models` | List all registered models |
| GET | `/api/v1/ml/models/latest` | Get latest model versions |
| GET | `/api/v1/ml/metrics/{type}` | Get metrics for intelligence type |
| GET | `/api/v1/ml/feature-importance/{type}` | Get feature importance |
| GET | `/api/v1/ml/training-history` | Get training history |

## Feature Configuration

Features are defined per intelligence service in `app/ml/utils/__init__.py`. Each service has:
- Feature list (numeric columns from processed DataCo dataset)
- Target column
- Task type (regression/classification)

## Metrics

### Regression (Demand)
- MAE, RMSE, MAPE, R²

### Classification (Inventory, Supplier, Logistics)
- Accuracy, Precision, Recall, F1, ROC AUC, Confusion Matrix

## Confidence Engine

- **Classification**: Confidence = distance from decision boundary (|p - 0.5| × 2)
- **Regression**: Residual-based confidence (1 - normalized_residual)
- **Calibration**: Expected Calibration Error (ECE) with binning

## Testing

```bash
# Unit tests (77 tests)
pytest tests/unit/ml/ -v --override-ini="addopts="

# Integration tests (5 tests)
pytest tests/integration/ml/ -v --override-ini="addopts="

# All ML tests
pytest tests/unit/ml/ tests/integration/ml/ -v --override-ini="addopts="
```

## Extension Points

This module is designed to connect with:
- **Knowledge Graph Module**: Model predictions feed into graph node attributes
- **TPKE Module**: Temporal patterns trigger model retraining
- **GraphRAG Module**: Model outputs provide context for reasoning
- **Dashboard Module**: Metrics and forecasts displayed in UI
