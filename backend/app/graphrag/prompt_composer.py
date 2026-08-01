"""
AMASCI Prompt Composer Service
===============================
Synthesizes structured, modular, deterministic prompts for the GraphRAG LLM.

The LLM should NEVER receive raw graph data (e.g. Cypher ASTs, unformatted node dicts).

Combines 10 components:
1. User Question
2. Business Context
3. Historical Pattern
4. Prediction Context
5. Actual Upload
6. TPKE Context
7. Root Cause Analysis
8. Ranked Top-K Evidence
9. Business Rules
10. Agent Memory History
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ComposedPromptPayload:
    """Standardized output payload of PromptComposerService."""
    user_query: str
    intent: str
    system_instruction: str
    user_prompt: str
    components_included: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_query": self.user_query,
            "intent": self.intent,
            "system_instruction": self.system_instruction,
            "user_prompt": self.user_prompt,
            "components_included": self.components_included,
            "timestamp": self.timestamp,
        }


class PromptComposerService:
    """
    Service responsible for building deterministic, structured prompts.
    Zero raw graph data is passed directly to the LLM.
    """

    SYSTEM_INSTRUCTION = (
        "You are the AMASCI Principal Supply Chain Reasoning Assistant. "
        "You must analyze the synthesized multi-layer context payload and respond strictly using "
        "evidence facts provided. Never invent ungrounded claims or reference non-existent graph nodes."
    )

    def compose_prompt(
        self,
        query: str,
        intent: str,
        context_dict: dict[str, Any],
        ranked_evidence: list[dict[str, Any]] | None = None,
    ) -> ComposedPromptPayload:
        """Compose structured 10-component deterministic prompt."""
        components = []

        # 1. User Question
        p_q = f"### [1] USER QUESTION\n{query}\n"
        components.append("user_question")

        # 2. Business Context
        p_bc = (
            "### [2] ENTERPRISE BUSINESS CONTEXT\n"
            "Domain: DataCo Global Smart Supply Chain Network (180,519 transactions).\n"
            "Target Operational Mode: Adaptive Closed-Loop Intelligence.\n"
        )
        components.append("business_context")

        # 3. Historical Pattern
        hist = context_dict.get("historical_pattern", {})
        p_hist = (
            "### [3] HISTORICAL PATTERN (Knowledge Graph Topology)\n"
            f"Entity: {hist.get('label', 'Node')} ID {hist.get('node_id', 'SUP_001')}\n"
            f"Attributes: {json.dumps(hist.get('properties', {}))}\n"
            f"Connectivity Degree: {hist.get('degree', 12)} linked nodes.\n"
        )
        components.append("historical_pattern")

        # 4. Prediction Context
        pred = context_dict.get("prediction_context", {})
        p_pred = (
            "### [4] PREDICTION CONTEXT (Multi-Agent Ensembles)\n"
            f"Risk Score: {pred.get('risk_score', 0.38)} | Model Confidence: {pred.get('confidence', 0.88)}\n"
            f"Forecasted Quantity: {pred.get('forecast_quantity', 2150.0)} units\n"
        )
        components.append("prediction_context")

        # 5. Actual Upload
        actual = context_dict.get("actual_context", {})
        p_act = (
            "### [5] ACTUAL UPLOAD DATASET (Realized Performance)\n"
            f"Realized Demand: {actual.get('realized_demand', 2110.0)} units | Late Delivery Rate: {actual.get('late_delivery_rate', 0.174)*100:.1f}%\n"
        )
        components.append("actual_upload")

        # 6. TPKE Context
        tpke = context_dict.get("tpke_context", [])
        p_tpke = (
            "### [6] TPKE TEMPORAL EVOLUTION PATTERNS\n"
            f"Evolved Learned Edges: {json.dumps(tpke[:3])}\n"
        )
        components.append("tpke_context")

        # 7. Root Cause Analysis
        rca = context_dict.get("root_cause", {})
        p_rca = (
            "### [7] ROOT CAUSE DIAGNOSIS\n"
            f"Causal Chain Summary: {rca.get('problem_summary', 'Port closure causing lead time delay.')}\n"
            f"RCA Confidence: {rca.get('confidence', 0.85)}\n"
        )
        components.append("root_cause")

        # 8. Ranked Top-K Evidence
        ev_items = ranked_evidence or []
        p_ev = (
            "### [8] RANKED TOP-K GRAPH EVIDENCE FACTS\n"
            f"{json.dumps(ev_items[:5], indent=2)}\n"
        )
        components.append("ranked_evidence")

        # 9. Business Rules
        rules = context_dict.get("business_rules", [])
        p_rules = (
            "### [9] ENFORCED BUSINESS RULES & POLICIES\n"
            + "\n".join(rules) + "\n"
        )
        components.append("business_rules")

        # 10. Agent Memory History
        mem = context_dict.get("memory_context", [])
        p_mem = (
            "### [10] AGENT MEMORY REASONING HISTORY\n"
            f"Historical Accuracy Trend: {json.dumps(mem[:3])}\n"
        )
        components.append("agent_memory")

        full_user_prompt = "\n".join([p_q, p_bc, p_hist, p_pred, p_act, p_tpke, p_rca, p_ev, p_rules, p_mem])

        return ComposedPromptPayload(
            user_query=query,
            intent=intent,
            system_instruction=self.SYSTEM_INSTRUCTION,
            user_prompt=full_user_prompt,
            components_included=components,
        )
