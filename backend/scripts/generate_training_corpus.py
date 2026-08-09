"""
generate_training_corpus.py
============================
Generates a JSONL fine-tuning corpus from the live Neo4j knowledge graph.

Run AFTER graph is built:
    python generate_training_corpus.py

Output: data/graphrag_training_corpus.jsonl
        data/graphrag_system_prompt.txt

Each line is an OpenAI-compatible chat fine-tune record:
{
  "messages": [
    {"role": "system", "content": "<system>"},
    {"role": "user",   "content": "<question>"},
    {"role": "assistant", "content": "<grounded JSON answer>"}
  ]
}
"""

import asyncio
import json
import logging
from pathlib import Path

from app.graph.connection import get_connection_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/graphrag_training_corpus.jsonl")
SYSTEM_PROMPT_PATH = Path("data/graphrag_system_prompt.txt")

# ── System prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are AMASCI — an Adaptive Supply Chain Intelligence analyst.
You have access to a Neo4j knowledge graph containing:
  Nodes: Supplier, Product, Warehouse, Shipment, Customer, Order, CalendarEvent
  Relationships: SUPPLIES, STORED_IN, SHIPS_VIA, DELIVERED_TO, PLACED, CONTAINS, INFLUENCES

Rules:
1. Ground every statement in the graph context provided. Never invent facts.
2. Return ONLY valid JSON with keys: answer, evidence, risks, recommendations.
3. answer: 1-3 sentences directly addressing the question.
4. evidence: list of node IDs or relationship facts from the context.
5. risks: specific risk factors with numeric scores where available.
6. recommendations: 2-4 actionable steps ranked by urgency.
7. If the graph context is empty, say so explicitly — do not fabricate data."""


# ── Cypher queries that produce training examples ──────────────────────────────

QUERIES = {
    "high_risk_suppliers": {
        "cypher": """
            MATCH (s:Supplier)
            WHERE coalesce(s.risk_score, 0) > 0.5
            RETURN s.node_id AS id,
                   s.supplier_name AS name,
                   round(coalesce(s.risk_score, 0), 3) AS risk,
                   round(coalesce(s.supplier_delay_rate, 0), 3) AS delay_rate,
                   round(coalesce(s.supplier_reliability_score, 0), 3) AS reliability
            ORDER BY risk DESC LIMIT 10
        """,
        "question_template": "Which suppliers have the highest delivery risk?",
        "answer_template": lambda rows: {
            "answer": f"Found {len(rows)} high-risk suppliers. The most critical is "
                      f"{rows[0]['name'] or rows[0]['id']} with a risk score of {rows[0]['risk']}.",
            "evidence": [f"{r['id']}: risk={r['risk']}, delay_rate={r['delay_rate']}" for r in rows[:5]],
            "risks": f"Top supplier {rows[0]['id']} has reliability score {rows[0]['reliability']}. "
                     f"Delay rates range from {min(r['delay_rate'] for r in rows):.2f} to "
                     f"{max(r['delay_rate'] for r in rows):.2f}.",
            "recommendations": [
                f"Activate backup supplier contracts for {rows[0]['id']} immediately.",
                "Increase safety stock by 20% for products supplied by top-3 risk suppliers.",
                "Schedule weekly SLA review calls with suppliers scoring above 0.65 risk.",
                "Evaluate alternative sourcing regions to reduce single-supplier dependency.",
            ],
        },
    },

    "warehouse_stress": {
        "cypher": """
            MATCH (w:Warehouse)
            WHERE coalesce(w.inventory_stress_index, 0) > 0.4
            RETURN w.node_id AS id,
                   w.city AS city,
                   w.region AS region,
                   round(coalesce(w.inventory_stress_index, 0), 3) AS stress,
                   round(coalesce(w.stock_coverage_ratio, 0), 3) AS coverage,
                   round(coalesce(w.days_until_reorder, 0), 1) AS days_reorder
            ORDER BY stress DESC LIMIT 10
        """,
        "question_template": "Which warehouses are under inventory stress?",
        "answer_template": lambda rows: {
            "answer": f"{len(rows)} warehouses show elevated inventory stress. "
                      f"{rows[0]['city'] or rows[0]['id']} ({rows[0]['region']}) is most critical "
                      f"with stress index {rows[0]['stress']} and only {rows[0]['days_reorder']} days until reorder.",
            "evidence": [f"{r['id']} ({r['city']}): stress={r['stress']}, coverage={r['coverage']}" for r in rows[:5]],
            "risks": f"Stock coverage ratios below 0.5 at {sum(1 for r in rows if r['coverage'] < 0.5)} locations. "
                     f"Reorder urgency is highest at {rows[0]['id']}.",
            "recommendations": [
                f"Trigger emergency reorder for {rows[0]['id']} within 24 hours.",
                "Redistribute inventory from low-stress warehouses to high-stress locations.",
                "Review demand forecasts for products stored at stressed warehouses.",
                "Set automated reorder alerts at 60% stock coverage threshold.",
            ],
        },
    },

    "late_delivery_shipments": {
        "cypher": """
            MATCH (sh:Shipment)
            WHERE coalesce(sh.late_delivery_rate, 0) > 0.5
            RETURN sh.node_id AS id,
                   sh.shipping_mode AS mode,
                   round(coalesce(sh.late_delivery_rate, 0), 3) AS late_rate,
                   round(coalesce(sh.shipping_delay, 0), 2) AS avg_delay,
                   round(coalesce(sh.shipping_efficiency_score, 0), 3) AS efficiency
            ORDER BY late_rate DESC LIMIT 10
        """,
        "question_template": "What are the shipping modes with the highest late delivery rates?",
        "answer_template": lambda rows: {
            "answer": f"Identified {len(rows)} shipment routes with late delivery rates above 50%. "
                      f"Mode '{rows[0]['mode']}' has the worst performance at {rows[0]['late_rate']*100:.1f}% late rate "
                      f"with average delay of {rows[0]['avg_delay']} days.",
            "evidence": [f"{r['id']} ({r['mode']}): late_rate={r['late_rate']}, avg_delay={r['avg_delay']}d" for r in rows[:5]],
            "risks": f"Efficiency scores range from {min(r['efficiency'] for r in rows):.2f} to "
                     f"{max(r['efficiency'] for r in rows):.2f}. "
                     f"{sum(1 for r in rows if r['avg_delay'] > 3)} routes exceed 3-day delay threshold.",
            "recommendations": [
                f"Reroute critical orders away from '{rows[0]['mode']}' shipping mode.",
                "Negotiate SLA penalties with carriers showing >60% late delivery rates.",
                "Implement real-time shipment tracking for all routes with efficiency < 0.6.",
                "Evaluate air freight for high-value orders currently on ground routes.",
            ],
        },
    },

    "supplier_product_dependency": {
        "cypher": """
            MATCH (s:Supplier)-[:SUPPLIES]->(p:Product)
            WITH s, count(p) AS product_count,
                 avg(coalesce(s.risk_score, 0)) AS avg_risk
            WHERE product_count > 2
            RETURN s.node_id AS supplier_id,
                   s.supplier_name AS name,
                   product_count,
                   round(avg_risk, 3) AS risk
            ORDER BY product_count DESC LIMIT 10
        """,
        "question_template": "Which suppliers have the highest product dependency exposure?",
        "answer_template": lambda rows: {
            "answer": f"Supplier {rows[0]['name'] or rows[0]['supplier_id']} supplies {rows[0]['product_count']} products, "
                      f"creating the highest single-supplier dependency with risk score {rows[0]['risk']}.",
            "evidence": [f"{r['supplier_id']}: {r['product_count']} products, risk={r['risk']}" for r in rows[:5]],
            "risks": f"Top {min(3, len(rows))} suppliers collectively cover "
                     f"{sum(r['product_count'] for r in rows[:3])} product lines. "
                     f"A failure in any one creates cascading stockout risk.",
            "recommendations": [
                "Dual-source the top 5 highest-volume product lines immediately.",
                f"Reduce {rows[0]['supplier_id']} dependency below 30% of total product portfolio.",
                "Map alternative suppliers for each product category in the affected lines.",
                "Increase safety stock buffer for all products from suppliers with risk > 0.5.",
            ],
        },
    },

    "demand_volatile_products": {
        "cypher": """
            MATCH (p:Product)
            WHERE coalesce(p.demand_volatility, 0) > 0.3
            RETURN p.node_id AS id,
                   p.category AS category,
                   round(coalesce(p.demand_volatility, 0), 3) AS volatility,
                   round(coalesce(p.rolling_7d_demand, 0), 2) AS demand_7d,
                   round(coalesce(p.forecast_risk, 0), 3) AS forecast_risk
            ORDER BY volatility DESC LIMIT 10
        """,
        "question_template": "Which product categories have the highest demand volatility?",
        "answer_template": lambda rows: {
            "answer": f"Category '{rows[0]['category']}' shows the highest demand volatility at {rows[0]['volatility']} "
                      f"with a 7-day rolling demand of {rows[0]['demand_7d']} units and forecast risk of {rows[0]['forecast_risk']}.",
            "evidence": [f"{r['id']} ({r['category']}): volatility={r['volatility']}, 7d_demand={r['demand_7d']}" for r in rows[:5]],
            "risks": f"High volatility products carry elevated forecast error risk. "
                     f"{sum(1 for r in rows if r['forecast_risk'] > 0.5)} products have forecast risk above 0.5.",
            "recommendations": [
                "Switch to weekly demand review cycles for high-volatility categories.",
                "Increase safety stock multiplier to 1.5x for products with volatility > 0.5.",
                "Apply exponential smoothing with α=0.3 for volatile demand series.",
                "Align promotional calendar with inventory replenishment schedules.",
            ],
        },
    },

    "warehouse_shipment_routes": {
        "cypher": """
            MATCH (w:Warehouse)-[:SHIPS_VIA]->(sh:Shipment)
            WITH w, sh,
                 coalesce(sh.late_delivery_rate, 0) AS late_rate
            WHERE late_rate > 0.4
            RETURN w.node_id AS warehouse_id,
                   w.city AS city,
                   sh.node_id AS shipment_id,
                   sh.shipping_mode AS mode,
                   round(late_rate, 3) AS late_rate
            ORDER BY late_rate DESC LIMIT 15
        """,
        "question_template": "Which warehouse-to-shipment routes carry the highest financial risk?",
        "answer_template": lambda rows: {
            "answer": f"Route from warehouse {rows[0]['city'] or rows[0]['warehouse_id']} via "
                      f"'{rows[0]['mode']}' has the highest late delivery rate at {rows[0]['late_rate']*100:.1f}%. "
                      f"Total {len(rows)} high-risk routes identified.",
            "evidence": [f"{r['warehouse_id']}→{r['shipment_id']} ({r['mode']}): {r['late_rate']*100:.1f}% late" for r in rows[:5]],
            "risks": f"Routes with late rates above 60% risk SLA breach penalties and customer churn. "
                     f"{sum(1 for r in rows if r['late_rate'] > 0.6)} routes exceed critical 60% threshold.",
            "recommendations": [
                "Reroute shipments from highest-risk warehouse-carrier combinations.",
                "Negotiate carrier performance bonds for routes with >50% late delivery.",
                "Implement predictive delay alerts 48 hours before scheduled delivery.",
                "Review warehouse dispatch scheduling to reduce carrier handoff delays.",
            ],
        },
    },

    "customer_order_risk": {
        "cypher": """
            MATCH (c:Customer)-[:PLACED]->(o:Order)
            WITH c, count(o) AS order_count,
                 avg(coalesce(o.profit_ratio, 0)) AS avg_profit
            WHERE order_count > 5
            RETURN c.node_id AS id,
                   c.segment AS segment,
                   c.country AS country,
                   order_count,
                   round(avg_profit, 3) AS avg_profit
            ORDER BY order_count DESC LIMIT 10
        """,
        "question_template": "Which customer segments have the highest order volume and what is their risk profile?",
        "answer_template": lambda rows: {
            "answer": f"Customer segment '{rows[0]['segment']}' in {rows[0]['country']} has the highest order volume "
                      f"with {rows[0]['order_count']} orders and average profit ratio of {rows[0]['avg_profit']}.",
            "evidence": [f"{r['id']} ({r['segment']}, {r['country']}): {r['order_count']} orders, profit={r['avg_profit']}" for r in rows[:5]],
            "risks": f"High-volume segments create concentration risk. "
                     f"Disruption to top segment affects {rows[0]['order_count']} orders simultaneously.",
            "recommendations": [
                "Prioritize fulfillment SLAs for top-volume customer segments.",
                "Implement dedicated inventory buffers for high-value customer accounts.",
                "Set up proactive delay notifications for customers with >10 active orders.",
                "Review profit margins — segments with avg_profit < 0.1 may need pricing review.",
            ],
        },
    },

    "tpke_inferred_risk": {
        "cypher": """
            MATCH (a)-[r:TPKE_INFERRED_RELATIONSHIP]->(b)
            RETURN a.node_id AS source,
                   labels(a)[0] AS source_label,
                   b.node_id AS target,
                   labels(b)[0] AS target_label,
                   round(coalesce(r.relationship_strength, r.weight, 0), 3) AS strength,
                   round(coalesce(r.confidence, 0), 3) AS confidence
            ORDER BY strength DESC LIMIT 10
        """,
        "question_template": "What causal relationships has the TPKE algorithm inferred in the supply chain?",
        "answer_template": lambda rows: {
            "answer": f"TPKE has inferred {len(rows)} causal relationships. "
                      f"The strongest pattern links {rows[0]['source_label']} '{rows[0]['source']}' "
                      f"to {rows[0]['target_label']} '{rows[0]['target']}' "
                      f"with strength {rows[0]['strength']} and confidence {rows[0]['confidence']}.",
            "evidence": [f"{r['source']}({r['source_label']})→{r['target']}({r['target_label']}): "
                         f"strength={r['strength']}, conf={r['confidence']}" for r in rows[:5]],
            "risks": f"TPKE-inferred edges represent temporal causal patterns. "
                     f"High-confidence edges (>0.7) indicate repeatable disruption sequences "
                     f"that should be treated as confirmed risk pathways.",
            "recommendations": [
                "Monitor TPKE high-confidence edges as early warning indicators.",
                "Trigger pre-emptive inventory adjustments when causal pattern A fires.",
                "Feed TPKE edge weights into the demand forecasting feature set.",
                "Review TPKE patterns monthly and decay stale edges below 0.1 strength.",
            ],
        },
    },
}


async def generate_corpus():
    conn = get_connection_manager()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Write system prompt
    SYSTEM_PROMPT_PATH.write_text(SYSTEM_PROMPT, encoding="utf-8")
    logger.info(f"System prompt written to {SYSTEM_PROMPT_PATH}")

    records_written = 0

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for query_name, config in QUERIES.items():
            logger.info(f"Running query: {query_name}")
            try:
                rows = await conn.execute_query(config["cypher"].strip(), {})
            except Exception as e:
                logger.warning(f"Query {query_name} failed (Neo4j offline?): {e}")
                rows = []

            if not rows:
                logger.warning(f"  No rows returned for {query_name} — skipping")
                continue

            try:
                answer_dict = config["answer_template"](rows)
            except Exception as e:
                logger.warning(f"  Answer template failed for {query_name}: {e}")
                continue

            record = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": config["question_template"]},
                    {"role": "assistant", "content": json.dumps(answer_dict, ensure_ascii=False)},
                ]
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            records_written += 1
            logger.info(f"  Written: {query_name} ({len(rows)} graph rows → 1 training record)")

    logger.info(f"\nCorpus complete: {records_written} training records → {OUTPUT_PATH}")
    logger.info(f"System prompt   → {SYSTEM_PROMPT_PATH}")
    logger.info("\nNext steps:")
    logger.info("  OpenAI fine-tune : openai api fine_tunes.create -t data/graphrag_training_corpus.jsonl -m gpt-3.5-turbo")
    logger.info("  Local (Ollama)   : Use system prompt in graphrag/langchain/__init__.py SYSTEM_PROMPT constant")
    logger.info("  Validate         : python -c \"import json; [json.loads(l) for l in open('data/graphrag_training_corpus.jsonl')]\"")


if __name__ == "__main__":
    asyncio.run(generate_corpus())
