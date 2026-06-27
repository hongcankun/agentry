# Assessment Tracks

Use this reference when a change crosses multiple surfaces or the right review tracks are not obvious. The goal is to choose useful coverage without turning every assessment into the same full-depth review.

## Track Selection

| Changed surface | Include these tracks | Notes |
| --- | --- | --- |
| Application or library logic | Correctness, maintainability, tests, validation | Add security when the logic touches trust boundaries, sensitive data, or dangerous sinks. |
| Public APIs, schemas, protocols, CLIs, or SDK contracts | Correctness, compatibility, tests, documentation, release risk | Check callers, generated clients, migrations, and versioning expectations when applicable. |
| Auth, authorization, permissions, identity, sessions, policy, or tenancy | Security, correctness, tests, validation | Treat this as security-sensitive even when the diff is small. |
| User input, parsing, serialization, queries, templates, shell commands, file paths, network calls, webhooks, or uploads | Security, correctness, tests, validation | Trace untrusted input to sinks and confirm existing guards still apply. |
| Secrets, cryptography, tokens, payment, financial, privacy, or audit logging | Security, correctness, tests, operations | Prefer dedicated `agentry-security` coverage when available. |
| Database schema, migrations, persistence, queues, caches, or background jobs | Correctness, compatibility, rollout risk, tests, validation | Check idempotency, backfills, ordering, retries, and rollback behavior when relevant. |
| Tests only | Test quality, behavior intent, validation | Review whether tests assert the right contract and remain deterministic; include correctness only to verify the intended behavior. |
| CI, build, packaging, deployment, configuration, or infrastructure | Validation, operations, release risk, documentation | Check trigger scope, environment assumptions, secrets handling, and rollback impact. |
| Documentation, examples, changelog, or release notes | Documentation accuracy, compatibility, release risk | Include code review only when docs claim behavior that should be verified in code. |
| Generated files or vendored output | Source-of-truth alignment, validation | Review the canonical source first, then verify generated output is synced. |

## Depth Guide

- Use narrow coverage for docs-only, test-only, or localized changes with low blast radius.
- Use multi-track coverage when the change crosses modules, public contracts, deployment paths, or security-sensitive boundaries.
- Escalate to deeper specialist review when a track can materially change the verdict.
- Record skipped tracks and why, especially when a requested specialist capability is unavailable.
