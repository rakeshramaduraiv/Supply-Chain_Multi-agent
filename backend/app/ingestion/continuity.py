"""
AMASCI Continuity Validator
=============================
validate_continuity(new_df, cumulative_df) -> ContinuityReport

REJECT (raises ContinuityError, HTTP 422):
  - Any order_date outside the claimed period's calendar month
  - date_min(new) <= date_max(cumulative)  — overlap or replay
  - Gap from cumulative date_max > 62 days
  - >2% of order_item_id already present in cumulative
  - target values outside {0, 1}

WARN (accept, flag in response):
  - Late rate more than 3 sigma from the trailing 6-month mean
  - Row count deviating >50% from the trailing monthly mean

Warnings surface in ContinuityReport.warnings and must be forwarded to
CycleResponse so the UI can render them in CycleStageTracker.
A detected drift warning is a feature, not an error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


class ContinuityError(ValueError):
    """Raised on a hard REJECT condition. Callers should return HTTP 422."""


@dataclass
class ContinuityReport:
    ok: bool                        # False only on REJECT (exception already raised)
    warnings: list[str] = field(default_factory=list)
    period: Optional[str] = None    # "YYYY-MM" claimed by the upload
    rows_new: int = 0
    rows_cumulative: int = 0
    date_min_new: Optional[str] = None
    date_max_new: Optional[str] = None
    date_max_cumulative: Optional[str] = None
    late_rate_new: Optional[float] = None
    late_rate_trailing_mean: Optional[float] = None
    late_rate_trailing_std: Optional[float] = None
    duplicate_id_rate: float = 0.0


def validate_continuity(
    new_df: pd.DataFrame,
    cumulative_df: pd.DataFrame,
    claimed_period: Optional[str] = None,  # "YYYY-MM"
) -> ContinuityReport:
    """
    Validate new_df against cumulative_df.

    Parameters
    ----------
    new_df : DataFrame with canonical column names (post schema_adapter.adapt)
    cumulative_df : all previously accepted rows, same schema
    claimed_period : "YYYY-MM" string from the upload manifest/filename

    Returns
    -------
    ContinuityReport — always returned on WARN; raises ContinuityError on REJECT.
    """
    report = ContinuityReport(ok=True, rows_new=len(new_df), rows_cumulative=len(cumulative_df))
    warnings: list[str] = []

    # ── Resolve date column ───────────────────────────────────────────────────
    date_col = "order_date" if "order_date" in new_df.columns else None
    if date_col is None:
        raise ContinuityError("new_df has no 'order_date' column — run schema_adapter first.")

    new_dates = pd.to_datetime(new_df[date_col], errors="coerce")
    if new_dates.isna().all():
        raise ContinuityError("order_date column contains no parseable dates.")

    date_min_new = new_dates.min()
    date_max_new = new_dates.max()
    report.date_min_new = str(date_min_new.date())
    report.date_max_new = str(date_max_new.date())

    # ── 1. Date containment: all rows must be within the claimed month ────────
    if claimed_period:
        report.period = claimed_period
        try:
            period_ts = pd.Period(claimed_period, freq="M")
            period_start = period_ts.start_time
            period_end   = period_ts.end_time
        except Exception:
            raise ContinuityError(f"claimed_period '{claimed_period}' is not a valid YYYY-MM string.")

        out_of_month = new_dates.dropna()
        out_of_month = out_of_month[(out_of_month < period_start) | (out_of_month > period_end)]
        if len(out_of_month) > 0:
            raise ContinuityError(
                f"REJECT: {len(out_of_month)} rows have order_date outside claimed period "
                f"{claimed_period} ({period_start.date()} .. {period_end.date()}). "
                f"Sample dates: {sorted(out_of_month.dt.date.unique())[:5]}"
            )

    # ── 2. Overlap / replay check ─────────────────────────────────────────────
    if len(cumulative_df) > 0 and date_col in cumulative_df.columns:
        cum_dates = pd.to_datetime(cumulative_df[date_col], errors="coerce").dropna()
        if not cum_dates.empty:
            date_max_cum = cum_dates.max()
            report.date_max_cumulative = str(date_max_cum.date())

            if date_min_new <= date_max_cum:
                raise ContinuityError(
                    f"REJECT: new data date_min ({date_min_new.date()}) <= "
                    f"cumulative date_max ({date_max_cum.date()}). "
                    f"This is an overlap or replay."
                )

            # ── 3. Gap check ──────────────────────────────────────────────────
            gap_days = (date_min_new - date_max_cum).days
            if gap_days > 62:
                raise ContinuityError(
                    f"REJECT: gap of {gap_days} days between cumulative date_max "
                    f"({date_max_cum.date()}) and new date_min ({date_min_new.date()}). "
                    f"Maximum allowed gap is 62 days."
                )

    # ── 4. Duplicate order_item_id check ──────────────────────────────────────
    id_col = "order_item_id" if "order_item_id" in new_df.columns else None
    if id_col and id_col in cumulative_df.columns and len(cumulative_df) > 0:
        new_ids = set(new_df[id_col].dropna().astype(str))
        cum_ids = set(cumulative_df[id_col].dropna().astype(str))
        dup_count = len(new_ids & cum_ids)
        dup_rate  = dup_count / max(len(new_ids), 1)
        report.duplicate_id_rate = round(dup_rate, 4)
        if dup_rate > 0.02:
            raise ContinuityError(
                f"REJECT: {dup_count} order_item_ids ({dup_rate:.1%}) already present "
                f"in cumulative data. Maximum allowed duplicate rate is 2%."
            )

    # ── 5. Target value check ─────────────────────────────────────────────────
    target_col = "target" if "target" in new_df.columns else None
    if target_col:
        invalid_target = new_df[target_col].dropna()
        invalid_target = invalid_target[~invalid_target.isin([0, 1, 0.0, 1.0])]
        if len(invalid_target) > 0:
            raise ContinuityError(
                f"REJECT: {len(invalid_target)} rows have target values outside {{0, 1}}. "
                f"Sample values: {sorted(invalid_target.unique())[:5]}"
            )

    # ── WARN: late rate drift ─────────────────────────────────────────────────
    if target_col and len(cumulative_df) > 0 and target_col in cumulative_df.columns:
        new_late_rate = float(new_df[target_col].mean())
        report.late_rate_new = round(new_late_rate, 4)

        # Trailing 6-month mean from cumulative
        if date_col in cumulative_df.columns:
            cum_dates_s = pd.to_datetime(cumulative_df[date_col], errors="coerce")
            valid_mask = cum_dates_s.notna()
            valid_dates = cum_dates_s[valid_mask]
            valid_cum = cumulative_df[valid_mask]

            cutoff = date_min_new - pd.DateOffset(months=6)
            trailing = valid_cum[valid_dates >= cutoff]
            trailing_dates = valid_dates[valid_dates >= cutoff]
        else:
            trailing = cumulative_df
            trailing_dates = pd.to_datetime(trailing[date_col], errors="coerce").dropna()
            trailing = trailing.loc[trailing_dates.index]

        if len(trailing) > 0 and len(trailing_dates) > 0:
            # Monthly late rates for std calculation
            monthly_rates = trailing.groupby(trailing_dates.dt.to_period("M"))[target_col].mean()
            monthly_rates = monthly_rates.tail(6)

            if len(monthly_rates) >= 2:
                trail_mean = float(monthly_rates.mean())
                trail_std  = float(monthly_rates.std())
                report.late_rate_trailing_mean = round(trail_mean, 4)
                report.late_rate_trailing_std  = round(trail_std, 4)

                if trail_std > 0 and abs(new_late_rate - trail_mean) > 3 * trail_std:
                    warnings.append(
                        f"DRIFT_LATE_RATE: new late rate {new_late_rate:.3f} is "
                        f"{abs(new_late_rate - trail_mean) / trail_std:.1f} sigma from "
                        f"trailing 6-month mean {trail_mean:.3f} "
                        f"(std={trail_std:.3f})"
                    )

    # ── WARN: row count deviation ─────────────────────────────────────────────
    if len(cumulative_df) > 0 and date_col in cumulative_df.columns:
        cum_dates_s = pd.to_datetime(cumulative_df[date_col], errors="coerce").dropna()
        if not cum_dates_s.empty:
            monthly_counts = cumulative_df.loc[cum_dates_s.index].groupby(cum_dates_s.dt.to_period("M")).size()
            monthly_counts = monthly_counts.tail(6)

            if len(monthly_counts) >= 2:
                mean_count = float(monthly_counts.mean())
                if mean_count > 0:
                    deviation = abs(len(new_df) - mean_count) / mean_count
                    if deviation > 0.50:
                        warnings.append(
                            f"DRIFT_ROW_COUNT: new upload has {len(new_df)} rows, "
                            f"trailing monthly mean is {mean_count:.0f} "
                            f"(deviation={deviation:.1%}, threshold=50%)"
                        )

    report.warnings = warnings
    return report
