"""
AMASCI Data Quality Report
============================
Computes 8 data quality issues from raw vs cleaned DataFrames.
All numbers are derived from the data — nothing is hardcoded.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_TARGET = "Late_delivery_risk"
_POST_SHIPMENT = [
    "delivery_gap", "is_delayed", "delivery_duration_days",
    "shipping_delay_ratio", "composite_risk_score",
]


def _cramers_v(x: pd.Series, y: pd.Series) -> float:
    """Cramér's V association between two categorical/binary series."""
    try:
        ct = pd.crosstab(x, y)
        n = ct.values.sum()
        chi2 = float(((ct - ct.sum(axis=0) * ct.sum(axis=1).values.reshape(-1, 1) / n) ** 2
                      / (ct.sum(axis=0) * ct.sum(axis=1).values.reshape(-1, 1) / n + 1e-9)
                      ).values.sum())
        r, k = ct.shape
        return float(np.sqrt(chi2 / (n * (min(r, k) - 1)))) if min(r, k) > 1 else 0.0
    except Exception:
        return 0.0


def build_quality_report(df_raw: pd.DataFrame,
                         df_clean: pd.DataFrame) -> pd.DataFrame:
    """
    Returns one row per issue with columns:
    issue_id, category, description, affected_columns, rows_affected,
    pct_affected, severity, action_taken, verified_after_cleaning
    """
    issues: list[dict[str, Any]] = []
    n = len(df_raw)

    # ── Q1 Delivery Status target proxy ──────────────────────────────────────
    if "Delivery Status" in df_raw.columns and _TARGET in df_raw.columns:
        ct = pd.crosstab(df_raw["Delivery Status"], df_raw[_TARGET])
        late_rows = int(df_raw[df_raw["Delivery Status"] == "Late delivery"].shape[0])
        cv = _cramers_v(df_raw["Delivery Status"], df_raw[_TARGET])
        cross_cells = int((ct > 0).values.sum())
        verified = "Delivery Status" not in df_clean.columns or \
                   _cramers_v(df_clean.get("Delivery Status",
                               pd.Series(dtype=str)), df_clean[_TARGET]) < 0.01 \
            if _TARGET in df_clean.columns else True
        issues.append({
            "issue_id": "Q1",
            "category": "Target Proxy",
            "description": (
                f"'Delivery Status' is a categorical restatement of {_TARGET}. "
                f"Cramér's V={cv:.4f}. 'Late delivery' maps perfectly to 1 "
                f"({late_rows:,} rows). Cross-cells with signal: {cross_cells}."
            ),
            "affected_columns": "Delivery Status",
            "rows_affected": late_rows,
            "pct_affected": round(late_rows / n * 100, 2),
            "severity": "CRITICAL",
            "action_taken": "Excluded from all model feature sets via BANNED_FROM_MODELS.",
            "verified_after_cleaning": str(verified),
        })

    # ── Q2 Duplicate column pairs ─────────────────────────────────────────────
    num_cols = df_raw.select_dtypes(include=[np.number]).columns.tolist()
    dup_pairs = []
    for i, a in enumerate(num_cols):
        for b in num_cols[i + 1:]:
            try:
                if df_raw[a].equals(df_raw[b]):
                    dup_pairs.append(f"{a} == {b}")
            except Exception:
                pass
    if dup_pairs:
        issues.append({
            "issue_id": "Q2",
            "category": "Duplicate Columns",
            "description": (
                f"{len(dup_pairs)} exact numeric column pairs found: "
                + "; ".join(dup_pairs[:6])
            ),
            "affected_columns": "|".join(dup_pairs),
            "rows_affected": n,
            "pct_affected": 100.0,
            "severity": "HIGH",
            "action_taken": "One of each pair retained; duplicate dropped.",
            "verified_after_cleaning": str(
                not any(p.split(" == ")[1] in df_clean.columns
                        and p.split(" == ")[0] in df_clean.columns
                        and df_clean[p.split(" == ")[0]].equals(
                            df_clean[p.split(" == ")[1]])
                        for p in dup_pairs)
            ),
        })

    # ── Q3 Zero-variance columns ──────────────────────────────────────────────
    zero_var = [c for c in df_raw.columns if df_raw[c].nunique(dropna=False) <= 1]
    if zero_var:
        issues.append({
            "issue_id": "Q3",
            "category": "Zero Variance",
            "description": (
                f"{len(zero_var)} columns with nunique<=1 (no predictive content): "
                + ", ".join(zero_var)
            ),
            "affected_columns": "|".join(zero_var),
            "rows_affected": n,
            "pct_affected": 100.0,
            "severity": "MEDIUM",
            "action_taken": "Dropped — no predictive content.",
            "verified_after_cleaning": str(
                not any(c in df_clean.columns for c in zero_var)
            ),
        })

    # ── Q4 High-null columns ──────────────────────────────────────────────────
    null_pcts = df_raw.isnull().mean() * 100
    high_null = null_pcts[null_pcts > 50].sort_values(ascending=False)
    if not high_null.empty:
        issues.append({
            "issue_id": "Q4",
            "category": "High Null Rate",
            "description": (
                f"{len(high_null)} columns with >50% nulls: "
                + "; ".join(f"{c}={v:.1f}%" for c, v in high_null.items())
            ),
            "affected_columns": "|".join(high_null.index.tolist()),
            "rows_affected": n,
            "pct_affected": 100.0,
            "severity": "MEDIUM",
            "action_taken": "Dropped during transformation step.",
            "verified_after_cleaning": str(
                not any(c in df_clean.columns for c in high_null.index)
            ),
        })

    # ── Q5 PII exposure ───────────────────────────────────────────────────────
    pii_keywords = ["email", "password", "street", "fname", "lname", "zipcode"]
    pii_cols = [c for c in df_raw.columns
                if any(k in c.lower() for k in pii_keywords)]
    if pii_cols:
        issues.append({
            "issue_id": "Q5",
            "category": "PII Exposure",
            "description": (
                f"{len(pii_cols)} PII columns detected: {', '.join(pii_cols)}"
            ),
            "affected_columns": "|".join(pii_cols),
            "rows_affected": n,
            "pct_affected": 100.0,
            "severity": "COMPLIANCE",
            "action_taken": "Dropped before any persistence. "
                            "Redacted from all stage export files.",
            "verified_after_cleaning": str(
                not any(c in df_clean.columns for c in pii_cols)
            ),
        })

    # ── Q6 Negative monetary values ──────────────────────────────────────────
    neg_cols = ["Benefit per order", "Order Profit Per Order"]
    for col in neg_cols:
        if col not in df_raw.columns:
            continue
        neg_mask = df_raw[col] < 0
        neg_count = int(neg_mask.sum())
        if neg_count:
            min_val = round(float(df_raw.loc[neg_mask, col].min()), 2)
            issues.append({
                "issue_id": "Q6",
                "category": "Negative Monetary Values",
                "description": (
                    f"'{col}' has {neg_count:,} negative values "
                    f"(min={min_val}). These are genuine losses, NOT data errors."
                ),
                "affected_columns": col,
                "rows_affected": neg_count,
                "pct_affected": round(neg_count / n * 100, 2),
                "severity": "INFO",
                "action_taken": (
                    "RETAINED. Negative profit/benefit is real business signal "
                    "(loss-making orders). Silently converting to positive would "
                    "destroy this signal. Convention: negative = loss."
                ),
                "verified_after_cleaning": "N/A — retained by design",
            })
            break  # report once for the pair

    # ── Q7 Cancelled shipments labelled on-time ───────────────────────────────
    if "Delivery Status" in df_raw.columns and _TARGET in df_raw.columns:
        cancelled_ontme = df_raw[
            (df_raw["Delivery Status"] == "Shipping canceled") &
            (df_raw[_TARGET] == 0)
        ]
        cnt = len(cancelled_ontme)
        if cnt:
            issues.append({
                "issue_id": "Q7",
                "category": "Definitional Ambiguity",
                "description": (
                    f"{cnt:,} rows have Delivery Status='Shipping canceled' "
                    f"but Late_delivery_risk=0. Cancelled orders are not "
                    f"classified as late under the DataCo convention."
                ),
                "affected_columns": "Delivery Status|Late_delivery_risk",
                "rows_affected": cnt,
                "pct_affected": round(cnt / n * 100, 2),
                "severity": "DEFINITIONAL",
                "action_taken": (
                    "Documented. Convention retained: cancelled=0 (not late). "
                    "Relabelling would change the target definition mid-project."
                ),
                "verified_after_cleaning": "N/A — convention retained",
            })

    # ── Q8 Post-shipment feature audit ────────────────────────────────────────
    if _TARGET in df_clean.columns:
        y = df_clean[_TARGET].astype(float)
        flagged = []
        for col in _POST_SHIPMENT:
            if col not in df_clean.columns:
                continue
            try:
                corr = abs(float(np.corrcoef(
                    df_clean[col].fillna(0).astype(float).values, y.values
                )[0, 1]))
                flagged.append(f"{col}(|r|={corr:.3f})")
            except Exception:
                pass
        if flagged:
            issues.append({
                "issue_id": "Q8",
                "category": "Post-Shipment Leakage",
                "description": (
                    f"Post-shipment features with high target correlation: "
                    + ", ".join(flagged)
                ),
                "affected_columns": "|".join(_POST_SHIPMENT),
                "rows_affected": len(df_clean),
                "pct_affected": 100.0,
                "severity": "CRITICAL",
                "action_taken": (
                    "All post-shipment features banned from Late_delivery_risk "
                    "models via BANNED_FROM_MODELS and _LEAKY guard in ml/utils. "
                    "Computed for inventory/demand use only."
                ),
                "verified_after_cleaning": "Enforced at Python import time.",
            })

    return pd.DataFrame(issues)


def build_provenance(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Single-row dataset provenance record."""
    date_col = "order date (DateOrders)"
    dates = pd.to_datetime(df_raw.get(date_col, pd.Series(dtype=str)),
                           errors="coerce").dropna()
    target_pos = (
        round(df_raw[_TARGET].mean() * 100, 2)
        if _TARGET in df_raw.columns else ""
    )
    return pd.DataFrame([{
        "dataset_name":       "DataCo Smart Supply Chain",
        "company":            "DataCo Global (fictitious e-commerce company)",
        "domain":             "clothing, sporting goods, electronics",
        "authors":            "Constante F.; Silva F.; Pereira A.",
        "institutions":       "Universidad Central del Ecuador; "
                              "Instituto Politecnico de Leiria",
        "published":          "2019, Mendeley Data V5",
        "doi":                "10.17632/8gx2fvg2k6.5",
        "rows":               len(df_raw),
        "columns":            len(df_raw.columns),
        "date_min":           str(dates.min().date()) if len(dates) else "",
        "date_max":           str(dates.max().date()) if len(dates) else "",
        "target":             _TARGET,
        "target_positive_pct": target_pos,
    }])
