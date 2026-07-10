---
name: plugin-authoring
description: Create, update, or review plugins and plugin marketplaces for AI coding tools like Claude Code and Trae CLI. A plugin bundles components such as skills, subagents, commands, hooks, and MCP servers; a marketplace is a catalog that distributes plugins. Use when a user asks to create a new plugin or marketplace, edit an existing one, or review plugin files such as .claude-plugin/plugin.json, .claude-plugin/marketplace.json, .trae-plugin/marketplace.json, or traecli.toml.
---

# Plugin Authoring

Create, update, or review **plugins** and **plugin marketplaces** for AI coding tools. A plugin is an installable package that bundles components — skills, subagents, slash commands, hooks, MCP servers, and (tool-dependent) model and tool-permission config — so they can be shared and versioned. A marketplace is a catalog that distributes plugins. Across tools (Claude Code, Trae CLI, and others), a plugin is a directory of component folders plus a manifest, and a marketplace is a `marketplace.json` catalog; the manifest file, catalog location, and a few fields differ per tool.

Follow these principles:
- Give each plugin a coherent theme; bundle components that are installed and used together.
- Keep the manifest minimal and accurate: name, description, and version are what users see and pin to.
- Put component directories (`skills/`, `agents/`, …) at the plugin root; keep only the manifest inside the tool's `.<tool>-plugin/` directory.
- Note that plugins typically do not deliver **rules**; plan how rules ship separately if the plugin has them.
- In a marketplace, give every plugin a unique kebab-case name and a clear description, and validate before publishing.

## When to use

Use this skill when the task is to:
- create a new plugin from a set of skills, subagents, or other components;
- create or extend a marketplace catalog that distributes plugins;
- update an existing plugin's manifest, components, or version, or a marketplace's entries;
- review plugin or marketplace files for validity, structure, scope, and overlap.

## Expected input

Provide as much of the following as available:
- which AI tool the plugin targets (Claude Code, Trae CLI, ...);
- the components the plugin should bundle (skills, subagents, commands, hooks, MCP servers, models);
- the plugin's name, description, and intended version;
- whether the task concerns a single **plugin**, a **marketplace** catalog, or both;
- the marketplace's name, owner, and how each plugin is sourced (in-repo path vs. external git);
- existing plugin or marketplace files that should be respected or updated;
- whether the task is **create**, **update**, or **review**.

If details are missing, infer reasonable defaults from the request and the repo: detect the target tool from existing plugin/marketplace files, prefer in-repo relative sources for plugins kept in the same repo, omit `version` only when intentionally tracking the latest commit, and keep each plugin's theme focused.

## Plugin and marketplace conventions

A plugin is a directory: component folders at the root plus a manifest in a tool-specific `.<tool>-plugin/` directory (Claude Code) or a `traecli.toml` main config (Trae, only when package-level MCP/hooks/models/tool permissions are needed). A marketplace is a `marketplace.json` catalog listing plugins by name and source. Two things are common across tools:

- **Plugin name** — unique, kebab-case; it namespaces the plugin's skills and commands.
- **Marketplace entry** — at minimum a `name` and a `source` telling the tool where to fetch the plugin.

Beyond these, the **manifest file**, the **catalog location**, the **`owner` shape**, and the **set of bundleable components** differ per tool. Notably, neither Claude Code's nor Trae's plugin format has a **rules** component, so rules are not delivered by installing a plugin.

Before writing, **detect the target tool and its convention** by checking which plugin or marketplace files already exist, then follow them. See `references/plugin-conventions.md` for the exact manifest, catalog location, and component set for each tool. Do not introduce a new location or format when one already exists.

## Workflow

### 1. Determine the tool, task type, and target

Detect the **target tool** (Claude Code, Trae CLI, ...) from existing plugin or marketplace files, or ask if ambiguous. Decide whether you are **creating**, **updating**, or **reviewing**, and whether the target is a **plugin**, a **marketplace**, or both. Locate the existing files first, using `references/plugin-conventions.md`.

### 2. Define the plugin boundary

For a plugin, clarify:
- the theme that ties its components together;
- which components it bundles and which it deliberately leaves out;
- whether it has associated rules and, if so, how they will be installed (since the plugin format will not deliver them).

If the components do not share a theme, split them into separate plugins.

### 3. Write or update the manifest and layout

- Lay out component directories (`skills/<name>/SKILL.md`, `agents/<name>.md`, ...) at the plugin root; place only the manifest inside the tool's plugin-config directory.
- Write the manifest fields using the **target tool's** schema from `references/plugin-conventions.md`: name, description, version, and author/owner in the shape that tool expects.
- Set `version` per the versioning conventions in `references/plugin-conventions.md`: version each plugin independently and bump it (SemVer) only when that plugin's content changes.
- Use `assets/plugin-manifest-template.json` (single plugin) or `assets/marketplace-template.json` (catalog) as a starting structure, adapting fields to the target tool.
- When updating, read the existing file first and preserve unrelated entries and fields.

### 4. Assemble or update the marketplace catalog

- Give the marketplace a kebab-case `name` and an `owner` in the tool's expected shape (object for Claude Code, string for Trae).
- Add each plugin with a unique `name`, a `description`, an optional `version`, and a `source` (relative `./path` for in-repo plugins, or a git object for external ones).
- Keep plugin names unique within the catalog and avoid path traversal in sources.

### 5. Review and validate

Check the result against `references/plugin-review-checklist.md`, then run the tool's own validator when available:

```bash
# Claude Code
claude plugin validate .
# Trae CLI
traecli plugin validate --path ./<plugin-dir>
```

At minimum confirm:
- the manifest is valid and the plugin name is unique and kebab-case;
- component directories are at the plugin root and recognized by the tool's validator;
- the marketplace catalog is at the correct location with each `source` resolvable;
- the `owner`/author shape matches the target tool;
- any rules the plugin relates to have a documented install path, since the plugin will not ship them.

## References

Read these files when needed:
- `references/plugin-conventions.md` — per-tool plugin manifest, marketplace catalog location and schema, bundleable components, and install/validate commands for Claude Code and Trae CLI.
- `references/plugin-review-checklist.md` — checklist for reviewing plugin and marketplace files.
- `assets/plugin-manifest-template.json` — starting template for a single plugin manifest.
- `assets/marketplace-template.json` — starting template for a marketplace catalog.
