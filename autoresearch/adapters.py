# -*- coding: utf-8 -*-
"""Live per-channel search adapters for the `research` command.

Each adapter is ``search(question: str, limit: int) -> list[dict]`` returning rows
with ``source``/``title``/``url``/``snippet``/``date``. Adapters wrap the SAME
upstream tools documented in SKILL.md (HN Algolia API, `gh`, Exa via `mcporter`) —
autoresearch only routes, it does not reimplement. Network/parse errors should
propagate; the orchestrator turns them into per-channel partial failures.

Only channels capable of a query-based search live here. Read-only / parse-only
channels (web, douyin, xiaoyuzhou, wechat-read) are intentionally absent.
"""

import json
import subprocess
import urllib.parse
import urllib.request

_UA = "autoresearch/1.0"


def _get_json(url: str, timeout: int = 10):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def search_hackernews(question: str, limit: int) -> list:
    """Hacker News stories via the public Algolia API (no auth)."""
    q = urllib.parse.quote(question)
    data = _get_json(f"https://hn.algolia.com/api/v1/search?query={q}&tags=story")
    rows = []
    for hit in (data.get("hits") or [])[:limit]:
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        rows.append({
            "source": "hackernews",
            "title": hit.get("title") or "",
            "url": url,
            "snippet": (hit.get("story_text") or "")[:280],
            "date": hit.get("created_at") or "",
        })
    return rows


def search_github(question: str, limit: int) -> list:
    """GitHub repositories via the `gh` CLI."""
    out = subprocess.run(
        ["gh", "search", "repos", question, "--limit", str(limit),
         "--json", "fullName,description,url,stargazersCount,updatedAt"],
        capture_output=True, encoding="utf-8", errors="replace", timeout=30,
    )
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
    out = subprocess.run(
        ["mcporter", "call",
         f'exa.web_search_exa(query: "{question}", numResults: {limit})'],
        capture_output=True, encoding="utf-8", errors="replace", timeout=40,
    )
    rows, cur = [], {}
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


def search_twitter(question: str, limit: int) -> list:
    """Recent tweets via twitter-cli (`twitter -c search`). Needs cookies configured."""
    out = subprocess.run(
        ["twitter", "-c", "search", question, "-n", str(limit)],
        capture_output=True, encoding="utf-8", errors="replace", timeout=30,
    )
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


# Channel name -> adapter. Keep in sync with searchable channels in doctor/check_all.
SEARCH_ADAPTERS = {
    "hackernews": search_hackernews,
    "github": search_github,
    "exa": search_exa,
    "twitter": search_twitter,
}


def live_adapters(channels=None) -> dict:
    """Resolve the adapter registry, optionally narrowed to ``channels``."""
    if channels is None:
        return dict(SEARCH_ADAPTERS)
    return {c: SEARCH_ADAPTERS[c] for c in channels if c in SEARCH_ADAPTERS}
