---
description: Review local changes, a branch, commit range, pull request, merge request, diff, or file for code-quality issues.
argument-hint: "[review target or intent]"
---

# Review Code

Use this command when the user wants an explicit code-quality review of a bounded change or file.

## Inputs

- `[review target or intent]`: Optional PR/MR number or URL, branch, commit range, file path, diff path, selected files, or plain-language review intent. If omitted, review the current uncommitted or unmerged repository changes.
- Selected files or pasted diffs may be treated as the intended review scope when the tool provides them.

If the review scope, base branch, or desired output format is unclear, ask one concise clarifying question before doing a broad review.

## Workflow

1. Follow the `code-review` skill as the authoritative review procedure, including its references and output contract.
2. Establish the exact review scope and intent:
   - for local work, inspect repository state and determine changed files with `git status --short --branch` and the relevant `git diff` command;
   - for a branch or commit range, identify the base/target and inspect the range diff;
   - for a PR/MR, read its metadata, description, checks, and diff when platform tools are available;
   - for named files, review only those files unless the change requires nearby context.
3. Read changed files in context, not just hunks, so call sites, contracts, and assumptions are visible.
4. Evaluate correctness, security, error handling, readability, design, performance, testing, and documentation. Prioritize security-sensitive changes first.
5. Run the project's relevant typecheck, lint, tests, or build when practical. Treat failures as review findings; if checks cannot run, state why.
6. Filter out speculative nits and low-confidence findings. Report only issues with a concrete impact and actionable fix.
7. When reviewing a PR/MR and the platform supports comments, prepare inline comments for findings tied to specific lines and a concise summary for cross-cutting points.

## Constraints

- Review only; do not edit, stage, commit, push, approve, or merge code unless the user explicitly asks in a separate instruction.
- Stay within the requested scope unless a problem outside it is directly caused by the reviewed change.
- Do not invent issues to make the review look busy. A clean review is valid.
- Never approve a change with a known security vulnerability or failing required checks.

## Output

Return:
- a concise change summary in your own words;
- findings grouped by severity, each with `file:line`, problem, impact, and suggested fix;
- validation results, including checks run, skipped, or blocked;
- a severity-count summary and a one-line verdict: approve, request changes, or block.
