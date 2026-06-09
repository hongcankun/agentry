---
name: subagent-manager
description: Create, update, or review AI subagents (specialized agents an AI coding tool delegates tasks to) across tools like Claude Code, Cursor, OpenCode, Trae CLI, and Codex, including defining the agent's role and trigger conditions, writing a focused system prompt, scoping tools and model, choosing the right scope, and reviewing agents for clarity and overlap. Use when a user asks to create a new subagent, edit an existing one, or review agent definition files such as .claude/agents/, .cursor/agents/, .opencode/agents/, .trae/agents/, or .codex/agents/.
---

# Subagent Manager

Create, update, or review **AI subagents**: specialized agents an AI coding tool can delegate a task to, each with its own focused system prompt, tool access, and isolated context window. Across tools (Claude Code, Cursor, OpenCode, Trae CLI, Codex, and others), a subagent is a Markdown file with YAML frontmatter; the frontmatter holds metadata and the body is the agent's system prompt. The directory and a few frontmatter fields differ per tool.

Follow these principles:
- Give each subagent one clear, narrow responsibility, not a grab-bag of duties.
- Write a `description` that tells the main agent exactly when to delegate to this subagent.
- Keep the system prompt focused: define the role, the workflow, and the output contract.
- Grant the minimum tools the subagent needs; restrict tools and model only when it helps.
- Avoid creating overlapping subagents that compete for the same trigger.

## When to use

Use this skill when the task is to:
- create a new subagent from a request, role, or repeated workflow;
- update or refine an existing subagent's description, prompt, tools, or model;
- review subagent definition files for clarity, scope, tool access, and overlap.

## Expected input

Provide as much of the following as available:
- which AI tool the subagent targets (Claude Code, Cursor, OpenCode, Trae CLI, Codex, ...);
- the job the subagent should own and the situations that should trigger it;
- the workflow, expertise, or constraints the subagent must follow;
- which tools and model the subagent should have access to;
- whether the subagent is **project-scoped** (repo) or **user/global-scoped** (home config dir);
- existing subagent files that should be respected or updated;
- whether the task is **create**, **update**, or **review**.

If details are missing, infer reasonable defaults from the request and the project: detect the target tool from existing agent directories or config, default to project scope unless the user asks for a personal/global agent, inherit all tools unless restriction is clearly beneficial, and keep the agent focused.

## Subagent file conventions

A subagent is a single Markdown file: YAML frontmatter (metadata) followed by the system prompt body. The body is the agent's system prompt. Two metadata fields are common to every tool:

- `name` (required) — unique identifier in kebab-case (most tools derive a default from the filename).
- `description` (required) — natural-language statement of the subagent's purpose and **when it should be invoked**. This drives automatic delegation, so write it for triggering, not just summary. Add "Use PROACTIVELY" / "MUST BE USED" (or "use proactively" / "always use for" in Cursor) when the agent should be preferred without being asked.

Beyond these, the **directory** and the **optional frontmatter fields** (tool allowlists, model, permissions, isolation) differ per tool. Subagents exist at two scopes everywhere:

- **Project scope** — an `agents/` directory in the repo, version-controlled, shared with the team, takes precedence on name conflicts.
- **User / global scope** — an `agents/` directory in the home config dir, available across all projects on that machine.

Before writing, **detect the target tool and its convention** by checking which agent directory or config already exists, then follow it. See `references/tool-conventions.md` for the exact directory and frontmatter for each tool. Do not introduce a new location or format when one already exists.

## Workflow

### 1. Determine the tool, task type, and scope

Detect the **target tool** (Claude Code, Cursor, OpenCode, Trae CLI, Codex, ...) from existing agent directories or config, or ask if ambiguous. Decide whether you are **creating**, **updating**, or **reviewing** a subagent, and whether the target is **project-scoped** (repo) or **user/global-scoped** (home config dir). Locate existing subagent files in that tool's directory first, using `references/tool-conventions.md`.

### 2. Define the subagent boundary

Clarify:
- the single responsibility this subagent owns;
- the concrete situations that should trigger delegation to it;
- the tools and model it needs, and what it should **not** do.

If the role is too broad, split it into separate, composable subagents.

### 3. Write or update the definition

- Write the `description` so the main agent can decide when to delegate; state the trigger conditions explicitly.
- Write the system prompt body as a focused role: responsibilities, step-by-step approach, constraints, and an explicit output contract.
- Use the **target tool's** frontmatter fields and directory from `references/tool-conventions.md`; scope tool access to the minimum needed and set the model only when a non-default tier is justified.
- Use `assets/subagent-template.md` as a starting structure when creating a new subagent, adapting the frontmatter to the target tool.
- When updating, read the existing file first and preserve unrelated content.
- Follow the depth guidance in `references/subagent-authoring-guidelines.md`.

### 4. Review for quality and overlap

Check the subagent against `references/subagent-review-checklist.md`.

At minimum confirm:
- `name` is kebab-case and unique; `description` clearly states when to invoke;
- the system prompt has a single focus with a clear output contract;
- tool access is minimal and justified; model choice fits the task;
- the agent does not overlap or compete with an existing subagent;
- the file is in the correct directory for the target tool and uses only that tool's valid frontmatter fields.

## References

Read these files when needed:
- `references/tool-conventions.md` — per-tool agent directories (project + user scope) and frontmatter fields for Claude Code, Cursor, OpenCode, Trae CLI, and Codex.
- `references/subagent-authoring-guidelines.md` — how to write focused subagents, descriptions, tool/model scoping, and design patterns.
- `references/subagent-review-checklist.md` — checklist for reviewing subagent definition files.
- `assets/subagent-template.md` — a starting template for a new subagent definition.
