#!/usr/bin/env python3
"""Standalone prepare/collect CLI for the authoring-evaluation skill.

This intentionally stays thin: it resolves only current-side artifact paths,
then delegates run materialization and scorecard rendering to the bundled
``eval_contract`` module.
"""

import argparse
import sys
from pathlib import Path

import eval_contract as ec

VERSION = "0.1.0"
RUNNER = {"name": "authoring-evaluation", "version": VERSION}


def _parse_tool_model(value):
    if ":" not in value:
        raise argparse.ArgumentTypeError("expected tool:model")
    tool, model = value.split(":", 1)
    if not tool or not model:
        raise argparse.ArgumentTypeError("expected tool:model")
    return {"id": value, "tool": tool, "model": model}


def _parse_evidence(value):
    if "/" not in value:
        raise argparse.ArgumentTypeError("expected MIN/TOTAL")
    left, right = value.split("/", 1)
    try:
        min_consistent = int(left)
        repetitions = int(right)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected integer MIN/TOTAL") from exc
    if min_consistent < 1 or repetitions < 1:
        raise argparse.ArgumentTypeError("MIN and TOTAL must be positive")
    if min_consistent > repetitions:
        raise argparse.ArgumentTypeError("MIN must be less than or equal to TOTAL")
    return min_consistent, repetitions


def _validate_path_fragment(value, label, *, allow_nested):
    if not isinstance(value, str) or not value:
        sys.exit(f"error: unsafe {label}: {value!r}")
    path = Path(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        sys.exit(f"error: unsafe {label}: {value}")
    if not allow_nested and len(path.parts) != 1:
        sys.exit(f"error: unsafe {label}: {value}")
    return value


def _confined_path(base, rel_path, label):
    root = base.resolve()
    candidate = (base / rel_path).resolve()
    if candidate != root and root not in candidate.parents:
        sys.exit(f"error: {label} escapes {base}: {rel_path}")
    return candidate


def _relative_to_root(path, root):
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _resolve_artifact_context(scenario, artifact_root):
    artifact_rel = scenario["artifact"]
    kind = scenario["kind"]

    _validate_path_fragment(artifact_rel, "artifact path", allow_nested=True)
    artifact_path = _confined_path(artifact_root, artifact_rel, "artifact path")
    if not artifact_path.exists():
        sys.exit(f"error: artifact not found: {artifact_path}")
    if not artifact_path.is_file():
        sys.exit(f"error: artifact path must be a file for {kind} scenarios: {artifact_path}")

    if kind == "skill":
        source_base = artifact_path.parent
        source_is_dir = True
    else:
        source_base = artifact_path
        source_is_dir = False
    rule_envelope = None
    if kind == "rule":
        rule_path = artifact_rel if artifact_rel.startswith("rules/") else f"rules/{artifact_rel}"
        rule_envelope = {"rule_path": rule_path}

    return {
        "kind": kind,
        "artifact": artifact_rel,
        "source_base": source_base,
        "source_is_dir": source_is_dir,
        "rule_envelope": rule_envelope,
    }


def cmd_prepare(args):
    artifact_root = args.artifact_root.resolve()
    scenario_paths = [*(args.scenario_options or []), *args.scenarios]
    if not scenario_paths:
        sys.exit("error: prepare requires at least one scenario path")
    units = []

    for scenario_path in scenario_paths:
        scenario_path = scenario_path.resolve()
        scenario = ec.parse_scenario(scenario_path)
        scenario["_dir"] = scenario_path.parent
        scenario["_path"] = str(scenario_path)
        context = _resolve_artifact_context(scenario, artifact_root)
        units.append(ec.ScenarioSide(
            scenario=scenario,
            side=ec.BASELINE_SIDE,
            source_base=context["source_base"],
            kind=context["kind"],
            artifact=context["artifact"],
            source_is_dir=context["source_is_dir"],
            artifact_absent=False,
            rule_envelope=context["rule_envelope"],
            suite_path=_relative_to_root(scenario_path, artifact_root),
        ))

    _, manifest_path = ec.prepare(
        units,
        args.run_dir,
        targets=[args.target],
        mode=args.mode,
        runner=RUNNER,
        side_labels={ec.BASELINE_SIDE: "current"},
        evaluator=args.evaluator,
        evidence_override=args.evidence,
    )
    print(f"prepared run: {manifest_path}")
    return 0


def cmd_collect(args):
    run_dir = args.run_dir
    report_path = args.report or (run_dir / "scorecard.md")
    report = ec.collect(run_dir)
    ec.write_scorecard(report, report_path)
    print(f"wrote scorecard: {report_path}")
    print(f"wrote scorecard JSON: {report_path.with_suffix('.json')}")
    print(f"status: {report['status']}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description="Prepare and collect authoring-evaluation runs without a project runner."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_prepare = sub.add_parser("prepare", help="materialize scenarios into a run")
    p_prepare.add_argument("scenarios", metavar="scenario.md", nargs="*", type=Path)
    p_prepare.add_argument("--scenario", dest="scenario_options", action="append", type=Path,
                           help="Scenario Markdown path; repeat for multiple scenarios.")
    p_prepare.add_argument("--target", required=True, type=_parse_tool_model,
                           help="Producer target as tool:model.")
    p_prepare.add_argument("--artifact-root", type=Path, default=Path.cwd(),
                           help="Root used to resolve scenario artifact paths (default: cwd).")
    p_prepare.add_argument("--run-dir", type=Path, default=Path("run"),
                           help="Directory to write the run into (default: ./run).")
    p_prepare.add_argument("--mode", choices=("rendered", "sandbox"), default="rendered")
    p_prepare.add_argument("--evaluator", type=_parse_tool_model,
                           help="Pinned rubric evaluator as tool:model.")
    p_prepare.add_argument("--evidence", type=_parse_evidence,
                           help="Override evidence bar as MIN/TOTAL, e.g. 3/3.")
    p_prepare.set_defaults(func=cmd_prepare)

    p_collect = sub.add_parser("collect", help="collect JSONL results into a scorecard")
    p_collect.add_argument("run_dir", type=Path)
    p_collect.add_argument("--report", type=Path,
                           help="Markdown scorecard path (default: <run-dir>/scorecard.md).")
    p_collect.set_defaults(func=cmd_collect)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
