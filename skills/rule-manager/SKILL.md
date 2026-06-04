---
name: rule-manager
description: Create, update, or review agent rules that guide AI agent behavior, at project scope or user/global scope, including defining scope and triggers, writing clear and actionable directives, organizing rule files, and reviewing rules for clarity and conflicts. Use when a user asks to create a new agent rule, update existing rules, or review rule files such as CLAUDE.md, AGENTS.md, .cursor/rules, .claude/rules, or ~/.claude/rules and ~/.trae rules.
---

# Rule Manager

Create, update, or review **agent rules**: the instruction files that tell an AI agent how to behave. Rules can be **project-scoped** (in the repo, e.g. `CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `.cursor/rules/`, `.claude/rules/`, `.trae/rules/`) or **user/global-scoped** (in the home config dir, e.g. `~/.claude/CLAUDE.md`, `~/.claude/rules/`, `~/.trae/AGENTS.md`).

Follow these principles:
- Write rules as clear, actionable directives, not vague preferences.
- Keep each rule focused on one behavior or concern.
- State when a rule applies so the agent can decide whether to follow it.
- Avoid conflicts, duplication, and unnecessary rules that add noise.

## When to use

Use this skill when the task is to:
- create a new agent rule or rule file, at project scope or user/global scope;
- update or extend existing agent rules with new guidance;
- review rule files for clarity, conflicts, redundancy, or missing scope.

## Expected input

Provide as much of the following as available:
- the behavior or convention the rule should enforce;
- whether the rule is **project-scoped** (repo) or **user/global-scoped** (home config dir);
- the trigger scope: which files, languages, or tasks the rule applies to;
- existing rule files that should be respected or updated;
- whether the task is **create**, **update**, or **review**.

If details are missing, infer reasonable defaults from the request and the project structure, default to project scope unless the user asks for global rules, and keep the rule set minimal.

## Rule file conventions

Agent rules exist at two scopes:
- **Project scope** — lives in the repo, version-controlled, applies to that project.
- **User / global scope** — lives in the user's home config dir, applies across all projects on that machine.

When working on a rule, first determine the intended scope. User-scoped rules belong in the home config dir, not the repo. Project-scoped rules belong in the repo.

### Project scope

- `CLAUDE.md` / `AGENTS.md` — project-wide instructions at the repo root.
- `.cursorrules` — single-file rules for Cursor (legacy, being deprecated; prefer `.cursor/rules/`).
- `.cursor/rules/*.mdc` — scoped, modular rules for Cursor (must be `.mdc`; plain `.md` is ignored). Supports subfolders for grouping, and nested `.cursor/rules/` folders in subdirectories (e.g. `packages/web/.cursor/rules/`) that override root rules for that subtree. Scope via `globs` / `alwaysApply` frontmatter.
- `.claude/rules/*.md` — scoped, modular rules for Claude Code. Discovered recursively, so subfolders (e.g. `frontend/`, `backend/`) can group rules; `paths` frontmatter globs scope rules to matching files.
- `.trae/rules/*.md` / `*.mdc` — scoped, modular rules for Trae (`project_rules.md` always loads). Supports subfolders for grouping (recursively read, up to 3 levels), and a `.trae/rules/` folder in any subdirectory for module-scoped rules. Also auto-discovers `.cursor/rules/*.mdc`.

### User / global scope

- `~/.claude/CLAUDE.md` / `~/.claude/rules/*.md` — Claude Code user rules; apply to all projects and load before project rules (project rules take precedence).
- `~/.trae/AGENTS.md` — Trae user rules (also `~/.coco/`, `~/.trae-cn/`, or `~/.agents/`).
- Cursor user rules live in Cursor settings (plain text), not in a repo directory; use them for personal preferences only, not shared code conventions.

Before writing, detect which convention the project already uses and follow it. Do not introduce a new format when one already exists.

## Workflow

### 1. Determine the task type and scope

Decide whether you are **creating**, **updating**, or **reviewing** rules, and whether the target is **project-scoped** (repo) or **user/global-scoped** (home config dir). Locate existing rule files in the relevant scope first.

### 2. Define the rule boundary

For each rule clarify:
- the behavior it enforces;
- the scope or trigger (when it applies);
- the reason, only if it is not obvious.

Write one rule per concern. Split unrelated guidance into separate rules.

### 3. Write or update the rule

- Use imperative, testable language ("Use X", "Never do Y", "Prefer A over B").
- Group related rules under clear headings.
- Use `assets/rule-template.md` as a starting structure when creating a new rule file.
- When updating, read the existing file first and preserve unrelated rules.
- Follow the depth guidance in `references/rule-writing-guidelines.md`.

### 4. Review for quality and conflicts

Check the rules against `references/rule-review-checklist.md`.

At minimum confirm:
- each rule is clear and actionable;
- no two rules contradict each other;
- there is no duplication or dead guidance;
- scope is stated where a rule is not always applicable;
- the file matches the project's existing rule convention.

## References

Read these files when needed:
- `references/rule-writing-guidelines.md` — how to write clear, scoped, conflict-free agent rules.
- `references/rule-review-checklist.md` — checklist for reviewing rule files.
- `assets/rule-template.md` — a starting template for a new rule file.
