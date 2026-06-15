# Risk Rating and Reporting

Turn confirmed vulnerabilities into honest, actionable findings. Two jobs: filter out what you cannot substantiate, then rate and report what survives.

## Pre-report confidence gate

The primary failure of an automated security reviewer is manufacturing findings — speculative issues, defenses already in place, and "security theater" that erodes trust and buries real risk. Before reporting a candidate, answer all of these:

1. **Location** — Can I cite the exact `file:line` (or component) where the weakness lives?
2. **Exploit path** — Can I name the untrusted source, the path it takes, the sink it reaches, and the resulting harm?
3. **Context** — Did I read the surrounding code (callers, guards, framework behavior) and confirm an existing defense (validation, encoding, parameterization, authz) does not already neutralize it?
4. **Boundary relevance** — Does the threat actually apply to this code's trust boundary and attacker model, or am I defending against something that cannot reach here?
5. **Defensibility** — Would a security engineer on this team agree this is a real risk worth fixing?

If any answer is "no" or "unsure", downgrade or drop the finding. Critical/High findings require explicit proof: the snippet, the concrete exploit scenario, and why existing guards do not stop it.

## Do not flag (common false positives)

- Defenses against threats that cannot reach the code's trust boundary (security theater).
- Input "unvalidated" at a sink when it is already validated/encoded/parameterized upstream for that sink.
- Missing hardening that adds no real protection given the actual attacker model.
- Theoretical crypto/randomness concerns on values that are not security-bearing (e.g. a non-security cache key).
- Generic "add rate limiting / add a WAF" suggestions with no specific abusable path.
- Issues in test fixtures, examples, or local-only tooling with no production exposure.
- Raw scanner output forwarded without confirming the path is reachable and exploitable.

Litmus test: *could I write or describe the concrete exploit, and would a defender prioritize fixing it?* If not, drop or mark it Info.

## Severity = likelihood × impact

Rate by how easily the bad path is reached **and** how much damage results — not by how alarming the class name is.

**Likelihood** — exposure (internet-facing > authenticated > internal-only), preconditions required, and attacker capability needed.

**Impact** — what the attacker gains: RCE, full data compromise, auth bypass > limited data read/modify > low-value disclosure.

| Severity | Meaning | Action |
|----------|---------|--------|
| **Critical** | Easily reached, high impact: unauthenticated RCE, auth bypass, mass data compromise, or trivially exploitable injection on an exposed path. | **Fix before release/merge.** |
| **High** | Real exploit with modest preconditions: authenticated privilege escalation/IDOR, injection behind auth, secret exposure, broken crypto protecting real data. | **Fix promptly; block if exposed.** |
| **Medium** | Exploitable only with significant preconditions, or limited impact: lower-value disclosure, DoS on a non-critical path, missing defense-in-depth that matters. | **Plan a fix.** |
| **Low** | Minor weakness or hardening gap with narrow impact and high preconditions. | **Optional / track.** |
| **Info** | Observation or defense-in-depth suggestion with no demonstrated exploit. | **Note only.** |

When unsure between two levels, state the assumption (exposure, preconditions) that would change the call. Keep exploitable boundary-crossing findings separate from Info hardening notes.

## Finding format

Lead with severity and location, then make the risk and the fix concrete:

```
[Severity] <Vulnerability class> — <file:line / component>

Exploit scenario: <untrusted source> → <path> → <sink> → <impact>.
Why it holds: <why existing guards don't stop it / preconditions>.
Remediation: <the secure pattern — what to change, concretely>.
```

- Show **vulnerable → fixed** code when it clarifies the remediation.
- Give a real remediation (parameterize this query, resolve-and-confine this path, verify the JWT signature with a pinned alg) — never just "sanitize input".
- Consolidate repeated instances of the same root cause into one finding noting that it recurs.
- Cite evidence when tooling or tests confirmed the finding.

## Report structure

1. **Scope & threat model summary** — what was audited, assets and attackers considered, trust boundaries; this anchors what the ratings are relative to.
2. **Findings by severity** — Critical → Info, each in the format above.
3. **Validation evidence** — scanners/tests run and what they confirmed.
4. **Risk summary** — a severity → count table and an explicit overall posture verdict (critical exposure / needs remediation / acceptable with noted hardening).

Acknowledge the meaningful defenses already present. If nothing is exploitable, say so and list only genuine Info-level hardening — a clean audit is a valid, valuable result.
