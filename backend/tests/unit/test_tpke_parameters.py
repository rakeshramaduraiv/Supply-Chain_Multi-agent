"""
Unit tests — TPKE Parameter Alignment (spec §4, Invariant 5).

Frozen values: θ_add=0.70, K=3, δ=0.05, θ_rem=0.10, W=30

Verifies:
  - config.py defaults match the frozen spec
  - TPKEEngine reads the same values from settings
  - PatternDetector is constructed with the correct K and θ
  - EdgeManager uses the correct decay rate and removal threshold
"""

import pytest

from app.core.config import get_settings
from app.core.constants import TPKE_MIN_EDGE_WEIGHT

# ── Frozen spec values ────────────────────────────────────────────────────────
FROZEN = {
    "tpke_confidence_threshold": 0.70,   # θ_add
    "tpke_top_k":                3,       # K
    "tpke_decay_rate":           0.05,    # δ
    "tpke_removal_threshold":    0.10,    # θ_rem
    "tpke_window_size_days":     30,      # W
}


class TestConfigDefaults:
    """config.py must carry the frozen TPKE values as defaults."""

    def test_confidence_threshold(self):
        s = get_settings()
        assert s.tpke_confidence_threshold == FROZEN["tpke_confidence_threshold"], (
            f"tpke_confidence_threshold={s.tpke_confidence_threshold} "
            f"(expected {FROZEN['tpke_confidence_threshold']})"
        )

    def test_top_k(self):
        s = get_settings()
        assert s.tpke_top_k == FROZEN["tpke_top_k"], (
            f"tpke_top_k={s.tpke_top_k} (expected {FROZEN['tpke_top_k']})"
        )

    def test_decay_rate(self):
        s = get_settings()
        assert s.tpke_decay_rate == FROZEN["tpke_decay_rate"], (
            f"tpke_decay_rate={s.tpke_decay_rate} (expected {FROZEN['tpke_decay_rate']})"
        )

    def test_removal_threshold(self):
        s = get_settings()
        assert s.tpke_removal_threshold == FROZEN["tpke_removal_threshold"], (
            f"tpke_removal_threshold={s.tpke_removal_threshold} "
            f"(expected {FROZEN['tpke_removal_threshold']})"
        )

    def test_window_size_days(self):
        s = get_settings()
        assert s.tpke_window_size_days == FROZEN["tpke_window_size_days"], (
            f"tpke_window_size_days={s.tpke_window_size_days} "
            f"(expected {FROZEN['tpke_window_size_days']})"
        )

    def test_all_frozen_values_at_once(self):
        """Single combined assertion for CI gate output."""
        s = get_settings()
        mismatches = []
        for key, expected in FROZEN.items():
            actual = getattr(s, key)
            if actual != expected:
                mismatches.append(f"  {key}: got {actual}, expected {expected}")
        assert not mismatches, (
            "TPKE parameter mismatch in config.py:\n" + "\n".join(mismatches)
        )


class TestConstantsAlignment:
    """constants.py TPKE_MIN_EDGE_WEIGHT must equal tpke_removal_threshold."""

    def test_min_edge_weight_equals_removal_threshold(self):
        s = get_settings()
        assert TPKE_MIN_EDGE_WEIGHT == s.tpke_removal_threshold, (
            f"TPKE_MIN_EDGE_WEIGHT={TPKE_MIN_EDGE_WEIGHT} != "
            f"tpke_removal_threshold={s.tpke_removal_threshold}. "
            f"EdgeManager uses the constant; config drives the spec. They must agree."
        )


class TestPatternDetectorParameters:
    """PatternDetector must be constructed with frozen K and θ."""

    def test_pattern_detector_uses_frozen_k(self):
        from app.tpke.pattern import PatternDetector
        s = get_settings()
        detector = PatternDetector(
            window_size_days=s.tpke_window_size_days,
            frequency_threshold=s.tpke_frequency_threshold,
            confidence_threshold=s.tpke_confidence_threshold,
            lag_days=s.tpke_lag_days,
        )
        assert detector._K == FROZEN["tpke_top_k"], (
            f"PatternDetector._K={detector._K} (expected {FROZEN['tpke_top_k']})"
        )

    def test_pattern_detector_uses_frozen_theta(self):
        from app.tpke.pattern import PatternDetector
        s = get_settings()
        detector = PatternDetector(
            window_size_days=s.tpke_window_size_days,
            frequency_threshold=s.tpke_frequency_threshold,
            confidence_threshold=s.tpke_confidence_threshold,
            lag_days=s.tpke_lag_days,
        )
        assert detector._theta == FROZEN["tpke_confidence_threshold"], (
            f"PatternDetector._theta={detector._theta} "
            f"(expected {FROZEN['tpke_confidence_threshold']})"
        )

    def test_pattern_detector_uses_frozen_window(self):
        from app.tpke.pattern import PatternDetector
        s = get_settings()
        detector = PatternDetector(
            window_size_days=s.tpke_window_size_days,
            frequency_threshold=s.tpke_frequency_threshold,
            confidence_threshold=s.tpke_confidence_threshold,
            lag_days=s.tpke_lag_days,
        )
        assert detector._window_days == FROZEN["tpke_window_size_days"], (
            f"PatternDetector._window_days={detector._window_days} "
            f"(expected {FROZEN['tpke_window_size_days']})"
        )


class TestEdgeManagerDecayRate:
    """EdgeManager must use the frozen decay rate from settings."""

    def test_edge_manager_decay_rate(self):
        from unittest.mock import MagicMock
        from app.tpke.edge_manager import EdgeManager
        mock_conn = MagicMock()
        manager = EdgeManager(mock_conn, session=None)
        assert manager._decay_rate == FROZEN["tpke_decay_rate"], (
            f"EdgeManager._decay_rate={manager._decay_rate} "
            f"(expected {FROZEN['tpke_decay_rate']})"
        )


class TestTPKEEngineReportParameters:
    """TPKEEngine.get_status() must report the frozen parameter values."""

    @pytest.mark.asyncio
    async def test_engine_status_reports_frozen_params(self):
        from unittest.mock import AsyncMock, MagicMock
        from app.tpke.engine import TPKEEngine

        mock_conn = MagicMock()
        mock_conn.execute_query = AsyncMock(return_value=[{"cnt": 0}])
        mock_session = AsyncMock()

        engine = TPKEEngine(mock_conn, mock_session)
        status = await engine.get_status()

        params = status["parameters"]
        assert params["confidence_threshold_theta"] == FROZEN["tpke_confidence_threshold"]
        assert params["frequency_threshold_K"] == FROZEN["tpke_top_k"]
        assert params["decay_rate"] == FROZEN["tpke_decay_rate"]
        assert params["window_size_days"] == FROZEN["tpke_window_size_days"]
