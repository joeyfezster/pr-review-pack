# Structured Outputs Investigation — Findings

**Date**: 2026-03-15
**Context**: PR Review Pack Streamlining, Phase 1.1

## Question

Does Claude Code's Agent tool support `output_config` or structured output constraints that would enforce JSON schema on spawned agent output?

## Answer: No

Claude Code's Agent tool accepts these parameters:
- `prompt` (string) — task for the agent
- `description` (string) — short description
- `subagent_type` (string) — type of subagent
- `model` (string) — optional model override
- `run_in_background` (boolean) — async execution
- `isolation` (string) — worktree isolation

**No `output_config`, `output_format`, or structured output parameters exist** at the Agent tool level.

### Important Distinction

- **Anthropic API / Agent SDK**: Supports structured outputs via `output_format` with JSON Schema constraints (GA since Jan 2026). Uses constrained decoding at the token generation level.
- **Claude Code Agent Tool**: Does NOT expose this capability. Subagent output is free-form text returned to the main conversation.

These are different interfaces. The API-level feature doesn't surface through Claude Code's interactive agent spawning.

## Recommended Enforcement Path

**Pydantic-only validation with prompt-based format instructions.**

1. **Prompt instructions**: Each paradigm prompt includes the ReviewConcept JSON schema and explicit .jsonl output instructions. The agent writes one JSON object per line to the output file.
2. **Pydantic validation**: The assembler script (`assemble_review_pack.py`) validates every line of every .jsonl file against the pydantic models. Invalid lines produce structured error reports.
3. **Recovery**: On validation failure, the orchestrator can re-prompt the agent with the error report for self-correction.

This is the "pydantic + recovery" approach from the proposal. Structured outputs at the API level would be additive if Claude Code ever exposes them, but the system works without them.

## Adversarial Testing Notes

Since we can't enforce schema at generation time, the assembler must be robust against:
- Missing required fields
- Extra unexpected fields
- Malformed JSON lines
- Wrong data types (string where int expected, etc.)
- Invalid enum values (grades outside A/B+/B/C/F)
- Empty arrays where non-empty expected
- Zone IDs not in registry

All of these are covered by the pydantic model validators and the assembler's verification checks.

## Out of Scope

- Direct API wrapper approach (no API key available)
- Agent SDK integration (requires programmatic setup outside Claude Code)
- PostToolUse hooks for output validation (added complexity, not needed if pydantic validation in assembler is sufficient)
