"""Behavioral evaluation contract: schema constants and the collect stage.

Freestanding, stdlib-only module that owns the ``evaluate`` contract constants,
schema validation, and the collect/aggregate/report stage. It has no repo-path
globals and no dependency on the maintenance CLI, so a byte-identical copy can
run inside a skill with nothing else present.
"""

import json
import re
import shutil
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import NotRequired, TypedDict

__all__ = [
    "SCENARIO_SCHEMA", "RUN_SCHEMA", "RESULT_SCHEMA", "SUPPORTED_SCHEMA_VERSIONS",
    "FRONTMATTER_FENCE", "DETERMINISTIC_CHECK_TYPES", "RUBRIC_CHECK_TYPES", "CHECK_TYPES",
    "SCENARIO_KINDS", "SIDES", "COMPARISON_SIDES", "EVIDENCE_TIERS", "DEFAULT_EVIDENCE_TIER",
    "ScenarioSide", "Scenario", "RunManifest", "Report",
    "parse_scenario", "prepare", "collect", "write_scorecard",
]

# ---------------------------------------------------------------------------
# Behavioral evaluation (`evaluate`) contract constants.
#
# The evaluate subcommand is a structured-data broker: it prepares scenario
# cases, optionally invokes an external agent executor, and collects/validates
# JSONL result records into a scorecard. It never invokes an LLM or parses
# free-form agent prose. See docs/designs/0001-behavioral-evaluation-authoring-artifacts.md.

# Structured evaluation artifacts carry a schema marker plus an integer major
# version. Parsers reject unknown markers and unsupported majors rather than
# guessing. A run comprises two document kinds that share the run schema and are
# told apart by their `run_document` field: the run manifest (an index) and one
# case per scenario/side/target (a self-contained execution unit). Result schema
# versioning is independent from scenario/run schemas.
SCENARIO_SCHEMA = "agentry.authoring-evaluation.scenario"
RUN_SCHEMA = "agentry.authoring-evaluation.run"
RESULT_SCHEMA = "agentry.authoring-evaluation.result"
SUPPORTED_SCHEMA_VERSIONS = {
    SCENARIO_SCHEMA: {1},
    RUN_SCHEMA: {1},
    RESULT_SCHEMA: {1},
}

# Scenario frontmatter is fenced by lines that are exactly `+++`, keeping the
# Markdown body ergonomic while the TOML block parses with the stdlib tomllib.
FRONTMATTER_FENCE = "+++"

# Deterministic and rubric check type vocabularies. Deterministic checks are
# preferred whenever strong enough; rubric checks cover semantic behavior.
DETERMINISTIC_CHECK_TYPES = ("required-text", "forbidden-text", "regex", "json-field", "ordered")
RUBRIC_CHECK_TYPES = ("rubric",)
CHECK_TYPES = DETERMINISTIC_CHECK_TYPES + RUBRIC_CHECK_TYPES

SCENARIO_KINDS = ("skill", "command", "agent", "rule")

# Evaluation sides. A run always has a baseline side. When it also has a
# variant side, collect compares variant against baseline. A baseline with no
# artifact bundle represents the "without artifact" control in presence tests.
BASELINE_SIDE = "baseline"
VARIANT_SIDE = "variant"
COMPARISON_SIDES = (BASELINE_SIDE, VARIANT_SIDE)
SIDES = COMPARISON_SIDES

# Evidence tier -> (default repetitions, minimum consistent required-check
# outcomes needed to call a check stable). LLM output is nondeterministic, so a
# check below its threshold collapses to needs-review rather than pass.
EVIDENCE_TIERS = {
    "exploratory": (1, 1),
    "normal": (3, 3),
    "acceptance": (5, 4),
}
DEFAULT_EVIDENCE_TIER = "normal"


# ---------------------------------------------------------------------------
# Structured-document shapes.
#
# The three documents that cross this module's public seam are deterministic
# given their (schema, schema_version): the scenario dict `parse_scenario`
# returns, the run manifest `prepare` writes and `collect` reads, and the report
# `collect` returns and `write_scorecard` renders. Their shape is pinned here as
# TypedDicts so the contract is visible in one place and checkable, without the
# serialize/rehydrate tax a dataclass would add to data that is fundamentally
# JSON on the wire. The three seam types (`Scenario`, `RunManifest`, `Report`)
# are public; the nested shapes they compose are private (underscore-prefixed)
# module detail. `NotRequired` marks keys absent in some valid states — optional
# frontmatter, tagged-union check fields, comparison-only report sections.

class _Check(TypedDict):
    """One scenario check. `type` selects which of the optional fields apply."""
    id: str
    type: str
    target: str
    required: NotRequired[bool]
    expect: NotRequired[str]        # rubric
    value: NotRequired[str]         # required-text / forbidden-text
    pattern: NotRequired[str]       # regex
    field: NotRequired[str]         # json-field
    phrases: NotRequired[list[str]]  # ordered


class _Turn(TypedDict):
    id: str
    body: str


class _Interaction(TypedDict):
    mode: str


class Scenario(TypedDict):
    """A parsed, validated scenario suite (the output of ``parse_scenario``).

    The frontmatter fields plus the injected working keys. ``_sections`` is set
    by ``parse_scenario``; ``_dir``/``_path`` are attached by the caller before
    ``prepare`` (they locate fixtures/tool-mocks on disk), so all three are
    ``NotRequired`` from the pure-parse shape's point of view.
    """
    schema: str
    schema_version: int
    id: str
    artifact: str
    kind: str
    baseline_failure: str
    checks: list[_Check]
    evidence_tier: NotRequired[str]
    repetitions: NotRequired[int]
    stability_threshold: NotRequired[int]
    interaction: NotRequired[_Interaction]
    turns: NotRequired[list[_Turn]]
    fixtures: NotRequired[dict[str, str]]
    _sections: NotRequired[dict[str, str]]
    _dir: NotRequired[Path]
    _path: NotRequired[str]


class _Target(TypedDict):
    id: str
    tool: str
    model: str


class _Runner(TypedDict):
    name: str
    version: str | None


class _Evaluator(TypedDict, total=False):
    id: str
    tool: str
    model: str


class _SideMetadata(TypedDict, total=False):
    label: str
    without_artifact: bool


class _RunSides(TypedDict, total=False):
    baseline: _SideMetadata
    variant: _SideMetadata


class _EvidenceOverride(TypedDict):
    min_consistent: int
    repetitions: int


class _CaseRef(TypedDict):
    side: str
    target: str
    case: str


class _ManifestScenario(TypedDict):
    id: str
    artifact: str
    artifact_kind: str
    suite_path: str
    suite_schema_version: int
    baseline_failure: str
    cases: list[_CaseRef]


class RunManifest(TypedDict):
    """The run index ``prepare`` writes and ``collect`` reads (``run_document``
    ``"manifest"``). Check definitions and execution params live in the
    self-contained cases it points at, not here.
    """
    schema: str
    schema_version: int
    run_document: str
    run_id: str
    runner: _Runner
    created: str
    mode: str
    sides: _RunSides
    targets: list[_Target]
    evaluator: _Evaluator | None
    evidence_override: _EvidenceOverride | None
    scenarios: list[_ManifestScenario]


class _ProvenanceEntry(TypedDict):
    producers: list[str]
    rubric_evaluators: list[str]
    checks_linked_to_output: int
    checks: int


class _Aggregate(TypedDict):
    passed: int
    failed: int
    needs_review: int
    missing: int
    short: int
    integrity: int
    pass_pct: float


class _MissingCoverage(TypedDict):
    scenario: str
    side: str
    target: str


class _ShortCheck(TypedDict):
    scenario: str
    target: str
    side: str
    check: str
    expected: int
    got: int


class _IntegrityFinding(TypedDict):
    scenario: str | None
    target: str | None
    side: str | None
    check: str | None
    repetition: int | None
    finding: str


class _CheckReport(TypedDict):
    id: str
    type: str
    required: bool
    outcome: str
    repetitions: int
    expected_repetitions: int
    short: bool


class _SideReport(TypedDict):
    outcome: str
    checks: list[_CheckReport]


