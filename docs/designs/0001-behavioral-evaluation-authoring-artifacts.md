# Design 0001: Behavioral Evaluation for Authoring Artifacts

- **ID:** 0001
- **Form:** RFC
- **Status:** Accepted
- **Answers:** https://github.com/hongcankun/agentry/issues/85
- **Author(s):** hongcankun

## Summary

Add a portable `authoring-evaluation` contract for evaluating skills, commands, subagents, and rules with fixture-backed scenarios, structured JSONL results, and before/after pass/fail deltas. Agentry will provide `/evaluate-authoring` as the evaluator command and `scripts/agentry.py evaluate` as the project runner, with true-activation sandbox preferred for acceptance evidence and rendered simulation as a fallback.

## Motivation

Agentry authoring changes need a repeatable way to show whether a skill, command, subagent, or rule behaves better after a change. The desired outcome is a portable, side-effect-free workflow that runs defined scenarios against before and after artifact versions and produces comparable per-scenario and aggregate results, with this repository providing the first project runner.

**Non-goals:** This design does not introduce mandatory PR gating, CI policy, external review publication, general agent benchmarking, a universal runner implementation, or replacement of `authoring-review`, `scripts/agentry.py validate`, or `scripts/tests`. Prompt templates can follow later once the first artifact types are proven.

## Current State

Agentry can statically review authoring artifacts through `authoring-review` and validate manifest/generated packaging through `scripts/agentry.py validate` and `scripts/tests`, but it has no repeatable behavioral evaluation workflow. The current workaround is manual before/after use of artifacts such as `review-publishing`, with no scenario corpus, structured result schema, stable comparison semantics, or side-effect-safe sandbox.

## Proposed Design

Add a portable `authoring-evaluation` skill that defines the evaluation workflow and comparison contract for authoring artifacts. The skill should stay tool-agnostic: it explains how to define scenarios, run before/after comparisons, keep runs side-effect-free, interpret pass/fail deltas, and report evidence. It does not require Agentry, `agentry.json`, Trae, Claude, or a specific script.

In this repository, implement the first runner around that portable contract:

1. **Portable capability:** `plugins/agentry-authoring/skills/authoring-evaluation/`, describing the scenario model, scenario-authoring guidance, evaluation procedure, comparison semantics, safety constraints, check semantics, result schema, and report shape.
2. **Evaluator command:** `/evaluate-authoring`, which loads the skill, executes the evaluation workflow in an active agent runtime, and emits structured JSONL results in the shared schema. It may run interactively or through a non-interactive runtime such as `traecli exec "/evaluate-authoring --run <manifest>"`, and may display a human-readable summary for direct use.
3. **Agentry project runner:** `python3 scripts/agentry.py evaluate`, which discovers Agentry artifacts from `agentry.json`, resolves canonical rules and plugin associations, materializes before/after refs, loads plugin-local scenarios, writes run manifests or packets, invokes the available agent runtime command executor when present, collects structured result files, aggregates results, reports, and sets exit status.
4. **Sandbox adapter guidance:** an `evaluation-sandbox` skill defines the shared true-activation sandbox contract, with tool-specific references such as `references/trae.md` or `references/claude-code.md`.
5. **Scenario files:** fixture-backed suites kept in plugin-level `eval/` trees outside normal component roots.

The stable boundary between the project runner and evaluator is structured data, not human prose. V1 uses JSONL as the canonical result format: `<run-dir>/results/*.jsonl`, with one result record per scenario, side, target, repetition, or check as defined by the shared schema. `agentry.py evaluate` must not parse free-form agent responses to infer pass/fail. It reads JSONL result files, validates them against the shared schema, aggregates them into a project report, and fails the run when required checks fail or remain `needs-review` under the selected evidence tier.

Every structured evaluation artifact must include a schema marker and schema version. Scenario frontmatter uses `schema = "agentry.authoring-evaluation.scenario"` and `schema_version = 1`; run manifests use `schema = "agentry.authoring-evaluation.run"` and `schema_version = 1`; JSONL result records use `schema = "agentry.authoring-evaluation.result"` and `schema_version = 1`. Parsers must reject unknown schema markers and unsupported major schema versions rather than guessing.

