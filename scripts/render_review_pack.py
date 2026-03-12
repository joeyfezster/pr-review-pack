#!/usr/bin/env python3
"""Pass 3 renderer: inject ReviewPackData into the HTML template.

Reads the template HTML and a ReviewPackData JSON file, generates HTML for
every <!-- INJECT: ... --> marker, and produces a self-contained HTML file.

This is deterministic rendering — zero LLM involvement.

Usage:
    python3 render_review_pack.py --data review_pack_data.json --output docs/pr6_review_pack.html
    python3 render_review_pack.py --data data.json --output out.html \
      --diff-data pr6_diff_data.json
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent.parent / "assets"
TEMPLATE_PATH = TEMPLATE_DIR / "template.html"
TEMPLATE_V2_PATH = TEMPLATE_DIR / "template_v2.html"

# ── Color / class maps ──────────────────────────────────────────────

LAYER_COLORS = {
    "factory": {"fill": "#dbeafe", "stroke": "#3b82f6", "text": "#1d4ed8"},
    "product": {"fill": "#dcfce7", "stroke": "#22c55e", "text": "#166534"},
    "infra": {"fill": "#f3e8ff", "stroke": "#8b5cf6", "text": "#6d28d9"},
}

GRADE_CLASS = {"A": "a", "B+": "b", "B": "b", "C": "c", "F": "f", "N/A": "na"}

# Agent abbreviations for compact badges
AGENT_ABBREV = {
    "code-health": "CH",
    "security": "SE",
    "test-integrity": "TI",
    "adversarial": "AD",
    "code-health-reviewer": "CH",
    "security-reviewer": "SE",
    "test-integrity-reviewer": "TI",
    "adversarial-reviewer": "AD",
    "architecture": "AR",
    "architecture-reviewer": "AR",
    "main": "MA",
    "main-agent": "MA",
}

GRADE_SORT = {"F": 0, "C": 1, "B": 2, "B+": 3, "A": 4, "N/A": 5}

CATEGORY_CLASS = {
    "environment": "cat-environment",
    "training": "cat-training",
    "pipeline": "cat-pipeline",
    "integration": "cat-integration",
}

STATUS_STYLE = {
    "passing": ("var(--green)", "&#x2713;", "Passing"),
    "pass": ("var(--green)", "&#x2713;", "Pass"),
    "failing": ("var(--red)", "&#x2717;", "Failing"),
    "fail": ("var(--red)", "&#x2717;", "Fail"),
    "advisory": ("var(--yellow)", "&#x26A0;", "Advisory"),
}


# ── Helpers ──────────────────────────────────────────────────────────


def _zone_tag(
    zone_id: str,
    zone_categories: dict[str, str] | None = None,
) -> str:
    """Render a single zone tag span with correct category CSS class."""
    cats = zone_categories or {}
    cat = cats.get(zone_id, "product")
    css = layer_tag_class(cat)
    return f'<span class="zone-tag {css}">{esc(zone_id)}</span>'


def esc(text: str) -> str:
    """HTML-escape plain text."""
    return html.escape(str(text))


def layer_tag_class(category: str) -> str:
    """Map zone category to CSS class for zone-tag."""
    return {"factory": "factory", "product": "product", "infra": "infra"}.get(
        category, "product"
    )


# ── Section renderers ───────────────────────────────────────────────

def render_stat_items(header: dict) -> str:
    commits = header.get("commits", 0)
    additions = header.get("additions", 0)
    deletions = header.get("deletions", 0)
    files = header.get("filesChanged", 0)
    return "\n      ".join([
        f'<span class="stat green">'
        f'<span class="num">+{additions}</span> additions</span>',
        f'<span class="stat red">'
        f'<span class="num">&minus;{deletions}</span> deletions</span>',
        f'<span class="stat">'
        f'<span class="num">{files}</span> files</span>',
        f'<span class="stat">'
        f'<span class="num">{commits}</span>'
        f' commit{"s" if commits != 1 else ""}</span>',
    ])


def render_status_badges(header: dict) -> str:
    badges = []
    for b in header.get("statusBadges", []):
        icon = b.get("icon", "")
        badges.append(
            f'<span class="status-badge {b["type"]}">{icon} {esc(b["label"])}</span>'
        )
    return "\n      ".join(badges)


def render_factory_history_tab_button(data: dict) -> str:
    if data.get("factoryHistory"):
        return (
            '<button class="tab-btn" onclick="switchTab(\'history\')">'
            "Factory History</button>"
        )
    return ""


def _wrap_svg_text(text: str, max_chars: int = 18) -> list[str]:
    """Split text into lines of at most max_chars characters, breaking on word boundaries."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if len(test) <= max_chars:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    # Limit to 2 lines, truncate 2nd line if too long
    if len(lines) > 2:
        lines = [lines[0], lines[1] + "\u2026"]
    return lines if lines else [text]


def render_architecture_svg(arch: dict) -> str:
    parts: list[str] = []

    # Arrowhead marker (defined once)
    parts.append(
        '<defs><marker id="arrowhead" markerWidth="8" markerHeight="6" '
        'refX="8" refY="3" orient="auto">'
        '<path d="M0,0 L8,3 L0,6 Z" fill="#9ca3af"/></marker></defs>'
    )

    # Row labels
    for label in arch.get("rowLabels", []):
        x, y = label["position"]["x"], label["position"]["y"]
        parts.append(
            f'<text x="{x}" y="{y}" text-anchor="end" '
            f'class="arch-row-label">{esc(label["text"])}</text>'
        )

    # Zone boxes + labels + sublabels + file count badges
    for zone in arch.get("zones", []):
        pos = zone["position"]
        cat = zone.get("category", "product")
        colors = LAYER_COLORS.get(cat, LAYER_COLORS["product"])
        x, y, w, h = pos["x"], pos["y"], pos["width"], pos["height"]
        cx = x + w / 2
        opacity = "1" if zone.get("isModified") else "0.6"

        # Calculate positions based on sublabel line count
        sublabel = zone.get("sublabel", "")
        sublabel_lines = _wrap_svg_text(sublabel, max_chars=18)
        n_sub_lines = len(sublabel_lines)

        if n_sub_lines <= 1:
            label_y = y + h / 2 - 4
            sublabel_y = y + h / 2 + 10
        else:
            label_y = y + h / 2 - 10
            sublabel_y = y + h / 2 + 4

        parts.append(
            f'<rect class="zone-box" data-zone="{esc(zone["id"])}" '
            f'x="{x}" y="{y}" width="{w}" height="{h}" rx="8" '
            f'fill="{colors["fill"]}" stroke="{colors["stroke"]}" '
            f'stroke-width="1.5" style="cursor:pointer;opacity:{opacity}"/>'
        )
        parts.append(
            f'<text x="{cx}" y="{label_y}" text-anchor="middle" '
            f'class="zone-label" fill="{colors["text"]}" '
            f'style="pointer-events:none">{esc(zone["label"])}</text>'
        )
        # Sublabel with word wrapping
        if n_sub_lines <= 1:
            parts.append(
                f'<text x="{cx}" y="{sublabel_y}" text-anchor="middle" '
                f'class="zone-sublabel" '
                f'style="pointer-events:none">'
                f'{esc(sublabel)}</text>'
            )
        else:
            tspans = "".join(
                f'<tspan x="{cx}" dy="{0 if i == 0 else 11}">'
                f'{esc(line)}</tspan>'
                for i, line in enumerate(sublabel_lines)
            )
            parts.append(
                f'<text x="{cx}" y="{sublabel_y}" text-anchor="middle" '
                f'class="zone-sublabel" '
                f'style="pointer-events:none">'
                f'{tspans}</text>'
            )
        fc = zone.get("fileCount", 0)
        if fc > 0:
            bcx, bcy = x + w - 8, y + 8
            parts.append(
                f'<circle class="zone-count-bg" cx="{bcx}" cy="{bcy}" '
                f'r="10" fill="{colors["stroke"]}"/>'
            )
            parts.append(
                f'<text class="zone-file-count" x="{bcx}" y="{bcy + 4}" '
                f'text-anchor="middle" fill="white" '
                f'style="pointer-events:none">{fc}</text>'
            )

    # Flow arrows
    for arrow in arch.get("arrows", []):
        fx, fy = arrow["from"]["x"], arrow["from"]["y"]
        tx, ty = arrow["to"]["x"], arrow["to"]["y"]
        parts.append(
            f'<line x1="{fx}" y1="{fy}" x2="{tx}" y2="{ty}" '
            f'stroke="#9ca3af" stroke-width="1.5" marker-end="url(#arrowhead)"/>'
        )

    # Unzoned files warning
    unzoned = arch.get("unzonedFiles", [])
    if unzoned:
        warn_y = max(
            (z["position"]["y"] + z["position"]["height"]
             for z in arch.get("zones", [])),
            default=200,
        ) + 25
        parts.append(
            f'<text x="10" y="{warn_y}" fill="#ef4444" '
            f'font-size="11" font-weight="700" '
            f'style="cursor:pointer" '
            f"onclick=\"scrollToSection('section-arch-assessment')\">"
            f"&#x26A0; {len(unzoned)} file(s) not in any zone "
            f"&mdash; click for details</text>"
        )

    return "\n          ".join(parts)


