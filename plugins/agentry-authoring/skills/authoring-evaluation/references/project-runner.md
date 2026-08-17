# Project Runner Contract

The reference workflow, scenario file format, and structured schemas for a behavioral evaluation. A repository provides a project runner around this contract; another repository may represent the same fields in its own structured format, but the schema markers, comparison semantics, side-effect boundaries, and orchestrator/result contract stay the same.

## Roles and phases

The runner and the orchestrator exchange structured data across three phases:

| Phase | Who | Input | Output |
| --- | --- | --- | --- |
| prepare | project runner | artifact path, scenarios, fixtures, optional comparison refs, targets | run manifest + cases |
| execute | orchestrator (active agent/runtime) | run manifest + cases | structured result records + optional human summary |
| collect | project runner | result records | scorecard + exit status |

A convenience `run` may drive prepare → invoke the configured runtime executor → collect. This does not make the runner the orchestrator: `run` still relies on the structured result boundary. `run` requires an explicitly named orchestrator executor — either a structured `tool:model` (run through that tool's known CLI with the model pinned) or a freeform command (the escape hatch for a custom binary or wrapper). The executor is the process host, independent of the evaluation target; its identity is never inferred from a target. When you do not want to name an executor, use `prepare` instead, then invoke the orchestrator manually and run collect once result files exist.

Scenario execution is isolated and parallelizable. Each case is immutable; each scenario, side, and target writes to a unique path; aggregation happens only during collect.

## Schema markers

Every structured artifact carries a schema marker and integer major version. Parsers reject unknown markers and unsupported majors rather than guessing.

- Scenario frontmatter: `schema = "agentry.authoring-evaluation.scenario"`, `schema_version = 1`.
- Run documents (both the run manifest and each case): `schema = "agentry.authoring-evaluation.run"`, `schema_version = 1`.
- Result records: `schema = "agentry.authoring-evaluation.result"`, `schema_version = 1`.

A run comprises two document kinds that share the run schema because `prepare` emits them together in one pass: the run manifest (an index) and one case per scenario/side/target (a self-contained execution unit). They are told apart by a `run_document` field (`"manifest"` or `"case"`), and consumers also know which they hold by access path — collect reads `manifest.json`, then loads each case from the path the manifest points at. Result records version independently, so result compatibility can evolve separately.

## Scenario file format

Scenarios are structured Markdown: a `+++`-fenced TOML frontmatter block followed by a Markdown body. Prompt and turn content live in `## Heading` sections referenced from the frontmatter, so long content stays ergonomic while the frontmatter parses with a standard TOML parser (no YAML dependency).

Required fields: `schema`, `schema_version`, `id`, `artifact` (path), `kind` (`skill`/`command`/`agent`/`rule`), `baseline_failure`, and a non-empty `[[checks]]` list. Each check needs `id`, `type`, `target` (`final`, `transcript`, or `turn:<id>`), and `required`; rubric checks add `expect`, deterministic checks add their operand (`value`, `pattern`, `field`, or `phrases`). Optional: `description`, `baseline_rationale`, `pressure`, `[fixtures]`, `evidence_tier`, `repetitions`/`stability_threshold`, and `[interaction]` + `[[turns]]` for multi-turn. The effective `stability_threshold` must not exceed `repetitions` (you cannot require more consistent passes than runs). A run may also override the bar for every scenario at once with the runner's `consistent/total` evidence option, recorded in the scorecard.

```markdown
+++
schema = "agentry.authoring-evaluation.scenario"
schema_version = 1
id = "review-publishing-sequencing"
artifact = "plugins/agentry-code-quality/skills/review-publishing/SKILL.md"
kind = "skill"
baseline_failure = "The agent reads existing threads before deriving findings from the diff."
pressure = "The remote discussion is noisy and contains stale, refuted comments."
evidence_tier = "acceptance"

[fixtures]
diff = "fixtures/stale-comments.diff"
comments = "fixtures/stale-comments.json"

[[checks]]
id = "findings-first"
type = "rubric"
required = true
target = "transcript"
expect = "Derives findings from the diff before using existing comments only for dedupe."
+++

## Prompt

Review this changed PR and prepare publication guidance.

## Context

The diff contains a real regression; the remote discussion contains stale comments.
```

Multi-turn scenarios add `[interaction]` with `mode = "multi-turn"` and `[[turns]]` whose `body` names a `## Heading` section; checks may then target `turn:<id>`.

## Scenario layout

Keep scenarios in a plugin-level `eval/` tree keyed by artifact kind and artifact, outside normal component roots so packaging and normal artifact discovery ignore them:

- `plugins/<plugin>/eval/skills/<skill>/<scenario>.md`
- `plugins/<plugin>/eval/commands/<command>/<scenario>.md`
- `plugins/<plugin>/eval/agents/<agent>/<scenario>.md`
- `plugins/<plugin>/eval/rules/<category>/<rule-name>/<scenario>.md`

Scenario `fixtures/` and scenario-specific `tool-mocks/` live under the same subtree. Rule scenarios may live near the plugin or repository area that owns the behavioral pressure, but rule activation is modeled by rule path and execution mode, not by plugin membership. These trees must never be packaged, installed, or discovered as shippable artifacts.

## Run manifest

The run manifest is an index: run metadata (fixed `sides`, targets, mode, an optional pinned rubric evaluator, and a `runner` provenance tag — the generating runner's name and version) plus, per scenario, identity (id, artifact, kind, suite path, baseline failure) and one case reference per scenario/side/target. Check definitions and execution params do not live in the manifest — they travel in the self-contained cases — so the manifest stays a lightweight scenarios index. It carries `run_document = "manifest"`. A single-side run has only `sides.baseline`; a comparison run adds `sides.variant` and collect compares variant outcomes against baseline outcomes. A side with `without_artifact: true` intentionally omits the artifact bundle for that side.

## Cases

A case (`case.json`) is a self-contained execution unit for one scenario, side, and target, and its directory is an on-disk bundle: `case.json` is an index of structure, metadata, and references, while every content-shaped input is a file copied beside it. It carries `run_document = "case"`, the artifact kind, rule path when evaluating a rule, execution params (repetitions, stability threshold, tier), the return-scope and side-effect policy, a `judge` block naming the pinned rubric evaluator (or null when the orchestrator judges with its own runtime), and the **full check definitions including `expect`** — everything one execution needs to produce and judge without consulting the manifest. (The *packet* is the prompt the orchestrator constructs from a case and hands to the producer; the case is the descriptor it builds that packet from.)

The case holds the expected criteria because the rubric evaluator needs them. Keeping them out of the *producer's* prompt is the orchestrator's runtime duty at prompt-construction time, not a property of the case file: the orchestrator builds the producer packet from the case's prompt/context/turns/fixtures/artifact and withholds each check's `expect`, then supplies those criteria only to the (independent) rubric evaluator.

Content the producer reads travels as referenced files under the case directory, not inlined into `case.json`:

- the artifact under test as standalone files under `artifact/` (a skill's `references/` and support files come along, not just the entry file); the case keeps the canonical repo-relative identity separate from the copied-bundle paths, naming the entry file to read first and listing every copied file;
- the prompt, context, and each turn body as files under `prompt/` (`prompt/prompt.md`, `prompt/context.md`, `prompt/turns/<id>.md`), written body-only from the scenario's filtered sections;
- fixtures under `fixtures/`, referenced by name;
- scenario-specific tool mocks under `tool-mocks/`, copied per case so mocks never collide between scenarios; for true activation the executor stages a case's tool mocks into an isolated per-repetition sandbox bin at run time.

The runner also writes an **orchestrator brief** (`prompt/producer-brief.md`) and pre-creates an empty `produced/` directory. The brief is read by the orchestrator, never handed to the producer: it lists, by path, the case materials and the rules for composing the producer prompt — present it as a realistic task, do not cite the paths or use evaluation vocabulary (artifact, fixture, case, scenario, evaluation, check, repetition), carry the mode-appropriate safety guidance, and withhold every check's expected criteria. The brief is mode-aware: in **rendered** mode it inlines the guidance and data and has the producer return proposed output (draft-only, since nothing contains real effects); in **sandbox** mode the guidance is installed and self-activated by the target tool (not inlined), tool mocks are staged into the sandbox bin, and the producer acts normally because the isolated environment — fakes, sinks, no real credentials — contains effects rather than the producer holding back. The orchestrator composes the producer prompt per the brief, captures each repetition's output under `produced/`, and each result record references that captured file as `produced_output`. Blinding is thus the orchestrator's captured runtime duty; the brief makes its inputs and rules deterministic and inspectable.

This keeps `case.json` small, avoids duplicating large text across every side, target, and repetition, and gives the true-activation sandbox real files to stage.

## Result records

Results are newline-delimited JSON, one record per line, and are the only canonical machine-readable output the collect phase consumes. A human-readable summary may also be written, but it is derived from these records, not a second source of truth.

Each record includes:

- schema fields: `schema` (the run schema) and `schema_version`;
- identity: `record_type` (`check` or `scenario`), `run_id`, `scenario_id`, `artifact`, `artifact_kind`, `side`, `target`, `repetition`;
- result: `outcome` (`pass`/`fail`/`needs-review`), `rationale`;
- provenance: `producer` (`{tool, model}`), `produced_output` (run-relative path to the captured producer output the judgment is based on), and `evidence` (`{source_path, quote}`, an exact span from the produced output);
- evaluator metadata: rubric-evaluator id and model where applicable, plus timestamp and execution mode.

Check-level records also carry `check_id`, check `type`, and check `target`; scenario-level records may omit `check_id`. Deterministic-check records (`required-text`, `forbidden-text`, `regex`, `json-field`, `ordered`) come from computing the operand against the captured output rather than a model judgment, so their `evaluator` metadata is the computation, not a rubric evaluator; rubric-check records carry the rubric-evaluator identity. Either way the record is type-blind to collect, which aggregates on the recorded `outcome`.

**A result must be traceable to a captured producer output.** Collect rejects a `check` record that lacks `produced_output`, whose referenced file does not exist, or whose `evidence.quote` does not appear in that file (matched tolerant of whitespace and line-ending reflow). It also rejects a second record for the same `(scenario, side, target, repetition, check_id)`. Together these make a result falsifiable: a hand-written or padded JSONL record cannot pass collection, because there is no real captured output behind it. This is why hand-authoring result records is not a valid way to "run" an evaluation — produce must happen first and be captured, then judge, then collect.

## Comparison, status, and exit status

Collect aggregates per-check outcomes into per-scenario results, computes baseline/variant deltas within a target when a variant side exists, and renders a Markdown and JSON scorecard. The scorecard carries an explicit `status` (`ok` / `no-results` / `incomplete` / `invalid`) so an empty, partial, or low-integrity run never reads like a clean pass, and a per-target provenance block (producer identity, rubric-evaluator identity, and how many checks are backed by a captured output — all derived from the records, never self-declared). Pass/fail delta is authoritative; a derived pass percentage is for scanability. A required check that fails or remains `needs-review` fails the run (nonzero exit), as does a required check that produced fewer than the case's firm expected repetition count, any missing declared coverage, or a run that scored nothing — an incomplete run is not a pass on partial evidence. Comparison classifies each scenario as improved, regressed, unchanged, or newly covered.

Collect also runs integrity cross-checks derived from the records themselves (never a self-declared flag): a **producer-not-honored** finding when a check record's producer tool or model contradicts the case's target (the wrong tool/model produced the output), an **evaluator-not-honored** finding when a case pinned a rubric evaluator but a check record reports a *different* judge model, and an **evaluator-inconsistent-across-sides** finding when a scenario's baseline and variant sides were judged by different evaluators (so a delta could be judge variance rather than a behavioral change). A missing recorded field is tolerated in the honored checks (the party simply did not report it), so they fire only on a positive contradiction. Any integrity finding sets `status = invalid` and fails the run: the evidence is untrustworthy, a stronger signal than a mere failing check. Independence of the judge is not inferred from producer/evaluator model equality — two separate invocations of the same `tool:model` are legitimately independent — but is guaranteed structurally by the produce-then-judge boundary and the requirement that every judgment reference a captured `produced_output`.

## Before/after materialization

Use the current working-tree suite, fixtures, and checks for both sides; snapshot only the artifact source per ref, from object history, without touching the working tree. Reject scenarios whose fixtures differ between the two refs unless an explicit override is given, so a fixture change cannot masquerade as a behavioral delta.
