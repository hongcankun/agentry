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
/plugin install agentry-git@agentry
/plugin install agentry-authoring@agentry
/plugin install agentry-docs@agentry
```

Update later with `/plugin marketplace update agentry`.

### Trae

```
traecli plugin marketplace add hongcankun/agentry
traecli plugin install agentry-code-quality@agentry
traecli plugin install agentry-git@agentry
traecli plugin install agentry-authoring@agentry
traecli plugin install agentry-docs@agentry
```

Update later with `traecli plugin marketplace update agentry` (or run the equivalents as `/plugin ...` inside a session).

### Installing rules

Neither the Claude Code nor the Trae plugin format has a "rules" component, so rules are not delivered by installing a plugin. After installing a plugin that has associated rules (e.g. `agentry-code-quality`), add them with the install script:

```
# Install the rules for a plugin, into the tool's project rules dir
python3 scripts/install.py --tool claude --plugin agentry-code-quality
python3 scripts/install.py --tool trae --plugin agentry-code-quality
```

The script reads `agentry.json` (so rules map to the same plugins as the marketplace) and writes to the tool's rules directory (`.claude/rules/`, `.trae/rules/`). It can also install skills and subagents directly from a checkout — useful for development or tools without marketplace support; see `python3 scripts/install.py --help`.

Flags: `--tool {claude,trae}`, `--plugin`, `--component {skills,agents,rules}` (repeatable), `--scope {project,global}`, `--project-dir`, `--dry-run`, `--force`.

## Plugins

Each plugin groups related extensions. Sources live under [`plugins/`](./plugins) (skills and subagents) and [`rules/`](./rules).

### [agentry-code-quality](./plugins/agentry-code-quality)

- **code-review** skill: Review code changes for correctness, readability, security, performance, and maintainability, then deliver prioritized, actionable feedback. Use when a user asks to review a diff, pull request, commit, branch, or file, or wants feedback on code they wrote or modified.
- **code-reviewer** agent: Reviews code changes for correctness, security, readability, performance, and maintainability, then returns prioritized, actionable feedback. Use proactively after writing or modifying code, or when reviewing a diff, pull request, merge request, commit, branch, or file.
- **code-quality/code-review** rule: Policy for when code review is required, the gates a change must pass before merging, and approval criteria; defers the review procedure to the `code-review` skill.

### [agentry-git](./plugins/agentry-git)

- **git-workflow** skill: Apply git workflow best practices, including choosing a branching strategy, writing commits and pull requests, performing merges and rebases safely, resolving conflicts, and managing releases and tags.
- **conventional-commits** skill: Create commits that follow the Conventional Commits specification, including selecting appropriate types, writing clear descriptions, and validating commit messages.

### [agentry-authoring](./plugins/agentry-authoring)

- **agent-skill-creator** skill: Create and refine Agent Skills that follow the open Agent Skills convention, including planning skill scope, writing SKILL.md metadata and instructions, organizing scripts references and assets, and validating the final package.
- **subagent-manager** skill: Create, update, or review AI subagents across tools like Claude Code, Cursor, OpenCode, Trae CLI, and Codex, including defining the agent's role and trigger conditions, writing a focused system prompt, scoping tools and model, choosing the right scope, and reviewing agents for clarity and overlap.
- **rule-manager** skill: Create, update, or review agent rules that guide AI agent behavior, at project scope or user/global scope, including defining scope and triggers, writing clear and actionable directives, organizing rule files, and reviewing rules for clarity and conflicts.
- **prompt-template-creator** skill: Create and refine reusable prompt templates for AI chat or AI agents, including defining the template purpose, structure, variables, examples, and validation.

### [agentry-docs](./plugins/agentry-docs)

- **readme-manager** skill: Create or update README.md files in git repositories, including analyzing the repo structure, identifying key information, and following standard README conventions.

## Repository layout

- [`agentry.json`](./agentry.json) — canonical, tool-agnostic manifest. **Edit this**, then regenerate derived files.
- [`plugins/`](./plugins) — each plugin's skills (`skills/<name>/SKILL.md`) and subagents (`agents/<name>.md`).
- [`rules/`](./rules) — tool-agnostic rules, organized by topic; associated with plugins via the manifest.
- [`scripts/install.py`](./scripts/install.py) — install a plugin's rules (and optionally skills/subagents) into a tool's directories.
- [`scripts/generate_claude.py`](./scripts/generate_claude.py) — regenerate Claude Code packaging from the manifest.
- [`scripts/generate_trae.py`](./scripts/generate_trae.py) — regenerate Trae packaging from the manifest.

### Generated files

Per-tool packaging is **generated** from `agentry.json` — do not edit it by hand:

- Claude Code: `.claude-plugin/marketplace.json` and each `plugins/*/.claude-plugin/plugin.json`.
- Trae: `.trae-plugin/marketplace.json`.

```
python3 scripts/generate_claude.py          # regenerate Claude Code packaging
python3 scripts/generate_trae.py            # regenerate Trae packaging
python3 scripts/generate_claude.py --check  # verify up to date (for CI); same flag on generate_trae.py
```

Claude Code and Trae have separate plugin specs that happen to overlap for our content: Trae can read Claude's catalog as a fallback, but its own schema differs (e.g. `owner` is a string, not an object), so we ship a native `.trae-plugin/marketplace.json`. Plugin packages also differ — Claude uses a per-plugin `plugin.json`, Trae auto-detects component dirs and uses `traecli.yaml` only for MCP servers, hooks, models, or tool-permissions. Agentry's plugins currently contain only skills and subagents, so no per-plugin manifest is required on Trae. If a plugin later adds MCP/hooks/models, `generate_trae.py` would need to emit a `traecli.yaml` for it.

Adding support for another tool means adding its targets to `scripts/install.py` and, if it has a package format, a generator alongside the existing ones — without changing the canonical manifest.
