"""Kepa Capture Lambda entry point.

Receives GitHub webhook payloads, verifies the HMAC signature (fail-closed:
a missing or invalid signature is always rejected, and an unconfigured
secret rejects everything), then runs the capture pipeline with real
Bedrock / S3 / CockroachDB clients.

Deploy as a Python 3.11+ Lambda behind a Function URL or API Gateway.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from capture.aws_clients import (
    BedrockEmbedder,
    BedrockSummarizer,
    CockroachMemoryStore,
    S3RawStore,
)
from capture.pipeline import (
    SignatureError,
    dumps,
    extract_context,
    require_valid_signature,
    run_pipeline,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Lambda entry point for GitHub webhook POST requests."""
    body = event.get("body", "")
    if isinstance(body, str):
        body = body.encode("utf-8")

    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    signature = headers.get("x-hub-signature-256", "")
    github_event = headers.get("x-github-event", "")

    # ── 1. Verify the webhook signature (fail-closed) ────────────────
    try:
        require_valid_signature(body, signature, GITHUB_WEBHOOK_SECRET)
    except SignatureError:
        logger.warning("Rejected webhook: invalid or missing signature")
        return {"statusCode": 403, "body": json.dumps({"error": "Invalid signature"})}

    payload = json.loads(body)
    logger.info("Received GitHub event: %s (action: %s)", github_event, payload.get("action"))

    # ── 2. Only process pull_request events ──────────────────────────
    if github_event != "pull_request":
        return {
            "statusCode": 200,
            "body": json.dumps({"skipped": True, "reason": f"Ignoring event: {github_event}"}),
        }

    # ── 3. Run the capture pipeline with real clients ────────────────
    memory = run_pipeline(
        payload,
        summarizer=BedrockSummarizer(),
        embedder=BedrockEmbedder(),
        raw_store=S3RawStore(),
        memory_store=CockroachMemoryStore(),
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"memory_id": memory["id"], "event_type": memory["event_type"]}
        ),
    }


def describe_context(payload: dict[str, Any]) -> dict[str, Any]:
    """Expose context extraction for local inspection (not used by Lambda)."""
    return extract_context(payload)


__all__ = ["describe_context", "dumps", "handler"]
