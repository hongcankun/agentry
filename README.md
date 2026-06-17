# Agentry

A collection of reusable extensions for AI coding agents — skills, subagents, and rules — following open agent conventions. The extensions are tool-agnostic and grouped into plugins; each AI tool's packaging is generated from a single canonical manifest, so no tool is privileged.

- **Canonical source:** [`agentry.json`](./agentry.json) defines every skill, subagent, and rule and how they group into plugins.
- **Per-tool packaging is derived from it** — each tool's marketplace files are generated from the manifest, and an install script copies a plugin's rules (and optionally other components) into a tool's directories.

## Install

Both Claude Code and Trae install Agentry as a plugin marketplace. Each tool reads its own catalog — generated from the same manifest — so the plugin set is identical.

### Claude Code

```
/plugin marketplace add hongcankun/agentry
/plugin install agentry-code-quality@agentry
/plugin install agentry-security@agentry
/plugin install agentry-git@agentry
/plugin install agentry-authoring@agentry
/plugin install agentry-docs@agentry
```

Update later with `/plugin marketplace update agentry`.

### Trae

```
traecli plugin marketplace add hongcankun/agentry
traecli plugin install agentry-code-quality@agentry
traecli plugin install agentry-security@agentry
traecli plugin install agentry-git@agentry
traecli plugin install agentry-authoring@agentry
traecli plugin install agentry-docs@agentry
```

Update later with `traecli plugin marketplace update agentry`.

### The install script

`scripts/agentry.py` complements the marketplace. It reads `agentry.json` (so everything maps to the same plugins) and delivers a plugin's pieces through one of **two channels**:

- **marketplace** — orchestrates the tool's own CLI (e.g. `traecli` / `claude`) to add the marketplace and install or remove the selected plugins. The marketplace channel is **user-scoped**, so it forces `--global` and cannot be combined with `--component`; it is the default for a `--global` run.
- **checkout** — copies components straight from this checkout into the tool's directories and never touches the marketplace. It is the default at project scope. Passing `--component {rules,skills,agents}` (repeatable) implicitly selects it; `--source checkout` forces it.

Rules are **never delivered by a plugin** (neither Claude Code nor Trae ship rules in their plugin format), so the script always copies them regardless of channel.

```
# Marketplace channel (user scope): add the marketplace + install the plugin, then copy rules
python3 scripts/agentry.py install --tool trae --global --plugin agentry-code-quality --yes

# Checkout channel (project scope): copy a plugin's rules into .trae/rules or .claude/rules
python3 scripts/agentry.py install --tool claude --plugin agentry-code-quality

# Checkout channel: copy skills and subagents from this checkout (for development, or tools
# without marketplace support)
python3 scripts/agentry.py install --tool trae --component skills --component agents
```

A bare `install` run is **interactive**: it reports each item's state (missing / synced / stale vs the canonical source), then prompts on a TTY for any omitted selection (`--tool`, `--plugin`, `--component`s, `--symlink`) and before each action, including marketplace/plugin CLI calls. Pass `--defaults` to accept the default selections without asking, or `--yes` to auto-confirm every action.

Non-interactive (CI, piped) behavior is conservative: install installs missing files and skips stale ones; uninstall removes owned files only. Both skip the marketplace/plugin phase unless `--yes` is given. Use `--dry-run` to preview either channel without writing anything.

Two companion subcommands round out the lifecycle:

