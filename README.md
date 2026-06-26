# Agentry

A collection of reusable extensions for AI coding agents — skills, subagents, commands, and rules — following open agent conventions. The extensions are tool-agnostic and grouped into plugins; each AI tool's packaging is generated from a single canonical manifest, so no tool is privileged.

- **Canonical source:** [`agentry.json`](./agentry.json) defines every skill, subagent, command, and rule and how they group into plugins.
- **Per-tool packaging is derived from it** — each tool's marketplace files are generated from the manifest, and an install script copies a plugin's rules (and optionally other components) into a tool's directories.

## Install

Both Claude Code and Trae install Agentry as a plugin marketplace. Each tool reads its own catalog — generated from the same manifest — so the plugin set is identical.

### Claude Code

```
claude plugin marketplace add hongcankun/agentry
claude plugin install agentry-code-quality@agentry
claude plugin install agentry-security@agentry
claude plugin install agentry-git@agentry
claude plugin install agentry-authoring@agentry
claude plugin install agentry-docs@agentry
```

Update later with `claude plugin marketplace update agentry`.

In the interactive Claude Code UI, the same plugin commands are available as slash commands, for example `/plugin marketplace add hongcankun/agentry` and `/plugin install agentry-code-quality@agentry`.

### Trae

```
traecli plugin marketplace add hongcankun/agentry
traecli plugin install agentry-code-quality@agentry
traecli plugin install agentry-security@agentry
traecli plugin install agentry-git@agentry
traecli plugin install agentry-authoring@agentry
traecli plugin install agentry-docs@agentry
```

Update later with `traecli plugin marketplace upgrade agentry`.

In the interactive Trae UI, use the same commands with a leading slash, for example `/plugin marketplace add hongcankun/agentry` and `/plugin install agentry-code-quality@agentry`.

### The install script

`scripts/agentry.py` complements the marketplace. It reads `agentry.json` (so everything maps to the same plugins) and delivers a plugin's pieces through one of **two channels**:

- **marketplace** — orchestrates the tool's own CLI (e.g. `traecli` / `claude`) to add the marketplace and install or remove the selected plugins. The marketplace channel is **user-scoped**, so it forces `--global` and cannot be combined with `--component`; it is the default for a `--global` run.
- **checkout** — copies components straight from this checkout into the tool's directories and never touches the marketplace. An omitted `--component` means all components on this channel. It is the default at project scope. Passing `--component {rules,skills,agents,commands,all}` (repeatable) implicitly selects it; `--source checkout` forces it.

Rules are **never delivered by a plugin** (neither Claude Code nor Trae ship rules in their plugin format), so the script always copies them regardless of channel.

```
# Marketplace channel (user scope): add the marketplace + install the plugin, then copy rules
python3 scripts/agentry.py install --tool trae --global --plugin agentry-code-quality --yes

# Checkout channel (project scope): copy all of a plugin's components
python3 scripts/agentry.py install --tool claude --plugin agentry-code-quality

# Checkout channel: copy skills, subagents, and commands from this checkout (for
# development, or tools without marketplace support)
python3 scripts/agentry.py install --tool trae --component skills --component agents --component commands
```

A bare `install` run is **interactive**: it reports each item's state (missing / synced / stale vs the canonical source), then prompts on a TTY for any omitted selection (`--tool`, `--plugin`, `--component`s, `--symlink`) and before each action, including marketplace/plugin CLI calls. Pass `--defaults` to accept the default selections without asking, or `--yes` to auto-confirm every action.

Non-interactive (CI, piped) behavior is conservative: install installs missing files and skips stale ones; uninstall removes owned files only. Both skip the marketplace/plugin phase unless `--yes` is given. Use `--dry-run` to preview either channel without writing anything.

Additional subcommands round out the lifecycle:

- `status` — report-only; writes nothing. Exits 1 if any file is missing or stale (handy for CI). Also reports marketplace and per-plugin install state read-only (at any scope — plugins are user-scoped), which is informational and never affects the exit code.
- `uninstall` — remove components this repo installed (owned copies or symlinks). Keeps items that have drifted from the source unless `--force` is passed. On the marketplace channel it uninstalls the plugin via the tool CLI and removes the marketplace only when no Agentry plugin remains (to keep it otherwise, or force-remove it, use the tool's own CLI).
- `inventory` — read-only manifest report for plugin versions and component membership. Use `--plugin`, repeated `--component`, `--details`, `--paths`, or `--json` to narrow or script the output.

Add `--symlink` to link components back to the checkout instead of copying, so they track the source with no drift (the link is relative; not portable to Windows checkouts):

```
python3 scripts/agentry.py install --tool trae --plugin agentry-code-quality --symlink
```

Common flags (any omitted selection is prompted interactively, or takes the noted default): `--tool {claude,trae}` (required non-interactively), `--plugin` (default: all plugins), `--source {marketplace,checkout}` (default: marketplace for `--global` runs without `--component`, otherwise checkout), `--component {skills,agents,commands,rules,all}` (repeatable; `all` expands to skills, agents, commands, and rules; selects checkout; default: all components for checkout runs, `rules` for marketplace runs), `--symlink` (install only; default: copy), `--global` (default: project scope; forced by the marketplace channel), `--project-dir`, `--yes`/`-y` (auto-confirm actions), `--defaults` (accept default selections without prompting), `--color {auto,always,never}`, `--dry-run`, `--force`.

## Plugins

Agentry currently ships **5 plugins** with **37 components**: 14 skills, 4 subagents, 12 commands, and 7 rules. Each plugin groups related extensions. Sources live under [`plugins/`](./plugins) (skills, subagents, and commands) and [`rules/`](./rules).

| Plugin | Version | Best for | Skills | Agents | Commands | Rules |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| [`agentry-code-quality`](./plugins/agentry-code-quality) | 0.10.5 | Code review, test design, test repair, review publishing, and pre-merge quality gates. | 3 | 2 | 4 | 3 |
| [`agentry-security`](./plugins/agentry-security) | 0.4.0 | Threat-driven audits for auth, user input, file/network access, crypto, secrets, payments, and other sensitive code. | 1 | 1 | 1 | 1 |
| [`agentry-git`](./plugins/agentry-git) | 0.6.1 | Branching, Conventional Commits, pull requests, merged-branch cleanup, and release flow. | 2 | 0 | 5 | 2 |
| [`agentry-authoring`](./plugins/agentry-authoring) | 0.4.0 | Creating and reviewing skills, subagents, commands, rules, prompt templates, plugins, and marketplaces. | 7 | 1 | 1 | 1 |
| [`agentry-docs`](./plugins/agentry-docs) | 0.2.0 | README creation and maintenance for software repositories. | 1 | 0 | 1 | 0 |

Use `scripts/agentry.py inventory --details` to print the same component counts and membership from the canonical manifest.

### Choosing Plugins

- Install [`agentry-code-quality`](./plugins/agentry-code-quality) for everyday engineering review work: review a diff, improve tests, run a quality gate, or publish review findings.
- Install [`agentry-security`](./plugins/agentry-security) when agents need a dedicated security audit workflow and a proactive security-auditor subagent.
- Install [`agentry-git`](./plugins/agentry-git) when agents should help with local commits, pull requests, merged-branch cleanup, and release publishing.
- Install [`agentry-authoring`](./plugins/agentry-authoring) when you author agent extensions and want the matching manager skills plus cross-artifact review.
- Install [`agentry-docs`](./plugins/agentry-docs) when the main need is README maintenance without the broader authoring toolkit.

### Component Types

- **Skills** are reusable procedures that agents load when a task matches their description.
- **Subagents** are specialist agent profiles that can review or execute bounded work in a focused context.
- **Commands** are slash-command workflows that package a repeatable agent task behind a short command name.
- **Rules** are policy guidance copied into the target tool's rule directories by the install script; plugin formats themselves do not ship rules.

### Plugin Inventory

#### [`agentry-code-quality`](./plugins/agentry-code-quality)

Code review and test-engineering skills, slash commands, and specialist subagents that catch correctness, security, maintainability, and test-quality issues with actionable guidance.

| Type | Components |
| --- | --- |
| Skills | [`code-review`](./plugins/agentry-code-quality/skills/code-review/SKILL.md), [`test-engineering`](./plugins/agentry-code-quality/skills/test-engineering/SKILL.md), [`review-publishing`](./plugins/agentry-code-quality/skills/review-publishing/SKILL.md) |
| Subagents | [`code-reviewer`](./plugins/agentry-code-quality/agents/code-reviewer.md), [`test-engineer`](./plugins/agentry-code-quality/agents/test-engineer.md) |
| Commands | [`review-code`](./plugins/agentry-code-quality/commands/review-code.md), [`improve-tests`](./plugins/agentry-code-quality/commands/improve-tests.md), [`quality-gate`](./plugins/agentry-code-quality/commands/quality-gate.md), [`publish-review`](./plugins/agentry-code-quality/commands/publish-review.md) |
| Rules | [`code-quality/code-review`](./rules/code-quality/code-review.md), [`code-quality/code-style`](./rules/code-quality/code-style.md), [`code-quality/testing`](./rules/code-quality/testing.md) |

#### [`agentry-security`](./plugins/agentry-security)

Security audit skill that runs a threat-driven review of code: maps the attack surface and trust boundaries, hunts vulnerability classes, rates findings by likelihood and impact, and reports exploit scenarios with concrete remediations.

| Type | Components |
| --- | --- |
| Skills | [`security-audit`](./plugins/agentry-security/skills/security-audit/SKILL.md) |
| Subagents | [`security-auditor`](./plugins/agentry-security/agents/security-auditor.md) |
| Commands | [`audit-security`](./plugins/agentry-security/commands/audit-security.md) |
| Rules | [`security/security-audit`](./rules/security/security-audit.md) |

#### [`agentry-git`](./plugins/agentry-git)

Git workflow and Conventional Commits skills for branching, merging, rebasing, pull requests, releases, and well-formed commit messages.

| Type | Components |
| --- | --- |
| Skills | [`git-workflow`](./plugins/agentry-git/skills/git-workflow/SKILL.md), [`conventional-commits`](./plugins/agentry-git/skills/conventional-commits/SKILL.md) |
| Subagents | None |
| Commands | [`prepare-commit`](./plugins/agentry-git/commands/prepare-commit.md), [`prepare-pr`](./plugins/agentry-git/commands/prepare-pr.md), [`finish-pr`](./plugins/agentry-git/commands/finish-pr.md), [`prepare-release`](./plugins/agentry-git/commands/prepare-release.md), [`publish-release`](./plugins/agentry-git/commands/publish-release.md) |
| Rules | [`vcs/conventional-commits`](./rules/vcs/conventional-commits.md), [`vcs/git-workflow`](./rules/vcs/git-workflow.md) |

#### [`agentry-authoring`](./plugins/agentry-authoring)

Authoring skills and review support for building AI agent extensions: create and review skills, subagents, commands, rules, prompt templates, and plugins or marketplaces that follow open agent conventions.

| Type | Components |
| --- | --- |
| Skills | [`skill-manager`](./plugins/agentry-authoring/skills/skill-manager/SKILL.md), [`subagent-manager`](./plugins/agentry-authoring/skills/subagent-manager/SKILL.md), [`command-manager`](./plugins/agentry-authoring/skills/command-manager/SKILL.md), [`rule-manager`](./plugins/agentry-authoring/skills/rule-manager/SKILL.md), [`prompt-template-manager`](./plugins/agentry-authoring/skills/prompt-template-manager/SKILL.md), [`plugin-manager`](./plugins/agentry-authoring/skills/plugin-manager/SKILL.md), [`authoring-review`](./plugins/agentry-authoring/skills/authoring-review/SKILL.md) |
| Subagents | [`authoring-reviewer`](./plugins/agentry-authoring/agents/authoring-reviewer.md) |
| Commands | [`review-authoring`](./plugins/agentry-authoring/commands/review-authoring.md) |
| Rules | [`authoring/authoring-review`](./rules/authoring/authoring-review.md) |

#### [`agentry-docs`](./plugins/agentry-docs)

Documentation authoring skills for software projects, starting with creating and maintaining README files following standard conventions.

| Type | Components |
| --- | --- |
| Skills | [`readme-manager`](./plugins/agentry-docs/skills/readme-manager/SKILL.md) |
| Subagents | None |
| Commands | [`update-readme`](./plugins/agentry-docs/commands/update-readme.md) |
| Rules | None |

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the contribution workflow — editing the canonical manifest, regenerating packaging, versioning, and PR expectations.

## Repository layout

- [`agentry.json`](./agentry.json) — canonical, tool-agnostic manifest. **Edit this**, then regenerate derived files.
- [`plugins/`](./plugins) — each plugin's skills (`skills/<name>/SKILL.md`), subagents (`agents/<name>.md`), and commands (`commands/<name>.md`).
- [`rules/`](./rules) — tool-agnostic rules, organized by topic; associated with plugins via the manifest.
- [`scripts/agentry.py`](./scripts/agentry.py) — maintenance CLI: `install`/`status`/`uninstall` a plugin's components into a tool's directories, report the manifest with `inventory`, and `generate` per-tool packaging from the manifest.
- [`scripts/tests/`](./scripts/tests) — stdlib-only (`unittest`) tests for `scripts/agentry.py`.

### Generated files

Per-tool packaging is **generated** from `agentry.json` — do not edit it by hand:

- Claude Code: `.claude-plugin/marketplace.json` and each `plugins/*/.claude-plugin/plugin.json`.
- Trae: `.trae-plugin/marketplace.json`.
- Derived skill references: a copy of a canonical rule embedded in a skill's `references/`, declared by a plugin's `skillReferences` map so the reference travels with the (copied) plugin while the rule stays canonical under `rules/`.

```
python3 scripts/agentry.py generate          # regenerate all packaging (or pass claude/trae)
python3 scripts/agentry.py generate --check  # verify up to date (for CI)
```

Claude Code and Trae have separate plugin specs that happen to overlap for our content: Trae can read Claude's catalog as a fallback, but its own schema differs (e.g. `owner` is a string, not an object), so we ship a native `.trae-plugin/marketplace.json`. Plugin packages also differ — Claude uses a per-plugin `plugin.json`, while Trae auto-detects component dirs and uses `traecli.toml` inside a plugin package only for MCP servers, hooks, models, or tool-permissions. Agentry's plugins currently contain only skills, subagents, and commands, so no per-plugin manifest is required on Trae. If a plugin later adds MCP/hooks/models, `agentry.py generate` would need to emit a plugin-package `traecli.toml` under that plugin.

Adding support for another tool means adding its targets to `scripts/agentry.py` and, if it has a package format, a generate target alongside the existing ones — without changing the canonical manifest.

## Versioning

Versions live in `agentry.json` and propagate to the generated packaging. Two levels serve different audiences:

- **Per-plugin `version`** (one per entry in `plugins`) — the **delivery** signal. Both Claude Code and Trae use it to push updates: a plugin updates for users only when its version string changes (omit it and the tool falls back to the git commit SHA). Version each plugin **independently** with [SemVer](https://semver.org) over that plugin's content, and bump only the plugins whose content actually changed so unrelated plugins don't show spurious updates:
  - **patch** — wording fixes, clarifications, or non-behavioral edits to existing components.
  - **minor** — add a new skill, subagent, command, or rule to the plugin, or a backward-compatible capability.
  - **major** — remove or rename a component, or otherwise change behavior in a breaking way.
  - While a plugin is still `0.x`, breaking changes may use a **minor** bump rather than jumping to `1.0.0`; once a plugin reaches `1.0.0`, breaking changes use **major** bumps.
- **Top-level `version`** — the **project release version**, and the value used for git release tags (`vX.Y.Z`). It is a SemVer snapshot marker for the repo's whole observable surface: the **plugin set** (what's installed) plus the **`agentry.py`** install/generate CLI that downstream consumers pin and run. It is also emitted into Claude Code's `marketplace.json`, but neither tool keys plugin updates off it, so it is purely a human/release/downstream-pin marker.

Bump affected plugin versions in normal change PRs when plugin content should be delivered through plugin marketplaces. Bump the top-level project release version only in an explicit release-prep change, usually prepared with `prepare-release`; publish the merged release later with `publish-release`. Between project releases, plugin versions on the rolling marketplace/main channel may be ahead of the versions recorded in the latest project tag; the project tag remains the reproducible full-repo snapshot.

When preparing a project release, choose the top-level version by the **most-severe change** since the previous project tag — a rollup: the `max()` of every per-plugin bump and any catalog/CLI change included in the release, on the same SemVer scale. While the project itself is still `0.x`, breaking observable changes may use a **minor** project bump rather than jumping to `1.0.0`; once the project reaches `1.0.0`, breaking observable changes use **major** bumps.

| Bump | When the release's worst change is… |
| --- | --- |
| **patch** | only fixes — a plugin's per-plugin **patch**, or an `agentry.py` fix |
| **minor** | something **added** — a plugin's new component (per-plugin **minor**), a plugin **added**, or a new `agentry.py` capability (new flag, channel, or subcommand) |
| **major** | after `1.0.0`, something **removed, renamed, or breaking** — a plugin's per-plugin **major**, a plugin **removed or renamed**, or a breaking `agentry.py` CLI/behavior change |

At release time, roll up the plugin bumps already chosen in change PRs plus any catalog/CLI change since the previous project tag. Changes with no observable surface — tests, no-op refactors, dev docs (`AGENTS.md`), or CI tweaks — do not affect the project release bump.

Release workflow:

- Normal change PRs bump only affected per-plugin versions and regenerate packaging with `python3 scripts/agentry.py generate`.
- Release-prep PRs bump the top-level project `version`, update [`CHANGELOG.md`](./CHANGELOG.md) with `git-cliff --output CHANGELOG.md`, regenerate packaging if the manifest changed, and commit those release files.
- Release-prep commits such as `chore(release): prepare vX.Y.Z` are excluded from the generated changelog so release notes focus on user-facing plugin/tooling changes.
- After the release PR merges, publish the release with an annotated tag `vX.Y.Z` matching the top-level `version`. Pushing tags and creating hosted releases are shared actions that require confirmation.
