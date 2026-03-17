"""Tests for assemble_review_pack.py validation and transform logic."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from assemble_review_pack import (
    ValidationReport,
    parse_agent_from_filename,
    read_and_validate_jsonl,
    transform_concept_to_finding,
    transform_concepts_to_review,
    transform_file_outcomes_to_coverage,
    transform_semantic_outputs,
    validate_concept_backing,
    validate_file_coverage,
    verify_findings,
)
from models import (
    FileReviewOutcome,
    Grade,
    ReviewConcept,
    SemanticOutput,
)


# ---------------------------------------------------------------------------
# Filename parsing
# ---------------------------------------------------------------------------


class TestFilenameParser:
    def test_valid_filename(self):
        assert parse_agent_from_filename("pr5-code-health-abc12345-def67890.jsonl") == "code-health"

    def test_synthesis_filename(self):
        assert parse_agent_from_filename("pr5-synthesis-abc12345-def67890.jsonl") == "synthesis"

    def test_architecture_filename(self):
        assert parse_agent_from_filename("pr5-architecture-abc12345-def67890.jsonl") == "architecture"

    def test_invalid_filename(self):
        assert parse_agent_from_filename("random_file.jsonl") is None

    def test_no_extension(self):
        assert parse_agent_from_filename("pr5-code-health-abc12345-def67890") is None

    def test_short_sha(self):
        """SHA must be exactly 8 hex chars."""
        assert parse_agent_from_filename("pr5-code-health-abc-def.jsonl") is None


# ---------------------------------------------------------------------------
# Validation report
# ---------------------------------------------------------------------------


class TestValidationReport:
    def test_empty_report(self):
        r = ValidationReport()
        assert not r.has_errors
        assert "No validation errors" in r.summary()

    def test_error_report(self):
        r = ValidationReport()
        r.add_error("test.jsonl", 5, "Bad JSON")
        assert r.has_errors
        assert "Bad JSON" in r.summary()

    def test_warning_report(self):
        r = ValidationReport()
        r.add_warning("test.jsonl", "File not in diff")
        assert not r.has_errors
        assert "File not in diff" in r.summary()


# ---------------------------------------------------------------------------
# Transform: ReviewConcept → AgenticFinding
# ---------------------------------------------------------------------------


class TestTransformConcept:
    def _make_concept(self, **kwargs) -> ReviewConcept:
        defaults = {
            "concept_id": "code-health-1",
            "title": "Test finding",
            "grade": "B",
            "category": "code-health",
            "summary": "Summary",
            "detail_html": "<p>Detail</p>",
            "locations": [{"file": "src/main.py", "zones": ["zone-alpha"]}],
        }
        defaults.update(kwargs)
        return ReviewConcept.model_validate(defaults)

    def test_basic_transform(self):
        rc = self._make_concept()
        finding = transform_concept_to_finding(rc, "code-health")
        assert finding["file"] == "src/main.py"
        assert finding["grade"] == "B"
        assert finding["zones"] == "zone-alpha"
        assert finding["agent"] == "code-health"
        assert finding["notable"] == "Test finding"
        assert finding["detail"] == "<p>Detail</p>"

    def test_grade_sort_order(self):
        for grade_val, expected_order in [("F", 0), ("C", 0), ("B", 1), ("B+", 2), ("A", 3)]:
            rc = self._make_concept(grade=grade_val)
            finding = transform_concept_to_finding(rc, "test")
            assert finding["gradeSortOrder"] == expected_order

    def test_multi_zone_locations(self):
        rc = self._make_concept(locations=[
            {"file": "src/main.py", "zones": ["zone-alpha", "zone-beta"]},
            {"file": "src/other.py", "zones": ["zone-gamma"]},
        ])
        finding = transform_concept_to_finding(rc, "test")
        assert "zone-alpha" in finding["zones"]
        assert "zone-beta" in finding["zones"]
        assert "zone-gamma" in finding["zones"]

    def test_zones_deduplicated(self):
        rc = self._make_concept(locations=[
            {"file": "src/a.py", "zones": ["zone-alpha"]},
            {"file": "src/b.py", "zones": ["zone-alpha"]},
        ])
        finding = transform_concept_to_finding(rc, "test")
        assert finding["zones"] == "zone-alpha"  # not "zone-alpha zone-alpha"


class TestTransformConceptsToReview:
    def test_overall_grade_worst_finding(self):
        concepts = {
            "code-health": [
                ReviewConcept.model_validate({
                    "concept_id": "ch-1", "title": "Good", "grade": "A",
                    "category": "code-health", "summary": "x", "detail_html": "x",
                    "locations": [{"file": "a.py", "zones": []}],
                }),
                ReviewConcept.model_validate({
                    "concept_id": "ch-2", "title": "Bad", "grade": "C",
                    "category": "code-health", "summary": "x", "detail_html": "x",
                    "locations": [{"file": "b.py", "zones": []}],
                }),
            ],
        }
        review = transform_concepts_to_review(concepts)
        assert review["overallGrade"] == "C"
        assert review["reviewMethod"] == "agent-teams"

    def test_overall_grade_f_not_suppressed_by_c(self):
        """F and C both have gradeSortOrder=0; overall grade must be F, not C."""
        concepts = {
            "adversarial": [
                ReviewConcept.model_validate({
                    "concept_id": "adv-1", "title": "Critical", "grade": "F",
                    "category": "adversarial", "summary": "x", "detail_html": "x",
                    "locations": [{"file": "a.py", "zones": []}],
                }),
            ],
            "code-health": [
                ReviewConcept.model_validate({
                    "concept_id": "ch-1", "title": "Issue", "grade": "C",
                    "category": "code-health", "summary": "x", "detail_html": "x",
                    "locations": [{"file": "b.py", "zones": []}],
                }),
            ],
        }
        review = transform_concepts_to_review(concepts)
        assert review["overallGrade"] == "F"

    def test_empty_concepts_grade_a(self):
        review = transform_concepts_to_review({})
        assert review["overallGrade"] == "A"
        assert review["findings"] == []

    def test_findings_sorted_by_severity(self):
        concepts = {
            "test": [
                ReviewConcept.model_validate({
                    "concept_id": "t-1", "title": "Good", "grade": "A",
                    "category": "code-health", "summary": "x", "detail_html": "x",
                    "locations": [{"file": "a.py", "zones": []}],
                }),
                ReviewConcept.model_validate({
                    "concept_id": "t-2", "title": "Critical", "grade": "F",
                    "category": "code-health", "summary": "x", "detail_html": "x",
                    "locations": [{"file": "b.py", "zones": []}],
                }),
            ],
        }
        review = transform_concepts_to_review(concepts)
        assert review["findings"][0]["grade"] == "F"
        assert review["findings"][1]["grade"] == "A"


# ---------------------------------------------------------------------------
# Transform: SemanticOutput → sections
# ---------------------------------------------------------------------------


class TestTransformSemanticOutputs:
    def test_what_changed(self):
        outputs = [
            SemanticOutput.model_validate({
                "output_type": "what_changed",
                "what_changed": {"layer": "product", "summary": "Product changes"},
            }),
            SemanticOutput.model_validate({
                "output_type": "what_changed",
                "what_changed": {"layer": "infrastructure", "summary": "Infra changes"},
            }),
        ]
        wc, decisions, pmi, fh = transform_semantic_outputs(outputs)
        assert wc["defaultSummary"]["product"] == "Product changes"
        assert wc["defaultSummary"]["infrastructure"] == "Infra changes"

    def test_decisions(self):
        outputs = [
            SemanticOutput.model_validate({
                "output_type": "decision",
                "decision": {
                    "number": 1, "title": "D1", "rationale": "R1",
                    "body": "B1", "zones": ["zone-alpha"],
                    "files": [{"path": "a.py", "change": "Changed"}],
                },
            }),
        ]
        _, decisions, _, _ = transform_semantic_outputs(outputs)
        assert len(decisions) == 1
        assert decisions[0]["title"] == "D1"
        assert decisions[0]["zones"] == "zone-alpha"

    def test_post_merge_items(self):
        outputs = [
            SemanticOutput.model_validate({
                "output_type": "post_merge_item",
                "post_merge_item": {
                    "priority": "medium", "title": "Watch this",
                    "description": "Context", "failure_scenario": "Bad",
                    "success_scenario": "Good", "zones": ["zone-alpha"],
                },
            }),
        ]
        _, _, pmi, _ = transform_semantic_outputs(outputs)
        assert len(pmi) == 1
        assert pmi[0]["priority"] == "medium"

    def test_factory_history(self):
        outputs = [
            SemanticOutput.model_validate({
                "output_type": "factory_event",
                "factory_event": {
                    "title": "Iter 1", "detail": "First", "meta": "Commit: abc",
                    "expanded_detail": "Details", "event_type": "automated",
                    "agent_label": "CI", "agent_type": "automated",
                },
            }),
        ]
        _, _, _, fh = transform_semantic_outputs(outputs)
        assert fh is not None
        assert len(fh["timeline"]) == 1

    def test_no_factory_events_returns_none(self):
        _, _, _, fh = transform_semantic_outputs([])
        assert fh is None


# ---------------------------------------------------------------------------
# Verification checks
# ---------------------------------------------------------------------------


class TestVerification:
    def test_file_not_in_diff(self):
        report = ValidationReport()
        concepts = {
            "code-health": [
                ReviewConcept.model_validate({
                    "concept_id": "ch-1", "title": "T", "grade": "A",
                    "category": "code-health", "summary": "x", "detail_html": "x",
                    "locations": [{"file": "nonexistent.py", "zones": ["zone-alpha"]}],
                }),
            ],
        }
        diff_data = {"files": {"src/real.py": {}}}
        zone_registry = {"zone-alpha": {"paths": ["src/**"]}}
        verify_findings(concepts, [], diff_data, zone_registry, report)
        assert any("nonexistent.py" in w["message"] for w in report.warnings)

    def test_zone_not_in_registry(self):
        report = ValidationReport()
        concepts = {
            "code-health": [
                ReviewConcept.model_validate({
                    "concept_id": "ch-1", "title": "T", "grade": "A",
                    "category": "code-health", "summary": "x", "detail_html": "x",
                    "locations": [{"file": "src/a.py", "zones": ["nonexistent-zone"]}],
                }),
            ],
        }
        diff_data = {"files": {"src/a.py": {}}}
        zone_registry = {"zone-alpha": {"paths": ["src/**"]}}
        verify_findings(concepts, [], diff_data, zone_registry, report)
        assert any("nonexistent-zone" in w["message"] for w in report.warnings)

    def test_architecture_unzoned_exception(self):
        """Architecture reviewer can have findings with zones not in registry."""
        report = ValidationReport()
        concepts = {
            "architecture": [
                ReviewConcept.model_validate({
                    "concept_id": "arch-1", "title": "T", "grade": "B",
                    "category": "architecture", "summary": "x", "detail_html": "x",
                    "locations": [{"file": "src/a.py", "zones": []}],
                }),
            ],
        }
        diff_data = {"files": {"src/a.py": {}}}
        zone_registry = {"zone-alpha": {"paths": ["src/**"]}}
        verify_findings(concepts, [], diff_data, zone_registry, report)
        # Should not have zone-related warnings for architecture
        zone_warnings = [w for w in report.warnings if "zone" in w["message"].lower()]
        assert len(zone_warnings) == 0

    def test_duplicate_concept_id(self):
        report = ValidationReport()
        concepts = {
            "test": [
                ReviewConcept.model_validate({
                    "concept_id": "test-1", "title": "T1", "grade": "A",
                    "category": "code-health", "summary": "x", "detail_html": "x",
                    "locations": [{"file": "a.py", "zones": []}],
                }),
                ReviewConcept.model_validate({
                    "concept_id": "test-1", "title": "T2", "grade": "B",
                    "category": "code-health", "summary": "x", "detail_html": "x",
                    "locations": [{"file": "b.py", "zones": []}],
                }),
            ],
        }
        verify_findings(concepts, [], {"files": {"a.py": {}, "b.py": {}}}, {}, report)
        assert any("Duplicate" in w["message"] for w in report.warnings)

    def test_coverage_gap_detection(self):
        report = ValidationReport()
        concepts = {
            "test": [
                ReviewConcept.model_validate({
                    "concept_id": "t-1", "title": "T", "grade": "A",
                    "category": "code-health", "summary": "x", "detail_html": "x",
                    "locations": [{"file": "src/covered.py", "zones": []}],
                }),
            ],
        }
        diff_data = {"files": {"src/covered.py": {}, "src/uncovered.py": {}}}
        verify_findings(concepts, [], diff_data, {}, report)
        assert any("uncovered.py" in w["message"] for w in report.warnings)

    def test_decision_zone_verification(self):
        report = ValidationReport()
        outputs = [
            SemanticOutput.model_validate({
                "output_type": "decision",
                "decision": {
                    "number": 1, "title": "D1", "rationale": "R1",
                    "body": "B1", "zones": ["zone-alpha"],
                },
            }),
        ]
        diff_data = {"files": {"src/unrelated.py": {}}}
        zone_registry = {"zone-alpha": {"paths": ["src/alpha/**"]}}
        verify_findings({}, outputs, diff_data, zone_registry, report)
        assert any("no diff files match" in w["message"] for w in report.warnings)


# ---------------------------------------------------------------------------
# JSONL reading (integration test with temp files)
# ---------------------------------------------------------------------------


class TestReadJSONL:
    def test_read_valid_jsonl(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "pr5-code-health-abcd1234-ef567890.jsonl"
            p.write_text(json.dumps({
                "concept_id": "code-health-1", "title": "Test",
                "grade": "A", "category": "code-health",
                "summary": "x", "detail_html": "x",
                "locations": [{"file": "a.py", "zones": []}],
            }) + "\n")

            report = ValidationReport()
            concepts, file_outcomes, semantics, arch = read_and_validate_jsonl(Path(tmpdir), report)
            assert "code-health" in concepts
            assert len(concepts["code-health"]) == 1
            assert not report.has_errors

    def test_read_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "pr5-code-health-abcd1234-ef567890.jsonl"
            p.write_text("not valid json\n")

            report = ValidationReport()
            read_and_validate_jsonl(Path(tmpdir), report)
            assert report.has_errors
            assert any("Invalid JSON" in e["message"] for e in report.errors)

    def test_read_invalid_schema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "pr5-code-health-abcd1234-ef567890.jsonl"
            p.write_text(json.dumps({"concept_id": "ch-1", "grade": "N/A"}) + "\n")

            report = ValidationReport()
            read_and_validate_jsonl(Path(tmpdir), report)
            assert report.has_errors

    def test_read_architecture_assessment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "pr5-architecture-abcd1234-ef567890.jsonl"
            lines = [
                json.dumps({
                    "concept_id": "architecture-1", "title": "Unzoned files",
                    "grade": "B", "category": "architecture",
                    "summary": "x", "detail_html": "x",
                    "locations": [{"file": "a.py", "zones": []}],
                }),
                json.dumps({"_type": "architecture_assessment", "overallHealth": "healthy", "summary": "All good"}),
            ]
            p.write_text("\n".join(lines) + "\n")

            report = ValidationReport()
            concepts, _, _, arch = read_and_validate_jsonl(Path(tmpdir), report)
            assert "architecture" in concepts
            assert arch is not None
            assert arch["overallHealth"] == "healthy"

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = ValidationReport()
            read_and_validate_jsonl(Path(tmpdir), report)
            assert report.has_errors
            assert any("No .jsonl" in e["message"] for e in report.errors)


# ---------------------------------------------------------------------------
# Hybrid output: FileReviewOutcome + ConceptUpdate in JSONL
# ---------------------------------------------------------------------------


class TestHybridJSONL:
    """Test reading .jsonl files with mixed FileReviewOutcome, ReviewConcept,
    and ConceptUpdate lines."""

    def _make_jsonl(self, tmpdir: str, agent: str, lines: list[dict]) -> Path:
        p = Path(tmpdir) / f"pr5-{agent}-abcd1234-ef567890.jsonl"
        p.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
        return p

    def test_file_review_outcomes_parsed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_jsonl(tmpdir, "code-health", [
                {"_type": "file_review", "file": "a.py", "grade": "A", "summary": "Clean file"},
                {"_type": "file_review", "file": "b.py", "grade": "C", "summary": "Issues found"},
            ])
            report = ValidationReport()
            concepts, file_outcomes, semantics, arch = read_and_validate_jsonl(Path(tmpdir), report)
            assert not report.has_errors
            assert "code-health" in file_outcomes
            assert len(file_outcomes["code-health"]) == 2
            assert file_outcomes["code-health"][0].file == "a.py"
            assert file_outcomes["code-health"][1].grade == Grade.C

    def test_hybrid_file_review_and_concepts(self):
        """FileReviewOutcome and ReviewConcept in same .jsonl."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_jsonl(tmpdir, "security", [
                {"_type": "file_review", "file": "a.py", "grade": "A", "summary": "Clean"},
                {"_type": "file_review", "file": "b.py", "grade": "F", "summary": "SQL injection"},
                {
                    "concept_id": "security-1", "title": "SQL Injection in b.py",
                    "grade": "F", "category": "security",
                    "summary": "Raw SQL", "detail_html": "<p>Bad</p>",
                    "locations": [{"file": "b.py", "zones": []}],
                },
            ])
            report = ValidationReport()
            concepts, file_outcomes, _, _ = read_and_validate_jsonl(Path(tmpdir), report)
            assert not report.has_errors
            assert len(file_outcomes["security"]) == 2
            assert len(concepts["security"]) == 1
            assert concepts["security"][0].grade == Grade.F

    def test_concept_update_merging(self):
        """ConceptUpdate overrides fields on matching concept."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_jsonl(tmpdir, "code-health", [
                {
                    "concept_id": "code-health-1", "title": "Original title",
                    "grade": "C", "category": "code-health",
                    "summary": "Original summary", "detail_html": "<p>Original</p>",
                    "locations": [{"file": "a.py", "zones": []}],
                },
                {
                    "_type": "concept_update", "concept_id": "code-health-1",
                    "grade": "B", "title": "Updated title",
                },
            ])
            report = ValidationReport()
            concepts, _, _, _ = read_and_validate_jsonl(Path(tmpdir), report)
            assert not report.has_errors
            merged = concepts["code-health"][0]
            assert merged.grade == Grade.B
            assert merged.title == "Updated title"
            assert merged.summary == "Original summary"  # unchanged

    def test_concept_update_missing_id_is_error(self):
        """ConceptUpdate referencing nonexistent concept_id is an error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_jsonl(tmpdir, "code-health", [
                {
                    "_type": "concept_update", "concept_id": "nonexistent-1",
                    "grade": "A",
                },
            ])
            report = ValidationReport()
            read_and_validate_jsonl(Path(tmpdir), report)
            assert report.has_errors
            assert any("nonexistent-1" in e["message"] for e in report.errors)


