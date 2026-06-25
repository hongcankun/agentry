# Contributing to Agentry

Thanks for your interest in contributing. This file is the short human-facing checklist. The detailed maintainer mechanics live in [`AGENTS.md`](./AGENTS.md), and user-facing behavior is documented in [`README.md`](./README.md).

## Core Rules

- For extension changes, edit the canonical sources: [`agentry.json`](./agentry.json), `plugins/`, and `rules/`.
- Do not hand-edit generated packaging such as `.claude-plugin/`, `.trae-plugin/`, or derived skill references.
- Keep extensions tool-agnostic. Put tool-specific behavior in generators, not in portable skills, subagents, commands, or rules.
- Use the matching `agentry-authoring` skill when creating or changing a skill, subagent, command, rule, or plugin.

## Change Checklist

1. Make the source change in the relevant canonical file or directory, such as `plugins/`, `rules/`, `scripts/`, docs, tests, or `.github/`.
2. Update `agentry.json` when plugin membership, component metadata, rules, references, or plugin versions change.
3. For extension changes, bump only the affected plugin `version`. Bump the top-level project `version` only in explicit release-prep PRs. See [`README.md#versioning`](./README.md#versioning).
4. Regenerate derived packaging after manifest or extension changes:
   ```bash
   python3 scripts/agentry.py generate
   ```
5. Update `README.md` when user-facing commands, plugins, skills, rules, or workflows change.
6. Validate before opening a PR:
   ```bash
   python3 scripts/agentry.py generate --check
   python3 -m unittest discover scripts/tests
   ```

For release-prep PRs, also update `CHANGELOG.md` with `git-cliff --output CHANGELOG.md`.

## Pull Requests

- Name branches as `type/short-description`, with the type matching the Conventional Commit type.
- Use [Conventional Commits](https://www.conventionalcommits.org/) for commits and PR titles.
- Add a brief commit body when the subject alone does not explain the important context, such as why the change exists, what user-facing behavior it adds, or why generated/dogfooding files changed. Hard-wrap commit body prose at about 72 columns.
- Keep each PR focused on one logical change.
- Use `.github/pull_request_template.md`; do not hard-wrap PR body paragraphs.
- Commit regenerated packaging with the source changes that require it.
