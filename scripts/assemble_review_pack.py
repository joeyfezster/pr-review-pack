#!/usr/bin/env python3
"""Review Pack Assembly — validates .jsonl, transforms, merges, renders.

Reads all .jsonl files from docs/reviews/pr{N}/, validates against pydantic
models, transforms ReviewConcept → AgenticFinding, transforms SemanticOutput →
whatChanged/decisions/postMergeItems/factoryHistory, merges into scaffold JSON,
runs verification checks, and calls the renderer.

Usage:
    python assemble_review_pack.py --pr 35
    python assemble_review_pack.py --pr 35 --reviews-dir docs/reviews/pr35
"""
from __future__ import annotations

import fnmatch
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

# Import sibling modules
_SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(_SCRIPT_DIR))

from models import (  # noqa: E402
    ArchitectureAssessmentOutput,
    Grade,
    LEGACY_GRADE_SORT_ORDER,
    ReviewConcept,
    SemanticOutput,
)


# ---------------------------------------------------------------------------
# Filename parsing
# ---------------------------------------------------------------------------

# Expected: pr{N}-{agent}-{base8}-{head8}.jsonl
_JSONL_PATTERN = re.compile(
    r"^pr\d+-(?P<agent>[a-z][a-z0-9-]*)-[a-f0-9]{8}-[a-f0-9]{8}\.jsonl$"
)


def parse_agent_from_filename(filename: str) -> str | None:
    """Extract agent name from .jsonl filename."""
    m = _JSONL_PATTERN.match(filename)
    return m.group("agent") if m else None


# ---------------------------------------------------------------------------
# Validation & error reporting
# ---------------------------------------------------------------------------


@dataclass
class ValidationReport:
    """Structured report of validation errors."""

    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)

    def add_error(self, file: str, line: int, message: str, data: str = "") -> None:
        self.errors.append({"file": file, "line": line, "message": message, "data": data[:200]})

    def add_warning(self, file: str, message: str) -> None:
        self.warnings.append({"file": file, "message": message})

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def summary(self) -> str:
        parts = []
        if self.errors:
            parts.append(f"{len(self.errors)} validation error(s):")
            for e in self.errors:
                parts.append(f"  {e['file']}:{e['line']} — {e['message']}")
                if e["data"]:
                    parts.append(f"    Data: {e['data']}")
        if self.warnings:
            parts.append(f"\n{len(self.warnings)} warning(s):")
            for w in self.warnings:
                parts.append(f"  {w['file']} — {w['message']}")
        if not parts:
            parts.append("No validation errors.")
        return "\n".join(parts)


def read_and_validate_jsonl(
    reviews_dir: Path,
    report: ValidationReport,
) -> tuple[dict[str, list[ReviewConcept]], list[SemanticOutput], dict | None]:
    """Read all .jsonl files, validate, return parsed objects.

    Returns:
        (agent_concepts, semantic_outputs, architecture_assessment)
    """
    agent_concepts: dict[str, list[ReviewConcept]] = {}
    semantic_outputs: list[SemanticOutput] = []
    architecture_assessment: dict | None = None

    jsonl_files = sorted(reviews_dir.glob("*.jsonl"))
    if not jsonl_files:
        report.add_error(str(reviews_dir), 0, "No .jsonl files found in reviews directory")
        return agent_concepts, semantic_outputs, architecture_assessment

    for jsonl_path in jsonl_files:
        agent_name = parse_agent_from_filename(jsonl_path.name)
        if agent_name is None:
            report.add_warning(
                jsonl_path.name,
                f"Filename doesn't match expected pattern pr{{N}}-{{agent}}-{{base8}}-{{head8}}.jsonl — skipping"
            )
            continue

        is_synthesis = agent_name == "synthesis"
        concepts: list[ReviewConcept] = []

        with open(jsonl_path) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                # Parse JSON
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    report.add_error(jsonl_path.name, line_num, f"Invalid JSON: {e}", line)
                    continue

                # Architecture assessment special case
                if obj.get("_type") == "architecture_assessment":
                    try:
                        validated = ArchitectureAssessmentOutput.model_validate(obj)
                        architecture_assessment = validated.model_dump(by_alias=True)
                    except ValidationError as e:
                        report.add_error(
                            jsonl_path.name, line_num,
                            f"Architecture assessment validation failed: {e.error_count()} error(s) — {e.errors()[0]['msg']}",
                            line,
                        )
                    continue

                # Synthesis agent → SemanticOutput
                if is_synthesis:
                    try:
                        so = SemanticOutput.model_validate(obj)
                        semantic_outputs.append(so)
                    except ValidationError as e:
                        report.add_error(
                            jsonl_path.name, line_num,
                            f"SemanticOutput validation failed: {e.error_count()} error(s) — {e.errors()[0]['msg']}",
                            line,
                        )
                    continue

                # Reviewer agent → ReviewConcept
                try:
                    rc = ReviewConcept.model_validate(obj)
                    concepts.append(rc)
                except ValidationError as e:
                    report.add_error(
                        jsonl_path.name, line_num,
                        f"ReviewConcept validation failed: {e.error_count()} error(s) — {e.errors()[0]['msg']}",
                        line,
                    )

        if concepts:
            agent_concepts[agent_name] = concepts

    return agent_concepts, semantic_outputs, architecture_assessment


