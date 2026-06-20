# Test Recipes

Use these recipes for common test-engineering tasks. They are intentionally framework-agnostic: first follow local project conventions, then adapt the steps to the test runner and fixtures already in use.

## Add a regression test

1. Identify the externally visible behavior that failed.
2. Find the narrowest existing test layer that can prove the behavior.
3. Write a test that would fail before the fix.
4. Assert the public outcome, side effect, persisted state, emitted message, or error contract.
5. Name the test so the previous failure is recognizable.
6. Run the targeted test first.
7. Run the relevant broader suite when the touched behavior crosses a boundary or shared contract.

Do not assert private helper calls unless the helper itself is the public unit under test.

## Add tests for new behavior

1. Extract the behavior contract from the issue, design, code, or user request.
2. List the primary success path and the highest-risk negative or boundary cases.
3. Choose the lowest test level that proves each case without hiding integration risk.
4. Reuse nearby fixture and assertion patterns.
5. Keep setup data minimal, with important values visible in the test.
6. Assert only outcomes that are part of the contract.
7. Run targeted tests, then broaden validation when the behavior affects shared paths.

Prefer a small set of meaningful cases over a large table that repeats the same assertion.

## Update tests after behavior changes

1. Decide whether the old expectation represented a real contract or an implementation detail.
2. Keep tests that still describe supported behavior.
3. Replace expectations only when the contract intentionally changed.
4. Add or update negative cases when the new behavior narrows accepted inputs or permissions.
5. Remove obsolete tests only when they no longer describe supported behavior.
6. Run related tests before and after the update to separate production regressions from stale expectations.

When a behavior change breaks many tests, look for one shared helper or fixture that encodes the old assumption before editing tests one by one.

## Fix a failing test

1. Classify the failure: assertion mismatch, setup error, timeout, dependency failure, cleanup leak, or environment issue.
2. Read the production change and the test expectation before editing either side.
3. Determine whether the production behavior or the test expectation is wrong.
4. Fix the smallest cause: production bug, stale fixture, incorrect assertion, missing cleanup, or missing test dependency.
5. Re-run the exact failing test.
6. Run nearby tests that share fixtures or setup.

Do not weaken assertions just to make the test pass. Preserve the behavior the test is meant to protect.

## Debug a flaky test

1. Capture the failure mode and how often it appears.
2. Check for uncontrolled time, randomness, ordering, shared state, async races, fixed ports, shared files, database collisions, leaked environment variables, and real external calls.
3. Replace sleeps with synchronization, fake timers, bounded polling, or framework-native waiting.
4. Make resource names and identifiers unique per test.
5. Ensure cleanup runs even when assertions fail.
6. Re-run the test repeatedly.
7. When supported, re-run with parallel execution enabled.

If the failure depends on test order, inspect both the failing test and the tests that run before it.

## Improve coverage

1. Inspect coverage output to find untested behavior, not just uncovered lines.
2. Prioritize branches that encode business rules, validation, error handling, permissions, persistence, serialization, or concurrency.
3. Skip generated code, framework boilerplate, and trivial accessors unless they contain project behavior.
4. Add assertions that would fail for a real regression.
5. Re-run coverage and report the measured change.

Coverage work is complete only when the added tests protect behavior the project cares about.

## Review test code

1. Verify the test would fail if the intended regression or missing behavior returned.
2. Check that assertions prove public behavior rather than internal implementation steps.
3. Check isolation, cleanup, determinism, and parallel safety.
4. Check fixture readability: important values should be visible, irrelevant defaults should stay hidden.
5. Check that mocks stop at external or slow boundaries.
6. Check that validation commands match the changed scope.

Report findings only when they affect confidence, maintainability, determinism, or execution cost.
