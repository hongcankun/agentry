---
description: Clean up after a merged pull request by updating the base branch and deleting the local feature branch after confirmation.
argument-hint: "[base-branch] [feature-branch]"
---

# Finish PR

Use this command when the user wants to clean up local git state after a pull request has merged.

## Inputs

- `[base-branch]`: Optional branch to return to and update. If omitted, infer from repository defaults such as `main`, `master`, or the merged PR base branch.
- `[feature-branch]`: Optional local branch to delete. If omitted, use the current branch when it is not the base branch.

If the target branch, feature branch, or merge status is unclear, ask one concise clarifying question before switching branches, pulling, pruning, or deleting anything.

## Workflow

1. Inspect repository state with `git status --short --branch`. Stop if there are uncommitted changes unless the user explicitly chooses how to handle them.
2. Identify the current branch, base branch, upstreams, and candidate feature branch:
   - `git branch --show-current`;
   - `git branch --merged <base>` when local merge state is enough;
   - use the hosting CLI when available to confirm the PR is merged.
3. Confirm that the feature branch is merged into the base branch or that the remote PR is merged. If merge status cannot be confirmed, ask before deleting the branch.
4. Present the planned actions, such as switching to the base branch, fast-forwarding it, deleting the local feature branch, and pruning stale remote-tracking refs.
5. Ask for explicit confirmation before running any branch deletion, pull, fetch prune, or other shared-state cleanup.
6. After confirmation:
   - switch to the base branch;
   - update it with a fast-forward only pull, such as `git pull --ff-only`;
   - delete the local feature branch with `git branch -d <feature-branch>`;
   - prune stale remote-tracking refs with `git fetch --prune`.
7. Verify with `git status --short --branch` and `git branch --list <feature-branch>`.

## Constraints

- Do not delete an unmerged branch unless the user explicitly asks and accepts the risk.
- Do not use `git branch -D` unless the user explicitly asks.
- Do not run `git reset --hard` or discard work.
- Do not delete remote branches unless the user explicitly asks; many hosts delete PR branches automatically after merge.
- Do not proceed when the worktree is dirty unless the user explicitly chooses a safe handling path.

## Output

Return:
- the base branch updated;
- the local branch deleted or intentionally kept;
- whether pruning ran;
- final repository status and any blocked cleanup.