# ---------------------------------------------------------------------------
# Verification checks
# ---------------------------------------------------------------------------


def verify_findings(
    agent_concepts: dict[str, list[ReviewConcept]],
    semantic_outputs: list[SemanticOutput],
    diff_data: dict,
    zone_registry: dict,
    report: ValidationReport,
) -> None:
    """Run all verification checks on validated data."""

    diff_files = set(diff_data.get("files", {}).keys())
    valid_zones = set(zone_registry.keys())

    # -- ReviewConcept checks --
    all_concept_ids: dict[str, set[str]] = {}
    all_files_mentioned: set[str] = set()

    for agent_name, concepts in agent_concepts.items():
        concept_ids: set[str] = set()

        for rc in concepts:
            # Concept ID uniqueness per agent
            if rc.concept_id in concept_ids:
                report.add_warning(
                    f"{agent_name}.jsonl",
                    f"Duplicate concept_id '{rc.concept_id}'"
                )
            concept_ids.add(rc.concept_id)

            # Grade validity (already enforced by pydantic, but double-check)
            if rc.grade not in Grade:
                report.add_error(
                    f"{agent_name}.jsonl", 0,
                    f"Invalid grade '{rc.grade}' in concept {rc.concept_id}"
                )

            for loc in rc.locations:
                all_files_mentioned.add(loc.file)

                # File path verification
                if loc.file not in diff_files:
                    report.add_warning(
                        f"{agent_name}.jsonl",
                        f"File '{loc.file}' in concept {rc.concept_id} not found in diff data"
                    )

                # Zone verification
                for zone_id in loc.zones:
                    if zone_id not in valid_zones:
                        # Exception: architecture reviewer may flag "unzoned" files
                        if agent_name != "architecture":
                            report.add_warning(
                                f"{agent_name}.jsonl",
                                f"Zone '{zone_id}' in concept {rc.concept_id} not in zone registry"
                            )

        all_concept_ids[agent_name] = concept_ids

    # Coverage gaps — files in diff no agent mentioned
    uncovered = diff_files - all_files_mentioned
    if uncovered:
        # Filter out common non-reviewable files
        non_reviewable = {".gitignore", "requirements.txt", "requirements.in"}
        meaningful_uncovered = {
            f for f in uncovered
            if not any(f.endswith(ext) for ext in (".lock", ".sum"))
            and Path(f).name not in non_reviewable
        }
        if meaningful_uncovered:
            report.add_warning(
                "coverage",
                f"{len(meaningful_uncovered)} file(s) in diff not mentioned by any agent: "
                f"{', '.join(sorted(meaningful_uncovered)[:5])}"
                + (f" (+{len(meaningful_uncovered)-5} more)" if len(meaningful_uncovered) > 5 else "")
            )

    # -- SemanticOutput checks --
    for so in semantic_outputs:
        if so.output_type == "decision" and so.decision:
            # Decision-zone verification
            for zone_id in so.decision.zones:
                if zone_id not in valid_zones:
                    report.add_warning(
                        "synthesis.jsonl",
                        f"Decision #{so.decision.number} claims zone '{zone_id}' not in registry"
                    )
                else:
                    # Check that ≥1 file in diff touches this zone's paths
                    zone_paths = zone_registry[zone_id].get("paths", [])
                    has_file_in_zone = any(
                        any(fnmatch.fnmatch(f, p) for p in zone_paths)
                        for f in diff_files
                    )
                    if not has_file_in_zone:
                        report.add_warning(
                            "synthesis.jsonl",
                            f"Decision #{so.decision.number} claims zone '{zone_id}' "
                            f"but no diff files match that zone's paths"
                        )

        if so.output_type == "post_merge_item" and so.post_merge_item:
            # Code snippet verification
            snippet = so.post_merge_item.code_snippet
            if snippet and snippet.file not in diff_files:
                report.add_warning(
                    "synthesis.jsonl",
                    f"Post-merge item code snippet references '{snippet.file}' not in diff"
                )

            # Zone verification
            for zone_id in so.post_merge_item.zones:
                if zone_id not in valid_zones:
                    report.add_warning(
                        "synthesis.jsonl",
                        f"Post-merge item zone '{zone_id}' not in registry"
                    )

    # what_changed: exactly 2 entries expected (infrastructure + product)
    wc_entries = [so for so in semantic_outputs if so.output_type == "what_changed"]
    if len(wc_entries) != 2:
        report.add_warning(
            "synthesis.jsonl",
            f"Expected exactly 2 what_changed entries (infrastructure + product), got {len(wc_entries)}"
        )
    else:
        layers = {so.what_changed.layer for so in wc_entries if so.what_changed}
        if layers != {"infrastructure", "product"}:
            report.add_warning(
                "synthesis.jsonl",
                f"what_changed layers should be {{'infrastructure', 'product'}}, got {layers}"
            )


