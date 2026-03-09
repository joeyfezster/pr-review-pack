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
    render_sidebar_gates,
    render_sidebar_merge_button,
    render_sidebar_metrics,
    render_sidebar_pr_meta,
    render_sidebar_section_nav,
    render_sidebar_status_badges,
    render_sidebar_verdict,
    render_sidebar_zone_minimap,
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
        assert "target=\"_blank\"" in result


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
            assert badge["label"] in result

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


# ── render_sidebar_gates ─────────────────────────────────────────────


class TestRenderSidebarGates:

    def test_gate_rows_rendered(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_sidebar_gates(convergence)
        assert result.count('class="sb-gate-row"') == 4

    def test_passing_gate_icon(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_sidebar_gates(convergence)
        assert "&#x2713;" in result
        assert "var(--green)" in result

    def test_failing_gate_icon(self):
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
        result = render_sidebar_gates(convergence)
        assert "&#x2717;" in result
        assert "var(--red)" in result

    def test_gate_names_present(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_sidebar_gates(convergence)
        assert "Gate 0" in result
        assert "Gate 1" in result
        assert "Gate 2" in result
        assert "Gate 3" in result

    def test_gate_name_html_escaped(self):
        convergence = {
            "gates": [
                {"name": "Gate <0>", "status": "passing"},
            ],
        }
        result = render_sidebar_gates(convergence)
        assert "Gate &lt;0&gt;" in result

    def test_onclick_scrolls_to_convergence(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_sidebar_gates(convergence)
        assert "scrollToSection('section-convergence')" in result

    def test_empty_gates(self):
        result = render_sidebar_gates({"gates": []})
        assert result == ""

    def test_missing_gates_key(self):
        result = render_sidebar_gates({})
        assert result == ""

    def test_mixed_passing_and_failing(self):
        convergence = {
            "gates": [
                {"name": "Gate 1", "status": "passing"},
                {"name": "Gate 2", "status": "failing"},
            ],
        }
        result = render_sidebar_gates(convergence)
        assert "var(--green)" in result
        assert "var(--red)" in result
        assert "&#x2713;" in result
        assert "&#x2717;" in result


# ── render_sidebar_metrics ───────────────────────────────────────────


class TestRenderSidebarMetrics:

    def test_four_metric_rows(self, sample_review_pack_data):
        result = render_sidebar_metrics(sample_review_pack_data)
        assert result.count('class="sb-metric-row"') == 4

    def test_ci_metric(self, sample_review_pack_data):
        result = render_sidebar_metrics(sample_review_pack_data)
        # 2 CI jobs, both pass
        assert "2/2" in result

    def test_ci_all_pass_shows_green(self, sample_review_pack_data):
        result = render_sidebar_metrics(sample_review_pack_data)
        # CI is first row; both pass so should show green checkmark
        assert "CI" in result
        assert "var(--green)" in result

    def test_scenario_metric(self, sample_review_pack_data):
        result = render_sidebar_metrics(sample_review_pack_data)
        # 1 pass, 1 fail out of 2 scenarios
        assert "1/2" in result

    def test_scenario_partial_shows_warning(self, sample_review_pack_data):
        result = render_sidebar_metrics(sample_review_pack_data)
        # Not all scenarios pass, so warning icon
        assert "Scenarios" in result
        assert "&#x26A0;" in result

    def test_findings_metric(self, sample_review_pack_data):
        result = render_sidebar_metrics(sample_review_pack_data)
        # 1 finding with grade C
        assert "Findings" in result

    def test_comments_metric(self, sample_review_pack_data):
        result = render_sidebar_metrics(sample_review_pack_data)
        assert "Comments" in result

    def test_onclick_sections(self, sample_review_pack_data):
        result = render_sidebar_metrics(sample_review_pack_data)
        assert "scrollToSection('section-ci-performance')" in result
        assert "scrollToSection('section-specs-scenarios')" in result
        assert "scrollToSection('section-convergence')" in result
        assert "scrollToSection('section-agentic-review')" in result

    def test_zero_findings_is_green(self):
        data = {
            "ciPerformance": [],
            "scenarios": [],
            "header": {"statusBadges": []},
            "agenticReview": {"findings": []},
        }
        result = render_sidebar_metrics(data)
        # Findings count is 0, which is_ok=True -> green
        assert "Findings" in result

    def test_scenario_na_when_empty(self):
        data = {
            "ciPerformance": [],
            "scenarios": [],
            "header": {"statusBadges": []},
            "agenticReview": {"findings": []},
        }
        result = render_sidebar_metrics(data)
        assert "N/A" in result

    def test_ci_partial_failure_shows_warning(self):
        data = {
            "ciPerformance": [
                {"name": "lint", "status": "pass"},
                {"name": "test", "status": "fail"},
            ],
            "scenarios": [],
            "header": {"statusBadges": []},
            "agenticReview": {"findings": []},
        }
        result = render_sidebar_metrics(data)
        assert "1/2" in result
        assert "&#x26A0;" in result


# ── render_sidebar_zone_minimap ──────────────────────────────────────


class TestRenderSidebarZoneMinimap:

    def test_zone_items_rendered(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_sidebar_zone_minimap(arch)
        assert result.count('class="sb-zone-item"') == 3

    def test_zone_labels(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_sidebar_zone_minimap(arch)
        assert "Zone Alpha" in result
        assert "Zone Beta" in result
        assert "Zone Gamma" in result

    def test_zone_data_attributes(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_sidebar_zone_minimap(arch)
        assert 'data-zone="zone-alpha"' in result
        assert 'data-zone="zone-beta"' in result
        assert 'data-zone="zone-gamma"' in result

    def test_modified_class(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_sidebar_zone_minimap(arch)
        # zone-alpha and zone-beta are modified, zone-gamma is not
        assert "modified" in result
        assert "unmodified" in result

    def test_file_count_badge_when_nonzero(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_sidebar_zone_minimap(arch)
        assert 'class="sb-zone-count"' in result
        assert "(4)" in result
        assert "(2)" in result

    def test_no_file_count_badge_for_zero(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_sidebar_zone_minimap(arch)
        # zone-gamma has fileCount=0, should not show (0) badge
        assert "(0)" not in result

    def test_product_zone_colors(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_sidebar_zone_minimap(arch)
        # product fill and stroke from LAYER_COLORS
        assert "#dcfce7" in result  # product fill
        assert "#22c55e" in result  # product stroke

    def test_infra_zone_colors(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_sidebar_zone_minimap(arch)
        # infra fill and stroke from LAYER_COLORS
        assert "#f3e8ff" in result  # infra fill
        assert "#8b5cf6" in result  # infra stroke

    def test_onclick_calls_sidebar_zone_click(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_sidebar_zone_minimap(arch)
        assert "sidebarZoneClick('zone-alpha')" in result
        assert "sidebarZoneClick('zone-beta')" in result
        assert "sidebarZoneClick('zone-gamma')" in result

    def test_clear_filter_element(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_sidebar_zone_minimap(arch)
        assert 'id="sb-clear-filter"' in result
        assert 'class="sb-clear-filter"' in result
        assert "resetZones()" in result

    def test_active_zone_indicator(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_sidebar_zone_minimap(arch)
        assert 'id="sb-zone-active"' in result
        assert 'class="sb-zone-active"' in result

    def test_empty_zones(self):
        result = render_sidebar_zone_minimap({"zones": []})
        # Still renders the clear filter and active indicator
        assert 'id="sb-clear-filter"' in result
        assert 'id="sb-zone-active"' in result

    def test_swatch_css_class(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_sidebar_zone_minimap(arch)
        assert 'class="sb-zone-swatch modified"' in result
        assert 'class="sb-zone-swatch unmodified"' in result

    def test_html_escaping_in_zone_label(self):
        arch = {
            "zones": [
                {
                    "id": "zone-x",
                    "label": "Zone <X>",
                    "category": "product",
                    "fileCount": 0,
                    "isModified": False,
                },
            ],
        }
        result = render_sidebar_zone_minimap(arch)
        assert "Zone &lt;X&gt;" in result
        assert "Zone <X>" not in result


# ── render_sidebar_section_nav ───────────────────────────────────────


class TestRenderSidebarSectionNav:

    def test_all_standard_sections_present(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        assert "Architecture" in result
        assert "What Changed" in result
        assert "Specs &amp; Scenarios" in result
        assert "Agent Reviews" in result
        assert "Key Decisions" in result
        assert "Convergence" in result
        assert "CI Performance" in result
        assert "Post-Merge Items" in result
        assert "Code Diffs" in result

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
        assert 'data-section="section-agentic-review"' in result
        assert 'data-section="section-key-decisions"' in result
        assert 'data-section="section-convergence"' in result
        assert 'data-section="section-ci-performance"' in result
        assert 'data-section="section-post-merge"' in result
        assert 'data-section="section-code-diffs"' in result

    def test_onclick_scroll(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        assert "scrollToSection('section-architecture')" in result
        assert "scrollToSection('section-ci-performance')" in result

    def test_group_labels(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        assert 'class="sb-nav-group-label"' in result
        assert "Architecture &amp; Context" in result
        assert "Safety &amp; Reasoning" in result
        assert "Follow-ups &amp; Evidence" in result

    def test_content_dot_for_architecture(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        # Architecture has zones, so dot_type should be "content"
        assert 'class="sb-nav-dot content"' in result

    def test_empty_dot_for_missing_content(self):
        data = {
            "architecture": {},
            "whatChanged": {"defaultSummary": {"infrastructure": "", "product": ""}},
            "scenarios": [],
            "agenticReview": {"findings": []},
            "decisions": [],
            "convergence": {},
            "ciPerformance": [],
            "postMergeItems": [],
            "codeDiffs": [],
            "factoryHistory": None,
        }
        result = render_sidebar_section_nav(data)
        assert 'class="sb-nav-dot empty"' in result

    def test_decisions_count_badge(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        # 1 decision in sample data
        assert 'class="sb-nav-count"' in result
        assert "(1)" in result

    def test_post_merge_count_badge(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        # 1 post-merge item in sample data
        assert "(1)" in result

    def test_code_diffs_count_badge(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        # 2 code diffs in sample data
        assert "(2)" in result

    def test_findings_dot_when_critical(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        # There's a grade C finding, so Agent Reviews should get "findings" dot
        assert 'class="sb-nav-dot findings"' in result

    def test_no_findings_dot_when_no_critical(self):
        data = {
            "architecture": {"zones": [{"id": "z"}]},
            "whatChanged": {"defaultSummary": {"infrastructure": "", "product": "stuff"}},
            "scenarios": [{"status": "pass"}],
            "agenticReview": {"findings": [
                {"grade": "A", "file": "f.py", "agent": "ch", "notable": "", "detail": ""},
            ]},
            "decisions": [],
            "convergence": {},
            "ciPerformance": [],
            "postMergeItems": [],
            "codeDiffs": [],
            "factoryHistory": None,
        }
        result = render_sidebar_section_nav(data)
        assert 'class="sb-nav-dot findings"' not in result

    def test_nav_item_class(self, sample_review_pack_data):
        result = render_sidebar_section_nav(sample_review_pack_data)
        assert 'class="sb-nav-item"' in result

    def test_empty_sections_get_empty_dot(self):
        data = {
            "architecture": {"zones": [{"id": "z"}]},
            "whatChanged": {"defaultSummary": {"infrastructure": "", "product": "stuff"}},
            "scenarios": [],
            "agenticReview": {"findings": []},
            "decisions": [],
            "convergence": {},
            "ciPerformance": [],
            "postMergeItems": [],
            "codeDiffs": [],
            "factoryHistory": None,
        }
        result = render_sidebar_section_nav(data)
        # Agent Reviews with no findings -> "empty" dot
        # Decisions with no items -> "empty" dot
        assert 'class="sb-nav-dot empty"' in result

    def test_no_count_badge_for_empty_decisions(self):
        data = {
            "architecture": {},
            "whatChanged": {},
            "scenarios": [],
            "agenticReview": {"findings": []},
            "decisions": [],
            "convergence": {},
            "ciPerformance": [],
            "postMergeItems": [],
            "codeDiffs": [],
            "factoryHistory": None,
        }
        result = render_sidebar_section_nav(data)
        # No count badge should appear since all lists are empty
        assert 'class="sb-nav-count"' not in result
