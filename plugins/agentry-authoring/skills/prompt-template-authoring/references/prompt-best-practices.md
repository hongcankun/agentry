# Prompt Best Practices

This document covers best practices for writing effective, reusable prompt templates for AI chat and AI agents.

## Prompt template structure

A good prompt template includes these sections:
1. **Purpose/Goal**: A clear statement of what the template is for.
2. **Context/Background**: Any necessary background information the AI needs.
3. **Instructions**: Step-by-step directions for the AI to follow.
4. **Variables**: Placeholders for dynamic content (e.g., {{user_input}}, {{context}}).
5. **Examples (optional)**: Sample inputs and outputs to illustrate the desired behavior.
6. **Constraints (optional)**: Rules or limitations the AI must follow (e.g., "keep responses under 100 words").
7. **Output Format (optional)**: Desired structure of the AI's response (e.g., JSON, markdown).

## Variable Syntax

Use double curly braces for variables: {{variable_name}}. Examples:
- {{user_input}}
- {{context}}
- {{code_snippet}}

## Example Prompt Template

See `assets/example-code-review-prompt.md` for a complete, filled-in example.
