---
description: Draft a well-framed change request — a feature request, bug report, or refactor proposal — from a rough need.
argument-hint: "[the need, problem, or change to request]"
---

# Draft Change Request

Use this command when the user wants to turn a rough need into a clear, well-framed change request for a project.

## Inputs

- `[the need, problem, or change to request]`: The underlying problem, desired capability, bug, or refactor. If omitted, ask the user what they want to request.
- Selected files, error output, or prior discussion may be treated as source context when the tool provides them.

If the request type (feature / bug / refactor) is unclear, infer the most likely one and state the assumption; ask only when the choice materially changes the artifact.

## Workflow

1. Follow the `change-request` skill's **authoring path** as the authoritative procedure, including its rubric, `references/request-types.md`, and the templates in `assets/`.
2. Classify the request type and choose the form and venue.
3. State the problem (Why, not How) with quantified pain, define result-oriented acceptance criteria, and set explicit non-goals.
4. Fill the matching template, keeping detail proportional to the request's complexity.

## Constraints

- Do not prescribe the implementation; leave How to the party doing the work unless a constraint is a hard requirement the requester owns.
- Do not invent evidence, metrics, or context the user did not provide; mark any field left thin because the input did not cover it.
- Do not file, post, push, or open anything on an external tracker; return the artifact for the user to submit.

## Output

Return the completed change-request artifact in Markdown, plus a note of the chosen type and venue and any rubric field that needs more input from the user.
