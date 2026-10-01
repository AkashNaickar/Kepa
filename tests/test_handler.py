"""Tests for the Lambda handler with injected fakes (no AWS)."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import pytest

import capture.handler as handler_mod
from capture.handler import handler

SECRET = "test-secret"

PAYLOAD = {
    "action": "closed",
    "repository": {"full_name": "acme/webapp"},
    "pull_request": {
        "title": "fix: null pointer in user service",
        "body": "Adds a null check.",
        "html_url": "https://github.com/acme/webapp/pull/42",
        "merged": True,
        "user": {"login": "dev-alice"},
    },
}


def make_event(payload: dict[str, Any], secret: str = SECRET) -> dict[str, Any]:
    body = json.dumps(payload).encode()
    return {
        "headers": {
            "x-github-event": "pull_request",
            "x-hub-signature-256": "sha256="
            + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(),
        },
        "body": body.decode(),
    }


@pytest.fixture(autouse=True)
def webhook_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(handler_mod, "GITHUB_WEBHOOK_SECRET", SECRET)


@pytest.fixture(autouse=True)
def fake_clients(monkeypatch: pytest.MonkeyPatch) -> dict[str, list]:
    """Replace the real AWS clients with recording fakes."""
    calls: dict[str, list] = {"summary": [], "embed": [], "raw": [], "memory": []}

    class FakeSummarizer:
        def summarize(self, context: dict[str, Any]) -> str:
            calls["summary"].append(context)
            return "fake summary"

    class FakeEmbedder:
        def embed(self, text: str) -> list[float]:
            calls["embed"].append(text)
            return [0.0] * 1536

    class FakeRawStore:
        def store(self, context: dict[str, Any], diff: str = "") -> str:
            calls["raw"].append(context)
            return "raw/acme/webapp/42.json"

    class FakeMemoryStore:
        def write(self, memory: dict[str, Any]) -> str:
            calls["memory"].append(memory)
            return "fixed-memory-id"

    monkeypatch.setattr(handler_mod, "BedrockSummarizer", FakeSummarizer)
    monkeypatch.setattr(handler_mod, "BedrockEmbedder", FakeEmbedder)
    monkeypatch.setattr(handler_mod, "S3RawStore", FakeRawStore)
    monkeypatch.setattr(handler_mod, "CockroachMemoryStore", FakeMemoryStore)
    return calls


class TestHandler:
    def test_valid_signature_processes_event(self, fake_clients: dict[str, list]) -> None:
        resp = handler(make_event(PAYLOAD), None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["memory_id"] == "fixed-memory-id"
        assert body["event_type"] == "bug_fix"
        assert len(fake_clients["memory"]) == 1

    def test_invalid_signature_rejected_403(self, fake_clients: dict[str, list]) -> None:
        event = make_event(PAYLOAD)
        event["headers"]["x-hub-signature-256"] = "sha256=" + "0" * 64
        resp = handler(event, None)
        assert resp["statusCode"] == 403
        assert fake_clients["memory"] == []

    def test_missing_signature_rejected_403(self, fake_clients: dict[str, list]) -> None:
        event = make_event(PAYLOAD)
        del event["headers"]["x-hub-signature-256"]
        resp = handler(event, None)
        assert resp["statusCode"] == 403

    def test_unconfigured_secret_rejects_everything(
        self, fake_clients: dict[str, list], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(handler_mod, "GITHUB_WEBHOOK_SECRET", "")
        resp = handler(make_event(PAYLOAD), None)
        assert resp["statusCode"] == 403
        assert fake_clients["memory"] == []

    def test_non_pull_request_event_skipped(self, fake_clients: dict[str, list]) -> None:
        event = make_event(PAYLOAD)
        event["headers"]["x-github-event"] = "issues"
        resp = handler(event, None)
        assert resp["statusCode"] == 200
        assert json.loads(resp["body"])["skipped"] is True
        assert fake_clients["memory"] == []

    def test_header_case_insensitive(self, fake_clients: dict[str, list]) -> None:
        event = make_event(PAYLOAD)
        event["headers"] = {k.upper(): v for k, v in event["headers"].items()}
        resp = handler(event, None)
        assert resp["statusCode"] == 200
