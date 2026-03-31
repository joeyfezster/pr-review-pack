"""Tests for ALL v1 render functions in render_review_pack.py.

Each test exercises a specific render function with real fixture data
and checks for concrete HTML output: class names, data attributes,
content strings, and structural elements.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from render_review_pack import (
    render_agentic_legend,
    render_agentic_method_badge,
    render_agentic_rows,
    render_architecture_legend,
    render_architecture_svg,
    render_ci_rows,
    render_convergence_grid,
    render_decision_cards,
    render_factory_history_tab_button,
    render_gate_findings_rows,
    render_history_summary_cards,
    render_history_timeline,
    render_key_findings,
    render_post_merge_items,
    render_review_gates_cards,
    render_scenario_cards,
    render_scenario_legend,
    render_spec_list,
    render_stat_items,
    render_status_badges,
    render_what_changed_default,
    render_what_changed_zones,
)

# ── render_stat_items ─────────────────────────────────────────────────


class TestRenderStatItems:
    def test_additions_green(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_stat_items(header)
        assert 'class="stat green"' in result
        assert "+150" in result

    def test_deletions_red(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_stat_items(header)
        assert 'class="stat red"' in result
        assert "&minus;30" in result

    def test_file_count(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_stat_items(header)
        assert ">8</span> files" in result

    def test_commit_count_plural(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_stat_items(header)
        assert ">3</span> commits" in result

    def test_commit_count_singular(self):
        header = {"commits": 1, "additions": 0, "deletions": 0, "filesChanged": 0}
        result = render_stat_items(header)
        assert ">1</span> commit<" in result
        assert "commits" not in result


# ── render_status_badges ──────────────────────────────────────────────


class TestRenderStatusBadges:
    def test_badge_type_class(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_status_badges(header)
        assert 'class="status-badge pass"' in result

    def test_badge_label_text(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_status_badges(header)
        assert "Gate 0: 0 critical, 2 warn" in result
        assert "CI 4/4" in result

    def test_badge_icon(self, sample_review_pack_data):
        header = sample_review_pack_data["header"]
        result = render_status_badges(header)
        # The checkmark icon should be present
        assert "\u2713" in result

    def test_empty_badges(self):
        result = render_status_badges({"statusBadges": []})
        assert result == ""


# ── render_factory_history_tab_button ─────────────────────────────────


class TestRenderFactoryHistoryTabButton:
    def test_present_when_factory_history_exists(self, sample_factory_history):
        data = {"factoryHistory": sample_factory_history}
        result = render_factory_history_tab_button(data)
        assert 'class="tab-btn"' in result
        assert "Factory History" in result
        assert "switchTab" in result

    def test_empty_when_none(self):
        result = render_factory_history_tab_button({"factoryHistory": None})
        assert result == ""

    def test_empty_when_missing(self):
        result = render_factory_history_tab_button({})
        assert result == ""


# ── render_architecture_svg ───────────────────────────────────────────


class TestRenderArchitectureSvg:
    def test_zone_box_elements(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_architecture_svg(arch)
        assert 'class="zone-box"' in result
        assert 'data-zone="zone-alpha"' in result
        assert 'data-zone="zone-beta"' in result
        assert 'data-zone="zone-gamma"' in result

    def test_zone_labels(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_architecture_svg(arch)
        assert "Zone Alpha" in result
        assert "Zone Beta" in result
        assert "Zone Gamma" in result

    def test_arrows(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_architecture_svg(arch)
        assert "marker-end" in result
        assert "url(#arrowhead)" in result

    def test_file_count_badges(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_architecture_svg(arch)
        # zone-alpha has fileCount=4, zone-beta has fileCount=2
        assert 'class="zone-file-count"' in result
        assert ">4<" in result
        assert ">2<" in result

    def test_opacity_for_unmodified(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_architecture_svg(arch)
        # zone-gamma is not modified, so opacity should be 0.6
        assert "opacity:0.6" in result
        # zone-alpha is modified, opacity should be 1
        assert "opacity:1" in result

    def test_arrowhead_marker_defined(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_architecture_svg(arch)
        assert 'id="arrowhead"' in result
        assert "<defs>" in result

    def test_row_labels(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_architecture_svg(arch)
        assert 'class="arch-row-label"' in result
        assert "PRODUCT CODE" in result
        assert "INFRA" in result

    def test_sublabels(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_architecture_svg(arch)
        assert 'class="zone-sublabel"' in result
        assert "Primary component" in result

    def test_no_badge_for_zero_file_count(self, sample_review_pack_data):
        arch = sample_review_pack_data["architecture"]
        result = render_architecture_svg(arch)
        # zone-gamma has fileCount=0, should NOT render a badge circle for it
        # Count zone-count-bg circles — should be 2 (alpha=4, beta=2), not 3
        assert result.count('class="zone-count-bg"') == 2


# ── render_spec_list ──────────────────────────────────────────────────


class TestRenderSpecList:
    def test_file_path_links(self, sample_review_pack_data):
        specs = sample_review_pack_data["specs"]
        result = render_spec_list(specs)
        assert 'class="file-path-link"' in result
        assert "specs/alpha_spec.md" in result
        assert "specs/beta_spec.md" in result

    def test_descriptions(self, sample_review_pack_data):
        specs = sample_review_pack_data["specs"]
        result = render_spec_list(specs)
        assert "Alpha component specification" in result
        assert "Beta component specification" in result

    def test_list_items(self, sample_review_pack_data):
        specs = sample_review_pack_data["specs"]
        result = render_spec_list(specs)
        assert "<li>" in result

    def test_empty_specs(self):
        result = render_spec_list([])
        assert result == ""


# ── render_scenario_legend ────────────────────────────────────────────


class TestRenderScenarioLegend:
    def test_category_classes_rendered(self, sample_review_pack_data):
        scenarios = sample_review_pack_data["scenarios"]
        result = render_scenario_legend(scenarios)
        # categories: "integration" and "pipeline"
        assert "scenario-category" in result
        assert "cat-integration" in result
        assert "cat-pipeline" in result

    def test_category_text(self, sample_review_pack_data):
        scenarios = sample_review_pack_data["scenarios"]
        result = render_scenario_legend(scenarios)
        assert "integration" in result
        assert "pipeline" in result


# ── render_scenario_cards ─────────────────────────────────────────────


class TestRenderScenarioCards:
    def test_status_icons(self, sample_review_pack_data):
        scenarios = sample_review_pack_data["scenarios"]
        result = render_scenario_cards(scenarios)
        # "pass" → checkmark, "fail" → cross
        assert "&#x2713;" in result  # checkmark for pass
        assert "&#x2717;" in result  # cross for fail

    def test_zone_data_attributes(self, sample_review_pack_data):
        scenarios = sample_review_pack_data["scenarios"]
        result = render_scenario_cards(scenarios)
        assert 'data-zone="zone-alpha"' in result
        assert 'data-zone="zone-beta"' in result

    def test_detail_blocks(self, sample_review_pack_data):
        scenarios = sample_review_pack_data["scenarios"]
        result = render_scenario_cards(scenarios)
        assert "scenario-card-detail" in result
        assert "<dt>What</dt>" in result
        assert "<dt>How</dt>" in result
        assert "<dt>Result</dt>" in result

    def test_scenario_names(self, sample_review_pack_data):
        scenarios = sample_review_pack_data["scenarios"]
        result = render_scenario_cards(scenarios)
        assert "Alpha processes input correctly" in result
        assert "Beta handles edge case" in result

    def test_scenario_card_class(self, sample_review_pack_data):
        scenarios = sample_review_pack_data["scenarios"]
        result = render_scenario_cards(scenarios)
        assert 'class="scenario-card"' in result

    def test_string_detail(self):
        scenarios = [
            {
                "name": "Simple scenario",
                "category": "integration",
                "status": "pass",
                "zone": "zone-alpha",
                "detail": "Everything works fine.",
            }
        ]
        result = render_scenario_cards(scenarios)
        assert "<p>Everything works fine.</p>" in result


# ── render_what_changed_default ───────────────────────────────────────


class TestRenderWhatChangedDefault:
    def test_infrastructure_rendered_as_div(self, sample_review_pack_data):
        wc = sample_review_pack_data["whatChanged"]
        result = render_what_changed_default(wc)
        assert '<div class="wc-summary"><strong>Infrastructure:</strong>' in result
        assert "Updated deployment scripts" in result

    def test_product_rendered_as_div(self, sample_review_pack_data):
        wc = sample_review_pack_data["whatChanged"]
        result = render_what_changed_default(wc)
        assert '<div class="wc-summary"><strong>Product:</strong>' in result
        assert "Added feature X to zone-alpha" in result

    def test_html_content_not_escaped(self, sample_review_pack_data):
        wc = sample_review_pack_data["whatChanged"]
        result = render_what_changed_default(wc)
        # HTML tags should render as-is, not escaped
        assert "<strong>zone-gamma</strong>" in result
        assert "&lt;strong&gt;" not in result

    def test_empty_infrastructure(self):
        wc = {"defaultSummary": {"infrastructure": "", "product": "Some product change."}}
        result = render_what_changed_default(wc)
        assert "Infrastructure" not in result
        assert "Some product change." in result

    def test_empty_both(self):
        wc = {"defaultSummary": {"infrastructure": "", "product": ""}}
        result = render_what_changed_default(wc)
        assert result == ""


# ── render_what_changed_zones ─────────────────────────────────────────


class TestRenderWhatChangedZones:
    def test_zone_detail_divs(self, sample_review_pack_data):
        wc = sample_review_pack_data["whatChanged"]
        result = render_what_changed_zones(wc)
        assert 'class="wc-zone-detail"' in result
        assert 'data-zone="zone-alpha"' in result
        assert 'data-zone="zone-beta"' in result

    def test_zone_titles(self, sample_review_pack_data):
        wc = sample_review_pack_data["whatChanged"]
        result = render_what_changed_zones(wc)
        assert "Zone Alpha Changes" in result
        assert "Zone Beta Changes" in result

    def test_zone_descriptions_html_not_escaped(self, sample_review_pack_data):
        wc = sample_review_pack_data["whatChanged"]
        result = render_what_changed_zones(wc)
        # HTML tags in descriptions should render as-is
        assert "<strong>feature X</strong>" in result
        assert "&lt;strong&gt;" not in result

    def test_zone_descriptions_wrapped_in_div(self, sample_review_pack_data):
        wc = sample_review_pack_data["whatChanged"]
        result = render_what_changed_zones(wc)
        # Descriptions should be in <div>, not <p>, to avoid nesting issues
        assert "<div><p>" in result
        assert "</p></div>" in result

    def test_empty_zone_details(self):
        wc = {"zoneDetails": []}
        result = render_what_changed_zones(wc)
        assert result == ""


# ── render_agentic_method_badge ───────────────────────────────────────


class TestRenderAgenticMethodBadge:
    def test_agent_teams_badge(self, sample_review_pack_data):
        review = sample_review_pack_data["agenticReview"]
        result = render_agentic_method_badge(review)
        assert "agent-teams" in result
        assert "Agent Teams" in result

    def test_main_agent_badge(self):
        review = {"reviewMethod": "main-agent"}
        result = render_agentic_method_badge(review)
        assert "main-agent" in result
        assert "Main Agent" in result

    def test_default_main_agent(self):
        review = {}
        result = render_agentic_method_badge(review)
        assert "main-agent" in result
        assert "Main Agent" in result


# ── render_agentic_legend ─────────────────────────────────────────────


class TestRenderAgenticLegend:
    def test_four_agent_abbreviations(self):
        result = render_agentic_legend()
        assert "CH" in result
        assert "SE" in result
        assert "TI" in result
        assert "AD" in result

    def test_agent_names(self):
        result = render_agentic_legend()
        assert "Code Health" in result
        assert "Security" in result
        assert "Test Integrity" in result
        assert "Adversarial" in result

    def test_legend_container(self):
        result = render_agentic_legend()
        assert 'class="agent-legend"' in result
        assert 'class="agent-legend-item"' in result

    def test_tooltip_descriptions(self):
        result = render_agentic_legend()
        assert "code quality" in result
        assert "vulnerabilities" in result


# ── render_agentic_rows ───────────────────────────────────────────────


class TestRenderAgenticRows:
    def test_grouped_by_file(self, sample_review_pack_data):
        review = sample_review_pack_data["agenticReview"]
        result = render_agentic_rows(review)
        # Two files have findings: src/alpha/core.py (CH, SE) and src/models.py (RB)
        assert result.count('class="adv-row"') == 2
        assert "src/alpha/core.py" in result
        assert "src/models.py" in result

    def test_agent_badges(self, sample_review_pack_data):
        review = sample_review_pack_data["agenticReview"]
        result = render_agentic_rows(review)
        assert 'class="agent-grade-badge"' in result
        assert 'class="agent-abbrev"' in result
        assert ">CH<" in result  # code-health abbreviation
        assert ">SE<" in result  # security abbreviation

    def test_grade_css_classes(self, sample_review_pack_data):
        review = sample_review_pack_data["agenticReview"]
        result = render_agentic_rows(review)
        assert 'class="grade a"' in result  # grade A
        assert 'class="grade c"' in result  # grade C

    def test_detail_rows(self, sample_review_pack_data):
        review = sample_review_pack_data["agenticReview"]
        result = render_agentic_rows(review)
        assert 'class="adv-detail-row"' in result
        assert "agent-detail-entry" in result
        assert "agent-detail-body" in result

    def test_empty_findings(self):
        result = render_agentic_rows({"findings": []})
        assert result == ""

    def test_zone_data_attribute(self, sample_review_pack_data):
        review = sample_review_pack_data["agenticReview"]
        result = render_agentic_rows(review)
        assert 'data-zones="zone-alpha"' in result

    def test_file_path_link(self, sample_review_pack_data):
        review = sample_review_pack_data["agenticReview"]
        result = render_agentic_rows(review)
        assert 'class="file-path-link"' in result
        assert "openFileModal" in result


# ── render_ci_rows ────────────────────────────────────────────────────


class TestRenderCiRows:
    def test_expandable_rows(self, sample_review_pack_data):
        ci = sample_review_pack_data["ciPerformance"]
        result = render_ci_rows(ci)
        assert 'class="expandable"' in result
        assert "toggleCIDetail" in result

    def test_status_badges(self, sample_review_pack_data):
        ci = sample_review_pack_data["ciPerformance"]
        result = render_ci_rows(ci)
        assert 'class="badge pass"' in result

    def test_health_tags(self, sample_review_pack_data):
        ci = sample_review_pack_data["ciPerformance"]
        result = render_ci_rows(ci)
        assert 'class="time-label normal"' in result  # 45s → normal
        assert 'class="time-label acceptable"' in result  # 135s → acceptable

    def test_time_labels(self, sample_review_pack_data):
        ci = sample_review_pack_data["ciPerformance"]
        result = render_ci_rows(ci)
        assert "45s" in result
        assert "2m 15s" in result

    def test_ci_names(self, sample_review_pack_data):
        ci = sample_review_pack_data["ciPerformance"]
        result = render_ci_rows(ci)
        assert "lint-and-type-check" in result
        assert "test-suite" in result

    def test_detail_rows(self, sample_review_pack_data):
        ci = sample_review_pack_data["ciPerformance"]
        result = render_ci_rows(ci)
        assert 'class="detail-row"' in result
        assert "<strong>Coverage:</strong>" in result
        assert "<strong>Gates:</strong>" in result

    def test_sub_checks(self, sample_review_pack_data):
        ci = sample_review_pack_data["ciPerformance"]
        result = render_ci_rows(ci)
        assert "ci-check-item" in result
        assert "ruff check" in result
        assert "mypy" in result

    def test_zone_tags_in_detail(self, sample_review_pack_data):
        ci = sample_review_pack_data["ciPerformance"]
        result = render_ci_rows(ci)
        assert 'class="zone-tag product"' in result
        assert "zone-alpha" in result

    def test_notes_rendering(self, sample_review_pack_data):
        ci = sample_review_pack_data["ciPerformance"]
        result = render_ci_rows(ci)
        assert "All checks green." in result

    def test_empty_ci(self):
        result = render_ci_rows([])
        assert result == ""


# ── render_decision_cards ─────────────────────────────────────────────


class TestRenderDecisionCards:
    def test_decision_card_structure(self, sample_review_pack_data):
        decisions = sample_review_pack_data["decisions"]
        result = render_decision_cards(decisions)
        assert 'class="decision-card"' in result
        assert 'data-zones="zone-alpha zone-beta"' in result

    def test_verified_flag(self, sample_review_pack_data):
        decisions = sample_review_pack_data["decisions"]
        result = render_decision_cards(decisions)
        # verified=True means no UNVERIFIED marker
        assert "[UNVERIFIED]" not in result

    def test_unverified_flag(self):
        decisions = [
            {
                "number": 1,
                "title": "Unverified decision",
                "rationale": "Reason",
                "body": "",
                "zones": "zone-alpha",
                "verified": False,
                "files": [],
            },
        ]
        result = render_decision_cards(decisions)
        assert "[UNVERIFIED]" in result

    def test_file_tables(self, sample_review_pack_data):
        decisions = sample_review_pack_data["decisions"]
        result = render_decision_cards(decisions)
        assert "src/alpha/core.py" in result
        assert "Async handler added" in result
        assert "<th>File</th>" in result
        assert "<th>Change</th>" in result

    def test_decision_title_and_rationale(self, sample_review_pack_data):
        decisions = sample_review_pack_data["decisions"]
        result = render_decision_cards(decisions)
        assert "Use async handlers for feature X" in result
        assert "Improves throughput under concurrent load." in result

    def test_zone_tags(self, sample_review_pack_data):
        decisions = sample_review_pack_data["decisions"]
        result = render_decision_cards(decisions)
        assert 'class="zone-tag product"' in result
        assert "zone-alpha" in result
        assert "zone-beta" in result

    def test_empty_decisions(self):
        result = render_decision_cards([])
        assert result == ""


# ── render_convergence_grid ───────────────────────────────────────────


class TestRenderConvergenceGrid:
    def test_conv_card_elements(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_convergence_grid(convergence)
        assert 'class="conv-card"' in result

    def test_status_classes(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_convergence_grid(convergence)
        assert 'class="conv-status passing"' in result

    def test_overall_card(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_convergence_grid(convergence)
        assert "Overall" in result
        assert "READY TO MERGE" in result

    def test_gate_names(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_convergence_grid(convergence)
        assert "Gate 0" in result
        assert "Gate 1" in result
        assert "Gate 2" in result
        assert "Gate 3" in result
        assert "Gate 4" in result

    def test_gate_count(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_convergence_grid(convergence)
        # 5 gates + 1 overall = 6 conv-card elements
        assert result.count('class="conv-card"') == 6

    def test_failing_gate(self):
        convergence = {
            "gates": [
                {
                    "name": "Gate 1",
                    "status": "failing",
                    "statusText": "FAILING",
                    "summary": "Lint errors found.",
                    "detail": "",
                }
            ],
            "overall": {},
        }
        result = render_convergence_grid(convergence)
        assert 'class="conv-status failing"' in result


# ── render_post_merge_items ───────────────────────────────────────────


class TestRenderPostMergeItems:
    def test_pm_item_structure(self, sample_review_pack_data):
        items = sample_review_pack_data["postMergeItems"]
        result = render_post_merge_items(items)
        assert 'class="pm-item"' in result

    def test_priority(self, sample_review_pack_data):
        items = sample_review_pack_data["postMergeItems"]
        result = render_post_merge_items(items)
        assert 'class="priority medium"' in result
        assert "MEDIUM" in result

    def test_code_snippets(self, sample_review_pack_data):
        items = sample_review_pack_data["postMergeItems"]
        result = render_post_merge_items(items)
        assert 'class="code-block"' in result
        assert "src/alpha/core.py" in result
        assert "L45-L60" in result
        assert "async def handle_request" in result

    def test_scenario_boxes(self, sample_review_pack_data):
        items = sample_review_pack_data["postMergeItems"]
        result = render_post_merge_items(items)
        assert 'class="scenario-box failure"' in result
        assert 'class="scenario-box success"' in result
        assert "Failure scenario" in result
        assert "Resolution" in result
        assert "Latency spikes" in result
        assert "Dashboard alerts" in result

    def test_zone_tags(self, sample_review_pack_data):
        items = sample_review_pack_data["postMergeItems"]
        result = render_post_merge_items(items)
        assert 'class="zone-tag product"' in result
        assert "zone-alpha" in result

    def test_item_without_code_snippet(self):
        items = [
            {
                "title": "Simple followup",
                "priority": "low",
                "description": "Track this metric.",
                "failureScenario": "Untracked.",
                "successScenario": "Tracked.",
                "zones": ["zone-beta"],
            },
        ]
        result = render_post_merge_items(items)
        assert "code-block" not in result
        assert "Simple followup" in result

    def test_empty_items(self):
        result = render_post_merge_items([])
        assert result == ""


# ── render_history_summary_cards ──────────────────────────────────────


class TestRenderHistorySummaryCards:
    def test_iteration_count(self, sample_factory_history):
        result = render_history_summary_cards(sample_factory_history)
        assert "Iterations" in result
        assert "3" in result

    def test_satisfaction(self, sample_factory_history):
        result = render_history_summary_cards(sample_factory_history)
        assert "Satisfaction" in result
        assert "60% -&gt; 80% -&gt; 100%" in result

    def test_card_structure(self, sample_factory_history):
        result = render_history_summary_cards(sample_factory_history)
        assert 'class="conv-card"' in result
        # Should render 2 cards: Iterations and Satisfaction
        assert result.count('class="conv-card"') == 2

    def test_satisfaction_detail(self, sample_factory_history):
        result = render_history_summary_cards(sample_factory_history)
        assert "Converged after 3 iterations." in result


# ── render_history_timeline ───────────────────────────────────────────


class TestRenderHistoryTimeline:
    def test_timeline_events(self, sample_factory_history):
        events = sample_factory_history["timeline"]
        result = render_history_timeline(events)
        assert 'class="history-event' in result
        assert "Iteration 1 started" in result
        assert "Human review requested" in result

    def test_intervention_class(self, sample_factory_history):
        events = sample_factory_history["timeline"]
        result = render_history_timeline(events)
        assert "intervention" in result

    def test_agent_labels(self, sample_factory_history):
        events = sample_factory_history["timeline"]
        result = render_history_timeline(events)
        assert "Codex" in result
        assert "Joey" in result
        assert "Factory" in result

    def test_human_agent_class(self, sample_factory_history):
        events = sample_factory_history["timeline"]
        result = render_history_timeline(events)
        assert 'class="event-agent human"' in result

    def test_event_detail(self, sample_factory_history):
        events = sample_factory_history["timeline"]
        result = render_history_timeline(events)
        assert "Initial code generation." in result
        assert "Spec clarification needed." in result


# ── render_gate_findings_rows ─────────────────────────────────────────


class TestRenderGateFindingsRows:
    def test_gate_table_rows(self, sample_factory_history):
        findings = sample_factory_history["gateFindings"]
        result = render_gate_findings_rows(findings)
        assert "<tr>" in result
        assert "Iteration 1" in result
        assert "Iteration 2" in result

    def test_badge_css(self, sample_factory_history):
        findings = sample_factory_history["gateFindings"]
        result = render_gate_findings_rows(findings)
        assert 'class="badge pass"' in result
        assert 'class="badge fail"' in result

    def test_popover_onclick(self, sample_factory_history):
        findings = sample_factory_history["gateFindings"]
        result = render_gate_findings_rows(findings)
        assert "showGatePopover" in result
        assert "gate-clickable" in result

    def test_action_column(self, sample_factory_history):
        findings = sample_factory_history["gateFindings"]
        result = render_gate_findings_rows(findings)
        assert "Continue" in result
        assert "Converged" in result

    def test_empty_popover_no_onclick(self):
        findings = [
            {
                "phase": "Phase 1",
                "phasePopover": "",
                "gate1": {"status": "pass", "label": "OK", "popover": ""},
                "gate2": {"status": "pass", "label": "OK", "popover": ""},
                "gate3": {"status": "pass", "label": "OK", "popover": ""},
                "action": "Done",
            },
        ]
        result = render_gate_findings_rows(findings)
        # With empty popovers, no gate-clickable class should appear
        assert "gate-clickable" not in result


# ── render_review_gates_cards ────────────────────────────────────────


class TestRenderReviewGatesCards:
    def test_gate_cards_rendered(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_review_gates_cards(convergence)
        assert result.count('class="gate-review-card"') == 5

    def test_gate_names(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_review_gates_cards(convergence)
        assert "Gate 0" in result
        assert "Gate 1" in result

    def test_data_gate_name_attribute(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_review_gates_cards(convergence)
        assert 'data-gate-name="Gate 0' in result

    def test_status_class(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_review_gates_cards(convergence)
        assert 'class="gate-status passing"' in result

    def test_failing_status_class(self):
        convergence = {
            "gates": [
                {
                    "name": "Gate 1",
                    "status": "failing",
                    "statusText": "FAILING",
                    "summary": "Errors.",
                    "detail": "",
                },
            ],
        }
        result = render_review_gates_cards(convergence)
        assert 'class="gate-status failing"' in result

    def test_summary_escaped(self):
        convergence = {
            "gates": [
                {
                    "name": "G",
                    "status": "passing",
                    "statusText": "OK",
                    "summary": "<script>alert(1)</script>",
                    "detail": "",
                },
            ],
        }
        result = render_review_gates_cards(convergence)
        assert "&lt;script&gt;" in result

    def test_onclick_toggles_open(self, sample_review_pack_data):
        convergence = sample_review_pack_data["convergence"]
        result = render_review_gates_cards(convergence)
        assert "this.classList.toggle('open')" in result

    def test_empty_gates(self):
        result = render_review_gates_cards({"gates": []})
        assert result == ""


# ── render_architecture_legend ──────────────────────────────────────


class TestArchitectureLegend:
    def test_legend_uses_data_categories(self):
        """Architecture legend should render categories from zone data, not hardcoded."""
        zones = [
            {"id": "z1", "category": "backend", "label": "API", "isModified": True},
            {"id": "z2", "category": "frontend", "label": "UI", "isModified": False},
        ]
        result = render_architecture_legend(zones)
        assert "Backend" in result
        assert "Frontend" in result
        assert "Factory" not in result

    def test_legend_no_duplicates(self):
        """Each category should appear once in the legend."""
        zones = [
            {"id": "z1", "category": "product", "label": "A"},
            {"id": "z2", "category": "product", "label": "B"},
            {"id": "z3", "category": "infra", "label": "C"},
        ]
        result = render_architecture_legend(zones)
        # "Product" should appear exactly once in legend items
        assert result.count("Product") == 1

    def test_legend_known_categories_use_fixed_colors(self):
        """Known categories (factory, product, infra) use predefined colors."""
        zones = [
            {"id": "z1", "category": "factory", "label": "F"},
            {"id": "z2", "category": "product", "label": "P"},
        ]
        result = render_architecture_legend(zones)
        assert "#dbeafe" in result  # factory fill
        assert "#dcfce7" in result  # product fill

    def test_legend_unknown_category_gets_hsl_color(self):
        """Unknown categories get deterministic HSL-based colors."""
        zones = [
            {"id": "z1", "category": "custom-layer", "label": "C"},
        ]
        result = render_architecture_legend(zones)
        assert "Custom Layer" in result
        assert "hsl(" in result

    def test_legend_empty_zones(self):
        """Empty zone list produces legend with only the circle hint."""
        result = render_architecture_legend([])
        assert "Blue circle" in result
        assert "arch-legend-swatch" not in result

    def test_legend_contains_click_hint(self):
        """Legend always includes the click-to-filter hint."""
        zones = [{"id": "z1", "category": "product", "label": "P"}]
        result = render_architecture_legend(zones)
        assert "Click zone to filter" in result


# ── render_key_findings agent legend ─────────────────────────────────


class TestKeyFindingsAgentLegend:
    """Key findings section must include the agent team legend."""

    def test_key_findings_has_agent_legend(self):
        """Legend with all agent abbreviations appears in key findings output."""
        data = {
            "agenticReview": {
                "overallGrade": "B+",
                "reviewMethod": "agent-teams",
                "findings": [
                    {
                        "file": "a.py",
                        "grade": "A",
                        "zones": "zone-a",
                        "notable": "Clean",
                        "detail": "Good",
                        "gradeSortOrder": 3,
                        "agent": "code-health",
                    },
                    {
                        "file": "b.py",
                        "grade": "B",
                        "zones": "zone-a",
                        "notable": "Warning",
                        "detail": "Minor",
                        "gradeSortOrder": 1,
                        "agent": "rbe",
                    },
                ],
            },
            "architecture": {"zones": [{"id": "zone-a", "category": "product"}]},
        }
        result = render_key_findings(data)
        assert "agent-legend" in result
        assert "CH" in result  # Code Health in legend
        assert "RB" in result  # RBE in legend

    def test_key_findings_legend_includes_all_agents(self):
        """Legend includes all 6 agent abbreviations regardless of which agents have findings."""
        data = {
            "agenticReview": {
                "overallGrade": "A",
                "findings": [
                    {
                        "file": "x.py",
                        "grade": "A",
                        "zones": "z",
                        "notable": "Ok",
                        "detail": "Fine",
                        "gradeSortOrder": 4,
                        "agent": "security",
                    },
                ],
            },
            "architecture": {"zones": [{"id": "z", "category": "product"}]},
        }
        result = render_key_findings(data)
        for abbrev in ("CH", "SE", "TI", "AD", "AR", "RB"):
            assert abbrev in result, f"Agent abbreviation {abbrev} missing from legend"


# ── Key Findings: Locations column ────────────────────────────────────


class TestKeyFindingsLocations:
    def test_locs_column_in_header(self):
        """Key findings table must have a Locs column header."""
        data = {
            "agenticReview": {
                "overallGrade": "B",
                "reviewMethod": "agent-teams",
                "findings": [
                    {
                        "file": "a.py",
                        "grade": "B",
                        "zones": "core",
                        "notable": "Test",
                        "detail": "<p>D</p>",
                        "gradeSortOrder": 1,
                        "agent": "adversarial",
                        "locations": [
                            {"file": "a.py", "lines": "10-20"},
                            {"file": "b.py", "lines": "42"},
                        ],
                    }
                ],
            },
            "architecture": {"zones": [{"id": "core", "category": "product"}]},
        }
        result = render_key_findings(data)
        assert "<th>" in result
        assert "Locs" in result

    def test_detail_shows_multiple_locations(self):
        """Expanded detail must list each location with file:lines."""
        data = {
            "agenticReview": {
                "overallGrade": "B",
                "reviewMethod": "agent-teams",
                "findings": [
                    {
                        "file": "a.py",
                        "grade": "B",
                        "zones": "core",
                        "notable": "Multi-location",
                        "detail": "<p>Spans files</p>",
                        "gradeSortOrder": 1,
                        "agent": "code-health",
                        "locations": [
                            {"file": "src/a.py", "lines": "10-20"},
                            {"file": "src/b.py", "lines": "42"},
                            {"file": "src/a.py", "lines": "55-60"},
                        ],
                    }
                ],
            },
            "architecture": {"zones": [{"id": "core", "category": "product"}]},
        }
        result = render_key_findings(data)
        assert "src/a.py" in result
        assert "src/b.py" in result
        assert "10-20" in result
        assert "42" in result
        assert "55-60" in result

    def test_backward_compat_no_locations(self):
        """Findings without locations array should still render (backward compat)."""
        data = {
            "agenticReview": {
                "overallGrade": "B",
                "reviewMethod": "agent-teams",
                "findings": [
                    {
                        "file": "old.py",
                        "grade": "B",
                        "zones": "core",
                        "notable": "Legacy",
                        "detail": "<p>Old format</p>",
                        "gradeSortOrder": 1,
                        "agent": "security",
                        # No locations array — legacy data
                    }
                ],
            },
            "architecture": {"zones": [{"id": "core", "category": "product"}]},
        }
        result = render_key_findings(data)
        assert "old.py" in result

    def test_locs_count_matches_locations_length(self):
        """Locs cell should show the number of locations."""
        data = {
            "agenticReview": {
                "overallGrade": "B",
                "reviewMethod": "agent-teams",
                "findings": [
                    {
                        "file": "a.py",
                        "grade": "B",
                        "zones": "core",
                        "notable": "Three locs",
                        "detail": "<p>D</p>",
                        "gradeSortOrder": 1,
                        "agent": "adversarial",
                        "locations": [
                            {"file": "a.py", "lines": "1"},
                            {"file": "b.py", "lines": "2"},
                            {"file": "c.py", "lines": "3"},
                        ],
                    }
                ],
            },
            "architecture": {"zones": [{"id": "core", "category": "product"}]},
        }
        result = render_key_findings(data)
        # The count 3 should appear in a td cell
        assert "<td>3</td>" in result
