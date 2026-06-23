# Pull requests

Conventions for opening and reviewing pull requests.

## Title

Use a Conventional Commits style title so it reads well in history:

```
<type>(<scope>): <description>
```

Example: `feat(auth): add password reset flow`

## Description template

```
## What
Brief summary of the change.

## Why
The problem this solves or the motivation.

## How
Key implementation details or decisions worth noting.

## Testing
How the change was verified (tests run, manual steps).

## Checklist
- [ ] Tests added or updated
- [ ] Docs updated if needed
- [ ] No secrets or debug output committed
```

Do not hard-wrap (auto-fold) body text: write each paragraph as a single line and let the host's Markdown renderer soft-wrap it. Hard line breaks mid-paragraph render badly on GitHub/GitLab. Use blank lines to separate paragraphs and explicit Markdown list items where structure is intended.

## Author checklist

- Keep the PR small and focused on a single concern.
- Ensure the branch is up to date with the base branch.
- Run tests and linters locally before requesting review.
- Write a description that lets a reviewer understand intent without reading every line.

## Reviewer checklist

- Confirm the change matches the stated intent.
- Check for correctness, edge cases, and security issues.
- Verify tests cover the new behavior.
- Prefer actionable, specific comments over vague requests.

## Updating a PR

- Push additional commits to the same branch to address feedback.
- Only rebase the PR branch if it is solely yours; use `git push --force-with-lease` afterward.
- Never rewrite history on a branch others are actively building on.
