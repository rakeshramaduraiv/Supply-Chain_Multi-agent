"""
tests/critical/test_graph_features_informative.py
===================================================
Asserts that each of the four GRAPH_CONTEXT_FEATURES carries genuine signal
on the training slice of processed_master.parquet.

Conditions (on the training 80% slice, chronologically):
  - nunique > 100   (not a handful of distinct values like scheduled days)
  - std    > 0.01   (not a near-constant column)

These tests skip when the parquet does not exist.
They FAIL (not skip) when the parquet exists but a feature fails the threshold —
that is a finding about the enrichment quality, not a missing file.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.ml.utils import GRAPH_CONTEXT_FEATURES

_PARQUET_PATH = Path(__file__).parents[2] / "data" / "uploads" / "processed_master.parquet"

_NUNIQUE_MIN = 100
_STD_MIN     = 0.01


def _training_slice() -> pd.DataFrame:
    if not _PARQUET_PATH.exists():
        pytest.skip(
            f"processed_master.parquet not found at {_PARQUET_PATH}. "
            "Run initialization to generate it."
        )
    df = pd.read_parquet(_PARQUET_PATH)
    if len(df) < 100_000:
        pytest.skip(
            f"processed_master.parquet has only {len(df):,} rows — this is a stub. "
            "Run initialization to regenerate it before these tests can pass."
        )
    split_idx = int(len(df) * 0.8)
    return df.iloc[:split_idx]


@pytest.mark.parametrize("feature", GRAPH_CONTEXT_FEATURES)
def test_graph_feature_nunique(feature: str):
    train = _training_slice()
    if feature not in train.columns:
        pytest.fail(
            f"GRAPH_CONTEXT_FEATURE '{feature}' is absent from "
            "processed_master.parquet. Re-run initialization."
        )
    n = train[feature].nunique()
    assert n > _NUNIQUE_MIN, (
        f"'{feature}' has only {n} distinct values on the training slice "
        f"(expected > {_NUNIQUE_MIN}). "
        "This feature carries no graph signal — it is likely a calendar flag "
        "or a scheduled-days column with few distinct values."
    )


@pytest.mark.parametrize("feature", GRAPH_CONTEXT_FEATURES)
def test_graph_feature_std(feature: str):
    train = _training_slice()
    if feature not in train.columns:
        pytest.fail(
            f"GRAPH_CONTEXT_FEATURE '{feature}' is absent from "
            "processed_master.parquet. Re-run initialization."
        )
    std = float(train[feature].std())
    assert std > _STD_MIN, (
        f"'{feature}' has std={std:.6f} on the training slice "
        f"(expected > {_STD_MIN}). "
        "This feature is near-constant and contributes no signal to the model."
    )
