# -*- coding: utf-8 -*-
"""Channels without an auto-installer (linkedin, douyin) must be reported
honestly during `agent-reach install`, instead of being silently skipped and
leaving the user thinking the tool was installed.
"""

import agent_reach.cli as cli


def test_report_manual_channels_explains_linkedin(capsys):
    cli._report_manual_channels({"linkedin"})
    out = capsys.readouterr().out.lower()
    assert "linkedin" in out
    # Tells the user it is NOT auto-installed and how to set it up.
    assert "manual" in out or "no auto-install" in out
    assert "linkedin-scraper-mcp" in out
    assert "mcporter" in out


def test_report_manual_channels_silent_for_auto_installed_channel(capsys):
    # twitter has a real installer, so it must not appear in manual guidance.
    cli._report_manual_channels({"twitter"})
    assert capsys.readouterr().out.strip() == ""


def test_report_manual_channels_silent_for_cookie_only_channel(capsys):
    # xueqiu is cookie-only (handled by the cookie import step), not MCP setup.
    cli._report_manual_channels({"xueqiu"})
    assert capsys.readouterr().out.strip() == ""
