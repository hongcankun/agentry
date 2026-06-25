---
name: conventional-commits
description: Create commits that follow the Conventional Commits specification, including selecting appropriate types, writing clear descriptions, and validating commit messages. Use when a user asks to create a commit, update a commit message, or ensure commits follow conventional commits.
---

# Conventional Commits

Create or modify commits to follow the Conventional Commits specification (https://www.conventionalcommits.org/).

## When to use

Use this skill when the task is to:
- create a new commit following conventional commits;
- rewrite an existing commit's message to follow conventional commits;
- validate if a commit message follows conventional commits.

## Commit scope

Keep each commit focused on a single logical change. A commit should do one thing, so its `type` and `description` describe it without ambiguity:

- If the staged changes span unrelated concerns (e.g. a bug fix plus an unrelated refactor), split them into separate commits rather than forcing one type onto a mixed change.
- A change that genuinely belongs together — code plus its tests, or a rename touching many files — is one logical change and stays in one commit.
- When you cannot pick a single accurate `type`, that is a signal the commit is doing too much; split it.

## Commit message structure

A Conventional Commit message has the following structure:

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Type (required)

Must be one of:
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc.)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools and libraries such as documentation generation

### Scope (optional)

A noun describing a section of the codebase surrounded by parenthesis, e.g., `fix(parser):`

### Description (required)

A short, imperative, present tense description of the change. Do not capitalize the first letter. No dot (.) at the end. Keep the subject line short (around 50 characters, 72 max).

### Body (optional)

A longer, imperative, present tense description of the change, providing additional context. Add a brief body when the subject alone does not explain important context, such as why the change exists, what behavior it adds, or why generated files changed.

Prefer wrapping commit body prose at about 72 columns for Git's conventional terminal-friendly formatting, but do not treat unwrapped body paragraphs as invalid Conventional Commits. Separate paragraphs with a blank line, and use list markers where structure is intended.

### Footer(s) (optional)

Additional meta-information, e.g., breaking changes, issue references.

## Workflow

1. Confirm the staged changes form a single logical change (see Commit scope); if not, split them first.
2. Analyze the changes being committed to determine the appropriate `type`.
3. Determine if a `scope` is appropriate (optional).
4. Write a clear, concise `description`.
5. Add a `body` if more context is needed (optional).
6. Add `footer(s)` if applicable (optional).
7. Validate the commit message (use `scripts/validate_commit_message.py` if needed).

## References

- `references/conventional-commits-spec.md`: Full Conventional Commits specification.
