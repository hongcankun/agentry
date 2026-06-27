# Agentry Agent Instructions

Project-specific guidance for AI agents maintaining this repository. This is meta-guidance only; do not package it into any plugin or install it elsewhere.

## Source of Truth

- Treat `agentry.json` as the canonical, tool-agnostic manifest for plugins, skills, subagents, commands, rules, versions, and component grouping.
- Edit canonical sources under `plugins/` and `rules/`. Do not hand-edit generated packaging:
  - `.claude-plugin/marketplace.json`
  - `plugins/*/.claude-plugin/plugin.json`
  - `.trae-plugin/marketplace.json`
  - derived skill references under `plugins/<plugin>/skills/<skill>/references/`
- For derived skill references, edit the canonical rule under `rules/`, then regenerate. Fence maintainer-only prose with `<!-- skill-reference:exclude:begin -->` and `<!-- skill-reference:exclude:end -->` when it must not appear in the portable skill copy.

## Extension Changes

When changing extensions or plugin membership:

1. Edit the canonical content: skills, agents, and commands under `plugins/<plugin>/`; rules under `rules/`.
2. Update `agentry.json` for added, removed, or renamed components, plugin metadata, rules associations, `skillReferences`, and the changed plugin's SemVer `version`.
3. Do not bump the top-level project release `version` in ordinary change PRs. Bump it only in explicit release-prep PRs, following `README.md#versioning`.
4. Regenerate packaging with `python3 scripts/agentry.py generate`.
5. Keep user-facing docs in sync:
   - update the top-level `README.md` for catalog-wide install, plugin list, versioning, or workflow changes;
   - update `plugins/<plugin>/README.md` for plugin-specific purpose, install guidance, component table, or workflow changes.
6. In release-prep PRs only, update `CHANGELOG.md` with `git-cliff --tag vX.Y.Z --output CHANGELOG.md`.
7. Validate with:
   ```bash
   python3 scripts/agentry.py validate
   python3 -m unittest discover scripts/tests
   ```

Plugin README files should stay concise: purpose, when to install, component table, and install commands that distinguish direct marketplace installs from `scripts/agentry.py`.

For each new or changed extension artifact, use the matching `agentry-authoring` skill (`skill-manager`, `subagent-manager`, `command-manager`, `rule-manager`, or `plugin-manager`) and follow that skill's validation. Do not call a skill's private helper scripts directly from here.

## Dogfooding

Agentry dogfoods its own plugins only in this repository. The committed `.trae/{skills,agents,commands,rules}` entries for Agentry-owned content must remain symlinks back to canonical sources, so local changes activate here without copying content or affecting other projects.

- Do not auto-generate the project-local dogfooding set from `agentry.json`; enabled plugins are a deliberate, hand-maintained choice.
- Add or remove project-scoped Trae dogfooding with `python3 scripts/agentry.py install --tool trae --plugin <plugin> --symlink --component all`.
- Do not copy Agentry-owned skills, agents, commands, or rules into `.trae/`. External third-party content may be committed there when appropriate.
- Rules are not delivered by plugin formats. Activate enabled plugin rules for this repo through `.trae/rules/` symlinks to `rules/`.
- Use `--dry-run` before uncertain install or uninstall operations. See `README.md` for the marketplace vs. checkout channel details.
- Restart the CLI after changing dogfooding symlinks.

Use the dogfooded `conventional-commits` and `git-workflow` skills for git work, `code-review` for reviews, and the `agentry-authoring` skills when editing extensions.

## Git Workflow

- Never commit directly to `main`. Land changes through a short-lived branch and pull request.
- Name branches as `type/short-description`; align the type with the Conventional Commit type.
- Use Conventional Commits for commit messages and PR titles.
- Add a brief commit body when the subject alone does not explain important context. Must hard-wrap commit body prose at about 72 columns.
- Always ask for explicit confirmation before pushing, opening a PR, updating a PR, pushing tags, or creating/publishing a GitHub Release.
- For clear local-only reversible git operations, state the plan and proceed without confirmation. Examples: staging, committing drafted changes, creating a branch for current work with `git switch -c`, switching clean branches, `git pull --ff-only`, `git branch -d`, and `git fetch --prune`.
- Stop and ask before destructive commands, switching a dirty worktree away from current work, unclear merge cleanup, ambiguous commit scope, or any `git reset --hard` style shortcut.
- Write PR bodies from `.github/pull_request_template.md`. Do not hard-wrap PR body paragraphs; let the hosting UI soft-wrap them.

## Authoring Conventions

- Keep extensions tool-agnostic. Put per-tool behavior in generators, not in portable skill, rule, command, or agent content.
- Rules live once under `rules/`, organized by topic, and are associated to plugins through each plugin's `rules` array in `agentry.json`. Every rule must be referenced by at least one plugin.
- A rule may be referenced by multiple plugins. Do not nest rules inside a single plugin.
- When a reference crosses a plugin boundary, name the other plugin, for example `agentry-git`.
- Skills must be self-contained and must not require a rule to be installed. If a skill needs rule text, embed it through the plugin's `skillReferences` map and regenerate.