# ---------------------------------------------------------------------------
# Cascading validation
# ---------------------------------------------------------------------------


class TestCascadingValidation:
    """Test validate_file_coverage and validate_concept_backing."""

    def test_file_coverage_all_covered(self):
        diff_data = {"files": {"a.py": {}, "b.py": {}}}
        outcomes = {
            "code-health": [
                FileReviewOutcome(file="a.py", grade=Grade.A, summary="ok"),
                FileReviewOutcome(file="b.py", grade=Grade.A, summary="ok"),
            ],
            "security": [
                FileReviewOutcome(file="a.py", grade=Grade.A, summary="ok"),
                FileReviewOutcome(file="b.py", grade=Grade.A, summary="ok"),
            ],
        }
        report = ValidationReport()
        validate_file_coverage(outcomes, diff_data, report)
        assert not report.has_errors

    def test_file_coverage_missing_file(self):
        diff_data = {"files": {"a.py": {}, "b.py": {}, "c.py": {}}}
        outcomes = {
            "code-health": [
                FileReviewOutcome(file="a.py", grade=Grade.A, summary="ok"),
                # missing b.py and c.py
            ],
        }
        report = ValidationReport()
        validate_file_coverage(outcomes, diff_data, report)
        assert report.has_errors
        assert any("Missing FileReviewOutcome" in e["message"] for e in report.errors)

    def test_file_coverage_no_outcomes_backward_compat(self):
        """No file outcomes at all is valid (pre-v3 packs)."""
        diff_data = {"files": {"a.py": {}}}
        report = ValidationReport()
        validate_file_coverage({}, diff_data, report)
        assert not report.has_errors

    def test_concept_backing_non_a_has_concept(self):
        concepts = {
            "code-health": [
                ReviewConcept(
                    concept_id="ch-1", title="Issue", grade=Grade.C,
                    category="code-health", summary="x", detail_html="x",
                    locations=[{"file": "b.py", "zones": []}],
                ),
            ],
        }
        outcomes = {
            "code-health": [
                FileReviewOutcome(file="a.py", grade=Grade.A, summary="ok"),
                FileReviewOutcome(file="b.py", grade=Grade.C, summary="issue"),
            ],
        }
        report = ValidationReport()
        validate_concept_backing(concepts, outcomes, report)
        assert not report.has_errors

    def test_concept_backing_non_a_without_concept_is_error(self):
        concepts = {"code-health": []}  # no concepts at all
        outcomes = {
            "code-health": [
                FileReviewOutcome(file="b.py", grade=Grade.C, summary="issue"),
            ],
        }
        report = ValidationReport()
        validate_concept_backing(concepts, outcomes, report)
        assert report.has_errors
        assert any("backing concept" in e["message"] for e in report.errors)

    def test_concept_backing_a_grade_no_concept_ok(self):
        """A-grade files don't need backing concepts."""
        concepts = {"code-health": []}
        outcomes = {
            "code-health": [
                FileReviewOutcome(file="a.py", grade=Grade.A, summary="ok"),
            ],
        }
        report = ValidationReport()
        validate_concept_backing(concepts, outcomes, report)
        assert not report.has_errors


