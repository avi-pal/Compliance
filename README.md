# Email Compliance System

## Overview

This repository implements an AI-powered email compliance surveillance system using Azure OpenAI, LangGraph, and ChromaDB. The solution uses a single comprehensive compliance agent to classify, score, and review emails for potential compliance violations, with persistent storage and a modern Streamlit UI for monitoring and management.

## Components

- `agents.py`
  - Defines the shared `SurveillanceState` data structure.
  - Implements a single `compliance_agent` that performs end-to-end analysis:
    - Classifies emails into compliance violation categories
    - Extracts evidence and specific lines from email content
    - Computes weighted priority scores
    - Generates final verdicts and recommended actions
  - Manages ChromaDB collections for persistent storage:
    - `non_compliant` - high-priority violations (score >= 5.0)
    - `human_approval` - lower-priority violations (score < 5.0)
  - Exposes functions for email storage, retrieval, and management.

- `main.py`
  - FastAPI web service with comprehensive endpoints:
    - Health checks and matrix management
    - Single and batch email analysis
    - CSV upload for batch processing
    - Email management (retrieve, delete, move between collections)
  - Loads or persists the priority weight matrix from `priority_matrix.json`.
  - Implements request logging middleware for audit trails.

- `app.py`
  - Streamlit frontend with aesthetic UI for:
    - Single email analysis
    - CSV batch upload
    - Priority matrix management
    - Non-compliant email monitoring
    - Human approval workflow

- `priority_matrix.json`
  - Stores per-category weights used by the compliance agent.
  - If missing, falls back to a default matrix.

- `requirements.txt`
  - Lists the Python dependencies needed to run this project.

## How It Works

1. **Email Analysis**: Client sends an email payload to `/analyze`, `/analyze/batch`, or uploads a CSV to `/analyze/csv`.
2. **Processing**: `main.py` loads the priority matrix and routes to the surveillance pipeline.
3. **AI Analysis**: `agents.py` runs the LangGraph pipeline with the compliance agent:
   - Calls Azure OpenAI to classify the email into compliance categories
   - Extracts evidence and specific lines containing violations
   - Calculates weighted priority score based on detected violations
   - Generates final verdict (ESCALATE/MONITOR/DISMISS) and action recommendation
4. **Storage Logic**:
   - Compliant emails (DISMISS or score = 0) are discarded
   - Non-compliant with score < 5.0 stored in `human_approval` collection
   - Non-compliant with score >= 5.0 stored in `non_compliant` collection
5. **Monitoring**: Users can view and manage flagged emails via the Streamlit UI or API endpoints.

## API Endpoints

- `GET /health`
  - Returns service health status.

- `GET /matrix`
  - Returns the current priority weight matrix.

- `PUT /matrix`
  - Updates the weight matrix. Request body must include `weights`.

- `POST /analyze`
  - Analyzes a single email.
  - Request model:
    ```json
    {
      "email_id": "...",
      "subject": "...",
      "sender": "...",
      "recipient": "...",
      "body": "...",
      "metadata": {}
    }
    ```

- `POST /analyze/batch`
  - Analyzes multiple emails in one request.
  - Request model:
    ```json
    {
      "emails": [
        {"email_id": "...", "subject": "...", "sender": "...", "recipient": "...", "body": "...", "metadata": {} }
      ]
    }
    ```

- `POST /analyze/csv`
  - Uploads a CSV file for background processing.
  - Returns immediately; emails are processed asynchronously.
  - Required columns: `email_id`, `subject`, `sender`, `recipient`, `body`
  - Optional column: `metadata` (JSON string)

- `GET /emails/non-compliant`
  - Retrieves high-priority non-compliant emails (score >= 5.0).
  - Query parameter: `limit` (default: 100, max: 1000)

- `GET /emails/human-approval`
  - Retrieves emails requiring human approval (score < 5.0).
  - Query parameter: `limit` (default: 100, max: 1000)

- `DELETE /emails/non-compliant/{email_id}`
  - Deletes a non-compliant email after action has been taken.

- `DELETE /emails/human-approval/{email_id}`
  - Deletes a human approval email after marking as compliant.

- `POST /emails/human-approval/{email_id}/move-to-non-compliant`
  - Moves an email from human approval to non-compliant collection.
  - Use when human review determines the email is high priority.

## Environment Setup

1. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```

2. Create a `.env` file with Azure OpenAI settings:
   ```text
   AZURE_ENDPOINT=<your-azure-endpoint>
   AZURE_API_KEY=<your-azure-api-key>
   ```

3. Run the API server:
   ```bash
   python -m uvicorn main:app --reload
   ```

4. Run the Streamlit UI (optional, in a separate terminal):
   ```bash
   python -m streamlit run app.py
   ```

## Streamlit UI Features

The Streamlit frontend (`app.py`) provides an intuitive interface for:

- **Upload CSV**: Upload email CSV files for batch analysis with background processing
- **Priority Matrix**: View and adjust violation category weights with visual feedback
- **Non-Compliant Emails**: Monitor high-priority violations (score >= 5.0) with action buttons
- **Human Approval**: Review lower-priority violations (score < 5.0) and decide on actions

Each email card displays:
- Priority level badge and score
- Subject, sender, recipient
- AI-generated summary
- Recommended action
- Expandable full content with classifications and extracted evidence

## Priority Scoring

The compliance agent computes priority scores using:

```text
priority_score = sum(weight × confidence) / number_of_categories
```

For single violations: `weight × confidence`

Thresholds:
- `CRITICAL` if score >= 8.0
- `HIGH` if score >= 5.0
- `MEDIUM` if score >= 2.0
- `LOW` if score < 2.0

Verdict Mapping:
- `ESCALATE`: CRITICAL or HIGH priority — needs immediate human review
- `MONITOR`: MEDIUM priority — flag for periodic review
- `DISMISS`: LOW priority — likely a false positive, no action needed

## Violation Categories

The system monitors for the following compliance violation categories:
- **Secrecy**: Confidential information disclosure
- **Market Manipulation/Misconduct**: Trading irregularities
- **Market Bribery**: Corruption and bribery attempts
- **Change in Communication**: Suspicious communication pattern changes
- **Complaints**: Customer or internal complaints
- **Employee Ethics**: Ethical violations by employees

## Storage & Data Management

- **ChromaDB**: Persistent vector storage for flagged emails
- **Collections**:
  - `non_compliant`: High-priority violations (score >= 5.0)
  - `human_approval`: Lower-priority violations (score < 5.0)
- **Compliant emails**: Automatically discarded (not stored)
- **Audit logging**: All API requests logged to `api_requests.log`

## Notes

- The compliance agent uses Azure OpenAI chat completion for end-to-end analysis.
- The pipeline is robust to API failures: returns default values on error with error logging.
- `priority_matrix.json` allows tuning category weights without modifying code.
- CSV processing runs in the background to handle large batches without blocking.
