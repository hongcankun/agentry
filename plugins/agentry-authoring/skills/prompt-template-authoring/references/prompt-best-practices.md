# Prompt Best Practices

This document covers best practices for writing effective, reusable prompt templates for AI chat and AI agents.

## General Principles

1. **Be Clear and Specific**: Avoid ambiguity. Provide detailed instructions about what you want the AI to do.
2. **Use Variables for Reusability**: Use placeholders like {{variable_name}} for dynamic content so the template can be reused with different inputs.
3. **Provide Context**: Give the AI any background information it needs to complete the task effectively.
4. **Give Step-by-Step Instructions**: Break complex tasks into clear, sequential steps.
5. **Include Examples**: When possible, provide 1-3 examples of good inputs and corresponding desired outputs.
6. **Define Output Format**: Specify the desired structure of the AI's response (e.g., JSON, markdown, bullet points).
7. **Set Constraints**: Clearly state any limitations (e.g., word count, tone, forbidden content).

## Variable Syntax

Use double curly braces for variables: {{variable_name}}. Examples:
- {{user_input}}
- {{context}}
- {{code_snippet}}

## Example Prompt Template

Here's an example of a good prompt template:

```markdown
# Code Review Prompt

## Purpose
You are a senior software engineer. Review the provided code for bugs, readability, performance, and best practices.

## Instructions
1. Read the code carefully.
2. Identify any bugs or potential issues.
3. Suggest improvements for readability and maintainability.
4. Check for performance optimizations.
5. Ensure the code follows language-specific best practices.
6. Provide your feedback in markdown format.

## Variables
- {{code_language}}: The programming language of the code (e.g., Python, JavaScript).
- {{code_snippet}}: The code to review.

## Constraints
- Keep your feedback constructive and actionable.
- Focus on the most important issues first.
- Do not rewrite the entire code unless necessary.

## Output Format
```markdown
## Summary
[Brief summary of the code review]

## Issues Found
- [ ] [Issue 1]
- [ ] [Issue 2]

## Suggestions
- [Suggestion 1]
- [Suggestion 2]
```
```
