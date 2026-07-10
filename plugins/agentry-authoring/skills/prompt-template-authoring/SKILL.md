---
name: prompt-template-authoring
description: Create, update, or review reusable prompt templates for AI chat or AI agents, including defining the template purpose, structure, variables, examples, and validation. Use when a user asks to create a prompt template, improve an existing one, review a template, or standardize prompts for a specific task.
---

# Prompt Template Authoring

Create, update, or review reusable prompt templates for AI chat or AI agents, ensuring they are clear, actionable, and easy to customize with variables.

## When to use

Use this skill when the task is to:
- create a new prompt template for a specific task;
- update or refine an existing prompt template;
- review a prompt template for clarity, completeness, and reusability;
- standardize prompts for consistent AI agent or chat behavior.

## Expected input

Provide as much of the following as available:
- the task or use case the prompt template is for;
- key variables or placeholders the template should include;
- desired tone, style, or format of the AI's response;
- examples of good inputs and outputs;
- any constraints or requirements the template must follow.

If important details are missing, ask clarifying questions or infer reasonable defaults.

## Prompt template structure

A good prompt template should include:
1. **Purpose/Goal**: A clear statement of what the template is for.
2. **Context/Background**: Any necessary background information the AI needs.
3. **Instructions**: Step-by-step directions for the AI to follow.
4. **Variables**: Placeholders for dynamic content (e.g., {{user_input}}, {{context}}).
5. **Examples (optional)**: Sample inputs and outputs to illustrate the desired behavior.
6. **Constraints (optional)**: Rules or limitations the AI must follow (e.g., "keep responses under 100 words").
7. **Output Format (optional)**: Desired structure of the AI's response (e.g., JSON, markdown).

## Workflow

### 1. Define the template's purpose and scope
Clarify:
- What task or problem is the template solving?
- Who or what is the intended user/consumer of the template?
- What are the key variables or dynamic inputs the template needs to accept?

### 2. Draft the core content
Write the template content, including:
- A clear purpose/goal statement.
- Any necessary context/background.
- Step-by-step instructions for the AI.
- Placeholders for variables (use {{variable_name}} syntax).
- Optional examples, constraints, and output format.

### 3. Add examples and test cases
Include 1-3 examples of:
- Filled-in templates with sample variables.
- Desired AI responses to those filled-in templates.

### 4. Review and validate the template
Check the template for:
- Clarity and lack of ambiguity.
- Completeness (includes all necessary information for the AI to complete the task).
- Reusability (easy to customize with variables).
- Consistency in tone and style.
- No hidden context or assumptions.

### 5. Save the template
Save the prompt template as a markdown file in the `assets/` directory (or provide it directly to the user). Use a descriptive, kebab-case filename (e.g., `code-review-prompt.md`).

## References

Read these files when needed:
- `references/prompt-best-practices.md` — best practices for writing effective prompts.

