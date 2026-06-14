"""Consistency guards between docs and code.

These tests catch the class of bugs where the skill/install docs drift away from
what the code actually installs and registers:

- the Twitter section must use the binary the installer provides (`twitter`),
  not the optional `bird` fallback that most users won't have;
- the "N platforms" claim must match the number of registered channels;
- the install guide's LinkedIn setup must use the robust stdio + home-scope
  mcporter config, not a fragile per-session HTTP server written into the
  current (possibly tracked) project config.
"""

import os
import re

import pytest

import agent_reach

_PKG_DIR = os.path.dirname(agent_reach.__file__)
_REPO_ROOT = os.path.dirname(_PKG_DIR)
SKILL_MD = os.path.join(_PKG_DIR, "skill", "SKILL.md")
INSTALL_MD = os.path.join(_REPO_ROOT, "docs", "install.md")


def _read(path):
    if not os.path.exists(path):
        pytest.skip(f"{path} not present in this install layout")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_skill_platform_count_matches_registered_channels():
    from agent_reach.channels import ALL_CHANNELS

    content = _read(SKILL_MD)
    matches = {int(n) for n in re.findall(r"(\d+)\s+platforms", content)}
    assert matches, "SKILL.md should state an 'N platforms' count"
    assert matches == {len(ALL_CHANNELS)}, (
        f"SKILL.md claims {matches} platforms but {len(ALL_CHANNELS)} channels are registered"
    )


def test_skill_twitter_section_uses_installed_binary():
    content = _read(SKILL_MD)
    assert "twitter search" in content, "SKILL.md must document the installed `twitter` CLI"
    # No code line should present `bird ` as the primary command — bird is only a fallback.
    offenders = [
        line for line in content.splitlines() if line.strip().startswith("bird ")
    ]
    assert not offenders, f"SKILL.md still shows `bird` as a primary command: {offenders}"


def test_install_guide_linkedin_uses_stdio_and_home_scope():
    content = _read(INSTALL_MD)
    assert "--command linkedin-scraper-mcp" in content, (
        "LinkedIn guide should configure mcporter to launch the scraper via stdio"
    )
    assert "--scope home" in content, (
        "LinkedIn guide should write the mcporter entry to the home config, "
        "not the project/repo config"
    )
