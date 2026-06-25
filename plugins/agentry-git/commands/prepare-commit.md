---
description: Inspect repository changes, stage a focused change set, and create a local Conventional Commit on an appropriate branch.
argument-hint: "[pathspecs or commit intent]"
---

# Prepare Commit

Use this command when the user wants help turning current repository changes into one focused local Conventional Commit, normally on a short-lived branch rather than directly on the default branch.

## Inputs

- `[pathspecs or commit intent]`: Optional files, directories, issue id, or plain-language commit intent. If omitted, inspect the whole worktree.
- Selected files may be treated as the intended commit scope when the tool provides them.

If the intended commit scope is ambiguous, the worktree contains unrelated changes, or committing would include unreviewed content, ask one concise clarifying question before staging or committing.

## Workflow

1. Inspect repository state with `git status --short --branch`.
2. Check the current branch. Prefer creating the local commit on a short-lived branch. If the repository is on its default or protected branch such as `main` or `master`, stop and ask whether to create or switch to a short-lived branch before committing, unless the user explicitly requested committing there and the repository workflow allows it.
3. Inspect the relevant diff:
   - use `git diff -- <pathspecs>` for unstaged changes;
   - use `git diff --cached -- <pathspecs>` for staged changes;
   - include untracked file names from `git status`, reading file contents only when needed to understand the commit.
4. Identify whether the changes form one coherent commit. If they should be split, propose focused commit groups and stop unless the user chooses one.
5. Choose a Conventional Commit type and optional scope. Prefer the existing repository conventions when visible in recent commit history.
6. Draft a commit message with a short imperative subject, optional body, and any relevant footer.
7. Present the exact files to stage and the exact commit message. Since staging and committing are local and reversible, proceed without an extra confirmation — but stop here if the scope, type, or message is questionable and the user may not have intended it.
8. Stage only the planned paths and create the commit.
9. Verify with `git status --short --branch` and, when practical, `git log -1 --oneline`.

## Constraints

- Do not amend, rebase, reset, stash, or discard changes unless the user explicitly asks.
- Do not commit directly on the default or protected branch unless the user explicitly asks and the repository workflow allows it.
- Do not stage files outside the confirmed scope.
- Do not bypass hooks with `--no-verify` unless the user explicitly asks and accepts the risk.
- Do not push after committing unless the user explicitly asks.
- If commit hooks fail, report the failure and leave the repository state intact.

## Output

Return:
- the commit hash and subject when a commit was created;
- the selected Conventional Commit reasoning in one sentence;
- any files intentionally left unstaged;
- any verification that passed or failed.
