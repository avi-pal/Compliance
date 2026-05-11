"""LangGraph Single-Agent Surveillance Pipeline
Agent:
  ComplianceAgent — performs end-to-end classification, scoring, and review
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

    # Agent output
    classifications: list[dict]          # [{category, confidence, evidence}]
    priority_score: float
    priority_level: str                  # CRITICAL / HIGH / MEDIUM / LOW
    verdict: str
    recommended_action: str
    summary: str
    notes: str

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


# ── Single Agent: Comprehensive Compliance Review ────────────────────────

async def compliance_agent(state: SurveillanceState) -> SurveillanceState:
    email = state["email"]
    matrix = state["matrix"]
    client = get_client()

    prompt = f"""You are a senior compliance agent at a bank. Perform a comprehensive
analysis of the email below in a single pass. Your job is to:

1. CLASSIFY: Identify any violation categories present
2. SCORE: Compute a weighted priority score
3. REVIEW: Generate a final verdict and recommended action

VIOLATION CATEGORIES:
{json.dumps(CATEGORIES, indent=2)}

WEIGHT MATRIX (category → weight):
{json.dumps(matrix, indent=2)}

SCORING THRESHOLDS:
- CRITICAL: score >= 8.0
- HIGH:     score >= 5.0
- MEDIUM:   score >= 2.0
- LOW:      score < 2.0

VERDICT GUIDE:
- ESCALATE: CRITICAL or HIGH priority — needs immediate human review
- MONITOR:  MEDIUM priority — flag for periodic review
- DISMISS:  LOW priority — likely a false positive, no action needed

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
  "priority_score": <computed score = sum(weight × confidence)>,
  "priority_level": "<CRITICAL|HIGH|MEDIUM|LOW>",
  "verdict": "<ESCALATE|MONITOR|DISMISS>",
  "recommended_action": "<concrete next step for the compliance team>",
  "summary": "<2-3 sentence plain-English summary of what was found>",
  "notes": "<any caveats, context, or observations>"
}}

If no violations detected, return classifications as empty array and priority_score as 0.0."""

    try:
        response = client.chat.completions.create(
            model=AZURE_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1500
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        parsed = json.loads(raw)

        return {
            **state,
            "classifications": parsed.get("classifications", []),
            "priority_score": parsed.get("priority_score", 0.0),
            "priority_level": parsed.get("priority_level", "LOW"),
            "verdict": parsed.get("verdict", "MONITOR"),
            "recommended_action": parsed.get("recommended_action", ""),
            "summary": parsed.get("summary", ""),
            "notes": parsed.get("notes", ""),
            "error": None
        }
    except Exception as e:
        return {
            **state,
            "classifications": [],
            "priority_score": 0.0,
            "priority_level": "LOW",
            "verdict": "MONITOR",
            "recommended_action": "Manual review required due to processing error.",
            "summary": f"Automated review encountered an error: {str(e)}",
            "notes": "",
            "error": f"Compliance agent error: {str(e)}"
        }








# ── Build the LangGraph ────────────────────────────────────────────────────

def build_graph():
    workflow = StateGraph(SurveillanceState)

    workflow.add_node("compliance", compliance_agent)

    workflow.set_entry_point("compliance")
    workflow.add_edge("compliance", END)

    return workflow.compile()


graph = build_graph()


# ── Public entry point ─────────────────────────────────────────────────────

async def run_surveillance_pipeline(email: dict, matrix: dict) -> dict:
    initial_state: SurveillanceState = {
        "email": email,
        "matrix": matrix,
        "classifications": [],
        "priority_score": 0.0,
        "priority_level": "LOW",
        "verdict": "",
        "recommended_action": "",
        "summary": "",
        "notes": "",
        "error": None
    }

    final_state = await graph.ainvoke(initial_state)

    return {
        "email": {
            "subject": email["subject"],
            "sender": email["sender"],
            "recipient": email["recipient"]
        },
        "agent_output": {
            "classifications": final_state["classifications"],
            "priority_score": final_state["priority_score"],
            "priority_level": final_state["priority_level"],
            "verdict": final_state["verdict"],
            "recommended_action": final_state["recommended_action"],
            "summary": final_state["summary"],
            "notes": final_state["notes"]
        },
        "priority_score": final_state["priority_score"],
        "priority_level": final_state["priority_level"],
        "verdict": final_state["verdict"],
        "summary": final_state["summary"],
        "classifications": final_state["classifications"],
        "error": final_state["error"]
    }
