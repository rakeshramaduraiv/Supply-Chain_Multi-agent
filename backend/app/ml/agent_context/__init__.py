"""
AMASCI Collaborative Multi-Agent Context Bus
==============================================
Lightweight shared prediction context that flows sequentially through agents:

    Demand Agent  →  Supplier Agent  →  Inventory Agent  →  Logistics Agent

Each agent reads the upstream context, enriches its own prediction with it,
then writes its result back so the next agent can consume it.

No model retraining. No LightGBM changes.
The context bus only carries scalar signals that downstream agents can use
as soft feature overrides or confidence adjustments.

Usage
-----
    from app.ml.agent_context import AgentContextBus, run_collaborative_pipeline

    bus = AgentContextBus()
    results = await run_collaborative_pipeline(df, bus)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from app.ml.prediction import (
    DemandAgent,
    InventoryAgent,
    LogisticsAgent,
    PredictionResult,
    SupplierAgent,
)
from app.ml.registry import ModelRegistry

logger = logging.getLogger(__name__)


@dataclass
class AgentSignal:
    """A single agent's output signal passed to downstream agents."""
    agent: str
    mean_prediction: float
    mean_confidence: float
    risk_level: str          # low / medium / high / critical
    risk_probability: float  # mean probability for classifiers, normalised for regressor
    n_predictions: int
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "mean_prediction": round(self.mean_prediction, 4),
            "mean_confidence": round(self.mean_confidence, 4),
            "risk_level": self.risk_level,
            "risk_probability": round(self.risk_probability, 4),
            "n_predictions": self.n_predictions,
            "timestamp": self.timestamp,
        }


@dataclass
class AgentContextBus:
    """
    Carries upstream agent signals so downstream agents can adjust their
    feature inputs before prediction.

    Signals are written in order: demand → supplier → inventory → logistics.
    """
    demand: AgentSignal | None = None
    supplier: AgentSignal | None = None
    inventory: AgentSignal | None = None
    logistics: AgentSignal | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "demand": self.demand.to_dict() if self.demand else None,
            "supplier": self.supplier.to_dict() if self.supplier else None,
            "inventory": self.inventory.to_dict() if self.inventory else None,
            "logistics": self.logistics.to_dict() if self.logistics else None,
        }


# ── Feature injection helpers ─────────────────────────────────────────────────

def _inject_demand_signal(df: pd.DataFrame, signal: AgentSignal) -> pd.DataFrame:
    """
    Inject demand agent signal into supplier feature space.

    If demand risk is high, we increase the effective order quantity signal
    to reflect surge pressure on suppliers.
    """
    df = df.copy()
    if signal.risk_level in ("high", "critical") and "Order Item Quantity" in df.columns:
        surge_factor = 1.0 + (signal.risk_probability * 0.3)
        df["Order Item Quantity"] = df["Order Item Quantity"] * surge_factor
        logger.debug(
            f"[ContextBus] Demand surge factor {surge_factor:.3f} "
            f"injected into supplier features"
        )
    return df


def _inject_supplier_signal(df: pd.DataFrame, signal: AgentSignal) -> pd.DataFrame:
    """
    Inject supplier agent signal into inventory feature space.

    High supplier risk → increase effective shipping delay signal.
    """
    df = df.copy()
    if signal.risk_level in ("high", "critical") and "Days for shipping (real)" in df.columns:
        delay_add = signal.risk_probability * 2.0  # up to +2 days
        df["Days for shipping (real)"] = df["Days for shipping (real)"] + delay_add
        logger.debug(
            f"[ContextBus] Supplier delay signal +{delay_add:.2f} days "
            f"injected into inventory features"
        )
    return df


def _inject_inventory_signal(df: pd.DataFrame, signal: AgentSignal) -> pd.DataFrame:
    """
    Inject inventory agent signal into logistics feature space.

    High inventory stress → increase delivery duration signal.
    """
    df = df.copy()
    if signal.risk_level in ("high", "critical") and "delivery_duration_days" in df.columns:
        stress_add = signal.risk_probability * 1.5
        df["delivery_duration_days"] = df["delivery_duration_days"] + stress_add
        logger.debug(
            f"[ContextBus] Inventory stress +{stress_add:.2f} days "
            f"injected into logistics features"
        )
    return df


# ── Signal builder ────────────────────────────────────────────────────────────

