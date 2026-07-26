"""
Kepa Capture Lambda

Receives GitHub webhook payloads, summarizes + embeds via Bedrock,
and writes the result to CockroachDB via the Managed MCP Server.

TODO: Deploy as a Python 3.11 Lambda behind API Gateway.
"""

import json
import hashlib
import hmac
import os
import urllib.request
from datetime import datetime, timezone
from uuid import uuid4

# ── Configuration ────────────────────────────────────────────────────
# TODO: Move these to Lambda environment variables
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.titan-embed-text-v1")
BEDROCK_REGION = os.environ.get("AWS_REGION", "us-east-1")
COCKROACH_MCP_ENDPOINT = os.environ.get("COCKROACH_MCP_ENDPOINT", "")
S3_BUCKET = os.environ.get("S3_BUCKET", "")
GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")


def verify_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verify the GitHub webhook HMAC signature."""
    if not GITHUB_WEBHOOK_SECRET:
        # TODO: Remove this fallback before production — only for local testing
        print("WARNING: No webhook secret configured, skipping verification")
        return True

    if not signature_header:
        return False

    expected = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(),
        payload_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header)


def classify_event(payload: dict) -> str:
    """
    TODO: Classify the GitHub event into one of:
      - bug_fix     (PR merged with keywords like fix, bug, patch)
      - decision    (PR review comment with architectural rationale)
      - review_comment (inline review comment)
    """
    # Placeholder logic — replace with LLM classification or regex heuristics
    action = payload.get("action", "")
    if action == "closed" and payload.get("pull_request", {}).get("merged"):
        title = payload["pull_request"].get("title", "").lower()
        if any(kw in title for kw in ("fix", "bug", "patch", "hotfix")):
            return "bug_fix"
    if action == "submitted":
        return "review_comment"
    return "decision"


def extract_context(payload: dict) -> dict:
    """
    TODO: Extract relevant context from the webhook payload:
      - repo name, file paths changed, PR title/body, diff URL, author, etc.
    """
    pr = payload.get("pull_request", {})
    return {
        "repo": payload.get("repository", {}).get("full_name", "unknown/repo"),
        "file_paths": [],  # TODO: Extract from PR files endpoint
        "source_url": pr.get("html_url", ""),
        "title": pr.get("title", ""),
        "body": pr.get("body", ""),
        "author": pr.get("user", {}).get("login", ""),
    }


def summarize_with_bedrock(context: dict) -> str:
    """
    TODO: Call Amazon Bedrock to generate a concise summary of the
    decision or bug fix from the PR context.

    Use the Converse API or InvokeModel with Claude / Titan Text.
    """
    # Placeholder — replace with actual Bedrock call
    prompt = f"""Summarize the following code change for future reference.
Focus on WHAT was changed, WHY, and any gotchas.

Title: {context['title']}
Body: {context['body']}

Provide a 2-3 sentence summary."""

    # TODO: Implement Bedrock InvokeModel call
    # import boto3
    # bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    # response = bedrock.invoke_model(
    #     modelId=BEDROCK_MODEL_ID,
    #     body=json.dumps({"inputText": prompt}),
    # )
    # return json.loads(response["body"].read())["results"][0]["outputText"]

    return f"[STUB] Summary of: {context['title']}"


def embed_with_bedrock(text: str) -> list[float]:
    """
    TODO: Generate a 1536-dimension embedding via Bedrock.
    Use Titan Embed Text or Cohere Embed.
    """
    # Placeholder — replace with actual Bedrock embedding call
    # import boto3
    # bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    # response = bedrock.invoke_model(
    #     modelId="amazon.titan-embed-text-v1",
    #     body=json.dumps({"inputText": text}),
    # )
    # return json.loads(response["body"].read())["embedding"]

    # Return a mock 1536-dim vector for local testing
    return [0.0] * 1536


def store_raw_in_s3(context: dict, diff: str = "") -> str:
    """
    TODO: Store the raw PR body and diff in S3 for archival.
    Return the S3 key.
    """
    key = f"raw/{context['repo']}/{context['source_url'].split('/')[-1]}.json"

    # TODO: Implement S3 put_object
    # import boto3
    # s3 = boto3.client("s3")
    # s3.put_object(
    #     Bucket=S3_BUCKET,
    #     Key=key,
    #     Body=json.dumps({"context": context, "diff": diff}),
    #     ContentType="application/json",
    # )

    print(f"[STUB] Would store raw data at s3://{S3_BUCKET}/{key}")
    return key


def write_to_cockroachdb(memory: dict) -> str:
    """
    TODO: Write the memory record to CockroachDB via the Managed MCP Server.

    The MCP server exposes a tool like `insert_memory` or you can use
    the SQL endpoint directly with psycopg2 / crdb driver.
    """
    memory_id = str(uuid4())

    # TODO Option A: Use CockroachDB MCP Server tool call
    # This is the preferred approach when the Managed MCP Server is enabled.
    # The MCP server handles auth, connection pooling, and query routing.
    #
    # TODO Option B: Direct SQL via psycopg2
    # import psycopg2
    # conn = psycopg2.connect(os.environ["DATABASE_URL"])
    # cur = conn.cursor()
    # cur.execute("""
    #     INSERT INTO memory (id, repo, file_paths, event_type, context, resolution, source_url, embedding, metadata)
    #     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    # """, (
    #     memory_id, memory["repo"], memory["file_paths"], memory["event_type"],
    #     memory["context"], memory["resolution"], memory["source_url"],
    #     str(memory["embedding"]), json.dumps(memory.get("metadata", {}))
    # ))
    # conn.commit()

    print(f"[STUB] Would write memory {memory_id} to CockroachDB")
    print(f"  repo: {memory['repo']}")
    print(f"  event_type: {memory['event_type']}")
    return memory_id


