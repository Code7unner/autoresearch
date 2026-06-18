#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic eval harness for the `research` command (the build-loop metric).

Runs the real `run_research` orchestrator over a fixed benchmark, with adapters
backed by *recorded fixtures* (offline, deterministic) — so the loop optimizes
code quality, not live-result noise. Prints a single line:

    coverage_score: 0.NNN

coverage_score in [0,1], higher is better = mean over questions of
(matched expected_signals / total expected_signals). A signal "matches" if it is a
lowercase substring of any returned result's title+snippet+url for that question.

Channels are discovered from the fixture directories, so "adding a channel adapter"
in an experiment = adding its fixtures here, and the score reflects the new coverage.

Usage: python scripts/eval_research.py [--verbose]
"""

import json
import os
import sys

import yaml

from autoresearch.research import run_research

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EVAL = os.path.join(_ROOT, "tests", "eval")
_FIXTURES = os.path.join(_EVAL, "fixtures")
_QUESTIONS = os.path.join(_EVAL, "research_questions.yaml")


def _fixture_adapter(channel, qid):
    path = os.path.join(_FIXTURES, channel, f"{qid}.json")

    def _search(question, limit):
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)[:limit]

    return _search


def main(verbose=False):
    with open(_QUESTIONS, encoding="utf-8") as fh:
        questions = yaml.safe_load(fh)

    channels = sorted(
        d for d in os.listdir(_FIXTURES) if os.path.isdir(os.path.join(_FIXTURES, d))
    )

    total = 0.0
    for q in questions:
        qid, query = q["id"], q["query"]
        signals = [s.lower() for s in q["expected_signals"]]
        adapters = {c: _fixture_adapter(c, qid) for c in channels}
        out = run_research(query, adapters=adapters, limit=5)

        blob = " ".join(
            f"{r['title']} {r['snippet']} {r['url']}"
            for rows in out["results"].values() for r in rows
        ).lower()
        matched = [s for s in signals if s in blob]
        score = len(matched) / len(signals) if signals else 0.0
        total += score
        if verbose:
            missing = [s for s in signals if s not in matched]
            print(f"  {qid}: {score:.3f}  missing={missing}")

    coverage = total / len(questions) if questions else 0.0
    print(f"coverage_score: {coverage:.3f}")
    return coverage


if __name__ == "__main__":
    main(verbose="--verbose" in sys.argv or "-v" in sys.argv)