The Agentry project runner automates discovery and aggregation but is not required for the portable evaluation contract. A maintainer can invoke `/evaluate-authoring` directly in an agent runtime for a specific scenario and can review generated results, as long as the command writes the same JSONL result schema and preserves the same side-effect boundaries, evaluator metadata, `needs-review` rules, and before/after comparison semantics.

V1 supports two execution modes. **True-activation sandbox** is preferred for acceptance evidence: it installs or exposes the artifact through the real target tool in an isolated config/home, routes external commands to run-local tool mocks and sinks, captures transcripts and sink writes, and returns produced outputs to the same scorecard contract. **Rendered simulation** builds packets from artifact source and fixtures; it is portable, cheap, and useful for manual runs, early authoring iteration, unsupported tools, and cases where sandbox setup is unavailable, but it is lower fidelity. Rendered simulation may support acceptance evidence only when it reproduces the known-bad before behavior under the fidelity gate.

Scenario files should be structured Markdown, not prose-only checklists. Use a Markdown body with `+++` TOML frontmatter for Agentry's first implementation: the prompt and context remain ergonomic prose, while the evaluator extracts the frontmatter and parses it with Python standard library `tomllib`, adding no YAML dependency. The portable skill should define the required fields conceptually, while allowing other repositories to represent them in their own structured format. Each scenario should name the baseline behavior it is meant to change, so the before/after scorecard proves an artifact effect rather than only an after-state pass.

The `authoring-evaluation` skill should include scenario-authoring guidance, preferably as `references/scenario-authoring.md`, rather than splitting a separate skill at first. That guidance covers observed baseline failures, realistic task pressure, check selection by failure mode, side-effect fixtures and fake sinks, producer-packet filtering so expected answers are hidden from the producer, and when to merge checks into one scenario or split scenarios.

Place scenarios in a plugin-level `eval/` tree keyed by artifact kind and artifact name, for example:

- `plugins/<plugin>/eval/skills/<skill>/<scenario>.md`
- `plugins/<plugin>/eval/commands/<command>/<scenario>.md`
- `plugins/<plugin>/eval/agents/<agent>/<scenario>.md`
- `plugins/<plugin>/eval/rules/<category>/<rule-name>/<scenario>.md`

This keeps evaluation assets close to the owning plugin while avoiding `skills/`, `commands/`, and `agents/` component roots that marketplace tools may scan. Rule scenarios live under the plugin whose manifest associates the rule, so a shared rule may have scenarios in more than one plugin context when the expected behavior differs by plugin. Scenario `fixtures/` and scenario-specific `tool-mocks/` directories live under the same scenario subtree.

Reusable scenario-specific tool mock sources live under `tool-mocks/` when their behavior is specific to that scenario. The project runner or sandbox setup copies or renders them into `<run-dir>/sandbox/bin/` before execution and configures them to write only to `<run-dir>/sandbox/sinks/`. Scenario-local tool mock sources are never executed in place and are excluded from generated packaging like other eval assets. Generic tool mocks used by many scenarios belong in the `evaluation-sandbox` guidance or supporting implementation, but active fake binaries still live only under the run directory.

Prefer one scenario with multiple checks when the artifact, prompt, context, fixtures, baseline failure, and before/after refs are the same. Use separate scenarios only when the setup or behavior pressure differs. This reduces repeated context and token cost without introducing grouped-session contamination, while the report still gives granular per-check failures.

Evaluation directories are maintainer-side assets, not normal artifacts. `generate`, `install`, `inventory`, packaged plugin manifests, and any normal artifact discovery path must ignore `plugins/*/eval/` so scenario files are never exposed as skills, commands, agents, rules, or shipped skill support files. Only the project runner and evaluator workflow read these directories.

Example shape:

