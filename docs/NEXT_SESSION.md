# autoresearch — improvement session

## Context
You're working on `autoresearch` (repo: github.com/Code7unner/autoresearch), a Python
CLI + skill + library that gives AI agents read/search access to 17 internet platforms
(Twitter/X, Reddit, HN, YouTube, GitHub, Bilibili, XHS, Douyin, Weibo, WeChat,
Xiaoyuzhou, LinkedIn, V2EX, Xueqiu, RSS, Exa web search, any web page). It's a
"glue layer" / installer + doctor + router — it calls upstream tools directly, never
reimplements or modifies them. Read CLAUDE.md first; it is authoritative.

## Current state
- Version 1.0.1. ~157 tests pass (`pytest tests/ -v`).
- The project was rebranded from "Agent Reach" to "autoresearch" (CLI command,
  package `autoresearch/`, class `AutoResearch`). Rebrand is merged to main.
- Active channels depend on the machine — run `autoresearch doctor` to see status.
  On the dev machine these were active: GitHub, Twitter/X, LinkedIn, HN, V2EX, RSS,
  Exa, Web (Jina), WeChat.

## Done (do not redo)
- **#1 `research` command** — multi-source fan-out + dedupe, grouped cited JSON. (PR #9)
  - All 6 code-review follow-ups also landed (PR #10): active-channel resolution,
    unknown-channel reporting, `_meta.channels_skipped`/`channels_unknown`,
    `--limit`/`--timeout` validation, `normalize_url` scheme detection, HN adapter
    routed through `HackerNewsChannel.search_stories`.
- **#6 Secrets via stdin/file** — `configure --stdin` / `--file PATH`, argv warning. (PR #11)
- **#7 Release + CI** — already in place: GitHub Release `v1.0.1` (check-update no longer
  404s) and `.github/workflows/pytest.yml` runs pytest on PRs.
- **#3 `doctor --fix`** — auto-applies yt-dlp JS-runtime config, Exa/mcporter entry, and
  config.yaml `chmod 0600`; manual hints for non-auto-fixable cases. New
  `Channel.fix(config) -> (changed, message)` mirrors `check()`. (PR #12)

## Hard rules (from CLAUDE.md — do not violate)
- NEVER modify upstream open-source projects. autoresearch only routes/calls.
- External upstream deps owned by "Panniantong" (mcp-server-weibo, wechat-article-for-ai)
  MUST stay as-is — they are real third-party tools, not the old repo owner. Do not
  "rebrand" or repoint them.
- Always a new branch, PR to main, never push to main directly.
- TDD: write a failing test first, then implement. Run `pytest tests/ -v` before commits.
- Version must match in 3 places: pyproject.toml, autoresearch/__init__.py,
  tests/test_cli.py — there's a guard test in tests/test_doc_consistency.py.
- There are doc<->code consistency tests (tests/test_doc_consistency.py); keep them green.

## Remaining hypotheses (brainstorm first, don't just build)
2. **First-class MCP server.** `autoresearch/integrations/mcp_server.py` exists but is
   thin. Expose 2-3 well-scoped tools (search/read/research) following MCP best
   practices: bundle workflows, sensible defaults, concrete examples, minimal tool
   count. Refs: AWS "MCP strategies" guide; Jfokus "MCP Servers Beyond 101".
   (Largest remaining item — design scope with the brainstorming skill first.)
4. **Session/cookie health checks in doctor** — Twitter/LinkedIn/XHS sessions expire
   silently; doctor should detect "expired/expiring" via a cheap probe, not just
   "installed". Pairs naturally with the `Channel.check()`/`fix()` surface from #3.
5. **Fetch-layer robustness** — unified retry/backoff + anti-bot/proxy fallbacks shared
   across channels. Refs: DEV "Reliable Web-Connected AI Agents Start at the Fetch
   Layer"; "Rate Limits & Anti-Bots in Agentic Scraping".
8. **Bilingual docs** — docs/install.md is half-Chinese; split or localize for English
   users. (Smallest remaining item — good quick win.)
9. **Expand `research` connectors** — only 4 of 17 channels feed the `research` fan-out
   today (HN, GitHub, Exa, Twitter). Add more sources and unify them under one search
   contract. **AGREED as the next initiative — full plan below.**

## Suggested starting point
**Next up: hypothesis #9 (expand `research` connectors)** — plan locked below, build in
phases. After that: **#4 session health checks** (medium, builds on `check()`/`fix()`),
**#2 MCP server** (largest), **#8 bilingual docs** (quick win).

---

## Plan: expand `research` connectors (#9 — agreed)

### Goal & decisions (locked with user, 2026-06-19)
- Grow the `research` fan-out beyond the current 4 adapters.
- **Architecture: route `research` through each channel's own `search()`** (not the
  parallel functions in `adapters.py`). This is the single-source-of-truth design and
  closes research code-review **follow-up #6** (adapters.py bypasses `BaseChannel`).
