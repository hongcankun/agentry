---
name: test-engineering
description: Write, update, debug, and review automated tests that cover meaningful behavior and match the project's test conventions. Use when the user asks to add tests, improve coverage, fix failing or flaky tests, review test code, or design a testing plan.
---

# Test Engineering

Write, update, debug, and review automated tests that give useful confidence without making the suite brittle. The goal is to cover important behavior with tests that are deterministic, maintainable, and aligned with the project's existing test style.

Follow these principles:
- Test behavior and contracts, not incidental implementation details.
- Match the project's existing test framework, fixture style, naming, and assertion patterns.
- Prefer small, focused tests that fail for one clear reason.
- Add regression tests for bug fixes before or alongside the fix when practical.
- Keep tests deterministic and parallel-safe: control time, randomness, IO, network calls, shared state, fixed ports, and concurrency.
- Use coverage as a signal, not the goal. Do not add shallow assertions just to raise a percentage.

## When to use

Use this skill when the task is to:
- add tests for new behavior or a bug fix;
- update tests after production behavior changes;
- repair failing or flaky tests;
- review test code for quality, coverage, and maintainability;
- design a testing plan before implementation;
- improve measured coverage for meaningful behavior.

For broad code review, use the `code-review` skill. For security-specific testing, combine this skill with the security-focused guidance from the relevant security audit workflow.

## Expected input

Gather as much of the following as available:
- the behavior, bug, or risk that needs test coverage;
- the production files and test files involved;
- the current test command, framework, and fixture conventions;
- relevant failures, stack traces, CI logs, coverage output, or flaky-test symptoms;
- the desired scope: plan only, write tests, update tests, debug failures, or review tests.

If scope is ambiguous, inspect nearby tests and project configuration, then choose the smallest useful test change that proves the requested behavior.

## Workflow

### 1. Understand the behavior under test

Read the production code, existing tests, and any issue or change description. Identify the observable contract: inputs, outputs, side effects, errors, persistence, messages, API responses, or UI state. For bug fixes, reproduce the failure when practical; otherwise describe the failing behavior from the available evidence before deciding what to assert.

### 2. Choose the right test level

Pick the lowest level that gives real confidence in the contract without hiding integration risk. Use the test-level table in `references/test-design.md` to match the behavior to unit, component, integration, or end-to-end, and add a regression test for a confirmed bug with a name or assertion that makes the previous failure obvious.

See `references/test-design.md` for case design too, and `references/test-recipes.md` for concrete workflows such as regression tests, flaky-test debugging, coverage improvements, and test review.

### 3. Match local conventions

Locate nearby tests for the same module or feature. Reuse existing helpers, factories, fixtures, setup/teardown patterns, and assertion style. Avoid introducing a new framework, snapshot style, mocking library, or fixture abstraction unless the project already uses it or the user explicitly asks.

### 4. Write or update tests

Keep each test focused on one behavior. Arrange data clearly, perform the action once when possible, and assert the observable result. Include important edge cases: empty input, invalid input, boundaries, permissions, errors, retries, concurrency, and serialization or persistence details when they matter.

Assume tests may run in parallel. Avoid shared mutable state, fixed ports, global environment leaks, order dependencies, and reused filesystem or database identifiers unless the test framework provides isolation.

Avoid over-mocking. Mock slow or external boundaries, not the internal logic being tested. If a test needs many mocks, reconsider whether an integration-style test would be clearer.

### 5. Debug failures and flakes

When a test fails, read the failure first and determine whether the production behavior, test expectation, fixture setup, or environment is wrong. For flaky tests, look for uncontrolled time, randomness, ordering, shared global state, leaked resources, async races, network access, and cleanup gaps.

### 6. Validate with evidence

Run the narrowest relevant test command first, then broader checks when the change is not isolated. If the user asks for coverage, or if coverage is the stated goal, run the project's coverage tool and report the measured result. Do not invent test or coverage results; state clearly when a command could not be run.

### 7. Review test quality

When reviewing tests, evaluate them with `references/test-review-checklist.md`. Report concrete issues with file and line references, impact, and a suggested fix. A clean test review is valid; do not pad findings with preferences.

## Output

For test implementation tasks, report:
- tests added or updated and the behavior they cover;
- validation commands run and their results;
- coverage results when measured;
- any remaining gaps or environment blockers.

For test plans, report:
- the behaviors to cover;
- recommended test level and files;
- key cases and fixtures;
- validation commands to run.

For test reviews, report:
- findings grouped by severity;
- the test quality or coverage impact;
- validation evidence when checks were run;
- a concise verdict.

## References

- `references/test-design.md`: choosing test levels, selecting cases, and designing maintainable tests.
- `references/test-recipes.md`: framework-agnostic workflows for adding, updating, debugging, reviewing, and improving tests.
- `references/test-review-checklist.md`: checklist for reviewing test correctness, determinism, coverage value, and maintainability.