def handler(event, context):
    """
    Lambda entry point — handles GitHub webhook POST requests.
    """
    # ── 1. Parse and verify the webhook ──────────────────────────────
    body = event.get("body", "")
    if isinstance(body, str):
        body = body.encode("utf-8")

    headers = event.get("headers", {})
    signature = headers.get("x-hub-signature-256", headers.get("X-Hub-Signature-256", ""))

    if not verify_signature(body, signature):
        return {"statusCode": 403, "body": json.dumps({"error": "Invalid signature"})}

    payload = json.loads(body)
    github_event = headers.get("x-github-event", headers.get("X-GitHub-Event", ""))

    print(f"Received GitHub event: {github_event} (action: {payload.get('action')})")

    # ── 2. Only process relevant events ──────────────────────────────
    if github_event != "pull_request":
        return {"statusCode": 200, "body": json.dumps({"skipped": True, "reason": f"Ignoring event: {github_event}"})}

    # ── 3. Classify the event ────────────────────────────────────────
    event_type = classify_event(payload)
    context_data = extract_context(payload)

    # ── 4. Summarize via Bedrock ─────────────────────────────────────
    summary = summarize_with_bedrock(context_data)

    # ── 5. Embed via Bedrock ─────────────────────────────────────────
    embedding = embed_with_bedrock(summary)

    # ── 6. Store raw payload in S3 ───────────────────────────────────
    s3_key = store_raw_in_s3(context_data)

    # ── 7. Write structured memory to CockroachDB ────────────────────
    memory = {
        "repo": context_data["repo"],
        "file_paths": context_data["file_paths"],
        "event_type": event_type,
        "context": summary,
        "resolution": "",  # TODO: Extract from merged PR diff or review thread
        "source_url": context_data["source_url"],
        "embedding": embedding,
        "metadata": {
            "s3_key": s3_key,
            "author": context_data["author"],
            "pr_title": context_data["title"],
        },
    }

    memory_id = write_to_cockroachdb(memory)

    return {
        "statusCode": 200,
        "body": json.dumps({"memory_id": memory_id, "event_type": event_type}),
    }


# ── Local testing ────────────────────────────────────────────────────
if __name__ == "__main__":
    # Mock GitHub pull_request webhook payload for local testing
    MOCK_PAYLOAD = {
        "action": "closed",
        "repository": {"full_name": "acme/webapp"},
        "pull_request": {
            "title": "fix: null pointer in user service when email is missing",
            "body": "This PR fixes NPE in UserService.getDisplayName() by adding a null check for the email field.",
            "html_url": "https://github.com/acme/webapp/pull/42",
            "merged": True,
            "user": {"login": "dev-alice"},
        },
    }

    mock_event = {
        "headers": {
            "x-github-event": "pull_request",
            "x-hub-signature-256": "",
        },
        "body": json.dumps(MOCK_PAYLOAD),
    }

    result = handler(mock_event, None)
    print(json.dumps(result, indent=2))
