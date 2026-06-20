# Test Design

Use this reference when deciding what tests to add or update.

## Start from behavior

Define the contract before writing test code:
- What input, event, request, or state starts the behavior?
- What output, side effect, error, record, message, or UI state should be observed?
- What must remain unchanged?
- Which behavior failed before, or which risk is the test meant to reduce?

Name tests after behavior, not implementation. A good test name makes the expected behavior clear even before reading the body.

## Choose the test level

Prefer the cheapest test that proves the contract:

| Test level | Use when | Avoid when |
| --- | --- | --- |
| Unit | Pure logic, validation, branching, error mapping, formatting, small state transitions | The behavior depends on framework wiring, persistence, or real serialization |
| Component | A module needs realistic collaborators but not the whole app | It requires extensive fake infrastructure |
| Integration | Persistence, API boundaries, permissions, queues, framework routing, serialization, migrations | A focused unit test proves the same contract |
| End-to-end | Critical user workflows and cross-system confidence | Lower-level tests can cover the behavior clearly |

When in doubt, add one focused lower-level test plus one integration test for the highest-risk boundary instead of many overlapping tests.

## Select cases

Cover cases that can fail independently:
- happy path for the primary behavior;
- boundaries and empty values;
- invalid input and expected errors;
- permission or ownership rules;
- persistence, serialization, and migration behavior;
- retry, timeout, and cancellation behavior;
- ordering, idempotency, and concurrency when relevant;
- regression input that previously failed.

Avoid matrix explosion. If many dimensions interact, choose representative cases plus one direct test for each known interaction.

## Arrange test data

Keep setup readable and local to the test unless a fixture removes real duplication:
- Prefer factories/builders already used by the project.
- Use explicit values for fields that matter to the assertion.
- Hide irrelevant defaults behind existing helpers.
- Do not reuse mutable fixtures across tests unless the framework isolates them.

## Assert meaningful outcomes

Assertions should prove the contract:
- Assert externally visible results, not private helper calls.
- Assert exact errors or status codes when they are part of the contract.
- Assert important side effects and the absence of forbidden side effects.
- Prefer specific assertions over broad snapshots for core logic.
- Keep snapshots small and intentional when the project uses them.

## Use mocks carefully

Mock boundaries that are slow, nondeterministic, expensive, or outside the process: network calls, clocks, random generators, file systems, payment providers, queues, and feature flag services.

Avoid mocks that restate the implementation. If the test verifies only that method A called method B with no observable outcome, it is usually brittle.

## Keep tests deterministic

Control nondeterminism:
- freeze or inject time;
- seed or replace randomness;
- avoid real sleeps; use fake timers or synchronization;
- isolate environment variables and global state;
- clean up files, database records, background tasks, and network stubs;
- avoid depending on test order.

## Coverage

Coverage is useful for finding untested branches, but high coverage is not proof of high confidence. When improving coverage:
- start with uncovered branches that encode business behavior or error handling;
- add assertions that would fail for a real regression;
- do not test trivial getters, generated code, or framework boilerplate unless they carry project-specific behavior;
- report measured coverage only after running the coverage tool.
