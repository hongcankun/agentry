---
name: Refactor Proposal
about: Propose an internal improvement that keeps external behavior unchanged
title: "Refactor: "
labels: refactor
---

<!-- Refactor Proposal template. Fill each section; delete guidance in parentheses. Behavior stays the same; you must justify that the change is worth it and that it introduces no regression. -->

## Target Module / Scope

(The specific files, modules, or subsystem this covers.)

## Current Pain (quantified)

(Justify with data, not taste. For example:)

- Maintenance cost: (changing X forces synchronized changes in Y/Z — coupling)
- Testability: (coverage is only NN%; adding cases is hard)
- Readability / complexity: (cyclomatic complexity NN; steep onboarding)
- Performance / resources: (memory churn, hot paths, etc.)

## Refactor Direction (not a detailed design)

(Direction, not line-level design: extract an interface, split a module, introduce a pattern. State that external behavior and existing APIs stay compatible.)

## Risk and Rollback

(Blast radius, rollout/gating strategy, rollback plan.)

## Verification (critical)

(How you prove behavior is unchanged: existing tests plus new characterization tests, and a performance benchmark comparison if there is a performance goal.)

## Non-Goals

(What you will explicitly not change along the way, to prevent scope creep.)
