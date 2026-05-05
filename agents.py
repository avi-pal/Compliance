"""
LangGraph Multi-Agent Surveillance Pipeline
Agents:
  1. ClassifierAgent  — detects violation categories + extracts source lines
  2. ScorerAgent      — computes priority score using weighted matrix
  3. ReviewerAgent    — synthesizes final verdict + recommended action
"""

import os
import json
import re
from typing import TypedDict, Annotated
from openai import AzureOpenAI
from langgraph.graph import StateGraph, END
import operator
from dotenv import load_dotenv

load_dotenv()

AZURE_DEPLOYMENT = "aprbatch1-de024833-f245-4323-9ffa-e0482c8e1ec8"

# ── Shared state flowing through the graph ─────────────────────────────────

class SurveillanceState(TypedDict):
    email: dict
    matrix: dict

    # Classifier output
    classifications: list[dict]          # [{category, confidence, evidence}]
    classifier_reasoning: str

    # Scorer output
    priority_score: float
    priority_level: str                  # CRITICAL / HIGH / MEDIUM / LOW
    scorer_breakdown: list[dict]

    # Reviewer output
    verdict: str
    recommended_action: str
    summary: str
    reviewer_notes: str

    # Error
    error: str | None


# ── Azure OpenAI client ───────────────────────────────────────────────────

def get_client():
    return AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_ENDPOINT"),
        api_key=os.getenv("AZURE_API_KEY"),
        api_version="2025-01-01-preview"
    )

MODEL = "aprbatch1-de024833-f245-4323-9ffa-e0482c8e1ec8"

CATEGORIES = [
    "Secrecy",
    "Market Manipulation/Misconduct",
    "Market Bribery",
    "Change in Communication",
    "Complaints",
    "Employee Ethics"
]


# ── Agent 1: Classifier ────────────────────────────────────────────────────

