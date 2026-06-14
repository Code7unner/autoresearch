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

import autoresearch

_PKG_DIR = os.path.dirname(autoresearch.__file__)
_REPO_ROOT = os.path.dirname(_PKG_DIR)
SKILL_MD = os.path.join(_PKG_DIR, "skill", "SKILL.md")
INSTALL_MD = os.path.join(_REPO_ROOT, "docs", "install.md")


def _read(path):
    if not os.path.exists(path):
        pytest.skip(f"{path} not present in this install layout")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_skill_platform_count_matches_registered_channels():
    from autoresearch.channels import ALL_CHANNELS

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


PYPROJECT = os.path.join(_REPO_ROOT, "pyproject.toml")
TEST_CLI = os.path.join(_REPO_ROOT, "tests", "test_cli.py")


def test_version_is_consistent_across_three_places():
    """CLAUDE.md mandates the version match in pyproject.toml, the package
    __init__, and tests/test_cli.py. This guards that rule."""
    import autoresearch

    pyproject = _read(PYPROJECT)
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert m, "pyproject.toml should declare a version"
    pyproject_version = m.group(1)

    assert autoresearch.__version__ == pyproject_version, (
        f"__init__ version {autoresearch.__version__!r} != "
        f"pyproject {pyproject_version!r}"
    )

    cli_tests = _read(TEST_CLI)
    assert f"v{pyproject_version}" in cli_tests, (
        f"tests/test_cli.py should reference v{pyproject_version} "
        "(the check-update 'latest' tag) so it tracks the current version"
    )
