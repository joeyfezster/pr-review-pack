"""Integration tests for the full render pipeline (v1 and v2 templates).

Calls render() end-to-end with real fixture data and both template versions,
then validates the output HTML: no unreplaced markers, sidebar components,
code diffs section, and factory history conditional rendering.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from render_review_pack import TEMPLATE_PATH, TEMPLATE_V2_PATH, render

# ── Helpers ────────────────────────────────────────────────────────


def _render_to_html(
    tmp_path: Path,
    data: dict,
    template_version: str,
) -> str:
    """Write data to a temp JSON file, call render(), return output HTML."""
    data_path = tmp_path / "review_pack_data.json"
    data_path.write_text(json.dumps(data), encoding="utf-8")
    output_path = tmp_path / "output.html"
    render(
        data_path=str(data_path),
        output_path=str(output_path),
        template_version=template_version,
    )
    return output_path.read_text(encoding="utf-8")


def _unreplaced_markers_outside_scripts(
    html: str,
    exclude: frozenset[str] | None = None,
) -> list[str]:
    """Find <!-- INJECT: ... --> markers that are NOT inside <script> blocks.

    Markers embedded inside <script> tags (e.g., in JSON diff data that
    contains raw template content) are false positives and must be excluded.

    Args:
        html: The rendered HTML string.
        exclude: Optional set of marker strings to ignore (e.g., factory
            history markers that are conditionally unreplaced by design).
    """
    # Remove all <script>...</script> blocks (non-greedy, case-insensitive)
    stripped = re.sub(
        r"<script\b[^>]*>.*?</script>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    markers = re.findall(r"<!-- INJECT: .+? -->", stripped)
    if exclude:
        markers = [m for m in markers if m not in exclude]
    return markers


# v1 factory history markers are conditionally unreplaced when
# factoryHistory is None — they live inside a hidden tab.
V1_FACTORY_HISTORY_MARKERS = frozenset({
    "<!-- INJECT: iteration count + satisfaction trajectory cards -->",
    "<!-- INJECT: factory history events from DATA.factoryHistory.timeline -->",
    "<!-- INJECT: gate finding rows from DATA.factoryHistory.gateFindings -->",
})


# ── Template availability guards ──────────────────────────────────


v1_available = pytest.mark.skipif(
    not TEMPLATE_PATH.exists(),
    reason="v1 template not found on disk",
)
v2_available = pytest.mark.skipif(
    not TEMPLATE_V2_PATH.exists(),
    reason="v2 template not found on disk",
)


# ── v1 template tests ─────────────────────────────────────────────


@v1_available
class TestV1Render:

    def test_no_unreplaced_markers(self, tmp_path, sample_review_pack_data):
        """No unreplaced markers except v1 factory history (conditionally hidden)."""
        html = _render_to_html(tmp_path, sample_review_pack_data, "v1")
        leftover = _unreplaced_markers_outside_scripts(
            html, exclude=V1_FACTORY_HISTORY_MARKERS
        )
        assert leftover == [], f"Unreplaced markers in v1 output: {leftover}"

    def test_no_unreplaced_markers_with_factory_history(
        self, tmp_path, sample_review_pack_data, sample_factory_history
    ):
        """When factoryHistory is present, ALL markers should be replaced."""
        data = {**sample_review_pack_data, "factoryHistory": sample_factory_history}
        html = _render_to_html(tmp_path, data, "v1")
        leftover = _unreplaced_markers_outside_scripts(html)
        assert leftover == [], f"Unreplaced markers in v1 output: {leftover}"

    def test_title_injected(self, tmp_path, sample_review_pack_data):
        html = _render_to_html(tmp_path, sample_review_pack_data, "v1")
        assert "Add feature X to zone-alpha" in html

    def test_head_sha_injected(self, tmp_path, sample_review_pack_data):
        html = _render_to_html(tmp_path, sample_review_pack_data, "v1")
        assert "abc1234" in html

    def test_architecture_section_present(self, tmp_path, sample_review_pack_data):
        html = _render_to_html(tmp_path, sample_review_pack_data, "v1")
        assert "Zone Alpha" in html
        assert "Zone Beta" in html

    def test_convergence_section_present(self, tmp_path, sample_review_pack_data):
        html = _render_to_html(tmp_path, sample_review_pack_data, "v1")
        assert "READY TO MERGE" in html

    def test_data_json_embedded(self, tmp_path, sample_review_pack_data):
        html = _render_to_html(tmp_path, sample_review_pack_data, "v1")
        assert "const DATA =" in html
        # DATA should not be the empty placeholder
        assert "const DATA = {};" not in html

    def test_no_factory_history_when_null(self, tmp_path, sample_review_pack_data):
        """When factoryHistory is None, factory history markers are not replaced."""
        assert sample_review_pack_data["factoryHistory"] is None
        html = _render_to_html(tmp_path, sample_review_pack_data, "v1")
        # The v1 template has factory history markers that stay as-is when
        # factoryHistory is None (they're inside a tab that's hidden).
        # Verify no factory history content is injected.
        assert "Iteration 1 started" not in html

    def test_factory_history_rendered_when_present(
        self, tmp_path, sample_review_pack_data, sample_factory_history
    ):
        data = {**sample_review_pack_data, "factoryHistory": sample_factory_history}
        html = _render_to_html(tmp_path, data, "v1")
        assert "Iteration 1 started" in html
        assert "Human review requested" in html


# ── v2 template tests ─────────────────────────────────────────────


@v2_available
class TestV2Render:

    def test_no_unreplaced_markers(self, tmp_path, sample_review_pack_data):
        html = _render_to_html(tmp_path, sample_review_pack_data, "v2")
        leftover = _unreplaced_markers_outside_scripts(html)
        assert leftover == [], f"Unreplaced markers in v2 output: {leftover}"

    def test_title_injected(self, tmp_path, sample_review_pack_data):
        html = _render_to_html(tmp_path, sample_review_pack_data, "v2")
        assert "Add feature X to zone-alpha" in html

    # ── Sidebar components ─────────────────────────────────────────

    def test_sidebar_pr_meta(self, tmp_path, sample_review_pack_data):
        html = _render_to_html(tmp_path, sample_review_pack_data, "v2")
        # PR number should appear in sidebar meta
        assert "42" in html
        # Branch info
        assert "feature/add-x" in html

    def test_sidebar_verdict_badge(self, tmp_path, sample_review_pack_data):
        html = _render_to_html(tmp_path, sample_review_pack_data, "v2")
        assert "READY" in html

    def test_sidebar_gates_status(self, tmp_path, sample_review_pack_data):
        html = _render_to_html(tmp_path, sample_review_pack_data, "v2")
        # Gate names from convergence data
        assert "Gate 0" in html
        assert "Gate 1" in html

    def test_sidebar_metrics(self, tmp_path, sample_review_pack_data):
        html = _render_to_html(tmp_path, sample_review_pack_data, "v2")
        # Stats from header: additions, deletions, files
        assert "150" in html  # additions
        assert "30" in html  # deletions
        assert "8" in html  # filesChanged

    def test_sidebar_zone_minimap(self, tmp_path, sample_review_pack_data):
        html = _render_to_html(tmp_path, sample_review_pack_data, "v2")
        # Zone names should appear in the minimap
        assert "zone-alpha" in html
        assert "zone-beta" in html

    def test_sidebar_section_nav(self, tmp_path, sample_review_pack_data):
        html = _render_to_html(tmp_path, sample_review_pack_data, "v2")
        # Section nav should have navigation dots/links
        assert "sb-nav" in html

    # ── Code diffs section ─────────────────────────────────────────

    def test_code_diffs_section_present(self, tmp_path, sample_review_pack_data):
        html = _render_to_html(tmp_path, sample_review_pack_data, "v2")
        assert "section-file-coverage" in html
        assert "src/alpha/core.py" in html
        assert "infra/deploy.sh" in html

    def test_code_diffs_stats_in_section(self, tmp_path, sample_review_pack_data):
        html = _render_to_html(tmp_path, sample_review_pack_data, "v2")
        assert "cd-add" in html
        assert "cd-del" in html

    # ── Factory history section ────────────────────────────────────

    def test_factory_history_absent_when_null(
        self, tmp_path, sample_review_pack_data
    ):
        assert sample_review_pack_data["factoryHistory"] is None
        html = _render_to_html(tmp_path, sample_review_pack_data, "v2")
        # The factory history section wrapper exists in the template, but
        # the injection should produce no content inside it.
        assert "Iteration 1 started" not in html
        assert "Factory History</h2>" not in html

    def test_factory_history_rendered_when_present(
        self, tmp_path, sample_review_pack_data, sample_factory_history
    ):
        data = {**sample_review_pack_data, "factoryHistory": sample_factory_history}
        html = _render_to_html(tmp_path, data, "v2")
        assert "Factory History</h2>" in html
        assert "Iteration 1 started" in html
        assert "Human review requested" in html

    def test_factory_history_gate_findings_table(
        self, tmp_path, sample_review_pack_data, sample_factory_history
    ):
        data = {**sample_review_pack_data, "factoryHistory": sample_factory_history}
        html = _render_to_html(tmp_path, data, "v2")
        assert "Gate Findings" in html
        assert "Converged" in html

    # ── Data JSON embedded ─────────────────────────────────────────

    def test_data_json_embedded(self, tmp_path, sample_review_pack_data):
        html = _render_to_html(tmp_path, sample_review_pack_data, "v2")
        assert "const DATA =" in html
        assert "const DATA = {};" not in html


# ── Cross-template backward compatibility ──────────────────────────


@v1_available
@v2_available
class TestCrossTemplateCompat:

    def test_same_data_works_for_both_templates(
        self, tmp_path, sample_review_pack_data
    ):
        """The same ReviewPackData dict renders successfully with both templates."""
        v1_html = _render_to_html(tmp_path, sample_review_pack_data, "v1")
        # Use a different subdir so output files don't collide
        v2_dir = tmp_path / "v2"
        v2_dir.mkdir()
        v2_html = _render_to_html(v2_dir, sample_review_pack_data, "v2")
        # Both should produce non-trivial output
        assert len(v1_html) > 1000
        assert len(v2_html) > 1000
        # Both should contain the PR title
        assert "Add feature X to zone-alpha" in v1_html
        assert "Add feature X to zone-alpha" in v2_html

    def test_no_unreplaced_markers_in_either(
        self, tmp_path, sample_review_pack_data
    ):
        v1_html = _render_to_html(tmp_path, sample_review_pack_data, "v1")
        v2_dir = tmp_path / "v2"
        v2_dir.mkdir()
        v2_html = _render_to_html(v2_dir, sample_review_pack_data, "v2")

        # v1 conditionally leaves factory history markers when factoryHistory is None
        v1_leftover = _unreplaced_markers_outside_scripts(
            v1_html, exclude=V1_FACTORY_HISTORY_MARKERS
        )
        v2_leftover = _unreplaced_markers_outside_scripts(v2_html)
        assert v1_leftover == [], f"v1 unreplaced: {v1_leftover}"
        assert v2_leftover == [], f"v2 unreplaced: {v2_leftover}"