def render_architecture_assessment(data: dict) -> str:
    """Render the Architecture Assessment section from architect agent output.

    Structure:
      - Health badge + summary (always visible)
      - Core Issues (collapsible, with health pill)
      - Architectural Changes Detected (collapsible)
      - Architect's Recommendations (collapsible)
        - Coupling / unintended consequences
        - Zone Registry (subsection, with Unzoned Files sub-subsection)
        - Documentation Recommendations (subsection)

    Each section is collapsed by default and hidden when empty.
    """
    assessment = data.get("architectureAssessment")
    if not assessment:
        return ""

    health = assessment.get("overallHealth", "healthy")
    summary = assessment.get("summary", "")

    parts: list[str] = []

    # Health badge
    health_css = {
        "healthy": "passing",
        "needs-attention": "warning",
        "action-required": "failing",
    }
    health_label = health.replace("-", " ").title()
    parts.append(
        f'<div class="arch-health-badge {health_css.get(health, "warning")}">'
        f"{esc(health_label)}</div>"
    )
    if summary:
        parts.append(f"<div>{summary}</div>")

    # ── Section 1: Core Issues ──
    narrative = assessment.get("diagramNarrative", "")
    verifications = assessment.get("decisionZoneVerification", [])
    unverified = [v for v in verifications if not v.get("verified")]
    has_core = bool(narrative or unverified)

    if has_core:
        pill_css = "failing" if health == "action-required" else "warning"
        pill_label = "Action Required" if health == "action-required" else "Needs Attention"
        core_body: list[str] = []
        if narrative:
            core_body.append(f'<div class="arch-narrative">{narrative}</div>')
        if unverified:
            core_body.append("<h5>Unverified Decision-Zone Claims</h5>")
            for v in unverified:
                core_body.append(
                    f'<div class="arch-verification-item">'
                    f'Decision #{v.get("decisionNumber", "?")}: '
                    f'zones {esc(", ".join(v.get("claimedZones", [])))} '
                    f'&mdash; {esc(v.get("reason", ""))}</div>'
                )
        parts.append(
            '<div class="arch-section collapsed">'
            '<div class="arch-section-header" '
            "onclick=\"this.parentElement.classList.toggle('collapsed')\">"
            f'<h4>Core Issues <span class="arch-issue-pill {pill_css}">'
            f"{esc(pill_label)}</span></h4>"
            '<span class="chevron">&#x25BC;</span>'
            "</div>"
            '<div class="arch-section-body">'
            + "\n".join(core_body)
            + "</div></div>"
        )

    # ── Section 2: Architectural Changes Detected ──
    changes = assessment.get("zoneChanges", [])
    if changes:
        change_items: list[str] = []
        for ch in changes:
            ch_type = esc(ch.get("type", "").replace("_", " ").title())
            change_items.append(
                f'<div class="arch-change-item">'
                f"<strong>{ch_type}</strong>: "
                f'{esc(ch.get("zone", ""))} &mdash; '
                f'{esc(ch.get("reason", ""))}</div>'
            )
        parts.append(
            '<div class="arch-section collapsed">'
            '<div class="arch-section-header" '
            "onclick=\"this.parentElement.classList.toggle('collapsed')\">"
            "<h4>Architectural Changes Detected</h4>"
            '<span class="chevron">&#x25BC;</span>'
            "</div>"
            '<div class="arch-section-body">'
            + "\n".join(change_items)
            + "</div></div>"
        )

    # ── Section 3: Architect's Recommendations ──
    coupling = assessment.get("couplingWarnings", [])
    reg_warnings = assessment.get("registryWarnings", [])
    unzoned = assessment.get("unzonedFiles", [])
    doc_recs = assessment.get("docRecommendations", [])
    has_recommendations = bool(coupling or reg_warnings or unzoned or doc_recs)

    if has_recommendations:
        rec_body: list[str] = []

        # Coupling / unintended consequences
        if coupling:
            rec_body.append("<h5>Cross-Zone Coupling</h5>")
            for cw in coupling:
                rec_body.append(
                    f'<div class="arch-coupling-item">'
                    f'{esc(cw.get("fromZone", ""))} &rarr; '
                    f'{esc(cw.get("toZone", ""))}: '
                    f'{esc(cw.get("evidence", ""))}</div>'
                )

        # Zone Registry subsection
        if reg_warnings or unzoned:
            rec_body.append('<div class="arch-subsection">')
            rec_body.append("<h5>Zone Registry</h5>")
            if reg_warnings:
                for rw in reg_warnings:
                    sev = rw.get("severity", "WARNING").lower()
                    rec_body.append(
                        f'<div class="arch-registry-item">'
                        f'<span class="badge {sev}">'
                        f'{esc(rw.get("severity", ""))}</span> '
                        f'{esc(rw.get("zone", ""))}: '
                        f'{esc(rw.get("warning", ""))}</div>'
                    )
            # Unzoned files sub-subsection
            if unzoned:
                rec_body.append('<div class="arch-subsubsection">')
                rec_body.append(
                    f"<h6>&#x26A0; {len(unzoned)} Unzoned File(s)</h6>"
                )
                rec_body.append(
                    "<table><thead><tr>"
                    "<th>File</th><th>Suggested Zone</th><th>Reason</th>"
                    "</tr></thead><tbody>"
                )
                for uf in unzoned:
                    suggested = esc(uf.get("suggestedZone") or "\u2014")
                    rec_body.append(
                        f"<tr>"
                        f'<td><code>{esc(uf["path"])}</code></td>'
                        f"<td>{suggested}</td>"
                        f'<td>{esc(uf["reason"])}</td>'
                        f"</tr>"
                    )
                rec_body.append("</tbody></table></div>")
            rec_body.append("</div>")

        # Documentation Recommendations subsection
        if doc_recs:
            rec_body.append('<div class="arch-subsection">')
            rec_body.append("<h5>Documentation Recommendations</h5>")
            for dr in doc_recs:
                rec_body.append(
                    f'<div class="arch-doc-item">'
                    f'<code>{esc(dr.get("path", ""))}</code>: '
                    f'{esc(dr.get("reason", ""))}</div>'
                )
            rec_body.append("</div>")

        parts.append(
            '<div class="arch-section collapsed">'
            '<div class="arch-section-header" '
            "onclick=\"this.parentElement.classList.toggle('collapsed')\">"
            "<h4>Architect&rsquo;s Recommendations</h4>"
            '<span class="chevron">&#x25BC;</span>'
            "</div>"
            '<div class="arch-section-body">'
            + "\n".join(rec_body)
            + "</div></div>"
        )

    return "\n".join(parts)


def render_spec_list(specs: list[dict]) -> str:
    items = []
    for s in specs:
        path = s["path"]
        items.append(
            f'<li>{s.get("icon", "\U0001F4C4")} '
            f'<code class="file-path-link" '
            f"onclick=\"openFileModal('{esc(path)}')\">"
            f'{esc(path)}</code> &mdash; '
            f'{esc(s["description"])}</li>'
        )
    return "\n          ".join(items)


def render_scenario_legend(scenarios: list[dict]) -> str:
    categories = sorted({s.get("category", "") for s in scenarios})
    return " ".join(
        f'<span class="scenario-category {CATEGORY_CLASS.get(c, "")}">{esc(c)}</span>'
        for c in categories
    )


def render_scenario_cards(scenarios: list[dict]) -> str:
    cards = []
    for s in scenarios:
        color, icon, text = STATUS_STYLE.get(
            s["status"], ("var(--gray)", "?", s["status"])
        )
        cat_class = CATEGORY_CLASS.get(s.get("category", ""), "")
        zone = s.get("zone", "")
        d = s.get("detail", {})
        # detail may be a dict {what, how, result} or a plain string
        if isinstance(d, str):
            detail_html = f'<p>{esc(d)}</p>' if d else ''
        else:
            detail_html = (
                f'<dl>\n'
                f'      <dt>What</dt><dd>{esc(d.get("what", ""))}</dd>\n'
                f'      <dt>How</dt><dd>{esc(d.get("how", ""))}</dd>\n'
                f'      <dt>Result</dt><dd>{esc(d.get("result", ""))}</dd>\n'
                f'    </dl>'
            )
        cards.append(
            f'<div class="scenario-card" data-zone="{esc(zone)}" '
            f'onclick="this.classList.toggle(\'open\')">\n'
            f'  <div class="name">{esc(s["name"])}\n'
            f'    <span class="scenario-category {cat_class}">'
            f'{esc(s.get("category", ""))}</span>\n'
            f'  </div>\n'
            f'  <div class="status" style="color:{color}">{icon} {text}</div>\n'
            f'  <div class="scenario-card-detail">\n'
            f'    {detail_html}\n'
            f'  </div>\n'
            f'</div>'
        )
    return "\n          ".join(cards)


def render_what_changed_default(wc: dict) -> str:
    """Infrastructure + product summaries.

    These fields may contain HTML produced by the Pass 2b LLM agent
    (e.g. <p>, <strong> tags).  They are NOT escaped — the content is
    wrapped in a <div class="wc-summary"> to avoid invalid <p>-in-<p>
    nesting when the content already contains block-level elements.
    """
    default = wc.get("defaultSummary", {})
    parts = []
    infra = default.get("infrastructure", "")
    if infra:
        parts.append(
            f'<div class="wc-summary"><strong>Infrastructure:</strong> {infra}</div>'
        )
    product = default.get("product", "")
    if product:
        parts.append(
            f'<div class="wc-summary"><strong>Product:</strong> {product}</div>'
        )
    return "\n          ".join(parts)


def render_what_changed_zones(wc: dict) -> str:
    """Zone-level change descriptions.

    The ``description`` field may contain HTML produced by the Pass 2b
    LLM agent.  It is NOT escaped — wrapped in a ``<div>`` to avoid
    invalid ``<p>``-in-``<p>`` nesting.
    """
    divs = []
    for z in wc.get("zoneDetails", []):
        divs.append(
            f'<div class="wc-zone-detail" data-zone="{esc(z["zoneId"])}">\n'
            f'  <h4>{esc(z["title"])}</h4>\n'
            f'  <div>{z["description"]}</div>\n'
            f'</div>'
        )
    return "\n        ".join(divs)


def render_agentic_method_badge(review: dict) -> str:
    method = review.get("reviewMethod", "main-agent")
    css = "agent-teams" if method == "agent-teams" else "main-agent"
    label = "Agent Teams" if method == "agent-teams" else "Main Agent"
    return f'<span class="review-method-badge {css}">{label}</span>'


def render_agentic_legend() -> str:
    """Render compact legend for agent abbreviations."""
    entries = [
        ("CH", "Code Health", "code quality + complexity + dead code"),
        ("SE", "Security", "vulnerabilities beyond bandit"),
        ("TI", "Test Integrity", "test quality beyond AST scanner"),
        ("AD", "Adversarial", "gaming, spec violations, architecture"),
        ("AR", "Architecture", "zone coverage, coupling, structural changes"),
    ]
    items = []
    for abbrev, name, desc in entries:
        items.append(
            f'<span class="agent-legend-item" title="{esc(desc)}">'
            f'<span class="agent-abbrev">{abbrev}</span> {esc(name)}</span>'
        )
    return (
        '<div class="agent-legend">'
        + " ".join(items)
        + "</div>"
    )


