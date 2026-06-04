---
# Frontmatter must be the FIRST thing in the file to be recognized.
# Keep it ONLY for modular rule files (.cursor/rules, .claude/rules, .trae/rules).
# Delete this whole block for root files (CLAUDE.md, AGENTS.md, .cursorrules) — they take no frontmatter.
# Use the fields for your target tool and remove the rest:
#
# Cursor (.mdc only — plain .md is ignored) / Trae (.md or .mdc):
description: Short summary of the rule
globs: "src/api/**/*.ts"   # comma-separated; load when matching files are in context
alwaysApply: false         # true = always load regardless of file
#
# Claude Code (.md):
# paths: "src/api/**/*.ts"  # glob(s); load when working with matching files. Omit to always load.
---

# Agent Rules

Instructions for the AI agent. Use this for project-scoped rules (in the repo) or user/global-scoped rules (in the home config dir); drop sections that do not apply to the chosen scope.

## General

- [State an always-applicable behavior the agent must follow.]
- [State another always-applicable rule.]

## Code Style

- [Style rule, e.g. "Use 2-space indentation for all files."]
- [Naming or formatting rule.]

## Testing

- [Rule about when and how to write tests.]

## Git

- [Rule about commits, branches, or messages.]

## Scoped Rules

- For [language or path]: [scoped rule that only applies in that context].
