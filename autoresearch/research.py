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

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional
from urllib.parse import urlsplit

SearchFn = Callable[[str, int], List[dict]]

_RESULT_KEYS = ("source", "title", "url", "snippet", "date")


def normalize_url(url: str) -> str:
    """Normalize a URL for cross-channel dedup.

    Lowercases host, drops scheme and ``www.``, and strips a trailing slash and
    query/fragment. Good enough to collapse the common duplicate forms; not a full
    canonicalizer.
    """
    if not url:
        return ""
    parts = urlsplit(url if "//" in url else "//" + url)
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
) -> dict:
    """Run ``question`` across the selected adapters and return grouped results.

    Returns ``{"query", "results": {channel: [rows]}, "_meta": {...}}``. A channel
    that errors or exceeds ``timeout`` is omitted from ``results`` and recorded under
    ``_meta.errors``; it never blocks the others.
    """
    selected = sorted(channels) if channels is not None else sorted(adapters)
    selected = [c for c in selected if c in adapters]

    raw: Dict[str, List[dict]] = {}
    errors: Dict[str, str] = {}

    pool = ThreadPoolExecutor(max_workers=max(1, len(selected)))
    try:
        futures = {c: pool.submit(adapters[c], question, limit) for c in selected}
        # Wait on each future with its own timeout. Futures run concurrently, so the
        # total wait is bounded by the slowest channel, not the sum.
        for channel, fut in futures.items():
            try:
                rows = fut.result(timeout=timeout) or []
                raw[channel] = [_normalize_row(r) for r in rows[:limit]]
            except Exception as exc:  # timeout, network, parse — all become partial
                errors[channel] = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
    finally:
        # Don't block on a slow/hung adapter; cancel anything not yet started.
        pool.shutdown(wait=False, cancel_futures=True)

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
            "channels_skipped": [c for c in sorted(adapters) if c not in selected],
            "errors": errors,
        },
    }
