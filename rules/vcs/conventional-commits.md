---
# Trae: always load this rule; description aids intelligent activation.
# Claude Code: ignores these keys, and loads always since `paths` is omitted.
description: When commits must follow Conventional Commits and the policy they must satisfy before committing.
alwaysApply: true
---

# Conventional Commits

Follow the `conventional-commits` skill as the authoritative procedure for how to write a commit (message structure, allowed types, scope, and validation). The rules below are the non-negotiable project policy that governs when the convention applies and what a commit must satisfy.

## When it applies

- Every commit on every branch must follow the Conventional Commits format; there are no exempt commits.
- When rewriting or amending a commit message, the rewritten message must also conform.

## Commit policy

- Use a type from the set defined by the `conventional-commits` skill; never invent a new type.
- Mark breaking changes explicitly with a `!` after the type/scope or a `BREAKING CHANGE:` footer.
- Keep each commit focused on a single logical change so its type and description are unambiguous; split unrelated changes into separate commits.
- Write the description in imperative mood, lowercase, with no trailing period.

## Before committing

- Validate the message against the convention before committing (use the skill's validation step); treat a non-conforming message as a blocker.
- Never bypass commit hooks or checks to land a non-conforming message.

## Related

- `agentry-git` plugin — the plugin this rule ships alongside.
- `conventional-commits` skill — the full message format, type list, and validation procedure.
- `git-workflow` skill (in the `agentry-git` plugin) — branch, merge, and release standards.
