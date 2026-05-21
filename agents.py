"""LangGraph Single-Agent Surveillance Pipeline
Agent:
  ComplianceAgent — performs end-to-end classification, scoring, and review
"""

import os
import json
import re
import uuid
from typing import TypedDict, Annotated
from openai import AzureOpenAI
from langgraph.graph import StateGraph, END
import operator
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings

load_dotenv()

AZURE_DEPLOYMENT = "aprbatch1-de024833-f245-4323-9ffa-e0482c8e1ec8"

# ── ChromaDB Vector Store Setup ───────────────────────────────────────────

chroma_client = chromadb.PersistentClient(path="./chroma_db")

non_compliant_collection = chroma_client.get_or_create_collection(
    name="non_compliant",
    metadata={"description": "Non-compliant emails with priority >= 6"}
)

human_approval_collection = chroma_client.get_or_create_collection(
    name="human_approval",
    metadata={"description": "Non-compliant emails with priority < 6 requiring human approval"}
)

def store_email(collection, email_id: str, email: dict, agent_output: dict, priority_score: float):
    """Store email and its analysis results in a ChromaDB collection."""
    document = f"Subject: {email['subject']}\nFrom: {email['sender']}\nTo: {email['recipient']}\nBody: {email['body']}"
    metadata = {
        "email_id": email_id,
        "subject": email['subject'],
        "sender": email['sender'],
        "recipient": email['recipient'],
        "priority_score": priority_score,
        "priority_level": agent_output.get('priority_level', 'LOW'),
        "verdict": agent_output.get('verdict', 'DISMISS'),
        "summary": agent_output.get('summary', ''),
        "recommended_action": agent_output.get('recommended_action', ''),
        "classifications": json.dumps(agent_output.get('classifications', []))
    }
    collection.add(
        ids=[email_id],
        documents=[document],
        metadatas=[metadata]
    )

def get_emails_from_collection(collection, limit: int = 100):
    """Retrieve emails from a collection."""
    results = collection.get(limit=limit, include=["metadatas", "documents"])
    emails = []
    for i, doc_id in enumerate(results['ids']):
        email_data = {
            "id": doc_id,
            "document": results['documents'][i] if results['documents'] else None,
            "metadata": results['metadatas'][i] if results['metadatas'] else None
        }
        emails.append(email_data)
    return emails

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

1. CLASSIFY: Identify ALL violation categories present (an email may have multiple violations)
2. EXTRACT: For each category, extract the specific lines from the email that contain the violation
3. SCORE: Compute a weighted priority score based on all detected violations
4. REVIEW: Generate a final verdict and recommended action

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

IMPORTANT: An email may contain violations from MULTIPLE categories. Tag ALL categories that apply.
For each category, extract the EXACT lines from the email body that contain the violation.

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
      "evidence": "<exact quote or phrase from the email that triggered this flag>",
      "lines": ["<exact line 1 from email body>", "<exact line 2 from email body>"]
    }}
  ],
  "priority_score": <computed score = if multiple violations: sum(weight × confidence for all categories) / number of categories; if single violation: weight × confidence>,
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

async def process_email_with_storage(email: dict, matrix: dict) -> dict:
    """Process a single email and store based on compliance logic."""
    result = await run_surveillance_pipeline(email, matrix)
    
    email_id = email.get("email_id", str(uuid.uuid4()))
    agent_output = result.get("agent_output", {})
    priority_score = result.get("priority_score", 0.0)
    verdict = agent_output.get("verdict", "DISMISS")
    
    # Logic:
    # - Compliant (DISMISS or no violations) -> Discard (don't store)
    # - Non-compliant + priority_score < 5 -> human_approval collection
    # - Non-compliant + priority_score >= 5 -> non_compliant collection

    if verdict == "DISMISS" or priority_score == 0.0:
        # Compliant email - discard (just return result, don't store)
        return {**result, "stored_in": None}

    if priority_score < 5.0:
        # Non-compliant but lower priority - needs human approval
        store_email(human_approval_collection, email_id, email, agent_output, priority_score)
        return {**result, "stored_in": "human_approval"}
    else:
        # Non-compliant and high priority
        store_email(non_compliant_collection, email_id, email, agent_output, priority_score)
        return {**result, "stored_in": "non_compliant"}

def get_non_compliant_emails(limit: int = 100):
    """Get all non-compliant emails (priority >= 5)."""
    return get_emails_from_collection(non_compliant_collection, limit)

def get_human_approval_emails(limit: int = 100):
    """Get all emails requiring human approval (priority < 5)."""
    return get_emails_from_collection(human_approval_collection, limit)

def delete_email_from_collection(collection, email_id: str) -> bool:
    """Delete an email from a collection by its ID."""
    try:
        collection.delete(ids=[email_id])
        return True
    except Exception as e:
        print(f"Error deleting email {email_id}: {e}")
        return False

def delete_non_compliant_email(email_id: str) -> bool:
    """Delete an email from the non-compliant collection."""
    return delete_email_from_collection(non_compliant_collection, email_id)

def delete_human_approval_email(email_id: str) -> bool:
    """Delete an email from the human approval collection."""
    return delete_email_from_collection(human_approval_collection, email_id)

def move_email_to_non_compliant(email_id: str) -> bool:
    """Move an email from human approval to non-compliant collection."""
    try:
        # Get the email from human approval collection
        results = human_approval_collection.get(ids=[email_id], include=["metadatas", "documents"])
        if not results or not results['ids']:
            return False

        # Extract email data
        document = results['documents'][0]
        metadata = results['metadatas'][0]

        # Add to non-compliant collection
        non_compliant_collection.add(
            ids=[email_id],
            documents=[document],
            metadatas=[metadata]
        )

        # Delete from human approval collection
        human_approval_collection.delete(ids=[email_id])
        return True
    except Exception as e:
        print(f"Error moving email {email_id}: {e}")
        return False

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
            "email_id": email["email_id"],
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