- **Connector set chosen:** Reddit, YouTube, V2EX (existing channels) + arXiv, Stack
  Overflow (new channels). China set (Weibo/XHS/Bilibili/Xueqiu) deferred — only worth
  it for China-focused research.

### Why these (connector assessment)
Requirement: the upstream tool must support *query search* (not just URL read) and map
to the research row schema `{source, title, url, snippet, date}`.
- **Reddit** — `rdt-cli` (tier 0). Live discussions/opinions — highest research value.
  ⚠️ confirm `rdt` has a search subcommand + needs `rdt login`.
- **YouTube** — `yt-dlp` `ytsearchN:<query>` returns video metadata (tier 0). Talks/reviews.
- **V2EX** — channel **already has `search(query, limit)`** (tier 0). Near-free to wire;
  niche (Chinese dev forum) but proves the channel.search() routing pattern.
- **arXiv** (new) — `export.arxiv.org/api/query` Atom feed, free, no auth. Papers.
- **Stack Overflow** (new) — `api.stackexchange.com /search/advanced`, free, ~300 req/day
  anon. Technical Q&A.
- Not suitable: RSS/Web (URL-read, not search; web search already = Exa), LinkedIn
  (ToS + people-search), WeChat/Douyin/Xiaoyuzhou (search limited/niche).

### Architecture (the search contract)
- `BaseChannel`: add `searchable: bool = False` and
  `search(self, query: str, limit: int = 5) -> list[dict]` returning research rows
  (`source/title/url/snippet/date`; dates ISO strings, snippet truncated ~280 chars).
  Default raises `NotImplementedError`; searchable channels override and set
  `searchable = True`.
- `adapters.resolve_research(channels=None)`: build the adapter map from
  `get_all_channels()` where `ch.searchable`, i.e. `{ch.name: ch.search}`, then apply
  the existing doctor-active filtering + `plan_research_channels` (skipped/unknown).
  Retire `SEARCH_ADAPTERS` and the per-tool functions (`search_github` etc.) — their
  logic moves into the channels. `adapters.py` keeps `plan_research_channels` +
  `resolve_research` only.
- `research.run_research` is unchanged (still adapter-injection based, offline-testable);
  only the *source* of the adapter map changes.

### Phasing (one PR each, TDD)
- **Phase 1 — contract + migrate existing 4 (closes follow-up #6).** Add `searchable`
  + `search()` to BaseChannel. Move HN/GitHub/Exa/Twitter search logic from `adapters.py`
  into their channels; flip `resolve_research` to read from channels. No new connectors.
- **Phase 2 — wire existing channels:** Reddit, YouTube, V2EX `search()` + `searchable=True`.
- **Phase 3 — new channels:** arXiv + Stack Overflow (`can_handle`/`check`/`search`;
  read-by-URL optional). Register in `channels/__init__`, update SKILL platform count
  (17 → 19) and skill/reference docs.

### Open questions / risks to resolve while building
- **Naming:** research currently keys Exa results as `exa`, but the channel name is
  `exa_search`. Routing by `ch.name` makes the key `exa_search`. **Recommend standardizing
  to channel names** and updating docs/tests + dropping the `_DOCTOR_TO_ADAPTER` alias
  (accept the `exa` → `exa_search` output-key change; pre-1.x, low blast radius).
- **rdt-cli search**: verify the subcommand + JSON output shape before Phase 2; gate the
  adapter on `rdt login` state (inactive → skipped via doctor, per the active-channel design).
- **yt-dlp `ytsearch` latency**: can be slow; already bounded by the per-channel research
  timeout — keep limit small.
- **Stack Exchange quota** (300/day anon) and **arXiv** rate etiquette (~1 req/3s) — fine
  for interactive research; note in the channel.
- **doc-consistency**: adding channels trips `test_skill_platform_count_matches_registered_channels`
  — bump the SKILL "N platforms" count in the same PR.
