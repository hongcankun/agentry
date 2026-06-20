---
description: Run a combined pre-merge gate covering code quality, security risk, and test adequacy.
argument-hint: "[change target or intent]"
---

# Quality Gate

Use this command when the user wants a consolidated pre-merge assessment of a bounded change before it is shipped, merged, or handed off for review.

## Inputs

- `[change target or intent]`: Optional PR/MR number or URL, branch, commit range, file path, diff path, selected files, or plain-language gate intent. If omitted, inspect the current uncommitted or unmerged repository changes.
- Selected files, pasted diffs, prior discussion, failing checks, coverage reports, or release notes may be treated as the intended gate scope when the tool provides them.

If the change scope, base branch, authorization for security review, or expected edit mode is unclear, ask one concise clarifying question before doing a broad gate.

## Workflow

1. Establish the exact change scope once:
   - for local work, inspect repository state and determine changed files with `git status --short --branch` and the relevant `git diff` command;
   - for a branch or commit range, identify the base/target and inspect the range diff;
   - for a PR/MR, read its metadata, description, checks, and diff when platform tools are available;
   - for named files, review only those files unless the change requires nearby context.
2. When subagent delegation is available, delegate the three tracks in parallel and give each subagent the same scope summary:
   - `code-reviewer`: review correctness, maintainability, performance, readability, error handling, regression risk, and general engineering fit;
   - `security-auditor`: audit security-sensitive boundaries, untrusted inputs, auth/authz, secrets, file or network access, dependency risk, and dangerous sinks;
   - `test-engineer`: review test adequacy, missing behavior cases, failing or flaky tests, coverage risk, and the validation plan. Ask for review/planning unless the user explicitly allowed test edits.
3. If subagents are unavailable, run the same tracks sequentially by following the `code-review`, `security-audit`, and `test-engineering` skills as the authoritative procedures.
4. Run relevant validation commands when practical. Prefer the narrowest meaningful test/check first, then broader checks when the change crosses shared boundaries. Treat failing required checks as gate findings.
5. Merge the track results:
   - deduplicate overlapping findings;
   - keep the highest justified severity for each issue;
   - distinguish confirmed findings from residual risks, missing evidence, or hardening opportunities;
   - mark confirmed security vulnerabilities and failing required checks as blocking.

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
