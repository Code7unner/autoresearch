#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Record real per-channel search outputs into tests/eval/fixtures/ (run once).

For each benchmark question and each live adapter, calls the real upstream tool and
saves the normalized rows as a fixture. This makes the deterministic eval reflect
*real* coverage; the build loop then optimizes code against frozen-but-real data.

Re-run when you want to refresh the cassettes. Usage:
    python scripts/record_fixtures.py [--limit 5] [--channels hackernews,github,exa]
"""

import json
import os
import sys

import yaml

from autoresearch.adapters import SEARCH_ADAPTERS

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EVAL = os.path.join(_ROOT, "tests", "eval")
_FIXTURES = os.path.join(_EVAL, "fixtures")
_QUESTIONS = os.path.join(_EVAL, "research_questions.yaml")


def _arg(flag, default):
    if flag in sys.argv:
        return sys.argv[sys.argv.index(flag) + 1]
    return default


def main():
    limit = int(_arg("--limit", "5"))
    only = _arg("--channels", "")
    channels = [c.strip() for c in only.split(",") if c.strip()] or list(SEARCH_ADAPTERS)

    with open(_QUESTIONS, encoding="utf-8") as fh:
        questions = yaml.safe_load(fh)

    for q in questions:
        qid, query = q["id"], q["query"]
        for channel in channels:
            fn = SEARCH_ADAPTERS.get(channel)
            if not fn:
                continue
            try:
                rows = fn(query, limit)
                status = f"{len(rows)} rows"
            except Exception as exc:
                rows = []
                status = f"ERROR {type(exc).__name__}: {exc}"
            outdir = os.path.join(_FIXTURES, channel)
            os.makedirs(outdir, exist_ok=True)
            with open(os.path.join(outdir, f"{qid}.json"), "w", encoding="utf-8") as fh:
                json.dump(rows, fh, ensure_ascii=False, indent=2)
            print(f"  {qid:12} {channel:12} -> {status}")


if __name__ == "__main__":
    main()
