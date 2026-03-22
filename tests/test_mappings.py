"""Tests for mapping constants and helper functions.

Verifies that all grade classes, agent abbreviations, layer tag classes,
health classes, category classes, and status styles are correctly defined.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from render_review_pack import (
    AGENT_ABBREV,
    CATEGORY_CLASS,
    GRADE_CLASS,
    STATUS_STYLE,
    layer_tag_class,
)

# ── GRADE_CLASS ───────────────────────────────────────────────────────


class TestGradeClass:
    def test_grade_a(self):
        assert GRADE_CLASS["A"] == "a"

    def test_grade_b_plus(self):
        assert GRADE_CLASS["B+"] == "b"

    def test_grade_b(self):
        assert GRADE_CLASS["B"] == "b"

    def test_grade_c(self):
        assert GRADE_CLASS["C"] == "c"

    def test_grade_f(self):
        assert GRADE_CLASS["F"] == "f"

    def test_grade_na(self):
        assert GRADE_CLASS["N/A"] == "na"

    def test_all_grades_present(self):
        expected = {"A", "B+", "B", "C", "F", "N/A"}
        assert set(GRADE_CLASS.keys()) == expected


# ── AGENT_ABBREV ──────────────────────────────────────────────────────


class TestAgentAbbrev:
    def test_code_health(self):
        assert AGENT_ABBREV["code-health"] == "CH"

    def test_security(self):
        assert AGENT_ABBREV["security"] == "SE"

    def test_test_integrity(self):
        assert AGENT_ABBREV["test-integrity"] == "TI"

    def test_adversarial(self):
        assert AGENT_ABBREV["adversarial"] == "AD"

    def test_code_health_reviewer_suffix(self):
        assert AGENT_ABBREV["code-health-reviewer"] == "CH"

    def test_security_reviewer_suffix(self):
        assert AGENT_ABBREV["security-reviewer"] == "SE"

    def test_test_integrity_reviewer_suffix(self):
        assert AGENT_ABBREV["test-integrity-reviewer"] == "TI"

    def test_adversarial_reviewer_suffix(self):
        assert AGENT_ABBREV["adversarial-reviewer"] == "AD"

    def test_architecture(self):
        assert AGENT_ABBREV["architecture"] == "AR"

    def test_architecture_reviewer_suffix(self):
        assert AGENT_ABBREV["architecture-reviewer"] == "AR"

    def test_main_agent(self):
        assert AGENT_ABBREV["main"] == "MA"
        assert AGENT_ABBREV["main-agent"] == "MA"

    def test_reviewer_variants_match_base(self):
        """All -reviewer variants should map to the same abbreviation as the base."""
        pairs = [
            ("code-health", "code-health-reviewer"),
            ("security", "security-reviewer"),
            ("test-integrity", "test-integrity-reviewer"),
            ("adversarial", "adversarial-reviewer"),
            ("architecture", "architecture-reviewer"),
        ]
        for base, reviewer in pairs:
            assert AGENT_ABBREV[base] == AGENT_ABBREV[reviewer], (
                f"{base} ({AGENT_ABBREV[base]}) != {reviewer} ({AGENT_ABBREV[reviewer]})"
            )


# ── layer_tag_class ───────────────────────────────────────────────────


class TestLayerTagClass:
    def test_factory(self):
        assert layer_tag_class("factory") == "factory"

    def test_product(self):
        assert layer_tag_class("product") == "product"

    def test_infra(self):
        assert layer_tag_class("infra") == "infra"

    def test_unknown_defaults_to_product(self):
        assert layer_tag_class("unknown") == "product"

    def test_empty_string_defaults_to_product(self):
        assert layer_tag_class("") == "product"

    def test_arbitrary_value_defaults_to_product(self):
        assert layer_tag_class("some-random-category") == "product"


# ── CATEGORY_CLASS ────────────────────────────────────────────────────


class TestCategoryClass:
    def test_all_values(self):
        assert CATEGORY_CLASS["environment"] == "cat-environment"
        assert CATEGORY_CLASS["training"] == "cat-training"
        assert CATEGORY_CLASS["pipeline"] == "cat-pipeline"
        assert CATEGORY_CLASS["integration"] == "cat-integration"

    def test_all_have_cat_prefix(self):
        for key, value in CATEGORY_CLASS.items():
            assert value.startswith("cat-"), f"{key} -> {value} missing 'cat-' prefix"


# ── STATUS_STYLE ──────────────────────────────────────────────────────


class TestStatusStyle:
    def test_passing(self):
        color, icon, label = STATUS_STYLE["passing"]
        assert "green" in color
        assert "2713" in icon  # checkmark
        assert label == "Passing"

    def test_pass(self):
        color, icon, label = STATUS_STYLE["pass"]
        assert "green" in color
        assert label == "Pass"

    def test_failing(self):
        color, icon, label = STATUS_STYLE["failing"]
        assert "red" in color
        assert "2717" in icon  # cross
        assert label == "Failing"

    def test_fail(self):
        color, icon, label = STATUS_STYLE["fail"]
        assert "red" in color
        assert label == "Fail"

    def test_advisory(self):
        color, icon, label = STATUS_STYLE["advisory"]
        assert "yellow" in color
        assert "26A0" in icon  # warning triangle
        assert label == "Advisory"

    def test_all_statuses_present(self):
        expected = {"passing", "pass", "failing", "fail", "advisory"}
        assert set(STATUS_STYLE.keys()) == expected

    def test_all_tuples_have_three_elements(self):
        for key, value in STATUS_STYLE.items():
            assert len(value) == 3, f"STATUS_STYLE['{key}'] has {len(value)} elements, expected 3"
