"""Tests for architecture assessment rendering.

Verifies render_architecture_assessment() produces correct HTML for each
subsection: health badge, narrative, unzoned files, zone changes, coupling
warnings, registry health, doc recommendations, and decision verification.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from render_review_pack import render_architecture_assessment

# ── Empty / None ─────────────────────────────────────────────────────


class TestArchAssessmentEmpty:
    def test_none_returns_empty(self):
        assert render_architecture_assessment({"architectureAssessment": None}) == ""

    def test_missing_key_returns_empty(self):
        assert render_architecture_assessment({}) == ""

    def test_empty_dict_returns_empty(self):
        """Empty dict is falsy in Python — treated same as None."""
        assert render_architecture_assessment({"architectureAssessment": {}}) == ""


# ── Health badge ─────────────────────────────────────────────────────


class TestHealthBadge:
    def test_healthy(self):
        html = render_architecture_assessment(
            {"architectureAssessment": {"overallHealth": "healthy"}}
        )
        assert "passing" in html
        assert "Healthy" in html

    def test_needs_attention(self):
        html = render_architecture_assessment(
            {"architectureAssessment": {"overallHealth": "needs-attention"}}
        )
        assert "warning" in html
        assert "Needs Attention" in html

    def test_action_required(self):
        html = render_architecture_assessment(
            {"architectureAssessment": {"overallHealth": "action-required"}}
        )
        assert "failing" in html
        assert "Action Required" in html


# ── Summary ──────────────────────────────────────────────────────────


class TestSummary:
    def test_summary_rendered(self):
        html = render_architecture_assessment(
            {"architectureAssessment": {"summary": "<p>Test summary.</p>"}}
        )
        assert "<p>Test summary.</p>" in html

    def test_no_summary_no_extra_div(self):
        html = render_architecture_assessment({"architectureAssessment": {"summary": ""}})
        assert "Test summary" not in html


# ── Diagram narrative ────────────────────────────────────────────────


class TestNarrative:
    def test_narrative_rendered(self):
        html = render_architecture_assessment(
            {"architectureAssessment": {"diagramNarrative": "<p>Arch changed.</p>"}}
        )
        assert "arch-narrative" in html
        assert "Arch changed." in html

    def test_no_narrative_no_section(self):
        html = render_architecture_assessment({"architectureAssessment": {"diagramNarrative": ""}})
        assert "arch-narrative" not in html


# ── Unzoned files ────────────────────────────────────────────────────


class TestUnzonedFiles:
    def test_unzoned_table_rendered(self):
        html = render_architecture_assessment(
            {
                "architectureAssessment": {
                    "unzonedFiles": [
                        {"path": "README.md", "suggestedZone": None, "reason": "No match"},
                    ],
                },
            }
        )
        assert "arch-subsubsection" in html
        assert "README.md" in html
        assert "1 Unzoned File(s)" in html

    def test_suggested_zone_shown(self):
        html = render_architecture_assessment(
            {
                "architectureAssessment": {
                    "unzonedFiles": [
                        {"path": "src/x.py", "suggestedZone": "zone-alpha", "reason": "Matches"},
                    ],
                },
            }
        )
        assert "zone-alpha" in html

    def test_no_unzoned_no_section(self):
        html = render_architecture_assessment({"architectureAssessment": {"unzonedFiles": []}})
        assert "arch-subsubsection" not in html

    def test_html_escaping_in_path(self):
        html = render_architecture_assessment(
            {
                "architectureAssessment": {
                    "unzonedFiles": [
                        {
                            "path": "<script>alert(1)</script>",
                            "suggestedZone": None,
                            "reason": "test",
                        },
                    ],
                },
            }
        )
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


# ── Zone changes ─────────────────────────────────────────────────────


class TestZoneChanges:
    def test_zone_changes_rendered(self):
        html = render_architecture_assessment(
            {
                "architectureAssessment": {
                    "zoneChanges": [
                        {"type": "new_zone_recommended", "zone": "new-mod", "reason": "3 files"},
                    ],
                },
            }
        )
        assert "arch-change-item" in html
        assert "new-mod" in html
        assert "New Zone Recommended" in html

    def test_no_changes_no_section(self):
        html = render_architecture_assessment({"architectureAssessment": {"zoneChanges": []}})
        assert "arch-change-item" not in html


# ── Coupling warnings ───────────────────────────────────────────────


class TestCouplingWarnings:
    def test_coupling_rendered(self):
        html = render_architecture_assessment(
            {
                "architectureAssessment": {
                    "couplingWarnings": [
                        {
                            "fromZone": "zone-alpha",
                            "toZone": "zone-beta",
                            "files": ["src/a.py"],
                            "evidence": "Direct import",
                        },
                    ],
                },
            }
        )
        assert "arch-coupling-item" in html
        assert "zone-alpha" in html
        assert "zone-beta" in html
        assert "Direct import" in html

    def test_no_coupling_no_section(self):
        html = render_architecture_assessment({"architectureAssessment": {"couplingWarnings": []}})
        assert "arch-coupling-item" not in html


# ── Registry warnings ───────────────────────────────────────────────


class TestRegistryWarnings:
    def test_registry_warnings_rendered(self):
        html = render_architecture_assessment(
            {
                "architectureAssessment": {
                    "registryWarnings": [
                        {"zone": "zone-beta", "warning": "Missing specs", "severity": "WARNING"},
                    ],
                },
            }
        )
        assert "arch-registry-item" in html
        assert "zone-beta" in html
        assert "Missing specs" in html
        assert "WARNING" in html

    def test_no_warnings_no_section(self):
        html = render_architecture_assessment({"architectureAssessment": {"registryWarnings": []}})
        assert "arch-registry-item" not in html


# ── Doc recommendations ─────────────────────────────────────────────


class TestDocRecommendations:
    def test_doc_recs_rendered(self):
        html = render_architecture_assessment(
            {
                "architectureAssessment": {
                    "docRecommendations": [
                        {"type": "update_needed", "path": "docs/arch.md", "reason": "Stale"},
                    ],
                },
            }
        )
        assert "arch-doc-item" in html
        assert "docs/arch.md" in html
        assert "Stale" in html

    def test_no_recs_no_section(self):
        html = render_architecture_assessment(
            {"architectureAssessment": {"docRecommendations": []}}
        )
        assert "arch-doc-item" not in html


# ── Decision verification ───────────────────────────────────────────


class TestDecisionVerification:
    def test_unverified_decisions_shown(self):
        html = render_architecture_assessment(
            {
                "architectureAssessment": {
                    "decisionZoneVerification": [
                        {
                            "decisionNumber": 2,
                            "claimedZones": ["zone-gamma"],
                            "verified": False,
                            "reason": "No files in zone-gamma touched",
                        },
                    ],
                },
            }
        )
        assert "Unverified Decision-Zone Claims" in html
        assert "arch-verification-item" in html
        assert "Decision #2" in html
        assert "zone-gamma" in html

    def test_verified_decisions_not_shown(self):
        html = render_architecture_assessment(
            {
                "architectureAssessment": {
                    "decisionZoneVerification": [
                        {
                            "decisionNumber": 1,
                            "claimedZones": ["zone-alpha"],
                            "verified": True,
                            "reason": "Files match",
                        },
                    ],
                },
            }
        )
        assert "arch-verification-item" not in html

    def test_no_verifications_no_section(self):
        html = render_architecture_assessment(
            {"architectureAssessment": {"decisionZoneVerification": []}}
        )
        assert "arch-verification-item" not in html


# ── Needs-attention pill (coreIssuesNeedAttention flag) ─────────────


class TestNeedsAttentionPill:
    def test_no_needs_attention_pill_when_healthy_and_flag_false(self):
        """When coreIssuesNeedAttention is False, no needs-attention pill should render."""
        data = {
            "architectureAssessment": {
                "overallHealth": "healthy",
                "summary": "Architecturally clean PR.",
                "diagramNarrative": "No architectural changes.",
                "coreIssuesNeedAttention": False,
                "decisionZoneVerification": [],
                "zoneChanges": [],
                "couplingWarnings": [],
                "registryWarnings": [],
                "unzonedFiles": [],
                "docRecommendations": [],
            }
        }
        result = render_architecture_assessment(data)
        assert "arch-issue-pill" not in result

    def test_needs_attention_pill_when_flag_true(self):
        """When coreIssuesNeedAttention is True, the pill should render."""
        data = {
            "architectureAssessment": {
                "overallHealth": "needs-attention",
                "summary": "Minor gaps found.",
                "diagramNarrative": "Some unzoned files detected.",
                "coreIssuesNeedAttention": True,
                "decisionZoneVerification": [],
                "zoneChanges": [],
                "couplingWarnings": [],
                "registryWarnings": [],
                "unzonedFiles": [],
                "docRecommendations": [],
            }
        }
        result = render_architecture_assessment(data)
        assert "arch-issue-pill" in result
        assert "Needs Attention" in result

    def test_legacy_data_without_flag_infers_from_health(self):
        """When coreIssuesNeedAttention is absent, fall back to health inference."""
        data = {
            "architectureAssessment": {
                "overallHealth": "needs-attention",
                "summary": "Minor gaps.",
                "diagramNarrative": "Some issues.",
                "decisionZoneVerification": [],
            }
        }
        result = render_architecture_assessment(data)
        assert "arch-issue-pill" in result


# ── Full fixture integration ────────────────────────────────────────


class TestFullFixtureRender:
    def test_renders_all_populated_sections(self, sample_review_pack_data):
        html = render_architecture_assessment(sample_review_pack_data)
        # Health badge
        assert "arch-health-badge" in html
        assert "Needs Attention" in html
        # Summary
        assert "1 unzoned file" in html
        # Narrative
        assert "arch-narrative" in html
        # Unzoned files
        assert "README.md" in html
        # Registry warnings
        assert "zone-beta" in html
        assert "Missing specs" in html
        # Decision verification — all verified, so no section
        assert "arch-verification-item" not in html
