"""Pydantic models for PR Review Pack structured agent outputs.

These models define the schema that review agents write to .jsonl files
and that the assembler validates and transforms into ReviewPackData.

Design decisions (from streamline_review_pack.md):
- Agent identity derived from filename, NOT a field in the schema
- Zones are string[] validated against zone-registry.yaml keys (lowercase-kebab-case)
- Valid grades: A, B+, B, C, F (NO N/A)
- Pydantic validation is the primary enforcement layer (Claude Code's Agent tool
  does not support structured output constraints)
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Grade(StrEnum):
    """Valid review grades. N/A is explicitly excluded."""

    A = "A"
    B_PLUS = "B+"
    B = "B"
    C = "C"
    F = "F"


# Internal sort order (worst=0, best=4) used for sorting findings by severity.
GRADE_SORT_ORDER: dict[Grade, int] = {
    Grade.F: 0,
    Grade.C: 1,
    Grade.B: 2,
    Grade.B_PLUS: 3,
    Grade.A: 4,
}

# Legacy AgenticFinding.gradeSortOrder values (from data-schema.md).
# The old schema used: 0=N/A, 1=B, 2=B+, 3=A.
# We map from Grade to the legacy values for backward compat.
LEGACY_GRADE_SORT_ORDER: dict[Grade, int] = {
    Grade.F: 0,  # was N/A in old schema; F is the new "worst"
    Grade.C: 0,  # C didn't exist in old schema; treat as lowest
    Grade.B: 1,
    Grade.B_PLUS: 2,
    Grade.A: 3,
}


class FindingCategory(StrEnum):
    """Categories for review concept findings."""

    CODE_HEALTH = "code-health"
    SECURITY = "security"
    TEST_INTEGRITY = "test-integrity"
    ADVERSARIAL = "adversarial"
    ARCHITECTURE = "architecture"
    CROSS_CUTTING = "cross-cutting"  # synthesis agent


# ---------------------------------------------------------------------------
# FileReviewOutcome — exhaustive per-file coverage from each reviewer
# ---------------------------------------------------------------------------


class FileReviewOutcome(BaseModel):
    """Per-file review outcome — one per diff file per reviewer.

    Emitted BEFORE ReviewConcept objects in the .jsonl file. Provides
    exhaustive per-file coverage for the File Coverage card. Every file
    in the diff must have a FileReviewOutcome from every reviewer.

    Distinguished from ReviewConcept by the `_type: "file_review"` field.
    """

    type_discriminator: Literal["file_review"] = Field(
        alias="_type",
        default="file_review",
    )
    file: str = Field(
        ...,
        description="File path relative to repo root (must match a file in the diff)",
    )
    grade: Grade = Field(
        ...,
        description="Quality grade for this file from this reviewer's paradigm",
    )
    summary: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="1-2 sentence summary of the file's status from this paradigm",
    )
    reviewed: bool = Field(
        default=True,
        description="Whether the reviewer actually examined this file (false for skip/N/A)",
    )


# ---------------------------------------------------------------------------
# ConceptUpdate — append-only corrections to previously-emitted concepts
# ---------------------------------------------------------------------------


class ConceptUpdate(BaseModel):
    """Append-only update to a previously-emitted ReviewConcept.

    When the orchestrator feeds back validation errors, the reviewer
    appends ConceptUpdate lines to the .jsonl file. The assembler
    resolves updates at read time: provided fields override the
    previous object's fields (matched by concept_id).

    Distinguished from ReviewConcept by the `_type: "concept_update"` field.
    """

    type_discriminator: Literal["concept_update"] = Field(
        alias="_type",
        default="concept_update",
    )
    concept_id: str = Field(
        ...,
        description="concept_id of the ReviewConcept to update",
    )
    # All ReviewConcept fields are optional — only provided fields override
    title: str | None = Field(default=None, max_length=200)
    grade: Grade | None = None
    category: FindingCategory | None = None
    summary: str | None = None
    detail_html: str | None = None
    locations: list[ConceptLocation] | None = None

    @field_validator("concept_id")
    @classmethod
    def validate_concept_id(cls, v: str) -> str:
        if not _KEBAB_RE.match(v):
            raise ValueError(f"concept_id '{v}' must be lowercase-kebab-case")
        return v


# ---------------------------------------------------------------------------
# Zone ID validation
# ---------------------------------------------------------------------------

_KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def _validate_zone_id(zone_id: str) -> str:
    """Validate a zone ID is lowercase-kebab-case.

    Actual existence in zone-registry.yaml is checked by the assembler
    (it has access to the registry; the model does not).
    """
    if not _KEBAB_RE.match(zone_id):
        raise ValueError(
            f"Zone ID '{zone_id}' must be lowercase-kebab-case (e.g. 'rl-core', 'review-pack')"
        )
    return zone_id


# ---------------------------------------------------------------------------
# ReviewConcept — what each review agent produces
# ---------------------------------------------------------------------------


class ConceptLocation(BaseModel):
    """A specific code location referenced by a review concept."""

    file: str = Field(
        ...,
        description="File path relative to repo root",
    )
    lines: str | None = Field(
        default=None,
        description="Line range, e.g. '42-58' or '12'. None for file-level findings.",
    )
    zones: list[str] = Field(
        default_factory=list,
        description="Zone IDs from zone-registry.yaml that this file belongs to",
    )
    comment: str | None = Field(
        default=None,
        description="Location-specific comment or code snippet context",
    )

    @field_validator("zones", mode="before")
    @classmethod
    def validate_zones(cls, v: list[str]) -> list[str]:
        for zone_id in v:
            _validate_zone_id(zone_id)
        return v


class ReviewConcept(BaseModel):
    """A single concept-level finding from a review agent.

    Each agent writes one ReviewConcept per line to a .jsonl file.
    The assembler transforms these into AgenticFinding objects for the
    review pack.

    Identity: The agent name is derived from the .jsonl filename
    (e.g., pr5-code-health-abc12345-def67890.jsonl → "code-health"),
    NOT stored in this model.
    """

    concept_id: str = Field(
        ...,
        description=(
            "Unique identifier within this agent's output. "
            "Convention: {category}-{seq}, e.g. 'security-1', 'code-health-3'"
        ),
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="One-line summary of the finding",
    )
    grade: Grade = Field(
        ...,
        description="Quality grade: A (clean), B+ (minor), B (warnings), C (issues), F (critical)",
    )
    category: FindingCategory = Field(
        ...,
        description="Finding category — should match the agent's paradigm",
    )
    summary: str = Field(
        ...,
        min_length=1,
        description="Brief explanation of the finding (plain text)",
    )
    detail_html: str = Field(
        ...,
        min_length=1,
        description="Full explanation with evidence (HTML-safe content)",
    )
    locations: list[ConceptLocation] = Field(
        ...,
        min_length=1,
        description=(
            "Code locations relevant to this finding. "
            "At least one location required. Single-location concepts are valid."
        ),
    )

    @field_validator("concept_id")
    @classmethod
    def validate_concept_id(cls, v: str) -> str:
        if not _KEBAB_RE.match(v):
            raise ValueError(
                f"concept_id '{v}' must be lowercase-kebab-case "
                f"(e.g. 'security-1', 'code-health-3')"
            )
        return v


# ---------------------------------------------------------------------------
# SemanticOutput — what the synthesis agent produces
# ---------------------------------------------------------------------------

# NOTE: Classes are ordered so that referenced types come before referencing
# types to avoid forward-reference issues with Pydantic v2 schema generation.


class ZoneDetail(BaseModel):
    """Per-zone change description for what-changed summaries."""

    zone_id: str
    title: str
    description: str = Field(
        ...,
        description="HTML-safe description of changes in this zone",
    )

    @field_validator("zone_id")
    @classmethod
    def validate_zone(cls, v: str) -> str:
        return _validate_zone_id(v)


class WhatChangedEntry(BaseModel):
    """Summary of what changed, split by layer."""

    layer: Literal["infrastructure", "product"]
    summary: str = Field(
        ...,
        min_length=1,
        description="HTML-safe summary of changes in this layer",
    )
    zone_details: list[ZoneDetail] = Field(
        default_factory=list,
        description="Per-zone breakdown of changes",
    )


class DecisionFile(BaseModel):
    """A file affected by a decision."""

    path: str
    change: str = Field(
        ...,
        description="One-line description of what changed",
    )


class DecisionEntry(BaseModel):
    """A key decision made or evident in this PR."""

    number: int = Field(..., ge=1)
    title: str = Field(..., min_length=1, max_length=200)
    rationale: str = Field(
        ...,
        min_length=1,
        description="One-line summary of why this decision was made",
    )
    body: str = Field(
        ...,
        min_length=1,
        description="Full explanation (HTML-safe)",
    )
    zones: list[str] = Field(
        ...,
        min_length=1,
        description="Zone IDs this decision affects",
    )
    files: list[DecisionFile] = Field(
        default_factory=list,
        description="Files affected by this decision",
    )

    @field_validator("zones", mode="before")
    @classmethod
    def validate_zones(cls, v: list[str]) -> list[str]:
        for zone_id in v:
            _validate_zone_id(zone_id)
        return v


class PostMergeEntry(BaseModel):
    """An item to watch or address after merging."""

    priority: Literal["medium", "low", "cosmetic"]
    title: str = Field(
        ...,
        min_length=1,
        description="One-line title (HTML-safe, may contain <code> tags)",
    )
    description: str = Field(
        ...,
        min_length=1,
        description="Context paragraph (HTML-safe)",
    )
    code_snippet: CodeSnippetRef | None = None
    failure_scenario: str = Field(
        ...,
        min_length=1,
        description="What could go wrong if left unaddressed",
    )
    success_scenario: str = Field(
        ...,
        min_length=1,
        description="What 'fixed' looks like",
    )
    zones: list[str] = Field(
        default_factory=list,
        description="Affected zone IDs",
    )

    @field_validator("zones", mode="before")
    @classmethod
    def validate_zones(cls, v: list[str]) -> list[str]:
        for zone_id in v:
            _validate_zone_id(zone_id)
        return v


class CodeSnippetRef(BaseModel):
    """Reference to a code snippet in a specific file."""

    file: str
    line_range: str = Field(
        ...,
        description="e.g. 'lines 72-78'",
    )
    code: str = Field(
        ...,
        description="Raw code content (rendered in <pre>)",
    )


class FactoryEventEntry(BaseModel):
    """A factory convergence event for factory history."""

    title: str
    detail: str
    meta: str = Field(
        ...,
        description="e.g. 'Commit: 67e5600 . Feb 22'",
    )
    expanded_detail: str = Field(
        ...,
        description="HTML-safe drill-down content",
    )
    event_type: Literal["automated", "intervention"]
    agent_label: str = Field(
        ...,
        description="e.g. 'CI (automated)' or 'Human (Joey)'",
    )
    agent_type: Literal["automated", "human"]


class SemanticOutput(BaseModel):
    """Typed union of synthesis agent outputs.

    Each line in the synthesis agent's .jsonl file is one SemanticOutput.
    The `output_type` discriminator determines which fields are populated.
    """

    output_type: Literal["what_changed", "decision", "post_merge_item", "factory_event"]

    # what_changed
    what_changed: WhatChangedEntry | None = None

    # decision
    decision: DecisionEntry | None = None

    # post_merge_item
    post_merge_item: PostMergeEntry | None = None

    # factory_event
    factory_event: FactoryEventEntry | None = None

    @model_validator(mode="after")
    def validate_populated_field(self) -> SemanticOutput:
        """Ensure exactly the field matching output_type is populated."""
        field_map = {
            "what_changed": self.what_changed,
            "decision": self.decision,
            "post_merge_item": self.post_merge_item,
            "factory_event": self.factory_event,
        }
        active = field_map[self.output_type]
        if active is None:
            raise ValueError(
                f"output_type is '{self.output_type}' but the corresponding field is None"
            )
        # Ensure other fields are None
        for key, val in field_map.items():
            if key != self.output_type and val is not None:
                raise ValueError(
                    f"output_type is '{self.output_type}' but '{key}' is also "
                    f"populated — only one field should be set"
                )
        return self


# ---------------------------------------------------------------------------
# ArchitectureAssessmentOutput — special output from architecture reviewer
# ---------------------------------------------------------------------------


class UnzonedFileEntry(BaseModel):
    """A file that matches no zone pattern."""

    path: str
    suggested_zone: str | None = Field(
        default=None,
        alias="suggestedZone",
    )
    reason: str


class ZoneChangeEntry(BaseModel):
    """A structural zone change detected in the PR."""

    type: Literal[
        "new_zone_recommended",
        "zone_split",
        "zone_merge",
        "zone_renamed",
        "zone_removed",
    ]
    zone: str
    reason: str
    suggested_paths: list[str] | None = Field(
        default=None,
        alias="suggestedPaths",
    )


class RegistryWarning(BaseModel):
    zone: str
    warning: str
    severity: Literal["CRITICAL", "WARNING", "NIT"]


class CouplingWarning(BaseModel):
    from_zone: str = Field(alias="fromZone")
    to_zone: str = Field(alias="toZone")
    files: list[str]
    evidence: str


class DocRecommendation(BaseModel):
    type: Literal["update_needed", "new_doc_suggested", "stale_reference"]
    path: str
    reason: str


class DecisionVerification(BaseModel):
    decision_number: int = Field(alias="decisionNumber")
    claimed_zones: list[str] = Field(alias="claimedZones")
    verified: bool
    reason: str


class ArchitectureAssessmentOutput(BaseModel):
    """Architecture assessment output from the architecture reviewer.

    Written as the last line in the architecture reviewer's .jsonl file,
    distinguished by `_type: "architecture_assessment"`.
    Maps to the ArchitectureAssessment interface in data-schema.md.
    """

    model_config = {"populate_by_name": True}

    type_discriminator: Literal["architecture_assessment"] = Field(
        alias="_type",
        default="architecture_assessment",
    )

    # Diagram data (nullable — may not be produced for small PRs)
    baseline_diagram: dict | None = Field(default=None, alias="baselineDiagram")
    update_diagram: dict | None = Field(default=None, alias="updateDiagram")
    diagram_narrative: str = Field(default="", alias="diagramNarrative")

    # Assessment details
    unzoned_files: list[UnzonedFileEntry] = Field(
        default_factory=list,
        alias="unzonedFiles",
    )
    zone_changes: list[ZoneChangeEntry] = Field(
        default_factory=list,
        alias="zoneChanges",
    )
    registry_warnings: list[RegistryWarning] = Field(
        default_factory=list,
        alias="registryWarnings",
    )
    coupling_warnings: list[CouplingWarning] = Field(
        default_factory=list,
        alias="couplingWarnings",
    )
    doc_recommendations: list[DocRecommendation] = Field(
        default_factory=list,
        alias="docRecommendations",
    )
    decision_zone_verification: list[DecisionVerification] = Field(
        default_factory=list,
        alias="decisionZoneVerification",
    )

    core_issues_need_attention: bool = Field(
        default=False,
        alias="coreIssuesNeedAttention",
        description="Explicit flag controlling the 'Needs Attention' pill in Core Issues",
    )

    overall_health: Literal["healthy", "needs-attention", "action-required"] = Field(
        alias="overallHealth",
    )
    summary: str


# ---------------------------------------------------------------------------
# Schema export utilities
# ---------------------------------------------------------------------------


def export_json_schemas(output_dir: str) -> None:
    """Generate .schema.json files for all agent output models."""
    import json
    from pathlib import Path

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for model_cls in (
        ReviewConcept,
        SemanticOutput,
        FileReviewOutcome,
        ConceptUpdate,
        ArchitectureAssessmentOutput,
    ):
        schema = model_cls.model_json_schema()
        path = out / f"{model_cls.__name__}.schema.json"
        path.write_text(json.dumps(schema, indent=2) + "\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        export_json_schemas(sys.argv[1])
    else:
        # Default: print schemas to stdout
        import json

        for model_cls in (
            ReviewConcept,
            SemanticOutput,
            FileReviewOutcome,
            ConceptUpdate,
            ArchitectureAssessmentOutput,
        ):
            print(f"--- {model_cls.__name__} ---")
            print(json.dumps(model_cls.model_json_schema(), indent=2))
