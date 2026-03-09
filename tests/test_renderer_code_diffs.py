"""Tests for render_code_diffs_list() in render_review_pack.py.

Exercises the Code Diffs file list renderer with various data shapes:
file paths, +/- stats, status badges, zone tags, empty input, and
files with no zones.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from render_review_pack import render_code_diffs_list

# ── File paths rendered ────────────────────────────────────────────


class TestCodeDiffsFilePaths:

    def test_file_paths_appear_in_output(self, sample_review_pack_data):
        result = render_code_diffs_list(sample_review_pack_data)
        assert "src/alpha/core.py" in result
        assert "infra/deploy.sh" in result

    def test_file_path_in_data_attribute(self, sample_review_pack_data):
        result = render_code_diffs_list(sample_review_pack_data)
        assert 'data-path="src/alpha/core.py"' in result
        assert 'data-path="infra/deploy.sh"' in result

    def test_file_path_in_span(self, sample_review_pack_data):
        result = render_code_diffs_list(sample_review_pack_data)
        assert '<span class="cd-file-path">src/alpha/core.py</span>' in result
        assert '<span class="cd-file-path">infra/deploy.sh</span>' in result


# ── Addition / deletion stats ──────────────────────────────────────


class TestCodeDiffsStats:

    def test_additions_rendered(self, sample_review_pack_data):
        result = render_code_diffs_list(sample_review_pack_data)
        assert '<span class="cd-add">+30</span>' in result
        assert '<span class="cd-add">+12</span>' in result

    def test_deletions_rendered(self, sample_review_pack_data):
        result = render_code_diffs_list(sample_review_pack_data)
        assert '<span class="cd-del">&minus;5</span>' in result
        assert '<span class="cd-del">&minus;2</span>' in result

    def test_zero_stats(self):
        data = {
            "codeDiffs": [
                {
                    "path": "empty_changes.py",
                    "additions": 0,
                    "deletions": 0,
                    "status": "modified",
                    "zones": [],
                },
            ],
        }
        result = render_code_diffs_list(data)
        assert '<span class="cd-add">+0</span>' in result
        assert '<span class="cd-del">&minus;0</span>' in result


# ── Status badges ──────────────────────────────────────────────────


class TestCodeDiffsStatusBadges:

    def test_modified_status(self, sample_review_pack_data):
        result = render_code_diffs_list(sample_review_pack_data)
        assert '<span class="cd-file-status modified">modified</span>' in result

    def test_added_status(self):
        data = {
            "codeDiffs": [
                {
                    "path": "new_file.py",
                    "additions": 10,
                    "deletions": 0,
                    "status": "added",
                    "zones": ["zone-alpha"],
                },
            ],
        }
        result = render_code_diffs_list(data)
        assert '<span class="cd-file-status added">added</span>' in result

    def test_deleted_status(self):
        data = {
            "codeDiffs": [
                {
                    "path": "old_file.py",
                    "additions": 0,
                    "deletions": 50,
                    "status": "deleted",
                    "zones": ["zone-beta"],
                },
            ],
        }
        result = render_code_diffs_list(data)
        assert '<span class="cd-file-status deleted">deleted</span>' in result

    def test_renamed_status(self):
        data = {
            "codeDiffs": [
                {
                    "path": "renamed_file.py",
                    "additions": 0,
                    "deletions": 0,
                    "status": "renamed",
                    "zones": [],
                },
            ],
        }
        result = render_code_diffs_list(data)
        assert '<span class="cd-file-status renamed">renamed</span>' in result


# ── Zone tags ──────────────────────────────────────────────────────


class TestCodeDiffsZoneTags:

    def test_zone_tags_rendered(self, sample_review_pack_data):
        result = render_code_diffs_list(sample_review_pack_data)
        assert "zone-alpha" in result
        assert "zone-gamma" in result

    def test_zone_tag_class_present(self, sample_review_pack_data):
        result = render_code_diffs_list(sample_review_pack_data)
        assert 'class="zone-tag' in result

    def test_data_zones_attribute(self, sample_review_pack_data):
        result = render_code_diffs_list(sample_review_pack_data)
        assert 'data-zones="zone-alpha"' in result
        assert 'data-zones="zone-gamma"' in result

    def test_multiple_zones_on_single_file(self):
        data = {
            "codeDiffs": [
                {
                    "path": "shared_module.py",
                    "additions": 5,
                    "deletions": 3,
                    "status": "modified",
                    "zones": ["zone-alpha", "zone-beta"],
                },
            ],
        }
        result = render_code_diffs_list(data)
        assert 'data-zones="zone-alpha zone-beta"' in result
        assert ">zone-alpha</span>" in result
        assert ">zone-beta</span>" in result


# ── Empty codeDiffs ────────────────────────────────────────────────


class TestCodeDiffsEmpty:

    def test_empty_list_returns_no_files_message(self):
        data = {"codeDiffs": []}
        result = render_code_diffs_list(data)
        assert "No files changed" in result

    def test_missing_key_returns_no_files_message(self):
        data = {}
        result = render_code_diffs_list(data)
        assert "No files changed" in result


# ── Files with no zones ───────────────────────────────────────────


class TestCodeDiffsNoZones:

    def test_file_with_empty_zones_renders(self):
        data = {
            "codeDiffs": [
                {
                    "path": "unzoned_file.py",
                    "additions": 1,
                    "deletions": 0,
                    "status": "added",
                    "zones": [],
                },
            ],
        }
        result = render_code_diffs_list(data)
        assert "unzoned_file.py" in result
        assert 'data-zones=""' in result
        # No zone-tag spans should appear
        assert "zone-tag" not in result

    def test_file_with_missing_zones_key(self):
        data = {
            "codeDiffs": [
                {
                    "path": "no_zones_key.py",
                    "additions": 2,
                    "deletions": 1,
                    "status": "modified",
                },
            ],
        }
        result = render_code_diffs_list(data)
        assert "no_zones_key.py" in result
        assert 'data-zones=""' in result
