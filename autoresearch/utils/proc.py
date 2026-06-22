# -*- coding: utf-8 -*-
"""Small subprocess helpers shared by channel search adapters."""


def raise_on_error(out, tool: str) -> None:
    """Raise on a nonzero CLI exit so a `research` fan-out reports an honest
    per-channel error instead of a silent empty result (e.g. `gh` not
    authenticated). ``out`` is a completed ``subprocess.run`` result."""
    if out.returncode != 0:
        msg = (out.stderr or out.stdout or "").strip()[:200]
        raise RuntimeError(
            f"{tool} exited {out.returncode}: {msg}" if msg
            else f"{tool} exited {out.returncode}"
        )
