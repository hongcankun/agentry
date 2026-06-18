---
description: Run a focused security audit of a repository, feature, boundary, or vulnerability class.
argument-hint: "[audit target or intent]"
---

# Audit Security

Use this command when the user wants an explicit security audit, threat assessment, or vulnerability hunt for code they own or are authorized to test.

## Inputs

- `[audit target or intent]`: Optional repository, path, service, feature, trust boundary, vulnerability class, branch, commit range, pull request, or plain-language audit intent. If omitted, audit the current repository with emphasis on code paths reachable from untrusted input.
- Selected files, pasted diffs, prior discussion, threat models, or known-risk notes may be treated as the intended audit scope when the tool provides them.

If authorization, scope, or the target trust boundary is unclear, ask one concise clarifying question before auditing broadly.

## Workflow

1. Follow the `security-audit` skill as the authoritative audit procedure, including its references and output contract.
2. Establish the audit scope, authorization, assets, attackers, and trust boundaries. Distinguish this from a general code review where security is only one concern.
3. Map the attack surface for the target:
   - routes, handlers, controllers, RPC methods, webhooks, and message consumers;
   - CLI arguments, environment variables, files, uploads, archives, and deserialization paths;
   - auth, authorization, session, tenant, payment, secret, cryptography, and network/file access boundaries.
4. Trace untrusted inputs to sensitive sinks and assess the relevant vulnerability classes: injection, authN/authZ and IDOR, SSRF, path traversal, XSS, CSRF, unsafe deserialization, secrets exposure, weak crypto/randomness, unsafe file handling, race/TOCTOU, dependency risk, and misconfiguration.
5. Confirm each candidate finding with concrete evidence: source, path, sink, impact, and why existing defenses do not neutralize it. Sweep for sibling instances of confirmed patterns.
6. Run relevant security checks, tests, dependency scanners, secret scanners, or targeted repros when practical. Treat tool output as evidence only after verifying it against the code.
7. Drop low-confidence claims and defense-in-depth notes that do not map to a real threat. A clean audit is valid.

## Constraints

- Audit only code the user owns or is explicitly authorized to assess.
- Do not provide weaponized exploitation guidance for unauthorized third-party targets.
- Do not edit, stage, commit, push, approve, or merge code unless the user explicitly asks in a separate instruction.
- Stay within the requested audit scope unless an adjacent issue is directly required to prove or disprove risk.
- Do not inflate severity or report speculative findings.

## Output

Return:
- a scope and threat-model summary;
- findings grouped by severity, each with location, vulnerability class, exploit scenario, impact, and concrete remediation;
- validation evidence, including checks run, skipped, or blocked;
- a risk summary table and an overall posture verdict;
- residual hardening opportunities as Info only when no exploitable issue is confirmed.
