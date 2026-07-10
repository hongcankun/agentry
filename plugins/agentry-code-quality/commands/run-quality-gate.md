---
description: Run an integrated pre-merge gate covering the review tracks and validation needed for a bounded change.
argument-hint: "[change target or intent]"
---

# Run Quality Gate

Use this command when the user wants a consolidated pre-merge assessment of a bounded change before it is shipped, merged, or handed off for review.

This command is the gate-oriented entry point for the `integrated-review` skill. Use `integrated-review` as the authoritative workflow for scope establishment, track selection, specialist delegation, validation, finding consolidation, and verdict reporting.

## Inputs

- `[change target or intent]`: Optional PR/MR number or URL, branch, commit range, file path, diff path, selected files, or plain-language gate intent. If omitted, inspect the current uncommitted or unmerged repository changes.
- Selected files, pasted diffs, prior discussion, failing checks, coverage reports, or release notes may be treated as the intended gate scope when the tool provides them.

If the change scope, base branch, authorization for security review, or expected edit mode is unclear, ask one concise clarifying question before doing a broad gate.

## Workflow

1. Run the `integrated-review` skill on the requested target or inferred local change.
2. Tell the skill this command needs a gate report, not publication-ready review comments.
3. Treat missing scope, degraded specialist coverage, failed required validation, confirmed correctness bugs, and confirmed security vulnerabilities as gate inputs.
4. Map the integrated review result to the gate verdict:
   - `pass` when no actionable findings or material residual risks remain;
   - `pass with warnings` when only non-blocking risks, hardening opportunities, or degraded nonessential coverage remain;
   - `request changes` when the change has actionable defects that should be fixed before merge;
   - `block` when the change has confirmed severe risk, failing required validation, unsafe security exposure, or unresolved scope ambiguity.

## Constraints

- Do not edit, stage, commit, push, approve, or merge code unless the user explicitly asks in a separate instruction.
- Keep the gate scoped to the requested change. Do not turn a change review into a whole-repository audit unless the user asked for that.
- Do not inflate findings or invent issues. A clean gate is valid.
- Do not provide weaponized exploit guidance for unauthorized third-party targets.
- If a referenced subagent or skill is unavailable, continue with the available procedure and state the coverage gap in the output.

## Output

Return:
- the gate scope and base/target used;
- a concise change summary in your own words;
- consolidated findings grouped by severity, each with `file:line` or component, problem, impact, source track, and suggested fix;
- separate short subsections for code-review coverage, security coverage, and test/coverage coverage, including any skipped or degraded track;
- validation evidence, including checks run, skipped, failed, or blocked;
- a severity-count summary table;
- a final gate verdict: `pass`, `pass with warnings`, `request changes`, or `block`.
