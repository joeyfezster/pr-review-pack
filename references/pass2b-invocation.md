# Pass 2b Invocation Specification

Exact invocation pattern for Pass 2b (Semantic Enrichment). This document tells the orchestrator how to spawn agents, what to give them, what to expect back, and how to merge results.

## Context: Review Pack vs Factory

The review pack runs **outside the factory loop**. There is no `TeamCreate` available. All agent spawning uses the **Agent tool** (also called `Task` in some contexts). Each agent is a separate invocation with its own prompt and context.

The factory's Tier 2 pattern (SKILL.md Step 4) is the blueprint — but adapted for Agent tool invocation instead of TeamCreate.

## Two Sub-Stages of Pass 2b

Pass 2b has two independent workstreams. They can run in parallel.

### Workstream A: Agentic Review (5 agents)

Five specialized review agents, each reviewing the diff through its own paradigm. These produce the `agenticReview` section and (for the architecture agent) the `architectureAssessment` section of the review pack.

### Workstream B: Semantic Analysis (1 agent)

One agent that reads the diff and produces `whatChanged`, `decisions`, `postMergeItems`, and `factoryHistory`. This is NOT the orchestrator — it is a delegated agent with its own context window, ensuring the review pack is built from diff analysis, not main-thread memory.

---

## Workstream A: Agentic Review — 5-Agent Invocation

### Agent Definitions

| Agent ID | Abbreviation | Paradigm Prompt | Focus |
|----------|-------------|----------------|-------|
| `code-health-reviewer` | CH | `packages/review-prompts/code_health_review.md` | Code quality, complexity, dead code |
| `security-reviewer` | SE | `packages/review-prompts/security_review.md` | Security vulnerabilities |
| `test-integrity-reviewer` | TI | `packages/review-prompts/test_integrity_review.md` | Test quality and integrity |
| `adversarial-reviewer` | AD | `packages/review-prompts/adversarial_review.md` | Gaming, spec violations, architectural dishonesty |
| `architecture-reviewer` | AR | `packages/review-prompts/architecture_review.md` | Zone coverage, coupling, structural changes, architecture documentation |

### Launch Pattern

Spawn all 5 agents in parallel using the Agent tool. Each agent receives the same base context plus its paradigm-specific prompt.

```
For each agent:
  Agent tool invocation with prompt:

  "You are the {agent_name} for a PR review pack (PR #{N}).

  YOUR PARADIGM PROMPT:
  {contents of the paradigm .md file}

  CODE QUALITY STANDARDS:
  {contents of packages/dark-factory/docs/code_quality_standards.md}

  DIFF DATA:
  {contents of docs/pr{N}_diff_data.json — the full per-file diff output from Pass 1}

  ZONE REGISTRY:
  {contents of .claude/zone-registry.yaml}

  TIER 1 GATE 0 RESULTS (if available):
  {contents of artifacts/factory/gate0_results.json, or "No Tier 1 results available" if not a factory PR}

  YOUR TASK:
  Review every changed file in the diff through your paradigm. For each file (or logical group of files), produce a structured finding.

  OUTPUT FORMAT — you MUST use this exact JSON format, nothing else:
  {
    "agent": "{abbreviation}",
    "findings": [
      {
        "file": "path/to/file.py",
        "grade": "A",
        "zones": "zone-id-1 zone-id-2",
        "notable": "One-line summary of finding",
        "detail": "Full HTML-safe explanation. Use <code>, <strong>, <br> as needed.",
        "severity": "WARNING"
      }
    ]
  }

  GRADE RUBRIC:
  - A: Clean. No issues or only NITs.
  - B+: Minor warnings, nothing structural.
  - B: Warnings that should be addressed.
  - C: Issues that need fixing before merge.
  - F: Critical problems. Blocks merge.
  - N/A: File is not reviewable through this paradigm (e.g., config file for security reviewer).

  RULES:
  1. Every file in the diff must appear in at least one finding (use N/A grade if not applicable to your paradigm).
  2. You may group related files into one finding (e.g., 'tests/test_*.py') but only if they share the same grade and finding.
  3. The 'zones' field must be space-separated zone IDs from the zone registry. Match the file path against zone path patterns.
  4. The 'detail' field is HTML-safe. Use <code> for code references, <strong> for emphasis, <br> for line breaks. Do NOT use markdown.
  5. Do NOT wrap your output in markdown code fences. Output raw JSON only.
  6. The 'severity' field uses the same scale as the paradigm prompt: CRITICAL, WARNING, or NIT.
  "
```

