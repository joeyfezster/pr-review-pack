# PR Readiness Prerequisites

Before generating a review pack, verify all PR readiness criteria are met. **All three gates must be green. If any gate fails, stop and fix it before proceeding.** Never present a review pack with a failed prerequisite.

**CRITICAL: Prerequisites must be checked in order. Gate 2 (comments) CANNOT be checked until Gate 1 (CI) is fully complete.** Bot reviewers (Copilot, Codex connector) post their comments AFTER CI finishes. Checking comments before CI completes will produce a stale "0 comments" result that becomes false minutes later. This has happened before -- don't repeat it.

## Gate 1: CI checks GREEN on HEAD

```bash
gh pr checks <N>
```

Wait until ALL checks complete (not just start). CI typically takes 4-6 minutes. If a bot pushed the HEAD commit (GITHUB_TOKEN), CI may not have re-triggered -- push a human-authored commit to fix.

## Gate 2: All review comments resolved

**Run this AFTER Gate 1 is fully green.** Bot reviewers post comments after CI completes.

```bash
# Get unresolved thread count via GraphQL
gh api graphql -f query='
{
  repository(owner: "{owner}", name: "{repo}") {
    pullRequest(number: {N}) {
      reviewThreads(first: 100) {
        nodes { isResolved }
      }
    }
  }
}' --jq '{
  total: (.data.repository.pullRequest.reviewThreads.nodes | length),
  unresolved: ([.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false)] | length)
}'
```

If `unresolved > 0`: resolve or address every comment before proceeding. Both human and AI reviewer comments (Copilot, Codex bot) count.

**Handling unresolved comments:** For each comment, the orchestrator must evaluate and route:

1. **Evaluate** the comment. Bot reviewers can be wrong. For each recommendation, reason about: Is it valid? Is it in scope? What severity does it actually warrant? Not every recommendation becomes action.
2. **Route by who can fix it:**
   - **Orchestrator's agent team territory** (non-product: infra, config, dependency compilation, docs, CI): Spawn an agent to fix it directly. Resolve the thread after the fix is pushed.
   - **Attractor territory** (product code OR complex logic OR security issues OR code performance): Synthesize the comment into `artifacts/factory/post_merge_feedback.md` -- preserving the file path, line number, what was flagged, and the orchestrator's assessment. Then loop back to the attractor (new factory iteration) with this feedback.
   - **Invalid/false-positive**: Resolve the thread with a reply explaining why the recommendation was declined.

**Every thread resolution MUST include a reply comment** explaining how it was resolved -- what was done, by whom, and where (commit SHA or feedback file). Never resolve a thread silently. The comment is the audit trail.

In both routing cases, the goal is to fix it now -- not carry tech debt. The distinction is only about which actor handles the fix.

**Comment counts are deterministic metadata.** They must be pulled via the GraphQL query above and injected directly into the review pack data -- never passed through an LLM agent for counting. Pass 1 (deterministic) owns PR metadata extraction, not Pass 2 (semantic). The badge shows `X/Y comments resolved` where Y is the total thread count and X is the resolved count, both from the API.

## Gate 3: The review pack itself

This is what this skill produces. It is always the last gate.

If any gate is unmet, state what is blocking and resolve it before proceeding.