def render_agentic_rows(review: dict, zone_categories: dict[str, str] | None = None) -> str:
    """Render agentic review rows grouped by file.

    Each file gets one master row with compact agent grade badges.
    Expanding shows per-agent detail.

    Args:
        review: The agenticReview dict containing findings.
        zone_categories: Mapping of zone ID → category (e.g. "factory", "product", "infra").
    """
    if zone_categories is None:
        zone_categories = {}
    findings = review.get("findings", [])
    if not findings:
        return ""

    # Group by file, preserving insertion order (Python 3.7+ dict guarantee)
    by_file: dict[str, list[dict]] = {}
    for f in findings:
        filepath = f.get("file", "unknown")
        by_file.setdefault(filepath, []).append(f)

    rows = []
    for filepath, file_findings in by_file.items():
        # Worst grade determines file sort order
        worst_sort = min(f.get("gradeSortOrder", 99) for f in file_findings)
        zones = file_findings[0].get("zones", "")

        # Compact agent badges: CH:A  SE:B  TI:A  AD:B
        badges = []
        for f in file_findings:
            agent_name = f.get("agent", "") or "main"
            abbrev = AGENT_ABBREV.get(agent_name, agent_name[:2].upper() if agent_name else "?")
            grade = f.get("grade", "N/A")
            grade_css = GRADE_CLASS.get(grade, "na")
            badges.append(
                f'<span class="agent-grade-badge">'
                f'<span class="agent-abbrev">{esc(abbrev)}</span>'
                f'<span class="grade {grade_css}">{esc(grade)}</span>'
                f'</span>'
            )
        badges_html = " ".join(badges)

        # Most notable finding for the summary column
        notable_finding = min(file_findings, key=lambda f: GRADE_SORT.get(f.get("grade", "N/A"), 5))
        notable_text = notable_finding.get("notable", "")

        # Resolve zone category from first zone ID
        first_zone = zones.split()[0] if zones.strip() else ""
        zone_cat = zone_categories.get(first_zone, "product")

        # Master row (one per file)
        rows.append(
            f'<tr class="adv-row" data-zones="{esc(zones)}" '
            f'data-grade-sort="{worst_sort}" onclick="toggleAdvDetail(this)">\n'
            f'  <td><code class="file-path-link" '
            f"onclick=\"event.stopPropagation();"
            f"openFileModal('{esc(filepath)}')\">"
            f'{esc(filepath)}</code></td>\n'
            f'  <td class="agent-badges-cell">{badges_html}</td>\n'
            f'  <td><span class="zone-tag {layer_tag_class(zone_cat)}">'
            f'{esc(zones)}</span></td>\n'
            f'  <td>{esc(notable_text)}</td>\n'
            f'</tr>\n'
        )

        # Detail row: per-agent breakdown
        # detail is HTML-safe: sanitized at ingestion by the Gate 0 review
        # agents. Contains structured HTML from agent analysis.
        detail_parts = []
        for f in file_findings:
            agent_name = f.get("agent", "") or "main"
            abbrev = AGENT_ABBREV.get(agent_name, agent_name[:2].upper() if agent_name else "?")
            grade = f.get("grade", "N/A")
            grade_css = GRADE_CLASS.get(grade, "na")
            detail_text = f.get("detail", "") or f.get("notable", "")
            detail_parts.append(
                f'<div class="agent-detail-entry">'
                f'<span class="agent-detail-header">'
                f'<span class="agent-abbrev">{esc(abbrev)}</span>'
                f'<span class="grade {grade_css}">{esc(grade)}</span>'
                f'<span class="agent-detail-name">{esc(agent_name)}</span>'
                f'</span>'
                f'<div class="agent-detail-body">{detail_text}</div>'
                f'</div>'
            )

        rows.append(
            f'<tr class="adv-detail-row" data-zones="{esc(zones)}">\n'
            f'  <td colspan="4">{"".join(detail_parts)}</td>\n'
            f'</tr>'
        )

    return "\n            ".join(rows)


def render_ci_rows(ci_checks: list[dict], zone_categories: dict[str, str] | None = None) -> str:
    if zone_categories is None:
        zone_categories = {}
    rows = []
    for ci in ci_checks:
        status_css = "pass" if ci["status"] == "pass" else "fail"
        health_css = ci.get("healthTag", "normal")
        detail = ci.get("detail", {})

        # Sub-checks — detail is HTML-safe: contains structured text from
        # the scaffold's CI performance builder, not raw user input.
        sub_html = ""
        for chk in detail.get("checks", []):
            sub_html += (
                '<div class="ci-check-item" '
                "onclick=\"event.stopPropagation();this.classList.toggle('open')\">\n"
                f'  <div class="ci-check-summary">'
                f'<span class="ci-sub-chevron">&#x25B6;</span> '
                f'{esc(chk["label"])}</div>\n'
                f'  <div class="ci-check-detail">{esc(chk.get("detail", ""))}</div>\n'
                "</div>\n"
            )

        zones_html = " ".join(
            _zone_tag(z, zone_categories)
            for z in detail.get("zones", [])
        )
        specs_html = " ".join(
            f'<code>{esc(s)}</code>' for s in detail.get("specRefs", [])
        )
        notes_html = (
            f'<p style="margin-top:6px;font-style:italic;font-size:12px;'
            f'color:var(--text-muted)">{esc(detail["notes"])}</p>'
            if detail.get("notes")
            else ""
        )

        rows.append(
            f'<tr class="expandable" onclick="toggleCIDetail(this)">\n'
            f'  <td><strong>{esc(ci["name"])}</strong> '
            f'<small style="color:var(--text-muted)">'
            f'{esc(ci.get("trigger", ""))}</small></td>\n'
            f'  <td><span class="badge {status_css}">{esc(ci["status"])}</span></td>\n'
            f'  <td><span class="time-label {health_css}">{esc(ci["time"])}</span>'
            f'<br><span class="time-health-sub">'
            f'{esc(ci.get("healthTag", ""))}</span></td>\n'
            f'  <td class="ci-chevron">&#x25BC;</td>\n'
            f'</tr>\n'
            f'<tr class="detail-row">\n'
            f'  <td colspan="4">\n'
            f'    <p><strong>Coverage:</strong> {esc(detail.get("coverage", ""))}</p>\n'
            f'    <p><strong>Gates:</strong> {esc(detail.get("gates", ""))}</p>\n'
            f'    {sub_html}'
            f'    <div style="margin-top:6px">Zones: {zones_html}</div>\n'
            + (f'    <div>Specs: {specs_html}</div>\n' if specs_html else "")
            + f'    {notes_html}\n'
            f'  </td>\n'
            f'</tr>'
        )
    return "\n            ".join(rows)


def render_decision_cards(
    decisions: list[dict],
    zone_categories: dict[str, str] | None = None,
) -> str:
    if zone_categories is None:
        zone_categories = {}
    cards = []
    for d in decisions:
        zones_str = d.get("zones", "")
        verified = d.get("verified", True)
        unverified = (
            ' <span style="color:var(--red);font-size:11px">[UNVERIFIED]</span>'
            if not verified
            else ""
        )
        zone_tags = " ".join(
            _zone_tag(z, zone_categories)
            for z in zones_str.split()
        )

        files_html = ""
        if d.get("files"):
            file_rows = ""
            for f in d["files"]:
                file_rows += (
                    f'<tr><td><code class="file-path-link" '
                    f"onclick=\"event.stopPropagation();"
                    f"openFileModal('{esc(f['path'])}')\">"
                    f'{esc(f["path"])}</code></td>'
                    f'<td>{esc(f["change"])}</td></tr>\n'
                )
            files_html = (
                '<table style="width:100%;margin-top:8px">'
                "<thead><tr><th>File</th><th>Change</th></tr></thead>"
                f"<tbody>{file_rows}</tbody></table>"
            )

        # body is HTML-safe: sanitized at ingestion by the Pass 2 LLM agent
        # and reviewed in the adversarial pass. Title/rationale are escaped.
        cards.append(
            f'<div class="decision-card" data-zones="{esc(zones_str)}">\n'
            f'  <div class="decision-header" '
            f'onclick="toggleDecision(this.parentElement)">\n'
            f'    <span class="decision-num">{d["number"]}</span>\n'
            f"    <div>\n"
            f'      <div class="decision-title">'
            f'{esc(d["title"])}{unverified}</div>\n'
            f'      <div class="decision-rationale">'
            f'{esc(d["rationale"])}</div>\n'
            f"    </div>\n"
            f"  </div>\n"
            f'  <div class="decision-body">\n'
            f'    <p>{d.get("body", "")}</p>\n'
            f'    <div class="decision-zones">{zone_tags}</div>\n'
            f'    <div class="decision-files">{files_html}</div>\n'
            f"  </div>\n"
            f"</div>"
        )
    return "\n        ".join(cards)


def render_convergence_grid(convergence: dict) -> str:
    cards = []
    for gate in convergence.get("gates", []):
        st = gate.get("status", "passing")
        # detail is HTML-safe: contains structured HTML from the Pass 2 LLM
        # agent, reviewed in the adversarial pass. name/summary are escaped.
        cards.append(
            f'<div class="conv-card" onclick="this.classList.toggle(\'open\')">\n'
            f'  <div class="conv-name">{esc(gate["name"])}</div>\n'
            f'  <div class="conv-status {st}">{esc(gate["statusText"])}</div>\n'
            f'  <div class="conv-detail">{esc(gate["summary"])}</div>\n'
            f'  <div class="conv-card-detail">{gate.get("detail", "")}</div>\n'
            f"</div>"
        )
    overall = convergence.get("overall", {})
    if overall:
        st = overall.get("status", "passing")
        # detail is HTML-safe: sanitized at ingestion
        cards.append(
            f'<div class="conv-card" onclick="this.classList.toggle(\'open\')">\n'
            f'  <div class="conv-name">Overall</div>\n'
            f'  <div class="conv-status {st}">{esc(overall["statusText"])}</div>\n'
            f'  <div class="conv-detail">{esc(overall["summary"])}</div>\n'
            f'  <div class="conv-card-detail">{overall.get("detail", "")}</div>\n'
            f"</div>"
        )
    return "\n          ".join(cards)