**The adversarial reviewer additionally receives:** The contents of `specs/*.md` files (the component specifications). The other 3 code-level agents do NOT receive specs — they review code quality, not spec compliance.

**The architecture reviewer additionally receives:**
- Full repository file tree (`find . -type f` excluding `.git`, `node_modules`, `__pycache__`) — needed for holistic architecture assessment beyond the diff
- The `architecture` section from the scaffold JSON — current zone layout (positions, categories, file counts, modification flags)
- Whatever architecture docs exist in the repo — `docs/architecture.md`, `docs/architecture/*.md`, ADRs, README architecture sections, or zone registry `architectureDocs` pointers. The format varies by project — the architect reads whatever is available.

**The architecture reviewer produces two outputs:**
1. **Findings** — standard `AgenticFinding[]` format (merged into `agenticReview.findings[]`, rendered with AR badge)
2. **Architecture Assessment** — a separate `ARCHITECTURE_ASSESSMENT:` JSON block extracted to `data.architectureAssessment` (new top-level field). See `pass2b-output-schema.md` for the shape.

### Reuse of Existing Gate 0 Tier 2 Files

**Before spawning any agent**, check if `artifacts/factory/gate0_tier2_{paradigm}.md` files already exist:

| File | Maps to Agent |
|------|--------------|
| `artifacts/factory/gate0_tier2_code_health.md` | code-health-reviewer |
| `artifacts/factory/gate0_tier2_security.md` | security-reviewer |
| `artifacts/factory/gate0_tier2_test_integrity.md` | test-integrity-reviewer |
| `artifacts/factory/gate0_tier2_adversarial.md` | adversarial-reviewer |
| `artifacts/factory/gate0_tier2_architecture.md` | architecture-reviewer |

**If a file exists AND was produced for the same HEAD SHA as this review pack:**
- Parse the findings from the markdown file (they use the `FINDING: / SEVERITY: / FILE: / LINE: / EVIDENCE: / IMPACT: / FIX:` format)
- Convert each finding to the `AgenticFinding` JSON format
- Skip spawning that agent — use the converted findings instead
- Set `reviewMethod` to `"agent-teams"` (the findings still came from an agent team, just from a prior run)

**If a file exists but is from a different SHA, or does not exist:** Spawn the agent as described above.

**Rationale:** The factory already ran these agents. Re-running them wastes time and tokens. The review pack should consume existing analysis when it is current.

### Converting Tier 2 Markdown to AgenticFinding JSON

The gate0_tier2 files use a text format. Map fields as follows:

| Tier 2 Markdown Field | AgenticFinding JSON Field |
|----------------------|--------------------------|
| `FINDING:` | `notable` |
| `SEVERITY:` | Used to derive `grade` (see below) |
| `FILE:` | `file` |
| `EVIDENCE:` + `IMPACT:` + `FIX:` | Concatenated into `detail` (HTML-escaped, wrapped in `<strong>Evidence:</strong>`, etc.) |
| (inferred from file path + zone registry) | `zones` |
| (agent name) | `agent` |

**Severity-to-grade mapping for converted findings:**
- CRITICAL → F
- WARNING → B
- NIT → A

### Merging 5 Agent Outputs into `agenticReview` and `architectureAssessment`

After all 5 agents complete (or their existing files are converted), merge:

1. **Collect all findings** from all 5 agents into a single `findings[]` array.

2. **Group by file.** Multiple agents may have findings for the same file. Keep all findings — the review pack renders per-file rows with per-agent grade badges (CH:A SE:B TI:A AD:B+).

3. **Compute per-file aggregate grade.** For each unique file path, the worst grade across all agents becomes the file's aggregate grade. Grade severity order: F > C > B > B+ > A > N/A.

4. **Assign `gradeSortOrder`.** This determines the severity sort in the rendered table:
   - F → 5
   - C → 4
   - B → 3
   - B+ → 2
   - A → 1
   - N/A → 0

5. **Compute `overallGrade`.** Aggregate across all findings:
   - Any F → overall F
   - Any C (no F) → overall C
   - Majority B or worse → overall B
   - Majority B+ or better → overall B+
   - All A/N/A → overall A

6. **Set `reviewMethod`** to `"agent-teams"`.

### Output Shape

See `pass2b-output-schema.md` for the exact JSON shape of the `agenticReview` object.

---

## Workstream B: Semantic Analysis — 1 Agent

One agent that produces the narrative and analytical sections of the review pack. It reads the diff and produces structured JSON for 4 fields.

