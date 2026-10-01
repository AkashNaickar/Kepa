"""Kepa capture pipeline.

Pure, dependency-free logic for the capture flow:

    webhook payload -> classify -> extract context -> summarize -> embed
                    -> archive raw payload -> write memory

All external services (Bedrock, S3, CockroachDB) are injected as clients,
so every step is unit-testable without AWS or network access.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

# ── Webhook signature verification ───────────────────────────────────


class SignatureError(Exception):
    """Raised when a webhook signature cannot be verified."""


def verify_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    """Verify a GitHub webhook HMAC-SHA256 signature.

    Fails closed: an empty secret or missing/invalid signature header
    always returns False. There is no "skip verification" path.
    """
    if not secret:
        return False
    if not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header)


def require_valid_signature(payload_body: bytes, signature_header: str, secret: str) -> None:
    """Raise :class:`SignatureError` unless the signature is valid."""
    if not verify_signature(payload_body, signature_header, secret):
        raise SignatureError("Invalid or missing webhook signature")


# ── Event classification ─────────────────────────────────────────────

_BUG_KEYWORDS = re.compile(r"\b(fix|bug|patch|hotfix|regression|workaround)\b", re.IGNORECASE)
_DECISION_KEYWORDS = re.compile(
    r"\b(architect|design|decide|decision|tradeoff|trade-off|chose|choose|migrate|upgrade)\b",
    re.IGNORECASE,
)


def classify_event(payload: dict[str, Any]) -> str:
    """Classify a pull_request webhook payload.

    Returns one of ``bug_fix``, ``decision``, ``review_comment``.

    - PR merged with bug-ish keywords in the title -> ``bug_fix``
    - PR merged with architecture-ish keywords -> ``decision``
    - PR review submitted -> ``review_comment``
    - Anything else merged -> ``decision`` (a change worth remembering)
    """
    action = payload.get("action", "")
    pr = payload.get("pull_request", {})

    if action == "submitted":
        return "review_comment"

    if action == "closed" and pr.get("merged"):
        title = pr.get("title", "")
        if _BUG_KEYWORDS.search(title):
            return "bug_fix"
        return "decision"

    # Not merged and not a review: still record as a decision candidate
    # only if it is a pull_request event we care about; callers filter.
    return "decision"


# ── Context extraction ───────────────────────────────────────────────


def extract_context(payload: dict[str, Any], file_paths: list[str] | None = None) -> dict[str, Any]:
    """Extract the relevant context fields from a webhook payload.

    ``file_paths`` may be supplied by the caller (e.g. fetched from the
    GitHub files endpoint); it defaults to an empty list.
    """
    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {}).get("full_name", "unknown/repo")
    return {
        "repo": repo,
        "file_paths": list(file_paths or []),
        "source_url": pr.get("html_url", ""),
        "title": pr.get("title", ""),
        "body": pr.get("body", "") or "",
        "author": pr.get("user", {}).get("login", ""),
    }


def build_summary_prompt(context: dict[str, Any]) -> str:
    """Build the summarization prompt sent to the LLM."""
    return (
        "Summarize the following code change for future reference.\n"
        "Focus on WHAT was changed, WHY, and any gotchas.\n\n"
        f"Title: {context['title']}\n"
        f"Body: {context['body']}\n\n"
        "Provide a 2-3 sentence summary."
    )


# ── Client protocols (injected) ──────────────────────────────────────


@runtime_checkable
class Summarizer(Protocol):
    def summarize(self, context: dict[str, Any]) -> str: ...


@runtime_checkable
class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


@runtime_checkable
class RawStore(Protocol):
    def store(self, context: dict[str, Any], diff: str = "") -> str: ...


@runtime_checkable
class MemoryStore(Protocol):
    def write(self, memory: dict[str, Any]) -> str: ...


# ── Pipeline ─────────────────────────────────────────────────────────


def run_pipeline(
    payload: dict[str, Any],
    *,
    summarizer: Summarizer,
    embedder: Embedder,
    raw_store: RawStore,
    memory_store: MemoryStore,
    file_paths: list[str] | None = None,
    diff: str = "",
) -> dict[str, Any]:
    """Run the full capture pipeline for one webhook payload.

    Returns the memory record that was written, including its id.
    Raises whatever the injected clients raise on failure.
    """
    event_type = classify_event(payload)
    context = extract_context(payload, file_paths=file_paths)

    summary = summarizer.summarize(context)
    embedding = embedder.embed(summary)
    s3_key = raw_store.store(context, diff=diff)

    memory = {
        "id": str(uuid4()),
        "repo": context["repo"],
        "file_paths": context["file_paths"],
        "event_type": event_type,
        "context": summary,
        "resolution": "",
        "source_url": context["source_url"],
        "embedding": embedding,
        "metadata": {
            "s3_key": s3_key,
            "author": context["author"],
            "pr_title": context["title"],
        },
    }

    memory["id"] = memory_store.write(memory)
    return memory


def dumps(payload: dict[str, Any]) -> str:
    """Stable JSON serialization helper (for logging/responses)."""
    return json.dumps(payload, default=str)