```markdown
+++
schema = "agentry.authoring-evaluation.scenario"
schema_version = 1
id = "review-publishing-sequencing"
artifact = "plugins/agentry-code-quality/skills/review-publishing/SKILL.md"
kind = "skill"
description = "Gather findings before reading existing threads for dedupe."
baseline_failure = "The agent reads existing review threads before deriving current findings from the diff."
baseline_rationale = "The agent treats existing discussion as prerequisite context instead of post-findings dedupe."
pressure = "The remote discussion is noisy and contains stale comments, making dedupe feel urgent."

[fixtures]
diff = "fixtures/review-publishing/stale-comments.diff"
comments = "fixtures/review-publishing/stale-comments.json"

[[checks]]
id = "findings-first"
type = "rubric"
required = true
target = "transcript"
expect = "The response derives current findings from the diff before using existing comments only for dedupe or thread-state decisions."

[[checks]]
id = "no-clean-summary-first"
type = "rubric"
required = true
target = "final"
expect = "The response does not publish or draft a clean summary before reviewing the current diff."

[[checks]]
id = "earliest-actionable-line"
type = "rubric"
required = true
target = "final"
expect = "The response anchors inline comments to the earliest actionable changed line."

[[checks]]
id = "no-ci-query"
type = "rubric"
required = true
target = "transcript"
expect = "The response treats review URL commit parameters as reviewed-revision metadata and does not query CI status by default."
+++

## Prompt

Review a changed PR and prepare publication guidance.

## Context

The diff contains a real regression. The remote discussion already contains stale refuted comments.
```

Scenarios are single-turn by default, but may define ordered interaction turns for artifacts that should ask for confirmation or request missing information. Multi-turn scenarios keep long turn content in Markdown sections and reference those sections from TOML frontmatter:

```markdown
+++
schema = "agentry.authoring-evaluation.scenario"
schema_version = 1
id = "review-publishing-confirmation"
artifact = "plugins/agentry-code-quality/skills/review-publishing/SKILL.md"
kind = "skill"
baseline_failure = "The agent publishes remote review comments without explicit confirmation."

[interaction]
mode = "multi-turn"

[[turns]]
id = "initial-request"
body = "Initial Request"

[[turns]]
id = "confirmation"
body = "Confirmation"

[[checks]]
id = "asks-before-remote-mutation"
type = "rubric"
target = "turn:initial-request"
required = true
expect = "The response asks for explicit confirmation before posting or mutating remote review state."

[[checks]]
id = "safe-after-confirmation"
type = "rubric"
target = "turn:confirmation"
required = true
expect = "After confirmation, the response prepares the publish action using the provided findings without re-reviewing unrelated files."
+++

## Initial Request

Publish these review findings to PR #123.

## Confirmation

Confirmed. Publish them.
```

In multi-turn mode, turns run in declared order and are stateful only within that scenario. Checks may target `turn:<id>`, `final`, or `transcript`. Asking for clarification, missing information, or confirmation can be expected behavior rather than a harness failure. Side-effect boundaries still apply: even after a confirmation turn, the scenario must use fixtures or a safe fake sink rather than mutating real remote state.

The Agentry project runner should support both single-run and comparison modes:

```bash
python3 scripts/agentry.py evaluate run --plugin agentry-code-quality
python3 scripts/agentry.py evaluate run --plugin agentry-code-quality --component skills
python3 scripts/agentry.py evaluate prepare plugins/agentry-code-quality/skills/review-publishing --scenario review-publishing-sequencing --run-dir .tmp/eval-runs/review-publishing
traecli exec "/evaluate-authoring --run .tmp/eval-runs/review-publishing/manifest.json"
python3 scripts/agentry.py evaluate collect .tmp/eval-runs/review-publishing --report .tmp/eval-runs/review-publishing/scorecard.md
python3 scripts/agentry.py evaluate run plugins/agentry-code-quality/skills/review-publishing --scenario review-publishing-sequencing --target trae:GPT-5.5
```

The project runner supports scoped discovery: all scenarios, all scenarios for one or more plugins, all scenarios for one or more component kinds, one artifact, or one or more scenarios. Scope and target options should be repeatable, following existing Agentry CLI conventions: repeated `--plugin`, `--component`, `--scenario`, and `--target` values are unioned, deduplicated while preserving first occurrence, and evaluated in manifest/scenario order where applicable. Component filters use the existing Agentry vocabulary: `skills`, `commands`, `agents`, `rules`, and `all`; `--component all` expands to all component kinds without duplicating explicitly listed kinds. Multiple targets produce a target matrix. The runner discovers scenarios under `plugins/<plugin>/eval/<component>/<artifact>/` and then applies `--plugin`, `--component`, artifact path, and `--scenario` filters. To avoid accidental broad runs, evaluating every discovered scenario requires an explicit `--all` when no artifact path or scope filters are provided.

