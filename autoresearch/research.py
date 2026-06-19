# -*- coding: utf-8 -*-
"""Multi-source `research` orchestrator.

Fans a query out across per-channel search adapters, runs them concurrently with
per-channel timeouts, tolerates partial failures, dedupes by normalized URL across
channels, and returns a stable grouped-JSON payload that a calling agent can
synthesize. autoresearch performs NO synthesis and needs NO LLM — it only gathers.

An *adapter* is a callable ``search(question: str, limit: int) -> list[dict]`` where
each dict has at least ``source``/``title``/``url`` (``snippet``/``date`` optional).
Adapters are injectable so this module is testable offline; the live registry lives
in ``adapters.py`` / is resolved from the active channels.
"""

import re
import threading
import time
from typing import Callable, Dict, List, Optional
from urllib.parse import urlsplit

SearchFn = Callable[[str, int], List[dict]]

_RESULT_KEYS = ("source", "title", "url", "snippet", "date")

# A real URL scheme: a letter followed by letters/digits/+-. then "://".
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")


def normalize_url(url: str) -> str:
    """Normalize a URL for cross-channel dedup.

    Lowercases host, drops scheme and ``www.``, and strips a trailing slash and
    query/fragment. Good enough to collapse the common duplicate forms; not a full
    canonicalizer.
    """
    if not url:
        return ""
    # Only prepend "//" when there is genuinely no authority component. Keying off a
    # bare "//" substring misfires when "//" appears solely in the query/fragment
    # (e.g. ``example.com/p?x=a//b``), which would strand the host inside the path.
    has_authority = bool(_SCHEME_RE.match(url)) or url.startswith("//")
    parts = urlsplit(url if has_authority else "//" + url)
    host = (parts.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = (parts.path or "").rstrip("/")
    return f"{host}{path}"


def _normalize_row(row: dict) -> dict:
    """Coerce an adapter row into the stable result schema."""
    return {k: row.get(k, "") for k in _RESULT_KEYS}


def run_research(
    question: str,
    adapters: Dict[str, SearchFn],
    channels: Optional[List[str]] = None,
    limit: int = 5,
    timeout: float = 20.0,
    skipped: Optional[List[str]] = None,
    unknown: Optional[List[str]] = None,
) -> dict:
    """Run ``question`` across the selected adapters and return grouped results.

    Returns ``{"query", "results": {channel: [rows]}, "_meta": {...}}``. A channel
    that errors or exceeds ``timeout`` is omitted from ``results`` and recorded under
    ``_meta.errors``; it never blocks the others.

    ``skipped`` (channels intentionally not queried — e.g. inactive) and ``unknown``
    (requested names that aren't searchable channels) are reported verbatim in
    ``_meta``. They are decided by the caller, which knows channel/active status; this
    executor only runs ``adapters`` and never invents either list (the old self-derived
    ``channels_skipped`` was structurally always empty).
    """
    selected = sorted(channels) if channels is not None else sorted(adapters)
    selected = [c for c in selected if c in adapters]

    raw: Dict[str, List[dict]] = {}
    errors: Dict[str, str] = {}
    lock = threading.Lock()

    def _worker(channel: str) -> None:
        try:
            rows = adapters[channel](question, limit) or []
            normalized = [_normalize_row(r) for r in rows[:limit]]
            with lock:
                raw[channel] = normalized
        except Exception as exc:  # network, parse, nonzero exit — all become partial
            with lock:
                errors[channel] = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__

    # One daemon thread per channel: they run concurrently, the wait shares a single
    # deadline (bounded by the slowest channel, not the sum), and being daemon they
    # never block interpreter exit if an adapter hangs past the timeout.
    threads = [(c, threading.Thread(target=_worker, args=(c,), daemon=True)) for c in selected]
    for _, t in threads:
        t.start()
    deadline = time.monotonic() + timeout
    for channel, t in threads:
        t.join(max(0.0, deadline - time.monotonic()))

    # Snapshot under the lock so a still-running (timed-out) worker can't mutate the
    # maps while we build the response.
    with lock:
        raw = dict(raw)
        for channel in selected:
            if channel not in raw and channel not in errors:
                errors[channel] = f"TimeoutError: exceeded {timeout:g}s"
        errors = dict(errors)

    # Dedup across channels by normalized URL, deterministic by sorted channel order.
    seen = set()
    results: Dict[str, List[dict]] = {}
    for channel in selected:
        if channel not in raw:
            continue
        kept = []
        for row in raw[channel]:
            key = normalize_url(row["url"])
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            kept.append(row)
        if kept:
            results[channel] = kept

    return {
        "query": question,
        "results": results,
        "_meta": {
            "channels_queried": [c for c in selected if c not in errors],
            "channels_skipped": list(skipped or []),
            "channels_unknown": list(unknown or []),
            "errors": errors,
        },
    }
