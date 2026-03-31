# PR Review Pack

Self-contained interactive HTML review pack generator for pull requests. The reviewer reads the pack, not the code.

The output is a Mission Control layout: a two-panel HTML file with sidebar navigation, zone mini-map, collapsible sections, and keyboard shortcuts. Open it in a browser, read the top-level summary, and drill into any section that needs deeper inspection.

## Install

```bash
git clone https://github.com/joeyfezster/pr-review-pack.git ~/.claude/skills/pr-review-pack
pip install pyyaml
```

That's it. The skill is now available as `/pr-review-pack` in any Claude Code session.

## Prerequisites

- **Python 3.12+** with `pyyaml` (installed above)
- **Node.js** (for Playwright E2E tests: `npm install`)
- **`gh` CLI** authenticated (`gh auth login`)
- **Zone registry** in the target project (`zone-registry.yaml` at root, or `.claude/zone-registry.yaml` as fallback)

## Zone Registry Setup

The zone registry declares which files belong to which architectural zones. Without it, the pipeline cannot map diffs to architecture or verify decision claims.

Place it at `.claude/zone-registry.yaml` in the target repo. Start from the example:

```bash
cp examples/zone-registry.example.yaml .claude/zone-registry.yaml
```

### Format

```yaml
zones:
  core-logic:
    paths: ["src/core/**", "tests/test_core_*.py"]
    specs: ["docs/core_spec.md"]
    category: product
    label: "Core Logic"
    sublabel: "primary business logic"

  api-layer:
    paths: ["src/api/**", "tests/test_api_*.py"]
    specs: ["docs/api_spec.md"]
    category: product
    label: "API Layer"
    sublabel: "HTTP endpoints"

  ci-cd:
    paths: [".github/workflows/**"]
    specs: []
    category: infra
    label: "CI/CD"
    sublabel: "build and deploy"
```

| Field | Required | Description |
|-------|----------|-------------|
| `paths` | Yes | Glob patterns matching files in this zone |
| `specs` | No | Spec files that govern this zone |
| `category` | Yes | `product`, `factory`, or `infra` -- controls grouping in the architecture diagram |
| `label` | Yes | Display name shown in the diagram and sidebar |
| `sublabel` | No | Short description shown beneath the label |
| `architectureDocs` | No | Paths to architecture documentation the AR agent should read for this zone |

## Quick Start

For PR number N:

```bash
# Phase 1: Setup (deterministic — diff + scaffold)
python3 scripts/review_pack_setup.py --pr N

# Phase 2: Review (spawn 5 review agents + 1 synthesis agent)
# See SKILL.md Phase 2 for agent spawn patterns

# Phase 3: Assemble (validate .jsonl, transform, merge, render)
python3 scripts/assemble_review_pack.py --pr N --render

# Phase 4: Deliver (Playwright validation + commit)
npx playwright test e2e/
```

Replace `N` with the actual PR number throughout.

## 6-Agent Review Team

Phase 2 spawns six review agents writing `.jsonl` files. Five run in parallel (anti-anchoring is structural — no agent sees another's conclusions). The sixth (synthesis) runs after all five complete.

| Abbreviation | Agent | Focus | Schema |
|--------------|-------|-------|--------|
| **CH** | Code Health | Code quality, complexity, dead code | ReviewConcept |
| **SE** | Security | Vulnerabilities, injection vectors, auth/authz | ReviewConcept |
| **TI** | Test Integrity | Test quality, vacuous assertions, mocking | ReviewConcept |
| **AD** | Adversarial | Gaming, spec violations, architectural dishonesty | ReviewConcept |
| **AR** | Architecture | Zone coverage, coupling, structural changes | ReviewConcept + ArchitectureAssessment |
| **SY** | Synthesis | Cross-cutting analysis, decisions, post-merge items | SemanticOutput |

Pydantic models for all schemas: `scripts/models.py`

## CLI Tool

Post-generation management:

```bash
# Check review pack status without modifying
python3 scripts/review_pack_cli.py status docs/prN_review_pack.html

# Refresh deterministic data (CI checks, comments, commit scope)
python3 scripts/review_pack_cli.py refresh docs/prN_review_pack.html

# Atomic merge: refresh -> validate -> snapshot -> commit -> push -> merge
python3 scripts/review_pack_cli.py merge N
```

Requires `GITHUB_TOKEN` env var or `gh auth token`.

## Template Selection

Pass `--template v2` to `render_review_pack.py` to use the Mission Control layout. v2 is the default for new packs.

The v2 template features:
- Sidebar navigation with zone mini-map
- Collapsible/expandable sections
- Per-file code diff viewer with syntax highlighting
- Agent grade badges per file (CH:A SE:B TI:A AD:B AR:A)
- Keyboard navigation

## Playwright Validation

E2E tests validate the rendered HTML structurally and visually.

```bash
npx playwright test e2e/
```

- `review-pack-v2.spec.ts` -- baseline suite covering all Mission Control sections, sidebar behavior, and interactive elements
- `pr-validation.template.ts` -- per-PR expansion template for PR-specific assertions

When all E2E tests pass, the validation banner is removed from the rendered pack.

## Project Structure

```
pr-review-pack/
├── assets/
│   └── template_v2.html          # Mission Control HTML template
├── scripts/
│   ├── review_pack_setup.py      # Phase 1: consolidated setup
│   ├── assemble_review_pack.py   # Phase 3: validate + transform + merge
│   ├── models.py                 # Pydantic models (ReviewConcept, SemanticOutput, etc.)
│   ├── generate_diff_data.py     # Deterministic diff extraction
│   ├── scaffold_review_pack_data.py  # Deterministic field scaffolding
│   ├── render_review_pack.py     # Deterministic HTML rendering
│   └── review_pack_cli.py        # CLI tool (status/refresh/merge)
├── e2e/                          # Playwright E2E tests
├── tests/                        # Python unit tests
├── references/
│   ├── schemas/                  # JSON schemas from pydantic models
│   ├── examples/                 # Example .jsonl files
│   └── *.md                      # Specification documents
├── docs/                         # Generated review pack artifacts
├── SKILL.md                      # Claude Code skill entry point
├── requirements.txt              # Python dependencies
├── package.json                  # Node dependencies (Playwright)
└── playwright.config.ts          # Playwright configuration
```

## Reference Documents

| Document | Description |
|----------|-------------|
| `references/build-spec.md` | Full build specification for the review pack |
| `references/data-schema.md` | JSON data schema consumed by the renderer |
| `references/pass2b-invocation.md` | Agent invocation patterns for Pass 2b |
| `references/pass2b-output-schema.md` | Expected output format from Pass 2b agents |
| `references/css-design-system.md` | CSS design system for the v2 template |
| `references/section-guide.md` | Section-by-section guide to the review pack layout |
| `references/validation-checklist.md` | Validation criteria for review pack correctness |
| `references/prerequisites.md` | Detailed prerequisite documentation |

## Development

Unit tests:

```bash
python3 -m pytest tests/ -v
```

E2E tests:

```bash
npx playwright install chromium
npx playwright test e2e/
```

## License

Apache 2.0 -- see [LICENSE](LICENSE) for details.