### Launch Pattern

```
Agent tool invocation with prompt:

"You are the semantic analysis agent for a PR review pack (PR #{N}).

DIFF DATA:
{contents of docs/pr{N}_diff_data.json}

ZONE REGISTRY:
{contents of .claude/zone-registry.yaml}

SCAFFOLD JSON (deterministic fields already populated):
{contents of /tmp/pr{N}_review_pack_data.json}

SPECS:
{contents of each file listed in zone registry 'specs' fields}

COMMIT LOG:
{output of: git log main..HEAD --oneline --no-decorate}

FACTORY ARTIFACTS (if they exist):
- artifacts/factory/feedback_iter_*.md
- artifacts/factory/gate0_results.json
- scenario_results.json

YOUR TASK:
Fill the following semantic fields in the review pack data. Output them as a single JSON object.

OUTPUT FORMAT — you MUST use this exact JSON structure:
{
  \"whatChanged\": { ... },
  \"decisions\": [ ... ],
  \"postMergeItems\": [ ... ],
  \"factoryHistory\": null | { ... }
}

See the FIELD SPECIFICATIONS below for the exact shape of each field.

FIELD SPECIFICATIONS:

1. whatChanged:
{
  \"defaultSummary\": {
    \"infrastructure\": \"<p>HTML paragraph summarizing factory/CI/tooling changes.</p>\",
    \"product\": \"<p>HTML paragraph summarizing application code changes.</p>\"
  },
  \"zoneDetails\": [
    {
      \"zoneId\": \"zone-id-from-registry\",
      \"title\": \"Zone Display Name\",
      \"description\": \"<p>HTML description of what changed in this zone.</p>\"
    }
  ]
}
- defaultSummary.infrastructure and .product are HTML strings, NOT arrays.
- zoneDetails[].description is an HTML string, NOT a bullets array.
- Every zone that has files in the diff MUST have a zoneDetail entry.

2. decisions:
[
  {
    \"number\": 1,
    \"title\": \"Short decision title\",
    \"rationale\": \"One-line rationale\",
    \"body\": \"<p>Full HTML explanation of the decision.</p>\",
    \"zones\": \"zone-id-1 zone-id-2\",
    \"files\": [
      { \"path\": \"src/file.py\", \"change\": \"One-line description of what changed\" }
    ],
    \"verified\": true
  }
]
- zones is a SPACE-SEPARATED STRING, not an array.
- files is an array of {path, change} objects.
- body is an HTML string with the full explanation.
- verified: set to true if at least one file in the 'files' list touches a path in the claimed zone(s). Set to false if the zone claim cannot be verified against the diff.
- number: sequential starting from 1.

3. postMergeItems:
[
  {
    \"priority\": \"medium\",
    \"title\": \"Item title (HTML-safe, may use <code>)\",
    \"description\": \"<p>Context paragraph.</p>\",
    \"codeSnippet\": {
      \"file\": \"src/file.py\",
      \"lineRange\": \"lines 42-48\",
      \"code\": \"def example():\\n    pass\"
    },
    \"failureScenario\": \"What goes wrong if not addressed.\",
    \"successScenario\": \"What 'fixed' looks like.\",
    \"zones\": [\"zone-id-1\"]
  }
]
- priority is LOWERCASE: \"medium\", \"low\", or \"cosmetic\".
- codeSnippet is SINGULAR (not codeSnippets). Set to null if no code reference.
- codeSnippet.code is raw code (not HTML-escaped — the renderer handles escaping).
- zones is an ARRAY of strings (unlike decisions where it is a space-separated string).

4. factoryHistory:
- Set to null if this is NOT a factory PR (no factory artifacts exist).
- If this IS a factory PR, produce the full object. See pass2b-output-schema.md for the shape.

RULES:
1. Every claim must be verifiable against the diff data. Do not invent changes that are not in the diff.
2. Decision zone claims must reference zones where at least one file in the diff touches that zone's paths.
3. Code snippet line references must exist in the actual diff.
4. File paths must appear in the diff file list.
5. Use HTML for rich text fields (detail, body, description). Use <p>, <ul>, <li>, <code>, <strong>, <br>. Do NOT use markdown.
6. Do NOT wrap your output in markdown code fences. Output raw JSON only.
"
```

### Factory History Detection

**How to determine if this is a factory PR:**
- Check if `artifacts/factory/` directory exists and contains `gate0_results.json` or `feedback_iter_*.md` files
- Check if the branch name matches factory patterns (`factory/**`, `df-crank-**`)
- If neither condition is met, set `factoryHistory` to `null`

