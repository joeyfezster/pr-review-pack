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
        label_y = y + h / 2 - 4
        sublabel_y = y + h / 2 + 10
        opacity = "1" if zone.get("isModified") else "0.6"

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
        parts.append(
            f'<text x="{cx}" y="{sublabel_y}" text-anchor="middle" '
            f'class="zone-sublabel" style="pointer-events:none">'
            f'{esc(zone["sublabel"])}</text>'
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
    """Render the Architecture Assessment section from architect agent output."""
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

    # Diagram narrative (what changed architecturally)
    narrative = assessment.get("diagramNarrative", "")
    if narrative:
        parts.append(f'<div class="arch-narrative">{narrative}</div>')

    # Unzoned files — THE BIG ONE
    unzoned = assessment.get("unzonedFiles", [])
    if unzoned:
        parts.append('<div class="arch-warning-section">')
        parts.append(
            f"<h4>&#x26A0; {len(unzoned)} Unzoned File(s)</h4>"
        )
        parts.append(
            "<table><thead><tr>"
            "<th>File</th><th>Suggested Zone</th><th>Reason</th>"
            "</tr></thead><tbody>"
        )
        for uf in unzoned:
            suggested = esc(uf.get("suggestedZone") or "\u2014")
            parts.append(
                f"<tr>"
                f'<td><code>{esc(uf["path"])}</code></td>'
                f"<td>{suggested}</td>"
                f'<td>{esc(uf["reason"])}</td>'
                f"</tr>"
            )
        parts.append("</tbody></table></div>")

    # Zone changes
    changes = assessment.get("zoneChanges", [])
    if changes:
        parts.append('<div class="arch-changes-section">')
        parts.append("<h4>Architectural Changes Detected</h4>")
        for ch in changes:
            ch_type = esc(ch.get("type", "").replace("_", " ").title())
            parts.append(
                f'<div class="arch-change-item">'
                f"<strong>{ch_type}</strong>: "
                f'{esc(ch.get("zone", ""))} &mdash; '
                f'{esc(ch.get("reason", ""))}</div>'
            )
        parts.append("</div>")

    # Coupling warnings
    coupling = assessment.get("couplingWarnings", [])
    if coupling:
        parts.append('<div class="arch-coupling-section">')
        parts.append("<h4>Cross-Zone Coupling</h4>")
        for cw in coupling:
            parts.append(
                f'<div class="arch-coupling-item">'
                f'{esc(cw.get("fromZone", ""))} &rarr; '
                f'{esc(cw.get("toZone", ""))}: '
                f'{esc(cw.get("evidence", ""))}</div>'
            )
        parts.append("</div>")

    # Registry warnings
    reg_warnings = assessment.get("registryWarnings", [])
    if reg_warnings:
        parts.append('<div class="arch-registry-section">')
        parts.append("<h4>Zone Registry Health</h4>")
        for rw in reg_warnings:
            sev = rw.get("severity", "WARNING").lower()
            parts.append(
                f'<div class="arch-registry-item">'
                f'<span class="badge {sev}">'
                f'{esc(rw.get("severity", ""))}</span> '
                f'{esc(rw.get("zone", ""))}: '
                f'{esc(rw.get("warning", ""))}</div>'
            )
        parts.append("</div>")

    # Doc recommendations
    doc_recs = assessment.get("docRecommendations", [])
    if doc_recs:
        parts.append('<div class="arch-docs-section">')
        parts.append("<h4>Documentation Recommendations</h4>")
        for dr in doc_recs:
            parts.append(
                f'<div class="arch-doc-item">'
                f'<code>{esc(dr.get("path", ""))}</code>: '
                f'{esc(dr.get("reason", ""))}</div>'
            )
        parts.append("</div>")

    # Decision zone verification
    verifications = assessment.get("decisionZoneVerification", [])
    if verifications:
        unverified = [v for v in verifications if not v.get("verified")]
        if unverified:
            parts.append('<div class="arch-verification-section">')
            parts.append("<h4>Unverified Decision-Zone Claims</h4>")
            for v in unverified:
                parts.append(
                    f'<div class="arch-verification-item">'
                    f'Decision #{v.get("decisionNumber", "?")}: '
                    f'zones {esc(", ".join(v.get("claimedZones", [])))} '
                    f'&mdash; {esc(v.get("reason", ""))}</div>'
                )
            parts.append("</div>")

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
    """Infrastructure + product summaries. These fields may contain HTML."""
    default = wc.get("defaultSummary", {})
    parts = []
    infra = default.get("infrastructure", "")
    if infra:
        parts.append(f'<p><strong>Infrastructure:</strong> {infra}</p>')
    product = default.get("product", "")
    if product:
        parts.append(f'<p><strong>Product:</strong> {product}</p>')
    return "\n          ".join(parts)


def render_what_changed_zones(wc: dict) -> str:
    divs = []
    for z in wc.get("zoneDetails", []):
        # description may contain HTML
        divs.append(
            f'<div class="wc-zone-detail" data-zone="{esc(z["zoneId"])}">\n'
            f'  <h4>{esc(z["title"])}</h4>\n'
            f'  <p>{z["description"]}</p>\n'
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


def render_agentic_rows(review: dict) -> str:
    """Render agentic review rows grouped by file.

    Each file gets one master row with compact agent grade badges.
    Expanding shows per-agent detail.
    """
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

        # Master row (one per file)
        rows.append(
            f'<tr class="adv-row" data-zones="{esc(zones)}" '
            f'data-grade-sort="{worst_sort}" onclick="toggleAdvDetail(this)">\n'
            f'  <td><code class="file-path-link" '
            f"onclick=\"event.stopPropagation();"
            f"openFileModal('{esc(filepath)}')\">"
            f'{esc(filepath)}</code></td>\n'
            f'  <td class="agent-badges-cell">{badges_html}</td>\n'
            f'  <td><span class="zone-tag {layer_tag_class("product")}">'
            f'{esc(zones)}</span></td>\n'
            f'  <td>{esc(notable_text)}</td>\n'
            f'</tr>\n'
        )

        # Detail row: per-agent breakdown
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


def render_ci_rows(ci_checks: list[dict]) -> str:
    rows = []
    for ci in ci_checks:
        status_css = "pass" if ci["status"] == "pass" else "fail"
        health_css = ci.get("healthTag", "normal")
        detail = ci.get("detail", {})

        # Sub-checks
        sub_html = ""
        for chk in detail.get("checks", []):
            sub_html += (
                '<div class="ci-check-item" '
                "onclick=\"event.stopPropagation();this.classList.toggle('open')\">\n"
                f'  <div class="ci-check-summary">'
                f'<span class="ci-sub-chevron">&#x25B6;</span> '
                f'{esc(chk["label"])}</div>\n'
                f'  <div class="ci-check-detail">{chk.get("detail", "")}</div>\n'
                "</div>\n"
            )

        zones_html = " ".join(
            f'<span class="zone-tag product">{esc(z)}</span>'
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


def render_decision_cards(decisions: list[dict]) -> str:
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
            f'<span class="zone-tag product">{esc(z)}</span>'
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

        # body may contain HTML
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
        # detail may contain HTML
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
        cards.append(
            f'<div class="conv-card" onclick="this.classList.toggle(\'open\')">\n'
            f'  <div class="conv-name">Overall</div>\n'
            f'  <div class="conv-status {st}">{esc(overall["statusText"])}</div>\n'
            f'  <div class="conv-detail">{esc(overall["summary"])}</div>\n'
            f'  <div class="conv-card-detail">{overall.get("detail", "")}</div>\n'
            f"</div>"
        )
    return "\n          ".join(cards)


def render_post_merge_items(items: list[dict]) -> str:
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
            f'<span class="zone-tag product">{esc(z)}</span>'
            for z in item.get("zones", [])
        )

        # title and description may contain HTML
        rendered.append(
            f'<div class="pm-item">\n'
            f'  <div class="pm-header" '
            f"onclick=\"this.parentElement.classList.toggle('open')\">\n"
            f'    <span class="priority {priority}">'
            f"{esc(priority.upper())}</span>\n"
            f'    <span>{item.get("title", "")}</span>\n'
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
        # expandedDetail may contain HTML
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


def render_sidebar_status_badges(header: dict) -> str:
    """Render status badges (CI, Scenarios, Comments, Gate 0) in sidebar."""
    badges = []
    for b in header.get("statusBadges", []):
        icon = b.get("icon", "")
        badge_type = b.get("type", "info")
        badges.append(
            f'<span class="status-badge {badge_type}" '
            f'style="font-size:10px;padding:2px 8px">'
            f'{icon} {esc(b.get("label", ""))}</span>'
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

    html = f'<div class="sb-verdict-wrapper">'
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


def render_sidebar_gates(convergence: dict) -> str:
    """Render gate status rows for the sidebar."""
    rows = []
    for gate in convergence.get("gates", []):
        name = gate.get("name", "")
        st = gate.get("status", "failing")
        icon = "&#x2713;" if st == "passing" else "&#x2717;"
        color = "var(--green)" if st == "passing" else "var(--red)"
        rows.append(
            f'<div class="sb-gate-row" onclick="scrollToSection(\'section-convergence\')">\n'
            f'  <span>{esc(name)}</span>\n'
            f'  <span class="sb-gate-icon" style="color:{color}">{icon}</span>\n'
            f'</div>'
        )
    return "\n".join(rows)


def render_sidebar_metrics(data: dict) -> str:
    """Render metric counts: CI, Scenarios, Comments, Findings."""
    ci = data.get("ciPerformance", [])
    ci_pass = sum(1 for c in ci if c.get("status") == "pass")
    ci_total = len(ci)

    scenarios = data.get("scenarios", [])
    sc_pass = sum(1 for s in scenarios if s.get("status") == "pass")
    sc_total = len(scenarios)

    # Comment counts from header badges
    badges = data.get("header", {}).get("statusBadges", [])
    comment_badge: dict = next(
        (b for b in badges if "comment" in b.get("label", "").lower()), {}
    )
    comment_label = comment_badge.get("label", "0/0 comments")

    findings = data.get("agenticReview", {}).get("findings", [])
    finding_count = sum(
        1 for f in findings if f.get("grade") in ("C", "F")
    )

    metrics = [
        ("CI", f"{ci_pass}/{ci_total}",
         "section-ci-performance", ci_pass == ci_total),
        ("Scenarios", f"{sc_pass}/{sc_total}" if sc_total > 0 else "N/A",
         "section-specs-scenarios", sc_pass == sc_total and sc_total > 0),
        ("Comments", comment_label.split(" ")[0] if comment_badge else "0/0",
         "section-convergence",
         "0" not in comment_label.split("/")[0:1]),
        ("Findings", str(finding_count),
         "section-agentic-review", finding_count == 0),
    ]

    rows = []
    for label, value, section_id, is_ok in metrics:
        icon = "&#x2713;" if is_ok else "&#x26A0;"
        color = "var(--green)" if is_ok else "var(--yellow)"
        rows.append(
            f'<div class="sb-metric-row" onclick="scrollToSection(\'{section_id}\')">\n'
            f'  <span>{label}</span>\n'
            f'  <span>{value} <span style="color:{color}">{icon}</span></span>\n'
            f'</div>'
        )
    return "\n".join(rows)


def render_sidebar_zone_minimap(arch: dict) -> str:
    """Render zone mini-map with colored swatches and file counts."""
    items = []
    for zone in arch.get("zones", []):
        zone_id = zone.get("id", "")
        label = zone.get("label", zone_id)
        cat = zone.get("category", "product")
        colors = LAYER_COLORS.get(cat, LAYER_COLORS["product"])
        is_modified = zone.get("isModified", False)
        fc = zone.get("fileCount", 0)
        mod_class = "modified" if is_modified else "unmodified"
        count_html = f'<span class="sb-zone-count">({fc})</span>' if fc > 0 else ""
        items.append(
            f'<div class="sb-zone-item" data-zone="{esc(zone_id)}" '
            f'onclick="sidebarZoneClick(\'{esc(zone_id)}\')">\n'
            f'  <span class="sb-zone-swatch {mod_class}" '
            f'style="background:{colors["fill"]};border-color:{colors["stroke"]};'
            f'color:{colors["stroke"]}"></span>\n'
            f'  <span>{esc(label)}</span>\n'
            f'  {count_html}\n'
            f'</div>'
        )
    return (
        "\n".join(items)
        + '\n<div id="sb-zone-active" class="sb-zone-active"></div>\n'
        + '<div id="sb-clear-filter" class="sb-clear-filter"'
        + ' onclick="resetZones()">Clear filter</div>'
    )


def render_sidebar_section_nav(data: dict) -> str:
    """Render section navigation list with activity dots and count badges."""
    # Each entry: (section_id, label, dot_type)
    # Group headers use ("__group__", "Group Label", None)
    # Determine arch assessment nav dot
    arch_assessment = data.get("architectureAssessment")
    if arch_assessment:
        aa_health = arch_assessment.get("overallHealth", "healthy")
        aa_dot = "findings" if aa_health == "action-required" else "content"
    else:
        aa_dot = "empty"

    sections: list[tuple[str, str | None, str | None]] = [
        ("__group__", "Architecture & Context", None),
        ("section-architecture", "Architecture", _nav_dot_for_arch(data)),
        ("section-arch-assessment", "Arch Assessment", aa_dot),
        ("section-what-changed", "What Changed",
         _nav_dot_for_content(data, "whatChanged")),
        ("section-specs-scenarios", "Specs & Scenarios",
         _nav_dot_for_content(data, "scenarios")),
    ]
    # Safety & Reasoning
    review = data.get("agenticReview", {})
    findings = review.get("findings", [])
    has_critical = any(f.get("grade") in ("C", "F") for f in findings)
    sections.append(("__group__", "Safety & Reasoning", None))
    sections.append(
        ("section-agentic-review", "Agent Reviews",
         "findings" if has_critical else ("content" if findings else "empty"))
    )
    decisions = data.get("decisions", [])
    sections.append(
        ("section-key-decisions", "Key Decisions",
         "content" if decisions else "empty")
    )
    sections.append(("section-convergence", "Convergence", "content"))
    # Follow-ups & Evidence
    ci = data.get("ciPerformance", [])
    pm = data.get("postMergeItems", [])
    code_diffs = data.get("codeDiffs", [])
    sections.append(("__group__", "Follow-ups & Evidence", None))
    sections.append(
        ("section-ci-performance", "CI Performance",
         "content" if ci else "empty")
    )
    sections.append(
        ("section-post-merge", "Post-Merge Items",
         "content" if pm else "empty")
    )
    sections.append(
        ("section-code-diffs", "Code Diffs",
         "content" if code_diffs else "empty")
    )
    fh = data.get("factoryHistory")
    if fh:
        sections.append(
            ("section-factory-history", "Factory History", "content")
        )

    items = []
    for section_id, label, dot_type in sections:
        if section_id == "__group__":
            items.append(
                f'<div class="sb-nav-group-label">'
                f'{esc(label or "")}</div>'
            )
            continue
        if label is None:
            items.append('<div class="sb-nav-separator"></div>')
            continue
        dot_css = dot_type if dot_type in ("content", "findings") else "empty"
        count = ""
        if label == "Key Decisions" and decisions:
            count = f'<span class="sb-nav-count">({len(decisions)})</span>'
        elif label == "Post-Merge Items" and pm:
            count = f'<span class="sb-nav-count">({len(pm)})</span>'
        elif label == "Code Diffs" and code_diffs:
            count = f'<span class="sb-nav-count">({len(code_diffs)})</span>'
        items.append(
            f'<div class="sb-nav-item" data-section="{section_id}" '
            f'onclick="scrollToSection(\'{section_id}\')">\n'
            f'  <span class="sb-nav-dot {dot_css}"></span>\n'
            f'  <span>{esc(label)}</span>\n'
            f'  {count}\n'
            f'</div>'
        )
    return "\n".join(items)


def _nav_dot_for_arch(data: dict) -> str:
    arch = data.get("architecture", {})
    return "content" if arch.get("zones") else "empty"


def _nav_dot_for_content(data: dict, key: str) -> str:
    val = data.get(key)
    if isinstance(val, list):
        return "content" if val else "empty"
    if isinstance(val, dict):
        return "content" if any(val.values()) else "empty"
    return "empty"


# ── v2 Tier 3 section renderers ─────────────────────────────────────


def render_code_diffs_list(data: dict) -> str:
    """Render the Code Diffs file list for Tier 3 inline expansion."""
    code_diffs = data.get("codeDiffs", [])
    if not code_diffs:
        return '<p style="color:var(--text-muted);font-size:13px">No files changed.</p>'
    items = []
    for cd in code_diffs:
        path = cd.get("path", "")
        adds = cd.get("additions", 0)
        dels = cd.get("deletions", 0)
        status = cd.get("status", "modified")
        zones = cd.get("zones", [])
        zones_str = " ".join(zones)
        zone_tags = " ".join(
            f'<span class="zone-tag {layer_tag_class("product")}">{esc(z)}</span>'
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


def render_factory_history_section(data: dict) -> str:
    """Render Factory History as a full section (Tier 3) or empty string if null."""
    history = data.get("factoryHistory")
    if not history:
        return ""
    summary = render_history_summary_cards(history)
    timeline = render_history_timeline(history.get("timeline", []))
    gate_rows = render_gate_findings_rows(history.get("gateFindings", []))
    return (
        f'<div class="section" id="section-factory-history">\n'
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
            render_agentic_rows(data.get("agenticReview", {}))
        ),
        "<!-- INJECT: CI check rows from DATA.ciPerformance -->": render_ci_rows(
            data.get("ciPerformance", [])
        ),
        "<!-- INJECT: decision cards from DATA.decisions -->": render_decision_cards(
            data.get("decisions", [])
        ),
        "<!-- INJECT: convergence gate cards + overall card from DATA.convergence -->": (
            render_convergence_grid(data.get("convergence", {}))
        ),
        "<!-- INJECT: post-merge items from DATA.postMergeItems -->": (
            render_post_merge_items(data.get("postMergeItems", []))
        ),
    }

    # Factory history (conditional) — v1 uses individual markers, v2 uses a full section
    history = data.get("factoryHistory")
    if template_version == "v2":
        # v2: sidebar + section markers
        replacements["<!-- INJECT: sidebar.prMeta -->"] = render_sidebar_pr_meta(header)
        replacements["<!-- INJECT: sidebar.verdictBadge -->"] = render_sidebar_verdict(data)
        replacements["<!-- INJECT: sidebar.commitScope -->"] = render_sidebar_commit_scope(data)
        replacements["<!-- INJECT: sidebar.mergeButton -->"] = render_sidebar_merge_button(data)
        replacements["<!-- INJECT: sidebar.statusBadges -->"] = (
            render_sidebar_status_badges(header)
        )
        replacements["<!-- INJECT: sidebar.gatesStatus -->"] = render_sidebar_gates(
            data.get("convergence", {})
        )
        replacements["<!-- INJECT: sidebar.metrics -->"] = render_sidebar_metrics(data)
        replacements["<!-- INJECT: sidebar.zoneMiniMap -->"] = render_sidebar_zone_minimap(
            data.get("architecture", {})
        )
        replacements["<!-- INJECT: sidebar.sectionNav -->"] = render_sidebar_section_nav(data)
        replacements["<!-- INJECT: architecture assessment section -->"] = (
            render_architecture_assessment(data)
        )
        replacements["<!-- INJECT: code diff file list -->"] = render_code_diffs_list(data)
        replacements["<!-- INJECT: factory history section -->"] = (
            render_factory_history_section(data)
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
