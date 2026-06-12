# Plugin & Marketplace Review Checklist

Use this checklist when reviewing a plugin or marketplace definition.

## Plugin manifest

- `name` is present, unique, and in kebab-case.
- `description` states what the plugin bundles and is meaningful in a plugin manager.
- `version` is present when updates should be pinned; omitted only when tracking the latest commit intentionally.
- `version` is bumped (SemVer) when the plugin's content changed, and versioned independently of other plugins.
- `author`/`owner` uses the shape the **target tool** expects (object for Claude Code, string for Trae marketplaces).
- Only fields valid for the target tool are used; no fields borrowed from a different tool's spec.

## Layout

- Component directories (`skills/`, `agents/`, `commands/`, …) are at the plugin root.
- For Claude Code, only `plugin.json` lives inside `.claude-plugin/`.
- For Trae, `traecli.yaml` exists only if the plugin has MCP servers, hooks, models, or tool-permissions.
- Each component is well-formed (e.g. `skills/<name>/SKILL.md` present; subagent files have valid frontmatter).
- The tool's validator (`claude plugin validate` / `traecli plugin validate`) recognizes every intended component.

## Theme and scope

- The plugin's components share a coherent theme and are used together.
- The plugin does not bundle unrelated components that belong in a separate plugin.
- Rules the plugin relates to have a documented install path, since the plugin format does not deliver rules.

## Marketplace catalog

- The catalog is at the correct location for the target tool.
- `name` is kebab-case; `owner` uses the tool's expected shape.
- Every plugin entry has a unique `name` and a resolvable `source`.
- Relative `source` paths point at real in-repo plugin directories; no path traversal.
- External `source` objects use the tool's valid form (`github`/`url`/`git-subdir`/`npm` as supported).

## Consistency

- Plugin names do not collide within the marketplace or with reserved names.
- Descriptions and versions agree between the plugin manifest and the marketplace entry (or are generated from one source).
- Terminology and naming match other plugins in the project.

## Value

- The plugin adds a distinct, installable capability rather than duplicating another plugin.
- No dead references to removed components, paths, or sources.

## Final check

- The definition reflects the intended plugin set and sources.
- Updates preserved unrelated existing entries and fields.
- The plugin/marketplace validates and is ready to publish or install.
