"""
AMASCI GraphRAG Structured Prompt Builder
============================================
Constructs a 7-section structured prompt context for LLM generation:

    1. Historical Pattern
    2. Current Prediction
    3. Current Actual Event
    4. TPKE Learned Relationships
    5. Root Cause Chain
    6. Prediction Confidence
    7. Business Context
"""

import json
from typing import Any


class StructuredPromptBuilder:
    """
    Constructs 7-section structured LLM prompt context from multi-source graph state.
    """

    def build_prompt(
        self,
        query: str,
        historical_patterns: list[dict[str, Any]],
        current_predictions: list[dict[str, Any]],
        current_actuals: list[dict[str, Any]],
        tpke_relationships: list[dict[str, Any]],
        root_cause_chain: list[dict[str, Any]],
        prediction_confidence: float = 0.88,
        business_context: dict[str, Any] | None = None,
    ) -> str:
        """
        Build full 7-section grounded prompt for LLM.
        """
        prompt = f"""You are AMASCI, an expert Supply Chain Intelligence Analyst.
Answer the user request using ONLY the structured Knowledge Graph evidence provided below.

========================
USER REQUEST
========================
{query}

========================
1. HISTORICAL PATTERNS
========================
{json.dumps(historical_patterns[:5], indent=2) if historical_patterns else "No historical pattern records available."}

========================
2. CURRENT PREDICTIONS
========================
{json.dumps(current_predictions[:5], indent=2) if current_predictions else "No current prediction records available."}

========================
3. CURRENT ACTUAL EVENTS
========================
{json.dumps(current_actuals[:5], indent=2) if current_actuals else "No actual upload event records available."}

========================
4. TPKE LEARNED RELATIONSHIPS
========================
{json.dumps(tpke_relationships[:5], indent=2) if tpke_relationships else "No TPKE inferred edges active."}

========================
5. ROOT CAUSE CHAIN
========================
{json.dumps(root_cause_chain[:5], indent=2) if root_cause_chain else "No active RCA causal chain."}

========================
6. PREDICTION CONFIDENCE
========================
Ensemble Model Confidence: {prediction_confidence:.2f}

========================
7. BUSINESS CONTEXT
========================
{json.dumps(business_context or {"domain": "Supply Chain Intelligence", "dataset": "DataCo Smart Supply Chain"}, indent=2)}

========================
RESPONSE GROUNDING MANDATE
========================
Structure your response strictly with the following 5 sections:
1. Direct Answer
2. Supporting Evidence (quote specific entities and graph paths)
3. Retrieved Entities
4. Overall Confidence
5. Actionable Business Recommendation

Never hallucinate. If evidence is insufficient, state clearly what data is missing.
"""
        return prompt
