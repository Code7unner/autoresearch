# -*- coding: utf-8 -*-
"""Live per-channel search adapters for the `research` command.

Each adapter is ``search(question: str, limit: int) -> list[dict]`` returning rows
with ``source``/``title``/``url``/``snippet``/``date``. Adapters wrap the SAME
upstream tools documented in SKILL.md (HN Algolia API, `gh`, Exa via `mcporter`) -
autoresearch only routes, it does not reimplement. Network/parse errors should
propagate; the orchestrator turns them into per-channel partial failures.

Only channels capable of a query-based search live here. Read-only / parse-only
channels (web, douyin, xiaoyuzhou, wechat-read) are intentionally absent.
"""

import json
import subprocess
from typing import Any, Optional, cast

import requests

from autoresearch.config import Config

_XQUIK_BASE_URL = "https://xquik.com"
JsonDict = dict[str, Any]


def _check(out, tool: str):
    """Raise on a nonzero CLI exit so the orchestrator reports an honest error
    instead of a silent empty result (e.g. `gh` not authenticated)."""
    if out.returncode != 0:
        msg = (out.stderr or out.stdout or "").strip()[:200]
        raise RuntimeError(f"{tool} exited {out.returncode}: {msg}" if msg
                           else f"{tool} exited {out.returncode}")


def search_hackernews(question: str, limit: int) -> list:
    """Hacker News stories - delegated to the HackerNews channel's own search.

    Routes through ``HackerNewsChannel.search_stories`` (the single Algolia source of
    truth) and maps its rows into the research schema, instead of re-implementing the
    API call here (which had drifted to a different scheme + duplicate JSON fetch)."""
    from autoresearch.channels.hackernews import HackerNewsChannel

    rows = []
    for hit in HackerNewsChannel().search_stories(question, limit)[:limit]:
        object_id = hit.get("objectID")
        url = hit.get("url") or (
            f"https://news.ycombinator.com/item?id={object_id}" if object_id else "")
        rows.append({
            "source": "hackernews",
            "title": hit.get("title") or "",
            "url": url,
            "snippet": "",
            "date": hit.get("created_at") or "",
        })
    return rows


def search_github(question: str, limit: int) -> list:
    """GitHub repositories via the `gh` CLI."""
    # `--` ends option parsing so a query starting with `-` can't smuggle a flag.
    out = subprocess.run(
        ["gh", "search", "repos", "--limit", str(limit),
         "--json", "fullName,description,url,stargazersCount,updatedAt",
         "--", question],
        capture_output=True, encoding="utf-8", errors="replace", timeout=30,
    )
    _check(out, "gh")
    items = json.loads(out.stdout or "[]")
    return [{
        "source": "github",
        "title": it.get("fullName") or "",
        "url": it.get("url") or "",
        "snippet": (it.get("description") or "")[:280],
        "date": it.get("updatedAt") or "",
    } for it in items[:limit]]


def search_exa(question: str, limit: int) -> list:
    """Web search via Exa MCP (mcporter). Parses mcporter's text output."""
    # Escape backslash + double-quote so the query can't break out of the DSL string.
    safe_q = question.replace("\\", "\\\\").replace('"', '\\"')
    out = subprocess.run(
        ["mcporter", "call",
         f'exa.web_search_exa(query: "{safe_q}", numResults: {int(limit)})'],
        capture_output=True, encoding="utf-8", errors="replace", timeout=40,
    )
    _check(out, "mcporter")
    rows: list[dict[str, str]] = []
    cur: dict[str, str] = {}
    for line in (out.stdout or "").splitlines():
        if line.startswith("Title:"):
            if cur.get("url"):
                rows.append(cur)
            cur = {"source": "exa", "title": line[6:].strip(), "url": "", "snippet": "", "date": ""}
        elif line.startswith("URL:"):
            cur["url"] = line[4:].strip()
        elif line.startswith("Published:"):
            cur["date"] = line[10:].strip()
    if cur.get("url"):
        rows.append(cur)
    return rows[:limit]


def _xquik_settings() -> Optional[tuple[str, str]]:
    config = Config()
    api_key = config.get("xquik_api_key")
    if not api_key:
        return None
    return api_key, config.get("xquik_base_url", _XQUIK_BASE_URL).rstrip("/")


def _first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value:
            return value
        if isinstance(value, (int, float)):
            return str(value)
    return ""


def _xquik_tweets(payload: JsonDict) -> list[JsonDict]:
    tweets = payload.get("tweets")
    if isinstance(tweets, list):
        return [item for item in tweets if isinstance(item, dict)]
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("tweets"), list):
        return [item for item in data["tweets"] if isinstance(item, dict)]
    return []


def _xquik_row(tweet: JsonDict) -> dict[str, str]:
    raw_author = tweet.get("author")
    author = cast(JsonDict, raw_author) if isinstance(raw_author, dict) else {}
    username = _first_text(author.get("username"), author.get("screen_name"), tweet.get("username"))
    text = _first_text(tweet.get("text"), tweet.get("full_text"))
    tweet_id = _first_text(tweet.get("id"), tweet.get("id_str"), tweet.get("tweet_id"))
    title_prefix = f"@{username}: " if username else ""
    return {
        "source": "twitter",
        "title": f"{title_prefix}{text[:60]}".strip(),
        "url": _first_text(tweet.get("url")) or (
            f"https://x.com/{username}/status/{tweet_id}" if username and tweet_id else ""
        ),
        "snippet": text[:280],
        "date": _first_text(tweet.get("created"), tweet.get("created_at"), tweet.get("createdAt")),
    }