---

## Merging Workstream A + B into Final JSON

After both workstreams complete, the orchestrator (not an agent) merges results into the scaffold JSON:

```python
# Pseudocode for the merge step

scaffold = json.load(open("/tmp/pr{N}_review_pack_data.json"))

# From Workstream A (agentic review — 5 agents)
scaffold["agenticReview"] = {
    "overallGrade": computed_overall_grade,
    "reviewMethod": "agent-teams",
    "findings": merged_findings_list  # findings from all 5 agents
}

# From Workstream A — architecture reviewer's assessment (extracted separately)
# The architecture reviewer produces an ARCHITECTURE_ASSESSMENT: JSON block
# in addition to its standard findings. Extract it to a top-level field.
scaffold["architectureAssessment"] = architecture_assessment_json  # or None if not available

# From Workstream B (semantic analysis)
semantic_output = json.loads(workstream_b_agent_output)
scaffold["whatChanged"] = semantic_output["whatChanged"]
scaffold["decisions"] = semantic_output["decisions"]
scaffold["postMergeItems"] = semantic_output["postMergeItems"]
scaffold["factoryHistory"] = semantic_output["factoryHistory"]

# Write merged result
json.dump(scaffold, open("/tmp/pr{N}_review_pack_data.json", "w"), indent=2)
```

**The orchestrator does NOT fill any semantic fields itself.** It only:
1. Spawns agents
2. Collects outputs
3. Validates JSON structure
4. Merges into scaffold
5. Runs verification checks

---

## Verification (Post-Merge, Pre-Render)

After merging, the orchestrator runs these checks before proceeding to Pass 3:

### Structural Checks
1. Every required field exists and is the correct type (see `pass2b-output-schema.md`)
2. `agenticReview.findings` is a non-empty array
3. `whatChanged.defaultSummary` has both `infrastructure` and `product` as strings
4. `whatChanged.zoneDetails` has an entry for every zone that has files in the diff
5. `decisions[].zones` is a space-separated string (not an array)
6. `decisions[].files` is an array of `{path, change}` objects
7. `decisions[].body` exists (not just `rationale`)
8. `postMergeItems[].codeSnippet` is singular (not `codeSnippets`)
9. `postMergeItems[].priority` is lowercase
10. `postMergeItems[].zones` is an array

### Semantic Checks
1. Every file path in `agenticReview.findings` exists in the diff data
2. Every zone reference exists in the zone registry
3. Decision zone claims are verified: for each decision, at least one file in its `files[]` touches a path matching the claimed zone's patterns
4. Code snippet file paths exist in the diff data

### Error Recovery
If a check fails:
- Log the specific failure
- Attempt to fix programmatically (e.g., convert `zones` array to space-separated string, lowercase priority values, rename `codeSnippets` to `codeSnippet`)
- If the fix is non-trivial (missing data, wrong structure), re-run the failing agent with a more specific prompt that includes the error message
- Never silently skip validation — failed checks that cannot be fixed must be reported to the user

---

## Error Handling: Agent Failures

### Agent produces malformed JSON
1. Attempt to extract JSON from the response (strip markdown fences, find first `{` to last `}`)
2. If parsing succeeds after cleanup, use the result
3. If parsing fails, re-spawn the agent with the error message appended: "Your previous output was not valid JSON. The parse error was: {error}. Output raw JSON only, no markdown fences."
4. Maximum 2 retries per agent

### Agent produces wrong schema
1. Validate against expected shape
2. Apply automatic fixes for common mistakes:
   - `zones` as array → join with spaces
   - `codeSnippets` → rename to `codeSnippet`, take first element
   - `priority` uppercase → lowercase
   - `bullets` array in whatChanged → join into HTML string
   - Missing `body` in decisions → copy from `rationale`
3. If structural issues remain after auto-fix, re-spawn with specific correction instructions

### Agent is unresponsive or times out
1. Wait up to 5 minutes per agent
2. If timeout, check for partial output
3. Re-spawn the specific agent — do not re-run the entire team
4. If second attempt also fails, produce a degraded review pack:
   - For agentic review: mark the missing agent's files as grade "N/A" with detail "Review agent timed out"
   - For semantic analysis: use minimal defaults (empty whatChanged summaries, no decisions, no postMergeItems)

### All agents fail
- This is a hard failure. Do not produce a review pack.
- Report to the user: "Pass 2b failed — all review agents were unresponsive. Check model availability and retry."
