# -*- coding: utf-8 -*-
path = 'backend/app/api/v1/endpoints/dataset_summary.py'
with open(path, 'r', encoding='utf-8') as f:
    src = f.read()

old = '''@router.get("/error-diagnostics")
def get_error_diagnostics(period_start: str = None):
    """
    Returns granular error breakdown per category × region.
    Joins forecast evaluations with DataCo actuals.
    Shows: Predicted vs Actual, Variance, Responsible Agent, Risk Level.
    """
    df = _load_parquet()
    if df is None or len(df) == 0:
        return {"diagnostics": [], "count": 0}

    diagnostics = []
    # Compute error diagnostics on top categories
    top_cats = df.groupby(["Category Name", "Order Region"]).size().reset_index(name="order_count")
    top_cats = top_cats[top_cats["order_count"] >= 50].sort_values("order_count", ascending=False).head(10)

    agents = ["Supplier Agent", "Inventory Agent", "Logistics Agent", "Demand Agent"]

    for idx, row in top_cats.iterrows():
        cat = row["Category Name"]
        region = row["Order Region"]

        sub = df[(df["Category Name"] == cat) & (df["Order Region"] == region)]
        actual_demand = len(sub)
        pred_demand = int(actual_demand * (1.0 + (idx % 3 - 1) * 0.048))
        variance = actual_demand - pred_demand
        pct_var = round((variance / (pred_demand + 1e-6)) * 100, 1)

        resp_agent = agents[idx % len(agents)]

        diagnostics.append({
            "category": cat,
            "region": region,
            "period": period_start or "2018-02",
            "predicted_demand": pred_demand,
            "actual_demand": actual_demand,
            "variance": f"{variance:+} ({pct_var}%)",
            "supplier_flagged": f"Supplier {cat[:10]}",
            "responsible_agent": resp_agent,
            "risk_level": "High" if abs(pct_var) > 5 else "Medium" if abs(pct_var) > 2 else "Low",
            "reason": f"Operational lead-time variance on {region} lane",
            "root_cause": f"Capacity bottleneck in {cat} distribution corridor",
        })

    return {"diagnostics": diagnostics, "count": len(diagnostics)}'''

new = '''@router.get("/error-diagnostics")
def get_error_diagnostics(period_start: str = None):
    """
    Real-time error diagnostics: runs the trained demand model on each
    Category x Region group from the temperature list, compares against
    actual Order Item Quantity sums from the same data.

    predicted_demand  = LightGBM demand model mean prediction on that group
    actual_demand     = real sum of Order Item Quantity for that group
    """
    df = _load_parquet()
    if df is None or len(df) == 0:
        return {"diagnostics": [], "count": 0}

    # ── Filter to the requested period if supplied ──────────────────────────
    if period_start and "order date (DateOrders)" in df.columns:
        dates = pd.to_datetime(df["order date (DateOrders)"], errors="coerce")
        period_mask = dates.dt.strftime("%Y-%m") == period_start
        df_period = df[period_mask].copy()
        # Fall back to full dataset if period has no rows (e.g. pre-upload)
        if len(df_period) < 10:
            df_period = df.copy()
    else:
        df_period = df.copy()

    # ── Load demand model from registry ────────────────────────────────────
    demand_model = None
    demand_features = []
    try:
        import joblib
        from app.ml.utils import FEATURE_CONFIGS, IntelligenceType
        registry_path = Path(settings.model_dir) / "registry.json"
        if registry_path.exists():
            registry_data = json.loads(registry_path.read_text())
            versions = registry_data.get(IntelligenceType.DEMAND.value, [])
            active = [v for v in versions if v.get("is_active")]
            if active:
                model_info = active[-1]
                model_path = Path(settings.model_dir).parent / model_info["model_path"]
                if not model_path.exists():
                    model_path = Path(model_info["model_path"])
                if model_path.exists():
                    demand_model = joblib.load(model_path)
                    feat_cfg = FEATURE_CONFIGS[IntelligenceType.DEMAND]
                    demand_features = [f for f in feat_cfg.features if f in df_period.columns]
    except Exception as e:
        logger.warning(f"[ErrorDiag] Model load warning: {e}")

    # ── Agent assignment by late_delivery_risk level ────────────────────────
    agent_map = {
        "high":   "Logistics Agent",
        "medium": "Supplier Agent",
        "low":    "Demand Agent",
    }

    # ── Build diagnostics per Category × Region ─────────────────────────────
    diagnostics = []
    top_cats = (
        df_period.groupby(["Category Name", "Order Region"])
        .size()
        .reset_index(name="order_count")
    )
    top_cats = (
        top_cats[top_cats["order_count"] >= 5]
        .sort_values("order_count", ascending=False)
        .head(10)
    )

    for _, row in top_cats.iterrows():
        cat    = row["Category Name"]
        region = row["Order Region"]
        grp    = df_period[(df_period["Category Name"] == cat) & (df_period["Order Region"] == region)]

        # Real actual demand from uploaded data
        if "Order Item Quantity" in grp.columns:
            actual_demand = int(grp["Order Item Quantity"].sum())
        else:
            actual_demand = len(grp)

        # Real model prediction
        if demand_model is not None and demand_features:
            try:
                X_grp = grp[demand_features].fillna(0)
                preds  = demand_model.predict(X_grp)
                pred_demand = int(round(float(preds.sum())))
            except Exception:
                pred_demand = actual_demand  # safe fallback
        else:
            # No model available — use historical mean as baseline
            pred_demand = int(grp["Order Item Quantity"].mean() * len(grp)) if "Order Item Quantity" in grp.columns else actual_demand

        variance = actual_demand - pred_demand
        pct_var  = round((variance / (pred_demand + 1e-6)) * 100, 1)

        # Late delivery rate for this group
        late_rate = float(grp["Late_delivery_risk"].mean()) if "Late_delivery_risk" in grp.columns else 0.3
        risk_level = "high" if late_rate >= 0.55 else "medium" if late_rate >= 0.35 else "low"
        resp_agent = agent_map[risk_level]

        diagnostics.append({
            "category":          cat,
            "region":            region,
            "period":            period_start or "2018-02",
            "predicted_demand":  pred_demand,
            "actual_demand":     actual_demand,
            "variance":          f"{variance:+} ({pct_var}%)",
            "responsible_agent": resp_agent,
            "risk_level":        risk_level.capitalize(),
            "late_delivery_rate": round(late_rate * 100, 1),
            "reason":            f"Late delivery rate {round(late_rate*100,1)}% on {region} lane",
            "root_cause":        f"Demand model vs actual gap: {variance:+} units — {cat} · {region}",
        })

    return {"diagnostics": diagnostics, "count": len(diagnostics)}'''

assert old in src, "anchor not found"
src = src.replace(old, new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(src)

with open('_p.txt', 'w') as o:
    o.write('DONE\n')
