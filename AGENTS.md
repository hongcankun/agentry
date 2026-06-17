# Agentry — Agent Instructions

Project-specific guidance for AI agents working in **this repository**. This is meta-guidance for maintaining Agentry itself; it is **not** deliverable content and must not be packaged into any plugin or installed elsewhere.

## Source of truth

`agentry.json` is the canonical, tool-agnostic manifest: it defines every skill, subagent, and rule and how they group into plugins. **Edit `agentry.json`**, never the generated packaging.

These files are **generated** — do not hand-edit them:

- `.claude-plugin/marketplace.json` and each `plugins/*/.claude-plugin/plugin.json` (Claude Code)
- `.trae-plugin/marketplace.json` (Trae)
- any derived skill reference declared via a plugin's `skillReferences` map — a copy of a canonical rule embedded under `plugins/<plugin>/skills/<skill>/references/` (e.g. `plugins/agentry-code-quality/skills/code-review/references/code-style.md`). Edit the canonical rule under `rules/`, then regenerate. To keep maintainer-only prose (e.g. a `## Related` section of ecosystem cross-links) out of the derived copy, fence it in the rule with `<!-- skill-reference:exclude:begin -->` / `<!-- skill-reference:exclude:end -->`; the markers render invisibly in the rule and the generator drops everything between them.

## Maintenance workflow

When changing the extensions or plugin set, follow these steps in order:

1. **Edit the content.** Add or modify skills/subagents under `plugins/<plugin>/`, or rules under `rules/`. New skills must keep the standard layout (`skills/<name>/SKILL.md`, optional `references/`, `scripts/`, `assets/`).
2. **Update `agentry.json`.** Reflect any added/removed/renamed component in the relevant plugin's `skills`/`agents`/`rules` arrays (and its `skillReferences` map when embedding a rule's content into a skill), and its `description`/`keywords` if scope changed.
3. **Bump the version.** Follow the Versioning policy in `README.md`: bump the changed plugin's `version` independently (SemVer — patch = fixes, minor = added component, major = removed/renamed/breaking). Bump the top-level `version` only for catalog-level changes (adding/removing a plugin).
4. **Regenerate packaging.**
   ```bash
   python3 scripts/agentry.py generate
   ```
5. **Update `README.md`.** Keep the plugin/skill list and any affected sections in sync with the change.
6. **Validate.**
   - For each new/changed skill, subagent, or rule, use the matching `agentry-authoring` skill (`skill-manager`, `subagent-manager`, `rule-manager`, `plugin-manager`); each defines and runs its own validation. Do not reach into a skill's internal scripts directly from here.
   - Confirm the generated packaging is current (CI enforces this on push/PR via `.github/workflows/check.yml`):
     ```bash
     python3 scripts/agentry.py generate --check
     ```
   - Run the test suite (stdlib `unittest` — no extra dependencies):
     ```bash
     python3 -m unittest discover scripts/tests
     ```

## Dogfooding

Agentry maintains itself with its own plugins, enabled **only for this project**. The committed `.trae/{rules,skills,agents}` entries are symlinked, so they activate when working here (and for anyone who clones the repo) without affecting other projects and without copying content into the tree. Restart the CLI after changing those symlinks.

Which plugins to enable is a **deliberate, hand-maintained choice** — not every plugin needs to be active here, so do not auto-generate this set from `agentry.json`. Add or remove project-scoped Trae dogfooding components by running `python3 scripts/agentry.py install --tool trae --plugin <plugin> --symlink --component all`.

Use these while working here: `conventional-commits`/`git-workflow` for commits and branches, `code-review` for reviewing changes, and the `agentry-authoring` skills (including `plugin-manager`) when adding or editing extensions.

Keep the source canonical:

- Edit `plugins/` and `rules/` only; the committed `.trae/skills`, `.trae/agents`, and `.trae/rules` entries for Agentry's own content must remain symlinks back to those canonical sources.
- Do **not** install Agentry's own plugins by **copying** their components into `.trae/skills`, `.trae/agents`, `.trae/rules` — that would duplicate the source of truth under `plugins/` and `rules/` and drift. Use `python3 scripts/agentry.py install --tool trae --symlink --component all` instead. (Committing *external*, third-party skills/agents/rules into `.trae/` is fine — only Agentry's own content must not be copied there.)
- Rules are not delivered by plugins, so each enabled plugin's rules are activated for this repo by **symlinks** under `.trae/rules/` pointing back to the canonical files under `rules/`. Skills and agents used for Trae dogfooding are likewise symlinked from `.trae/skills/` and `.trae/agents/` back into `plugins/`. The symlinks track the canonical source with no copy; do not replace them with copied files.
- `agentry.py install`/`uninstall` has two delivery channels (`--source {marketplace,checkout}`). The **marketplace** channel orchestrates the tool's own CLI to add the marketplace and install/remove plugins; these plugins are user-scoped, so it forces `--global` and is the default for `--global` runs. The **checkout** channel copies or symlinks components straight from this checkout and is the project-scope default (passing `--component` also selects it). Rules are never delivered by a plugin — both channels copy them. Use `--dry-run` to preview any run without writing; see README.md for the full flag set.

## Git workflow

This repo follows a PR-based flow; apply it on top of the `git-workflow` and `conventional-commits` skills:

- Never commit directly to `main`. Land every change via a short-lived feature branch and a pull request.
- Always ask for explicit confirmation before pushing a branch or opening/updating a pull request; approval to make a change locally does not authorize these shared, remote actions.
- Use Conventional Commits for both commit messages and PR titles.
- Write the PR body to match `.github/pull_request_template.md`; `gh pr create --body` bypasses the template, so include its sections yourself. Check (`[x]`) each item when satisfied, or when it does not apply append `— N/A: <reason>`; leave a box unchecked only for outstanding work.
- After a PR merges, switch back to `main`, fast-forward it, delete the local feature branch, and prune stale remote-tracking refs (`git fetch --prune`). The remote branch is auto-deleted on merge.

## Conventions

- Keep extensions tool-agnostic; encode per-tool specifics only in the generators, not in skill/rule content.
- Rules are not delivered by plugins (no plugin format has a rules component); they install via `scripts/agentry.py install`. Associate each rule with a plugin via that plugin's `rules` array in `agentry.json`. A rule lives once under `rules/` (organized by topic, not by plugin) and may be referenced by more than one plugin — the association is many-to-many, keyed by the rule's path, so never nest rules inside a single plugin. Every rule must currently be referenced by at least one plugin (that reference is also its install handle); a rule referenced by none is unreachable by the installer. For a repo-wide rule with no natural owner, attach it to the most relevant plugin for now — fully standalone rules would need an additive top-level `rules` declaration and a non-plugin install selector, not added yet.
- When a reference crosses a plugin boundary, name the other plugin (e.g. "the `agentry-git` plugin").
- A skill stays self-contained: it must not depend on a rule being installed. When a skill needs a rule's content at hand, embed a generated copy via the plugin's `skillReferences` map (`{ "<skill>": ["<rule path>"] }`); `generate` writes it into the skill's `references/`. The rule stays canonical under `rules/` (and keeps its own `rules`-array association); fence any maintainer-only prose in the rule with the `skill-reference:exclude` markers so it does not leak into the portable copy.
- Authoring guidance for skills, subagents, rules, and plugins lives in the `agentry-authoring` plugin's skills — consult the matching skill when creating those.
