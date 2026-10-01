"""Unit tests for the pure capture pipeline (no AWS, no network)."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import pytest

from capture.pipeline import (
    SignatureError,
    build_summary_prompt,
    classify_event,
    extract_context,
    require_valid_signature,
    run_pipeline,
    verify_signature,
)

SECRET = "test-secret"

MERGED_BUG_PR = {
    "action": "closed",
    "repository": {"full_name": "acme/webapp"},
    "pull_request": {
        "title": "fix: null pointer in user service when email is missing",
        "body": "Adds a null check for the email field.",
        "html_url": "https://github.com/acme/webapp/pull/42",
        "merged": True,
        "user": {"login": "dev-alice"},
    },
}

MERGED_ARCH_PR = {
    "action": "closed",
    "repository": {"full_name": "acme/webapp"},
    "pull_request": {
        "title": "migrate auth service to JWT sessions",
        "body": "Chose JWT over server sessions for horizontal scaling.",
        "html_url": "https://github.com/acme/webapp/pull/43",
        "merged": True,
        "user": {"login": "dev-bob"},
    },
}

REVIEW_PAYLOAD = {
    "action": "submitted",
    "repository": {"full_name": "acme/webapp"},
    "pull_request": {
        "title": "add retry logic",
        "body": "",
        "html_url": "https://github.com/acme/webapp/pull/44",
        "user": {"login": "dev-carol"},
    },
}


def sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ── Signature verification ───────────────────────────────────────────


class TestVerifySignature:
    def test_valid_signature_passes(self) -> None:
        body = json.dumps(MERGED_BUG_PR).encode()
        assert verify_signature(body, sign(body), SECRET) is True

    def test_wrong_signature_fails(self) -> None:
        body = b"{}"
        assert verify_signature(body, sign(body, "other-secret"), SECRET) is False

    def test_missing_signature_fails(self) -> None:
        assert verify_signature(b"{}", "", SECRET) is False

    def test_missing_secret_fails_closed(self) -> None:
        body = b"{}"
        assert verify_signature(body, sign(body), "") is False

    def test_bad_prefix_fails(self) -> None:
        body = b"{}"
        assert verify_signature(body, "sha1=abc", SECRET) is False

    def test_require_valid_signature_raises_on_invalid(self) -> None:
        with pytest.raises(SignatureError):
            require_valid_signature(b"{}", "", SECRET)

    def test_require_valid_signature_passes_on_valid(self) -> None:
        body = b"payload"
        require_valid_signature(body, sign(body), SECRET)  # no raise


# ── Classification ───────────────────────────────────────────────────


class TestClassifyEvent:
    def test_merged_bug_pr(self) -> None:
        assert classify_event(MERGED_BUG_PR) == "bug_fix"

    def test_merged_architecture_pr(self) -> None:
        assert classify_event(MERGED_ARCH_PR) == "decision"

    def test_review_submission(self) -> None:
        assert classify_event(REVIEW_PAYLOAD) == "review_comment"

    def test_unmerged_pr_is_decision(self) -> None:
        pr = {**MERGED_BUG_PR["pull_request"], "merged": False}
        payload = {**MERGED_BUG_PR, "pull_request": pr}
        assert classify_event(payload) == "decision"


# ── Context extraction ───────────────────────────────────────────────


class TestExtractContext:
    def test_extracts_fields(self) -> None:
        ctx = extract_context(MERGED_BUG_PR, file_paths=["src/user.py"])
        assert ctx["repo"] == "acme/webapp"
        assert ctx["source_url"] == "https://github.com/acme/webapp/pull/42"
        assert ctx["author"] == "dev-alice"
        assert ctx["file_paths"] == ["src/user.py"]
        assert "null pointer" in ctx["title"]

    def test_none_body_becomes_empty_string(self) -> None:
        payload = {**MERGED_BUG_PR, "pull_request": {**MERGED_BUG_PR["pull_request"], "body": None}}
        assert extract_context(payload)["body"] == ""

    def test_prompt_contains_title_and_body(self) -> None:
        prompt = build_summary_prompt(extract_context(MERGED_BUG_PR))
        assert "null pointer" in prompt
        assert "null check" in prompt


# ── Full pipeline with fake clients ──────────────────────────────────


class FakeSummarizer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def summarize(self, context: dict[str, Any]) -> str:
        self.calls.append(context)
        return f"summary of {context['title']}"


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [0.1, 0.2, 0.3]


class FakeRawStore:
    def __init__(self) -> None:
        self.stored: list[tuple[dict[str, Any], str]] = []

    def store(self, context: dict[str, Any], diff: str = "") -> str:
        self.stored.append((context, diff))
        return f"raw/{context['repo']}/42.json"


class FakeMemoryStore:
    def __init__(self) -> None:
        self.written: list[dict[str, Any]] = []

    def write(self, memory: dict[str, Any]) -> str:
        self.written.append(memory)
        return "11111111-1111-1111-1111-111111111111"


class TestRunPipeline:
    def test_full_flow_writes_memory(self) -> None:
        summarizer, embedder = FakeSummarizer(), FakeEmbedder()
        raw_store, memory_store = FakeRawStore(), FakeMemoryStore()

        memory = run_pipeline(
            MERGED_BUG_PR,
            summarizer=summarizer,
            embedder=embedder,
            raw_store=raw_store,
            memory_store=memory_store,
            file_paths=["src/user.py"],
            diff="diff --git a/src/user.py",
        )

        # Order: summarize -> embed(summary) -> archive -> write
        assert embedder.calls == [f"summary of {MERGED_BUG_PR['pull_request']['title']}"]
        assert len(raw_store.stored) == 1
        assert raw_store.stored[0][1] == "diff --git a/src/user.py"
        assert len(memory_store.written) == 1

        assert memory["id"] == "11111111-1111-1111-1111-111111111111"
        assert memory["event_type"] == "bug_fix"
        assert memory["repo"] == "acme/webapp"
        assert memory["file_paths"] == ["src/user.py"]
        assert memory["embedding"] == [0.1, 0.2, 0.3]
        assert memory["metadata"]["s3_key"] == "raw/acme/webapp/42.json"
        assert memory["metadata"]["author"] == "dev-alice"
        assert memory["metadata"]["pr_title"] == MERGED_BUG_PR["pull_request"]["title"]

    def test_client_failure_propagates(self) -> None:
        class FailingStore:
            def store(self, context: dict[str, Any], diff: str = "") -> str:
                raise RuntimeError("s3 down")

        with pytest.raises(RuntimeError, match="s3 down"):
            run_pipeline(
                MERGED_BUG_PR,
                summarizer=FakeSummarizer(),
                embedder=FakeEmbedder(),
                raw_store=FailingStore(),
                memory_store=FakeMemoryStore(),
            )
