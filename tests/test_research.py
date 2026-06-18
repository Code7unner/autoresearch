# -*- coding: utf-8 -*-
"""Tests for the multi-source `research` orchestrator (autoresearch/research.py).

The orchestrator fans a query out across injectable per-channel search adapters,
runs them concurrently with per-channel timeouts, tolerates partial failures,
dedupes by normalized URL across channels, and returns a stable grouped-JSON
schema. Adapters are injected so these tests are fully deterministic and offline.
"""

import time

from autoresearch.research import run_research, normalize_url


def _fake(results):
    def _search(question, limit):
        return results[:limit]
    return _search


def test_groups_results_by_channel():
    adapters = {
        "hackernews": _fake([{"source": "hackernews", "title": "A", "url": "http://x/1"}]),
        "github": _fake([{"source": "github", "title": "B", "url": "http://x/2"}]),
    }
    out = run_research("q", adapters=adapters)
    assert set(out["results"].keys()) == {"hackernews", "github"}
    assert out["results"]["hackernews"][0]["title"] == "A"
    assert out["query"] == "q"


def test_schema_has_required_keys():
    adapters = {"hackernews": _fake([{"source": "hackernews", "title": "A", "url": "http://x/1"}])}
    out = run_research("q", adapters=adapters)
    row = out["results"]["hackernews"][0]
    for key in ("source", "title", "url", "snippet", "date"):
        assert key in row, f"missing {key}"
    assert set(out["_meta"]) >= {"channels_queried", "channels_skipped", "errors"}


def test_dedup_across_channels_by_normalized_url():
    dup = "https://example.com/post/"
    adapters = {
        "github": _fake([{"source": "github", "title": "dup", "url": "http://example.com/post"}]),
        "hackernews": _fake([{"source": "hackernews", "title": "dup", "url": dup}]),
    }
    out = run_research("q", adapters=adapters)
    urls = [r["url"] for rows in out["results"].values() for r in rows]
    assert len(urls) == 1, f"duplicate not removed: {urls}"


def test_partial_failure_skips_channel_and_records_error():
    def boom(question, limit):
        raise RuntimeError("api down")

    adapters = {
        "hackernews": _fake([{"source": "hackernews", "title": "A", "url": "http://x/1"}]),
        "reddit": boom,
    }
    out = run_research("q", adapters=adapters)
    assert "hackernews" in out["results"]
    assert "reddit" in out["_meta"]["errors"]
    assert "reddit" not in out["results"]


def test_limit_respected_per_channel():
    many = [{"source": "github", "title": str(i), "url": f"http://x/{i}"} for i in range(10)]
    adapters = {"github": _fake(many)}
    out = run_research("q", adapters=adapters, limit=3)
    assert len(out["results"]["github"]) == 3


def test_timeout_marks_channel_errored():
    def slow(question, limit):
        time.sleep(2)
        return [{"source": "slow", "title": "late", "url": "http://x/late"}]

    adapters = {"slow": slow}
    out = run_research("q", adapters=adapters, timeout=0.2)
    assert "slow" not in out["results"]
    assert "slow" in out["_meta"]["errors"]


def test_channels_filter_limits_which_adapters_run():
    adapters = {
        "hackernews": _fake([{"source": "hackernews", "title": "A", "url": "http://x/1"}]),
        "github": _fake([{"source": "github", "title": "B", "url": "http://x/2"}]),
    }
    out = run_research("q", adapters=adapters, channels=["github"])
    assert set(out["results"].keys()) == {"github"}
    assert out["_meta"]["channels_queried"] == ["github"]


def test_normalize_url_collapses_scheme_and_trailing_slash():
    assert normalize_url("https://Example.com/a/") == normalize_url("http://example.com/a")


def test_cli_research_prints_json(capsys, monkeypatch):
    """`autoresearch research "q"` prints grouped JSON, using injected adapters."""
    import autoresearch.adapters as adapters_mod
    import autoresearch.cli as cli

    monkeypatch.setattr(
        adapters_mod, "live_adapters",
        lambda channels=None: {"github": _fake(
            [{"source": "github", "title": "repo", "url": "http://gh/1"}])},
    )
    monkeypatch.setattr("sys.argv", ["autoresearch", "research", "mcp servers"])
    cli.main()
    import json
    out = json.loads(capsys.readouterr().out)
    assert out["query"] == "mcp servers"
    assert out["results"]["github"][0]["title"] == "repo"


def test_total_wait_bounded_by_single_deadline_not_sum(monkeypatch):
    """Multiple slow channels must share ONE deadline, not stack N x timeout."""
    import time

    def slow(question, limit):
        time.sleep(1.0)
        return [{"source": "s", "title": "x", "url": "http://x/1"}]

    adapters = {"a": slow, "b": slow, "c": slow}
    t0 = time.time()
    out = run_research("q", adapters=adapters, timeout=0.3)
    elapsed = time.time() - t0
    # One shared deadline => ~0.3s. Cumulative per-channel waits => ~0.9s+. Guard tight.
    assert elapsed < 0.7, f"waits stacked: {elapsed:.2f}s"
    assert set(out["_meta"]["errors"]) == {"a", "b", "c"}


def test_slow_channel_does_not_block_process_exit():
    """A channel slower than the timeout must not hang interpreter exit
    (worker threads must be daemon). Regression for the atexit-join hang."""
    import subprocess
    import sys
    import time

    script = (
        "import time\n"
        "from autoresearch.research import run_research\n"
        "run_research('q', adapters={'slow': lambda q, n: time.sleep(30)}, timeout=0.5)\n"
        "print('done')\n"
    )
    t0 = time.time()
    proc = subprocess.run([sys.executable, "-c", script],
                          capture_output=True, text=True, timeout=15)
    elapsed = time.time() - t0
    assert "done" in proc.stdout
    # Without daemon threads the process would hang ~30s on atexit join.
    assert elapsed < 8, f"process hung at exit: {elapsed:.2f}s"
