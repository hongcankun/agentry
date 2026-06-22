---
name: git-workflow
description: Apply git workflow best practices, including choosing a branching strategy, writing commits and pull requests, performing merges and rebases safely, resolving conflicts, and managing releases and tags. Use when a user asks how to structure git work, set up a branching model, review a workflow, or carry out git operations like rebasing, merging, or releasing.
---

# Git Workflow

Help select and apply a git workflow: branching strategy, commit and pull request conventions, merge vs rebase decisions, conflict resolution, and release management.

## When to use

Use this skill when the task is to:
- choose or set up a branching strategy for a project or team;
- structure feature work, commits, or pull requests;
- decide between merge and rebase, or perform either safely;
- resolve merge conflicts;
- cut a release or manage tags and versioning;
- review or improve an existing git workflow.

## Workflow

1. Identify the context: team size, release cadence, and whether the branch is shared.
2. Pick a branching strategy (see `references/branching-strategies.md`).
3. Write commits following Conventional Commits. If the task is specifically about commit messages, use the `conventional-commits` skill.
4. Open pull requests with a clear title and description (see `references/pull-requests.md`).
5. Choose merge vs rebase per the safety rules below, then integrate.
6. Resolve conflicts deliberately, never discarding work blindly.
7. For releases, apply Semantic Versioning and annotated tags (see `references/releases.md`).

## Branching strategies (summary)

- **GitHub Flow**: `main` always deployable; short-lived feature branches merged via PR. Default for most teams.
- **Trunk-Based**: very short-lived branches merged quickly, often behind feature flags. Suits high-velocity teams with strong CI.
- **GitFlow**: long-lived `main` + `develop` with release and hotfix branches. Suits scheduled, versioned releases.

Full comparison and naming conventions: `references/branching-strategies.md`.

## Merge vs rebase safety rules

- **Merge** to preserve true history (e.g. integrating a shared branch); use when others may have based work on the branch.
- **Rebase** to keep a linear history on your own local, unpushed branch before opening or updating a PR.
- **Never rebase or force-push a shared, pushed, or protected branch.** If you must force-push your own branch, use `--force-with-lease`, not `--force`.

Decision guidance, the rebase workflow, and squash-on-merge: `references/merge-vs-rebase.md`.

## Conflict resolution

1. Run the merge or rebase and read which files conflict.
2. Open each file and resolve markers (`<<<<<<<`, `=======`, `>>>>>>>`) by understanding both sides, not by reflexively keeping one.
3. Test, then stage resolved files and continue (`git rebase --continue` or commit the merge).
4. If unsure, prefer `git merge --abort` / `git rebase --abort` over guessing.

Details and tooling: `references/conflict-resolution.md`.

## Operational rules

- Read repository state (`git status`, `git log`, current branch) before acting.
- Treat destructive or shared-state operations (force-push, `reset --hard`, deleting branches, pushing) as needing explicit user confirmation.
- Keep branches focused and short-lived; delete merged branches.
- Name branches `type/short-description`, keeping the branch `type` consistent with the Conventional Commit type its commits carry (see `references/branching-strategies.md`).
- Prefer fixing root causes over bypassing checks (avoid `--no-verify`).

## References

- `references/branching-strategies.md`: Branching models, naming conventions, and selection guidance.
- `references/pull-requests.md`: PR title and description conventions and review checklists.
- `references/merge-vs-rebase.md`: Merge vs rebase decision guidance, rebase workflow, and squash-on-merge.
- `references/conflict-resolution.md`: Conflict resolution steps, tools, and prevention.
- `references/releases.md`: Semantic Versioning, tagging, and changelog guidance.
