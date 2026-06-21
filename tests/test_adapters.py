# -*- coding: utf-8 -*-
"""Unit tests for live adapter normalization (offline via monkeypatched subprocess)."""

import json
from types import SimpleNamespace

import autoresearch.adapters as A


class _NoXquikConfig:
    def get(self, key, default=None):
        return default


def test_twitter_adapter_normalizes_rows(monkeypatch):
    sample = [
        {"id": "123", "author": "@alice", "text": "tokio is great for async rust",
            "likes": 9, "rts": 1, "time": "Jun 09 16:25"},
    ]

    monkeypatch.setattr(A, "Config", lambda: _NoXquikConfig())

    def fake_run(cmd, **kw):
        return SimpleNamespace(returncode=0, stdout=json.dumps(sample), stderr="")

    monkeypatch.setattr(A.subprocess, "run", fake_run)
    rows = A.search_twitter("rust async", 5)
    assert len(rows) == 1
    r = rows[0]
    assert r["source"] == "twitter"
    assert "tokio" in r["snippet"]
    assert r["url"] == "https://x.com/alice/status/123"
    assert r["title"]  # non-empty (author or text-derived)
    for key in ("source", "title", "url", "snippet", "date"):
        assert key in r


def test_twitter_in_registry():
    assert "twitter" in A.SEARCH_ADAPTERS


def test_github_adapter_neutralizes_flag_smuggling(monkeypatch):
    """A query starting with '-' must not be parsed as a gh flag."""
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="[]", stderr="")

    monkeypatch.setattr(A.subprocess, "run", fake_run)
    A.search_github("--version", 5)
    cmd = captured["cmd"]
    # The untrusted query must come after a `--` end-of-options separator.
    assert "--" in cmd
    assert cmd.index("--") < cmd.index("--version")


def test_twitter_adapter_neutralizes_flag_smuggling(monkeypatch):
    captured = {}
    monkeypatch.setattr(A, "Config", lambda: _NoXquikConfig())

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="[]", stderr="")

    monkeypatch.setattr(A.subprocess, "run", fake_run)
    A.search_twitter("-n 9999", 5)
    cmd = captured["cmd"]
    assert "--" in cmd
    assert cmd.index("--") < cmd.index("-n 9999")


def test_exa_adapter_escapes_quotes(monkeypatch):
    """A query containing a double quote must not break out of the DSL string."""
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(A.subprocess, "run", fake_run)
    A.search_exa('foo") + evil("', 5)
    call_arg = captured["cmd"][2]
    # Raw unescaped quote sequence must not appear; it should be backslash-escaped.
    assert '") + evil("' not in call_arg
    assert '\\"' in call_arg


def test_github_adapter_raises_on_nonzero_exit(monkeypatch):
    """A failed gh call (e.g. not authenticated) must raise, not return []."""
    def fake_run(cmd, **kw):
        return SimpleNamespace(returncode=1, stdout="", stderr="gh: not logged in")
    monkeypatch.setattr(A.subprocess, "run", fake_run)
    import pytest
    with pytest.raises(Exception) as ei:
        A.search_github("anything", 5)
    assert "not logged in" in str(ei.value)


def test_twitter_adapter_raises_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr(A, "Config", lambda: _NoXquikConfig())

    def fake_run(cmd, **kw):
        return SimpleNamespace(returncode=2, stdout="", stderr="auth failed")
    monkeypatch.setattr(A.subprocess, "run", fake_run)
    import pytest
    with pytest.raises(Exception):
        A.search_twitter("anything", 5)


def test_twitter_adapter_uses_xquik_when_configured(monkeypatch):
    captured = {}

    class _XquikConfig:
        def get(self, key, default=None):
            values = {
                "xquik_api_key": "test-key",
                "xquik_base_url": "https://xquik.test",
            }
            return values.get(key, default)

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs

        class _Response:
            status_code = 200

            def json(self):
                return {
                    "tweets": [
                        {
                            "id": "42",
                            "text": "xquik search works",
                            "created": "2026-06-21T00:00:00Z",
                            "author": {"username": "alice"},
                        }
                    ]
                }

        return _Response()

    monkeypatch.setattr(A, "Config", lambda: _XquikConfig())
    monkeypatch.setattr(A.requests, "get", fake_get)
    rows = A.search_twitter("agent tools", 500)

    assert captured["url"] == "https://xquik.test/api/v1/x/tweets/search"
    assert captured["kwargs"]["headers"] == {"x-api-key": "test-key"}
    assert captured["kwargs"]["params"] == {
        "q": "agent tools",
        "queryType": "Latest",
        "limit": "200",
    }
    assert rows == [
        {
            "source": "twitter",
            "title": "@alice: xquik search works",
            "url": "https://x.com/alice/status/42",
            "snippet": "xquik search works",
            "date": "2026-06-21T00:00:00Z",
        }
    ]
