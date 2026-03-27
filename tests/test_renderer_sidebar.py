"""Tests for all 6 sidebar render functions in render_review_pack.py.

Each test exercises a specific sidebar render function with real fixture data
and checks for concrete HTML output: class names, data attributes,
content strings, and structural elements.

Uses abstract zone names (zone-alpha, zone-beta, zone-gamma) to keep tests
project-agnostic.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from render_review_pack import (
    render_sidebar_commit_scope,
    render_sidebar_gate_pills,
    render_sidebar_merge_button,
    render_sidebar_pr_meta,
    render_sidebar_section_nav,
    render_sidebar_status_badges,
    render_sidebar_verdict,
)

# ── render_sidebar_pr_meta ───────────────────────────────────────────


class TestRenderSidebarPrMeta:
    def test_pr_number(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_sidebar_pr_meta(header)
        assert "PR #42" in result

    def test_title(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_sidebar_pr_meta(header)
        assert "Add feature X to zone-alpha" in result

    def test_additions(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_sidebar_pr_meta(header)
        assert "+150" in result

    def test_deletions(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_sidebar_pr_meta(header)
        assert "&minus;30" in result

    def test_file_count(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_sidebar_pr_meta(header)
        assert "8 files" in result

    def test_css_classes(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_sidebar_pr_meta(header)
        assert 'class="sb-pr-meta"' in result
        assert 'class="sb-pr-number"' in result
        assert 'class="sb-pr-title"' in result
        assert 'class="sb-pr-stats"' in result

    def test_html_escaping_in_title(self):
        header = {
            "prNumber": 1,
            "title": "<script>alert('xss')</script>",
            "additions": 0,
            "deletions": 0,
            "filesChanged": 0,
        }
        result = render_sidebar_pr_meta(header)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_defaults_for_missing_keys(self):
        result = render_sidebar_pr_meta({})
        assert "PR #" in result
        assert "+0" in result
        assert "&minus;0" in result
        assert "0 files" in result

    def test_branch_info(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_sidebar_pr_meta(header)
        assert "feature/add-x" in result
        assert "main" in result
        assert "&rarr;" in result

    def test_head_sha(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_sidebar_pr_meta(header)
        assert "abc1234" in result

    def test_commits(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_sidebar_pr_meta(header)
        assert "commit" in result

    def test_pr_url_link(self):
        header = {
            "prNumber": 5,
            "title": "Test",
            "prUrl": "https://github.com/test/repo/pull/5",
        }
        result = render_sidebar_pr_meta(header)
        assert 'href="https://github.com/test/repo/pull/5"' in result
        assert 'target="_blank"' in result


# ── render_sidebar_status_badges ─────────────────────────────────────


class TestRenderSidebarStatusBadges:
    def test_renders_badges(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_sidebar_status_badges(header)
        assert "status-badge" in result

    def test_badge_labels(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_sidebar_status_badges(header)
        for badge in header.get("statusBadges", []):
            label = badge["label"]
            # CI and Gate 0 badges are filtered (covered by gate pills)
            if label.startswith("CI") or "Gate 0" in label:
                continue
            assert label in result

    def test_badge_types(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_sidebar_status_badges(header)
        for badge in header.get("statusBadges", []):
            assert badge["type"] in result

    def test_empty_badges(self):
        result = render_sidebar_status_badges({"statusBadges": []})
        assert result == ""

    def test_no_badges_key(self):
        result = render_sidebar_status_badges({})
        assert result == ""


# ── render_sidebar_verdict ───────────────────────────────────────────


class TestRenderSidebarVerdict:
    def test_ready_status(self, sample_review_pack_data):
        result = render_sidebar_verdict(sample_review_pack_data)
        assert 'class="sb-verdict ready"' in result
        assert "READY" in result

    def test_ready_icon(self, sample_review_pack_data):
        result = render_sidebar_verdict(sample_review_pack_data)
        # checkmark entity
        assert "&#x2713;" in result

    def test_review_status(self):
        data = {"verdict": {"status": "review", "text": "NEEDS REVIEW"}}
        result = render_sidebar_verdict(data)
        assert 'class="sb-verdict review"' in result
        assert "NEEDS REVIEW" in result
        # warning icon
        assert "&#x26A0;" in result

    def test_blocked_status(self):
        data = {"verdict": {"status": "blocked", "text": "BLOCKED"}}
        result = render_sidebar_verdict(data)
        assert 'class="sb-verdict blocked"' in result
        assert "BLOCKED" in result
        # cross icon
        assert "&#x2717;" in result

    def test_unknown_status_fallback(self):
        data = {"verdict": {"status": "unknown", "text": "UNKNOWN"}}
        result = render_sidebar_verdict(data)
        assert 'class="sb-verdict unknown"' in result
        assert "?" in result

    def test_missing_verdict_defaults_to_review(self):
        result = render_sidebar_verdict({})
        assert 'class="sb-verdict review"' in result
        assert "REVIEW" in result

    def test_text_html_escaped(self):
        data = {"verdict": {"status": "ready", "text": "<b>READY</b>"}}
        result = render_sidebar_verdict(data)
        assert "&lt;b&gt;" in result
        assert "<b>" not in result


# ── render_sidebar_verdict (new status field) ───────────────────────


class TestRenderSidebarVerdictNewStatus:
    """Tests for verdict rendering with the new status field."""

    def test_needs_review_with_reasons(self):
        data = {
            "status": {
                "value": "needs-review",
                "text": "NEEDS REVIEW",
                "reasons": ["C-grade findings in 2 file(s)", "3 commit(s) not covered"],
            },
        }
        result = render_sidebar_verdict(data)
        assert 'class="sb-verdict needs-review"' in result
        assert "NEEDS REVIEW" in result
        assert "sb-status-reasons" in result
        assert "C-grade findings" in result
        assert "3 commit(s)" in result

    def test_ready_no_reasons(self):
        data = {"status": {"value": "ready", "text": "READY", "reasons": []}}
        result = render_sidebar_verdict(data)
        assert 'class="sb-verdict ready"' in result
        assert "sb-status-reasons" not in result

    def test_blocked_with_reasons(self):
        data = {
            "status": {
                "value": "blocked",
                "text": "BLOCKED",
                "reasons": ["Failing gates: Gate 1"],
            },
        }
        result = render_sidebar_verdict(data)
        assert 'class="sb-verdict blocked"' in result
        assert "Failing gates" in result

    def test_falls_back_to_legacy_verdict(self):
        data = {"verdict": {"status": "review", "text": "REVIEW"}}
        result = render_sidebar_verdict(data)
        assert 'class="sb-verdict review"' in result


# ── render_sidebar_commit_scope ─────────────────────────────────────


class TestRenderSidebarCommitScope:
    def test_matching_shas(self):
        data = {
            "reviewedCommitSHA": "abc1234567890",
            "headCommitSHA": "abc1234567890",
            "commitGap": 0,
        }
        result = render_sidebar_commit_scope(data)
        assert "sb-commit-scope" in result
        assert "abc1234" in result
        assert "match" in result
        assert "sb-commit-gap" not in result

    def test_mismatched_shas_shows_gap(self):
        data = {
            "reviewedCommitSHA": "abc1234567890",
            "headCommitSHA": "def5678901234",
            "commitGap": 3,
        }
        result = render_sidebar_commit_scope(data)
        assert "mismatch" in result
        assert "abc1234" in result
        assert "def5678" in result
        assert "sb-commit-gap" in result
        assert "3 commit(s)" in result

    def test_empty_shas_returns_empty(self):
        result = render_sidebar_commit_scope({})
        assert result == ""

    def test_zero_gap_no_warning(self):
        data = {
            "reviewedCommitSHA": "abc1234567890",
            "headCommitSHA": "def5678901234",
            "commitGap": 0,
        }
        result = render_sidebar_commit_scope(data)
        assert "sb-commit-gap" not in result


# ── render_sidebar_merge_button ─────────────────────────────────────


class TestRenderSidebarMergeButton:
    def test_ready_button_enabled(self):
        data = {
            "status": {"value": "ready", "text": "READY", "reasons": []},
            "header": {"prNumber": 26},
        }
        result = render_sidebar_merge_button(data)
        assert "sb-merge-btn ready" in result
        assert "Approve and Merge" in result
        assert "disabled" not in result
        assert "review-pack merge 26" in result

    def test_needs_review_button_enabled_with_warning(self):
        data = {
            "status": {"value": "needs-review", "text": "NEEDS REVIEW", "reasons": ["gap"]},
            "header": {"prNumber": 42},
        }
        result = render_sidebar_merge_button(data)
        assert "sb-merge-btn needs-review" in result
        assert "with warnings" in result
        assert "review-pack merge 42" in result

    def test_blocked_button_disabled(self):
        data = {
            "status": {"value": "blocked", "text": "BLOCKED", "reasons": ["gates"]},
            "header": {"prNumber": 10},
        }
        result = render_sidebar_merge_button(data)
        assert "disabled" in result
        assert "cannot merge" in result
        assert "sb-merge-panel" not in result

    def test_merge_steps_present(self):
        data = {
            "status": {"value": "ready", "text": "READY", "reasons": []},
            "header": {"prNumber": 5},
        }
        result = render_sidebar_merge_button(data)
        assert "merge-steps" in result
        assert "Validate the snapshot" in result


# ── render_sidebar_gate_pills ────────────────────────────────────────


class TestRenderSidebarGatePills:
    def test_pills_rendered(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_sidebar_gate_pills(convergence)
        assert result.count('class="sb-gate-pill ') == 4

    def test_passing_pill_class(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_sidebar_gate_pills(convergence)
        assert "sb-gate-pill pass" in result
        assert "&#x2713;" in result

    def test_failing_pill_class(self):
        convergence = {
            "gates": [
                {
                    "name": "Gate 1",
                    "status": "failing",
                    "statusText": "FAILING",
                    "summary": "Errors.",
                },
            ],
        }
        result = render_sidebar_gate_pills(convergence)
        assert "sb-gate-pill fail" in result
        assert "&#x2717;" in result

    def test_onclick_calls_scroll_to_gate(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_sidebar_gate_pills(convergence)
        assert "scrollToGate(" in result

    def test_container_class(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_sidebar_gate_pills(convergence)
        assert 'class="sb-gate-pills"' in result

    def test_short_label_from_em_dash(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_sidebar_gate_pills(convergence)
        # "Gate 0 — Two-Tier Review" should show "Gate 0" as short label
        assert "Gate 0 " in result

    def test_empty_gates(self):
        result = render_sidebar_gate_pills({"gates": []})
        assert result == ""

    def test_missing_gates_key(self):
        result = render_sidebar_gate_pills({})
        assert result == ""

    def test_mixed_passing_and_failing(self):
        convergence = {
            "gates": [
                {"name": "Gate 1", "status": "passing"},
                {"name": "Gate 2", "status": "failing"},
            ],
        }
        result = render_sidebar_gate_pills(convergence)
        assert "sb-gate-pill pass" in result
        assert "sb-gate-pill fail" in result


# ── render_sidebar_section_nav ───────────────────────────────────────


class TestRenderSidebarSectionNav:
    def test_all_standard_sections_present(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        assert "Architecture" in result
        assert "What Changed" in result
        assert "Specs &amp; Scenarios" in result
        assert "Review Gates" in result
        assert "Key Findings" in result
        assert "File Coverage" in result
        assert "Key Decisions" in result
        assert "Convergence" in result
        assert "CI Performance" in result
        assert "Post-Merge Items" in result

    def test_no_factory_history_when_none(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        assert "Factory History" not in result

    def test_factory_history_when_present(self, sample_review_pack_data, sample_factory_history):
        data = {**sample_review_pack_data, "factoryHistory": sample_factory_history}
        result = render_sidebar_section_nav(data)
        assert "Factory History" in result
        assert 'data-section="section-factory-history"' in result

    def test_nav_items_have_section_ids(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        assert 'data-section="section-architecture"' in result
        assert 'data-section="section-what-changed"' in result
        assert 'data-section="section-specs-scenarios"' in result
        assert 'data-section="section-review-gates"' in result
        assert 'data-section="section-key-findings"' in result
        assert 'data-section="section-file-coverage"' in result
        assert 'data-section="section-key-decisions"' in result
        assert 'data-section="section-convergence"' in result
        assert 'data-section="section-ci-performance"' in result
        assert 'data-section="section-post-merge"' in result

    def test_onclick_scroll(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        assert "scrollToSection('section-architecture')" in result
        assert "scrollToSection('section-ci-performance')" in result

    def test_group_labels(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        assert 'class="sb-nav-group-label"' in result
        assert "Architecture &amp; Changes" in result
        assert "Factory" in result
        assert "Review &amp; Evidence" in result
        assert "Follow-ups" in result

    def test_nav_item_class(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        assert 'class="sb-nav-item"' in result

    # ── Icon relationship tests ──

    def test_architecture_icon_shows_modified_zone_count(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        # 2 modified zones (alpha, beta) → count badge with "2"
        assert 'class="sb-nav-icon count"' in result
        assert ">2<" in result

    def test_what_changed_icon_present_when_content(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        assert 'class="sb-nav-icon present"' in result

    def test_key_decisions_icon_shows_count(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        # 1 decision → count badge with "1"
        assert ">1<" in result

    def test_review_gates_icon_pass_when_all_passing(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        # All gates passing → green ✓
        assert 'class="sb-nav-icon pass"' in result

    def test_review_gates_icon_fail_when_gate_failing(self):
        data = {
            "architecture": {"zones": []},
            "whatChanged": {"defaultSummary": {}},
            "scenarios": [{"status": "pass"}],
            "agenticReview": {"findings": []},
            "decisions": [],
            "convergence": {
                "gates": [{"name": "G1", "status": "failing"}],
                "overall": {"status": "failing"},
            },
            "ciPerformance": [],
            "postMergeItems": [],
            "factoryHistory": None,
        }
        result = render_sidebar_section_nav(data)
        assert 'class="sb-nav-icon fail"' in result

    def test_arch_assessment_icon_warn_for_needs_attention(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        # overallHealth="needs-attention" → yellow ⚠
        assert 'class="sb-nav-icon warn"' in result

    def test_arch_assessment_icon_pass_for_healthy(self, sample_review_pack_data):
        data = {**sample_review_pack_data}
        aa = {**data["architectureAssessment"], "overallHealth": "healthy"}
        data["architectureAssessment"] = aa
        result = render_sidebar_section_nav(data)
        assert 'class="sb-nav-icon pass"' in result

    def test_arch_assessment_icon_fail_for_action_required(self, sample_review_pack_data):
        data = {**sample_review_pack_data}
        aa = {**data["architectureAssessment"], "overallHealth": "action-required"}
        data["architectureAssessment"] = aa
        result = render_sidebar_section_nav(data)
        assert 'class="sb-nav-icon fail"' in result

    def test_code_review_icon_count_fail_when_cf_findings(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        # 1 C-grade finding → red count chip with "1"
        assert 'class="sb-nav-icon count-fail"' in result

    def test_code_review_icon_pass_when_no_cf_findings(self):
        data = {
            "architecture": {"zones": []},
            "whatChanged": {"defaultSummary": {}},
            "scenarios": [{"status": "pass"}],
            "agenticReview": {
                "findings": [
                    {"grade": "A", "file": "f.py", "agent": "ch", "notable": "", "detail": ""},
                ]
            },
            "decisions": [],
            "convergence": {"gates": [], "overall": {}},
            "ciPerformance": [],
            "postMergeItems": [],
            "factoryHistory": None,
        }
        result = render_sidebar_section_nav(data)
        assert 'class="sb-nav-icon pass"' in result

    def test_ci_icon_pass_when_all_green(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        # All CI pass → ✓
        assert 'class="sb-nav-icon pass"' in result

    def test_ci_icon_fail_when_some_fail(self):
        data = {
            "architecture": {"zones": []},
            "whatChanged": {"defaultSummary": {}},
            "scenarios": [{"status": "pass"}],
            "agenticReview": {"findings": []},
            "decisions": [],
            "convergence": {"gates": [], "overall": {}},
            "ciPerformance": [
                {"name": "lint", "status": "pass"},
                {"name": "test", "status": "fail"},
            ],
            "postMergeItems": [],
            "factoryHistory": None,
        }
        result = render_sidebar_section_nav(data)
        assert 'class="sb-nav-icon fail"' in result

    def test_post_merge_icon_count_warn_when_items(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        # 1 post-merge item → yellow count chip with "1"
        assert 'class="sb-nav-icon count-warn"' in result

    def test_post_merge_icon_empty_when_no_items(self):
        data = {
            "architecture": {"zones": []},
            "whatChanged": {"defaultSummary": {}},
            "scenarios": [],
            "agenticReview": {"findings": []},
            "decisions": [],
            "convergence": {},
            "ciPerformance": [],
            "postMergeItems": [],
            "factoryHistory": None,
        }
        result = render_sidebar_section_nav(data)
        assert 'class="sb-nav-icon empty"' in result

    def test_specs_scenarios_icon_fail_when_failing(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        # 1 failing scenario → ✗
        assert 'class="sb-nav-icon fail"' in result

    def test_specs_scenarios_icon_empty_no_scenarios(self):
        data = {
            "architecture": {"zones": []},
            "whatChanged": {"defaultSummary": {}},
            "scenarios": [],
            "agenticReview": {"findings": []},
            "decisions": [],
            "convergence": {},
            "ciPerformance": [],
            "postMergeItems": [],
            "factoryHistory": None,
        }
        result = render_sidebar_section_nav(data, has_scenarios=False)
        assert 'class="sb-nav-icon empty"' in result

    def test_factory_history_icon_shows_iteration_count(
        self,
        sample_review_pack_data,
        sample_factory_history,
    ):
        data = {**sample_review_pack_data, "factoryHistory": sample_factory_history}
        result = render_sidebar_section_nav(data)
        # 3 iterations → count badge with "3"
        assert ">3<" in result


# ── Sidebar pill dedup, tooltips, descriptive names ────────────────


class TestSidebarPillDedup:
    def test_no_ci_in_status_badges(self):
        """CI badge should NOT appear in status badges — covered by Gate 1 pill."""
        header = {
            "statusBadges": [
                {"label": "CI 4/4", "type": "pass", "icon": "✓"},
                {"label": "3/3 comments resolved", "type": "pass", "icon": "✓"},
            ]
        }
        result = render_sidebar_status_badges(header)
        assert "CI 4/4" not in result
        assert "comments resolved" in result

    def test_no_gate0_in_status_badges(self):
        """Gate 0 badge should NOT appear in status badges — covered by Gate 0 pill."""
        header = {
            "statusBadges": [
                {"label": "Gate 0: 0 critical, 2 warn", "type": "pass", "icon": "✓"},
                {"label": "CI 4/4", "type": "pass", "icon": "✓"},
                {"label": "3/3 comments resolved", "type": "pass", "icon": "✓"},
            ]
        }
        result = render_sidebar_status_badges(header)
        assert "Gate 0" not in result

    def test_gate_pills_have_descriptive_names(self):
        """Gate pills should include the descriptor, not just 'Gate 1'."""
        convergence = {
            "gates": [
                {"name": "Gate 1 \u2014 CI", "status": "passing", "statusText": "4/4 checks passing"},
                {
                    "name": "Gate 2 \u2014 Deterministic",
                    "status": "passing",
                    "statusText": "Not run",
                },
            ]
        }
        result = render_sidebar_gate_pills(convergence)
        assert "CI" in result
        assert "Deterministic" in result

    def test_gate_pills_have_tooltips_with_status(self):
        """Gate pills should have title attribute with gate name and status text."""
        convergence = {
            "gates": [
                {"name": "Gate 1 \u2014 CI", "status": "passing", "statusText": "4/4 checks passing"},
            ]
        }
        result = render_sidebar_gate_pills(convergence)
        assert "title=" in result
        assert "4/4 checks passing" in result