Single-run mode evaluates the current artifact source against one scenario selected by `--scenario` or against the artifact's full scenario set when no scenario is selected. It emits the same per-scenario and per-check scorecard without before/after delta fields. For comparison mode, `--before` and `--after` make the project runner materialize two temporary checkouts or source snapshots, then produce and score both sides using the same scenario files, fixtures, schema, and check definitions from the current working tree. A future design may add historical-suite comparison, but v1 should reject or require an explicit flag for scenarios whose fixtures differ between refs.

Evaluation targets are a first-class run dimension. A target names the producing environment, such as `trae:GPT-5.5` or `claude-code:claude-opus-4.8`; in rendered simulation, this is the host agent/tool/model asked to produce output from the execution packet, while in true-activation sandbox mode it is the actual tool/model runtime being exercised. The project runner may prepare a target matrix, producing one isolated execution packet per scenario, side, and target. Scorecards report results per target and compare before/after only within the same target by default. Cross-target summaries are descriptive unless explicitly requested; they must not imply an artifact improved universally when only one target improved.

Behavior production in v1 supports both execution modes. In true-activation sandbox mode, the project runner materializes the before and after refs, creates an isolated sandbox per side, target, and repetition, and installs or exposes that side's artifact version through the target tool's normal loading mechanism using isolated config/home paths and run-local tool mocks. Before and after sides must not share mutable sandbox state; a reusable sandbox must be reset to a clean snapshot before each run. In rendered-simulation mode, the project runner or evaluator builds an execution packet containing the artifact kind, artifact source text, relevant manifest/rule context, scenario prompt or ordered turns, scenario context, and fixture contents. The evaluator applies the shared check semantics and writes structured result files for the project runner to collect.

Because rendered simulation can hide real activation differences or contaminate the before side with improved behavior already present in the active agent's context, v1 must prefer true-activation sandbox for the `review-publishing` witness when the target tool can be isolated. The default witness uses the known #80 -> #82 behavior boundary: the before side should reproduce at least one known-bad behavior, and the after side should remove it without regressing the other witness scenarios. If a sandbox run cannot be created for the target, rendered simulation may be used only if it reproduces the known-bad before behavior; otherwise the comparison is `needs-review`, not proof of no improvement.

The v1 flow is explicit, whether the run manifest is produced by the project runner or supplied directly to an agent runtime:

1. `prepare`: the project runner validates scenarios, resolves Agentry-specific context, and writes a run manifest plus execution packets.
2. `execute`: `/evaluate-authoring` or another active agent/runtime flow reads the run manifest, produces outputs, applies the evaluation contract, and writes structured result files.
3. `collect`: the project runner reads structured result files, validates their schema, aggregates them, emits the scorecard, and sets exit status.

`prepare` and `collect` are the primitive project-runner subcommands in v1. For convenience, `evaluate run` may orchestrate the full workflow by performing `prepare`, invoking the configured runtime executor for `/evaluate-authoring`, then running `collect`. This does not make `agentry.py` the evaluator: `run` still relies on the structured JSONL boundary. If no non-interactive runtime executor is available, `prepare` can stop after writing the manifest and tell the user how to invoke `/evaluate-authoring` manually in an agent runtime, then `collect` can run after result files exist. Humans may invoke or supervise the command and review results, but human-produced outputs are not treated as agent-behavior evidence.

| Phase | Input | Output / handoff |
| --- | --- | --- |
| `prepare` | artifact path, plugin-local scenarios, fixtures, before/after refs, targets | run manifest and execution packets under `--run-dir` |
| `execute` | run manifest and execution packets | structured JSONL result files under `<run-dir>/results/`, plus optional human-readable summary |
| `collect` | structured result files | Markdown/JSON scorecard at `--report`, plus exit status |
| `run` | same inputs as `prepare`, plus configured runtime executor | orchestrates `prepare` -> `execute` -> `collect` |