def render_post_merge_items(
    items: list[dict],
    zone_categories: dict[str, str] | None = None,
) -> str:
    if zone_categories is None:
        zone_categories = {}
    rendered = []
    for item in items:
        priority = item.get("priority", "low")

        code_html = ""
        if item.get("codeSnippet"):
            cs = item["codeSnippet"]
            header = f'## {cs.get("file", "")}'
            if cs.get("lineRange"):
                header += f', {cs["lineRange"]}'
            code_html = (
                f'<div class="code-block">'
                f'{esc(header)}\n{esc(cs.get("code", ""))}</div>'
            )

        zones_html = " ".join(
            _zone_tag(z, zone_categories)
            for z in item.get("zones", [])
        )

        # title is escaped (plain text label).
        # description is HTML-safe: sanitized at ingestion by the Pass 2
        # LLM agent, reviewed in the adversarial pass.
        rendered.append(
            f'<div class="pm-item">\n'
            f'  <div class="pm-header" '
            f"onclick=\"this.parentElement.classList.toggle('open')\">\n"
            f'    <span class="priority {priority}">'
            f"{esc(priority.upper())}</span>\n"
            f'    <span>{esc(item.get("title", ""))}</span>\n'
            f"  </div>\n"
            f'  <div class="pm-body">\n'
            f'    <p>{item.get("description", "")}</p>\n'
            f"    {code_html}\n"
            f'    <div class="scenario-box failure">\n'
            f'      <div class="scenario-label">Failure scenario</div>\n'
            f'      {esc(item.get("failureScenario", ""))}\n'
            f"    </div>\n"
            f'    <div class="scenario-box success">\n'
            f'      <div class="scenario-label">Resolution</div>\n'
            f'      {esc(item.get("successScenario", ""))}\n'
            f"    </div>\n"
            f'    <div style="margin-top:6px">{zones_html}</div>\n'
            f"  </div>\n"
            f"</div>"
        )
    return "\n        ".join(rendered)


def render_history_summary_cards(history: dict) -> str:
    return "\n        ".join([
        (
            f'<div class="conv-card" onclick="this.classList.toggle(\'open\')">\n'
            f'  <div class="conv-name">Iterations</div>\n'
            f'  <div class="conv-status passing">'
            f'{esc(history.get("iterationCount", ""))}</div>\n'
            f'  <div class="conv-detail">Factory convergence iterations</div>\n'
            f'  <div class="conv-card-detail">'
            f'{esc(history.get("satisfactionDetail", ""))}</div>\n'
            f"</div>"
        ),
        (
            f'<div class="conv-card" onclick="this.classList.toggle(\'open\')">\n'
            f'  <div class="conv-name">Satisfaction</div>\n'
            f'  <div class="conv-status passing">'
            f'{esc(history.get("satisfactionTrajectory", ""))}</div>\n'
            f'  <div class="conv-detail">Scenario satisfaction trajectory</div>\n'
            f'  <div class="conv-card-detail">'
            f'{esc(history.get("satisfactionDetail", ""))}</div>\n'
            f"</div>"
        ),
    ])


def render_history_timeline(events: list[dict]) -> str:
    rendered = []
    for ev in events:
        ev_class = "intervention" if ev.get("type") == "intervention" else ""
        agent = ev.get("agent", {})
        agent_class = "human" if agent.get("type") == "human" else ""
        # expandedDetail is HTML-safe: sanitized at ingestion by the factory
        # orchestrator. Contains structured HTML for timeline expansion.
        rendered.append(
            f'<div class="history-event {ev_class}" '
            f'onclick="this.classList.toggle(\'open\')">\n'
            f'  <div class="history-event-header">\n'
            f'    <div class="history-event-title">{esc(ev["title"])}</div>\n'
            f'    <span class="event-agent {agent_class}">'
            f'{esc(agent.get("label", ""))}</span>\n'
            f"  </div>\n"
            f'  <div class="history-event-detail-summary">'
            f'{esc(ev.get("detail", ""))}</div>\n'
            f'  <div class="history-event-meta">'
            f'{esc(ev.get("meta", ""))}</div>\n'
            f'  <div class="history-event-detail">'
            f'{ev.get("expandedDetail", "")}</div>\n'
            f"</div>"
        )
    return "\n        ".join(rendered)


def _escape_popover(text: str) -> str:
    """Escape popover text for safe embedding in onclick JS attribute."""
    return (
        text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace('"', "&quot;")
        .replace("\n", "\\n")
    )


def render_gate_findings_rows(findings: list[dict]) -> str:
    rows = []
    for row in findings:

        def cell_html(cell: dict) -> str:
            status = cell.get("status", "not-run")
            label = cell.get("label", "")
            popover = _escape_popover(cell.get("popover", ""))
            css_map = {"pass": "pass", "fail": "fail", "advisory": "info"}
            css = css_map.get(status, "")
            click = (
                f" class=\"gate-clickable\" "
                f"onclick=\"showGatePopover(event, '{popover}')\""
                if popover
                else ""
            )
            return f"<td{click}><span class=\"badge {css}\">{esc(label)}</span></td>"

        phase_popover = _escape_popover(row.get("phasePopover", ""))
        phase_click = (
            f" class=\"gate-clickable\" "
            f"onclick=\"showGatePopover(event, '{phase_popover}')\""
            if phase_popover
            else ""
        )
        rows.append(
            f"<tr>\n"
            f"  <td{phase_click}>{esc(row['phase'])}</td>\n"
            f"  {cell_html(row['gate1'])}\n"
            f"  {cell_html(row['gate2'])}\n"
            f"  {cell_html(row['gate3'])}\n"
            f"  <td>{esc(row.get('action', ''))}</td>\n"
            f"</tr>"
        )
    return "\n          ".join(rows)


# ── v2 Sidebar renderers ──────────────────────────────────────────


def render_sidebar_pr_meta(header: dict) -> str:
    """Render PR number, title, branch, SHA, and stats for the sidebar."""
    pr_num = header.get("prNumber", "")
    title = header.get("title", "")
    pr_url = header.get("prUrl", "")
    head_branch = header.get("headBranch", "")
    base_branch = header.get("baseBranch", "")
    head_sha = header.get("headSha", "")
    adds = header.get("additions", 0)
    dels = header.get("deletions", 0)
    files = header.get("filesChanged", 0)
    commits = header.get("commits", 0)
    pr_link = (
        f'<a href="{esc(pr_url)}" target="_blank" '
        f'style="color:var(--blue);text-decoration:none">'
        f'PR #{pr_num}</a>'
    ) if pr_url else f'PR #{pr_num}'
    sha_short = esc(head_sha[:7]) if head_sha else "?"
    return (
        f'<div class="sb-pr-meta">\n'
        f'  <div class="sb-pr-number">{pr_link}</div>\n'
        f'  <div class="sb-pr-title">{esc(title)}</div>\n'
        f'  <div class="sb-pr-stats">'
        f'<span style="color:#166534">+{adds}</span> / '
        f'<span style="color:#991b1b">&minus;{dels}</span> &middot; '
        f'{files} files &middot; '
        f'{commits} commit{"s" if commits != 1 else ""}'
        f'</div>\n'
        f'  <div style="font-size:10px;color:var(--text-muted);'
        f'margin-top:4px">'
        f'{esc(head_branch)} &rarr; {esc(base_branch)}</div>\n'
        f'  <div style="font-size:10px;color:var(--text-muted);'
        f'font-family:var(--mono)">HEAD: {sha_short}</div>\n'
        f'</div>'
    )


def render_sidebar_status_badges(header: dict, has_scenarios: bool = True) -> str:
    """Render status badges (CI, Scenarios, Comments, Gate 0) in sidebar.

    When *has_scenarios* is False, the scenario pill is omitted.
    """
    badges = []
    for b in header.get("statusBadges", []):
        label = b.get("label", "")
        # Skip scenario badge when there are no scenarios
        if not has_scenarios and "scenario" in label.lower():
            continue
        icon = b.get("icon", "")
        badge_type = b.get("type", "info")
        badges.append(
            f'<span class="status-badge {badge_type}" '
            f'style="font-size:10px;padding:2px 8px">'
            f'{icon} {esc(label)}</span>'
        )
    if not badges:
        return ""
    return (
        '<div style="display:flex;flex-wrap:wrap;gap:4px;'
        'margin-bottom:12px">\n'
        + "\n".join(badges)
        + "\n</div>"
    )


def render_sidebar_verdict(data: dict) -> str:
    """Render status badge: READY / NEEDS REVIEW / BLOCKED.

    Uses new ``status`` field if present, falls back to legacy ``verdict``.
    """
    status_obj = data.get("status")
    if status_obj and "value" in status_obj:
        value = status_obj["value"]
        text = status_obj.get("text", value.upper())
        reasons = status_obj.get("reasons", [])
    else:
        verdict = data.get("verdict", {})
        value = verdict.get("status", "review")
        text = verdict.get("text", value.upper())
        reasons = []

    icon = {
        "ready": "&#x2713;",
        "needs-review": "&#x26A0;",
        "review": "&#x26A0;",
        "blocked": "&#x2717;",
    }.get(value, "?")

    html = '<div class="sb-verdict-wrapper">'
    html += f'\n  <div class="sb-verdict {value}">{icon} {esc(text)}</div>'
    if reasons:
        html += '\n  <ul class="sb-status-reasons">'
        for r in reasons:
            html += f"\n    <li>{esc(r)}</li>"
        html += "\n  </ul>"
    html += "\n</div>"
    return html