# ---------------------------------------------------------------------------
# Transform: ReviewConcept → AgenticFinding
# ---------------------------------------------------------------------------


def transform_concept_to_finding(
    concept: ReviewConcept,
    agent_name: str,
) -> dict:
    """Transform a ReviewConcept into an AgenticFinding dict.

    Mapping:
        concept.locations[0].file → finding.file (primary; multi-file uses glob notation)
        concept.grade.value       → finding.grade (string: "A", "B+", "B", "C", "F")
        concept.locations[*].zones → finding.zones (space-separated, deduplicated)
        concept.title             → finding.notable
        concept.detail_html       → finding.detail
        LEGACY_GRADE_SORT_ORDER   → finding.gradeSortOrder (0=F/C, 1=B, 2=B+, 3=A)
        agent_name (from filename) → finding.agent
    """
    # Collect zones from all locations (space-separated for legacy format)
    all_zones: list[str] = []
    for loc in concept.locations:
        all_zones.extend(loc.zones)
    unique_zones = list(dict.fromkeys(all_zones))  # preserve order, dedupe

    # Primary file is the first location's file
    primary_file = concept.locations[0].file

    # If multiple files, use glob-like notation
    if len(concept.locations) > 1:
        files = [loc.file for loc in concept.locations]
        # Check if they share a common directory
        common = Path(files[0]).parent
        all_same_dir = all(Path(f).parent == common for f in files)
        if all_same_dir and len(files) > 2:
            primary_file = f"{common}/* ({len(files)} files)"

    return {
        "file": primary_file,
        "grade": concept.grade.value,
        "zones": " ".join(unique_zones),
        "notable": concept.title,
        "detail": concept.detail_html,
        "gradeSortOrder": LEGACY_GRADE_SORT_ORDER.get(concept.grade, 1),
        "agent": agent_name,
    }