Scenario execution is isolated and parallelizable. Each execution packet is immutable, and each scenario/side/target writes produced output and structured results to a unique run path. Scenario runs must not mutate shared state or depend on execution order; aggregation happens only during `collect`. Implementations may run independent scenarios, sides, and targets in parallel. For rubric checks in comparison mode, keep the before/after pair for a single scenario and target with the same evaluator where practical, so evaluator variance does not become the measured delta.

The portable result/report contract emits:

- per-scenario result: `pass`, `fail`, or `needs-review`;
- per-check result with evidence and short rationale;
- produced-output scope: final output, per-turn output when present, and full transcript;
- aggregate summary: passed / failed / needs-review counts;
- comparison summary, only in comparison mode: improved, regressed, unchanged, newly covered;
- run metadata: artifact path, artifact kind, before ref, after ref, target, producer tool, producer model, suite path, suite schema version, rubric evaluator identity, runner version, timestamp.

JSONL result records are the only canonical machine-readable output consumed by `agentry.py evaluate collect`. `/evaluate-authoring` may also display a concise terminal summary or write a Markdown scorecard for humans running evaluations directly, but that output is derived from the JSONL records and is not a second source of truth. When a run may be collected later, `/evaluate-authoring` must write JSONL even if it also prints or writes human-readable output.

Each JSONL result record must include:

- schema fields: `schema = "agentry.authoring-evaluation.result"`, `schema_version`;
- identity fields: `record_type`, `run_id`, `scenario_id`, `artifact`, `artifact_kind`, `side`, `target`, `repetition`;
- result fields: `outcome`, `rationale`, `evidence`;
- producer metadata: `producer_tool`, `producer_model`, and execution mode;
- evaluator metadata: evaluator id/type/model where applicable, plus timestamp.

Check-level records also include `check_id`, check `type`, and check `target`; scenario-level records may omit `check_id` only when `record_type = "scenario"`. Result schema versioning is independent from scenario schema versioning so result compatibility can evolve separately.

The comparison contract should be deliberately simple: **pass/fail delta is authoritative**, with a derived pass percentage only for scanability. A revision improves a scenario when before fails and after passes; it regresses when before passes and after fails. Numeric model scores are not part of the acceptance bar in v1. A scenario with any required `needs-review` check produces a scenario-level `needs-review`, not a pass.

LLM outputs are nondeterministic, so repetition count depends on evidence tier. Exploratory authoring runs may use one repetition and should label pass/fail as provisional. Normal regression checks should default to three repetitions; only 3/3 consistent required-check outcomes are stable, and mixed outcomes are `needs-review`. Acceptance witnesses should default to five repetitions and require at least four consistent outcomes for each required check on each side before claiming stable pass or stable fail. Required checks below the threshold collapse the scenario result to `needs-review`; they are not treated as pass. Scenario metadata may override repetitions and thresholds when the reason is recorded, but the scorecard must report the effective values. When distinguishable, reports record whether instability came from producer output variance or rubric evaluator variance. Acceptance witnesses should require stable reproduction of known-bad before behavior and stable after behavior before claiming improvement.

Evaluations must avoid live external side effects in both execution modes. In rendered-simulation mode, scenarios provide fixtures and fake sinks, and the evaluator asks the producer to return proposed outputs or fake-sink writes rather than execute real mutations. In true-activation sandbox mode, the target tool runs with isolated config/home paths, no production credentials, and network-capable commands routed to executables under `<run-dir>/sandbox/bin/` that write to `<run-dir>/sandbox/sinks/`. Confirmation turns authorize only the simulated or sandboxed action. Any attempt to call real remotes, use production credentials, execute scenario-local tool mock sources in place, or write outside the run directory is a failed or `needs-review` run.

Checks should support two classes:

- **Deterministic checks:** required text, forbidden text, regex, JSON-field presence, ordered phrase checks.
- **Rubric checks:** versioned natural-language criteria judged from the produced response, with a required rationale and evidence quote.

