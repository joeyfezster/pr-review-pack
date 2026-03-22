"""Tests for scaffold helper functions in scaffold_review_pack_data.py.

Tests pure helper functions that don't require git/gh CLI access:
status computation, verdict (legacy), zone matching, health tagging,
code diff building, category zone mapping, and scenario building.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from scaffold_review_pack_data import (
    build_architecture,
    build_category_zone_map,
    build_code_diffs,
    build_scenarios,
    compute_status,
    compute_verdict,
    health_tag,
    match_file_to_zones,
)

_HEALTHY_AA = {"overallHealth": "healthy"}

# ── compute_verdict ───────────────────────────────────────────────────


class TestComputeVerdict:
    def test_ready_all_gates_passing_no_bad_grades(self):
        convergence = {
            "gates": [
                {"status": "passing"},
                {"status": "passing"},
            ],
            "overall": {"status": "passing"},
        }
        agentic_review = {
            "findings": [
                {"grade": "A"},
                {"grade": "B"},
                {"grade": "B+"},
            ],
        }
        result = compute_verdict(
            convergence,
            agentic_review,
            architecture_assessment=_HEALTHY_AA,
        )
        assert result["status"] == "ready"
        assert "READY" in result["text"]

    def test_blocked_failing_gate(self):
        convergence = {
            "gates": [
                {"status": "passing"},
                {"status": "failing"},
            ],
            "overall": {"status": "passing"},
        }
        agentic_review = {"findings": [{"grade": "A"}]}
        result = compute_verdict(convergence, agentic_review)
        assert result["status"] == "blocked"
        assert "BLOCKED" in result["text"]

    def test_blocked_overall_failing(self):
        convergence = {
            "gates": [{"status": "passing"}],
            "overall": {"status": "failing"},
        }
        agentic_review = {"findings": []}
        result = compute_verdict(convergence, agentic_review)
        assert result["status"] == "blocked"

    def test_blocked_f_grade(self):
        convergence = {
            "gates": [{"status": "passing"}],
            "overall": {"status": "passing"},
        }
        agentic_review = {
            "findings": [
                {"grade": "A"},
                {"grade": "F"},
            ],
        }
        result = compute_verdict(convergence, agentic_review)
        assert result["status"] == "blocked"
        assert "critical finding" in result["text"].lower()

    def test_review_c_grade_gates_passing(self):
        convergence = {
            "gates": [{"status": "passing"}],
            "overall": {"status": "passing"},
        }
        agentic_review = {
            "findings": [
                {"grade": "A"},
                {"grade": "C"},
            ],
        }
        result = compute_verdict(convergence, agentic_review)
        assert result["status"] == "review"
        assert "REVIEW" in result["text"]

    def test_ready_with_no_findings(self):
        convergence = {
            "gates": [{"status": "passing"}],
            "overall": {"status": "passing"},
        }
        agentic_review = {"findings": []}
        result = compute_verdict(
            convergence,
            agentic_review,
            architecture_assessment=_HEALTHY_AA,
        )
        assert result["status"] == "ready"

    def test_f_grade_overrides_c_grade(self):
        """F grade should produce blocked, not review, even with C grades."""
        convergence = {
            "gates": [{"status": "passing"}],
            "overall": {"status": "passing"},
        }
        agentic_review = {
            "findings": [
                {"grade": "C"},
                {"grade": "F"},
            ],
        }
        result = compute_verdict(convergence, agentic_review)
        assert result["status"] == "blocked"


# ── compute_status ───────────────────────────────────────────────────


class TestComputeStatus:
    """Tests for the new compute_status function with reasons list."""

    def _passing_convergence(self, num_gates=3):
        gates = [{"name": f"Gate {i}", "status": "passing"} for i in range(num_gates)]
        return {"gates": gates, "overall": {"status": "passing"}}

    def test_ready_all_clear(self):
        result = compute_status(
            self._passing_convergence(),
            {"findings": [{"grade": "A"}, {"grade": "B"}]},
            architecture_assessment=_HEALTHY_AA,
        )
        assert result["value"] == "ready"
        assert result["text"] == "READY"
        assert result["reasons"] == []

    def test_blocked_failing_gate_has_reason(self):
        convergence = {
            "gates": [
                {"name": "Gate 0", "status": "passing"},
                {"name": "Gate 1", "status": "failing"},
            ],
            "overall": {"status": "passing"},
        }
        result = compute_status(convergence, {"findings": []})
        assert result["value"] == "blocked"
        assert "Gate 1" in result["reasons"][0]

    def test_blocked_f_grade_has_reason(self):
        result = compute_status(
            self._passing_convergence(),
            {"findings": [{"grade": "F"}, {"grade": "A"}]},
        )
        assert result["value"] == "blocked"
        assert "critical" in result["reasons"][0].lower()

    def test_blocked_overall_failing_has_reason(self):
        """Overall convergence failing should block even if individual gates pass."""
        convergence = {
            "gates": [{"name": "Gate 0", "status": "passing"}],
            "overall": {"status": "failing"},
        }
        result = compute_status(convergence, {"findings": []})
        assert result["value"] == "blocked"
        assert any("convergence" in r.lower() for r in result["reasons"])

    def test_needs_review_c_grade(self):
        result = compute_status(
            self._passing_convergence(),
            {
                "findings": [
                    {"file": "src/a.py", "grade": "C"},
                    {"file": "src/b.py", "grade": "C"},
                    {"file": "src/c.py", "grade": "A"},
                ]
            },
        )
        assert result["value"] == "needs-review"
        assert result["text"] == "NEEDS REVIEW"
        assert "2 file(s)" in result["reasons"][0]

    def test_needs_review_c_grade_dedupes_same_file(self):
        """Multiple C-grade findings on the same file count as 1 file."""
        result = compute_status(
            self._passing_convergence(),
            {
                "findings": [
                    {"file": "src/a.py", "agent": "code-health", "grade": "C"},
                    {"file": "src/a.py", "agent": "security", "grade": "C"},
                    {"file": "src/a.py", "agent": "adversarial", "grade": "C"},
                    {"file": "src/b.py", "agent": "code-health", "grade": "A"},
                ]
            },
        )
        assert result["value"] == "needs-review"
        assert "1 file(s)" in result["reasons"][0]

    def test_needs_review_commit_gap(self):
        result = compute_status(
            self._passing_convergence(),
            {"findings": [{"grade": "A"}]},
            commit_gap=3,
        )
        assert result["value"] == "needs-review"
        assert "3 commit(s)" in result["reasons"][0]

    def test_needs_review_both_c_grade_and_commit_gap(self):
        result = compute_status(
            self._passing_convergence(),
            {"findings": [{"file": "src/a.py", "grade": "C"}]},
            commit_gap=2,
            architecture_assessment=_HEALTHY_AA,
        )
        assert result["value"] == "needs-review"
        assert len(result["reasons"]) == 2

    def test_blocked_overrides_needs_review(self):
        """F grade produces blocked even with commit gap."""
        result = compute_status(
            self._passing_convergence(),
            {"findings": [{"grade": "F"}]},
            commit_gap=5,
        )
        assert result["value"] == "blocked"

    def test_ready_no_findings(self):
        result = compute_status(
            self._passing_convergence(),
            {"findings": []},
            architecture_assessment=_HEALTHY_AA,
        )
        assert result["value"] == "ready"

    def test_needs_review_architecture_action_required(self):
        result = compute_status(
            self._passing_convergence(),
            {"findings": [{"grade": "A"}]},
            architecture_assessment={"overallHealth": "action-required"},
        )
        assert result["value"] == "needs-review"
        assert any("architecture" in r.lower() for r in result["reasons"])

    def test_ready_architecture_healthy(self):
        result = compute_status(
            self._passing_convergence(),
            {"findings": [{"grade": "A"}]},
            architecture_assessment={"overallHealth": "healthy"},
        )
        assert result["value"] == "ready"

    def test_ready_architecture_needs_attention_does_not_downgrade(self):
        """needs-attention is informational, not a status downgrade."""
        result = compute_status(
            self._passing_convergence(),
            {"findings": [{"grade": "A"}]},
            architecture_assessment={"overallHealth": "needs-attention"},
        )
        assert result["value"] == "ready"

    def test_needs_review_architecture_none(self):
        """Missing architecture assessment triggers needs-review."""
        result = compute_status(
            self._passing_convergence(),
            {"findings": [{"grade": "A"}]},
            architecture_assessment=None,
        )
        assert result["value"] == "needs-review"
        assert any("missing" in r.lower() for r in result["reasons"])


# ── build_code_diffs ──────────────────────────────────────────────────


class TestBuildCodeDiffs:
    def test_files_mapped_to_zones(self, sample_diff_data, sample_zone_registry):
        result = build_code_diffs(sample_diff_data, sample_zone_registry)
        assert len(result) == 2

        alpha_file = next(f for f in result if f["path"] == "src/alpha/core.py")
        assert "zone-alpha" in alpha_file["zones"]
        assert alpha_file["additions"] == 30
        assert alpha_file["deletions"] == 5
        assert alpha_file["status"] == "modified"

        infra_file = next(f for f in result if f["path"] == "infra/deploy.sh")
        assert "zone-gamma" in infra_file["zones"]
        assert infra_file["additions"] == 12
        assert infra_file["deletions"] == 2

    def test_empty_diff_data(self, sample_zone_registry):
        result = build_code_diffs({"files": {}}, sample_zone_registry)
        assert result == []

    def test_file_with_no_zone_match(self, sample_zone_registry):
        diff_data = {
            "files": {
                "README.md": {
                    "additions": 1,
                    "deletions": 0,
                    "status": "modified",
                },
            },
        }
        result = build_code_diffs(diff_data, sample_zone_registry)
        assert len(result) == 1
        assert result[0]["zones"] == []


# ── match_file_to_zones ──────────────────────────────────────────────


class TestMatchFileToZones:
    def test_matches_by_fnmatch_pattern(self, sample_zone_registry):
        result = match_file_to_zones("src/alpha/core.py", sample_zone_registry)
        assert "zone-alpha" in result

    def test_matches_test_file(self, sample_zone_registry):
        result = match_file_to_zones("tests/test_alpha_unit.py", sample_zone_registry)
        assert "zone-alpha" in result

    def test_no_match(self, sample_zone_registry):
        result = match_file_to_zones("docs/readme.md", sample_zone_registry)
        assert result == []

    def test_multiple_zone_match(self):
        """A file can match multiple zones if patterns overlap."""
        registry = {
            "zone-a": {"paths": ["src/**"]},
            "zone-b": {"paths": ["src/shared/**"]},
        }
        result = match_file_to_zones("src/shared/utils.py", registry)
        assert "zone-a" in result
        assert "zone-b" in result

    def test_exact_filename_pattern(self, sample_zone_registry):
        result = match_file_to_zones("scripts/build.sh", sample_zone_registry)
        assert "zone-gamma" in result


# ── health_tag ────────────────────────────────────────────────────────


class TestHealthTag:
    def test_normal_under_60s(self):
        assert health_tag(0) == "normal"
        assert health_tag(30) == "normal"
        assert health_tag(59) == "normal"

    def test_acceptable_60_to_300(self):
        assert health_tag(60) == "acceptable"
        assert health_tag(180) == "acceptable"
        assert health_tag(299) == "acceptable"

    def test_watch_300_to_600(self):
        assert health_tag(300) == "watch"
        assert health_tag(450) == "watch"
        assert health_tag(599) == "watch"

    def test_refactor_600_and_above(self):
        assert health_tag(600) == "refactor"
        assert health_tag(1200) == "refactor"
        assert health_tag(3600) == "refactor"

    def test_boundary_values(self):
        """Exact boundary: 59.9 is normal, 60 is acceptable, etc."""
        assert health_tag(59.9) == "normal"
        assert health_tag(60.0) == "acceptable"
        assert health_tag(299.9) == "acceptable"
        assert health_tag(300.0) == "watch"
        assert health_tag(599.9) == "watch"
        assert health_tag(600.0) == "refactor"


# ── build_category_zone_map ───────────────────────────────────────────


class TestBuildCategoryZoneMap:
    def test_derives_mapping_from_zone_registry(self, sample_zone_registry):
        result = build_category_zone_map(sample_zone_registry)
        # Zone IDs map to themselves
        assert result["zone-alpha"] == "zone-alpha"
        assert result["zone-beta"] == "zone-beta"
        assert result["zone-gamma"] == "zone-gamma"

    def test_label_mapping(self, sample_zone_registry):
        result = build_category_zone_map(sample_zone_registry)
        # Lowercased labels also map to zone IDs
        assert result["zone alpha"] == "zone-alpha"
        assert result["zone beta"] == "zone-beta"
        assert result["zone gamma"] == "zone-gamma"

    def test_empty_registry(self):
        result = build_category_zone_map({})
        assert result == {}


# ── build_scenarios ───────────────────────────────────────────────────


class TestBuildScenarios:
    def test_with_category_map(self, sample_zone_registry):
        cat_map = build_category_zone_map(sample_zone_registry)
        scenario_data = {
            "passed": 1,
            "total": 2,
            "results": [
                {
                    "name": "Alpha test",
                    "category": "zone-alpha",
                    "passed": True,
                    "exit_code": 0,
                    "duration_seconds": 1.5,
                    "stdout": "OK",
                    "stderr": "",
                },
                {
                    "name": "Beta test",
                    "category": "zone-beta",
                    "passed": False,
                    "exit_code": 1,
                    "duration_seconds": 0.8,
                    "stdout": "",
                    "stderr": "AssertionError",
                    "error_summary": "Assertion failed",
                },
            ],
        }
        result = build_scenarios(scenario_data, cat_map)
        assert len(result) == 2

        alpha = result[0]
        assert alpha["name"] == "Alpha test"
        assert alpha["status"] == "pass"
        assert alpha["zone"] == "zone-alpha"
        assert alpha["category"] == "zone-alpha"

        beta = result[1]
        assert beta["name"] == "Beta test"
        assert beta["status"] == "fail"
        assert beta["zone"] == "zone-beta"

    def test_no_map_falls_back_to_empty_zone(self):
        scenario_data = {
            "passed": 1,
            "total": 1,
            "results": [
                {
                    "name": "Standalone test",
                    "category": "unknown-category",
                    "passed": True,
                    "exit_code": 0,
                    "duration_seconds": 0.5,
                    "stdout": "Done",
                    "stderr": "",
                },
            ],
        }
        result = build_scenarios(scenario_data, None)
        assert len(result) == 1
        assert result[0]["zone"] == ""

    def test_none_scenario_data(self):
        result = build_scenarios(None)
        assert result == []

    def test_empty_results(self):
        result = build_scenarios({"passed": 0, "total": 0, "results": []})
        assert result == []

    def test_detail_structure(self):
        scenario_data = {
            "passed": 1,
            "total": 1,
            "results": [
                {
                    "name": "Detail test",
                    "category": "integration",
                    "passed": True,
                    "exit_code": 0,
                    "duration_seconds": 2.3,
                    "stdout": "Success output",
                    "stderr": "",
                },
            ],
        }
        result = build_scenarios(scenario_data, {})
        detail = result[0]["detail"]
        assert detail["what"] == "Detail test"
        assert "Exit code 0" in detail["how"]
        assert "2.3s" in detail["how"]
        assert detail["result"] == "Success output"


# ── build_architecture (unzoned file tracking) ──────────────────────


class TestBuildArchitectureUnzoned:
    def test_unzoned_files_tracked(self, sample_zone_registry):
        diff_data = {
            "files": {
                "src/alpha/core.py": {"additions": 10},
                "README.md": {"additions": 5},
            },
        }
        result = build_architecture(sample_zone_registry, diff_data)
        assert "README.md" in result["unzonedFiles"]
        assert "src/alpha/core.py" not in result["unzonedFiles"]

    def test_no_unzoned_when_all_mapped(self, sample_zone_registry):
        diff_data = {
            "files": {"src/alpha/core.py": {"additions": 10}},
        }
        result = build_architecture(sample_zone_registry, diff_data)
        assert result["unzonedFiles"] == []

    def test_empty_diff(self, sample_zone_registry):
        result = build_architecture(sample_zone_registry, {"files": {}})
        assert result["unzonedFiles"] == []

    def test_all_unzoned(self):
        registry = {"zone-x": {"paths": ["nonexistent/**"]}}
        diff_data = {
            "files": {
                "README.md": {"additions": 1},
                "CHANGELOG.md": {"additions": 2},
            },
        }
        result = build_architecture(registry, diff_data)
        assert len(result["unzonedFiles"]) == 2

    def test_file_counts_plus_unzoned_covers_all(self, sample_zone_registry):
        diff_data = {
            "files": {
                "src/alpha/core.py": {"additions": 10},
                "infra/deploy.sh": {"additions": 5},
                "README.md": {"additions": 1},
            },
        }
        result = build_architecture(sample_zone_registry, diff_data)
        zone_sum = sum(z["fileCount"] for z in result["zones"])
        total_coverage = zone_sum + len(result["unzonedFiles"])
        # Every file is either in a zone or unzoned — some files
        # may appear in multiple zones, so coverage >= file count
        assert total_coverage >= len(diff_data["files"])


# ── compute_verdict with no-scenario convergence ─────────────────────


class TestComputeVerdictNoScenarios:
    """Verify verdict works when Gate 3 (Scenarios) is absent."""

    def test_ready_with_three_gates_no_scenarios(self):
        """When there are no scenarios, 3 passing gates → ready."""
        convergence = {
            "gates": [
                {"name": "Gate 0", "status": "passing"},
                {"name": "Gate 1", "status": "passing"},
                {"name": "Gate 2", "status": "passing"},
            ],
            "overall": {"status": "passing"},
        }
        agentic_review = {"findings": [{"grade": "A"}]}
        result = compute_verdict(
            convergence,
            agentic_review,
            architecture_assessment=_HEALTHY_AA,
        )
        assert result["status"] == "ready"

    def test_blocked_with_three_gates_one_failing(self):
        """Gate failure with no scenarios still blocks."""
        convergence = {
            "gates": [
                {"name": "Gate 0", "status": "passing"},
                {"name": "Gate 1", "status": "failing"},
                {"name": "Gate 2", "status": "passing"},
            ],
            "overall": {"status": "failing"},
        }
        agentic_review = {"findings": []}
        result = compute_verdict(convergence, agentic_review)
        assert result["status"] == "blocked"

    def test_ready_with_four_gates_scenarios_passing(self):
        """When scenarios exist and pass, 4 gates → ready."""
        convergence = {
            "gates": [
                {"name": "Gate 0", "status": "passing"},
                {"name": "Gate 1", "status": "passing"},
                {"name": "Gate 2", "status": "passing"},
                {"name": "Gate 3 — Scenarios", "status": "passing"},
            ],
            "overall": {"status": "passing"},
        }
        agentic_review = {"findings": [{"grade": "A"}, {"grade": "B"}]}
        result = compute_verdict(
            convergence,
            agentic_review,
            architecture_assessment=_HEALTHY_AA,
        )
        assert result["status"] == "ready"

    def test_blocked_with_four_gates_scenarios_failing(self):
        """When scenarios exist and fail, Gate 3 blocks."""
        convergence = {
            "gates": [
                {"name": "Gate 0", "status": "passing"},
                {"name": "Gate 1", "status": "passing"},
                {"name": "Gate 2", "status": "passing"},
                {"name": "Gate 3 — Scenarios", "status": "failing"},
            ],
            "overall": {"status": "passing"},
        }
        agentic_review = {"findings": []}
        result = compute_verdict(convergence, agentic_review)
        assert result["status"] == "blocked"
