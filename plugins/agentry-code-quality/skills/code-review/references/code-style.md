<!-- GENERATED from rules/code-quality/code-style.md by 'scripts/agentry.py generate'. Do not edit by hand; edit the canonical rule. -->

# Code Style

General code style conventions that apply across projects. Defer to the project's own established conventions (existing code, linters, formatters, style guides) wherever they are more specific or differ.

## Core principles

- KISS: prefer the simplest solution that works; optimize for clarity over cleverness, and avoid premature optimization.
- DRY: extract repeated logic into a shared function once the repetition is real, not speculative.
- YAGNI: do not build features, abstractions, or configuration before they are needed.

## Formatting

- Match the existing style of the file you are editing; do not reformat unrelated lines.
- Follow the project's configured formatter and linter; never fight their output.
- Use consistent indentation within a file, matching the width and kind (tabs or spaces) the file already uses.
- Keep lines reasonably short and break long expressions across lines for readability.
- End every file with a single trailing newline.
- Follow the idiomatic style guide of the language in use (e.g. PEP 8 for Python).

## Naming

- Use descriptive, intention-revealing names; avoid abbreviations and single-letter names except for short-lived loop variables.
- Follow the language's idiomatic casing conventions for functions, variables, constants, and types.
- Name booleans as predicates (e.g. `is`/`has`/`should`/`can` prefixes) so their meaning is clear.
- Keep names consistent with the surrounding module's existing vocabulary.

## Structure

- Organize code by feature or domain, not by type.
- Keep files focused and cohesive; split a large file into smaller modules and extract utilities when it grows unwieldy.
- Keep functions small and single-purpose; split a long function into focused pieces with clear responsibilities.
- Prefer early returns over deep nesting; flatten logic once conditionals start stacking.
- Replace magic numbers with named constants for meaningful thresholds, limits, and delays.

## Language idioms

- Prefer the standard library and existing helpers over new dependencies or hand-rolled equivalents.
- Use the language's idiomatic constructs rather than porting patterns from another language.
- Prefer immutable data: return new values instead of mutating shared inputs in place, unless the language or project idiom favors in-place updates.

## Error handling & input validation

- Handle errors explicitly; never silently swallow them.
- Fail fast with a clear message at system boundaries (file I/O, parsing, external input); do not add defensive handling for conditions that cannot occur.
- Validate untrusted input (user input, API responses, file content) before acting on it, using the project's validation approach where one exists.
- Surface user-facing messages at the boundary while logging detailed context for diagnosis.

## Comments & docs

- Write comments that explain *why*, not *what*; do not narrate code that already reads clearly.
- Do not add comments, docstrings, or type annotations to code you did not change.
- Give modules and non-trivial public functions a concise docstring describing purpose and behavior.
- Remove dead code rather than commenting it out.