Deterministic checks are preferred whenever they are strong enough. Choose check types to match the baseline failure: use literal or regex checks for required or forbidden output elements, ordered checks for sequence failures, structured checks for machine-readable fields, and rubric checks for semantic behavior. Rubric checks are still part of v1 because the motivating behavior is semantic: for example, proving that review publication gathers current findings before using existing comments only for dedupe is an ordering and intent claim, not a stable substring. To reduce false confidence, every rubric check must be tied to a clear expected observable behavior and must record the evaluator identity in the report.

## Evaluator Policy

The portable skill defines three roles:

- **Project runner:** project-specific code such as `scripts/agentry.py evaluate` that discovers scenarios, resolves artifacts/refs/targets, writes manifests and packets, invokes or coordinates an evaluator, validates JSONL result schema, aggregates results, renders reports, and sets exit status. It does not define check semantics.
- **Producer:** the active agent, subagent, or sandboxed tool/model runtime that produces observable output from execution packets.
- **Rubric evaluator:** the active agent or a human reviewer that judges semantic rubric checks from produced output.

`/evaluate-authoring` is the standard evaluator/executor for active-agent runs. It reads the run manifest, performs or coordinates producer and rubric-evaluator work, applies the shared deterministic and rubric check semantics, and writes JSONL result records. It may also show a human-readable summary, but JSONL remains the source of truth.

Humans may invoke or supervise `/evaluate-authoring` and may supply rubric judgments when recorded in JSONL with evaluator identity. Human-produced outputs are not agent-behavior evidence and must not be used for acceptance witnesses.

Producer target identity (`tool`, `model`) is distinct from rubric evaluator identity. Semantic checks should use the same rubric evaluator across compared targets where practical. For before/after comparisons, the same rubric evaluator should judge both sides of a scenario and target in one pass where practical; otherwise required rubric deltas default to `needs-review`.

If required rubric results are missing, ambiguous, conflicting, unverifiable, or unmatched, the affected check is `needs-review`, not pass.

Rules should be first-class artifacts in the portable skill. In Agentry, a rule scenario can target either:

- an individual canonical rule path, such as `rules/code-quality/code-review.md`; or
- an effective plugin context, such as `agentry-code-quality` with its associated rules from `agentry.json`.

For Agentry rule evaluation, the project runner or evaluator should render an effective prompt envelope that includes the canonical rule text and, when plugin context is requested, the manifest association that would activate it. It should not depend on marketplace packaging because plugin formats do not deliver rules. When tool-specific activation matters, the fixture should model the project-local `.trae/rules/` or `.claude/rules/` symlink state as local context rather than requiring a real global install. The portable skill should describe this as an activation-context requirement: evaluate rules as active guidance in context, not as isolated Markdown.

The first committed suite should use `review-publishing` as the acceptance witness because it is the motivating case and has known before/after behavior from recent review workflow corrections. Seed scenarios should cover at least:

- gather current findings before reading existing comments for dedupe;
- anchor inline comments to the earliest actionable changed line;
- treat review URL commit parameters as reviewed-revision metadata, not as a reason to query platform CI by default;
- publish or draft a clean summary only after the review found no current findings.

## Alternatives Considered

**Static authoring review only.** This keeps the workflow simple, but it cannot show before/after behavioral improvement. It remains complementary: run `authoring-review` for clarity, consistency, and portability, then run evaluation for behavior.

**Agentry-specific runner as the whole feature.** A command in `scripts/agentry.py` alone would solve this repository's mechanics, but it would not be reusable as an authoring capability and would push portable behavior guidance into repo-local code. The chosen design makes the skill and `/evaluate-authoring` result schema the contract and treats `scripts/agentry.py` as Agentry's project runner.

**Tool-specific sandbox skills only.** Separate `trae-evaluation-sandbox`, `claude-code-evaluation-sandbox`, and similar skills would keep each tool self-contained, but they would duplicate the shared sandbox safety model: isolated config/home, fake remotes, transcript capture, cleanup, and scorecard handoff. The chosen design uses one generic `evaluation-sandbox` skill with tool-specific references, and can split a tool into its own skill later if its workflow becomes large or independently useful.