def render_sidebar_commit_scope(data: dict) -> str:
    """Render commit scope: reviewed SHA, HEAD SHA, gap warning."""
    reviewed = data.get("reviewedCommitSHA", "")
    head = data.get("headCommitSHA", "")
    gap = data.get("commitGap", 0)

    if not reviewed and not head:
        return ""

    reviewed_short = reviewed[:7] if reviewed else "unknown"
    head_short = head[:7] if head else "unknown"
    match_class = "match" if reviewed == head else "mismatch"

    html = '<div class="sb-commit-scope">'
    html += (
        f'<div class="sha-row">'
        f'<span class="sha-label">Analyzed:</span>'
        f'<span class="sha-value">{esc(reviewed_short)}</span>'
        f"</div>"
    )
    html += (
        f'<div class="sha-row">'
        f'<span class="sha-label">HEAD:</span>'
        f'<span class="sha-value {match_class}">{esc(head_short)}</span>'
        f"</div>"
    )
    if gap > 0:
        html += (
            f'<div class="sb-commit-gap" onclick="toggleCommitList()">'
            f"&#x26A0; {gap} commit(s) since analysis"
            f"</div>"
        )
    html += "</div>"
    return html


def render_sidebar_merge_button(data: dict) -> str:
    """Render the Approve and Merge button + command panel."""
    status_obj = data.get("status", {})
    value = status_obj.get("value", "needs-review") if "value" in status_obj else "needs-review"
    pr_number = data.get("header", {}).get("prNumber", "?")

    if value == "blocked":
        return (
            '<button class="sb-merge-btn" disabled '
            'title="Resolve blockers before merging">'
            "&#x2717; Blocked &mdash; cannot merge</button>"
        )

    btn_class = "ready" if value == "ready" else "needs-review"
    btn_text = "Approve and Merge" if value == "ready" else "Approve and Merge (with warnings)"

    html = (
        f'<button class="sb-merge-btn {btn_class}" onclick="toggleMergePanel()">'
        f"{esc(btn_text)}</button>"
    )
    html += (
        f'<div class="sb-merge-panel" id="sb-merge-panel">'
        f"<strong>To merge this PR, run:</strong>"
        f'<code id="merge-cmd" onclick="copyMergeCommand()" '
        f'title="Click to copy">review-pack merge {pr_number}</code>'
        f'<div class="merge-steps">This will:'
        f"<ol>"
        f"<li>Refresh all deterministic data</li>"
        f"<li>Snapshot dynamic &rarr; static</li>"
        f"<li>Validate the snapshot</li>"
        f"<li>Commit the review pack</li>"
        f"<li>Merge the PR</li>"
        f"</ol></div></div>"
    )
    return html


def render_sidebar_refresh_button(data: dict) -> str:
    """Render the refresh button — copies the full refresh command on click.

    NOTE: The embedded command includes the machine-specific CWD path,
    making this button only useful on the machine that rendered the pack.
    This is acceptable — refresh is a developer workflow, not a CI artifact.
    """
    pr_number = data.get("header", {}).get("prNumber", "?")
    # Derive repo path from git remote or current working directory
    repo_root = Path.cwd()
    try:
        home = Path.home()
        rel_path = repo_root.relative_to(home)
        cd_path = f"~/{rel_path}"
    except ValueError:
        cd_path = str(repo_root)
    cmd = (
        f"cd {cd_path} && python3 packages/pr-review-pack/scripts/"
        f"review_pack_cli.py refresh docs/pr{pr_number}_review_pack.html"
    )
    return (
        f'<button class="sb-refresh-btn" id="sb-refresh-btn" '
        f'onclick="copyRefreshCmd()" '
        f'title="Copy refresh command to clipboard">'
        f'&#x21BB; Copy Refresh Command</button>'
        f'<input type="hidden" id="refresh-cmd-value" value="{esc(cmd)}"/>'
    )


def render_sidebar_gate_pills(convergence: dict, has_scenarios: bool = True) -> str:
    """Render compact gate status pills for the sidebar.

    Each pill is colored green (passing) or red (failing) and clickable
    to scroll to the Review Gates section and expand that gate's card.

    When *has_scenarios* is False, the scenario gate pill is omitted.
    """
    pills = []
    for gate in convergence.get("gates", []):
        name = gate.get("name", "")
        if not has_scenarios and "scenario" in name.lower():
            continue
        st = gate.get("status", "failing")
        pill_class = "pass" if st == "passing" else "fail"
        icon = "&#x2713;" if st == "passing" else "&#x2717;"
        # Short label: extract gate number or use full name
        short = name.split("\u2014")[0].strip() if "\u2014" in name else name
        pills.append(
            f'<span class="sb-gate-pill {pill_class}" '
            f"onclick=\"scrollToGate('{esc(name)}')\" "
            f'title="{esc(name)}">'
            f'{icon} {esc(short)}</span>'
        )
    if not pills:
        return ""
    return f'<div class="sb-gate-pills">{"".join(pills)}</div>'






def _nav_icon(icon_type: str, value: object = None) -> str:
    """Generate a nav icon HTML span.

    icon_type — one of:
      "pass"       → green ✓
      "fail"       → red ✗
      "warn"       → yellow ⚠
      "count"      → blue chip with number
      "count-warn" → yellow chip with number
      "count-fail" → red chip with number
      "present"    → small blue dot
      "empty"      → invisible dot (placeholder)
    """
    if icon_type == "pass":
        return '<span class="sb-nav-icon pass">&#x2713;</span>'
    if icon_type == "fail":
        return '<span class="sb-nav-icon fail">&#x2717;</span>'
    if icon_type == "warn":
        return '<span class="sb-nav-icon warn">&#x26A0;</span>'
    if icon_type == "count":
        return f'<span class="sb-nav-icon count">{value}</span>'
    if icon_type == "count-warn":
        return f'<span class="sb-nav-icon count-warn">{value}</span>'
    if icon_type == "count-fail":
        return f'<span class="sb-nav-icon count-fail">{value}</span>'
    if icon_type == "present":
        return '<span class="sb-nav-icon present"></span>'
    # empty
    return '<span class="sb-nav-icon empty"></span>'


def render_sidebar_section_nav(data: dict, has_scenarios: bool = True) -> str:
    """Render section navigation list with status icons.

    Each nav item gets a small icon that conveys the core insight of the
    card at a glance.  The icon is derived from the card's data.

    When *has_scenarios* is False, the Convergence and Factory History
    entries are omitted, and "Specs & Scenarios" becomes "Specifications".
    """
    # Pre-compute data for icon derivation
    arch_zones = data.get("architecture", {}).get("zones", [])
    modified_zones = sum(1 for z in arch_zones if z.get("isModified"))
    wc = data.get("whatChanged", {}).get("defaultSummary", {})
    has_wc = bool(wc.get("infrastructure") or wc.get("product"))
    decisions = data.get("decisions", [])

    gates = data.get("convergence", {}).get("gates", [])
    all_gates_pass = all(g.get("status") == "passing" for g in gates) if gates else True

    scenarios = data.get("scenarios", [])
    failing_scenarios = sum(1 for s in scenarios if s.get("status") != "pass")

    convergence_overall = data.get("convergence", {}).get("overall", {})
    conv_status = convergence_overall.get("status", "passing")

    fh = data.get("factoryHistory")
    iteration_count = fh.get("iterationCount", 0) if fh else 0

    aa = data.get("architectureAssessment")
    aa_health = aa.get("overallHealth", "healthy") if aa else "healthy"

    review = data.get("agenticReview", {})
    findings = review.get("findings", [])
    cf_count = sum(1 for f in findings if f.get("grade") in ("C", "F"))

    ci = data.get("ciPerformance", [])
    ci_all_pass = all(c.get("status") == "pass" for c in ci) if ci else True

    pm = data.get("postMergeItems", [])

    specs_label = "Specs &amp; Scenarios" if has_scenarios else "Specifications"

    # Build sections: (section_id, label, icon_html)
    sections: list[tuple[str, str | None, str]] = []

    # Tier 1: Architecture & Changes
    sections.append(("__group__", "Architecture &amp; Changes", ""))
    sections.append((
        "section-architecture", "Architecture",
        _nav_icon("count", modified_zones) if modified_zones > 0
        else _nav_icon("empty"),
    ))
    sections.append((
        "section-what-changed", "What Changed",
        _nav_icon("present") if has_wc else _nav_icon("empty"),
    ))
    sections.append((
        "section-key-decisions", "Key Decisions",
        _nav_icon("count", len(decisions)) if decisions
        else _nav_icon("empty"),
    ))

    # Tier 2: Factory
    if has_scenarios or fh:
        sections.append(("__group__", "Factory", ""))
        if has_scenarios:
            if not scenarios:
                sc_icon = _nav_icon("empty")
            elif failing_scenarios > 0:
                sc_icon = _nav_icon("fail")
            else:
                sc_icon = _nav_icon("pass")
        else:
            specs_list = data.get("specs", [])
            sc_icon = _nav_icon("present") if specs_list else _nav_icon("empty")
        sections.append(("section-specs-scenarios", specs_label, sc_icon))
        if has_scenarios:
            sections.append((
                "section-convergence", "Convergence",
                _nav_icon("pass") if conv_status == "passing"
                else _nav_icon("fail"),
            ))
        if fh:
            sections.append((
                "section-factory-history", "Factory History",
                _nav_icon("count", iteration_count) if iteration_count > 0
                else _nav_icon("empty"),
            ))

    # Tier 3: Review & Evidence
    sections.append(("__group__", "Review &amp; Evidence", ""))
    sections.append((
        "section-review-gates", "Review Gates",
        _nav_icon("pass") if all_gates_pass else _nav_icon("fail"),
    ))
    aa_icon_map = {
        "healthy": _nav_icon("pass"),
        "needs-attention": _nav_icon("warn"),
        "action-required": _nav_icon("fail"),
    }
    sections.append((
        "section-arch-assessment", "Arch Assessment",
        aa_icon_map.get(aa_health, _nav_icon("empty")),
    ))
    sections.append((
        "section-code-review", "Code Review",
        _nav_icon("count-fail", cf_count) if cf_count > 0
        else _nav_icon("pass") if findings else _nav_icon("empty"),
    ))
    sections.append((
        "section-ci-performance", "CI Performance",
        _nav_icon("pass") if ci and ci_all_pass
        else _nav_icon("fail") if ci and not ci_all_pass
        else _nav_icon("empty"),
    ))

    # Tier 4: Follow-ups
    sections.append(("__group__", "Follow-ups", ""))
    sections.append((
        "section-post-merge", "Post-Merge Items",
        _nav_icon("count-warn", len(pm)) if pm
        else _nav_icon("empty"),
    ))

    items = []
    for section_id, label, icon_html in sections:
        if section_id == "__group__":
            items.append(
                f'<div class="sb-nav-group-label">{label or ""}</div>'
            )
            continue
        if label is None:
            items.append('<div class="sb-nav-separator"></div>')
            continue
        items.append(
            f'<div class="sb-nav-item" data-section="{section_id}" '
            f'onclick="scrollToSection(\'{section_id}\')">\n'
            f'  {icon_html}\n'
            f'  <span>{label}</span>\n'
            f'</div>'
        )
    return "\n".join(items)


