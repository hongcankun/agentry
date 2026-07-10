---
name: code-review
description: Review code changes for correctness, readability, security, performance, and maintainability, then deliver prioritized, actionable feedback. Use when a user asks to review a diff, pull request, commit, branch, or file, or wants feedback on code they wrote or modified.
---

# Code Review

Review a set of code changes and return clear, prioritized, actionable feedback. The goal is to catch defects and risks early while respecting the author's intent and the change's scope.

Follow these principles:
- Review the change, not the whole codebase; stay within the scope of the diff unless a problem outside it is directly caused by the change.
- Prioritize findings by severity so the author knows what must be fixed versus what is optional.
- Be specific: reference exact files and line numbers, explain the impact, and suggest a concrete fix.
- Separate correctness and security issues (blocking) from style and preference (non-blocking).
- Assume good intent; critique the code, not the person.
- **Signal over noise.** Report a finding only when you are confident it is a real problem. Manufactured findings and speculative nits are the primary failure mode of an automated reviewer; a clean review is a valid review. Do not invent issues or withhold approval to appear rigorous.

## When to use

Use this skill when the task is to:
- review a pull request, merge request, diff, commit, or branch;
- review a specific file or function the user points to;
- give feedback on code the user just wrote or changed;
- act as a reviewer before code is merged or shipped.

## Expected input

Gather as much of the following as available:
- what to review (PR/MR number or URL, commit range, branch, file paths, or pasted diff);
- the base/target to diff against (e.g. `main`) when reviewing a branch or local work;
- the change's intent (linked issue, PR description, or a one-line summary);
- the project's conventions (linters, style guides, `CONTRIBUTING`, existing patterns);
- the desired output form (inline comments, a summary report, or both) and depth.

If the scope is ambiguous, default to reviewing the uncommitted or unmerged changes against the main branch, and ask only if the target cannot be determined.

## Review mode

Pick the mode from the input:
- **Local review** — uncommitted or unmerged work. Determine the changed set with `git diff --name-only` (or against the base branch); if nothing changed, stop and say so.
- **PR/MR review** — a pull/merge request given by number, URL, or branch. Resolve it, read its metadata and intent, then review the changes at the PR head.

Both modes use the same workflow below; PR review adds publishing the result back to the platform.

## Workflow

### 1. Establish scope and intent

Identify exactly which changes are under review and what they are meant to accomplish. Read the diff and the change description (PR/issue/commit message); categorize the changed files (source, tests, config, docs). Do not review unchanged code unless the change affects it. Note the languages, frameworks, and project conventions (`CLAUDE.md`, `CONTRIBUTING`, linters, style guides) that apply. Note the state of the change too: whether CI is passing, merge conflicts are resolved, and the branch is up to date with its target — flag these as blockers rather than reviewing around them.

### 2. Read the change in context

Read the **full content of each changed file**, not just the diff hunks, so you see call sites, contracts, and assumptions the diff alone hides. Verify the change actually does what its description claims. Prefer understanding over pattern-matching: a line can be correct or wrong depending on its context.

### 3. Evaluate against the review dimensions

Assess the change across each dimension in `references/review-dimensions.md`: correctness, security, error handling, readability, design, performance, testing, and documentation. **Check security first**, especially when the change touches a security-sensitive trigger (auth/authorization, user input, database queries, file-system access, external API calls, cryptography, or payment/financial code). Then focus remaining effort where the change carries the most risk.

### 4. Validate when possible

If the environment allows, run the project's checks to ground the review in evidence: detect the toolchain from config files and run the matching typecheck, lint, test, and build commands (e.g. `npm`/`pnpm` scripts for Node/TS, `cargo clippy`/`test`/`build` for Rust, `go vet`/`test`/`build ./...` for Go, `pytest` for Python). Treat validation failures as findings. Skip this step only when the changes are docs/config-only or the environment cannot run them.

### 5. Filter findings through the pre-report gate

Pass each candidate finding through the gate in `references/false-positives.md`, and drop or downgrade anything that does not clear it. Report only findings you are confident are real problems; skip the common false positives listed there. That gate also sets the extra proof bar for High/Critical findings.

### 6. Classify and prioritize findings

Assign each surviving finding a severity using `references/severity-levels.md` (Critical, High, Medium, Low, Nit). Keep blocking issues (correctness, security) clearly separated from non-blocking suggestions and pure preferences. Do not inflate severity; a style nit is not a bug. Never approve code with a security vulnerability.

### 7. Decide and deliver feedback

Map findings to a recommendation using the decision logic in `references/severity-levels.md`, then deliver the review in the format described under **Output**. For a PR/MR, publish it on the platform with inline comments on the relevant lines.

## Output

Default to a structured review with:
- a **change summary** in your own words (not a copy of the author's description), covering the problem the change addresses, the solution/approach taken, and the notable concrete changes by area or file; keep it concise and omit empty parts for small diffs. Use it to surface any mismatch between the stated intent and what the diff actually does;
- findings grouped by severity, each as `file:line` + problem + impact + suggested fix (show BAD → GOOD code when it clarifies the fix);
- validation results when checks were run (what passed/failed);
- a summary table of severity → count, and an explicit one-line verdict (approve / request changes / block).

When the platform supports inline comments (e.g. a PR), map findings to specific lines and reserve the summary for cross-cutting points. Acknowledge what the change does well, not only what is wrong. If there are no real findings, say so plainly and approve — do not pad the review.

## References

- `references/review-dimensions.md`: the dimensions to evaluate (correctness, security, error handling, readability, design, performance, testing, docs) with what to look for in each.
- `references/severity-levels.md`: severity definitions (Critical/High/Medium/Low/Nit), how to classify and communicate findings, and the approve/request-changes/block decision logic.
- `references/false-positives.md`: the pre-report confidence gate and the common false positives an automated reviewer should not flag.
- `references/code-style.md`: the project's style standard, underpinning several review dimensions (notably readability, error handling, and design).