**Project runner directly invokes a configured model.** Direct model invocation would make `evaluate-authoring` feel complete in one command, but it would also introduce configuration, authentication, availability, and reproducibility concerns into the local script. The chosen design has the project runner prepare manifests and collect structured results while `/evaluate-authoring` or another active agent/runtime flow performs the produce/judge work.

**General-purpose test cases in `scripts/tests`.** Unit tests are the right home for project-runner behavior, but they are too implementation-focused for extension behavior. Authoring scenarios need to live near extension workflows and describe observable agent outcomes, not Python internals.

**Repo-level scenario tree.** A repo-level `evals/authoring/` tree would be simple to enumerate, but it separates scenarios from the plugin context they exercise and makes them easier to miss during authoring changes. Plugin-level `eval/` trees are the chosen design because they keep scenarios near the owning plugin while avoiding normal component roots that marketplace tools may scan.

**Golden transcript snapshots.** Exact output snapshots make regressions easy to detect, but they are brittle for LLM-shaped output. The chosen design uses deterministic checks only where stable, and rubric checks where behavior is semantic.

**YAML frontmatter.** YAML frontmatter would match many existing Markdown conventions, but this repository's scripts do not currently parse YAML. TOML frontmatter gives the same Markdown-body ergonomics while staying parseable with Python standard library `tomllib`.

**Full CI gate from day one.** CI would make evaluation visible, but it would prematurely turn a still-new comparison method into policy. The chosen design emits reports that can be attached to PRs; enforcement can be proposed separately after the signal is trusted.

## Drawbacks

This design adds several durable contracts at once: scenario layout, Markdown plus TOML scenario schema, JSONL result records, runner/evaluator roles, and sandbox expectations. The v1 slice is therefore larger than a simple skill addition, and true-activation sandbox setup may be expensive for each target tool. Rendered simulation remains useful but lower fidelity, so the first witness must prove the chosen mode can reproduce known-bad behavior before improvement claims are trusted.

## Prior Art

Several established testing and evaluation patterns apply, but none maps exactly to Agentry's authoring artifacts:

- **Prompt and LLM evaluation frameworks** such as promptfoo, OpenAI Evals, Braintrust, LangSmith, Langfuse, DeepEval, and Ragas use datasets or scenarios, deterministic assertions, model- or human-judged rubrics, run metadata, and comparison over time. The lesson for this design is to combine deterministic checks with rubric checks, record evaluator identity, and treat the scorecard as evidence rather than an informal note.
- **Rule and policy test harnesses** such as ESLint `RuleTester`, Semgrep rule tests, and OPA/Rego tests use nearby fixtures to validate policy behavior against positive and negative examples. The lesson is to keep scenarios discoverable near the plugin context they exercise and to make rules first-class evaluation targets.
- **Skill-authoring TDD and snapshot-testing patterns** show both sides of the evaluation shape: guidance should be tested from an observed baseline failure through a revised artifact, while whole-transcript golden outputs become brittle when output is intentionally flexible. The lesson is to record the weak baseline behavior, the rationale or pressure that triggered it, and the before/after delta; checks should match that failure mode instead of defaulting to exact full-output matching.

The resulting shape is deliberate: prompt-eval style scenarios and scorecards, rule-test style nearby fixtures, and snapshot-test restraint around brittle exact output matching. Agentry should reuse those lightweight patterns, not the hosted-platform machinery, large benchmark environments, provider registries, dashboards, tracing systems, or default CI gates that many full evaluation products include.

## Impact

This reaches:

- `plugins/agentry-authoring`, adding an `authoring-evaluation` skill with scenario-authoring guidance, a thin command wrapper that emits structured JSONL results, and an `evaluation-sandbox` skill with initial tool-specific references for true-activation setup guidance;
- `scripts/agentry.py`, adding the Agentry project runner `evaluate`;
- `scripts/tests`, covering project-runner behavior: scenario discovery, artifact selection, manifest/result schema validation, normal-discovery and generated-packaging exclusion, result aggregation, report generation, and rule association handling;
- plugin-level `eval/` scenario directories for Agentry's acceptance witness;
- `agentry.json`, generated plugin packaging, and plugin/root README catalog entries for new extension artifacts;
- dogfooding symlinks if the new skill or command is enabled locally.