# ---------------------------------------------------------------------------
# File coverage transform
# ---------------------------------------------------------------------------


class TestFileCoverageTransform:
    def test_basic_transform(self):
        outcomes = {
            "code-health": [
                FileReviewOutcome(file="a.py", grade=Grade.A, summary="Clean"),
                FileReviewOutcome(file="b.py", grade=Grade.C, summary="Issues"),
            ],
            "security": [
                FileReviewOutcome(file="a.py", grade=Grade.A, summary="Safe"),
                FileReviewOutcome(file="b.py", grade=Grade.F, summary="Vuln"),
            ],
        }
        result = transform_file_outcomes_to_coverage(outcomes)
        assert result["agents"] == ["code-health", "security"]
        assert len(result["files"]) == 2
        # Worst grade first (F before A)
        assert result["files"][0]["file"] == "b.py"
        assert result["files"][0]["worstGrade"] == "F"
        assert result["files"][0]["grades"]["security"] == "F"
        assert result["files"][1]["file"] == "a.py"
        assert result["files"][1]["worstGrade"] == "A"

    def test_empty_outcomes(self):
        result = transform_file_outcomes_to_coverage({})
        assert result["agents"] == []
        assert result["files"] == []


# ---------------------------------------------------------------------------
# Architecture assessment graceful degradation
# ---------------------------------------------------------------------------


