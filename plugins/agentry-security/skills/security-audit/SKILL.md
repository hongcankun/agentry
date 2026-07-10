---
name: security-audit
description: Perform a threat-driven security audit of code or a codebase to find real, exploitable vulnerabilities across classes like injection, auth/authz flaws, SSRF, secrets exposure, and weak crypto. Use when a user asks for a security review, security audit, threat assessment, or vulnerability hunt of code they own or are authorized to test.
---

# Security Audit

Audit code for security weaknesses and report exploitable findings with their risk and remediation. Unlike a general code review, a security audit is threat-driven: you reason like an attacker about what an adversary could do, then verify whether the code actually defends against it.

Follow these principles:
- **Authorized use only.** Do this for code the user owns or is explicitly authorized to assess (their own project, an engagement, a CTF, security research). If authorization is unclear for a third-party target, ask before proceeding. Report findings to help defenders fix them — do not produce weaponized exploits for unauthorized targets.
- **Think in threats, not lines.** Start from assets, entry points, and trust boundaries; trace untrusted data to where it causes harm. A line is only a vulnerability in the context of how data reaches it.
- **Evidence over suspicion.** Report a finding only when you can show the vulnerable path and a concrete way it is exploited. Confirm that existing guards (validation, encoding, parameterization, auth middleware) do not already neutralize it.
- **No security theater.** Do not flag defenses against threats that do not apply to the code's trust boundary, or restate hardening that adds no real protection. A clean audit is a valid result.
- **Rate honestly.** Severity is likelihood × impact, not how alarming the class name sounds. Do not inflate to look thorough.

## When to use

Use this skill when the task is to:
- run a security audit or security review of a service, library, module, or repository;
- assess a specific feature or boundary (auth flow, file upload, API endpoint, deserialization path);
- hunt for a vulnerability class across the code (e.g. injection, SSRF, IDOR);
- produce a threat assessment or risk write-up for code the user owns or is authorized to test.

For routine review of a change/diff where security is one of several concerns, use the `code-review` skill (in the `agentry-code-quality` plugin) instead; reach for this skill when security is the primary objective.

## Expected input

Gather as much of the following as available:
- the audit scope and target (repo, paths, services, or a specific feature/boundary), and confirmation it is owned or authorized;
- the assets worth protecting (user data, credentials, funds, availability) and who the relevant attackers are (anonymous internet user, authenticated user, insider);
- trust boundaries and entry points (network endpoints, CLI, file/IPC inputs, message queues, third-party callbacks);
- the languages, frameworks, and security-relevant libraries in use, and the deployment context (internet-facing vs internal);
- any prior audit findings, threat model, or known-risky areas to focus on.

If scope is ambiguous, default to auditing the code paths reachable from untrusted input, and ask only when authorization or the target boundary cannot be determined.

## Workflow

### 1. Establish scope, authorization, and the threat model
Confirm what you are auditing and that it is authorized. Identify the assets to protect, the relevant attackers and their capabilities, and the trust boundaries the code sits behind. Use `references/threat-modeling.md` to frame this. Note the stack and deployment context, since they change which threats apply.

### 2. Map the attack surface
Enumerate every entry point where untrusted data or actions cross a trust boundary: HTTP routes and parameters, headers and cookies, file uploads, deserialization, CLI args and env, IPC/queues, and third-party webhooks. Trace how untrusted input flows through the code toward sensitive sinks (queries, commands, file paths, responses, auth decisions). Prioritize the most exposed and most damaging paths.

### 3. Assess each relevant vulnerability class
Walk the attack surface against the catalog in `references/vulnerability-classes.md` (injection, XSS, SSRF, path traversal, authN/authZ & IDOR, insecure deserialization, secrets exposure, weak crypto/randomness, sensitive-data exposure & logging, CSRF, unsafe file handling, race/TOCTOU, dependency/supply-chain, misconfiguration). For each candidate, read the surrounding code — callers, guards, framework behavior — to decide whether the defense actually holds.

### 4. Confirm findings with evidence
For each candidate vulnerability, establish the concrete exploit path: the untrusted source, the route it takes, the sink it reaches, and the resulting harm. Pass it through the confidence gate in `references/risk-rating-and-reporting.md` and drop anything you cannot substantiate. When you confirm a vulnerability, sweep the codebase for sibling instances of the same pattern (sink, helper, or anti-pattern) so the fix addresses every occurrence, not just the one you found. When the environment allows, corroborate with the project's own tooling (dependency/secret scanners, SAST, tests) and treat their confirmed results as evidence — but verify, do not just forward raw scanner output.

### 5. Rate risk
Assign each confirmed finding a severity from likelihood × impact (Critical/High/Medium/Low/Info) using `references/risk-rating-and-reporting.md`. Keep exploitable, boundary-crossing issues separate from defense-in-depth hardening suggestions.

### 6. Report with remediations
Deliver the audit in the format under **Output**. Every finding gets a concrete, actionable remediation — the secure pattern, not just "sanitize input".

## Output

Default to a structured audit report with:
- a **scope & threat model summary**: what was audited, the assets and attackers considered, and the trust boundaries — so the reader knows what the rating is relative to;
- **findings grouped by severity**, each with: `location` (`file:line` or component) + vulnerability class + the exploit scenario (untrusted source → path → sink → impact) + a concrete remediation (show vulnerable → fixed code when it clarifies the fix);
- **validation evidence** when tools or tests were run (what confirmed the finding);
- a **risk summary table** (severity → count) and an explicit overall posture verdict (e.g. critical exposure / needs remediation / acceptable with noted hardening).

Acknowledge meaningful defenses already in place, not only weaknesses. If you find no exploitable issues, say so plainly and report the residual hardening opportunities (if any) as Info — do not manufacture findings.

## References

- `references/threat-modeling.md`: how to map assets, entry points, trust boundaries, and data flows, with STRIDE-style prompts to drive coverage and prioritization.
- `references/vulnerability-classes.md`: the catalog of vulnerability classes to hunt — what to look for and the typical exploit for each.
- `references/risk-rating-and-reporting.md`: the likelihood × impact rating scale, the pre-report confidence gate against false positives/security theater, and the finding/report format.
