# Test Review Checklist

Use this checklist when reviewing tests or deciding whether new tests are ready. These are pass/fail checks; for why each matters (boundary-only mocks, controlled nondeterminism, coverage as a signal not a target), see `test-design.md`.

## Correctness

- The test asserts the intended behavior, not just the current implementation.
- The assertion would fail if the bug or regression returned.
- Expected errors, status codes, messages, and side effects match the real contract.
- Test data represents realistic inputs for the behavior being covered.
- The test does not pass for the wrong reason because setup failed or assertions are too broad.

## Coverage value

- New production behavior has at least one focused test.
- Bug fixes include a regression test when practical.
- Important edge cases are covered without duplicating equivalent cases.
- Negative paths and permission or validation failures are covered when they are part of the risk.
- Coverage is meaningful; tests are not just executing lines without checking outcomes.

## Determinism

- Time, randomness, ordering, async work, and retries are controlled.
- External services, files, databases, queues, and environment variables are isolated or cleaned up.
- Tests do not depend on execution order or shared mutable state.
- Parallel test execution would not create collisions in names, ports, records, or temp paths.
- No real sleeps, unbounded waits, or network calls are used unless explicitly required by the test type.

## Maintainability

- Test names describe behavior and expected outcome.
- Setup is clear, with relevant values visible and irrelevant defaults hidden.
- Helpers reduce duplication without obscuring what the test proves.
- Assertions are specific enough to diagnose failures quickly.
- Mocks are limited to boundaries and do not mirror internal implementation step by step.
- The test follows local framework, fixture, and naming conventions.

## Review findings

Treat these as higher-severity findings:
- a test can pass while the target behavior is broken;
- a test is flaky or order-dependent;
- a test is not safe to run in parallel and can collide through shared files, fixed ports, database records, global state, or environment variables;
- a test hits a real external service unexpectedly;
- risky production logic lacks meaningful coverage;
- a test changes shared state without cleanup.

Treat these as lower-severity findings:
- unclear names or noisy setup;
- redundant cases that slow the suite;
- overly broad snapshots;
- minor assertion style mismatches.

Do not report preference-only differences when the test is correct, deterministic, and consistent with nearby tests.
