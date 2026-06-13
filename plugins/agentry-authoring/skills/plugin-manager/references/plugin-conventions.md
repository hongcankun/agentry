# Plugin & Marketplace Tool Conventions

Per-tool conventions for how plugins and marketplaces are structured. All tools share the same shape: a plugin is a directory of component folders (`skills/`, `agents/`, …) plus a manifest, and a marketplace is a `marketplace.json` catalog that lists plugins by `name` and `source`. The manifest file, catalog location, `owner`/author shape, and bundleable components differ per tool.

Always detect the target tool from existing plugin/marketplace files before writing, and follow whatever convention the project already uses. Plugin and marketplace names must be kebab-case (lowercase letters, numbers, hyphens), and plugin names must be unique within a marketplace.

> Across both tools below, the plugin format has **no rules component**. Rules are not delivered by installing a plugin; plan a separate install path for them. A rule is therefore associated with a plugin by reference (not nested inside it), which lets the same rule belong to more than one plugin — treat the rule↔plugin relationship as many-to-many.

## Claude Code

### Plugin layout

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json      # the ONLY file inside .claude-plugin/
├── skills/<name>/SKILL.md
├── agents/<name>.md
├── commands/<name>.md
├── hooks/hooks.json
└── .mcp.json
```

- Only `plugin.json` goes inside `.claude-plugin/`; all component directories live at the plugin root.
- A single-skill plugin may place `SKILL.md` at the plugin root with no manifest.

### plugin.json

- `name` (required) — kebab-case; namespaces the plugin's skills/commands.
- `description` (optional) — shown in the plugin manager.
- `version` (optional) — pin string; if omitted with git distribution, the commit SHA is used.
- `author` (optional) — object, e.g. `{ "name": "…", "email": "…" }`.
- `homepage`, `repository`, `license` (optional).

### marketplace.json

- Location: `.claude-plugin/marketplace.json` at the repo root.
- `name` (required) — kebab-case marketplace id.
- `owner` (required) — **object**: `{ "name": "…", "email": "…" }` (email optional).
- `plugins` (required) — array of entries.
- `metadata.pluginRoot` (optional) — base directory for relative `source` paths.
- Plugin entry: `name` + `source` (required); optional `description`, `version`, `category`, `keywords`, `author`.
- `source` forms: relative string starting with `./`; or object `{ "source": "github", "repo": "owner/repo", "ref": … }`, `url`, `git-subdir`, `npm`.

### Components

skills, slash commands, subagents, hooks, MCP servers, LSP servers, background monitors, `bin/` executables, default `settings.json`.

### Commands

```bash
claude plugin validate .                 # validate a plugin/marketplace dir
claude --plugin-dir ./my-plugin          # load a plugin without installing
/plugin marketplace add owner/repo       # add a marketplace
/plugin install plugin-name@marketplace  # install a plugin
```

## Trae CLI (coco)

### Plugin layout

```
my-plugin/
├── traecli.yaml         # main config (compat name: coco.yaml); optional
├── skills/<name>/SKILL.md
├── agents/<name>.md
├── commands/<name>.md
└── mcp.json             # also .mcp.json / mcp.yaml / .mcp.yaml
```

- There is **no per-plugin manifest file**: plugin metadata comes from the marketplace entry, and component directories are auto-detected.
- `traecli.yaml` is needed only for MCP servers, hooks, models, or tool-permission rules (`mcp_servers`, `hooks`, `models`, `allowed_tools`/`disallowed_tools`). A plugin of only skills/subagents/commands needs no `traecli.yaml`.
- Skills install under the `pluginname:skillname` namespace. Path variables in `traecli.yaml`: `${COCO_PLUGIN_ROOT}` (aliases `${CLAUDE_PLUGIN_ROOT}`, `${AGENT_PLUGIN_ROOT}`).

### marketplace.json

- Location: `.coco-plugin/marketplace.json`, `.trae-plugin/marketplace.json`, **or** `.claude-plugin/marketplace.json` (Trae reads the Claude location as a fallback).
- `name` (required) — kebab-case marketplace id.
- `owner` (required) — **string**, e.g. `"My Team"` (differs from Claude Code's object form).
- `plugins` (required) — array of entries.
- Plugin entry: `name` + `source` (required); optional `description`, `version`.
- `source` forms: relative string (e.g. `"./plugins/review"`); object `{ "url": …, "ref": … }`; object `{ "source": "git-subdir", "url": …, "path": … }`.

### Components

skills, slash commands, subagents, hooks, MCP servers, model config, tool-permission rules.

### Commands

```bash
traecli plugin validate --path ./my-plugin     # validate a local plugin
traecli plugin install ./my-plugin             # install (local/git/tar/marketplace)
traecli plugin marketplace add <source>        # add a marketplace
traecli plugin install name@marketplace        # install from a marketplace
```

## Versioning

A plugin's `version` is the user-facing update signal: both Claude Code and Trae deliver a plugin update only when its version string changes, and fall back to the git commit SHA when `version` is omitted. Follow these conventions:

- **Version each plugin independently.** Bump only the plugins whose content changed so unrelated plugins do not show spurious updates. Avoid a single shared version across all plugins.
- **A marketplace may carry its own catalog version** (informational); it does not drive per-plugin updates. Bump it for catalog-level changes such as adding or removing a plugin.
- **Use SemVer for plugin content:** *patch* = wording/non-behavioral fixes; *minor* = add a component or backward-compatible capability; *major* = remove/rename a component or change behavior in a breaking way.
- When a project derives packaging from a single source (e.g. a manifest), set the version there and regenerate, rather than editing generated manifests by hand.

## Notes

- The Claude and Trae specs overlap for skills/subagents/commands, so a plugin with only those components, plus a `.claude-plugin/marketplace.json`, can install in both tools. They diverge on the `owner` shape and on where MCP/hooks/model config lives (`plugin.json` vs `traecli.yaml`), so ship a native catalog per tool when targeting both.
- Conventions evolve; if a project's layout disagrees with this file, follow the project and flag the discrepancy. Verify field names and source forms against the target tool's own docs before committing to them.
