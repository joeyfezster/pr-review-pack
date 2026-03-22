"""Tests for review_pack_cli.py pure functions.

Tests the data extraction and status reporting functions without
requiring git/gh CLI or network access.

TODO: cmd_refresh and cmd_merge are subprocess-heavy and tightly coupled
to git/gh — add integration tests when a mock harness is available.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from review_pack_cli import cmd_status, extract_data_from_html, get_auth_token  # noqa: E402, I001


# ── extract_data_from_html ───────────────────────────────────────────


class TestExtractDataFromHtml:
    def test_extracts_valid_json(self, tmp_path):
        data = {"header": {"prNumber": 42}, "status": {"value": "ready"}}
        html = f"""<html>
<script>
const DATA = {json.dumps(data)};
</script>
</html>"""
        html_file = tmp_path / "test.html"
        html_file.write_text(html)
        result = extract_data_from_html(str(html_file))
        assert result is not None
        assert result["header"]["prNumber"] == 42

    def test_returns_none_for_no_data(self, tmp_path):
        html_file = tmp_path / "test.html"
        html_file.write_text("<html><body>No data here</body></html>")
        result = extract_data_from_html(str(html_file))
        assert result is None

    def test_returns_none_for_invalid_json(self, tmp_path):
        html = """<html><script>
const DATA = {invalid json here};
</script></html>"""
        html_file = tmp_path / "test.html"
        html_file.write_text(html)
        result = extract_data_from_html(str(html_file))
        assert result is None

    def test_extracts_nested_data(self, tmp_path):
        data = {
            "header": {"prNumber": 10},
            "status": {
                "value": "needs-review",
                "text": "NEEDS REVIEW",
                "reasons": ["C-grade findings in 2 file(s)"],
            },
            "reviewedCommitSHA": "abc123",
            "headCommitSHA": "def456",
            "commitGap": 3,
            "packMode": "live",
        }
        html = f"""<html>
<script>
const DATA = {json.dumps(data)};
</script>
</html>"""
        html_file = tmp_path / "test.html"
        html_file.write_text(html)
        result = extract_data_from_html(str(html_file))
        assert result["commitGap"] == 3
        assert result["packMode"] == "live"
        assert result["status"]["reasons"] == ["C-grade findings in 2 file(s)"]


# ── cmd_status (output format) ───────────────────────────────────────


class TestCmdStatusOutput:
    """Test status command output via the extract + format logic."""

    def _make_html(self, tmp_path, data):
        html = f"""<html><script>
