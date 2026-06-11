---
# Trae: always load this rule; description aids intelligent activation.
# Claude Code: ignores these keys, and loads always since `paths` is omitted.
description: How to review code changes before approving or merging.
alwaysApply: true
---

# Code Review

Follow the `code-review` skill as the authoritative procedure for how to review (scope, dimensions, severity, findings format). The rules below are the non-negotiable project policy that governs when a review is required and when a change may merge.

## When to review

- Before merging any pull request or committing to a shared branch.
- When the change touches security-sensitive code (auth, user data, payments) or makes an architectural change.

## Merge gates

A change must not merge until:

- CI and all automated checks pass.
- Merge conflicts are resolved and the branch is up to date with its target.
- All Critical and High findings are resolved (see approval criteria).

For local review of uncommitted or unmerged work, these gates do not block the review itself — review early to catch issues before committing. Run the project's typecheck, lint, and tests as part of the review and treat any failure as a finding.

## Approval criteria

- Block on any Critical finding (security vulnerability or data-loss risk); it must be fixed before merge.
- Do not approve while a High finding is open; resolve it or get explicit sign-off before merge.
- Never approve a change with a security vulnerability or failing CI.

## Related

- `code-review` skill — the full review procedure and references.
- `git-workflow` and `conventional-commits` skills — branch, merge, and commit standards.
