---
# Subagent definition. Frontmatter must be the FIRST thing in the file.
# Save to the target tool's agents/ dir (see references/tool-conventions.md), e.g.:
#   .claude/agents/<name>.md | .cursor/agents/<name>.md | .opencode/agents/<name>.md
#   .trae/agents/<name>.md   | .codex/agents/<name>.md   (project scope; ~/... for user scope)
#
# Common fields (every tool): name + description.
name: example-agent
# Describe what the agent does AND when to invoke it. This drives automatic delegation.
# Add "Use PROACTIVELY" / "MUST BE USED" (Cursor: "use proactively") to encourage auto-use.
description: One-line role plus explicit trigger conditions. Use PROACTIVELY when <situation>.
#
# Tool-specific optional fields — keep only the ones your target tool supports:
#   Claude Code: tools (comma list), model (sonnet|opus|haiku|inherit)
#   Cursor:      model (inherit|<id>), readonly (bool), is_background (bool)
#   OpenCode:    mode (primary|subagent|all), model (provider/id), temperature, permission
#   Trae CLI:    tools, disallowed_tools, model, isolation (worktree), permission_mode, skills
#   Codex:       Claude-compatible fields
tools: Read, Grep, Glob
model: inherit
---

You are a [role] specializing in [domain].

## Responsibilities

- [Concrete task this agent owns.]
- [Another task in scope.]

## Approach

1. [First step the agent should take.]
2. [Next step.]
3. [Final step before reporting back.]

## Constraints

- [What the agent must not do.]
- [Any safety or quality rule.]

## Output

Return [the exact shape of the result, e.g. a findings list with severity, a summary, or a patch]. The main agent only sees your final message, so make it self-contained and actionable.
