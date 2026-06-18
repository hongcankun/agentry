# Command Tool Conventions

Agent commands are explicit user-invoked workflows, often exposed as slash commands. They are best for tasks a user chooses to run on demand, such as "review this diff", "write a PR description", or "generate a migration plan". Use rules for always-on instructions, skills for reusable agent procedures, and subagents for delegated specialists.

Conventions change by tool. Always inspect the target repo or user config first and follow the existing command layout when present.

## Common Design

- Use kebab-case command names.
- Prefer one workflow per command.
- Include a short description when the tool supports metadata.
- Document arguments in the command body or frontmatter.
- State what context the user must provide, such as selected files, a branch name, an issue id, or free-form instructions.
- State the expected output shape and verification steps.
- Keep project-specific commands in the repo; keep personal convenience commands in the user/global config.

## Claude Code

### Project and User Commands

```text
.claude/commands/<name>.md
~/.claude/commands/<name>.md
```

Commands are Markdown files. The filename normally defines the invocation name. Subdirectories can be used to group commands when the tool supports namespaced command paths.

Common frontmatter:

```yaml
---
description: Short user-facing command description.
argument-hint: "<required> [optional]"
allowed-tools: Read, Grep, Glob
---
```

Use `allowed-tools` only when the command genuinely benefits from a constrained tool set. Keep the prompt body clear about how `$ARGUMENTS` or the tool's equivalent argument placeholder should be interpreted.

### Plugin Commands

```text
my-plugin/
├── .claude-plugin/plugin.json
└── commands/<name>.md
```

Plugin commands live at the plugin root under `commands/`, not inside `.claude-plugin/`.

Validate a plugin or marketplace directory when available:

```bash
claude plugin validate .
```

## Trae CLI

### Project and User Commands

```text
.trae/commands/<name>.md
~/.trae/commands/<name>.md
```

Trae plugin packages can also include command files:

```text
my-plugin/
└── commands/<name>.md
```

Trae auto-detects command component directories in plugin packages. A plugin that only contains skills, agents, and commands usually does not need `traecli.toml`; reserve it for MCP servers, hooks, models, or tool-permission configuration.

Validate a plugin package when available:

```bash
traecli plugin validate --path ./<plugin-dir>
```

## Cursor

Cursor command conventions are less standardized across installations. Before writing, inspect the project for existing command folders or documentation. If no command convention exists, avoid inventing one silently; ask which Cursor mechanism the user wants, or suggest using a prompt template, rule, or project documentation instead.

## Codex

Codex command conventions may be project- or environment-specific. Inspect existing `.codex/` or command-related directories first. If no convention is present, ask for the intended command format or create a portable Markdown prompt template instead of assuming a runtime-specific command location.

## Scope Selection

- Choose **project scope** when the command encodes a team workflow, repo convention, or project-specific operation.
- Choose **user/global scope** for personal shortcuts that should follow the user across repos.
- Choose **plugin scope** when the command belongs to an installable component bundle and should travel with related skills, agents, hooks, or MCP servers.

## Command vs Other Components

- Use a **command** when the user explicitly invokes a workflow.
- Use a **skill** when an agent needs reusable procedural knowledge that can trigger from natural-language requests.
- Use a **rule** when behavior should apply automatically.
- Use a **subagent** when work should be delegated to a specialized role with its own context and output contract.
