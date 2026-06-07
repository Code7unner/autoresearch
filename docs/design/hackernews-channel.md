# Design: Hacker News Channel

**Status:** Approved (brainstorming complete) — ready for TDD implementation
**Date:** 2026-06-06
**Scope:** Add a zero-config Hacker News channel to Agent-Reach (read + search).

---

## Understanding Summary

- **What:** A new `HackerNewsChannel` (`agent_reach/channels/hackernews.py`), tier 0, backed by the public Algolia HN Search API. Operations: `read(url)` (story + truncated comment tree) and `search(query)` (story list).
- **Why:** Hacker News is a top-requested data source for AI agents; it strengthens the "zero config" positioning (no key, no login) — raising zero-config channels from 8 to 9.
- **Who:** AI agents (via the installed skill, which documents `curl` commands) and developers calling the channel from CLI/Python.
- **Key constraints:** Stay within the glue-layer philosophy — only call the public API, never reimplement or hack internals. Mirror existing patterns (`v2ex.py`, `format_xhs_result`). Register in `ALL_CHANNELS`; pass `test_channel_contracts.py`; all tests green before commit; new branch → PR to main.
- **Non-goals (YAGNI):** No write/post. No front-page/user/comment-search in v1. No caching or client-side throttle in v1. No routing to an external `hn-cli`.

## Assumptions

1. `read(url)` accepts `news.ycombinator.com/item?id=N`, extracts `id`, calls `GET /items/{id}`.
2. `can_handle` matches `news.ycombinator.com` and `hn.algolia.com`.
3. `search(query)` → `GET /search?query=...&tags=story`.
4. Truncation defaults (read mode): depth ≤ 3, ≤ 30 top-level comments, ≤ 5 children/node, ≤ 1000 chars/comment.

## Decision Log

| # | Decision | Alternatives | Rationale |
|---|---|---|---|
| 1 | Hacker News channel, tier 0 | arXiv / Stack Exchange / Mastodon | Top source for agents; clean zero-config |
| 2 | read + search (v1) | + front page / user / comment search | Minimal `BaseChannel` contract; YAGNI |
| 3 | Direct HTTP from Python (`urllib`) | Route to `hn-cli`/MCP | `v2ex.py` precedent; true zero-config; no deps |
| 4 | Algolia API | Official Firebase v0 | Whole comment tree in one call + real search; Firebase = N+1 |
| 5 | Truncated tree + limits | Flat list / full thread | Spirit of `format_xhs_result`; protect context, keep structure |
| 6 | `format hn` with auto-detection | Tree-only (read) | One pipe for any HN curl; uniform for the agent |
| 7 | Token economy via `agent-reach format hn` | Shaping inside `read()` | `format xhs` precedent; agent hits API directly (glue) |
| 8 | TDD on mocked `urllib` | Network integration tests | Determinism; matches existing test pattern |

---

## Final Design

### 1. Channel: `agent_reach/channels/hackernews.py`

Mirrors `v2ex.py` (module-level `_get_json`, `_UA="agent-reach/1.0"`, `_TIMEOUT=10`).

```python
class HackerNewsChannel(Channel):
    name = "hackernews"
    description = "Hacker News stories and comment threads"
    backends = ["Algolia HN API (public)"]
    tier = 0
```

- **Base:** `http://hn.algolia.com/api/v1`
- `can_handle(url)` → True for `news.ycombinator.com` and `hn.algolia.com`.
- `check(config=None)` → probe `GET /search?query=test&tags=story`; `ok` on success, `warn` on network error (proxy may be required).
- `_extract_item_id(url)` → parse `?id=` via `urllib.parse`.
- `search_stories(query, limit=20)` → `GET /search?query=<q>&tags=story`; thin wrapper over `_get_json`.
- `get_item(item_id)` → `GET /items/{id}`; thin wrapper.

### 2. Token economy: `format_hn_result(data)` + CLI

Lives in `channels/hackernews.py`, imported by `_cmd_format` in `cli.py`. Auto-detects input shape:

- `{"hits": [...]}` → **search mode**: flat list, fields `title, url, author, points, num_comments, objectID, created_at`. No truncation.
- has `{"children": [...]}` / story item → **read mode**: truncated tree.

Constants (named for testability):
```python
HN_MAX_DEPTH = 3
HN_MAX_TOP_LEVEL = 30
HN_MAX_CHILDREN = 5
HN_TEXT_LIMIT = 1000
```

- Comment node → `{author, text, created_at, children}`; strip Algolia HTML tags; truncate text to `HN_TEXT_LIMIT`.
- Story head → `{title, url, author, points, num_comments}`.
- Drop `parent_id, story_id, options, null points`, etc.
- On truncated levels add `"_truncated": N` (count of hidden items) so the agent knows more exists.

CLI wiring: `format` subparser `choices=["xhs"]` → `["xhs", "hn"]`; `_cmd_format` adds an `hn` branch calling `format_hn_result(json.load(stdin))`.

### 3. Registration & skill docs

- `channels/__init__.py`: import + add `HackerNewsChannel()` to `ALL_CHANNELS`.
- `doctor.py`: auto-grouped under Tier 0 (doctor iterates `ALL_CHANNELS`).
- `skill/references/social.md`: new "Hacker News (public API)" section with curl + `| agent-reach format hn` examples (mirrors the V2EX section).
- `SKILL.md` / `SKILL_en.md`: add triggers `hackernews / hn / ycombinator`.
- No `guides/setup-*.md` (zero-config).

Agent usage:
```bash
curl -s "http://hn.algolia.com/api/v1/items/ID"                | agent-reach format hn
curl -s "http://hn.algolia.com/api/v1/search?query=Q&tags=story" | agent-reach format hn
```

### 4. Testing strategy (TDD, red → green → refactor)

All tests mock `urllib` (no real network), matching V2EX/Xueqiu/Reddit tests.

1. `test_channel_contracts.py` — HN auto-picked up (asserts `name/can_handle/check` on every channel).
2. `test_channels.py` — new tests:
   - `can_handle`: HN item URL → True; Algolia URL → True; reddit.com → False.
   - `_extract_item_id`: valid `?id=`, missing/garbage id.
   - `search_stories`: mocked `{hits:[...]}` → correct list, respects `limit`.
   - `format_hn_result` search mode: `{hits}` → flat list with required fields only.
   - `format_hn_result` read mode: deep tree → respects `HN_MAX_DEPTH/TOP_LEVEL/CHILDREN`, text truncation, `_truncated` marker, HTML stripped.
   - `check`: mocked success → `ok`; mocked network error → `warn`.
3. `test_cli.py` — `format hn` reads stdin and calls `format_hn_result`; reflect version bump here if bumped.

## Open items resolved at design time

- Truncation defaults set to 30 / 5 / 3 / 1000 (top-level / children / depth / chars).
- `format hn` uses auto-detection (search vs read).

## Risks

- Algolia API shape drift → mitigated by isolating field mapping in `format_hn_result` and covering with tests.
- HTML in comment text (Algolia returns HTML) → must strip tags in `format_hn_result`.
- Network/proxy environments → `check` returns `warn`, not a hard failure (matches V2EX).
