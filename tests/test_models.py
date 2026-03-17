"""Tests for ReviewConcept and SemanticOutput pydantic models."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from models import (
    CodeSnippetRef,
    ConceptLocation,
    ConceptUpdate,
    DecisionEntry,
    DecisionFile,
    FactoryEventEntry,
    FileReviewOutcome,
    FindingCategory,
    Grade,
    GRADE_SORT_ORDER,
    PostMergeEntry,
    ReviewConcept,
    SemanticOutput,
    WhatChangedEntry,
    ZoneDetail,
)


# ---------------------------------------------------------------------------
# ReviewConcept
# ---------------------------------------------------------------------------


class TestReviewConcept:
    """Tests for ReviewConcept model validation."""

    def _valid_concept(self, **overrides) -> dict:
        base = {
            "concept_id": "code-health-1",
            "title": "Test finding",
            "grade": "B",
            "category": "code-health",
            "summary": "A test summary",
            "detail_html": "<p>Detail</p>",
            "locations": [{"file": "src/main.py", "zones": ["zone-alpha"]}],
        }
        base.update(overrides)
        return base

    def test_valid_concept(self):
        rc = ReviewConcept.model_validate(self._valid_concept())
        assert rc.concept_id == "code-health-1"
        assert rc.grade == Grade.B
        assert rc.category == FindingCategory.CODE_HEALTH
        assert len(rc.locations) == 1

    def test_all_valid_grades(self):
        for grade in ["A", "B+", "B", "C", "F"]:
            rc = ReviewConcept.model_validate(self._valid_concept(grade=grade))
            assert rc.grade.value == grade

    def test_invalid_grade_na(self):
        with pytest.raises(ValidationError):
            ReviewConcept.model_validate(self._valid_concept(grade="N/A"))

    def test_invalid_grade_d(self):
        with pytest.raises(ValidationError):
            ReviewConcept.model_validate(self._valid_concept(grade="D"))

    def test_empty_locations_rejected(self):
        with pytest.raises(ValidationError):
            ReviewConcept.model_validate(self._valid_concept(locations=[]))

    def test_single_location_valid(self):
        rc = ReviewConcept.model_validate(self._valid_concept())
        assert len(rc.locations) == 1

    def test_multiple_locations(self):
        data = self._valid_concept(locations=[
            {"file": "src/a.py", "zones": ["zone-alpha"]},
            {"file": "src/b.py", "lines": "10-20", "zones": ["zone-beta"]},
        ])
        rc = ReviewConcept.model_validate(data)
        assert len(rc.locations) == 2
        assert rc.locations[1].lines == "10-20"

    def test_concept_id_must_be_kebab_case(self):
        with pytest.raises(ValidationError):
            ReviewConcept.model_validate(self._valid_concept(concept_id="CamelCase"))

    def test_concept_id_with_numbers(self):
        rc = ReviewConcept.model_validate(self._valid_concept(concept_id="code-health-42"))
        assert rc.concept_id == "code-health-42"

    def test_no_agent_field(self):
        """Agent identity is NOT in the schema — derived from filename."""
        data = self._valid_concept()
        data["agent"] = "code-health"
        # Extra fields are ignored by default in pydantic v2
        rc = ReviewConcept.model_validate(data)
        assert not hasattr(rc, "agent") or "agent" not in rc.model_fields

    def test_zone_id_validation_kebab_case(self):
        rc = ReviewConcept.model_validate(self._valid_concept(
            locations=[{"file": "a.py", "zones": ["rl-core", "review-pack"]}]
        ))
        assert rc.locations[0].zones == ["rl-core", "review-pack"]

    def test_zone_id_validation_rejects_camel_case(self):
        with pytest.raises(ValidationError):
            ReviewConcept.model_validate(self._valid_concept(
                locations=[{"file": "a.py", "zones": ["CamelCase"]}]
            ))

    def test_zone_id_validation_rejects_spaces(self):
        with pytest.raises(ValidationError):
            ReviewConcept.model_validate(self._valid_concept(
                locations=[{"file": "a.py", "zones": ["has spaces"]}]
            ))

    def test_empty_zones_valid(self):
        """Empty zones array is valid (file may be unzoned)."""
        rc = ReviewConcept.model_validate(self._valid_concept(
            locations=[{"file": "README.md", "zones": []}]
        ))
        assert rc.locations[0].zones == []

    def test_title_max_length(self):
        with pytest.raises(ValidationError):
            ReviewConcept.model_validate(self._valid_concept(title="x" * 201))

    def test_title_min_length(self):
        with pytest.raises(ValidationError):
            ReviewConcept.model_validate(self._valid_concept(title=""))

    def test_missing_required_field(self):
        data = self._valid_concept()
        del data["summary"]
        with pytest.raises(ValidationError):
            ReviewConcept.model_validate(data)

    def test_all_categories(self):
        for cat in ["code-health", "security", "test-integrity", "adversarial", "architecture", "cross-cutting"]:
            rc = ReviewConcept.model_validate(self._valid_concept(category=cat))
            assert rc.category.value == cat

    def test_location_with_comment(self):
        data = self._valid_concept(locations=[
            {"file": "a.py", "zones": ["zone-alpha"], "comment": "Important context"}
        ])
        rc = ReviewConcept.model_validate(data)
        assert rc.locations[0].comment == "Important context"

    def test_location_lines_optional(self):
        data = self._valid_concept(locations=[
            {"file": "a.py", "zones": ["zone-alpha"]}
        ])
        rc = ReviewConcept.model_validate(data)
        assert rc.locations[0].lines is None


# ---------------------------------------------------------------------------
# SemanticOutput
# ---------------------------------------------------------------------------


class TestSemanticOutput:
    """Tests for SemanticOutput model validation."""

    def test_what_changed(self):
        data = {
            "output_type": "what_changed",
            "what_changed": {
                "layer": "product",
                "summary": "Added feature X",
                "zone_details": [{"zone_id": "zone-alpha", "title": "Zone Alpha", "description": "Changes"}],
            },
        }
        so = SemanticOutput.model_validate(data)
        assert so.output_type == "what_changed"
        assert so.what_changed is not None
        assert so.what_changed.layer == "product"

    def test_decision(self):
        data = {
            "output_type": "decision",
            "decision": {
                "number": 1,
                "title": "Use async handlers",
                "rationale": "Better throughput",
                "body": "<p>Full explanation</p>",
                "zones": ["zone-alpha"],
                "files": [{"path": "src/a.py", "change": "Made async"}],
            },
        }
        so = SemanticOutput.model_validate(data)
        assert so.decision is not None
        assert so.decision.number == 1
        assert so.decision.zones == ["zone-alpha"]

    def test_post_merge_item(self):
        data = {
            "output_type": "post_merge_item",
            "post_merge_item": {
                "priority": "medium",
                "title": "Monitor latency",
                "description": "Watch p99",
                "failure_scenario": "Latency spike undetected",
                "success_scenario": "Alert on p99 > 200ms",
                "zones": ["zone-alpha"],
            },
        }
        so = SemanticOutput.model_validate(data)
        assert so.post_merge_item is not None
        assert so.post_merge_item.priority == "medium"

    def test_post_merge_item_with_code_snippet(self):
        data = {
            "output_type": "post_merge_item",
            "post_merge_item": {
                "priority": "low",
                "title": "Clean up",
                "description": "Remove dead code",
                "code_snippet": {
                    "file": "src/a.py",
                    "line_range": "lines 10-15",
                    "code": "def unused(): pass",
                },
                "failure_scenario": "Dead code accumulates",
                "success_scenario": "Clean codebase",
                "zones": [],
            },
        }
        so = SemanticOutput.model_validate(data)
        assert so.post_merge_item.code_snippet is not None
        assert so.post_merge_item.code_snippet.file == "src/a.py"

    def test_factory_event(self):
        data = {
            "output_type": "factory_event",
            "factory_event": {
                "title": "Iteration 1",
                "detail": "Initial generation",
                "meta": "Commit: abc1234 . Mar 15",
                "expanded_detail": "<p>Details</p>",
                "event_type": "automated",
                "agent_label": "CI (automated)",
                "agent_type": "automated",
            },
        }
        so = SemanticOutput.model_validate(data)
        assert so.factory_event is not None
        assert so.factory_event.event_type == "automated"

    def test_wrong_field_populated(self):
        """output_type says 'decision' but what_changed is populated."""
        data = {
            "output_type": "decision",
            "what_changed": {"layer": "product", "summary": "x"},
        }
        with pytest.raises(ValidationError):
            SemanticOutput.model_validate(data)

    def test_field_is_none(self):
        """output_type says 'decision' but decision field is None."""
        data = {"output_type": "decision"}
        with pytest.raises(ValidationError):
            SemanticOutput.model_validate(data)

    def test_invalid_output_type(self):
        with pytest.raises(ValidationError):
            SemanticOutput.model_validate({"output_type": "invalid_type"})

    def test_decision_zone_validation(self):
        data = {
            "output_type": "decision",
            "decision": {
                "number": 1,
                "title": "Test",
                "rationale": "Test",
                "body": "Test",
                "zones": ["BadZone"],
                "files": [],
            },
        }
        with pytest.raises(ValidationError):
            SemanticOutput.model_validate(data)

    def test_decision_requires_zones(self):
        data = {
            "output_type": "decision",
            "decision": {
                "number": 1,
                "title": "Test",
                "rationale": "Test",
                "body": "Test",
                "zones": [],
                "files": [],
            },
        }
        with pytest.raises(ValidationError):
            SemanticOutput.model_validate(data)

    def test_invalid_priority(self):
        data = {
            "output_type": "post_merge_item",
            "post_merge_item": {
                "priority": "high",  # invalid
                "title": "Test",
                "description": "Test",
                "failure_scenario": "Bad",
                "success_scenario": "Good",
            },
        }
        with pytest.raises(ValidationError):
            SemanticOutput.model_validate(data)


# ---------------------------------------------------------------------------
# Grade sort order
# ---------------------------------------------------------------------------


class TestGradeSortOrder:
    def test_f_is_lowest(self):
        assert GRADE_SORT_ORDER[Grade.F] == 0

    def test_a_is_highest(self):
        assert GRADE_SORT_ORDER[Grade.A] == 4

    def test_sort_order_is_monotonic(self):
        grades = [Grade.F, Grade.C, Grade.B, Grade.B_PLUS, Grade.A]
        values = [GRADE_SORT_ORDER[g] for g in grades]
        assert values == sorted(values)


# ---------------------------------------------------------------------------
# Example JSONL validation
# ---------------------------------------------------------------------------


class TestExampleJSONL:
    """Validate the reference example .jsonl files parse correctly."""

    @pytest.fixture()
    def examples_dir(self) -> Path:
        return Path(__file__).parent.parent / "references" / "examples"

    def test_review_concept_examples(self, examples_dir: Path):
        jsonl_files = list(examples_dir.glob("*-code-health-*.jsonl"))
        assert len(jsonl_files) >= 1, "Expected at least 1 code-health example"
        concept_count = 0
        file_review_count = 0
        for f in jsonl_files:
            with open(f) as fh:
                for i, line in enumerate(fh, 1):
                    obj = json.loads(line)
                    # Hybrid format: FileReviewOutcome or ReviewConcept
                    if obj.get("_type") == "file_review":
                        fro = FileReviewOutcome.model_validate(obj)
                        assert fro.file, f"Line {i} in {f.name} has empty file"
                        file_review_count += 1
                    else:
                        rc = ReviewConcept.model_validate(obj)
                        assert rc.concept_id, f"Line {i} in {f.name} has empty concept_id"
                        concept_count += 1
        assert concept_count > 0, "Expected at least 1 ReviewConcept in examples"
        assert file_review_count > 0, "Expected at least 1 FileReviewOutcome in examples"

    def test_semantic_output_examples(self, examples_dir: Path):
        jsonl_files = list(examples_dir.glob("*-synthesis-*.jsonl"))
        assert len(jsonl_files) >= 1, "Expected at least 1 synthesis example"
        for f in jsonl_files:
            with open(f) as fh:
                for i, line in enumerate(fh, 1):
                    obj = json.loads(line)
                    so = SemanticOutput.model_validate(obj)
                    assert so.output_type, f"Line {i} in {f.name} has empty output_type"


# ---------------------------------------------------------------------------
# FileReviewOutcome
# ---------------------------------------------------------------------------


class TestFileReviewOutcome:
    def test_valid_file_review(self):
        fro = FileReviewOutcome.model_validate({
            "_type": "file_review",
            "file": "src/main.py",
            "grade": "A",
            "summary": "Clean implementation",
        })
        assert fro.file == "src/main.py"
        assert fro.grade == Grade.A
        assert fro.reviewed is True

    def test_file_review_with_reviewed_false(self):
        fro = FileReviewOutcome.model_validate({
            "_type": "file_review",
            "file": "data/config.yaml",
            "grade": "A",
            "summary": "Config file, not code-reviewed",
            "reviewed": False,
        })
        assert fro.reviewed is False

    def test_file_review_type_discriminator(self):
        fro = FileReviewOutcome(file="a.py", grade=Grade.B, summary="ok")
        dumped = fro.model_dump(by_alias=True)
        assert dumped["_type"] == "file_review"

    def test_file_review_missing_file_rejected(self):
        with pytest.raises(ValidationError):
            FileReviewOutcome.model_validate({
                "_type": "file_review",
                "grade": "A",
                "summary": "Missing file field",
            })

    def test_file_review_empty_summary_rejected(self):
        with pytest.raises(ValidationError):
            FileReviewOutcome.model_validate({
                "_type": "file_review",
                "file": "a.py",
                "grade": "A",
                "summary": "",
            })

    def test_file_review_invalid_grade_rejected(self):
        with pytest.raises(ValidationError):
            FileReviewOutcome.model_validate({
                "_type": "file_review",
                "file": "a.py",
                "grade": "N/A",
                "summary": "ok",
            })


# ---------------------------------------------------------------------------
# ConceptUpdate
# ---------------------------------------------------------------------------


class TestConceptUpdate:
    def test_valid_concept_update(self):
        cu = ConceptUpdate.model_validate({
            "_type": "concept_update",
            "concept_id": "security-1",
            "grade": "B",
            "title": "Updated finding",
        })
        assert cu.concept_id == "security-1"
        assert cu.grade == Grade.B
        assert cu.title == "Updated finding"
        assert cu.summary is None  # not provided

    def test_concept_update_type_discriminator(self):
        cu = ConceptUpdate(concept_id="ch-1")
        dumped = cu.model_dump(by_alias=True)
        assert dumped["_type"] == "concept_update"

    def test_concept_update_all_fields_optional_except_id(self):
        cu = ConceptUpdate.model_validate({
            "_type": "concept_update",
            "concept_id": "arch-1",
        })
        assert cu.grade is None
        assert cu.title is None
        assert cu.summary is None
        assert cu.category is None

    def test_concept_update_invalid_id_rejected(self):
        with pytest.raises(ValidationError):
            ConceptUpdate.model_validate({
                "_type": "concept_update",
                "concept_id": "Invalid ID With Spaces",
            })

    def test_concept_update_missing_id_rejected(self):
        with pytest.raises(ValidationError):
            ConceptUpdate.model_validate({
                "_type": "concept_update",
                "grade": "A",
            })