def render_review_gates_cards(convergence: dict, has_scenarios: bool = True) -> str:
    """Render expandable review gate cards for the Review Gates section.

    Each gate gets an expandable card with name, status, statusText,
    summary, and detail.  Cards carry ``data-gate-name`` for JS navigation.
    """
    cards = []
    for gate in convergence.get("gates", []):
        name = gate.get("name", "")
        if not has_scenarios and "scenario" in name.lower():
            continue
        st = gate.get("status", "passing")
        status_text = gate.get("statusText", "")
        summary = esc(gate.get("summary", ""))
        detail = gate.get("detail", "")
        cards.append(
            f'<div class="gate-review-card" data-gate-name="{esc(name)}" '
            f"onclick=\"this.classList.toggle('open')\">\n"
            f'  <div class="gate-name">{esc(name)}</div>\n'
            f'  <div class="gate-status {st}">{esc(status_text)}</div>\n'
            f'  <div class="gate-summary">{summary}</div>\n'
            f'  <div class="gate-detail">{detail}</div>\n'
            f"</div>"
        )
    return "\n          ".join(cards)


# ── v2 Tier 3 section renderers ─────────────────────────────────────


def render_code_diffs_list(data: dict) -> str:
    """Render the Code Diffs file list for Tier 3 inline expansion."""
    code_diffs = data.get("codeDiffs", [])
    if not code_diffs:
        return '<p style="color:var(--text-muted);font-size:13px">No files changed.</p>'
    # Build zone ID → category lookup from architecture data
    zone_categories = {
        z["id"]: z.get("category", "product")
        for z in data.get("architecture", {}).get("zones", [])
    }
    items = []
    for cd in code_diffs:
        path = cd.get("path", "")
        adds = cd.get("additions", 0)
        dels = cd.get("deletions", 0)
        status = cd.get("status", "modified")
        zones = cd.get("zones", [])
        zones_str = " ".join(zones)
        zone_tags = " ".join(
            _zone_tag(z, zone_categories)
            for z in zones
        )
        items.append(
            f'<div class="cd-file-item" data-path="{esc(path)}" '
            f'data-zones="{esc(zones_str)}">\n'
            f'  <div class="cd-file-header" onclick="toggleCodeDiff(this.parentElement)">\n'
            f'    <span class="cd-file-path">{esc(path)}</span>\n'
            f'    <span class="cd-file-stats">'
            f'<span class="cd-add">+{adds}</span> '
            f'<span class="cd-del">&minus;{dels}</span></span>\n'
            f'    <span class="cd-file-status {status}">{esc(status)}</span>\n'
            f'    <span class="cd-file-zones">{zone_tags}</span>\n'
            f'  </div>\n'
            f'  <div class="cd-file-body">\n'
            f'    <div class="cd-file-toolbar">\n'
            f'      <button class="cd-file-tab active" '
            f'onclick="event.stopPropagation();setCodeDiffTab(this,this.closest(\'.cd-file-item\'),\'side-by-side\')">Side-by-side</button>\n'
            f'      <button class="cd-file-tab" '
            f'onclick="event.stopPropagation();setCodeDiffTab(this,this.closest(\'.cd-file-item\'),\'integrated\')">Unified</button>\n'
            f'      <button class="cd-file-tab" '
            f'onclick="event.stopPropagation();setCodeDiffTab(this,this.closest(\'.cd-file-item\'),\'raw\')">Raw</button>\n'
            f'    </div>\n'
            f'    <div class="cd-file-diff-content"></div>\n'
            f'  </div>\n'
            f'</div>'
        )
    return "\n".join(items)


def render_code_review_list(data: dict) -> str:
    """Render code review as a table with one column per agent paradigm.

    - Each file gets a row with agent grade columns (CH, SE, TI, AD, AR).
    - Agents without findings for a file show a dash ("—").
    - Click on row expands to show per-agent detail.
    - Click on file path opens the diff modal.
    """
    findings = data.get("agenticReview", {}).get("findings", [])
    code_diffs = data.get("codeDiffs", [])

    # Build zone ID → category lookup from architecture data
    zone_categories = {
        z["id"]: z.get("category", "product")
        for z in data.get("architecture", {}).get("zones", [])
    }

    # All agent paradigms in display order
    agent_paradigms = [
        ("CH", "code-health", "Code Health"),
        ("SE", "security", "Security"),
        ("TI", "test-integrity", "Test Integrity"),
        ("AD", "adversarial", "Adversarial"),
        ("AR", "architecture", "Architecture"),
    ]
    # Build findings lookup by file path
    findings_by_file: dict[str, list[dict]] = {}
    for f in findings:
        path = f.get("file", "")
        findings_by_file.setdefault(path, []).append(f)

    # Union of code diffs and findings
    all_files: dict[str, dict] = {}
    for cd in code_diffs:
        path = cd.get("path", "")
        all_files[path] = cd
    for path in findings_by_file:
        if path not in all_files:
            all_files[path] = {
                "path": path,
                "additions": 0,
                "deletions": 0,
                "status": "reviewed",
                "zones": [],
            }

    if not all_files:
        return '<p style="color:var(--text-muted);font-size:13px">No files changed.</p>'

    # Table header
    header_cols = "".join(
        f'<th class="cr-agent-col" title="{name}">{abbrev}</th>'
        for abbrev, _, name in agent_paradigms
    )
    html = (
        '<table class="cr-table">'
        "<thead><tr>"
        "<th>File</th>"
        f"{header_cols}"
        "<th>+/&minus;</th>"
        "<th>Zone</th>"
        "</tr></thead><tbody>"
    )

    for path, cd in all_files.items():
        file_findings = findings_by_file.get(path, [])
        zones = cd.get("zones", [])
        zones_str = " ".join(zones) if isinstance(zones, list) else zones
        additions = cd.get("additions", 0)
        deletions = cd.get("deletions", 0)

        # Build agent → grade + detail maps
        agent_grades: dict[str, str] = {}
        agent_details: dict[str, list[dict]] = {}
        for ff in file_findings:
            agent_name = ff.get("agent", "")
            abbrev = AGENT_ABBREV.get(
                agent_name, agent_name[:2].upper() if agent_name else "?"
            )
            grade = ff.get("grade", "N/A")
            # Keep worst grade
            if abbrev not in agent_grades or GRADE_SORT.get(
                grade, 5
            ) < GRADE_SORT.get(agent_grades[abbrev], 5):
                agent_grades[abbrev] = grade
            agent_details.setdefault(abbrev, []).append(ff)

        # Grade cells
        grade_cells = ""
        for abbrev, _, _ in agent_paradigms:
            if abbrev in agent_grades:
                grade = agent_grades[abbrev]
                gc = GRADE_CLASS.get(grade, "na")
                grade_cells += (
                    f'<td class="cr-agent-col">'
                    f'<span class="grade {gc}" '
                    f'style="width:24px;height:24px;line-height:24px;'
                    f'font-size:11px">{esc(grade)}</span></td>'
                )
            else:
                grade_cells += (
                    '<td class="cr-agent-col">'
                    '<span class="cr-grade-dash">&mdash;</span></td>'
                )

        # Zone tags
        zone_html = ""
        if zones:
            zone_list = zones if isinstance(zones, list) else zones.split()
            zone_html = " ".join(
                _zone_tag(z, zone_categories)
                for z in zone_list
            )

        # File row
        html += (
            f'<tr class="cr-file-row" data-zones="{esc(zones_str)}" '
            f'onclick="toggleCRDetail(this)">'
            f"<td>"
            f'<code class="file-path-link" '
            f"onclick=\"event.stopPropagation();"
            f"openFileModal('{esc(path)}')\">"
            f"{esc(path)}</code></td>"
            f"{grade_cells}"
            f'<td><span class="cd-file-stats">'
            f'<span class="cd-add">+{additions}</span> '
            f'<span class="cd-del">&minus;{deletions}</span>'
            f"</span></td>"
            f"<td>{zone_html}</td>"
            f"</tr>\n"
        )

        # Detail row: per-agent breakdown (all paradigms, including "no comments")
        detail_parts: list[str] = []
        for abbrev, _agent_key, agent_name in agent_paradigms:
            agent_findings = agent_details.get(abbrev, [])
            if agent_findings:
                grade = agent_grades.get(abbrev, "N/A")
                gc = GRADE_CLASS.get(grade, "na")
                # detail is HTML-safe: sanitized at ingestion by the Gate 0
                # review agents. Contains structured HTML from agent analysis.
                detail_text = " ".join(
                    ff.get("detail", "") or ff.get("notable", "")
                    for ff in agent_findings
                )
                detail_parts.append(
                    f'<div class="agent-detail-entry">'
                    f'<span class="agent-detail-header">'
                    f'<span class="agent-abbrev">{esc(abbrev)}</span>'
                    f'<span class="grade {gc}">{esc(grade)}</span>'
                    f'<span class="agent-detail-name">'
                    f"{esc(agent_name)}</span>"
                    f"</span>"
                    f'<div class="agent-detail-body">{detail_text}</div>'
                    f"</div>"
                )
            else:
                detail_parts.append(
                    f'<div class="agent-detail-entry cr-no-comment">'
                    f'<span class="agent-detail-header">'
                    f'<span class="agent-abbrev">{esc(abbrev)}</span>'
                    f'<span class="grade na">&mdash;</span>'
                    f'<span class="agent-detail-name">'
                    f"{esc(agent_name)}</span>"
                    f"</span>"
                    f'<div class="agent-detail-body">'
                    f"<em>No comments on this file.</em></div>"
                    f"</div>"
                )

        ncols = len(agent_paradigms) + 3  # file + agents + stats + zone
        html += (
            f'<tr class="cr-detail-row" data-zones="{esc(zones_str)}">'
            f'<td colspan="{ncols}">'
            + "".join(detail_parts)
            + "</td></tr>\n"
        )

    html += "</tbody></table>"
    return html


