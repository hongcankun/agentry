---
description: Inspect branch state and draft or create a pull request with a Conventional Commit title after confirmation.
argument-hint: "[base-branch] [PR intent]"
---

# Prepare PR

Use this command when the user wants help preparing a pull request for the current branch.

## Inputs

- `[base-branch]`: Optional target branch. If omitted, infer it from repository defaults such as `main`, `master`, or the upstream branch.
- `[PR intent]`: Optional summary, issue id, reviewer notes, or release context.
- Selected files or prior discussion may be used as additional PR context.

If the base branch is unclear, the current branch has uncommitted changes, or pushing/opening a pull request would affect shared remote state, ask one concise clarifying question before acting.

## Workflow

1. Inspect repository state with `git status --short --branch`.
2. Determine the current branch and target base branch. Refuse to prepare a PR from the protected base branch itself unless the user explicitly asks for a branch plan instead.
3. Inspect branch relationship and commits with commands such as:
   - `git branch --show-current`;
   - `git rev-parse --abbrev-ref --symbolic-full-name @{u}` when an upstream exists;
   - `git log --oneline <base>..HEAD`;
   - `git diff --stat <base>...HEAD`;
   - `git diff <base>...HEAD` when needed for an accurate summary.
4. Check for an existing pull request template, such as `.github/pull_request_template.md`, and follow it when drafting the body.
5. Draft a PR title using Conventional Commit format. Use the dominant change type, or ask before choosing if multiple unrelated changes are present.
6. Draft a PR body that summarizes changes, testing, risks, and open follow-ups. Preserve required checklist items from the repository template.
7. Present the proposed title and body. Ask for explicit confirmation before pushing, setting upstream, or opening/updating a pull request.
8. If confirmed and the relevant CLI is available, push only the current branch and create or update the PR. Otherwise, return the ready-to-use title and body.
9. Verify the result by reporting the PR URL or the command that could not be run.

## Constraints

- Do not push, force-push, or open/update a pull request without explicit user confirmation.
- Do not use `--force`; use `--force-with-lease` only when the user explicitly approves a force-push.
- Do not hide failing checks or omit known risks from the PR body.
- Do not invent test results. If tests were not run, state that clearly.

## Output

Return:
- the target base branch and current branch;
- the proposed or created PR title and body;
- the push/PR URL when created;
- validation performed, skipped, or blocked.
