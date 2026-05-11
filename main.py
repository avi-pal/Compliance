import asyncio
import io
import logging
import time
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json
import os
import pandas as pd

# ── Logging Configuration ────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('api_requests.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
from agents import (
    run_surveillance_pipeline, process_email_with_storage,
    get_non_compliant_emails, get_human_approval_emails,
    delete_non_compliant_email, delete_human_approval_email,
    move_email_to_non_compliant
)

app = FastAPI(title="Email Compliance System API", version="1.0.0")

# ── Request Logging Middleware ──────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path

    logger.info(f"REQUEST | {client_ip} | {method} {path}")

    try:
        response = await call_next(request)
        duration = time.time() - start_time
        status = response.status_code

        logger.info(f"RESPONSE | {client_ip} | {method} {path} | Status: {status} | Duration: {duration:.3f}s")
        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"ERROR | {client_ip} | {method} {path} | Error: {str(e)} | Duration: {duration:.3f}s")
        raise

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
    email_id: str
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
    return {"status": "ok", "version": "1.0.0", "engine": "LangGraph Single-Agent Compliance Solution"}

@app.get("/matrix")
def get_matrix():
    return load_matrix()

@app.put("/matrix")
def update_matrix(update: MatrixUpdate):
    logger.info(f"MATRIX_UPDATE | Priority matrix updated with {len(update.weights)} categories")
    save_matrix(update.weights)
    return {"status": "updated", "weights": update.weights}

@app.post("/analyze")
async def analyze_email(request: EmailRequest):
    logger.info(f"ANALYZE | Analyzing single email: {request.email_id} | Subject: {request.subject}")
    matrix = load_matrix()
    email_dict = {
        "email_id": request.email_id,
        "subject": request.subject,
        "sender": request.sender,
        "recipient": request.recipient,
        "body": request.body,
        "metadata": request.metadata or {}
    }
    try:
        result = await run_surveillance_pipeline(email_dict, matrix)
        logger.info(f"ANALYZE | Email {request.email_id} processed | Verdict: {result.get('verdict', 'UNKNOWN')} | Score: {result.get('priority_score', 0)}")
        return result
    except Exception as e:
        logger.error(f"ANALYZE | Failed to analyze email {request.email_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/batch")
