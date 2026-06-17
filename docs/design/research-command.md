# Design: `autoresearch research "<question>"`

Status: **locked** (brainstormed 2026-06). Implementation pending.

## Understanding summary
- **What:** a new CLI command `autoresearch research "<question>"` that fans a query
  out across the active platform channels, dedupes, and returns a **structured,
  grouped JSON** payload of cited results. The calling **agent** synthesizes the
  final prose answer — `autoresearch` does not.
- **Why:** the product's differentiator is breadth (17 platforms). No competitor
  (Firecrawl = web scrape, Exa = web search) does cross-platform research. This is
  the highest-leverage feature and aligns with the product name.
- **Who:** AI agents (Claude, etc.) calling autoresearch via skill/CLI; and humans at
  the CLI.
- **Key constraint:** autoresearch stays **LLM-free** — no API keys, no cost, no
  synthesis inside the tool.
- **Non-goals (v1):** no synthesis, no cross-source ranking/scoring, no caching, no LLM.

## Decision log
1. **Synthesis = caller/agent (glue-only).** `research` gathers + dedupes and emits
   structured cited data; the agent writes the prose. _Alternatives:_ built-in LLM
   (rejected: adds key/cost/dependency), skill-only (rejected: no reusable command).
   _Why:_ preserves the LLM-free glue-layer philosophy.
2. **Default scope = all active channels** (per `doctor`), with `--channels` to narrow.
   _Alternatives:_ curated text-first set; explicit-only. _Why:_ user wants maximum
   breadth; noise is acceptable, the agent filters.
3. **Output = grouped JSON**: `{channel: [{source, title, url, snippet, date}]}`.
   _Alternatives:_ Markdown digest; both via `--format`. _Why:_ machine-parseable,
   token-efficient, consistent with existing `format hn/xhs`.

## Assumptions (confirmed)
1. **Only searchable channels participate.** "All active" = active **and** capable of a
   query-based search. Read-only / parse-only channels (web, douyin, xiaoyuzhou,
   wechat-read) are excluded from the fan-out even when active.
2. **Depth:** top **5** results per channel by default; `-n/--limit` overrides.
3. **Parallel + timeout:** channels are queried concurrently, each with a per-channel
   timeout (~20s); a slow/failed channel is skipped with an error note and **never
   blocks** the others (partial results).
4. **Dedup** by normalized URL across channels.
5. v1 non-goals as above.

## Final design (v1)
- New subcommand `research` in `autoresearch/cli.py`, dispatched like `doctor`/`format`.
- A **per-channel search-adapter layer** (new module, e.g. `autoresearch/research.py`)
  that maps each searchable channel to its existing upstream invocation (the same ones
  documented in SKILL.md): `twitter search`, `gh search`, Exa via `mcporter`, HN Algolia
  via `curl`, Reddit, V2EX, Xueqiu, YouTube/Bilibili search, etc. Each adapter returns a
  normalized list of `{source, title, url, snippet, date}`.
- An **orchestrator** that: resolves active∩searchable channels (reuse
  `doctor.check_all`), runs adapters concurrently with timeouts, collects partial
  results, dedupes by URL, and prints grouped JSON (plus a `_meta` block listing
  channels queried / skipped / errored).
- **Output schema** (stable contract for the agent):
  ```json
  {
    "query": "...",
    "results": { "hackernews": [ {"source":"hackernews","title":"...","url":"...","snippet":"...","date":"..."} ] },
    "_meta": { "channels_queried": [...], "channels_skipped": [...], "errors": {"reddit":"timeout"} }
  }
  ```
- **Testing:** TDD. Unit tests for each adapter's normalization (against recorded
  fixtures), dedup, partial-failure handling, and JSON schema. A deterministic eval
  harness (see `docs/research-program.md`) measures coverage over a fixed benchmark.
- **SKILL.md:** add a `research` section + triggers ("research", "look across",
  "what are people saying about").

## Risks
- Live results are non-deterministic → the optimization/eval loop must use **recorded
  fixtures** for a stable metric; a separate optional live smoke test checks real
  connectivity.
- Search invocations currently live only as shell snippets in SKILL.md → encoding them
  in Python is the real implementation work; keep adapters thin and uniform.