def search_twitter_xquik(question: str, limit: int, api_key: str, base_url: str) -> list:
    """Recent tweets via Xquik. Needs XQUIK_API_KEY or xquik_api_key config."""
    bounded_limit = max(1, min(int(limit), 200))
    response = requests.get(
        f"{base_url}/api/v1/x/tweets/search",
        headers={"x-api-key": api_key},
        params={"q": question, "queryType": "Latest", "limit": str(bounded_limit)},
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Xquik API returned {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Xquik API returned invalid JSON") from exc
    return [_xquik_row(tweet) for tweet in _xquik_tweets(payload)[:bounded_limit]]


def _search_twitter_cli(question: str, limit: int) -> list:
    """Recent tweets via twitter-cli (`twitter -c search`). Needs cookies configured."""
    # `--` ends option parsing so a query starting with `-` can't smuggle a flag.
    out = subprocess.run(
        ["twitter", "-c", "search", "-n", str(limit), "--", question],
        capture_output=True, encoding="utf-8", errors="replace", timeout=30,
    )
    _check(out, "twitter")
    items = json.loads(out.stdout or "[]")
    rows = []
    for it in items[:limit]:
        author = (it.get("author") or "").lstrip("@")
        text = it.get("text") or ""
        rows.append({
            "source": "twitter",
            "title": f"{it.get('author', '')}: {text[:60]}".strip(),
            "url": f"https://x.com/{author}/status/{it.get('id')}" if author else "",
            "snippet": text[:280],
            "date": it.get("time") or "",
        })
    return rows


def search_twitter(question: str, limit: int) -> list:
    """Recent tweets via the configured Twitter/X backend."""
    xquik = _xquik_settings()
    if xquik:
        api_key, base_url = xquik
        return search_twitter_xquik(question, limit, api_key, base_url)
    return _search_twitter_cli(question, limit)


# Channel name -> adapter. Keep in sync with searchable channels in doctor/check_all.
SEARCH_ADAPTERS = {
    "hackernews": search_hackernews,
    "github": search_github,
    "exa": search_exa,
    "twitter": search_twitter,
}

# The research adapter for Exa is keyed "exa"; doctor registers the channel as
# "exa_search". Map doctor/CLI names onto adapter names so a user can write either.
_DOCTOR_TO_ADAPTER = {"exa_search": "exa"}


def _to_adapter_name(name: str) -> str:
    return _DOCTOR_TO_ADAPTER.get(name, name)


def live_adapters(channels=None) -> dict:
    """Resolve the adapter registry, optionally narrowed to ``channels``."""
    if channels is None:
        return dict(SEARCH_ADAPTERS)
    return {c: SEARCH_ADAPTERS[c] for c in channels if c in SEARCH_ADAPTERS}


def plan_research_channels(requested, active, searchable, known):
    """Decide which channels to query, skip, or flag - given plain name sets.

    Pure (no doctor/Config dependency) so it is unit-testable offline.

    Args:
        requested: explicit ``--channels`` list, or ``None`` for the default run.
        active:    channel names usable right now (doctor status "ok").
        searchable: channel names that have a search adapter.
        known:     every registered channel name (searchable or not).

    Returns ``(run, skipped, unknown)``, each a sorted list:
        run:     channels to actually query.
        skipped: searchable channels skipped because inactive (default run only).
        unknown: requested names that are not searchable channels - covers both
                 real-but-not-searchable (e.g. ``reddit``) and outright typos.
    """
    searchable, active = set(searchable), set(active)
    if requested is None:
        # Default = active searchable channels; the rest are skipped, not errored.
        default_run = searchable & active
        return sorted(default_run), sorted(searchable - active), []
    # Explicit request overrides the active filter: the user asked for these by name,
    # so run them even if doctor thinks they're inactive and let any real error surface.
    run: set[str] = set()
    unknown: set[str] = set()
    for name in requested:
        (run if name in searchable else unknown).add(name)
    return sorted(run), [], sorted(unknown)


def resolve_research(channels=None):
    """Doctor-aware resolution of a research run into ``(adapters, skipped, unknown)``.

    Probes channel health via ``doctor.check_all`` so a default run targets only
    *active* channels (the locked design), and surfaces inactive/unknown names instead
    of letting them fail with cryptic per-channel errors.
    """
    from autoresearch.config import Config
    from autoresearch.doctor import check_all

    results = check_all(Config())
    active = {_to_adapter_name(n) for n, r in results.items() if r.get("status") == "ok"}
    known = {_to_adapter_name(n) for n in results}
    searchable = set(SEARCH_ADAPTERS)
    requested = [_to_adapter_name(c) for c in channels] if channels else None

    run, skipped, unknown = plan_research_channels(requested, active, searchable, known)
    adapters = {n: SEARCH_ADAPTERS[n] for n in run}
    return adapters, skipped, unknown
