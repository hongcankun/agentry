---
description: Inspect repository changes, stage a focused commit, and create a Conventional Commit after confirmation.
argument-hint: "[pathspecs or commit intent]"
---

# Prepare Commit

Use this command when the user wants help turning current repository changes into one focused Conventional Commit.

## Inputs

- `[pathspecs or commit intent]`: Optional files, directories, issue id, or plain-language commit intent. If omitted, inspect the whole worktree.
- Selected files may be treated as the intended commit scope when the tool provides them.

If the intended commit scope is ambiguous, the worktree contains unrelated changes, or committing would include unreviewed content, ask one concise clarifying question before staging or committing.

## Workflow

1. Inspect repository state with `git status --short --branch`.
2. Inspect the relevant diff:
   - use `git diff -- <pathspecs>` for unstaged changes;
   - use `git diff --cached -- <pathspecs>` for staged changes;
   - include untracked file names from `git status`, reading file contents only when needed to understand the commit.
3. Identify whether the changes form one coherent commit. If they should be split, propose focused commit groups and stop unless the user chooses one.
4. Choose a Conventional Commit type and optional scope. Prefer the existing repository conventions when visible in recent commit history.
5. Draft a commit message with a short imperative subject, optional body, and any relevant footer.
6. Present the exact files to stage and the exact commit message. Ask for explicit confirmation before running `git add` or `git commit`.
7. After confirmation, stage only the confirmed paths and create the commit.
8. Verify with `git status --short --branch` and, when practical, `git log -1 --oneline`.

## Constraints

- Do not amend, rebase, reset, stash, or discard changes unless the user explicitly asks.
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