def render_factory_history_section(data: dict) -> str:
    """Render Factory History as a full section (Tier 3) or empty string if null."""
    history = data.get("factoryHistory")
    if not history:
        return ""
    summary = render_history_summary_cards(history)
    timeline = render_history_timeline(history.get("timeline", []))
    gate_rows = render_gate_findings_rows(history.get("gateFindings", []))
    return (
        f'<div class="section">\n'
        f'  <div class="section-header"'
        f' onclick="this.parentElement.classList.toggle(\'collapsed\')">\n'
        f'    <h2>Factory History</h2>\n'
        f'    <span class="chevron">&#x25BC;</span>\n'
        f'  </div>\n'
        f'  <div class="section-body">\n'
        f'    <div class="convergence-grid" style="margin-bottom:20px">{summary}</div>\n'
        f'    <h3 style="font-size:13px;font-weight:700;margin-bottom:12px">Timeline</h3>\n'
        f'    <div class="history-timeline">{timeline}</div>\n'
        f'    <h3 style="font-size:13px;font-weight:700;margin:20px 0 12px">Gate Findings</h3>\n'
        f'    <table>\n'
        f'      <thead><tr><th>Phase</th><th>Gate 1</th>'
        f'<th>Gate 2</th><th>Gate 3</th><th>Action</th></tr></thead>\n'
        f'      <tbody>{gate_rows}</tbody>\n'
        f'    </table>\n'
        f'  </div>\n'
        f'</div>'
    )


# ── Main render pipeline ────────────────────────────────────────────


def _escape_script_closing(text: str) -> str:
    """Escape </script> sequences so embedded JSON doesn't break HTML parsing.

    The HTML parser scans for </script> to close <script> blocks regardless
    of JavaScript string context. If raw file content (e.g., template.html)
    contains </script>, the browser closes the <script> tag prematurely,
    corrupting the page. Replacing </script with <\\/script is safe — the
    JS engine interprets \\/ as / but the HTML parser no longer sees a
    closing tag.
    """
    return re.sub(
        r"</([Ss][Cc][Rr][Ii][Pp][Tt])",
        lambda m: r"<\/" + m.group(1),
        text,
    )


def _calculate_viewbox(arch: dict) -> str:
    """Calculate SVG viewBox from architecture zone positions.

    Returns a viewBox string that fits all zones, labels, and arrows
    with padding. The left margin accounts for row labels rendered
    with text-anchor='end'.
    """
    if not arch or not arch.get("zones"):
        return "0 0 780 360"  # fallback default

    min_x, min_y = float("inf"), float("inf")
    max_x, max_y = float("-inf"), float("-inf")

    for zone in arch.get("zones", []):
        pos = zone.get("position", {})
        x, y = pos.get("x", 0), pos.get("y", 0)
        w, h = pos.get("width", 120), pos.get("height", 70)
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x + w)
        max_y = max(max_y, y + h)

    for arrow in arch.get("arrows", []):
        for endpoint in ("from", "to"):
            pt = arrow.get(endpoint, {})
            max_x = max(max_x, pt.get("x", 0))
            max_y = max(max_y, pt.get("y", 0))

    # Row labels sit at small x with text-anchor="end", extending left.
    # Reserve ~120px to the left of min_x for label text.
    label_margin = 120
    pad = 20  # general padding

    vb_x = min(min_x - label_margin, 0) - pad
    vb_y = min(min_y, 0) - pad
    vb_w = max_x - vb_x + pad
    vb_h = max_y - vb_y + pad

    return f"{vb_x:.0f} {vb_y:.0f} {vb_w:.0f} {vb_h:.0f}"