def _build_signal(agent_name: str, result: PredictionResult) -> AgentSignal:
    """Convert a PredictionResult into an AgentSignal for the context bus."""
    mean_pred = float(np.mean(result.predictions)) if result.predictions else 0.0

    # For classifiers, mean probability is the risk signal
    if result.probabilities:
        risk_prob = float(np.mean(result.probabilities))
    else:
        # Regressor: normalise prediction to [0,1] using a soft cap at 500 units
        risk_prob = min(1.0, mean_pred / 500.0)

    # Derive risk level from probability
    if risk_prob >= 0.75:
        risk_level = "critical"
    elif risk_prob >= 0.50:
        risk_level = "high"
    elif risk_prob >= 0.25:
        risk_level = "medium"
    else:
        risk_level = "low"

    return AgentSignal(
        agent=agent_name,
        mean_prediction=mean_pred,
        mean_confidence=result.mean_confidence,
        risk_level=risk_level,
        risk_probability=risk_prob,
        n_predictions=result.n_predictions,
    )


# ── Collaborative pipeline ────────────────────────────────────────────────────

def run_collaborative_pipeline(
    df: pd.DataFrame,
    registry: ModelRegistry | None = None,
) -> dict[str, Any]:
    """
    Run all four agents in sequence, passing context downstream.

    Pipeline:
        1. Demand Agent  → produces demand signal
        2. Supplier Agent receives demand signal → produces supplier signal
        3. Inventory Agent receives supplier signal → produces inventory signal
        4. Logistics Agent receives inventory signal → produces logistics signal

    Returns:
        {
            "bus": AgentContextBus.to_dict(),
            "results": {
                "demand": PredictionResult.to_dict(),
                "supplier": ...,
                "inventory": ...,
                "logistics": ...,
            }
        }
    """
    bus = AgentContextBus()
    results: dict[str, Any] = {}

    demand_agent = DemandAgent(registry)
    supplier_agent = SupplierAgent(registry)
    inventory_agent = InventoryAgent(registry)
    logistics_agent = LogisticsAgent(registry)

    # Step 1: Demand
    try:
        demand_result = demand_agent.predict(df)
        bus.demand = _build_signal("demand", demand_result)
        results["demand"] = demand_result.to_dict()
        logger.info(
            f"[ContextBus] Demand: mean={bus.demand.mean_prediction:.2f} "
            f"risk={bus.demand.risk_level}"
        )
    except Exception as e:
        logger.error(f"[ContextBus] Demand agent failed: {e}")
        results["demand"] = {"error": str(e)}

    # Step 2: Supplier — receives demand signal
    try:
        supplier_df = df
        if bus.demand:
            supplier_df = _inject_demand_signal(df, bus.demand)
        supplier_result = supplier_agent.predict(supplier_df)
        bus.supplier = _build_signal("supplier", supplier_result)
        results["supplier"] = supplier_result.to_dict()
        logger.info(
            f"[ContextBus] Supplier: risk={bus.supplier.risk_level} "
            f"(demand context: {bus.demand.risk_level if bus.demand else 'none'})"
        )
    except Exception as e:
        logger.error(f"[ContextBus] Supplier agent failed: {e}")
        results["supplier"] = {"error": str(e)}

    # Step 3: Inventory — receives supplier signal
    try:
        inventory_df = df
        if bus.supplier:
            inventory_df = _inject_supplier_signal(df, bus.supplier)
        inventory_result = inventory_agent.predict(inventory_df)
        bus.inventory = _build_signal("inventory", inventory_result)
        results["inventory"] = inventory_result.to_dict()
        logger.info(
            f"[ContextBus] Inventory: risk={bus.inventory.risk_level} "
            f"(supplier context: {bus.supplier.risk_level if bus.supplier else 'none'})"
        )
    except Exception as e:
        logger.error(f"[ContextBus] Inventory agent failed: {e}")
        results["inventory"] = {"error": str(e)}

    # Step 4: Logistics — receives inventory signal
    try:
        logistics_df = df
        if bus.inventory:
            logistics_df = _inject_inventory_signal(df, bus.inventory)
        logistics_result = logistics_agent.predict(logistics_df)
        bus.logistics = _build_signal("logistics", logistics_result)
        results["logistics"] = logistics_result.to_dict()
        logger.info(
            f"[ContextBus] Logistics: risk={bus.logistics.risk_level} "
            f"(inventory context: {bus.inventory.risk_level if bus.inventory else 'none'})"
        )
    except Exception as e:
        logger.error(f"[ContextBus] Logistics agent failed: {e}")
        results["logistics"] = {"error": str(e)}

    return {"bus": bus.to_dict(), "results": results}
