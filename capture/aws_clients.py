"""Concrete clients for the Kepa pipeline backed by AWS and CockroachDB.

Each adapter implements one of the protocols in :mod:`capture.pipeline`.
boto3 and psycopg are imported lazily inside methods so that the pure
pipeline logic (and its tests) never require the AWS SDK.
"""

from __future__ import annotations

import json
import os
from typing import Any

from capture.pipeline import build_summary_prompt

# ── Bedrock ──────────────────────────────────────────────────────────


class BedrockSummarizer:
    """Summarizer backed by Amazon Bedrock InvokeModel (text model)."""

    def __init__(self, model_id: str | None = None, region: str | None = None) -> None:
        self.model_id = model_id or os.environ.get(
            "BEDROCK_SUMMARY_MODEL_ID", "amazon.titan-text-express-v1"
        )
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")

    def summarize(self, context: dict[str, Any]) -> str:
        import boto3  # lazy: not needed for pure-logic tests

        client = boto3.client("bedrock-runtime", region_name=self.region)
        prompt = build_summary_prompt(context)
        response = client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({"inputText": prompt}),
        )
        result = json.loads(response["body"].read())
        return result["results"][0]["outputText"].strip()


class BedrockEmbedder:
    """Embedder backed by Amazon Bedrock Titan Embed (1536 dims)."""

    def __init__(self, model_id: str | None = None, region: str | None = None) -> None:
        self.model_id = model_id or os.environ.get(
            "BEDROCK_MODEL_ID", "amazon.titan-embed-text-v1"
        )
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")

    def embed(self, text: str) -> list[float]:
        import boto3  # lazy

        client = boto3.client("bedrock-runtime", region_name=self.region)
        response = client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({"inputText": text}),
        )
        return json.loads(response["body"].read())["embedding"]


# ── S3 ───────────────────────────────────────────────────────────────


class S3RawStore:
    """RawStore that archives the PR context (and optional diff) to S3."""

    def __init__(self, bucket: str | None = None) -> None:
        self.bucket = bucket or os.environ.get("S3_BUCKET", "")

    def store(self, context: dict[str, Any], diff: str = "") -> str:
        import boto3  # lazy

        if not self.bucket:
            raise ValueError("S3_BUCKET is not configured")

        pr_number = context["source_url"].rstrip("/").split("/")[-1] or "unknown"
        key = f"raw/{context['repo']}/{pr_number}.json"

        client = boto3.client("s3")
        client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps({"context": context, "diff": diff}),
            ContentType="application/json",
        )
        return key


# ── CockroachDB ──────────────────────────────────────────────────────

_INSERT_SQL = """
INSERT INTO memory
    (id, repo, file_paths, event_type, context, resolution, source_url, embedding, metadata)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


class CockroachMemoryStore:
    """MemoryStore writing directly to CockroachDB over the postgres wire protocol.

    Requires ``DATABASE_URL`` (CockroachDB Cloud Serverless connection string
    with ``sslmode=verify-full``) and the ``psycopg`` package.
    """

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", "")

    def write(self, memory: dict[str, Any]) -> str:
        import psycopg  # lazy

        if not self.database_url:
            raise ValueError("DATABASE_URL is not configured")

        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    _INSERT_SQL,
                    (
                        memory["id"],
                        memory["repo"],
                        memory["file_paths"],
                        memory["event_type"],
                        memory["context"],
                        memory["resolution"],
                        memory["source_url"],
                        memory["embedding"],
                        json.dumps(memory.get("metadata", {})),
                    ),
                )
            conn.commit()
        return memory["id"]