const DATA = {json.dumps(data)};
</script></html>"""
        p = tmp_path / "pr99_review_pack.html"
        p.write_text(html)
        return str(p)

    def test_status_extracts_pr_number(self, tmp_path):
        data = {
            "header": {"prNumber": 99},
            "status": {"value": "ready", "text": "READY", "reasons": []},
            "reviewedCommitSHA": "aaa",
            "headCommitSHA": "aaa",
            "commitGap": 0,
            "lastRefreshed": "2026-03-09T12:00:00Z",
            "packMode": "live",
            "agenticReview": {"findings": []},
            "convergence": {"gates": [{"status": "passing"}]},
        }
        result = extract_data_from_html(self._make_html(tmp_path, data))
        assert result["header"]["prNumber"] == 99

    def test_status_detects_commit_gap(self, tmp_path):
        data = {
            "header": {"prNumber": 5},
            "status": {"value": "needs-review", "text": "NEEDS REVIEW", "reasons": ["gap"]},
            "reviewedCommitSHA": "abc123",
            "headCommitSHA": "def456",
            "commitGap": 2,
            "lastRefreshed": "2026-03-09T12:00:00Z",
            "packMode": "live",
            "agenticReview": {"findings": [{"grade": "C"}]},
            "convergence": {"gates": []},
        }
        result = extract_data_from_html(self._make_html(tmp_path, data))
        assert result["commitGap"] == 2
        assert result["status"]["value"] == "needs-review"


# ── get_auth_token ──────────────────────────────────────────────────


class TestGetAuthToken:
    """Test auth token resolution priority and error handling."""

    def test_returns_env_var_when_set(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "gh_test_token_123"}):
            assert get_auth_token() == "gh_test_token_123"

    def test_env_var_takes_priority_over_gh_cli(self):
        """GITHUB_TOKEN env var has higher priority than gh auth token."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "env_token"}):
            # Even if gh auth would succeed, env var wins
            assert get_auth_token() == "env_token"

    def test_falls_back_to_gh_cli(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("subprocess.check_output", return_value="gh_cli_token\n"),
        ):
            # Remove GITHUB_TOKEN if present
            os.environ.pop("GITHUB_TOKEN", None)
            assert get_auth_token() == "gh_cli_token"

    def test_exits_when_no_auth_available(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "subprocess.check_output",
                side_effect=FileNotFoundError("gh not found"),
            ),
        ):
            os.environ.pop("GITHUB_TOKEN", None)
            with pytest.raises(SystemExit):
                get_auth_token()

    def test_strips_whitespace_from_env_token(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "  token_with_spaces  "}):
            assert get_auth_token() == "token_with_spaces"

    def test_ignores_empty_env_var(self):
        """Empty GITHUB_TOKEN falls through to gh CLI."""
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "  "}),
            patch("subprocess.check_output", return_value="gh_token\n"),
        ):
            assert get_auth_token() == "gh_token"


# ── cmd_status (full output) ────────────────────────────────────────


class TestCmdStatusFullOutput:
    """Test cmd_status prints expected output to stdout."""

    def _make_html(self, tmp_path, data):
        html = f"""<html><script>
const DATA = {json.dumps(data)};
</script></html>"""
        p = tmp_path / "pr99_review_pack.html"
        p.write_text(html)
        return str(p)

    def test_cmd_status_prints_pr_number(self, tmp_path, capsys):
        data = {
            "header": {"prNumber": 42},
            "status": {"value": "ready", "text": "READY", "reasons": []},
            "reviewedCommitSHA": "abc1234",
            "headCommitSHA": "abc1234",
            "commitGap": 0,
            "lastRefreshed": "2026-03-09T12:00:00Z",
            "packMode": "live",
            "agenticReview": {"findings": []},
            "convergence": {"gates": [{"status": "passing"}]},
        }
        html_path = self._make_html(tmp_path, data)
        args = argparse.Namespace(html_path=html_path)
        cmd_status(args)
        captured = capsys.readouterr()
        assert "PR #42" in captured.out
        assert "READY" in captured.out

    def test_cmd_status_shows_commit_gap(self, tmp_path, capsys):
        data = {
            "header": {"prNumber": 7},
            "status": {"value": "needs-review", "text": "NEEDS REVIEW", "reasons": ["gap"]},
            "reviewedCommitSHA": "aaa1111",
            "headCommitSHA": "bbb2222",
            "commitGap": 5,
            "lastRefreshed": "2026-03-09T12:00:00Z",
            "packMode": "live",
            "agenticReview": {"findings": [{"grade": "C"}]},
            "convergence": {"gates": []},
        }
        html_path = self._make_html(tmp_path, data)
        args = argparse.Namespace(html_path=html_path)
        cmd_status(args)
        captured = capsys.readouterr()
        assert "5 commit(s) not analyzed" in captured.out

    def test_cmd_status_exits_on_missing_file(self, tmp_path):
        args = argparse.Namespace(html_path=str(tmp_path / "nonexistent.html"))
        with pytest.raises(SystemExit):
            cmd_status(args)

    def test_cmd_status_exits_on_bad_data(self, tmp_path):
        p = tmp_path / "bad.html"
        p.write_text("<html>No DATA here</html>")
        args = argparse.Namespace(html_path=str(p))
        with pytest.raises(SystemExit):
            cmd_status(args)