This leaves untouched:

- existing `validate` and `generate` semantics;
- existing authoring-review behavior;
- marketplace install behavior, except for packaging the new skill and command;
- scenario directories and fixtures, because they are ignored by normal artifact discovery and excluded from generated packaging;
- release versioning, unless this lands in an explicit release-prep PR;
- CI and PR gating policy.

## Rollout and Rollback

Roll out as one useful v1 capability slice, then expand. This slice may land across multiple PRs, but it is not complete until the pieces work together:

1. V1 slice: add the portable `authoring-evaluation` skill with scenario-authoring guidance, thin `/evaluate-authoring` command with structured JSONL result output, Agentry project runner, rendered-simulation mode, scenario discovery, manifest/result schema validation, generated-packaging exclusion, deterministic and rubric check semantics, result aggregation, report format, unit tests, and the first four single-turn, single-target `review-publishing` witness scenarios. Include true-activation sandbox through `evaluation-sandbox` in this slice when it can land without blocking the first useful path; otherwise keep it as the preferred evidence path and use rendered simulation only under the fidelity gate. This proves the skill contract, runner/evaluator boundary, evaluator policy, and before/after comparison together.
2. Follow-up PRs: add more tool sandbox references, scenarios, artifact kinds, multi-turn coverage, and target-matrix coverage after the witness suite produces useful evidence.
3. Later proposal: decide whether to add CI visibility or PR gating once the local reports are trusted.

No migration is needed because this is additive. Existing workflows continue to use `validate`, unit tests, and authoring review.

Rollback is straightforward: remove the new skill/command registration, project-runner entry point, scenarios, and docs. Since no persistent external state or schema migration is introduced, backing out leaves existing extension packaging unchanged after regeneration.

## Risks

- **False confidence from weak scenarios.** Mitigate by requiring each scenario to state observable expected behavior and by seeding v1 with known `review-publishing` regressions.
- **Producer and rubric evaluator nondeterminism.** Mitigate with deterministic checks where possible, repeated runs for important scenarios, recorded evaluator and target metadata, fixture-backed prompts, `needs-review` for unstable required checks, and pass/fail deltas instead of free-form numeric scoring.
- **Historical suite drift.** Mitigate by using the current working tree suite, fixtures, schema, and checks for both `--before` and `--after` in v1, and rejecting implicit historical-suite comparisons.
- **Scenario format churn.** Mitigate by versioning scenario frontmatter from v1 and keeping the schema intentionally small.
- **Scenario packaging or discovery leakage.** Mitigate by keeping scenario files in plugin-level `eval/` trees outside component roots, excluding those trees from generated packaging, ignoring them in normal artifact discovery, and adding regression tests that they cannot become skills, commands, agents, rules, or shipped skill support files.
- **Rendered simulation differs from true activation.** Mitigate by preferring true-activation sandbox for acceptance witnesses, validating any rendered-simulation fallback against known `review-publishing` before/after behavior, and treating failure to reproduce known-bad before behavior as `needs-review`.
- **Rules evaluated differently from real activation.** Mitigate by deriving plugin-rule associations from `agentry.json` and rendering canonical rule text or modeled `.trae/rules` symlink context explicitly.
- **Side effects leaking into scenarios.** Mitigate by treating fixtures as the only allowed external state and requiring publication, network, or tracker actions to be represented as drafts or planned actions only.

## Observability

The success signal is the generated Markdown and JSON scorecard: maintainers can see per-scenario pass/fail/needs-review, aggregate pass rate, before/after improvement or regression counts, repetition counts, stability classification, producer versus rubric variance when distinguishable, evaluator identity, and any unresolved rubric checks. For the first acceptance witness, `review-publishing` should show stable known-bad behavior before the relevant corrections and stable fixed behavior after them, without needing live PR or tracker mutation.

## Additional Context

This RFC is the design response to issue #85 and should be implemented through the normal extension-change workflow: update canonical plugin sources, `agentry.json`, generated packaging, plugin README, and validation tests as needed.
