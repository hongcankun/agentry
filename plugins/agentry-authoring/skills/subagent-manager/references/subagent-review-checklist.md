# Subagent Review Checklist

Use this checklist when reviewing an AI subagent definition file.

## Metadata

- `name` is present, unique, and in kebab-case (or correctly derived from the filename for tools that do so).
- `name` reads as a noun naming the role/doer (e.g. `code-reviewer`, `test-runner`), not a verb phrase naming the action (`code-review`).
- `description` states both what the subagent does and **when to invoke it**.
- Trigger phrases in the description are concrete enough to drive delegation.
- "Use PROACTIVELY" / "MUST BE USED" (Cursor: "use proactively") is present only when automatic invocation is intended.
- Only frontmatter fields valid for the **target tool** are used (see `tool-conventions.md`); no fields borrowed from a different tool.
- Tool-scoping and model fields, if set, are valid for that tool (e.g. `tools`/`disallowed_tools`, `readonly`, `permission`, `model`).

## Focus

- The subagent has a single, clear responsibility.
- The system prompt defines role, responsibilities, workflow, and constraints.
- There is an explicit output contract describing what the agent returns.
- The prompt is self-contained and does not rely on the main conversation's hidden context.
- Any skill the subagent's procedure depends on is preloaded (e.g. a `skills` field), not assumed to carry over from the main session; the prompt still stands alone if that skill is unavailable.

## Scope and access

- Tool access is the minimum the job needs; sensitive jobs are restricted (e.g. read-only reviewers have no write/execute tools).
- The model tier fits the task (cheap/fast for mechanical work, stronger for deep reasoning).
- The file is in the correct directory for the target tool and scope (project repo `agents/` vs. user home-config `agents/`).

## Consistency

- The subagent does not overlap or compete with an existing subagent's trigger.
- It composes cleanly with related subagents rather than duplicating them.
- Terminology and format match other subagents in the project.

## Value

- The subagent adds a capability the main agent does not already cover well.
- No dead references to removed tools, paths, or workflows.
- The prompt is focused enough to produce reliable behavior.

## Final check

- The definition reflects the intended role and triggers.
- Updates preserved unrelated existing content.
- The file is portable and ready for the agent to use.
