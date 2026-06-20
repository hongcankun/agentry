---
# Trae: always load this rule; description aids intelligent activation.
# Claude Code: ignores these keys, and loads always since `paths` is omitted.
description: Testing policy for adding or changing behavior, including meaningful coverage, determinism, and parallel safety.
alwaysApply: true
---

# Testing

When adding or changing behavior, decide whether automated tests should be added or updated. Use the `test-engineering` skill for the detailed workflow.

## When to test

Add or update tests when a change:

- introduces user-visible behavior;
- fixes a bug;
- changes validation, permissions, persistence, serialization, concurrency, or error handling;
- touches shared logic, public APIs, commands, generated outputs, or other contracts;
- addresses a previously untested edge case.

If tests are not added for a risky change, state why.

## Test expectations

- Test observable behavior and contracts, not incidental implementation details.
- Match the project's existing test framework, fixtures, naming, and assertion style.
- Structure tests so setup, behavior, and expectations are easy to distinguish; use arrange-act-assert or the closest local equivalent when it fits local style.
- Name tests after the behavior or case they prove.
- Keep tests deterministic and safe to run in parallel: avoid shared mutable state, fixed ports, order dependencies, global environment leaks, and reused filesystem or database identifiers unless the test framework provides isolation.
- Prefer meaningful assertions over coverage-only execution.

## Failing tests

- Investigate whether a failure comes from production behavior, test expectations, fixtures, mocks, isolation, or environment before editing the test.
- Fix the implementation when the test describes the intended contract; update the test only when the expectation is stale or wrong.

## Related

- `agentry-code-quality` plugin — the plugin this rule ships alongside.
- `test-engineering` skill — the full test design, writing, debugging, and review procedure.
