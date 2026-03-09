"""Tests for review_pack_cli.py pure functions.

Tests the data extraction and status reporting functions without
requiring git/gh CLI or network access.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from review_pack_cli import extract_data_from_html  # noqa: E402, I001


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