- `status` — report-only; writes nothing. Exits 1 if any file is missing or stale (handy for CI). Also reports marketplace and per-plugin install state read-only (at any scope — plugins are user-scoped), which is informational and never affects the exit code.
- `uninstall` — remove components this repo installed (owned copies or symlinks). Keeps items that have drifted from the source unless `--force` is passed. On the marketplace channel it uninstalls the plugin via the tool CLI and removes the marketplace only when no Agentry plugin remains (to keep it otherwise, or force-remove it, use the tool's own CLI).

Add `--symlink` to link components back to the checkout instead of copying, so they track the source with no drift (the link is relative; not portable to Windows checkouts):

```
python3 scripts/agentry.py install --tool trae --plugin agentry-code-quality --symlink
```

Common flags (any omitted selection is prompted interactively, or takes the noted default): `--tool {claude,trae}` (required non-interactively), `--plugin` (default: all plugins), `--source {marketplace,checkout}` (default: marketplace for `--global` runs without `--component`, otherwise checkout), `--component {skills,agents,rules}` (repeatable; selects checkout; default: `rules`), `--symlink` (install only; default: copy), `--global` (default: project scope; forced by the marketplace channel), `--project-dir`, `--yes`/`-y` (auto-confirm actions), `--defaults` (accept default selections without prompting), `--color {auto,always,never}`, `--dry-run`, `--force`.

## Plugins

Each plugin groups related extensions. Sources live under [`plugins/`](./plugins) (skills and subagents) and [`rules/`](./rules).

### [agentry-code-quality](./plugins/agentry-code-quality)

- **code-review** skill: Review code changes for correctness, readability, security, performance, and maintainability, then deliver prioritized, actionable feedback. Use when a user asks to review a diff, pull request, commit, branch, or file, or wants feedback on code they wrote or modified.
- **code-reviewer** agent: Reviews code changes for correctness, security, readability, performance, and maintainability, then returns prioritized, actionable feedback. Use proactively after writing or modifying code, or when reviewing a diff, pull request, merge request, commit, branch, or file.
- **code-quality/code-review** rule: Policy for when code review is required, the gates a change must pass before merging, and approval criteria; defers the review procedure to the `code-review` skill.
- **code-quality/code-style** rule: Code style conventions covering core principles, formatting, naming, structure, language idioms, error handling, and comments that code should follow.

### [agentry-security](./plugins/agentry-security)

- **security-audit** skill: Perform a focused security audit of code or a codebase — map the attack surface and trust boundaries, hunt for vulnerability classes (injection, auth flaws, SSRF, secrets, weak crypto, and more), rate each finding by likelihood and impact, and report exploit scenarios with concrete remediations. Use when a user asks for a security review, security audit, threat assessment, or vulnerability hunt of code they own or are authorized to test.
- **security-auditor** agent: Runs a threat-driven security audit in an isolated context, following the `security-audit` skill. Use proactively when a change touches security-sensitive code (auth, user input, queries, file/network access, cryptography, secrets, payments), or when asked for a security audit, threat assessment, or vulnerability hunt.
- **security/security-audit** rule: Policy for when a security audit is required, the gates a change must pass before merging, and approval criteria; defers the audit procedure to the `security-audit` skill.

### [agentry-git](./plugins/agentry-git)

- **git-workflow** skill: Apply git workflow best practices, including choosing a branching strategy, writing commits and pull requests, performing merges and rebases safely, resolving conflicts, and managing releases and tags.
- **conventional-commits** skill: Create commits that follow the Conventional Commits specification, including selecting appropriate types, writing clear descriptions, and validating commit messages.
- **vcs/conventional-commits** rule: Policy for when the Conventional Commits format applies and what a commit message must satisfy before committing; defers the message format and validation procedure to the `conventional-commits` skill.

### [agentry-authoring](./plugins/agentry-authoring)

- **skill-manager** skill: Create, update, or review Agent Skills that follow the open Agent Skills convention, including planning skill scope, writing SKILL.md metadata and instructions, organizing scripts references and assets, and validating the final package.
- **subagent-manager** skill: Create, update, or review AI subagents across tools like Claude Code, Cursor, OpenCode, Trae CLI, and Codex, including defining the agent's role and trigger conditions, writing a focused system prompt, scoping tools and model, choosing the right scope, and reviewing agents for clarity and overlap.
- **rule-manager** skill: Create, update, or review agent rules that guide AI agent behavior, at project scope or user/global scope, including defining scope and triggers, writing clear and actionable directives, organizing rule files, and reviewing rules for clarity and conflicts.
- **prompt-template-manager** skill: Create, update, or review reusable prompt templates for AI chat or AI agents, including defining the template purpose, structure, variables, examples, and validation.
- **plugin-manager** skill: Create, update, or review plugins and plugin marketplaces for AI coding tools like Claude Code and Trae CLI, including defining a plugin's components, writing the manifest, organizing the layout, assembling a marketplace catalog, and reviewing for validity and overlap.

### [agentry-docs](./plugins/agentry-docs)

- **readme-manager** skill: Create or update README.md files in git repositories, including analyzing the repo structure, identifying key information, and following standard README conventions.

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the contribution workflow — editing the canonical manifest, regenerating packaging, versioning, and PR expectations.

## Repository layout

- [`agentry.json`](./agentry.json) — canonical, tool-agnostic manifest. **Edit this**, then regenerate derived files.
- [`plugins/`](./plugins) — each plugin's skills (`skills/<name>/SKILL.md`) and subagents (`agents/<name>.md`).
- [`rules/`](./rules) — tool-agnostic rules, organized by topic; associated with plugins via the manifest.
- [`scripts/agentry.py`](./scripts/agentry.py) — maintenance CLI: `install`/`status`/`uninstall` a plugin's components into a tool's directories, and `generate` per-tool packaging from the manifest.
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

Claude Code and Trae have separate plugin specs that happen to overlap for our content: Trae can read Claude's catalog as a fallback, but its own schema differs (e.g. `owner` is a string, not an object), so we ship a native `.trae-plugin/marketplace.json`. Plugin packages also differ — Claude uses a per-plugin `plugin.json`, Trae auto-detects component dirs and uses `traecli.yaml` only for MCP servers, hooks, models, or tool-permissions. Agentry's plugins currently contain only skills and subagents, so no per-plugin manifest is required on Trae. If a plugin later adds MCP/hooks/models, `agentry.py generate` would need to emit a `traecli.yaml` for it.

Adding support for another tool means adding its targets to `scripts/agentry.py` and, if it has a package format, a generate target alongside the existing ones — without changing the canonical manifest.

## Versioning

Versions live in `agentry.json` and propagate to the generated packaging. Two levels:

- **Per-plugin `version`** (one per entry in `plugins`) — the meaningful, user-facing version. Both Claude Code and Trae use it to deliver updates: a plugin updates for users only when its version string changes (omit it and the tool falls back to the git commit SHA). Version each plugin **independently** — bump only the plugins whose content actually changed, so unrelated plugins don't show spurious updates.
- **Top-level `version`** — an informational version for the marketplace catalog as a whole. It is emitted into Claude Code's `marketplace.json`; neither tool keys plugin updates off it. Bump it for catalog-level changes (adding/removing a plugin, or a coordinated release).

Use [SemVer](https://semver.org) for a plugin's content:

- **patch** — wording fixes, clarifications, or non-behavioral edits to existing components.
- **minor** — add a new skill, subagent, or rule to the plugin, or a backward-compatible capability.
- **major** — remove or rename a component, or otherwise change behavior in a breaking way.

Bump versions by editing `agentry.json`, then regenerate the packaging (`python3 scripts/agentry.py generate`).
