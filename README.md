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

Each plugin groups related extensions. Sources live under [`plugins/`](./plugins) (skills, subagents, and commands) and [`rules/`](./rules).

### [agentry-code-quality](./plugins/agentry-code-quality)

- **code-review** skill: Review code changes for correctness, readability, security, performance, and maintainability, then deliver prioritized, actionable feedback. Use when a user asks to review a diff, pull request, commit, branch, or file, or wants feedback on code they wrote or modified.
- **test-engineering** skill: Write, update, debug, and review automated test code by identifying behavior to cover, matching the project's test framework and style, adding focused assertions or fixtures, and validating the result. Use when the user asks to add tests, improve coverage, fix failing tests, review test code, or design a testing plan.
- **review-publishing** skill: Draft and publish existing review findings to PRs, MRs, or code review surfaces by mapping findings to inline or summary comments, deduplicating noise, and requiring explicit approval for remote mutations. Use when the user asks to publish, post, draft, or prepare review comments from existing findings.
- **review-code** command: Review local changes, a branch, commit range, pull request, merge request, diff, or file for code-quality issues.
- **improve-tests** command: Add, update, debug, review, or plan automated tests using the `test-engineering` skill.
- **quality-gate** command: Run a combined pre-merge gate covering code quality, security risk, and test adequacy.
- **publish-review** command: Publish existing review findings to a PR, MR, or code review surface after explicit approval.
- **code-reviewer** agent: Reviews code changes for correctness, security, readability, performance, and maintainability, then returns prioritized, actionable feedback. Use proactively after writing or modifying code, or when reviewing a diff, pull request, merge request, commit, branch, or file.
- **test-engineer** agent: Writes, updates, debugs, and reviews automated tests using the `test-engineering` skill. Use proactively for test coverage, failing or flaky tests, test-quality review, and code changes that need meaningful test coverage.
- **code-quality/code-review** rule: Policy for when code review is required, the gates a change must pass before merging, and approval criteria; defers the review procedure to the `code-review` skill.
- **code-quality/code-style** rule: Code style conventions covering core principles, formatting, naming, structure, language idioms, error handling, and comments that code should follow.
- **code-quality/testing** rule: Testing policy for adding or changing behavior, including meaningful coverage, determinism, and parallel safety.

### [agentry-security](./plugins/agentry-security)

- **security-audit** skill: Perform a focused security audit of code or a codebase — map the attack surface and trust boundaries, hunt for vulnerability classes (injection, auth flaws, SSRF, secrets, weak crypto, and more), rate each finding by likelihood and impact, and report exploit scenarios with concrete remediations. Use when a user asks for a security review, security audit, threat assessment, or vulnerability hunt of code they own or are authorized to test.
- **audit-security** command: Run a focused security audit of a repository, feature, boundary, or vulnerability class.
- **security-auditor** agent: Runs a threat-driven security audit in an isolated context, following the `security-audit` skill. Use proactively when a change touches security-sensitive code (auth, user input, queries, file/network access, cryptography, secrets, payments), or when asked for a security audit, threat assessment, or vulnerability hunt.
- **security/security-audit** rule: Policy for when a security audit is required, the gates a change must pass before merging, and approval criteria; defers the audit procedure to the `security-audit` skill.

### [agentry-git](./plugins/agentry-git)

- **git-workflow** skill: Apply git workflow best practices, including choosing a branching strategy, writing commits and pull requests, performing merges and rebases safely, resolving conflicts, and managing releases and tags.
- **conventional-commits** skill: Create commits that follow the Conventional Commits specification, including selecting appropriate types, writing clear descriptions, and validating commit messages.
- **prepare-commit** command: Inspect repository changes, stage a focused change set, and create a local Conventional Commit on an appropriate branch.
- **prepare-pr** command: Inspect branch state and draft or create a pull request with a Conventional Commit title after confirmation.
- **finish-pr** command: Clean up after a merged pull request by updating the base branch and deleting the local feature branch after confirmation.
- **prepare-release** command: Prepare a project release commit by updating version, generated metadata, and release notes.
- **publish-release** command: Publish a prepared release by verifying the merged release state, tagging it, and optionally creating hosted release notes.
- **vcs/conventional-commits** rule: Policy for when the Conventional Commits format applies and what a commit message must satisfy before committing; defers the message format and validation procedure to the `conventional-commits` skill.

### [agentry-authoring](./plugins/agentry-authoring)

- **skill-manager** skill: Create, update, or review Agent Skills that follow the open Agent Skills convention, including planning skill scope, writing SKILL.md metadata and instructions, organizing scripts references and assets, and validating the final package.
- **subagent-manager** skill: Create, update, or review AI subagents across tools like Claude Code, Cursor, OpenCode, Trae CLI, and Codex, including defining the agent's role and trigger conditions, writing a focused system prompt, scoping tools and model, choosing the right scope, and reviewing agents for clarity and overlap.
- **command-manager** skill: Create, update, or review AI agent commands across tools like Claude Code, Trae CLI, Cursor, and Codex, including defining command purpose, arguments, prompt body, file placement, metadata, and validation.
- **rule-manager** skill: Create, update, or review agent rules that guide AI agent behavior, at project scope or user/global scope, including defining scope and triggers, writing clear and actionable directives, organizing rule files, and reviewing rules for clarity and conflicts.
- **prompt-template-manager** skill: Create, update, or review reusable prompt templates for AI chat or AI agents, including defining the template purpose, structure, variables, examples, and validation.
- **plugin-manager** skill: Create, update, or review plugins and plugin marketplaces for AI coding tools like Claude Code and Trae CLI, including defining a plugin's components, writing the manifest, organizing the layout, assembling a marketplace catalog, and reviewing for validity and overlap.

### [agentry-docs](./plugins/agentry-docs)

- **readme-manager** skill: Create or update README.md files in git repositories, including analyzing the repo structure, identifying key information, and following standard README conventions.
- **update-readme** command: Create or update a repository README with accurate setup, usage, contribution, and license details.

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
