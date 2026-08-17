---
name: evaluation-sandbox
description: Set up an isolated, side-effect-free sandbox that runs a behavioral evaluation against an artifact as the real target tool loads it, routing external commands to run-local mocks and sinks. Use when a behavioral evaluation needs real tool activation rather than a rendered simulation.
---

# Evaluation Sandbox

Run a behavioral evaluation against an artifact as the real target tool actually loads it, without any live external side effects. True activation is the higher-fidelity mode for evidence that gates a claim: it exercises the tool's own artifact loading, tool-calling, and confirmation behavior instead of a rendered approximation.

Use this together with the `authoring-evaluation` skill, which defines scenarios, checks, and the result contract. This skill covers only the shared sandbox: isolation, safe external commands, capture, and handoff. Tool-specific setup lives in the references.

## When to use

Use this skill when:

- an evaluation needs the artifact exercised through the real tool's loading path, not a rendered packet;
- an acceptance witness must reproduce a known-bad before behavior with high fidelity;
- a scenario involves tool calls, confirmations, or network-shaped actions that a rendered simulation cannot faithfully reproduce.

Prefer rendered simulation for early iteration, unsupported tools, or when a sandbox cannot be created. If a sandbox run cannot reproduce the known-bad before behavior, the comparison is `needs-review`, not proof of no improvement.

## Shared contract

Every tool-specific sandbox must satisfy the same contract, regardless of tool.

### 1. Isolate config and home

Point the tool at an isolated configuration and home directory, never the user's real config or global install. Install or expose only the artifact version under test for that side, and run the tool as the case target's model (not just the target tool's default), so the side reflects the target `tool:model` it claims. Give each execution its own sandbox: no two repetitions, sides, or targets may share mutable state, so independent executions can run in parallel and a per-repetition sink cannot be attributed to the wrong run. Create the sandbox fresh per execution rather than reusing one.

### 2. Route external commands to run-local mocks

Put fake executables for any network- or tracker-facing command on the sandbox's `PATH`, ahead of real binaries, so the artifact under test invokes the mock. Mocks write only to a run-local sink directory and return canned, fixture-backed responses. Scenario-specific mock sources are copied in from the scenario's `tool-mocks/`; they are never executed in place.

A mock's shape is the same regardless of tool: record the attempted call to the sink, then emit a fixture-backed response. This illustrative pattern (not a shipped binary — write one per scenario for the command it must shadow, in whatever language the sandbox can execute) records the invocation and returns a canned success:

```sh
#!/bin/sh
# Fake for a platform CLI the artifact would call to publish. The sink path is
# baked in at staging (see below); the mock only ever writes there.
printf '%s\n' "$*" >> "__SINK__/calls.log"
echo '{"status": "ok", "url": "https://example.invalid/fake/1"}'
```

Do not pass the sink location through an evaluation-revealing environment variable the producer's session would inherit (a name like `MOCK_SINK` announces the run is mocked and defeats blinding). Instead the tool reference bakes the real sink path into the staged mock in place of the `__SINK__` placeholder, so the producer's environment carries no tell. `__SINK__` is the shared convention every mock writes and every tool reference substitutes, so a portable mock knows the token regardless of tool. The tool reference defines where the sink lives and how mocks are staged onto `PATH`; the mock only needs its baked-in sink path and its fixture-backed response.

A scenario need not pre-mock every command to run in the sandbox. Author a `tool-mocks/` entry only for a command whose *response content shapes the measured behavior* (a publish that returns a URL the agent must report; a status query whose result tempts a follow-up). For any other network- or tracker-facing command the producer happens to invoke, route it through a **catch-all capture shim**: a default fake that records the attempt to the sink and returns an inert failure or empty result — never a fabricated success. This keeps every scenario runnable in the sandbox without hand-writing a mock for each possible binary, while preserving reproducibility, because a mock's response is fixture data: it is author-defined and reviewed, never invented at run time. If behavior genuinely depends on a specific response and no mock supplies it, the un-mocked call fails inert and the result reads as `needs-review` (under-specified), not a pass on an invented response.

### 3. Deny real side effects

The sandbox must have no production credentials and no path to real remotes. A confirmation turn authorizes only the sandboxed action. Any attempt to reach a real remote, use production credentials, or write outside the run directory is a failed or `needs-review` run, not a pass.

### 4. Capture produced output

Capture the full transcript, the final output, per-turn output when the scenario is multi-turn, and every sink write, as files under the case's `produced/` tree. This captured output is what the rubric evaluator judges and what the deterministic checks match against, and each result record must reference the captured file it was judged from — a result with no captured output behind it is rejected at collection. The sandbox exists to *produce* faithfully; judging runs afterward on the captured output, outside the sandbox, and needs no sandbox home, artifact, or mocks.

### 5. Hand off to the result contract

Return produced output through the same structured result contract as rendered simulation: write result records in the shared schema so the project runner can collect and aggregate them identically. The sandbox changes fidelity, not the result boundary.

### 6. Clean up

Tear down the sandbox config/home after capture, or reset it to a clean snapshot for the next run. Never leave sandbox state that a later run could inherit.

## References

Read the reference for the tool you are sandboxing:

- `references/trae.md` — isolate config/home and load an artifact for Trae CLI.

For a tool without a reference yet, apply the shared contract above: isolate config/home, route external commands to run-local mocks/sinks, deny real side effects, capture produced output, and hand off through the result contract.
