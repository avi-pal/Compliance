# Compliance Surveillance Pipeline

## Overview

This repository implements a multi-agent compliance surveillance pipeline for email monitoring using Azure OpenAI and LangGraph. The solution uses three sequential agents to classify, score, and review emails for potential compliance violations.

## Components

- `agents.py`
  - Defines the shared `SurveillanceState` data structure.
  - Implements three asynchronous agents:
    1. `classifier_agent` - detects violation categories and extracts evidence from the email.
    2. `scorer_agent` - computes a weighted priority score using a category weight matrix.
    3. `reviewer_agent` - produces a final verdict, recommended action, and summary.
  - Builds the LangGraph workflow and exposes `run_surveillance_pipeline`.

- `main.py`
  - Provides a FastAPI web service with endpoints for health checks, matrix management, and email analysis.
  - Loads or persists the priority weight matrix from `priority_matrix.json`.
  - Routes requests to `run_surveillance_pipeline` for single or batch email processing.

- `priority_matrix.json`
  - Stores per-category weights used by the scorer.
  - If missing, `main.py` falls back to a default matrix.

- `requirements.txt`
  - Lists the Python dependencies needed to run this project.

## How It Works

1. Client sends an email payload to `/analyze` or a batch payload to `/analyze/batch`.
2. `main.py` loads the priority matrix and constructs the email state.
3. `agents.py` runs the LangGraph pipeline:
   - `classifier_agent` calls Azure OpenAI to classify the email into one or more compliance categories.
   - `scorer_agent` calculates a weighted score based on the classification confidence and the matrix.
   - `reviewer_agent` produces a final compliance verdict and action recommendation.
4. The API returns a structured JSON response containing agent outputs and final decisions.

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
        {"subject": "...", "sender": "...", "recipient": "...", "body": "...", "metadata": {} }
      ]
    }
    ```

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

## Priority Scoring

The scorer uses the formula:

```text
priority_score = sum(weight × confidence)
```

Thresholds:
- `CRITICAL` if score >= 8.0
- `HIGH` if score >= 5.0
- `MEDIUM` if score >= 2.0
- `LOW` if score < 2.0

## Notes

- The classifier and reviewer agents rely on Azure OpenAI chat completion calls.
- The pipeline is robust to API failures: the scorer has a fallback manual score computation, and the reviewer returns a default `MONITOR` verdict on error.
- `priority_matrix.json` allows tuning category weights without modifying code.
