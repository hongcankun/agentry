---
description: Short user-facing description of what this command does.
argument-hint: "<required-input> [optional-context]"
---

# Command Name

Use this command when the user wants to <describe the explicit workflow>.

## Inputs

- `<required-input>`: Describe the required argument and accepted forms.
- `[optional-context]`: Describe optional arguments, selected files, or default behavior.

If required input is missing or ambiguous, ask one concise clarifying question before acting.

## Workflow

1. Inspect the relevant context and existing project conventions.
2. Execute the focused workflow this command owns.
3. Validate or sanity-check the result.
4. Return the requested output in the format below.

## Output

Return:
- the main result;
- important assumptions or skipped validation;
- next steps only when they directly follow from the result.