class _ScenarioReport(TypedDict):
    id: str
    target: str
    evidence_tier: str | None
    repetitions: int | None
    sides: dict[str, _SideReport]
    delta: NotRequired[str]


class _Comparison(TypedDict):
    improved: int
    regressed: int
    unchanged: int
    newly_covered: int


class Report(TypedDict):
    """The scorecard report ``collect`` returns and ``write_scorecard`` renders.

    ``targets`` here is a list of target *ids* (not full ``_Target`` descriptors,
    unlike the manifest). ``comparison`` is present only when a variant side is
    compared against a baseline side.
    The project runner derives its pass/fail exit code from ``status`` and
    ``aggregate``; that gate is the runner's policy, not part of this contract.
    """
    run_id: str | None
    runner: _Runner | None
    mode: str | None
    status: str
    evidence_override: _EvidenceOverride | None
    sides: _RunSides
    comparison_mode: bool
    targets: list[str]
    provenance: dict[str, _ProvenanceEntry]
    aggregate: _Aggregate
    missing_coverage: list[_MissingCoverage]
    short_checks: list[_ShortCheck]
    integrity_findings: list[_IntegrityFinding]
    scenarios: list[_ScenarioReport]
    comparison: NotRequired[_Comparison]


# Private stdlib-only utility copies. The collect functions below call these
# module-local ``_serialize``/``_confined_path`` so eval_contract stays freestanding
# (byte-identical to agentry.py's own copies, which non-eval code keeps using).


