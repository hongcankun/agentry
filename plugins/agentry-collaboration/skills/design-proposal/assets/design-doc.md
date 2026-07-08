<!-- Lightweight design doc template. Fill each section; delete guidance in parentheses. Use this tier for a medium, mostly-reversible change with one or two real alternatives. For a small, reversible change, skip the template and write an inline note (approach + main risk) directly in the issue or PR. -->

# Design Doc: (title)

- **Status:** (draft / in review / accepted / rejected / superseded)
- **Answers:** (link to the accepted change request / issue this designs)
- **Author(s):** (names)

## Summary

(One short paragraph: the problem in a sentence and the approach you propose in a sentence. Enough for a reviewer to know what this design does before reading the details.)

## Motivation

(One or two sentences: the core of the accepted change request — the problem and desired outcome — linked under **Answers** above. Recap, do not re-justify.)

**Non-goals:** (what this design does *not* aim to do — aims left out of scope, to keep it from sprawling.)

## Proposed Design

(The chosen approach, enough for an implementer to build from. Keep it proportional — this is not a full RFC.)

## Alternatives Considered

(The one or two real options weighed and why the chosen approach wins, plus the main drawback of the chosen one. Mention relevant prior art here when it influenced the chosen approach; use the RFC form if prior art needs dedicated treatment. If there were no alternatives worth weighing, say so and why the choice is obvious.)

## Impact

(What this change reaches — the components, interfaces, data, or dependents it touches — and what it leaves untouched. Reach, not intent.)

## Risks

(The main failure modes and mitigations. For anything breaking or stateful, add a line on how users or data move and how to back out.)

## Observability

(One line: the signal or metric that will confirm the built design achieved the accepted outcome, and how its health is seen once running. Design-level, not code testing.)
