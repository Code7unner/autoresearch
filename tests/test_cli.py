# -*- coding: utf-8 -*-
"""Tests for autoresearch CLI."""

import pytest
import requests
from unittest.mock import patch
import autoresearch.cli as cli
from autoresearch.cli import main


class TestCLI:
    def test_version(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["autoresearch", "version"]):
                main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "autoresearch v" in captured.out

    def test_no_command_shows_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["autoresearch"]):
                main()
        assert exc_info.value.code == 0

    def test_doctor_runs(self, capsys):
        with patch("sys.argv", ["autoresearch", "doctor"]):
            main()
        captured = capsys.readouterr()
        assert "autoresearch" in captured.out
        assert "✅" in captured.out

    def test_parse_twitter_cookie_input_separate_values(self):
        auth_token, ct0 = cli._parse_twitter_cookie_input("token123 ct0abc")
        assert auth_token == "token123"
        assert ct0 == "ct0abc"

    def test_parse_twitter_cookie_input_cookie_header(self):
        auth_token, ct0 = cli._parse_twitter_cookie_input(
            "auth_token=token123; ct0=ct0abc; other=value"
        )
        assert auth_token == "token123"
        assert ct0 == "ct0abc"


class TestCheckUpdateRetry:
    def test_retry_timeout_classification(self):
        sleeps = []

        def fake_sleep(seconds):
            sleeps.append(seconds)

        with patch("requests.get", side_effect=requests.exceptions.Timeout("timed out")):
            resp, err, attempts = cli._github_get_with_retry(
                "https://api.github.com/test",
                timeout=1,
                retries=3,
                sleeper=fake_sleep,
            )

        assert resp is None
        assert err == "timeout"
        assert attempts == 3
        assert sleeps == [1, 2]

    def test_retry_dns_classification(self):
        error = requests.exceptions.ConnectionError("getaddrinfo failed for api.github.com")
        with patch("requests.get", side_effect=error):
            resp, err, attempts = cli._github_get_with_retry(
                "https://api.github.com/test",
                retries=1,
                sleeper=lambda _x: None,
            )
        assert resp is None
        assert err == "dns"
        assert attempts == 1

    def test_retry_rate_limit_then_success(self):
        sleeps = []

        class R:
            def __init__(self, code, payload=None, headers=None):
                self.status_code = code
                self._payload = payload or {}
                self.headers = headers or {}

            def json(self):
                return self._payload

        sequence = [
            R(429, headers={"Retry-After": "3"}),
            R(200, payload={"tag_name": "v1.0.1"}),
        ]

        with patch("requests.get", side_effect=sequence):
            resp, err, attempts = cli._github_get_with_retry(
                "https://api.github.com/test",
                retries=3,
                sleeper=lambda s: sleeps.append(s),
            )

        assert err is None
        assert resp is not None
        assert resp.status_code == 200
        assert attempts == 2
        assert sleeps == [3.0]

    def test_classify_rate_limit_from_403(self):
        class R:
            status_code = 403
            headers = {"X-RateLimit-Remaining": "0"}

            @staticmethod
            def json():
                return {"message": "API rate limit exceeded"}

        assert cli._classify_github_response_error(R()) == "rate_limit"

    def test_check_update_reports_classified_error(self, capsys):
        with patch("autoresearch.cli._github_get_with_retry", return_value=(None, "timeout", 3)):
            result = cli._cmd_check_update()

        captured = capsys.readouterr()
        assert result == "error"
        assert "Network timeout" in captured.out
        assert "retried 3 times" in captured.out


class TestFormatCommand:
    def _run_format(self, platform, stdin_text, capsys):
        import io
        import json as _json

        with patch("sys.stdin", io.StringIO(stdin_text)):
            with patch("sys.argv", ["autoresearch", "format", platform]):
                main()
        out = capsys.readouterr().out
        return _json.loads(out)

    def test_format_hn_item_returns_cleaned_story(self, capsys):
        import json as _json

        payload = _json.dumps(
            {
                "type": "story",
                "title": "HN Story",
                "url": "https://example.com",
                "author": "pg",
                "points": 123,
                "created_at": "2026-01-01T00:00:00Z",
                "children": [
                    {
                        "type": "comment",
                        "author": "u1",
                        "text": "<p>hi &amp; bye</p>",
                        "created_at": "2026-01-01T01:00:00Z",
                        "children": [],
                    }
                ],
            }
        )
        result = self._run_format("hn", payload, capsys)
        assert result["title"] == "HN Story"
        assert result["author"] == "pg"
        assert result["comments"][0]["text"] == "hi & bye"

    def test_format_hn_search_returns_flat_list(self, capsys):
        import json as _json

        payload = _json.dumps(
            {
                "hits": [
                    {
                        "objectID": "1",
                        "title": "T1",
                        "url": "https://e.com/1",
                        "author": "a",
                        "points": 9,
                        "num_comments": 3,
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                ]
            }
        )
        result = self._run_format("hn", payload, capsys)
        assert isinstance(result, list)
        assert result[0]["title"] == "T1"
        assert result[0]["objectID"] == "1"