def _serialize(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _confined_path(base, rel_path, label):
    """Join ``rel_path`` under ``base`` and fail if the resolved path escapes."""
    root = base.resolve()
    candidate = (base / rel_path).resolve()
    if candidate != root and root not in candidate.parents:
        sys.exit(f"error: {label} escapes {base}: {rel_path}")
    return candidate


def _require_schema(data, expected, label):
    """Reject a structured artifact whose schema marker or major is unsupported."""
    schema = data.get("schema")
    if schema != expected:
        sys.exit(f"error: {label}: unknown schema {schema!r}; expected {expected!r}")
    version = data.get("schema_version")
    if not isinstance(version, int) or version not in SUPPORTED_SCHEMA_VERSIONS[expected]:
        sys.exit(f"error: {label}: unsupported {expected} schema_version {version!r}")


# Additional private stdlib-only utility copies used by the prepare stage below.
# These mirror agentry.py's own copies byte-for-byte so eval_contract stays
# freestanding (non-eval maintenance code keeps using agentry.py's versions).
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _validate_path_fragment(value, label, *, allow_nested):
    """Return ``value`` after rejecting absolute or parent-traversing paths."""
    if not isinstance(value, str) or not value:
        sys.exit(f"error: unsafe {label}: {value!r}")
    path = Path(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        sys.exit(f"error: unsafe {label}: {value}")
    if not allow_nested and (len(path.parts) != 1 or not _SAFE_NAME_RE.fullmatch(value)):
        sys.exit(f"error: unsafe {label}: {value}")
    return value


def _write_json(path, data):
    """Write ``data`` as pretty JSON, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_serialize(data), encoding="utf-8")


def _slug(value):
    """Return a filesystem-safe slug for a target/scenario id."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)


# --- collect / aggregate / report -------------------------------------------


def _normalize_for_match(text):
    """Collapse whitespace and normalize line endings for tolerant matching.

    Agents lightly reflow quotes (reindent, rewrap, CRLF), so an evidence quote
    is matched against produced output after collapsing runs of whitespace to a
    single space. A materially absent quote still fails.
    """
    return re.sub(r"\s+", " ", text.replace("\r\n", "\n")).strip()


def _validate_check_provenance(record, run_dir, label):
    """Enforce that a check result is backed by a captured producer output.

    A check record must reference ``produced_output`` (a path under the run
    dir), that file must exist, and its ``evidence.quote`` must appear in the
    file. This is what makes a result falsifiable: a hand-written record with no
    real captured output cannot pass collection.
    """
    if not record.get("check_id"):
        sys.exit(f"error: {label}: check record missing 'check_id'")
    produced_rel = record.get("produced_output")
    if not produced_rel:
        sys.exit(f"error: {label}: check record missing 'produced_output' "
                 "(results must be traceable to a captured producer output)")
    produced_path = _confined_path(run_dir, produced_rel, "produced_output")
    if not produced_path.is_file():
        sys.exit(f"error: {label}: produced_output not found: {produced_rel}")
    evidence = record.get("evidence")
    if not isinstance(evidence, dict) or not evidence.get("quote"):
        sys.exit(f"error: {label}: check record needs evidence with a 'quote'")
    quote = evidence["quote"]
    haystack = _normalize_for_match(produced_path.read_text(encoding="utf-8"))
    if _normalize_for_match(quote) not in haystack:
        sys.exit(f"error: {label}: evidence quote not found in {produced_rel}")


def _load_results(run_dir):
    """Read, schema-validate, and provenance-check every JSONL result record.

    Beyond schema, each ``check`` record must be traceable to a captured
    producer output (see ``_validate_check_provenance``) and must be unique for
    its ``(scenario, side, target, repetition, check_id)`` key, so a run cannot
    pass on hand-written or padded records.
    """
    results_dir = run_dir / "results"
    if not results_dir.is_dir():
        sys.exit(f"error: no results directory at {results_dir}")
    records = []
    seen = {}
    for jsonl in sorted(results_dir.glob("*.jsonl")):
        for lineno, line in enumerate(jsonl.read_text(encoding="utf-8").splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            label = f"{jsonl.name}:{lineno}"
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                sys.exit(f"error: {label}: invalid JSON result record: {exc}")
            _require_schema(record, RESULT_SCHEMA, label)
            if record.get("record_type") == "check":
                _validate_check_provenance(record, run_dir, label)
                key = (record.get("scenario_id"), record.get("side"), record.get("target"),
                       record.get("repetition"), record.get("check_id"))
                if key in seen:
                    sys.exit(f"error: {label}: duplicate check record for {key} "
                             f"(first seen at {seen[key]})")
                seen[key] = label
            records.append(record)
    return records


def _load_cases(run_dir, run_manifest):
    """Load and schema-validate the cases the manifest references.

    Returns a ``{(scenario_id, target, side): case}`` map. Cases are the
    authority for check definitions and execution params; the manifest only
    points at them. A case shares the run schema with the manifest and is
    identified by ``run_document == "case"``.
    """
    cases = {}
    for sinfo in run_manifest.get("scenarios", []):
        for ref in sinfo.get("cases", []):
            case_path = run_dir / ref["case"]
            if not case_path.exists():
                sys.exit(f"error: run manifest references missing case: {case_path}")
            case = json.loads(case_path.read_text(encoding="utf-8"))
            _require_schema(case, RUN_SCHEMA, str(case_path))
            if case.get("run_document") != "case":
                sys.exit(f"error: {case_path}: expected run_document 'case', got {case.get('run_document')!r}")
            cases[(sinfo["id"], ref["target"], ref["side"])] = case
    return cases


def collect(run_dir, run_manifest: "RunManifest | None" = None) -> "Report":
    """Load a run's results and cases and aggregate them into a scorecard report.

    Reads ``manifest.json`` from ``run_dir`` when ``run_manifest`` is not given,
    validates it, loads the result records and referenced cases, and returns the
    aggregated report dict. The caller renders/handles exit status.
    """
    if run_manifest is None:
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            sys.exit(f"error: no run manifest at {manifest_path}")
        run_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _require_schema(run_manifest, RUN_SCHEMA, str(manifest_path))
    records = _load_results(run_dir)
    cases = _load_cases(run_dir, run_manifest)
    return _aggregate_results(records, run_manifest, cases)


def _classify_check(outcomes, min_consistent, expected=0):
    """Collapse a check's repetition outcomes to pass/fail/needs-review.

    A check is stable pass only when at least ``min_consistent`` reps pass with
    no fail or needs-review; stable fail when at least ``min_consistent`` reps
    fail; otherwise needs-review. When ``expected`` is given, a check with some
    results but fewer than the firm expected count can never be a stable pass:
    an incomplete run is needs-review, not a pass on partial evidence. Applies to
    required and optional checks alike; required-vs-optional gating happens in
    ``_scenario_outcome``.
    """
    if not outcomes:
        return "needs-review"
    if expected and len(outcomes) < expected and outcomes.count("fail") < min_consistent:
        # Too few reps to confirm a pass; only a stable fail can still stand.
        return "needs-review"
    passes = outcomes.count("pass")
    fails = outcomes.count("fail")
    if passes >= min_consistent and fails == 0 and outcomes.count("needs-review") == 0:
        return "pass"
    if fails >= min_consistent:
        return "fail"
    return "needs-review"


def _evaluator_label(record):
    """Return a canonical judge label from a record, or None when unidentified.

    Prefer ``tool:model``; fall back to the agent ``id`` or a bare ``model`` so a
    judge can be compared across sides regardless of which identity fields it
    carries. ``None`` means the record names no judge to compare.
    """
    evaluator = record.get("evaluator") or {}
    tool, model = evaluator.get("tool"), evaluator.get("model")
    if tool and model:
        return f"{tool}:{model}"
    return evaluator.get("id") or model or None


def _evaluator_not_honored(record, pinned_evaluator):
    """True when a pinned evaluator was named but a different model judged.

    Only a *present* recorded model that differs from the pinned model counts as
    a violation; a missing recorded model is tolerated (the judge simply did not
    report its model), so this never fires on an under-specified but plausibly
    honored record.
    """
    if not pinned_evaluator:
        return False
    recorded_model = (record.get("evaluator") or {}).get("model")
    return bool(recorded_model) and recorded_model != pinned_evaluator.get("model")


def _producer_not_honored(record, target_id):
    """True when the recorded producer contradicts the case's target tool:model.

    The target is the intended producing ``tool:model``; the record's producer
    carries ``{tool, model}``. A *present* recorded tool or model that differs
    from the target's is a violation (the wrong tool/model produced the output);
    a missing field is tolerated, mirroring the evaluator check, so this never
    fires on an under-specified but plausibly honored record.
    """
    if not target_id or ":" not in target_id:
        return False
    target_tool, target_model = target_id.split(":", 1)
    producer = record.get("producer") or {}
    tool, model = producer.get("tool"), producer.get("model")
    if tool and tool != target_tool:
        return True
    if model and model != target_model:
        return True
    return False


def _aggregate_results(records, run_manifest, cases) -> "Report":
    """Aggregate JSONL records into a scorecard report structure (pure).

    ``cases`` maps ``(scenario_id, target, side)`` to that case's dict, the
    authority for check definitions and execution params (the manifest is only
    an index). ``collect`` loads the cases referenced by the manifest and
    passes them here.
    """
    manifest_scenarios = {s["id"]: s for s in run_manifest.get("scenarios", [])}
    manifest_sides_meta = run_manifest.get("sides") or {}
    comparison_mode = VARIANT_SIDE in manifest_sides_meta
    targets = [t["id"] for t in run_manifest.get("targets", [])]

    # Bucket check outcomes by (scenario, target, side, check_id).
    buckets = {}
    for rec in records:
        if rec.get("record_type") != "check":
            continue
        key = (rec["scenario_id"], rec["target"], rec["side"], rec["check_id"])
        buckets.setdefault(key, []).append(rec["outcome"])

    # Derive per-target provenance from the records themselves (never
    # self-declared): which producer(s) generated outputs, which rubric
    # evaluator judged, and how many checks are backed by a captured output.
    # The same pass collects integrity findings and, per (scenario, target),
    # the set of judge labels used on each side for the cross-side check.
    provenance = {t: {"producers": {}, "rubric_evaluators": {}, "linked": 0, "checks": 0}
                  for t in targets}
    integrity = []
    side_judges = {}
    for rec in records:
        if rec.get("record_type") != "check":
            continue
        prov = provenance.setdefault(
            rec.get("target"), {"producers": {}, "rubric_evaluators": {}, "linked": 0, "checks": 0})
        prov["checks"] += 1
        if rec.get("produced_output"):
            prov["linked"] += 1
        producer = rec.get("producer") or {}
        pid = f"{producer.get('tool')}:{producer.get('model')}" if producer else None
        if pid:
            prov["producers"][pid] = prov["producers"].get(pid, 0) + 1
        evaluator = rec.get("evaluator") or {}
        eid = evaluator.get("id") or evaluator.get("model")
        if eid:
            prov["rubric_evaluators"][eid] = prov["rubric_evaluators"].get(eid, 0) + 1
        label = _evaluator_label(rec)
        if label:
            side_judges.setdefault((rec.get("scenario_id"), rec.get("target")), {}) \
                .setdefault(rec.get("side"), set()).add(label)
        case = cases.get((rec.get("scenario_id"), rec.get("target"), rec.get("side")))
        pinned_evaluator = (case or {}).get("judge", {}).get("evaluator")
        if _producer_not_honored(rec, rec.get("target")):
            integrity.append({
                "scenario": rec.get("scenario_id"), "target": rec.get("target"),
                "side": rec.get("side"), "check": rec.get("check_id"),
                "repetition": rec.get("repetition"), "finding": "producer-not-honored",
            })
        if _evaluator_not_honored(rec, pinned_evaluator):
            integrity.append({
                "scenario": rec.get("scenario_id"), "target": rec.get("target"),
                "side": rec.get("side"), "check": rec.get("check_id"),
                "repetition": rec.get("repetition"), "finding": "evaluator-not-honored",
            })

    # Cross-side consistency: a comparison must be judged by the same evaluator
    # on both sides, or the delta could be judge variance rather than a
    # behavioral change. Flag a (scenario, target) whose baseline and variant
    # sides used different judge labels.
    for (sid, target), by_side in side_judges.items():
        baseline, variant = by_side.get(BASELINE_SIDE), by_side.get(VARIANT_SIDE)
        if baseline and variant and baseline != variant:
            integrity.append({
                "scenario": sid, "target": target, "side": "baseline/variant",
                "check": None, "repetition": None,
                "finding": "evaluator-inconsistent-across-sides",
            })

    scenarios_report = []
    aggregate = {"passed": 0, "failed": 0, "needs_review": 0}
    comparison = {"improved": 0, "regressed": 0, "unchanged": 0, "newly_covered": 0}
    # Declared (scenario, side, target) cases that produced no records at all:
    # a broken or incomplete run must not silently pass the exit-status gate.
    missing_coverage = []

    for sid, sinfo in manifest_scenarios.items():
        declared = {(p["side"], p["target"]) for p in sinfo.get("cases", [])}
        for target in targets:
            sides = {}
            tier = None
            reps_reported = None
            for side in SIDES:
                case = cases.get((sid, target, side))
                if case is None:
                    continue
                # Check definitions and execution params come from the case.
                min_consistent = case.get("min_consistent", EVIDENCE_TIERS[DEFAULT_EVIDENCE_TIER][1])
                expected_reps = case.get("repetitions", 0)
                check_defs = case.get("checks", [])
                tier = case.get("evidence_tier")
                reps_reported = expected_reps
                side_checks = []
                has_records = False
                for check in check_defs:
                    outcomes = buckets.get((sid, target, side, check["id"]))
                    if outcomes:
                        has_records = True
                    result = _classify_check(outcomes or [], min_consistent, expected_reps)
                    got = len(outcomes or [])
                    side_checks.append({
                        "id": check["id"],
                        "type": check["type"],
                        "required": bool(check.get("required")),
                        "outcome": result,
                        "repetitions": got,
                        "expected_repetitions": expected_reps,
                        "short": bool(outcomes) and expected_reps and got < expected_reps,
                    })
                if not has_records:
                    if (side, target) in declared:
                        missing_coverage.append({"scenario": sid, "side": side, "target": target})
                    continue
                outcome = _scenario_outcome(side_checks)
                sides[side] = {"outcome": outcome, "checks": side_checks}

            if not sides:
                continue
            entry = {
                "id": sid,
                "target": target,
                "evidence_tier": tier,
                "repetitions": reps_reported,
                "sides": sides,
            }
            if comparison_mode and BASELINE_SIDE in sides and VARIANT_SIDE in sides:
                delta = _compare_sides(sides[BASELINE_SIDE]["outcome"], sides[VARIANT_SIDE]["outcome"])
                entry["delta"] = delta
                comparison[delta.replace("-", "_")] += 1
            elif comparison_mode and VARIANT_SIDE in sides and BASELINE_SIDE not in sides:
                entry["delta"] = "newly-covered"
                comparison["newly_covered"] += 1

            # Aggregate counts use the variant side in comparison mode, else the
            # single present side.
            gate_side = VARIANT_SIDE if VARIANT_SIDE in sides else next(iter(sides))
            gate_outcome = sides[gate_side]["outcome"]
            if gate_outcome == "pass":
                aggregate["passed"] += 1
            elif gate_outcome == "fail":
                aggregate["failed"] += 1
            else:
                aggregate["needs_review"] += 1
            scenarios_report.append(entry)

    aggregate["missing"] = len(missing_coverage)
    # Required checks that produced fewer than the firm expected repetitions: an
    # incomplete run the exit-status gate must not treat as a pass.
    short_checks = [
        {"scenario": s["id"], "target": s["target"], "side": side, "check": c["id"],
         "expected": c["expected_repetitions"], "got": c["repetitions"]}
        for s in scenarios_report
        for side, side_data in s["sides"].items()
        for c in side_data["checks"]
        if c.get("short") and c["required"]
    ]
    aggregate["short"] = len(short_checks)
    aggregate["integrity"] = len(integrity)
    total = aggregate["passed"] + aggregate["failed"] + aggregate["needs_review"]
    aggregate["pass_pct"] = round(100.0 * aggregate["passed"] / total, 1) if total else 0.0

    # Per-target provenance for the scorecard, shaped for display.
    provenance_report = {
        t: {
            "producers": sorted(p["producers"]),
            "rubric_evaluators": sorted(p["rubric_evaluators"]),
            "checks_linked_to_output": p["linked"],
            "checks": p["checks"],
        }
        for t, p in provenance.items() if p["checks"]
    }

    # Explicit run status so an empty/incomplete/low-integrity run never reads
    # like a clean pass: no scored scenarios -> no-results; any integrity finding
    # -> invalid (evidence untrustworthy, the strongest signal); missing/short
    # reps -> incomplete.
    if total == 0:
        status = "no-results"
    elif integrity:
        status = "invalid"
    elif aggregate["missing"] or aggregate["short"]:
        status = "incomplete"
    else:
        status = "ok"

    report = {
        "run_id": run_manifest.get("run_id"),
        "runner": run_manifest.get("runner"),
        "mode": run_manifest.get("mode"),
        "status": status,
        "evidence_override": run_manifest.get("evidence_override"),
        "sides": manifest_sides_meta,
        "comparison_mode": comparison_mode,
        "targets": targets,
        "provenance": provenance_report,
        "aggregate": aggregate,
        "missing_coverage": missing_coverage,
        "short_checks": short_checks,
        "integrity_findings": integrity,
        "scenarios": scenarios_report,
    }
    if comparison_mode:
        report["comparison"] = comparison
    return report


def _scenario_outcome(side_checks):
    """Return a scenario-side outcome from its required checks."""
    required = [c for c in side_checks if c["required"]]
    gating = required or side_checks
    if any(c["outcome"] == "fail" for c in gating):
        return "fail"
    if any(c["outcome"] == "needs-review" for c in gating):
        return "needs-review"
    return "pass"


def _compare_sides(baseline_outcome, variant_outcome):
    """Classify a baseline/variant scenario pair. pass/fail delta is authoritative."""
    if baseline_outcome == "fail" and variant_outcome == "pass":
        return "improved"
    if baseline_outcome == "pass" and variant_outcome == "fail":
        return "regressed"
    return "unchanged"


def _render_scorecard_json(report):
    return _serialize(report)


def _render_scorecard_markdown(report):
    """Render a human-readable Markdown scorecard from the report structure."""
    lines = []
    lines.append(f"# Evaluation scorecard: {report['run_id']}")
    lines.append("")
    lines.append(f"- Status: {report.get('status', 'ok')}")
    runner = report.get("runner") or {}
    if runner.get("name"):
        version = f" {runner['version']}" if runner.get("version") else ""
        lines.append(f"- Runner: {runner['name']}{version}")
    lines.append(f"- Mode: {report['mode']}")
    evo = report.get("evidence_override") or {}
    if evo:
        lines.append(
            f"- Evidence override: {evo['min_consistent']}/{evo['repetitions']} "
            "(consistent/total) applied at run time"
        )
    sides_meta = report.get("sides") or {}
    baseline_label = (sides_meta.get(BASELINE_SIDE) or {}).get("label", BASELINE_SIDE)
    variant_label = (sides_meta.get(VARIANT_SIDE) or {}).get("label", VARIANT_SIDE)
    if report.get("comparison_mode"):
        lines.append(f"- Baseline: `{baseline_label}` -> Variant: `{variant_label}`")
    lines.append(f"- Targets: {', '.join(report['targets']) or '(none)'}")
    agg = report["aggregate"]
    lines.append(
        f"- Aggregate: {agg['passed']} passed / {agg['failed']} failed / "
        f"{agg['needs_review']} needs-review ({agg['pass_pct']}% pass)"
    )
    if agg.get("missing"):
        lines.append(f"- Missing coverage: {agg['missing']} declared case(s) produced no results")
    if agg.get("integrity"):
        lines.append(f"- Integrity: {agg['integrity']} finding(s) — evidence is untrustworthy")
    if report.get("comparison_mode"):
        cmp = report["comparison"]
        lines.append(
            f"- Comparison: {cmp['improved']} improved / {cmp['regressed']} regressed / "
            f"{cmp['unchanged']} unchanged / {cmp['newly_covered']} newly-covered"
        )
    # Per-target provenance, derived from the records, so a low-integrity run
    # (e.g. checks not backed by captured output) is visible at a glance.
    provenance = report.get("provenance") or {}
    if provenance:
        lines.append("")
        lines.append("## Provenance")
        lines.append("")
        lines.append("| Target | Producer(s) | Rubric evaluator(s) | Checks backed by output |")
        lines.append("| --- | --- | --- | --- |")
        for target in report["targets"]:
            p = provenance.get(target)
            if not p:
                continue
            producers = ", ".join(p["producers"]) or "(none)"
            evaluators = ", ".join(p["rubric_evaluators"]) or "(none)"
            lines.append(
                f"| {target} | {producers} | {evaluators} | "
                f"{p['checks_linked_to_output']}/{p['checks']} |"
            )
    # Integrity findings, derived from the records: a run whose producer is not
    # the case target, that ignored its pinned evaluator, or that judged
    # baseline/variant with different evaluators is invalid, not merely failing.
    integrity = report.get("integrity_findings") or []
    if integrity:
        lines.append("")
        lines.append("## Integrity")
        lines.append("")
        lines.append("| Scenario | Target | Side | Check | Rep | Finding |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        def _cell(v):
            return "" if v is None else v
        for f in integrity:
            lines.append(
                f"| {f['scenario']} | {f['target']} | {_cell(f['side'])} | {_cell(f['check'])} | "
                f"{_cell(f['repetition'])} | {f['finding']} |"
            )
    lines.append("")
    lines.append("## Scenarios")
    lines.append("")
    if report.get("comparison_mode"):
        lines.append("| Scenario | Target | Baseline | Variant | Delta | Tier | Reps |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for s in report["scenarios"]:
            sides = s["sides"]
            baseline = sides.get(BASELINE_SIDE, {}).get("outcome", "-")
            variant = sides.get(VARIANT_SIDE, {}).get("outcome", "-")
            lines.append(
                f"| {s['id']} | {s['target']} | {baseline} | {variant} | {s.get('delta', '-')} | "
                f"{s.get('evidence_tier', '-')} | {s.get('repetitions', '-')} |"
            )
    else:
        lines.append("| Scenario | Target | Outcome | Tier | Reps |")
        lines.append("| --- | --- | --- | --- | --- |")
        for s in report["scenarios"]:
            sides = s["sides"]
            side = VARIANT_SIDE if VARIANT_SIDE in sides else next(iter(sides))
            lines.append(
                f"| {s['id']} | {s['target']} | {sides[side]['outcome']} | "
                f"{s.get('evidence_tier', '-')} | {s.get('repetitions', '-')} |"
            )
    lines.append("")
    # Per-check breakdown for non-passing checks.
    breakdown = []
    for s in report["scenarios"]:
        for side, side_data in s["sides"].items():
            for check in side_data["checks"]:
                if check["outcome"] != "pass":
                    breakdown.append((s["id"], s["target"], side, check))
    if breakdown:
        lines.append("## Non-passing checks")
        lines.append("")
        for sid, target, side, check in breakdown:
            required = "required" if check["required"] else "optional"
            lines.append(
                f"- `{sid}` [{target}/{side}] `{check['id']}` ({check['type']}, {required}): "
                f"**{check['outcome']}** over {check['repetitions']} rep(s)"
            )
        lines.append("")
    missing = report.get("missing_coverage") or []
    if missing:
        lines.append("## Missing coverage")
        lines.append("")
        for m in missing:
            lines.append(f"- `{m['scenario']}` [{m['target']}/{m['side']}] produced no results")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def write_scorecard(report: "Report", report_path) -> None:
    """Emit the scorecard for ``report`` as Markdown and JSON.

    Writes the Markdown scorecard to ``report_path`` and the JSON scorecard
    alongside it (``report_path`` with a ``.json`` suffix), creating parent
    directories as needed. This is the scorecard *emission* step; deciding a
    pass/fail exit code from the report is the caller's (project runner's) gate
    policy, not part of the contract.
    """
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render_scorecard_markdown(report), encoding="utf-8")
    report_path.with_suffix(".json").write_text(_render_scorecard_json(report), encoding="utf-8")


# --- scenario parsing / validation ------------------------------------------


def _split_frontmatter(text, label):
    """Return ``(toml_text, body)`` by peeling a leading ``+++`` fenced block."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != FRONTMATTER_FENCE:
        sys.exit(f"error: {label}: missing '{FRONTMATTER_FENCE}' frontmatter fence")
    for i in range(1, len(lines)):
        if lines[i].strip() == FRONTMATTER_FENCE:
            return "".join(lines[1:i]), "".join(lines[i + 1:])
    sys.exit(f"error: {label}: unterminated '{FRONTMATTER_FENCE}' frontmatter fence")


def _parse_markdown_sections(body):
    """Return a ``{heading: content}`` map for ``## Heading`` blocks in ``body``.

    Turn and prompt/context bodies are kept as ergonomic Markdown sections and
    referenced by heading text from the TOML frontmatter, so long turn content
    stays readable instead of being crammed into TOML strings. ``##`` lines
    inside fenced code blocks are content, not headings, so a scenario body may
    embed Markdown samples without splitting the section wrongly.
    """
    sections = {}
    current = None
    buf = []
    in_fence = False
    fence_marker = None
    for line in body.splitlines():
        stripped = line.lstrip()
        # Track ``` / ~~~ fenced code blocks so headings inside them are ignored.
        if stripped.startswith("```") or stripped.startswith("~~~"):
            marker = stripped[:3]
            if not in_fence:
                in_fence, fence_marker = True, marker
            elif marker == fence_marker:
                in_fence, fence_marker = False, None
        match = None if in_fence else re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            if current is not None:
                sections[current] = "\n".join(buf).strip("\n")
            current = match.group(1).strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip("\n")
    return sections


def parse_scenario(path) -> "Scenario":
    """Parse one scenario Markdown file into a validated scenario dict.

    The returned dict is the ``Scenario`` shape; a caller attaches ``_dir``/
    ``_path`` and wraps it as ``ScenarioSide.scenario`` before ``prepare``.
    """
    label = str(path)
    raw = path.read_text(encoding="utf-8")
    toml_text, body = _split_frontmatter(raw, label)
    try:
        data = tomllib.loads(toml_text)
    except tomllib.TOMLDecodeError as exc:
        sys.exit(f"error: {label}: invalid TOML frontmatter: {exc}")
    _require_schema(data, SCENARIO_SCHEMA, label)
    data["_sections"] = _parse_markdown_sections(body)
    _validate_scenario(data, path)
    return data


def _scenario_error(path, message):
    sys.exit(f"error: {path}: {message}")


def _validate_scenario(scenario, path):
    """Enforce required scenario fields, check shapes, and turn references."""
    for field in ("id", "artifact", "kind", "baseline_failure"):
        value = scenario.get(field)
        if not isinstance(value, str) or not value:
            _scenario_error(path, f"missing required scenario field '{field}'")
    if scenario["kind"] not in SCENARIO_KINDS:
        _scenario_error(path, f"unknown scenario kind {scenario['kind']!r}; expected one of {', '.join(SCENARIO_KINDS)}")

    sections = scenario.get("_sections", {})
    interaction = scenario.get("interaction", {})
    mode = interaction.get("mode", "single-turn")
    turn_ids = []
    if mode == "multi-turn":
        turns = scenario.get("turns")
        if not isinstance(turns, list) or not turns:
            _scenario_error(path, "multi-turn interaction requires a non-empty [[turns]] list")
        for turn in turns:
            turn_id = turn.get("id")
            body_heading = turn.get("body")
            if not isinstance(turn_id, str) or not turn_id:
                _scenario_error(path, "each turn requires an 'id'")
            if not isinstance(body_heading, str) or body_heading not in sections:
                _scenario_error(path, f"turn {turn_id!r} body must reference a '## {body_heading}' section")
            turn_ids.append(turn_id)
    elif mode == "single-turn":
        if "Prompt" not in sections:
            _scenario_error(path, "single-turn scenario requires a '## Prompt' section")
    else:
        _scenario_error(path, f"unknown interaction mode {mode!r}")

    checks = scenario.get("checks")
    if not isinstance(checks, list) or not checks:
        _scenario_error(path, "scenario requires a non-empty [[checks]] list")
    seen_ids = set()
    for check in checks:
        cid = check.get("id")
        if not isinstance(cid, str) or not cid:
            _scenario_error(path, "each check requires an 'id'")
        if cid in seen_ids:
            _scenario_error(path, f"duplicate check id {cid!r}")
        seen_ids.add(cid)
        ctype = check.get("type")
        if ctype not in CHECK_TYPES:
            _scenario_error(path, f"check {cid!r} has unknown type {ctype!r}")
        target = check.get("target")
        if not isinstance(target, str) or not target:
            _scenario_error(path, f"check {cid!r} requires a 'target'")
        if target.startswith("turn:"):
            ref = target.split(":", 1)[1]
            if ref not in turn_ids:
                _scenario_error(path, f"check {cid!r} targets undeclared turn {ref!r}")
        elif target not in ("final", "transcript"):
            _scenario_error(path, f"check {cid!r} has unknown target {target!r}")
        if ctype in RUBRIC_CHECK_TYPES and not check.get("expect"):
            _scenario_error(path, f"rubric check {cid!r} requires an 'expect' criterion")
        if ctype in ("required-text", "forbidden-text") and not check.get("value"):
            _scenario_error(path, f"check {cid!r} of type {ctype!r} requires a 'value'")
        if ctype == "regex" and not check.get("pattern"):
            _scenario_error(path, f"regex check {cid!r} requires a 'pattern'")
        if ctype == "json-field" and not check.get("field"):
            _scenario_error(path, f"json-field check {cid!r} requires a 'field'")
        if ctype == "ordered" and not isinstance(check.get("phrases"), list):
            _scenario_error(path, f"ordered check {cid!r} requires a 'phrases' list")

    tier = scenario.get("evidence_tier", DEFAULT_EVIDENCE_TIER)
    if tier not in EVIDENCE_TIERS:
        _scenario_error(path, f"unknown evidence_tier {tier!r}")
    # The effective (total reps, consistent-pass threshold) pair must be
    # coherent: you cannot require more consistent passes than repetitions run,
    # or a check could never reach a stable pass. Validate the resolved pair so a
    # single-value override cannot silently create an unsatisfiable bar.
    reps, min_consistent = _evidence_threshold(scenario)
    _require_coherent_evidence(reps, min_consistent,
                               lambda msg: _scenario_error(path, msg))


def _require_coherent_evidence(reps, min_consistent, fail):
    """Enforce 1 <= min_consistent <= reps, calling ``fail(msg)`` otherwise."""
    if not (isinstance(reps, int) and isinstance(min_consistent, int)):
        fail("repetitions and stability_threshold must be integers")
    if reps < 1:
        fail(f"repetitions must be >= 1, got {reps}")
    if min_consistent < 1:
        fail(f"stability_threshold must be >= 1, got {min_consistent}")
    if min_consistent > reps:
        fail(f"stability_threshold {min_consistent} cannot exceed repetitions {reps} "
             "(write the evidence bar as consistent/total, e.g. 4/5)")


def _evidence_threshold(scenario, override=None):
    """Return effective ``(repetitions, min_consistent)`` for a scenario.

    ``override`` is an optional run-time ``(min_consistent, reps)`` pair from
    ``--evidence`` that wins over the tier default and any scenario-file value,
    so one flag sets a coherent bar for the whole run.
    """
    tier = scenario.get("evidence_tier", DEFAULT_EVIDENCE_TIER)
    reps, min_consistent = EVIDENCE_TIERS[tier]
    reps = scenario.get("repetitions", reps)
    min_consistent = scenario.get("stability_threshold", min_consistent)
    if override is not None:
        min_consistent, reps = override
    return reps, min_consistent


# --- case / manifest construction -----------------------------------------
#
# A case directory is a self-contained, on-disk bundle: case.json is an
# index of structure + references, while every content-shaped input (the
# artifact, fixtures, prompt/context/turn bodies, and scenario tool-mocks) is a
# file copied beside it. This keeps case.json small, avoids duplicating large
# text across side/target/repetition, and gives the true-activation sandbox real
# files to stage. The producer-facing bundle never carries expected answers.


@dataclass
class ScenarioSide:
    """One (scenario, side) input to ``prepare`` with its source already placed.

    The caller resolves every repo/git concern up front — the artifact's
    canonical identity, the on-disk source for this side (working tree or a
    per-side snapshot), and the rule activation envelope — and hands ``prepare``
    already-resolved units. ``prepare`` only copies files and stamps records, so
    the contract module carries no repo-path or git coupling.
    """
    scenario: Scenario     # the dict from parse_scenario, with _dir/_path attached by the caller
    side: str               # "baseline" | "variant"
    source_base: Path       # on-disk dir (skill) or file (other kinds) already placed by the caller
    kind: str               # resolved artifact kind (from artifact-context resolution, not raw scenario["kind"])
    artifact: str           # resolved canonical repo-relative artifact id (for case + manifest index)
    source_is_dir: bool
    artifact_absent: bool
    rule_envelope: dict | None   # {rule_path} or None
    suite_path: str              # repo-relative scenario path string (for the manifest entry)


def _copy_scenario_dir(scenario, subdir, case_dir, label):
    """Copy a scenario subtree (fixtures/ or tool-mocks/) into the case dir.

    Returns the list of case-relative paths copied. Paths are confined under
    the scenario directory so a crafted scenario cannot read outside it.
    """
    src_root = _confined_path(scenario["_dir"], subdir, label)
    if not src_root.is_dir():
        return []
    copied = []
    for src in sorted(p for p in src_root.rglob("*") if p.is_file()):
        rel = Path(subdir) / src.relative_to(src_root)
        dest = case_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        copied.append(rel.as_posix())
    return copied


def _materialize_fixtures(scenario, case_dir):
    """Copy declared fixtures into the case's fixtures/ dir; return name->path."""
    out = {}
    scenario_dir = scenario["_dir"]
    for name, rel in scenario.get("fixtures", {}).items():
        rel = _validate_path_fragment(rel, "fixture path", allow_nested=True)
        fixture_path = _confined_path(scenario_dir, rel, "fixture path")
        if not fixture_path.exists():
            sys.exit(f"error: {scenario['_path']}: fixture {name!r} not found: {fixture_path}")
        dest_rel = Path("fixtures") / Path(rel).name
        dest = case_dir / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fixture_path, dest)
        out[name] = dest_rel.as_posix()
    return out


def _materialize_prompt_and_turns(scenario, case_dir):
    """Write the prompt/context/turn bodies as files under ``prompt/``.

    Returns ``(prompt_file, turns, context_file)`` as case-relative paths. The
    scenario .md itself is never referenced for the producer because its
    frontmatter carries expected answers; only the filtered section bodies are
    written into the case, body-only (the ``## Heading`` is an authoring label,
    not part of the text the producer receives). All prompt material is grouped
    under ``prompt/`` so ``case.json`` is the only loose file at the root.
    """
    sections = scenario.get("_sections", {})
    interaction = scenario.get("interaction", {})
    prompt_dir = case_dir / "prompt"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    context_file = None
    if sections.get("Context"):
        (prompt_dir / "context.md").write_text(sections["Context"] + "\n", encoding="utf-8")
        context_file = "prompt/context.md"
    if interaction.get("mode") == "multi-turn":
        (prompt_dir / "turns").mkdir(parents=True, exist_ok=True)
        turns = []
        for t in scenario.get("turns", []):
            body = sections.get(t["body"], "")
            rel = f"prompt/turns/{_slug(t['id'])}.md"
            (case_dir / rel).write_text(body + "\n", encoding="utf-8")
            turns.append({"id": t["id"], "file": rel})
        return None, turns, context_file
    (prompt_dir / "prompt.md").write_text(sections.get("Prompt", "") + "\n", encoding="utf-8")
    return "prompt/prompt.md", [], context_file


def _build_check_definitions(scenario):
    """Return the full check list for the rubric evaluator (includes expect/operands)."""
    return [dict(check) for check in scenario.get("checks", [])]


# Mode-specific safety guidance the composed producer prompt must convey. The
# invariant is identical in both modes — no real remote mutation, no real
# credentials — but it is achieved differently: rendered mode instructs the
# producer to hold back (there is no sandbox), while sandbox mode relies on
# environmental containment and must NOT tell the producer to hold back, or it
# would mask the very acting behavior the run measures.
_PRODUCER_SAFETY_RENDERED = (
    "work in draft only — do not perform real remote actions, use real credentials, "
    "or mutate any external state; return the proposed output rather than executing it, "
    "and treat the provided materials as the only context"
)
_PRODUCER_SAFETY_SANDBOX = (
    "behave normally and take the actions you would for a real request; the environment "
    "is isolated (external commands are routed to fakes and no real credentials exist), "
    "so it contains any effects — do not hold back the behavior under test"
)


def _render_producer_brief(scenario, entry_rel, fixtures, tool_mocks,
                           prompt_file, turns, context_file, mode):
    """Assemble the orchestrator-facing brief for composing the producer prompt.

    This file is read by the *orchestrator*, never handed to the producer. It
    lists, by path, the case materials the orchestrator uses and the rules for
    composing a realistic, blinded producer prompt, and it forbids leaking any
    evaluation framing (the paths, the words artifact/fixture/case/scenario/
    evaluation, check or repetition) into that prompt. Blinding remains the
    orchestrator's captured runtime duty; this brief makes the inputs and rules
    deterministic and inspectable.

    The brief is mode-aware. In rendered mode the artifact guidance and data
    files are inlined into the prompt and the producer returns proposed output;
    in sandbox mode the artifact is installed and self-activated by the target
    tool (not inlined), tool mocks are staged into the sandbox bin, and the
    producer acts normally under environmental containment.
    """
    sandbox = mode == "sandbox"
    lines = [
        "# Orchestrator brief: compose the producer prompt",
        "",
        "You are the evaluation orchestrator. Do NOT hand this file to the producer.",
        "Compose a realistic task prompt for the producer from the materials below,",
        "then capture the composed prompt under `produced/` and run the producer.",
        "",
        "## Task materials",
    ]
    if turns:
        lines.append("- Request turns, in order:")
        for t in turns:
            lines.append(f"  - `{t['file']}`")
    elif prompt_file:
        lines.append(f"- Task request: `{prompt_file}`")
    if context_file:
        lines.append(f"- Background context: `{context_file}`")
    if entry_rel:
        if sandbox:
            lines.append("- Guidance under test: install it into the target tool so the tool activates "
                         "it as it normally would; the producer must not be told the guidance is under test.")
        else:
            lines.append(f"- Guidance the producer should follow: `{entry_rel}` (and files it references)")
    if fixtures:
        label = "- Data files (make available in the sandbox):" if sandbox else "- Provided data files:"
        lines.append(label)
        for name, rel in fixtures.items():
            lines.append(f"  - {name}: `{rel}`")
    if sandbox and tool_mocks:
        lines.append("- Tool mocks to stage into the sandbox bin (see the evaluation-sandbox skill):")
        for rel in tool_mocks:
            lines.append(f"  - `{rel}`")

    lines += ["", "## Composition rules"]
    if sandbox:
        lines += [
            "- Give the producer the real task inside the isolated sandbox; let the target tool "
            "load and activate the installed guidance itself — do not paste the guidance into the prompt.",
        ]
    else:
        lines += [
            "- Present the task the way a real user would ask it; inline the content, do not cite these paths.",
        ]
    lines += [
        "- Do NOT use the words artifact, fixture, case, scenario, evaluation, check, or repetition,",
        "  and do NOT reveal that this is an evaluation or that the output will be judged.",
        f"- Convey this safety guidance to the producer: {_PRODUCER_SAFETY_SANDBOX if sandbox else _PRODUCER_SAFETY_RENDERED}.",
        "- Withhold every check's expected criteria from the producer prompt.",
    ]
    return "\n".join(lines) + "\n"


def _materialize_case_artifact(source_base, source_is_dir, case_dir, *, artifact_absent=False):
    """Copy the artifact's file(s) into the case folder as standalone files.

    ``source_base`` is the on-disk path the caller already placed for this side
    (a directory for skills, a single file for other kinds). Skills travel as
    their whole directory (so ``references/`` come along); other kinds travel as
    their single file. Returns ``(entry_rel, files)`` of case-relative paths. No
    artifact text is inlined into case.json; the producer reads the copied files.
    """
    if artifact_absent:
        return None, []
    entry_name = "SKILL.md" if source_is_dir else source_base.name
    files = []
    if source_is_dir:
        if source_base.is_dir():
            for src in sorted(p for p in source_base.rglob("*") if p.is_file()):
                rel = src.relative_to(source_base)
                dest = case_dir / "artifact" / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest)
                files.append(f"artifact/{rel.as_posix()}")
    elif source_base.is_file():
        dest = case_dir / "artifact" / entry_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_base, dest)
        files.append(f"artifact/{entry_name}")
    entry_rel = f"artifact/{entry_name}" if f"artifact/{entry_name}" in files else None
    return entry_rel, files


def _case_rule_context(rule_envelope):
    """Return rule metadata for the case without duplicating the rule body.

    The rule body already travels as a copied file under artifact/, so the
    case references it rather than embedding a second copy. ``rule_envelope`` is
    the unit's rule envelope (or ``None`` for a non-rule artifact).
    """
    if not rule_envelope:
        return None
    return {"rule_path": rule_envelope["rule_path"]}


def _prepare_case_sandbox(mode, case_dir):
    """Pre-create the empty ``sandbox/`` anchor for a true-activation case.

    Only ``mode == "sandbox"`` cases get a sandbox. ``mode`` in the case is
    the sole case-specific signal that a sandbox is needed; the ``sandbox/``
    location and the per-repetition isolation policy (a fresh ``bin``/``sinks``/
    ``home`` per repetition, so executions never share mutable state) are the
    evaluation-sandbox skill's contract, documented there once rather than
    restated as hardcoded fields in every case. prepare only pre-creates the
    empty root as a discoverability anchor; the executor creates the runtime
    dirs beneath it.
    """
    if mode != "sandbox":
        return
    (case_dir / "sandbox").mkdir(parents=True, exist_ok=True)


def _build_case(scenario, unit, target, run_dir, mode, case_dir, *, evaluator=None, evidence_override=None):
    """Return a self-contained execution case for the orchestrator.

    The case is a complete execution unit: producer inputs (prompt/context/
    fixtures/artifact/tool-mocks) plus the full check definitions and effective
    execution params (repetitions, stability threshold, tier). The orchestrator
    reads it, constructs the producer prompt while withholding expected criteria,
    runs the producer, then runs the rubric evaluator against these checks. The
    manifest is only an index, so a case carries everything one execution needs.

    ``unit`` is the ``ScenarioSide`` for this scenario/side: it carries the side,
    the already-placed on-disk artifact source, and the resolved artifact/rule
    identity, so this builder copies files and stamps records without any repo or
    git concern. ``evaluator`` is the optional pinned rubric-evaluator descriptor;
    when set it travels in the case's ``judge`` block so any orchestrator uses the
    same judge. ``evidence_override`` is the optional run-time
    ``(min_consistent, reps)`` pair from ``--evidence`` that wins over the
    scenario's tier for this run.
    """
    reps, min_consistent = _evidence_threshold(scenario, evidence_override)
    entry_rel, artifact_files = _materialize_case_artifact(
        unit.source_base, unit.source_is_dir, case_dir, artifact_absent=unit.artifact_absent)
    prompt_file, turns, context_file = _materialize_prompt_and_turns(scenario, case_dir)
    fixtures = _materialize_fixtures(scenario, case_dir)
    tool_mocks = _copy_scenario_dir(scenario, "tool-mocks", case_dir, "tool-mocks path")
    # True-activation cases get an empty sandbox/ anchor; mode is the signal
    # and the evaluation-sandbox skill owns the layout/isolation contract.
    _prepare_case_sandbox(mode, case_dir)
    # Runner writes the orchestrator brief (composition inputs + blinding rules,
    # never handed to the producer) under prompt/ so case.json stays the only
    # loose file at the case root, and pre-creates produced/ where the
    # orchestrator captures producer output.
    (case_dir / "prompt" / "producer-brief.md").write_text(
        _render_producer_brief(scenario, entry_rel, fixtures, tool_mocks,
                               prompt_file, turns, context_file, mode),
        encoding="utf-8",
    )
    (case_dir / "produced").mkdir(parents=True, exist_ok=True)
    return {
        "schema": RUN_SCHEMA,
        "schema_version": 1,
        "run_document": "case",
        "run_id": run_dir.name,
        "scenario_id": scenario["id"],
        "side": unit.side,
        "target": target["id"],
        "mode": mode,
        # Effective execution params travel with the case so it is self-contained.
        "repetitions": reps,
        "min_consistent": min_consistent,
        "evidence_tier": scenario.get("evidence_tier", DEFAULT_EVIDENCE_TIER),
        # `artifact` is the canonical repo-relative identity (matches the
        # manifest index and result records). `artifact_bundle` holds case-
        # relative paths into the copied files the producer actually reads.
        "artifact": unit.artifact,
        "artifact_kind": unit.kind,
        "artifact_bundle": {"entry": entry_rel, "files": artifact_files},
        "context": {
            "rule": _case_rule_context(unit.rule_envelope),
        },
        "interaction": {"mode": scenario.get("interaction", {}).get("mode", "single-turn")},
        # Prompt/context/turn bodies are written as files (scenario frontmatter,
        # which carries expected answers, is never referenced for the producer).
        "prompt_file": prompt_file,
        "turns": turns,
        "context_file": context_file,
        "fixtures": fixtures,
        "tool_mocks": tool_mocks,
        "produce": {
            "return_scope": ["final", "transcript"],
            # Mode-specific: rendered returns proposed outputs (no sandbox to
            # contain effects); sandbox lets the producer act, with the isolated
            # environment routing external calls to fakes and blocking real state.
            "side_effect_policy": (
                "run the producer in an isolated sandbox; route external commands to run-local "
                "fakes/sinks and allow no real credentials or remote mutation"
                if mode == "sandbox" else
                "return proposed outputs or fake-sink writes only; do not mutate real state"
            ),
            # The orchestrator reads this brief (never the producer), composes the
            # producer prompt per its rules, and captures each repetition's output
            # under produced/; result records reference those files as produced_output.
            "producer_brief": "prompt/producer-brief.md",
            "produced_dir": "produced",
        },
        # Judge-time policy: the pinned rubric evaluator, if any. When null, the
        # orchestrator judges with its own runtime. Either way the actual judge
        # identity is recorded in each result's `evaluator` field.
        "judge": {"evaluator": evaluator},
        # Full check definitions (including `expect`) for the rubric evaluator.
        # The orchestrator must withhold `expect` when constructing the producer
        # prompt; leakage prevention is the orchestrator's runtime duty, not a
        # property of this file.
        "checks": _build_check_definitions(scenario),
    }


def _side_label(side, side_labels):
    label = (side_labels or {}).get(side)
    if label is None:
        return side
    return str(label)


def _build_sides(side_ids, side_labels, absent_sides):
    sides = {}
    seen = set(side_ids)
    if BASELINE_SIDE not in seen:
        sys.exit("error: evaluation run needs a baseline side")
    sides[BASELINE_SIDE] = {"label": _side_label(BASELINE_SIDE, side_labels)}
    if BASELINE_SIDE in absent_sides:
        sides[BASELINE_SIDE]["without_artifact"] = True
    if VARIANT_SIDE in seen:
        sides[VARIANT_SIDE] = {"label": _side_label(VARIANT_SIDE, side_labels)}
        if VARIANT_SIDE in absent_sides:
            sides[VARIANT_SIDE]["without_artifact"] = True
    return sides


def _build_run_manifest(run_id, mode, sides, targets, scenario_entries, *, runner, evaluator=None, evidence_override=None) -> "RunManifest":
    """Assemble the run manifest: an index of scenarios and their cases.

    The manifest carries run metadata and, per scenario, identity plus case
    pointers. Check definitions and execution params live in the self-contained
    cases, not here, so the manifest stays a lightweight scenarios index.

    ``runner`` is a ``{name, version}`` provenance tag for the generator of the
    run (the project runner's display name and the project version), so a
    committed scorecard records which runner and release produced it.
    ``evidence_override`` is the optional run-time ``(min_consistent, reps)`` pair
    from ``--evidence``, recorded so the scorecard can note the override.
    """
    evidence = None
    if evidence_override is not None:
        min_consistent, reps = evidence_override
        evidence = {"min_consistent": min_consistent, "repetitions": reps}
    return {
        "schema": RUN_SCHEMA,
        "schema_version": 1,
        "run_document": "manifest",
        "run_id": run_id,
        "runner": runner,
        "created": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "mode": mode,
        "sides": sides,
        "targets": targets,
        # Run-level judge policy: the pinned rubric evaluator, or null when the
        # orchestrator judges with its own runtime. Cases carry the same value.
        "evaluator": evaluator,
        # Run-time evidence-bar override from --evidence, or null. Recorded so the
        # scorecard can note that the effective bar differs from scenario tiers.
        "evidence_override": evidence,
        "scenarios": scenario_entries,
    }


def _validate_sides(units):
    """Abort unless the run's sides are coherent, derived from the units alone.

    Enforces the side contract without repository coupling: every unit's side
    must be known, every run needs a baseline side, and when a variant side is
    present every scenario needs both sides so each delta is computed from a
    matched pair. An artifact-absent baseline is valid only when a variant exists.
    """
    seen = {u.side for u in units}
    unknown = seen - set(SIDES)
    if unknown:
        sys.exit(f"error: unknown evaluation side(s) {sorted(unknown)}; expected one of {list(SIDES)}")
    if BASELINE_SIDE not in seen:
        sys.exit("error: evaluation run needs a baseline side")
    has_variant = VARIANT_SIDE in seen
    if any(u.artifact_absent for u in units if u.side == BASELINE_SIDE) and not has_variant:
        sys.exit("error: artifact-absent baseline needs a variant side to compare against")
    if has_variant:
        by_scenario = {}
        for u in units:
            by_scenario.setdefault(u.scenario["id"], set()).add(u.side)
        for sid, sides in by_scenario.items():
            missing = set(COMPARISON_SIDES) - sides
            if missing:
                sys.exit(f"error: scenario {sid!r} is missing comparison side(s) "
                         f"{sorted(missing)}; a comparison run needs both sides per scenario")


def prepare(units: "list[ScenarioSide]", run_dir, *, targets, mode, runner, side_labels=None, evaluator=None, evidence_override=None) -> "tuple[RunManifest, Path]":
    """Materialize already-resolved units into cases and a run manifest.

    The single prepare entry point for both single-side and comparison runs.
    Each ``ScenarioSide`` in ``units`` carries a scenario, a side, and the
    on-disk source the caller already placed for that side, so this stage only
    copies files and stamps records — it holds no repo-path or git coupling. It
    creates ``run_dir``/``results``, builds one case per unit/target, writes each
    ``case.json``, and assembles the run manifest indexing them. Returns
    ``(run_manifest, manifest_path)``.

    A scenario appears once per side, so its units are grouped by scenario id
    (first-seen order preserved) and the manifest lists the scenario once with
    all its cases across sides and targets. ``runner`` is the finished
    ``{name, version}`` provenance tag the caller built; this stage only stamps
    it. ``side_labels`` is optional display metadata for the manifest's fixed
    baseline/variant sides; it drives no path logic here.
    """
    _validate_sides(units)
    if evidence_override is not None:
        # The run-time bar wins over every scenario's tier, so validate it once,
        # up front, before any dir is written: an incoherent override (e.g.
        # threshold > total) would otherwise make every check unsatisfiable.
        min_consistent, reps = evidence_override
        _require_coherent_evidence(reps, min_consistent, sys.exit)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "results").mkdir(exist_ok=True)

    # Group scenario entries by scenario id, preserving first-seen order. A
    # scenario appears once per side; the manifest lists it once with all its
    # cases, so consecutive same-scenario units (its sides) accumulate into one
    # entry whose identity fields come from the unit and are the same per side.
    entries = {}
    for unit in units:
        scenario = unit.scenario
        sid = scenario["id"]
        entry = entries.get(sid)
        if entry is None:
            # The manifest is an index: scenario identity + case pointers. Check
            # definitions and execution params live in the self-contained cases.
            entry = {
                "id": sid,
                "artifact": unit.artifact,
                "artifact_kind": unit.kind,
                "suite_path": unit.suite_path,
                "suite_schema_version": scenario["schema_version"],
                "baseline_failure": scenario["baseline_failure"],
                "cases": [],
            }
            entries[sid] = entry
        for target in targets:
            # Group by <target>/<side>: the baseline/variant pair compared within
            # a target sits together, and targets (never crossed for
            # comparison) are the outer partition.
            rel = Path("cases") / _slug(sid) / _slug(target["id"]) / unit.side
            case_dir = run_dir / rel
            case = _build_case(
                scenario, unit, target, run_dir, mode, case_dir,
                evaluator=evaluator, evidence_override=evidence_override,
            )
            case_rel = rel / "case.json"
            _write_json(run_dir / case_rel, case)
            entry["cases"].append({"side": unit.side, "target": target["id"], "case": str(case_rel)})

    side_ids = [u.side for u in units]
    absent_sides = {u.side for u in units if u.artifact_absent}
    manifest_sides = _build_sides(side_ids, side_labels, absent_sides)
    run_manifest = _build_run_manifest(
        run_dir.name, mode, manifest_sides, targets, list(entries.values()),
        evaluator=evaluator, runner=runner, evidence_override=evidence_override,
    )
    manifest_path = run_dir / "manifest.json"
    _write_json(manifest_path, run_manifest)
    return run_manifest, manifest_path
