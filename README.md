# Skills

A collection of Agent Skills following the open Agent Skills convention.

## Skills Included

- [agent-skill-creator](./skills/agent-skill-creator): Create and refine Agent Skills that follow the open Agent Skills convention, including planning skill scope, writing SKILL.md metadata and instructions, organizing scripts references and assets, and validating the final package.
- [code-review](./skills/code-review): Review code changes for correctness, readability, security, performance, and maintainability, then deliver prioritized, actionable feedback. Use when a user asks to review a diff, pull request, commit, branch, or file, or wants feedback on code they wrote or modified.
- [conventional-commits](./skills/conventional-commits): Create commits that follow the Conventional Commits specification, including selecting appropriate types, writing clear descriptions, and validating commit messages.
- [git-workflow](./skills/git-workflow): Apply git workflow best practices, including choosing a branching strategy, writing commits and pull requests, performing merges and rebases safely, resolving conflicts, and managing releases and tags.
- [prompt-template-creator](./skills/prompt-template-creator): Create and refine reusable prompt templates for AI chat or AI agents, including defining the template purpose, structure, variables, examples, and validation.
- [readme-manager](./skills/readme-manager): Create or update README.md files in git repositories, including analyzing the repo structure, identifying key information, and following standard README conventions.
- [rule-manager](./skills/rule-manager): Create, update, or review agent rules that guide AI agent behavior, at project scope or user/global scope, including defining scope and triggers, writing clear and actionable directives, organizing rule files, and reviewing rules for clarity and conflicts.
- [subagent-manager](./skills/subagent-manager): Create, update, or review AI subagents (specialized agents an AI coding tool delegates tasks to) across tools like Claude Code, Cursor, OpenCode, Trae CLI, and Codex, including defining the agent's role and trigger conditions, writing a focused system prompt, scoping tools and model, choosing the right scope, and reviewing agents for clarity and overlap.

## Rules Included

Platform-agnostic agent rules, organized by topic under [`rules/`](./rules), ready to be installed into a tool's rules directory (e.g. `.claude/rules/`, `.trae/rules/`).

- [code-quality/code-review](./rules/code-quality/code-review.md): Policy for when code review is required, the gates a change must pass before merging, and approval criteria; defers the review procedure to the `code-review` skill.
