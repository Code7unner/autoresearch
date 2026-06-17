# -*- coding: utf-8 -*-
"""Unit tests for live adapter normalization (offline via monkeypatched subprocess)."""

import json
from types import SimpleNamespace

import autoresearch.adapters as A


def test_twitter_adapter_normalizes_rows(monkeypatch):
    sample = [
        {"id": "123", "author": "@alice", "text": "tokio is great for async rust",
         "likes": 9, "rts": 1, "time": "Jun 09 16:25"},
    ]

    def fake_run(cmd, **kw):
        return SimpleNamespace(stdout=json.dumps(sample), stderr="")

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
