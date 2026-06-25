---
# Trae: always load this rule; description aids intelligent activation.
# Claude Code: ignores these keys, and loads always since `paths` is omitted.
description: Branch, pull request, and shared-state safety policy for Git workflows.
alwaysApply: true
---

# Git Workflow

Follow the `git-workflow` skill as the authoritative procedure for choosing branch strategies, preparing pull requests, integrating changes, resolving conflicts, and publishing releases. The rules below are the non-negotiable policy for branch and shared-state safety.

## Branch policy

- Prefer a short-lived branch for each ordinary change.
- Do not commit directly on a repository's default or protected branch, such as `main` or `master`, unless the user explicitly asks and the repository workflow allows it.
- Keep branch names focused and consistent with repository conventions. When the repository uses `type/short-description`, choose a branch type that matches the primary Conventional Commit type.
- Keep commits on a branch focused on one coherent change set. Split unrelated work before opening or updating a pull request.

## Shared-state policy

- Ask for explicit confirmation before pushing, force-pushing, opening or updating a pull request, publishing a release, or mutating other shared remote state.
- Use `--force-with-lease`, not `--force`, when the user explicitly approves force-pushing a branch that is safe to rewrite.
- Do not delete remote branches unless the user explicitly asks or the hosting workflow performs that cleanup automatically.

## Cleanup policy

- After a pull request merges, update the base branch with a fast-forward-only pull before deleting local feature branches.
- Delete local feature branches with `git branch -d` when they are merged. Use `git branch -D` only when the user explicitly asks, or when the pull request is confirmed merged and `git log --cherry <base>...<branch>` proves the remaining local commits are patch-equivalent.
- Prune stale remote-tracking refs after merged-branch cleanup.

## Related

- `agentry-git` plugin — the plugin this rule ships alongside.
- `git-workflow` skill — the full branch, pull request, merge, cleanup, and release procedure.
- `conventional-commits` skill (in the `agentry-git` plugin) — commit message format and type selection.
