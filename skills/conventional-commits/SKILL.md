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

A short, imperative, present tense description of the change. Do not capitalize the first letter. No dot (.) at the end.

### Body (optional)

A longer, imperative, present tense description of the change, providing additional context.

### Footer(s) (optional)

Additional meta-information, e.g., breaking changes, issue references.

## Workflow

1. Analyze the changes being committed to determine the appropriate `type`.
2. Determine if a `scope` is appropriate (optional).
3. Write a clear, concise `description`.
4. Add a `body` if more context is needed (optional).
5. Add `footer(s)` if applicable (optional).
6. Validate the commit message (use `scripts/validate_commit_message.py` if needed).

## References

- `references/conventional-commits-spec.md`: Full Conventional Commits specification.
