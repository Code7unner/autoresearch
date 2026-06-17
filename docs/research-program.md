# research-program.md — autonomous build loop for the `research` command

> This file is a lightweight "skill" in the spirit of
> [karpathy/autoresearch](https://github.com/karpathy/autoresearch): the human
> iterates on *this* file; the agent reads it and runs an autonomous experiment loop.
> Instead of optimizing a training run for `val_bpb`, you optimize an implementation of
> the `autoresearch research` command for **`coverage_score`** against a fixed,
> deterministic benchmark — keeping changes that improve it, reverting changes that don't.

## What you are building
The `autoresearch research "<question>"` command. Read the locked design first:
**`docs/design/research-command.md`** — it defines scope, output schema, and non-goals.
Also read `CLAUDE.md` (authoritative project rules) and skim `autoresearch/cli.py`,
`autoresearch/doctor.py`, `autoresearch/channels/` and `autoresearch/skill/SKILL.md`.

## Setup (do once, with the user)
1. **Agree on a run tag** (e.g. `jun17`). The branch `autoresearch/research-<tag>` must
   not already exist — this is a fresh run.
2. **Create the branch:** `git checkout -b autoresearch/research-<tag>` from `main`.
3. **Confirm baseline green:** `pytest tests/ -v` (expect ~109 passing).
4. **Build the deterministic eval harness** (this is your `evaluate_bpb` analog):
   - `tests/eval/research_questions.yaml` — ~8 fixed questions, each with
     `expected_signals`: a small list of deterministic checks (keywords that must appear
     in titles/snippets, and/or expected source domains).
   - `tests/eval/fixtures/` — record **real** per-channel search outputs once (cassettes)
     so scoring is deterministic and offline. The loop optimizes *code*, not live-result
     noise.
   - `scripts/eval_research.py` — runs `research` over the benchmark **against fixtures**
     and prints one line: `coverage_score: 0.NNN` (mean over questions of
     matched_expected_signals / total_expected_signals; higher is better, range [0,1]).
5. **Lock the metric and gates**, then record the baseline after the first real run.
6. **Confirm with the user, then start the loop. Do not ask again after this.**

## The metric (single source of truth)
`coverage_score` ∈ [0,1], higher is better. Computed by `scripts/eval_research.py`
over the fixed benchmark **on recorded fixtures** (deterministic).

**Hard gates** — an experiment is only `keep`-able if ALL hold:
- `pytest tests/ -q` is green (no regressions; new code is TDD-covered).
- `research` emits the JSON schema in the design doc (valid, deduped).
- Aggregation latency on fixtures stays within budget (set at setup, e.g. < 2s).

## Simplicity criterion
All else equal, **simpler is better**. A tiny `coverage_score` gain that adds ugly
complexity is not worth it. Removing code while holding or improving the score is a win.
Weigh complexity cost against improvement magnitude every time you decide keep/discard.

## Logging results
Append one row per experiment to `results.tsv` (TAB-separated; do **not** commit this
file — leave it untracked):
```
commit	coverage_score	status	description
a1b2c3d	0.000	keep	baseline: fan-out + dedup + JSON schema, no adapters yet
b2c3d4e	0.420	keep	add hackernews + exa adapters
c3d4e5f	0.410	discard	add reddit adapter (regressed dedup, broke 2 fixtures)
```
status ∈ {`keep`, `discard`, `crash`}. Use `0.000` for crashes.

## The experiment loop
On branch `autoresearch/research-<tag>`. **LOOP FOREVER:**
1. Note current git state (branch/commit).
2. Make ONE focused improvement. Per project rules this is **TDD**: write/extend the
   failing test first, then implement (e.g. add one channel adapter, improve dedup,
   tighten the schema, add the SKILL.md section).
3. `git commit` the change.
4. Run gates + metric: `pytest tests/ -q` then `python scripts/eval_research.py`.
5. If pytest fails or the run crashes: if it's a dumb fix (typo/import), fix and re-run;
   if the idea is fundamentally broken, `git reset --hard` to the prior commit, log
   `crash`/`discard`, move on.
6. If all gates pass AND `coverage_score` improved (or held with simpler code): **keep**
   — the branch advances. Otherwise `git reset --hard` back to the start of this
   experiment.
7. Append the row to `results.tsv`. Repeat.

## Never stop
Once the loop has begun, do **not** pause to ask "should I keep going?" / "good stopping
point?". The human may be away and expects you to work until manually stopped. If you run
out of ideas: add another channel adapter, harden partial-failure handling, improve
snippet quality/dedup, expand the benchmark, or read the upstream tools' `--help` for
better query flags. Keep going until interrupted.

## Finish (when the human stops you)
- Ensure `pytest tests/ -v` is green and `coverage_score` is at its best `keep`.
- Bump the version in all three places (`pyproject.toml`, `autoresearch/__init__.py`,
  `tests/test_cli.py`) — the consistency test enforces this.
- Open a PR from `autoresearch/research-<tag>` to `main` (never push to `main` directly).
  Summarize the `results.tsv` trajectory in the PR body.

## Guardrails (from CLAUDE.md — do not violate)
- NEVER modify upstream projects; autoresearch only routes/calls their public CLIs/APIs.
- Keep external deps owned by "Panniantong" (mcp-server-weibo, wechat-article-for-ai)
  exactly as-is.
- LLM-free: `research` must not call an LLM or need an API key at runtime.
- New branch → PR to main; run `pytest` before every commit; TDD always.
