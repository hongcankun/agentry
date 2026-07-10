---
name: readme-authoring
description: Create, refresh, or simplify repository README files by grounding setup, usage, contribution, and license guidance in the actual project structure. Use when a user asks to create a README, update an existing README, or document a software project.
---

# Readme Authoring

Create or update repository README files with accurate, task-oriented documentation.

## When to use

Use this skill when the task is to:
- create a new README.md file for a project;
- update an existing README.md with new information;
- refresh, simplify, or correct repository documentation.

## Expected input

Provide as much of the following as available:
- the project name and purpose;
- key features of the project;
- installation instructions;
- usage examples;
- contributing guidelines;
- license information.

If details are missing, infer them from the repository structure and existing files. Do not invent capabilities, support guarantees, commands, or validation results.

## Standard README sections

`assets/README-template.md` is the canonical section set. Include only the sections that serve the project and audience; omit the rest.

Non-obvious selection guidance:
- **Features**: list capabilities the repository actually supports, never planned or aspirational ones.
- Keep **Requirements** (prerequisites needed before install) distinct from **Configuration** (settings the user provides after install, such as environment variables or config files).

## Workflow

### 1. Analyze the repository
- Explore the repository structure to understand the project.
- Look for existing files (package.json, requirements.txt, LICENSE, etc.) that can provide information.
- Check if a README.md already exists.
- Identify whether there are nested package READMEs, generated docs, or docs that should not be edited.

### 2. Gather information
- Identify the project name and purpose.
- Determine installation requirements from dependency files.
- Look for usage examples in the codebase or existing documentation.
- Check for a LICENSE file.
- Read CLI help, tests, examples, or configuration files when they are the best source for behavior.

### 3. Create or update the README
- If a README exists, read it first to preserve existing information.
- Use the template in `assets/README-template.md` only as a starting point for a missing or severely incomplete README.
- Fill in the sections with the gathered information.
- Keep the language clear, concise, and aligned with the project's existing terminology.
- Prefer updating stale sections over rewriting a working README into a generic template.

### 4. Review and validate
- Check that useful sections are included and unsupported sections are omitted.
- Ensure the information is accurate and up-to-date.
- Verify links, paths, and examples when practical.
- Run documented commands only when appropriate for the task and environment. If you cannot run them, say so.
- Review the diff for invented claims, duplicated guidance, broken structure, and accidental edits to generated files.

## References

- `assets/README-template.md` — a standard README template to use as a starting point.
