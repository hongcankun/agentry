# Command Review Checklist

Use this checklist when reviewing an AI agent command file or command package.

## Purpose and Fit

- The command has one clear, repeatable workflow.
- The command is appropriate for explicit invocation, rather than always-on rule behavior.
- The command does not duplicate an existing command, skill, rule, or subagent.
- The command name and description make the trigger obvious to a user.

## Naming and Metadata

- The invocation name is kebab-case and stable.
- The filename matches the intended invocation name or the target tool's naming convention.
- Frontmatter is valid for the target tool.
- The description is short, user-facing, and specific.
- Optional tool restrictions are present only when useful and valid for the target tool.

## Arguments and Inputs

- Required and optional arguments are documented.
- Argument examples match the actual prompt behavior.
- Defaults and omitted-argument behavior are explicit.
- The command states what selected files, repository state, external context, or user-provided text it expects.
- The command rejects or asks about unsafe or ambiguous inputs instead of guessing.

## Prompt Body

- The prompt body gives direct workflow steps the agent can execute.
- The command states constraints, safety checks, and verification steps.
- The output contract is explicit: format, level of detail, and any file or command results to include.
- The command avoids hidden local assumptions and machine-specific paths unless it is intentionally project-scoped and documented.
- The command does not contain stale references to removed files, tools, or options.

## Placement and Scope

- The command lives in the correct directory for the target tool and scope.
- Project-scoped commands are version-controlled when intended for the team.
- User/global commands do not accidentally land in the repo.
- Plugin commands live under the plugin root `commands/` directory.
- Related plugin manifests or marketplace entries still describe the package accurately.

## Validation

- The target tool's validator passes when one is available.
- The command frontmatter parses.
- The command can be invoked by its intended name.
- The workflow was smoke-tested when practical.

## Final Check

- The command is useful as a small, memorable entry point.
- Updates preserved unrelated existing command behavior.
- The command is ready to install, package, or commit.
