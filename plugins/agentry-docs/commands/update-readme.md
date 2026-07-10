---
description: Create or update a repository README with accurate setup, usage, contribution, and license details.
argument-hint: "[README intent or focus]"
---

# Update Readme

Use this command when the user wants to create, refresh, or improve a repository README.

## Inputs

- `[README intent or focus]`: Optional project area, feature, installation path, usage scenario, audience, or plain-language documentation goal. If omitted, inspect the repository and update the primary README.md for accuracy and completeness.
- Selected files, package manifests, existing docs, issue notes, or prior discussion may be treated as source context when the tool provides them.

If the target README, intended audience, or scope of documentation changes is unclear, ask one concise clarifying question before rewriting broadly.

## Workflow

1. Follow the `readme-authoring` skill as the authoritative README procedure, including its template guidance and output expectations.
2. Inspect the repository structure and existing documentation:
   - find the primary `README.md` and any nested package READMEs relevant to the requested scope;
   - read project metadata, dependency files, build/test config, license, contribution docs, examples, and CLI help when available;
   - identify generated files or package-manager locks that should not be edited for documentation-only work.
3. Determine the README purpose and audience: new users, contributors, operators, plugin consumers, library users, or maintainers.
4. Preserve accurate existing content and remove or update stale sections. Prefer concise, task-oriented prose over broad marketing language.
5. Add or revise only sections that are useful for the project: description, features, requirements, installation, usage, configuration, development, testing, contributing, troubleshooting, and license.
6. Verify commands, links, paths, and examples when practical. If a command cannot be run, state that rather than presenting it as verified.
7. Review the diff for readability, broken structure, duplicate information, and claims not supported by the repository.

## Constraints

- Do not invent capabilities, installation steps, badges, compatibility guarantees, or test results.
- Do not overwrite project-specific guidance with a generic template.
- Do not edit generated files unless the repository explicitly treats the target README as generated output.
- Keep docs aligned with existing project tone and terminology.
- Do not stage, commit, push, or open a pull request unless the user explicitly asks.

## Output

Return:
- the README file or files updated;
- the main sections changed and why;
- verification performed, skipped, or blocked;
- any follow-up documentation gaps that remain.