def render(
    data_path: str | Path,
    output_path: str | Path,
    diff_data_path: str | Path | None = None,
    template_version: str = "v1",
) -> None:
    """Render the review pack HTML from template + data.

    Args:
        data_path: Path to ReviewPackData JSON (Pass 2 output).
        output_path: Where to write the rendered HTML.
        diff_data_path: Path to diff data JSON (Pass 1 output).
            If provided, the diff data is embedded inline in the HTML,
            making the pack truly self-contained (no companion file
            needed, no CORS issues with file:// protocol).
            Generated by generate_diff_data.py — deterministic git
            output, zero LLM involvement.
        template_version: "v1" (default) or "v2" (Mission Control layout).
    """
    template_path = TEMPLATE_V2_PATH if template_version == "v2" else TEMPLATE_PATH
    if not template_path.exists():
        print(f"ERROR: Template not found: {template_path}", file=sys.stderr)
        sys.exit(1)
    template = template_path.read_text(encoding="utf-8")
    data = json.loads(Path(data_path).read_text(encoding="utf-8"))

    header = data.get("header", {})

    # Load diff data for inline embedding
    diff_data_json: str | None = None
    if diff_data_path is not None:
        dd_path = Path(diff_data_path)
        if dd_path.exists():
            diff_data_json = dd_path.read_text(encoding="utf-8")
            # Verify it's valid JSON (deterministic — no transform)
            json.loads(diff_data_json)
            print(f"Embedding diff data inline ({dd_path.stat().st_size / 1024:.0f} KB)")
        else:
            print(
                f"WARNING: diff data file not found: {dd_path}",
                file=sys.stderr,
            )

    # ── Text injection map (marker → replacement) ──
    replacements: dict[str, str] = {
        # Simple text fields
        "<!-- INJECT: header.title -->": esc(header.get("title", "")),
        "<!-- INJECT: header.prUrl -->": esc(header.get("prUrl", "")),
        "<!-- INJECT: header.headBranch -->": esc(header.get("headBranch", "")),
        "<!-- INJECT: header.baseBranch -->": esc(header.get("baseBranch", "")),
        "<!-- INJECT: header.headSha -->": esc(header.get("headSha", "")),
        "<!-- INJECT: header.generatedAt -->": esc(header.get("generatedAt", "")),
        # Complex section injections
        "<!-- INJECT: stat items for additions, deletions, files, commits -->": (
            render_stat_items(header)
        ),
        "<!-- INJECT: status badges -->": render_status_badges(header),
        "<!-- INJECT: Factory History tab button "
        "(conditionally, only if factoryHistory is present) -->": (
            render_factory_history_tab_button(data)
        ),
        "<!-- INJECT: architecture zones, labels, arrows from DATA.architecture -->": (
            render_architecture_svg(data.get("architecture", {}))
        ),
        "<!-- INJECT: specification items from DATA.specs -->": render_spec_list(
            data.get("specs", [])
        ),
        "<!-- INJECT: scenario category legend items -->": render_scenario_legend(
            data.get("scenarios", [])
        ),
        "<!-- INJECT: scenario cards from DATA.scenarios -->": render_scenario_cards(
            data.get("scenarios", [])
        ),
        "<!-- INJECT: whatChanged.defaultSummary.infrastructure and .product -->": (
            render_what_changed_default(data.get("whatChanged", {}))
        ),
        "<!-- INJECT: wc-zone-detail divs for each zone -->": (
            render_what_changed_zones(data.get("whatChanged", {}))
        ),
        "<!-- INJECT: adversarial review method badge -->": (
            render_agentic_method_badge(data.get("agenticReview", {}))
            + render_agentic_legend()
        ),
        "<!-- INJECT: adversarial finding rows from DATA.agenticReview.findings -->": (
            render_agentic_rows(
                data.get("agenticReview", {}),
                zone_categories={
                    z["id"]: z.get("category", "product")
                    for z in data.get("architecture", {}).get("zones", [])
                },
            )
        ),
        "<!-- INJECT: CI check rows from DATA.ciPerformance -->": render_ci_rows(
            data.get("ciPerformance", []),
            zone_categories={
                z["id"]: z.get("category", "product")
                for z in data.get("architecture", {}).get("zones", [])
            },
        ),
        "<!-- INJECT: decision cards from DATA.decisions -->": render_decision_cards(
            data.get("decisions", []),
            zone_categories={
                z["id"]: z.get("category", "product")
                for z in data.get("architecture", {}).get("zones", [])
            },
        ),
        "<!-- INJECT: convergence gate cards + overall card from DATA.convergence -->": (
            render_convergence_grid(data.get("convergence", {}))
        ),
        "<!-- INJECT: post-merge items from DATA.postMergeItems -->": (
            render_post_merge_items(
                data.get("postMergeItems", []),
                zone_categories={
                    z["id"]: z.get("category", "product")
                    for z in data.get("architecture", {}).get("zones", [])
                },
            )
        ),
    }

    # Factory history (conditional) — v1 uses individual markers, v2 uses a full section
    history = data.get("factoryHistory")
    has_scenarios = bool(data.get("scenarios"))
    if template_version == "v2":
        # v2: sidebar + section markers
        replacements["<!-- INJECT: sidebar.prMeta -->"] = render_sidebar_pr_meta(header)
        replacements["<!-- INJECT: sidebar.verdictBadge -->"] = render_sidebar_verdict(data)
        replacements["<!-- INJECT: sidebar.commitScope -->"] = render_sidebar_commit_scope(data)
        replacements["<!-- INJECT: sidebar.mergeButton -->"] = render_sidebar_merge_button(data)
        replacements["<!-- INJECT: sidebar.refreshButton -->"] = (
            render_sidebar_refresh_button(data)
        )
        replacements["<!-- INJECT: sidebar.statusBadges -->"] = (
            render_sidebar_status_badges(header, has_scenarios=has_scenarios)
        )
        replacements["<!-- INJECT: sidebar.gatePills -->"] = render_sidebar_gate_pills(
            data.get("convergence", {}), has_scenarios=has_scenarios
        )
        replacements["<!-- INJECT: sidebar.sectionNav -->"] = render_sidebar_section_nav(
            data, has_scenarios=has_scenarios
        )
        replacements["<!-- INJECT: review gates cards -->"] = (
            render_review_gates_cards(
                data.get("convergence", {}), has_scenarios=has_scenarios
            )
        )
        replacements["<!-- INJECT: architecture assessment section -->"] = (
            render_architecture_assessment(data)
        )
        replacements["<!-- INJECT: code diff file list -->"] = render_code_diffs_list(data)
        replacements["<!-- INJECT: code review file list -->"] = render_code_review_list(data)
        replacements["<!-- INJECT: factory history section -->"] = (
            render_factory_history_section(data)
        )
        # Conditional specs/scenarios section title and scenarios block
        replacements["<!-- INJECT: specsScenarios.title -->"] = (
            "Spec &amp; Scenarios" if has_scenarios else "Specifications"
        )
        if has_scenarios:
            scenario_legend = render_scenario_legend(data.get("scenarios", []))
            scenario_cards = render_scenario_cards(data.get("scenarios", []))
            replacements["<!-- INJECT: specsScenarios.scenariosBlock -->"] = (
                '<h3 style="font-size:13px;margin:14px 0 8px">Scenarios</h3>\n'
                f'          <div class="scenario-legend" id="scenario-legend">\n'
                f'            {scenario_legend}\n'
                f'          </div>\n'
                f'          <div class="scenario-grid" id="scenario-grid">\n'
                f'            {scenario_cards}\n'
                f'          </div>'
            )
        else:
            replacements["<!-- INJECT: specsScenarios.scenariosBlock -->"] = ""
        # Conditional display for factory tier, convergence, and factory history
        has_factory = has_scenarios or bool(history)
        replacements["<!-- INJECT: factoryTier.displayAttr -->"] = (
            "" if has_factory else 'style="display:none"'
        )
        replacements["<!-- INJECT: convergence.displayAttr -->"] = (
            "" if has_scenarios else 'style="display:none"'
        )
        replacements["<!-- INJECT: factoryHistory.displayAttr -->"] = (
            "" if has_scenarios else 'style="display:none"'
        )
    else:
        # v1: individual factory history markers
        if history:
            replacements[
                "<!-- INJECT: iteration count + satisfaction trajectory cards -->"
            ] = render_history_summary_cards(history)
            replacements[
                "<!-- INJECT: factory history events from DATA.factoryHistory.timeline -->"
            ] = render_history_timeline(history.get("timeline", []))
            replacements[
                "<!-- INJECT: gate finding rows from DATA.factoryHistory.gateFindings -->"
            ] = render_gate_findings_rows(history.get("gateFindings", []))

    # ── Apply all replacements ──
    for marker, content in replacements.items():
        template = template.replace(marker, content)

    # Clean up sub-comment hints (not injection points, just guidance)
    for hint in (
        '<!-- Row labels -->',
        '<!-- Zone boxes (rect.zone-box[data-zone="..."]) -->',
        '<!-- Zone labels (text.zone-label) -->',
        '<!-- Zone sublabels (text.zone-sublabel) -->',
        '<!-- File count circles (circle.zone-count-bg + text.zone-file-count) -->',
        '<!-- Flow arrows (line with marker-end) -->',
        '<!-- Each row: tr.adv-row[data-zones="..."][data-grade-sort="N"] + tr.adv-detail-row -->',
        '<!-- Each: tr.expandable + tr.detail-row with sub-checks -->',
    ):
        template = template.replace(hint, "")

    # ── Dynamic SVG viewBox from architecture data ──
    arch_data = data.get("architecture", {})
    viewbox = _calculate_viewbox(arch_data)
    template = template.replace(
        'viewBox="0 0 780 360"',
        f'viewBox="{viewbox}"',
    )
    vb_parts = viewbox.split()
    vb_width = float(vb_parts[2])
    template = template.replace(
        "max-width:780px",
        f"max-width:{max(780, int(vb_width))}px",
    )

    # ── File coverage verification ──
    unzoned = arch_data.get("unzonedFiles", [])
    total_files = header.get("filesChanged", 0)
    zone_file_sum = sum(z.get("fileCount", 0) for z in arch_data.get("zones", []))
    if unzoned:
        print(
            f"WARNING: {len(unzoned)} file(s) not mapped to any "
            f"architecture zone: {unzoned}",
            file=sys.stderr,
        )
    if total_files > 0 and (zone_file_sum + len(unzoned)) < total_files:
        print(
            f"WARNING: zone coverage gap — {zone_file_sum} zoned + "
            f"{len(unzoned)} unzoned = "
            f"{zone_file_sum + len(unzoned)}, but "
            f"header reports {total_files} files",
            file=sys.stderr,
        )

    # ── Inject DATA JSON for JS interactivity ──
    # Use rfind to replace the LAST occurrence (inside the <script> block),
    # not an earlier occurrence that may appear inside rendered finding text.
    data_json = json.dumps(data, indent=2)
    data_placeholder = "const DATA = {};"
    last_idx = template.rfind(data_placeholder)
    if last_idx >= 0:
        template = (
            template[:last_idx]
            + f"const DATA = {data_json};"
            + template[last_idx + len(data_placeholder) :]
        )

    # ── Fix PR URL href ──
    pr_url = header.get("prUrl", "#")
    template = template.replace(
        'id="pr-url" href="#"', f'id="pr-url" href="{esc(pr_url)}"'
    )

    # ── Embed reference file content for non-diff files ──
    # Spec files, scenario files, etc. aren't in the diff data but users
    # still need to view their raw content via the file modal.
    ref_files: dict[str, str] = {}
    repo_root = Path.cwd()
    for spec in data.get("specs", []):
        spec_path = spec.get("path", "")
        if spec_path:
            full = repo_root / spec_path
            if full.exists():
                ref_files[spec_path] = full.read_text(encoding="utf-8")
    if ref_files:
        safe_ref_json = _escape_script_closing(json.dumps(ref_files))
        ref_inject = (
            "<script>\n"
            "// Reference file content embedded by render_review_pack.py\n"
            "// These files are not in the diff but are viewable in raw mode.\n"
            f"const REFERENCE_FILES = {safe_ref_json};\n"
            "</script>\n"
        )
        template = template.replace(
            "<script>\n// ═══",
            ref_inject + "<script>\n// ═══",
            1,
        )
        print(f"Embedded {len(ref_files)} reference file(s) for raw view")

    # ── Embed diff data inline for self-contained pack ──
    # The template's loadDiffData() fetches pr_diff_data.json via fetch().
    # This fails on file:// protocol due to CORS. To make the pack truly
    # self-contained, we embed the diff data in a <script> block and
    # replace the fetch with an immediate callback.
    #
    # Trust chain: generate_diff_data.py runs `git diff` and `git show`
    # — deterministic git CLI output, zero LLM, byte-equivalent to
    # what GitHub displays for the same commit SHA.
    #
    # CRITICAL: The diff data may contain raw file content (e.g.,
    # template.html) with literal </script> tags. The HTML parser
    # does not understand JS string context — it would close the
    # <script> block prematurely, rendering the rest as visible text.
    # _escape_script_closing() prevents this.
    if diff_data_json is not None:
        safe_diff_json = _escape_script_closing(diff_data_json)
        # Inject diff data as a global variable
        diff_inject = (
            "<script>\n"
            "// Diff data embedded inline by render_review_pack.py\n"
            "// Source: generate_diff_data.py (Pass 1, deterministic)\n"
            "// Trust: raw git diff/show output, zero LLM involvement\n"
            f"const DIFF_DATA_INLINE = {safe_diff_json};\n"
            "</script>\n"
        )
        # Insert before the main <script> block (v1 uses ═══, v2 uses ===)
        if "<script>\n// ═══" in template:
            template = template.replace(
                "<script>\n// ═══",
                diff_inject + "<script>\n// ═══",
                1,
            )
        else:
            template = template.replace(
                "<script>\n// ===",
                diff_inject + "<script>\n// ===",
                1,
            )
        # Replace fetch-based loading with inline data
        template = template.replace(
            "fetch('pr_diff_data.json')",
            "Promise.resolve(new Response(JSON.stringify("
            "DIFF_DATA_INLINE)))",
        )

    # ── Write output ──
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(template, encoding="utf-8")

    size_kb = out.stat().st_size / 1024
    print(f"Rendered: {out} ({size_kb:.0f} KB)")

    # ── Quick sanity check: any unreplaced markers? ──
    # Count markers OUTSIDE of embedded content (diff data, reference files)
    # to avoid false positives from SKILL.md/template.html diffs.
    remaining = template.count("<!-- INJECT:")
    if remaining > 0:
        # Check if all remaining markers are inside <script> blocks (embedded data)
        outside_script = re.sub(
            r"<script\b[^>]*>.*?</script>",
            "",
            template,
            flags=re.DOTALL,
        )
        real_remaining = outside_script.count("<!-- INJECT:")
        if real_remaining > 0:
            print(
                f"WARNING: {real_remaining} unreplaced <!-- INJECT: --> "
                f"markers remain in HTML content!",
                file=sys.stderr,
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render PR review pack HTML from template + data (Pass 3)."
    )
    parser.add_argument(
        "--data", required=True, help="Path to ReviewPackData JSON file"
    )
    parser.add_argument("--output", required=True, help="Output HTML file path")
    parser.add_argument(
        "--diff-data",
        default=None,
        help=(
            "Path to diff data JSON (Pass 1 output). "
            "Embeds inline for self-contained pack."
        ),
    )
    parser.add_argument(
        "--template",
        default="v1",
        choices=["v1", "v2"],
        help="Template version: v1 (default) or v2 (Mission Control layout).",
    )
    args = parser.parse_args()
    render(args.data, args.output, args.diff_data, args.template)


if __name__ == "__main__":
    main()
