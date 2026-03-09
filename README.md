# PR Review Pack

Self-contained interactive HTML review pack generator for pull requests. The reviewer reads the pack, not the code.

The output is a Mission Control layout: a two-panel HTML file with sidebar navigation, zone mini-map, collapsible sections, and keyboard shortcuts. Open it in a browser, read the top-level summary, and drill into any section that needs deeper inspection.

## Prerequisites

- **Python 3.12+** with `pyyaml` (`pip install -r requirements.txt`)
- **Node.js** (for Playwright E2E tests: `npm install`)
- **`gh` CLI** authenticated (`gh auth login`)
- **Zone registry** in the target project (`.claude/zone-registry.yaml`)

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
# Pass 1: Extract diff data (deterministic, no LLM)
python3 scripts/generate_diff_data.py --base main --head HEAD --output docs/prN_diff_data.json

# Pass 2a: Scaffold deterministic fields
python3 scripts/scaffold_review_pack_data.py --pr N --diff-data docs/prN_diff_data.json --output /tmp/prN_review_pack_data.json

# Pass 2b: Semantic enrichment (orchestrator spawns 5 review agents + 1 semantic agent)
# See references/pass2b-invocation.md for the exact agent invocation pattern

# Pass 3: Render HTML
python3 scripts/render_review_pack.py --data /tmp/prN_review_pack_data.json --output docs/prN_review_pack.html --diff-data docs/prN_diff_data.json --template v2

# Validate with Playwright
npx playwright test e2e/
```

Replace `N` with the actual PR number throughout.

## 5-Agent Review Team

Pass 2b spawns five independent review agents, each in its own context window. Anti-anchoring is structural -- no agent sees another's conclusions.

| Abbreviation | Agent | Focus |
|--------------|-------|-------|
| **CH** | Code Health | Code quality, complexity, dead code, maintainability |
| **SE** | Security | Vulnerabilities, injection vectors, auth/authz gaps |
| **TI** | Test Integrity | Test quality, vacuous assertions, mocking hygiene |
| **AD** | Adversarial | Gaming, spec violations, architectural dishonesty |
| **AR** | Architecture | Zone coverage, coupling, structural changes, architecture documentation |

A sixth agent (Semantic) runs in parallel, producing `whatChanged`, `decisions`, `postMergeItems`, and `factoryHistory` from the diff.

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
packages/pr-review-pack/
├── assets/
│   ├── template.html             # Legacy single-page template
│   └── template_v2.html          # Mission Control HTML template
├── scripts/
│   ├── generate_diff_data.py     # Pass 1: deterministic diff extraction
│   ├── scaffold_review_pack_data.py  # Pass 2a: deterministic field scaffolding
│   ├── render_review_pack.py     # Pass 3: deterministic HTML rendering
│   └── review_pack_cli.py        # CLI tool (status/refresh/merge)
├── e2e/                          # Playwright E2E tests
├── tests/                        # Python unit tests
├── references/                   # Specification documents
├── examples/                     # Zone registry example
├── docs/                         # Generated review pack artifacts
├── review-prompts -> ../review-prompts  # Agent paradigm prompts
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
