# Threat Modeling

Frame the audit before reading code line by line. A vulnerability only matters relative to an asset, an attacker, and a trust boundary — model those first so effort goes where exposure and impact are highest.

## Assets

Identify what is worth protecting, since impact is measured against it:

- **Data** — user PII, credentials, tokens, payment data, business secrets, internal config.
- **Integrity** — correctness of records, balances, permissions, and audit trails.
- **Availability** — the service staying up for legitimate users.
- **Capability** — privileged actions (admin operations, money movement, code execution).

## Attackers and capabilities

Define who you are defending against; their access changes which threats are real:

- **Anonymous external** — reaches public endpoints with no credentials.
- **Authenticated user** — a valid low-privilege account trying to escalate or reach others' data.
- **Tenant/peer** — a legitimate user of one account/tenant probing isolation from another.
- **Insider / compromised dependency** — has elevated access or runs in-process code.
- **Network position** — can observe or tamper with traffic (relevant to transport and crypto).

## Trust boundaries

A trust boundary is any point where data or control crosses from less-trusted to more-trusted. Vulnerabilities cluster here. Common boundaries:

- client → server; internet → internal network.
- unauthenticated → authenticated; user → admin; tenant → tenant.
- application → database / OS / filesystem / other services.
- third-party input (webhooks, uploads, redirects, deserialized payloads) → your code.

For each boundary, ask: what is validated/authorized as data crosses it, and what happens if that check is missing or wrong?

## Entry points

Enumerate every place untrusted input or action enters. Each is a starting node for data-flow tracing:

- HTTP routes, query/body params, path segments, headers, cookies.
- File uploads and file/path inputs.
- Deserialization (JSON/XML/YAML/pickle/native), message-queue payloads, IPC.
- CLI arguments and environment variables.
- Third-party callbacks, OAuth redirects, signed/unsigned webhooks.

## Data-flow tracing

The core technique: follow untrusted data from a **source** (entry point) to a **sink** (where it causes effect) and check every guard in between.

```
source (untrusted input) → transformations/guards → sink (query, command, path, response, auth decision)
```

- A sink is dangerous only if untrusted data reaches it without an adequate guard for that sink (parameterization for SQL, encoding for HTML, allow-listing for paths/URLs, authorization for actions).
- Track where validation/encoding happens and whether it matches the sink. Input validated for one sink may be unsafe for another (e.g. HTML-escaped data is still unsafe in a shell command).

## STRIDE prompts

Use STRIDE to drive coverage at each boundary; map each to the catalog in `vulnerability-classes.md`:

- **Spoofing** — can an attacker impersonate a user/service? (auth, session, token validation)
- **Tampering** — can they modify data in transit or at rest? (integrity, signing, access control)
- **Repudiation** — can they deny an action due to missing/forgeable logs? (audit logging)
- **Information disclosure** — can they read data they shouldn't? (authz, sensitive-data exposure, error leakage)
- **Denial of service** — can they exhaust resources or crash a path? (unbounded work, missing limits)
- **Elevation of privilege** — can they gain capabilities beyond their role? (authz gaps, injection → RCE)

## Prioritization

You will not have time to verify everything equally. Rank paths by **exposure × impact**:

1. Internet-facing + unauthenticated + reaches a high-impact sink → audit first.
2. Authenticated but crosses a tenant/privilege boundary → next.
3. Internal-only or requires improbable preconditions → lower, note assumptions.

Record the assumptions behind each priority call so the final report's ratings are interpretable.
