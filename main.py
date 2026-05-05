import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json
import os
from agents import run_surveillance_pipeline

app = FastAPI(title="Bank Comms Surveillance API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MATRIX_FILE = "priority_matrix.json"

DEFAULT_MATRIX = {
    "Secrecy": 2.0,
    "Market Manipulation/Misconduct": 3.0,
    "Market Bribery": 2.5,
    "Change in Communication": 1.5,
    "Complaints": 1.5,
    "Employee Ethics": 2.0
}

def load_matrix():
    if os.path.exists(MATRIX_FILE):
        with open(MATRIX_FILE) as f:
            return json.load(f)
    return DEFAULT_MATRIX


def save_matrix(matrix):
    with open(MATRIX_FILE, "w") as f:
        json.dump(matrix, f, indent=2)


class EmailRequest(BaseModel):
    subject: str
    sender: str
    recipient: str
    body: str
    metadata: Optional[dict] = {}

class BatchRequest(BaseModel):
    emails: list[EmailRequest]

class MatrixUpdate(BaseModel):
    weights: dict


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0", "engine": "LangGraph Multi-Agent Compliance Solution"}

@app.get("/matrix")
def get_matrix():
    return load_matrix()

@app.put("/matrix")
def update_matrix(update: MatrixUpdate):
    save_matrix(update.weights)
    return {"status": "updated", "weights": update.weights}

@app.post("/analyze")
async def analyze_email(request: EmailRequest):
    matrix = load_matrix()
    email_dict = {
        "subject": request.subject,
        "sender": request.sender,
        "recipient": request.recipient,
        "body": request.body,
        "metadata": request.metadata or {}
    }
    try:
        result = await run_surveillance_pipeline(email_dict, matrix)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/batch")
async def analyze_batch(request: BatchRequest):
    matrix = load_matrix()

    tasks = [
        run_surveillance_pipeline({
            "subject": email.subject,
            "sender": email.sender,
            "recipient": email.recipient,
            "body": email.body,
            "metadata": email.metadata or {}
        }, matrix)
        for email in request.emails
    ]

    try:
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return {"results": results, "total": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
