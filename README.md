# PR Review Pack

Self-contained interactive HTML review pack generator for pull requests, implemented as a Claude Code skill with agent-team-based code review.

The project lead reviews the report, not the code. The review pack is the artifact that tells them whether to merge, what the risks are, and what to watch post-merge.

## Prerequisites

- **Python 3.12+** with `pyyaml` installed (`pip install -r requirements.txt`)
- **git**
- **gh CLI** (authenticated -- run `gh auth login`) -- used for PR metadata, CI checks, and comment resolution
- **Claude Code** with Agent Teams enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`)

## Quick Start

1. Clone into your repo's Claude Code skills directory:
   ```bash
   git clone https://github.com/joeyfezster/pr-review-pack.git .claude/skills/pr-review-pack
   pip install -r .claude/skills/pr-review-pack/requirements.txt
   ```
2. Create a zone registry from the example:
   ```bash
   cp .claude/skills/pr-review-pack/examples/zone-registry.example.yaml .claude/zone-registry.yaml
   # Edit zone-registry.yaml to map your repo's files to architectural zones
   ```
3. Run the skill:
   ```
   /pr-review-pack <PR#>
   ```

The skill produces a self-contained HTML file at `docs/pr{N}_review_pack.html` with interactive diff viewing, architecture diagrams, and review findings.

## Three-Pass Pipeline

The review pack is built through a deterministic three-pass pipeline:

### Pass 1 -- Deterministic Diff Extraction

Extracts structured diff data from the PR using `git` and `gh` CLI. Produces a JSON file with per-file hunks, stats, and metadata. No LLM involvement -- this pass is fully deterministic and reproducible.

### Pass 2 -- LLM Agent Team Semantic Review

An agent team performs semantic analysis of the changes. Each reviewer runs in a separate Claude Code session with independent context (see Agent Teams below). Reviewers assess code health, test integrity, security posture, and adversarial concerns. The structured findings are merged into the review pack data.

If a Dark Factory `gate0_results.json` artifact is present, Pass 2 reuses the Tier 2 findings from Gate 0 instead of re-running the LLM review agents, avoiding duplicate work.

### Pass 3 -- Deterministic HTML Render

Renders the final HTML from the review pack data JSON and an HTML template. This pass is fully deterministic -- given the same data, it produces the same HTML every time. The diff data is embedded inline so the HTML file is entirely self-contained.

## Agent Teams: Why and How

### Why Agent Teams

Each reviewer runs in a **separate Claude Code session** with its own independent context window. This structurally guarantees anti-anchoring: a security reviewer cannot be influenced by what the code health reviewer concluded, and vice versa. The reviews are genuinely independent, not just prompted to be independent within a shared context.

### How to Enable

Set the environment variable before launching Claude Code:

```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

The skill handles team creation, task assignment, and result aggregation automatically. You do not need to manage agents manually.

## Configuration

### Zone Registry

The zone registry maps file paths to architectural zones. It is used to generate the architecture diagram and to route files to the correct reviewer. Create one from the example:

```bash
cp examples/zone-registry.example.yaml .claude/zone-registry.yaml
```

Each zone has a name, a list of glob patterns, and display coordinates for the architecture SVG.

### Output Directory

Review pack artifacts are written to `docs/` by default:

| Artifact | Filename |
|----------|----------|
| Review pack HTML | `docs/pr{N}_review_pack.html` |
| Diff data JSON | `docs/pr{N}_diff_data.json` |

### Specs (Optional)

If your repo has component specifications in `specs/`, the review pack will cross-reference changes against relevant specs and surface any spec compliance concerns.

### Factory Integration

When used within the Dark Factory loop, the PR Review Pack reuses Gate 0 Tier 2 (LLM review agent) findings if `artifacts/factory/gate0_results.json` exists. This avoids running the same LLM review twice -- once in Gate 0 and again in the review pack.

## Permissions & Setup

**This skill is extremely permissive.** The SKILL.md `allowed-tools` frontmatter pre-approves broad bash patterns (`python3 *`, `gh *`, `osascript *`, `screencapture *`) to avoid constant permission prompts during the multi-step pipeline. Review the list before adopting.

### Claude Code Permissions

The skill's `allowed-tools` should handle most prompts automatically. If you still get permission requests, add these to your project's `.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 *)", "Bash(gh *)", "Bash(git diff *)", "Bash(git log *)",
      "Bash(git show *)", "Bash(git status *)", "Bash(screencapture *)",
      "Bash(osascript *)", "Bash(open *)", "Bash(sleep *)", "Bash(which *)"
    ]
  }
}
```

### macOS Permissions (one-time, per machine)

Visual validation uses `screencapture` and `osascript` (for scrolling the browser). These require OS-level grants that cannot be automated:

| Permission | Where to grant | When prompted |
|------------|---------------|---------------|
| **Screen Recording** | System Settings → Privacy & Security → Screen Recording → iTerm2 | First `screencapture` call |
| **Accessibility** | System Settings → Privacy & Security → Accessibility → iTerm2 | First `osascript` keystroke call |

Grant once per Mac. **Restart iTerm2 after granting.** If you skip visual validation, these aren't needed — but the red "NOT Visually Inspected" banner will remain on the review pack.

## License

Apache 2.0 -- see [LICENSE](LICENSE) for details.
