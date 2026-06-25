# Contributing to Agentry

Thanks for your interest in contributing. This guide covers the human-facing workflow; the detailed mechanics live in [`AGENTS.md`](./AGENTS.md) and [`README.md`](./README.md), so this file links to them rather than restating them.

## Before you start

- Agentry's extensions are **tool-agnostic**. Per-tool packaging is generated from a single canonical manifest, [`agentry.json`](./agentry.json) — **edit the manifest and content, never the generated files** (`.claude-plugin/`, `.trae-plugin/`). See [`AGENTS.md`](./AGENTS.md) for the full source-of-truth rules.
- Skills, subagents, and rules each follow a standard layout. Use the matching `agentry-authoring` skill (`skill-manager`, `subagent-manager`, `rule-manager`, `plugin-manager`) when creating or editing one — each defines and runs its own validation.

## Making a change

Follow the extension-change workflow in [`AGENTS.md`](./AGENTS.md#extension-changes). In short:

1. Edit the content under `plugins/<plugin>/` (skills/subagents) or `rules/` (rules).
2. Update [`agentry.json`](./agentry.json) to reflect any added/removed/renamed component.
3. Bump versions per the [Versioning policy](./README.md#versioning): in ordinary change PRs, bump only the changed plugin's `version` (per-plugin SemVer). The top-level project release `version` is bumped only in release-prep PRs.
4. Regenerate packaging:
   ```bash
   python3 scripts/agentry.py generate
   ```
5. In release-prep PRs, update the generated changelog:
   ```bash
   git-cliff --output CHANGELOG.md
   ```
   Release-prep commits are excluded from the generated changelog; it should describe the changes being released, not the metadata commit that packages them.
6. Update [`README.md`](./README.md) if the plugin/skill list or any affected section changed.
7. Validate packaging before opening a PR:
   ```bash
   python3 scripts/agentry.py generate --check
   ```
   Must pass — `--check` fails if the generated packaging is out of date.
8. Run the test suite (stdlib `unittest`, no extra dependencies):
   ```bash
   python3 -m unittest discover scripts/tests
   ```

## Proposing a new plugin

A new plugin changes the plugin set: add it to `agentry.json` under `plugins`, create its directory under `plugins/<name>/`, bump that plugin's `version`, and regenerate. The top-level project release `version` is bumped later in a release-prep PR. Use the `plugin-manager` skill for the layout and manifest details, and explain the rationale in your PR description.

## Commits and pull requests

- Name branches with the `type/short-description` form, where `short-description` is lowercase and hyphenated (for example, `fix/branch-naming-policy`).
- This repo follows [Conventional Commits](https://www.conventionalcommits.org/) — see the `conventional-commits` skill in the `agentry-git` plugin.
- Add a brief commit body when the subject alone does not explain the important context, such as why the change exists, what user-facing behavior it adds, or why generated/dogfooding files changed. Hard-wrap commit body prose at about 72 columns.
- Keep each PR focused on one change, with a clear description of what and why. Do not hard-wrap PR body paragraphs; let the hosting UI soft-wrap them.
- Confirm the validation commands above pass and the generated packaging is committed alongside your source edits.
