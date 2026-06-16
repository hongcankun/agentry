---
# Trae: always load this rule; description aids intelligent activation.
# Claude Code: ignores these keys, and loads always since `paths` is omitted.
description: When a security audit is required and the policy a change must satisfy before merging.
alwaysApply: true
---

# Security Audit

Follow the `security-audit` skill as the authoritative procedure for how to audit (threat modeling, attack-surface mapping, vulnerability classes, risk rating, findings format). The rules below are the non-negotiable project policy that governs when a security audit is required and when a change may merge.

## When to audit

- Before merging a change that touches security-sensitive code: authentication/authorization, user or untrusted input, database queries, file-system access, network/external calls, cryptography, secrets handling, or payment/financial logic.
- When adding or changing an externally reachable entry point (new endpoint, upload, deserialization path, webhook).
- Audit only code the team owns or is explicitly authorized to assess; treat unauthorized third-party targets as out of scope.

## Merge gates

A change in scope must not merge until:

- All Critical and High findings are resolved (see approval criteria).
- Any committed secret or credential is treated as a Critical finding: rotate it and purge it from version-control history, not merely delete it from the current code.
- Dependencies the change introduces or updates are free of known Critical/High vulnerabilities, or the risk is explicitly accepted.

## Approval criteria

- Block on any Critical finding (e.g. auth bypass, injection, secret exposure, data-loss risk); it must be fixed before merge.
- Do not approve while a High finding is open; resolve it or get explicit sign-off before merge.
- Never merge a change with a known, unmitigated security vulnerability.
- Rate findings by likelihood and impact; do not inflate severity, and do not block on defense-in-depth hardening alone.

## Related

- `agentry-security` plugin — the plugin this rule ships alongside.
- `security-audit` skill — the full audit procedure and references.
- `security-auditor` agent — a subagent that runs the audit in an isolated context, following the `security-audit` skill.
- `code-review` rule and skill (in the `agentry-code-quality` plugin) — general review policy and procedure that treat security as one dimension.