async def classifier_agent(state: SurveillanceState) -> SurveillanceState:
    email = state["email"]
    client = get_client()

    prompt = f"""You are a financial compliance classifier at a bank.

Analyze the following email and identify any violation categories present.

VIOLATION CATEGORIES:
{json.dumps(CATEGORIES, indent=2)}

EMAIL:
Subject: {email['subject']}
From: {email['sender']}
To: {email['recipient']}
Body:
{email['body']}

Return ONLY valid JSON (no markdown, no explanation) in this exact format:
{{
  "classifications": [
    {{
      "category": "<one of the exact category names>",
      "confidence": <0.0 to 1.0>,
      "evidence": "<exact quote or phrase from the email that triggered this flag>"
    }}
  ],
  "reasoning": "<brief explanation of your analysis>"
}}

If no violations detected, return classifications as empty array."""

    try:
        client = get_client()
        response = client.chat.completions.create(
            model=AZURE_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        parsed = json.loads(raw)

        return {
            **state,
            "classifications": parsed.get("classifications", []),
            "classifier_reasoning": parsed.get("reasoning", ""),
            "error": None
        }
    except Exception as e:
        return {
            **state,
            "classifications": [],
            "classifier_reasoning": "",
            "error": f"Classifier error: {str(e)}"
        }


# ── Agent 2: Scorer ────────────────────────────────────────────────────────

async def scorer_agent(state: SurveillanceState) -> SurveillanceState:
    classifications = state["classifications"]
    matrix = state["matrix"]

    if not classifications:
        return {
            **state,
            "priority_score": 0.0,
            "priority_level": "LOW",
            "scorer_breakdown": []
        }

    client = get_client()

    prompt = f"""You are a compliance risk scorer. You receive violation classifications
and a priority weight matrix. Compute a weighted priority score.

WEIGHT MATRIX (category → weight):
{json.dumps(matrix, indent=2)}

CLASSIFICATIONS FROM CLASSIFIER:
{json.dumps(classifications, indent=2)}

SCORING FORMULA: priority_score = sum(weight × confidence) for each classification

THRESHOLDS:
- CRITICAL: score >= 8.0
- HIGH:     score >= 5.0
- MEDIUM:   score >= 2.0
- LOW:      score < 2.0

Return ONLY valid JSON (no markdown):
{{
  "breakdown": [
    {{
      "category": "<category name>",
      "weight": <weight from matrix>,
      "confidence": <confidence from classifier>,
      "contribution": <weight × confidence>
    }}
  ],
  "total_score": <sum of contributions>,
  "priority_level": "<CRITICAL|HIGH|MEDIUM|LOW>"
}}"""

    try:
        client = get_client()
        response = client.chat.completions.create(
            model=AZURE_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=600
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        parsed = json.loads(raw)

        return {
            **state,
            "priority_score": parsed.get("total_score", 0.0),
            "priority_level": parsed.get("priority_level", "LOW"),
            "scorer_breakdown": parsed.get("breakdown", [])
        }
    except Exception as e:
        # Fallback: compute score manually
        score = 0.0
        breakdown = []
        for c in classifications:
            cat = c.get("category", "")
            conf = c.get("confidence", 0.0)
            weight = matrix.get(cat, 1.0)
            contrib = weight * conf
            score += contrib
            breakdown.append({
                "category": cat,
                "weight": weight,
                "confidence": conf,
                "contribution": round(contrib, 3)
            })

        if score >= 8.0:
            level = "CRITICAL"
        elif score >= 5.0:
            level = "HIGH"
        elif score >= 2.0:
            level = "MEDIUM"
        else:
            level = "LOW"

        return {
            **state,
            "priority_score": round(score, 3),
            "priority_level": level,
            "scorer_breakdown": breakdown
        }


# ── Agent 3: Reviewer ──────────────────────────────────────────────────────

async def reviewer_agent(state: SurveillanceState) -> SurveillanceState:
    email = state["email"]
    classifications = state["classifications"]
    priority_level = state["priority_level"]
    priority_score = state["priority_score"]
    breakdown = state["scorer_breakdown"]
    classifier_reasoning = state["classifier_reasoning"]

    client = get_client()

    prompt = f"""You are a senior compliance reviewer at a bank. You receive the outputs
of an automated classification and scoring pipeline. Your job is to write a final
review verdict with a recommended action.

EMAIL SUMMARY:
Subject: {email['subject']}
From: {email['sender']}
To: {email['recipient']}

CLASSIFIER OUTPUT:
- Violations found: {json.dumps(classifications, indent=2)}
- Classifier reasoning: {classifier_reasoning}

SCORER OUTPUT:
- Priority score: {priority_score}
- Priority level: {priority_level}
- Breakdown: {json.dumps(breakdown, indent=2)}

Return ONLY valid JSON (no markdown):
{{
  "verdict": "<ESCALATE|MONITOR|DISMISS>",
  "recommended_action": "<concrete next step for the compliance team>",
  "summary": "<2-3 sentence plain-English summary of what was found>",
  "notes": "<any caveats, context, or reviewer observations>"
}}

Verdict guide:
- ESCALATE: CRITICAL or HIGH priority — needs immediate human review
- MONITOR:  MEDIUM priority — flag for periodic review
- DISMISS:  LOW priority — likely a false positive, no action needed"""

    try:
        client = get_client()
        response = client.chat.completions.create(
            model=AZURE_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=600
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        parsed = json.loads(raw)

        return {
            **state,
            "verdict": parsed.get("verdict", "MONITOR"),
            "recommended_action": parsed.get("recommended_action", ""),
            "summary": parsed.get("summary", ""),
            "reviewer_notes": parsed.get("notes", "")
        }
    except Exception as e:
        return {
            **state,
            "verdict": "MONITOR",
            "recommended_action": "Manual review required due to processing error.",
            "summary": f"Automated review encountered an error: {str(e)}",
            "reviewer_notes": ""
        }


# ── Build the LangGraph ────────────────────────────────────────────────────

def build_graph():
    workflow = StateGraph(SurveillanceState)

    workflow.add_node("classifier", classifier_agent)
    workflow.add_node("scorer", scorer_agent)
    workflow.add_node("reviewer", reviewer_agent)

    workflow.set_entry_point("classifier")
    workflow.add_edge("classifier", "scorer")
    workflow.add_edge("scorer", "reviewer")
    workflow.add_edge("reviewer", END)

    return workflow.compile()


graph = build_graph()


# ── Public entry point ─────────────────────────────────────────────────────

async def run_surveillance_pipeline(email: dict, matrix: dict) -> dict:
    initial_state: SurveillanceState = {
        "email": email,
        "matrix": matrix,
        "classifications": [],
        "classifier_reasoning": "",
        "priority_score": 0.0,
        "priority_level": "LOW",
        "scorer_breakdown": [],
        "verdict": "",
        "recommended_action": "",
        "summary": "",
        "reviewer_notes": "",
        "error": None
    }

    final_state = await graph.ainvoke(initial_state)

    return {
        "email": {
            "subject": email["subject"],
            "sender": email["sender"],
            "recipient": email["recipient"]
        },
        "agent_outputs": {
            "classifier": {
                "classifications": final_state["classifications"],
                "reasoning": final_state["classifier_reasoning"]
            },
            "scorer": {
                "score": final_state["priority_score"],
                "level": final_state["priority_level"],
                "breakdown": final_state["scorer_breakdown"]
            },
            "reviewer": {
                "verdict": final_state["verdict"],
                "recommended_action": final_state["recommended_action"],
                "summary": final_state["summary"],
                "notes": final_state["reviewer_notes"]
            }
        },
        "priority_score": final_state["priority_score"],
        "priority_level": final_state["priority_level"],
        "verdict": final_state["verdict"],
        "summary": final_state["summary"],
        "classifications": final_state["classifications"],
        "error": final_state["error"]
    }
