"""
Unit tests for Feature Importance module.
"""

import numpy as np
import pytest
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.ensemble import RandomForestClassifier

from app.ml.feature_importance import FeatureImportanceResult, compute_feature_importance


def _train_lgbm_classifier():
    X = np.random.rand(200, 5)
    y = np.random.randint(0, 2, 200)
    model = LGBMClassifier(n_estimators=10, max_depth=3, verbose=-1, random_state=42)
    model.fit(X, y)
    return model


def _train_lgbm_regressor():
    X = np.random.rand(200, 5)
    y = np.random.rand(200) * 100
    model = LGBMRegressor(n_estimators=10, max_depth=3, verbose=-1, random_state=42)
    model.fit(X, y)
    return model


def _train_random_forest():
    X = np.random.rand(200, 5)
    y = np.random.randint(0, 2, 200)
    model = RandomForestClassifier(n_estimators=10, max_depth=3, random_state=42)
    model.fit(X, y)
    return model


class TestFeatureImportance:
    """Tests for feature importance computation."""

    def test_lgbm_classifier(self):
        model = _train_lgbm_classifier()
        features = ["f1", "f2", "f3", "f4", "f5"]
        result = compute_feature_importance(model, features)

        assert len(result.gain_importance) == 5
        assert len(result.split_importance) == 5
        assert len(result.ranking) == 5
        assert result.ranking[0]["rank"] == 1
        # Importances should sum to ~1
        assert abs(sum(result.gain_importance) - 1.0) < 0.01

    def test_lgbm_regressor(self):
        model = _train_lgbm_regressor()
        features = ["f1", "f2", "f3", "f4", "f5"]
        result = compute_feature_importance(model, features)

        assert len(result.gain_importance) == 5
        assert all(v >= 0 for v in result.gain_importance)

    def test_random_forest(self):
        model = _train_random_forest()
        features = ["f1", "f2", "f3", "f4", "f5"]
        result = compute_feature_importance(model, features)

        assert len(result.gain_importance) == 5
        assert abs(sum(result.gain_importance) - 1.0) < 0.01

    def test_top_n(self):
        model = _train_lgbm_classifier()
        features = ["f1", "f2", "f3", "f4", "f5"]
        result = compute_feature_importance(model, features, top_n=3)

        assert len(result.top_features) == 3
        assert len(result.ranking) == 5  # Full ranking still available

    def test_ranking_sorted(self):
        model = _train_lgbm_classifier()
        features = ["f1", "f2", "f3", "f4", "f5"]
        result = compute_feature_importance(model, features)

        for i in range(1, len(result.ranking)):
            assert result.ranking[i - 1]["gain_importance"] >= result.ranking[i]["gain_importance"]

    def test_to_dict(self):
        model = _train_lgbm_classifier()
        features = ["f1", "f2", "f3", "f4", "f5"]
        result = compute_feature_importance(model, features)
        d = result.to_dict()

        assert "feature_names" in d
        assert "gain_importance" in d
        assert "split_importance" in d
        assert "top_features" in d
        assert "ranking" in d
