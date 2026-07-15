"""
AMASCI Feature Importance
===========================
Feature ranking, gain/split importance, and visualization data generation.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FeatureImportanceResult:
    """Feature importance analysis result."""
    feature_names: list[str]
    gain_importance: list[float]
    split_importance: list[float]
    top_features: list[dict[str, Any]]
    ranking: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_names": self.feature_names,
            "gain_importance": self.gain_importance,
            "split_importance": self.split_importance,
            "top_features": self.top_features,
            "ranking": self.ranking,
        }


def compute_feature_importance(
    model: Any,
    feature_names: list[str],
    top_n: int = 10,
) -> FeatureImportanceResult:
    """
    Compute feature importance from a trained model.

    Supports LightGBM (gain + split) and scikit-learn (feature_importances_).
    """
    gain_importance: list[float] = []
    split_importance: list[float] = []

    # LightGBM models expose booster with importance_type parameter
    if hasattr(model, "booster_"):
        booster = model.booster_
        gain_raw = booster.feature_importance(importance_type="gain")
        split_raw = booster.feature_importance(importance_type="split")

        gain_total = gain_raw.sum() if gain_raw.sum() > 0 else 1.0
        split_total = split_raw.sum() if split_raw.sum() > 0 else 1.0

        gain_importance = (gain_raw / gain_total).tolist()
        split_importance = (split_raw / split_total).tolist()

    elif hasattr(model, "feature_importances_"):
        # scikit-learn style (RandomForest, etc.)
        raw = np.array(model.feature_importances_)
        total = raw.sum() if raw.sum() > 0 else 1.0
        gain_importance = (raw / total).tolist()
        split_importance = gain_importance  # RF only has one type

    else:
        # Fallback: uniform importance
        n = len(feature_names)
        gain_importance = [1.0 / n] * n
        split_importance = [1.0 / n] * n

    # Build ranking (sorted by gain importance descending)
    indexed = list(enumerate(gain_importance))
    indexed.sort(key=lambda x: x[1], reverse=True)

    ranking = []
    for rank, (idx, gain_val) in enumerate(indexed, start=1):
        ranking.append({
            "rank": rank,
            "feature": feature_names[idx],
            "gain_importance": round(gain_val, 6),
            "split_importance": round(split_importance[idx], 6),
        })

    top_features = ranking[:top_n]

    result = FeatureImportanceResult(
        feature_names=feature_names,
        gain_importance=[round(v, 6) for v in gain_importance],
        split_importance=[round(v, 6) for v in split_importance],
        top_features=top_features,
        ranking=ranking,
    )

    logger.info(f"Feature importance computed: top feature = {top_features[0]['feature'] if top_features else 'N/A'}")
    return result
