---
name: command-manager
description: Create, update, or review AI agent commands across tools like Claude Code, Trae CLI, Cursor, and Codex, including defining command purpose, arguments, prompt body, file placement, metadata, and validation. Use when a user asks to create a slash command, edit an existing command, or review command files such as .claude/commands/, .trae/commands/, .cursor/commands/, or plugin commands/.
---

# Command Manager

Create, update, or review **AI agent commands**: reusable command definitions that users invoke explicitly, often as slash commands, to run a focused agent workflow with optional arguments or selected context. Commands are usually Markdown files with YAML frontmatter or tool-specific metadata plus a prompt body. Their file locations, argument syntax, and namespacing differ by tool.

Follow these principles:
- Make each command a clear entry point for one repeatable workflow.
- Prefer commands for explicit user-invoked workflows; use rules for always-on behavior and subagents for delegation.
- Write invocation names and descriptions so users can discover the command quickly.
- Define arguments and expected context precisely, including defaults and failure behavior.
- Keep command prompts portable and tool-aware, without depending on hidden local context.

## When to use

Use this skill when the task is to:
- create a new command or slash command for an AI coding tool;
- update a command's name, description, arguments, prompt body, or placement;
- review command files for clarity, scope, metadata, portability, and overlap.

## Expected input

Provide as much of the following as available:
- which AI tool the command targets (Claude Code, Trae CLI, Cursor, Codex, ...);
- the workflow the command should start and the user situations that should trigger it;
- the invocation name, arguments, and any required selected files or context;
- whether the command is **project-scoped** (repo), **user/global-scoped** (home config dir), or bundled in a plugin;
- existing command files that should be respected or updated;
- whether the task is **create**, **update**, or **review**.

If details are missing, infer reasonable defaults from the request and project: detect the target tool from existing command directories or plugin layout, default to project scope unless the user asks for personal/global commands, keep arguments minimal, and avoid overlapping an existing command.

## Command file conventions

A command should have:
- a stable kebab-case invocation name;
- a concise description of what it does and when to use it;
- a prompt body that states the workflow, inputs, constraints, and output contract;
- argument documentation when the tool supports arguments;
- correct placement for the target tool and scope.

Commands can live in different places:
- **Project scope** - version-controlled command files in the repo, shared with the team.
- **User / global scope** - personal commands in the user's home config dir.
- **Plugin scope** - command files under a plugin's `commands/` directory and distributed with that plugin.

Before writing, detect the target tool and follow the existing convention. Do not introduce a new command directory or metadata shape when the project already has one. See `references/command-conventions.md` for known layouts and fields.

## Workflow

### 1. Determine the tool, task type, and scope

Detect the target tool from existing command directories, plugin files, or repo config. Decide whether you are **creating**, **updating**, or **reviewing** a command, and whether it belongs at project, user/global, or plugin scope.

For create/update work, locate related commands first so the new command fits the existing naming and structure.

### 2. Define the command boundary

Clarify:
- the workflow the command owns;
- the exact user trigger and invocation name;
- required arguments, optional arguments, and selected context;
- what the command should produce;
- what it should deliberately leave to another command, skill, rule, or subagent.

If the command would need many unrelated modes, split it into separate commands or use a command that asks the user to choose a bounded mode.

### 3. Write or update the command

- Use the target tool's command directory and metadata from `references/command-conventions.md`.
- Use `assets/command-template.md` as a starting point when creating a Markdown command.
- Write the description for discovery by a human user, not as an internal implementation note.
- Put arguments near the top of the file and state accepted forms, defaults, and validation.
- Write the prompt body as concrete instructions: gather context, execute the workflow, verify the result, and return the expected output.
- When updating, read the existing file first and preserve unrelated behavior.

### 4. Review for quality and overlap

Check the result against `references/command-review-checklist.md`.

At minimum confirm:
- the name is kebab-case, discoverable, and not duplicated;
- the command has one clear workflow and an explicit output contract;
- arguments are documented and safe to omit when optional;
- the command is in the right scope and directory for the target tool;
- the command does not duplicate an existing command, rule, skill, or subagent.

### 5. Validate

Run the target tool's validator when available, or at least parse the command frontmatter and inspect the invocation path:

```bash
# Claude Code plugin or marketplace
claude plugin validate .

# Trae CLI plugin
traecli plugin validate --path ./<plugin-dir>
```

If no validator is available, do a manual review using `references/command-review-checklist.md` and test the command in the target tool when practical.

## References

Read these files when needed:
- `references/command-conventions.md` - per-tool command directories, metadata, plugin placement, and validation commands.
- `references/command-review-checklist.md` - checklist for reviewing command files.
- `assets/command-template.md` - a starting template for a Markdown command definition.
