---
description: Add, update, debug, review, or plan automated tests using the test-engineering skill.
argument-hint: "[test target or intent]"
---

# Improve Tests

Use this command when the user wants explicit help with automated tests for a bounded change, file, module, failure, or coverage goal.

## Inputs

- `[test target or intent]`: Optional file, module, failing test, error log, coverage goal, changed behavior, or plain-language testing intent. If omitted, inspect the current repository changes and nearby tests.
- Selected files, pasted failures, or coverage output may be treated as the intended scope when the tool provides them.

If the testing target, desired mode, or edit permission is unclear, ask one concise clarifying question before making broad changes.

## Workflow

1. Follow the `test-engineering` skill as the authoritative procedure, including its references and output contract.
2. Establish the exact testing scope and mode:
   - for current changes, inspect `git status --short --branch` and the relevant diff;
   - for named files or modules, inspect the production code and nearby tests;
   - for failing tests, read the failure output and identify the exact test command when available;
   - for coverage work, inspect the coverage report and target meaningful untested behavior.
3. Determine whether the user wants a plan, test implementation, failure/flakiness debugging, coverage improvement, or test review.
4. Match the project's existing test framework, fixtures, helpers, naming, and assertion style.
5. Add or update tests only within the confirmed scope. Prefer behavior-focused, deterministic, parallel-safe tests that avoid over-mocking.
6. Run the narrowest relevant test command first, then broader validation when the touched behavior crosses shared boundaries. If checks cannot run, state why.
7. For review-only requests, do not edit files; report concrete findings and validation evidence.

## Constraints

- Do not introduce a new test framework, mocking library, or fixture system unless the user explicitly asks.
- Do not weaken assertions or delete tests merely to make failures disappear.
- Do not chase coverage percentages with tests that lack meaningful assertions.
- Do not edit unrelated production code unless the user explicitly asks for a fix and the test work reveals a production defect.
- Do not invent test or coverage results.

## Output

Return:
- the testing scope and mode selected;
- tests added, updated, reviewed, or planned;
- validation commands run and their results;
- coverage results when measured;
- remaining gaps, blockers, or follow-up risks.