def transform_concepts_to_review(
    agent_concepts: dict[str, list[ReviewConcept]],
) -> dict:
    """Transform all agent concepts into AgenticReview dict."""
    findings: list[dict] = []

    for agent_name, concepts in agent_concepts.items():
        for concept in concepts:
            findings.append(transform_concept_to_finding(concept, agent_name))

    # Sort by grade severity (worst first)
    findings.sort(key=lambda f: f.get("gradeSortOrder", 2))

    # Compute overall grade
    if findings:
        worst = min(f["gradeSortOrder"] for f in findings)
        # Reverse lookup: find the worst grade matching the sort order.
        # F and C both map to 0 in LEGACY_GRADE_SORT_ORDER, so we pick the
        # worst letter grade (F > C) when there's a collision.
        worst_grades = [f["grade"] for f in findings if f["gradeSortOrder"] == worst]
        # Grade severity: F is worse than C
        _GRADE_SEVERITY = {"F": 0, "C": 1, "B": 2, "B+": 3, "A": 4}
        overall_grade = min(worst_grades, key=lambda g: _GRADE_SEVERITY.get(g, 2))
    else:
        overall_grade = "A"

    return {
        "overallGrade": overall_grade,
        "reviewMethod": "agent-teams",
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# Transform: SemanticOutput → review pack sections
# ---------------------------------------------------------------------------


def transform_semantic_outputs(
    outputs: list[SemanticOutput],
) -> tuple[dict, list[dict], list[dict], dict | None]:
    """Transform SemanticOutput list into review pack sections.

    Returns: (whatChanged, decisions, postMergeItems, factoryHistory)
    """
    what_changed: dict = {
        "defaultSummary": {"infrastructure": "", "product": ""},
        "zoneDetails": [],
    }
    decisions: list[dict] = []
    post_merge_items: list[dict] = []
    factory_events: list[dict] = []

    for so in outputs:
        if so.output_type == "what_changed" and so.what_changed:
            wc = so.what_changed
            if wc.layer == "infrastructure":
                what_changed["defaultSummary"]["infrastructure"] = wc.summary
            elif wc.layer == "product":
                what_changed["defaultSummary"]["product"] = wc.summary

            for zd in wc.zone_details:
                what_changed["zoneDetails"].append({
                    "zoneId": zd.zone_id,
                    "title": zd.title,
                    "description": zd.description,
                })

        elif so.output_type == "decision" and so.decision:
            d = so.decision
            decisions.append({
                "number": d.number,
                "title": d.title,
                "rationale": d.rationale,
                "body": d.body,
                "zones": " ".join(d.zones),
                "files": [{"path": f.path, "change": f.change} for f in d.files],
                "verified": True,  # Will be updated by verification checks
            })

        elif so.output_type == "post_merge_item" and so.post_merge_item:
            pmi = so.post_merge_item
            item: dict = {
                "priority": pmi.priority,
                "title": pmi.title,
                "description": pmi.description,
                "codeSnippet": None,
                "failureScenario": pmi.failure_scenario,
                "successScenario": pmi.success_scenario,
                "zones": pmi.zones,
            }
            if pmi.code_snippet:
                item["codeSnippet"] = {
                    "file": pmi.code_snippet.file,
                    "lineRange": pmi.code_snippet.line_range,
                    "code": pmi.code_snippet.code,
                }
            post_merge_items.append(item)

        elif so.output_type == "factory_event" and so.factory_event:
            fe = so.factory_event
            factory_events.append({
                "title": fe.title,
                "detail": fe.detail,
                "meta": fe.meta,
                "expandedDetail": fe.expanded_detail,
                "type": fe.event_type,
                "agent": {
                    "label": fe.agent_label,
                    "type": fe.agent_type,
                },
            })

    factory_history: dict | None = None
    if factory_events:
        factory_history = {
            "iterationCount": str(len(factory_events)),
            "satisfactionTrajectory": "",
            "satisfactionDetail": "",
            "timeline": factory_events,
            "gateFindings": [],
        }

    return what_changed, decisions, post_merge_items, factory_history


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def assemble(
    pr_number: int,
    reviews_dir: Path,
    repo: Path,
) -> tuple[dict, ValidationReport]:
    """Main assembly: read, validate, transform, merge, verify.

    Returns (assembled_data, validation_report).
    """
    report = ValidationReport()

    # Load scaffold
    scaffold_path = reviews_dir / f"pr{pr_number}_scaffold.json"
    if not scaffold_path.exists():
        report.add_error(str(reviews_dir), 0, f"Scaffold not found: {scaffold_path}")
        return {}, report

    scaffold_data = json.loads(scaffold_path.read_text())

    # Load diff data (find the file)
    diff_files = list(reviews_dir.glob(f"pr{pr_number}_diff_data_*.json"))
    if not diff_files:
        report.add_error(str(reviews_dir), 0, "No diff data file found")
        return scaffold_data, report
    diff_data = json.loads(diff_files[0].read_text())

    # Load zone registry
    zone_registry_path = repo / ".claude" / "zone-registry.yaml"
    if not zone_registry_path.exists():
        zone_registry_path = repo / "zone-registry.yaml"
    if not zone_registry_path.exists():
        report.add_error(str(repo), 0, "zone-registry.yaml not found")
        return scaffold_data, report

    zone_registry = yaml.safe_load(zone_registry_path.read_text()).get("zones", {})

    # Step 1: Read and validate all .jsonl files
    print("Reading and validating .jsonl files...")
    agent_concepts, semantic_outputs, architecture_assessment = read_and_validate_jsonl(
        reviews_dir, report
    )

    if report.has_errors:
        print(f"\nValidation errors found — assembly may be incomplete.")
        print(report.summary())

    # Step 2: Run verification checks
    print("Running verification checks...")
    verify_findings(agent_concepts, semantic_outputs, diff_data, zone_registry, report)

    # Step 3: Transform ReviewConcept → AgenticReview
    print("Transforming ReviewConcepts → AgenticFindings...")
    agentic_review = transform_concepts_to_review(agent_concepts)

    # Step 4: Transform SemanticOutput → sections
    print("Transforming SemanticOutputs → review pack sections...")
    what_changed, decisions, post_merge_items, factory_history = (
        transform_semantic_outputs(semantic_outputs)
    )

    # Step 5: Handle architecture assessment
    if architecture_assessment:
        # Remove the _type discriminator before merging
        arch_assessment = {k: v for k, v in architecture_assessment.items() if k != "_type"}
        scaffold_data["architectureAssessment"] = arch_assessment

    # Step 6: Merge into scaffold
    scaffold_data["whatChanged"] = what_changed
    scaffold_data["agenticReview"] = agentic_review
    scaffold_data["decisions"] = decisions
    scaffold_data["postMergeItems"] = post_merge_items
    if factory_history is not None:
        scaffold_data["factoryHistory"] = factory_history

    # Step 7: Recompute status with new data
    from scaffold_review_pack_data import compute_status  # noqa: E402

    scaffold_data["status"] = compute_status(
        scaffold_data.get("convergence", {}),
        agentic_review,
        reviewed_sha=scaffold_data.get("reviewedCommitSHA", ""),
        head_sha=scaffold_data.get("headCommitSHA", ""),
        commit_gap=scaffold_data.get("commitGap", 0),
        architecture_assessment=scaffold_data.get("architectureAssessment"),
    )

    return scaffold_data, report


def main() -> None:
    import argparse

    from generate_diff_data import find_repo_root  # noqa: E402

    parser = argparse.ArgumentParser(
        description="Assemble review pack from .jsonl files"
    )
    parser.add_argument("--pr", type=int, required=True, help="PR number")
    parser.add_argument("--reviews-dir", default=None,
                        help="Reviews directory (default: docs/reviews/pr{N})")
    parser.add_argument("--repo", default=None, help="Repository root path")
    parser.add_argument("--output", default=None,
                        help="Output JSON path (default: {reviews_dir}/pr{N}_review_pack_data.json)")
    parser.add_argument("--render", action="store_true",
                        help="Also render the HTML review pack")
    parser.add_argument("--strict", action="store_true",
                        help="Exit with error if validation warnings exist")
    args = parser.parse_args()

    repo = Path(args.repo) if args.repo else find_repo_root()
    reviews_dir = Path(args.reviews_dir) if args.reviews_dir else repo / "docs" / "reviews" / f"pr{args.pr}"
    output_path = Path(args.output) if args.output else reviews_dir / f"pr{args.pr}_review_pack_data.json"

    print(f"Assembling review pack for PR #{args.pr}")
    print(f"  Reviews dir: {reviews_dir}")
    print(f"  Repository:  {repo}")

    assembled_data, report = assemble(args.pr, reviews_dir, repo)

    if not assembled_data:
        print("\nAssembly failed — no data produced.")
        print(report.summary())
        sys.exit(1)

    # Write assembled JSON
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(assembled_data, indent=2) + "\n")
    print(f"\nAssembled: {output_path}")

    # Report
    findings_count = len(assembled_data.get("agenticReview", {}).get("findings", []))
    print(f"  Findings: {findings_count} AgenticFindings")
    print(f"  Decisions: {len(assembled_data.get('decisions', []))}")
    print(f"  Post-merge items: {len(assembled_data.get('postMergeItems', []))}")
    print(f"  Status: {assembled_data.get('status', {}).get('text', 'UNKNOWN')}")

    # Validation report
    if report.has_errors or report.warnings:
        print(f"\n{report.summary()}")

    if args.strict and report.warnings:
        print("\n--strict mode: exiting with error due to warnings")
        sys.exit(1)

    # Render if requested
    if args.render:
        diff_data_path = diff_files[0] if (diff_files := list(reviews_dir.glob(f"pr{args.pr}_diff_data_*.json"))) else None
        if diff_data_path is None:
            print("\nCannot render: no diff data file found")
            sys.exit(1)

        html_output = repo / "docs" / f"pr{args.pr}_review_pack.html"
        print(f"\nRendering HTML review pack to {html_output}...")

        from render_review_pack import render  # noqa: E402

        render(
            data_path=str(output_path),
            output_path=str(html_output),
            diff_data_path=str(diff_data_path),
            template_version="v2",
        )


if __name__ == "__main__":
    main()
