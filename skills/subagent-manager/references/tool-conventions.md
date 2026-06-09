# Subagent Tool Conventions

Per-tool conventions for where subagents live and which frontmatter fields they support. All tools share the same shape: a Markdown file with YAML frontmatter (metadata) followed by the system-prompt body, with `name` and `description` as the common core. Project scope takes precedence over user scope on name conflicts.

Always detect the target tool from the existing agent directories or config before writing, and follow whatever convention the project already uses.

## Claude Code

- **Project**: `.claude/agents/<name>.md`
- **User/global**: `~/.claude/agents/<name>.md`
- **Frontmatter**:
  - `name` (required) — kebab-case identifier.
  - `description` (required) — purpose + when to invoke; add "Use PROACTIVELY" / "MUST BE USED" for automatic delegation.
  - `tools` (optional) — comma-separated allowlist. Omit to inherit all tools.
  - `model` (optional) — alias (`sonnet`, `opus`, `haiku`) or `inherit`. Omit for default.

## Cursor

- **Project**: `.cursor/agents/<name>.md` (also reads `.claude/agents/` and `.codex/agents/` for compatibility; `.cursor/` wins on conflicts)
- **User/global**: `~/.cursor/agents/<name>.md` (plus `~/.claude/`, `~/.codex/` compat)
- **Frontmatter**:
  - `name` (optional) — defaults to filename; lowercase + hyphens.
  - `description` (optional but recommended) — drives delegation; include "use proactively" / "always use for" to encourage automatic use.
  - `model` (optional) — `inherit` (default) or a specific model ID (e.g. `composer-2`, `gpt-5.5`).
  - `readonly` (optional, bool) — `true` restricts write/state-changing actions.
  - `is_background` (optional, bool) — `true` runs in background without blocking the parent.
- **Invocation**: `/name` or natural mention. Built-in subagents: Explore, Bash, Browser.

## OpenCode

- **Project**: `.opencode/agents/<name>.md` (or JSON under the `agent` key in `opencode.json`)
- **User/global**: `~/.config/opencode/agents/<name>.md`
- **Frontmatter**:
  - `description` (required) — purpose + when to use.
  - `mode` (optional) — `primary`, `subagent`, or `all` (default `all`).
  - `model` (optional) — `provider/model-id`.
  - `temperature` / `top_p` (optional) — sampling controls.
  - `permission` (optional) — map of `edit`, `bash`, `read`, `task`, etc. to `allow`/`ask`/`deny`.
  - `hidden` (optional, bool) — hide a `subagent`-mode agent from the `@` menu.
  - `disable`, `steps`, `color`, `prompt` (`{file:...}`) and other model options are passed through.
  - The agent name comes from the filename.

## Trae CLI (coco)

- **Project**: `.trae/agents/<name>.md` (read-only compat: `.coco/agents/`, `.agents/agents/`)
- **User/global**: `~/.trae/agents/<name>.md`
- **Priority**: project > user > built-in > plugin.
- **Frontmatter**:
  - `name` (required) — unique identifier.
  - `description` (required) — purpose + when to delegate.
  - `tools` (optional) — comma-separated allowlist (e.g. `Read,Write,Edit,Grep,Glob,Bash`); MCP tools as `mcp__<server>__<tool>`. Omit to inherit all.
  - `disallowed_tools` (optional) — remove specific tools from the inherited/allowed set.
  - `model` (optional) — model id; must be available in the model config.
  - `isolation` (optional) — `worktree` to run in an isolated git worktree.
  - `permission_mode` (optional) — e.g. `bypass_permissions`.
  - `skills` (optional) — comma-separated skill IDs to inject into the system prompt.
- **Create helper**: `/agent-new` scaffolds a draft into `.trae/agents/`. Built-in subagents: general-purpose, Explore, Plan. Invocation: `@name`.

## Codex

- **Project**: `.codex/agents/<name>.md`
- **User/global**: `~/.codex/agents/<name>.md`
- **Frontmatter**: Claude-compatible Markdown (`name`, `description`, plus tool/model fields as supported). Cursor reads this location for compatibility.

## Notes

- When a project already uses one tool's directory, do not introduce another tool's format alongside it unless the user explicitly wants multi-tool support.
- Verify model aliases/IDs and tool names against the target tool's own configuration before committing to them.
- Conventions evolve; if a project's layout disagrees with this file, follow the project and flag the discrepancy.
