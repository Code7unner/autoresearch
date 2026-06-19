# autoresearch — improvement session

## Context
You're working on `autoresearch` (repo: github.com/Code7unner/autoresearch), a Python
CLI + skill + library that gives AI agents read/search access to 17 internet platforms
(Twitter/X, Reddit, HN, YouTube, GitHub, Bilibili, XHS, Douyin, Weibo, WeChat,
Xiaoyuzhou, LinkedIn, V2EX, Xueqiu, RSS, Exa web search, any web page). It's a
"glue layer" / installer + doctor + router — it calls upstream tools directly, never
reimplements or modifies them. Read CLAUDE.md first; it is authoritative.

## Current state
- Version 1.0.1. ~138 tests pass (`pytest tests/ -v`).
- The project was rebranded from "Agent Reach" to "autoresearch" (CLI command,
  package `autoresearch/`, class `AutoResearch`). Rebrand is merged to main.
- Active channels depend on the machine — run `autoresearch doctor` to see status.
  On the dev machine these were active: GitHub, Twitter/X, LinkedIn, HN, V2EX, RSS,
  Exa, Web (Jina), WeChat.

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

## Prioritized hypotheses to evaluate (brainstorm first, don't just build)
1. **`autoresearch research "<question>"` — multi-source fan-out + synthesis.** The
   product's name and unique edge is breadth. No competitor (Firecrawl=web, Exa=search)
   does cross-platform research. Fan out a query across active channels, dedupe, and
   synthesize a cited summary. Likely the highest-leverage feature.
   Refs: nickscamara/open-deep-research; "Building a Deep Research Agent Using
   MCP-Agent" (HN, 91 pts).
2. **First-class MCP server.** `autoresearch/integrations/mcp_server.py` exists but is
   thin. Expose 2-3 well-scoped tools (search/read/research) following MCP best
   practices: bundle workflows, sensible defaults, concrete examples, minimal tool
   count. Refs: AWS "MCP strategies" guide; Jfokus "MCP Servers Beyond 101".
3. **`autoresearch doctor --fix`** — auto-fix the fixable (yt-dlp js-runtime config,
   mcporter entries) instead of printing manual steps.
4. **Session/cookie health checks in doctor** — Twitter/LinkedIn/XHS sessions expire
   silently; doctor should detect "expired/expiring" via a cheap probe, not just
   "installed".
5. **Fetch-layer robustness** — unified retry/backoff + anti-bot/proxy fallbacks shared
   across channels. Refs: DEV "Reliable Web-Connected AI Agents Start at the Fetch
   Layer"; "Rate Limits & Anti-Bots in Agentic Scraping".
6. **Security: secrets via stdin/file, not argv.** `configure twitter-cookies "..."`
   leaks into shell history / `ps`. Read from stdin or a file.
7. **Release + CI.** Cut a GitHub Release for the current version (so `check-update`
   stops 404ing on releases/latest) and add a GitHub Actions workflow running pytest on PRs.
8. **Bilingual docs** — docs/install.md is half-Chinese; split or localize for English
   users.

## Suggested starting point
Start with hypothesis #1 (the `research` command) using the brainstorming skill to
design scope/output format before writing code, OR if you want a quick win first, do
#7 (release + CI) and #6 (secret handling). Confirm direction with the user.

## Follow-ups from the `research` command code review (PR #9)

The `research` command landed in PR #9. A high-effort code review surfaced these;
the two blockers (process-hang on slow channel, silent CLI-failure reporting) were
fixed in that PR. The rest are non-blocking follow-ups, roughly by value:

1. **Integrate `research` fan-out with active-channel status.** `adapters.live_adapters`
   returns *all searchable* adapters regardless of whether the upstream tool is
   installed/configured, so a default run reports cryptic errors (e.g.
   `_meta.errors["twitter"] = "FileNotFoundError"`) for inactive channels instead of
   skipping them. The locked design says default = *active* channels — wire it to
   `doctor.check_all` so inactive channels are skipped (and listed in
   `channels_skipped`), not errored. `autoresearch/adapters.py`, `autoresearch/cli.py:_cmd_research`.
2. **Report unknown / non-searchable channel names.** `--channels reddit,github` drops
   `reddit` silently (not searchable) — it appears in neither `errors` nor
   `channels_skipped`. Validate `--channels` against the registry and surface unknown
   names. `autoresearch/cli.py:_cmd_research`.
3. **`_meta.channels_skipped` is structurally always `[]`.** It's computed from the
   already-narrowed `adapters` dict, not the full registry, so it can never report what
   it promises. Either compute it from the full searchable set or drop the field.
   `autoresearch/research.py` (`run_research`).
4. **Validate `--limit` / `--timeout`.** `-n 0` → all channels silently empty; `-n -1`
   → drops the last result per channel; `--timeout 0` → every channel `TimeoutError`.
   Reject non-positive values at the CLI boundary. `autoresearch/cli.py`.
5. **`normalize_url` "//" heuristic.** `url if "//" in url else "//" + url` misfires when
   `//` appears only in the query/fragment (e.g. `example.com/p?x=a//b`), so the host
   lands in the path and a duplicate isn't collapsed. Detect a scheme explicitly.
   `autoresearch/research.py`.
6. **De-duplicate HN search + `_get_json` (reuse / altitude).** `adapters.search_hackernews`
   and `adapters._get_json` reimplement logic already in
   `autoresearch/channels/hackernews.py` (which even uses `http://` vs the adapter's
   `https://` — already drifting). More broadly, `adapters.py` is a parallel search
   surface that bypasses the `BaseChannel.search()` contract CLAUDE.md mandates. Consider
   routing `research` through channels' own `search()` so there's a single source of
   truth. `autoresearch/adapters.py` vs `autoresearch/channels/`.