async def analyze_batch(request: BatchRequest):
    email_count = len(request.emails)
    logger.info(f"BATCH | Processing {email_count} emails in batch")
    matrix = load_matrix()

    tasks = [
        run_surveillance_pipeline({
            "email_id": email.email_id,
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
        logger.info(f"BATCH | Successfully processed {len(results)} emails")
        return {"results": results, "total": len(results)}
    except Exception as e:
        logger.error(f"BATCH | Failed to process batch: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_csv_background(file_content: bytes, matrix: dict):
    """Background task to process CSV emails with compliance logic."""
    try:
        df = pd.read_csv(io.BytesIO(file_content))
        total_emails = len(df)
        logger.info(f"CSV_BG | Starting background processing of {total_emails} emails from CSV")

        # Expected columns: email_id, subject, sender, recipient, body, metadata (optional)
        processed = 0
        for _, row in df.iterrows():
            email_dict = {
                "email_id": str(row.get("email_id", "")),
                "subject": str(row.get("subject", "")),
                "sender": str(row.get("sender", "")),
                "recipient": str(row.get("recipient", "")),
                "body": str(row.get("body", "")),
                "metadata": json.loads(row.get("metadata", "{}")) if pd.notna(row.get("metadata")) else {}
            }

            try:
                result = await process_email_with_storage(email_dict, matrix)
                stored_in = result.get('stored_in', 'unknown')
                if stored_in:
                    logger.info(f"CSV_BG | Email {email_dict['email_id']} stored in {stored_in} | Score: {result.get('priority_score', 0)}")
                else:
                    logger.info(f"CSV_BG | Email {email_dict['email_id']} discarded (compliant)")
                processed += 1
            except Exception as e:
                logger.error(f"CSV_BG | Error processing email {email_dict['email_id']}: {e}")
                continue

        logger.info(f"CSV_BG | Completed processing {processed}/{total_emails} emails from CSV")
    except Exception as e:
        logger.error(f"CSV_BG | Error processing CSV: {e}")


@app.post("/analyze/csv")
async def analyze_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="CSV file with email columns: email_id, subject, sender, recipient, body, metadata (optional)")
):
    """
    Upload a CSV file with emails for async processing.
    Returns OK immediately, processes emails in background.
    """
    if not file.filename.endswith('.csv'):
        logger.warning(f"CSV_UPLOAD | Rejected non-CSV file: {file.filename}")
        raise HTTPException(status_code=400, detail="File must be a CSV")

    logger.info(f"CSV_UPLOAD | Received CSV upload: {file.filename}")
    matrix = load_matrix()
    file_content = await file.read()

    # Add background task to process emails
    background_tasks.add_task(process_csv_background, file_content, matrix)
    logger.info(f"CSV_UPLOAD | Queued background processing for {file.filename}")

    return {
        "status": "ok",
        "message": "CSV uploaded successfully. Emails are being processed in the background.",
        "filename": file.filename
    }


@app.get("/emails/non-compliant")
def get_non_compliant_emails_endpoint(limit: int = Query(100, ge=1, le=1000)):
    """
    Get all non-compliant emails with priority score >= 5.
    These are high-priority violations.
    """
    try:
        emails = get_non_compliant_emails(limit)
        logger.info(f"GET_NON_COMPLIANT | Retrieved {len(emails)} non-compliant emails (limit: {limit})")
        return {
            "status": "ok",
            "count": len(emails),
            "emails": emails
        }
    except Exception as e:
        logger.error(f"GET_NON_COMPLIANT | Failed to retrieve emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/emails/human-approval")
def get_human_approval_emails_endpoint(limit: int = Query(100, ge=1, le=1000)):
    """
    Get all emails requiring human approval (non-compliant with priority score < 5).
    These are lower-priority violations that need manual review.
    """
    try:
        emails = get_human_approval_emails(limit)
        logger.info(f"GET_HUMAN_APPROVAL | Retrieved {len(emails)} human approval emails (limit: {limit})")
        return {
            "status": "ok",
            "count": len(emails),
            "emails": emails
        }
    except Exception as e:
        logger.error(f"GET_HUMAN_APPROVAL | Failed to retrieve emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/emails/non-compliant/{email_id}")
def delete_non_compliant_email_endpoint(email_id: str):
    """
    Delete a non-compliant email after action has been taken.
    """
    try:
        success = delete_non_compliant_email(email_id)
        if success:
            logger.info(f"DELETE_NON_COMPLIANT | Email {email_id} deleted (action taken)")
            return {"status": "ok", "message": f"Email {email_id} deleted successfully"}
        else:
            logger.warning(f"DELETE_NON_COMPLIANT | Email {email_id} not found")
            raise HTTPException(status_code=404, detail=f"Email {email_id} not found")
    except Exception as e:
        logger.error(f"DELETE_NON_COMPLIANT | Failed to delete email {email_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/emails/human-approval/{email_id}")
def delete_human_approval_email_endpoint(email_id: str):
    """
    Delete a human approval email after action has been taken (marked as compliant).
    """
    try:
        success = delete_human_approval_email(email_id)
        if success:
            logger.info(f"DELETE_HUMAN_APPROVAL | Email {email_id} deleted (marked as compliant)")
            return {"status": "ok", "message": f"Email {email_id} deleted successfully"}
        else:
            logger.warning(f"DELETE_HUMAN_APPROVAL | Email {email_id} not found")
            raise HTTPException(status_code=404, detail=f"Email {email_id} not found")
    except Exception as e:
        logger.error(f"DELETE_HUMAN_APPROVAL | Failed to delete email {email_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/emails/human-approval/{email_id}/move-to-non-compliant")
def move_to_non_compliant_endpoint(email_id: str):
    """
    Move an email from human approval to non-compliant collection.
    Use this when human review determines the email is actually high priority.
    """
    try:
        success = move_email_to_non_compliant(email_id)
        if success:
            logger.info(f"MOVE_TO_NON_COMPLIANT | Email {email_id} moved from human_approval to non_compliant")
            return {"status": "ok", "message": f"Email {email_id} moved to non-compliant list"}
        else:
            logger.warning(f"MOVE_TO_NON_COMPLIANT | Email {email_id} not found in human_approval")
            raise HTTPException(status_code=404, detail=f"Email {email_id} not found")
    except Exception as e:
        logger.error(f"MOVE_TO_NON_COMPLIANT | Failed to move email {email_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
