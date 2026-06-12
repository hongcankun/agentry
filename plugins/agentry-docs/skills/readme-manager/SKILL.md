---
name: readme-manager
description: Create or update README.md files in git repositories, including analyzing the repo structure, identifying key information, and following standard README conventions. Use when a user asks to create a README, update an existing README, or document a new project.
---

# Readme Manager

Create or update README.md files in git repositories with standard sections and clear documentation.

## When to use

Use this skill when the task is to:
- create a new README.md file for a project;
- update an existing README.md with new information;
- refresh or improve the documentation of a git repository.

## Expected input

Provide as much of the following as available:
- the project name and purpose;
- key features of the project;
- installation instructions;
- usage examples;
- contributing guidelines;
- license information.

If details are missing, infer them from the repository structure and existing files.

## Standard README sections

A comprehensive README should include:
1. **Project Title**: Clear, concise name of the project.
2. **Description**: Brief overview of what the project does and why it exists.
3. **Features**: Key features or capabilities of the project (optional).
4. **Installation**: Step-by-step instructions for installing the project.
5. **Usage**: Examples of how to use the project.
6. **Contributing**: Guidelines for how others can contribute (optional).
7. **License**: Information about the project's license (optional).

## Workflow

### 1. Analyze the repository
- Explore the repository structure to understand the project.
- Look for existing files (package.json, requirements.txt, LICENSE, etc.) that can provide information.
- Check if a README.md already exists.

### 2. Gather information
- Identify the project name and purpose.
- Determine installation requirements from dependency files.
- Look for usage examples in the codebase or existing documentation.
- Check for a LICENSE file.

### 3. Create or update the README
- If a README exists, read it first to preserve existing information.
- Use the template in `assets/README-template.md` as a starting point.
- Fill in the sections with the gathered information.
- Keep the language clear and concise.

### 4. Review and validate
- Check that all standard sections are included (where applicable).
- Ensure the information is accurate and up-to-date.
- Verify links and examples work correctly.

## References

- `assets/README-template.md` — a standard README template to use as a starting point.