class TestArchAssessmentDegradation:
    """Test partial validation and consistency checks for architecture assessment."""

    def _make_jsonl(self, tmpdir: str, lines: list[dict]) -> Path:
        p = Path(tmpdir) / "pr5-architecture-abcd1234-ef567890.jsonl"
        p.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
        return p

    def test_valid_assessment_no_warnings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_jsonl(tmpdir, [
                {"_type": "architecture_assessment", "overallHealth": "healthy",
                 "summary": "All zones are covered."},
            ])
            report = ValidationReport()
            _, _, _, arch = read_and_validate_jsonl(Path(tmpdir), report)
            assert arch is not None
            assert arch["overallHealth"] == "healthy"
            assert not report.has_errors
            # No consistency warning for healthy + positive
            assert not any("inconsistency" in w["message"].lower() for w in report.warnings)

    def test_partial_degradation_keeps_health_and_summary(self):
        """If full validation fails but overallHealth + summary exist, keep them."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_jsonl(tmpdir, [
                {
                    "_type": "architecture_assessment",
                    "overallHealth": "needs-attention",
                    "summary": "<p>Some gaps found</p>",
                    "zoneChanges": "INVALID_NOT_A_LIST",  # will fail validation
                },
            ])
            report = ValidationReport()
            _, _, _, arch = read_and_validate_jsonl(Path(tmpdir), report)
            assert arch is not None
            assert arch["overallHealth"] == "needs-attention"
            assert arch.get("_partial") is True
            assert not report.has_errors  # degraded, not errored

    def test_full_degradation_when_no_health_or_summary(self):
        """If even overallHealth/summary are missing, fully degrade."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_jsonl(tmpdir, [
                {"_type": "architecture_assessment", "zoneChanges": "INVALID"},
            ])
            report = ValidationReport()
            _, _, _, arch = read_and_validate_jsonl(Path(tmpdir), report)
            assert arch is not None
            assert arch["overallHealth"] == "missing"
            assert arch.get("_partial") is True

    def test_consistency_warning_negative_health_positive_summary(self):
        """Warn when overallHealth is bad but summary starts positively."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_jsonl(tmpdir, [
                {
                    "_type": "architecture_assessment",
                    "overallHealth": "needs-attention",
                    "summary": "Good shape overall, minor gaps.",
                },
            ])
            report = ValidationReport()
            read_and_validate_jsonl(Path(tmpdir), report)
            assert any("inconsistency" in w["message"].lower() for w in report.warnings)

    def test_no_consistency_warning_when_healthy(self):
        """No consistency warning for healthy + positive summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_jsonl(tmpdir, [
                {
                    "_type": "architecture_assessment",
                    "overallHealth": "healthy",
                    "summary": "Good shape, all zones covered.",
                },
            ])
            report = ValidationReport()
            read_and_validate_jsonl(Path(tmpdir), report)
            assert not any("inconsistency" in w["message"].lower() for w in report.warnings)
