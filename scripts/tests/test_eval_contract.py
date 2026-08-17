#!/usr/bin/env python3
"""Tests for the canonical evaluation-contract module (``scripts/eval_contract.py``).

These exercise the module directly (loaded by path, like the skill's own copy is)
and assert two things the re-export in ``test_agentry.py`` does not: that the
module is freestanding (imports no ``agentry``, carries no repo-path globals), and
that the collect stage validates a real on-disk run end to end.
"""
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / "scripts" / "eval_contract.py"
_spec = importlib.util.spec_from_file_location("eval_contract_under_test", MODULE)
ec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ec)


class FreestandingTests(unittest.TestCase):
    def test_module_imports_no_agentry(self):
        # The whole point of the extraction: the contract module must not pull in
        # the maintenance CLI, so a byte-identical copy runs inside a skill alone.
        self.assertFalse(hasattr(ec, "agentry"))

    def test_no_repo_path_globals(self):
        for forbidden in ("REPO_ROOT", "RULES_DIR", "PLUGINS_DIR", "MANIFEST", "BRAND"):
            self.assertFalse(hasattr(ec, forbidden), f"{forbidden} leaked into eval_contract")

    def test_exposes_collect_surface(self):
        for name in ("_load_results", "_load_cases", "_aggregate_results", "_classify_check",
                     "_compare_sides", "_render_scorecard_json", "_render_scorecard_markdown",
                     "collect", "write_scorecard", "_require_schema", "RUN_SCHEMA",
                     "RESULT_SCHEMA"):
            self.assertTrue(hasattr(ec, name), f"missing {name}")

    def test_public_api_is_exactly_all(self):
        # The public surface is intentional: every __all__ name is present, and
        # nothing public leaked without being declared.
        expected = {
            "SCENARIO_SCHEMA", "RUN_SCHEMA", "RESULT_SCHEMA", "SUPPORTED_SCHEMA_VERSIONS",
            "FRONTMATTER_FENCE", "DETERMINISTIC_CHECK_TYPES", "RUBRIC_CHECK_TYPES", "CHECK_TYPES",
            "SCENARIO_KINDS", "SIDES", "COMPARISON_SIDES", "EVIDENCE_TIERS", "DEFAULT_EVIDENCE_TIER",
            "ScenarioSide", "Scenario", "RunManifest", "Report",
            "parse_scenario", "prepare", "collect", "write_scorecard",
        }
        self.assertEqual(set(ec.__all__), expected)
        for name in ec.__all__:
            self.assertTrue(hasattr(ec, name), f"__all__ names {name} but module lacks it")

    def test_document_typeddicts_exposed(self):
        # The three cross-seam document shapes are pinned as TypedDicts so the
        # contract is visible in one place: scenario (parse_scenario out),
        # run manifest (prepare out / collect in), report (collect out).
        for name in ("Scenario", "RunManifest", "Report"):
            typ = getattr(ec, name)
            self.assertTrue(hasattr(typ, "__annotations__"), f"{name} is not a TypedDict")
            self.assertTrue(hasattr(typ, "__required_keys__"), f"{name} is not a TypedDict")


class ClassifyCheckTests(unittest.TestCase):
    def test_stable_pass(self):
        self.assertEqual(ec._classify_check(["pass", "pass", "pass"], 3), "pass")

    def test_below_threshold_is_needs_review(self):
        self.assertEqual(ec._classify_check(["pass", "pass"], 3), "needs-review")

    def test_stable_fail(self):
        self.assertEqual(ec._classify_check(["fail", "fail", "fail"], 3), "fail")

    def test_short_of_expected_cannot_pass(self):
        self.assertEqual(ec._classify_check(["pass"] * 3, 3, expected=5), "needs-review")


class IntegrityHelperTests(unittest.TestCase):
    def test_producer_not_honored_on_model_mismatch(self):
        rec = {"producer": {"tool": "trae", "model": "GPT-6"}}
        self.assertTrue(ec._producer_not_honored(rec, "trae:GPT-5.5"))

    def test_producer_missing_field_tolerated(self):
        self.assertFalse(ec._producer_not_honored({"producer": {"tool": "trae"}}, "trae:GPT-5.5"))

    def test_evaluator_not_honored_on_model_mismatch(self):
        rec = {"evaluator": {"model": "weak"}}
        self.assertTrue(ec._evaluator_not_honored(rec, {"model": "strong"}))

    def test_evaluator_missing_model_tolerated(self):
        self.assertFalse(ec._evaluator_not_honored({"evaluator": {"id": "r"}}, {"model": "strong"}))


class CollectRoundTripTests(unittest.TestCase):
    """Aggregate a minimal but real on-disk run through the collect stage."""

    def _run_dir(self, tmp):
        run = Path(tmp)
        (run / "results").mkdir()
        produced = "cases/s1/trae_GPT-5.5/baseline/produced/rep-1.md"
        ppath = run / produced
        ppath.parent.mkdir(parents=True, exist_ok=True)
        ppath.write_text("the produced answer\n", encoding="utf-8")
        case = {"schema": ec.RUN_SCHEMA, "schema_version": 1, "run_document": "case",
                "run_id": "t", "scenario_id": "s1", "side": "baseline", "target": "trae:GPT-5.5",
                "mode": "rendered", "repetitions": 3, "min_consistent": 3, "evidence_tier": "normal",
                "judge": {"evaluator": None},
                "checks": [{"id": "c1", "type": "rubric", "required": True}]}
        case_rel = "cases/s1/trae_GPT-5.5/baseline/case.json"
        (run / case_rel).parent.mkdir(parents=True, exist_ok=True)
        (run / case_rel).write_text(ec._serialize(case), encoding="utf-8")
        manifest = {"schema": ec.RUN_SCHEMA, "schema_version": 1, "run_document": "manifest",
                    "run_id": "t", "runner": {"name": "Agentry", "version": "0.5.1"},
                    "mode": "rendered", "sides": {"baseline": {"label": "current"}},
                    "targets": [{"id": "trae:GPT-5.5", "tool": "trae", "model": "GPT-5.5"}],
                    "evaluator": None, "evidence_override": None,
                    "scenarios": [{"id": "s1", "artifact": "x", "artifact_kind": "skill",
                                   "cases": [{"side": "baseline", "target": "trae:GPT-5.5", "case": case_rel}]}]}
        (run / "manifest.json").write_text(ec._serialize(manifest), encoding="utf-8")
        recs = [{"schema": ec.RESULT_SCHEMA, "schema_version": 1, "record_type": "check",
                 "run_id": "t", "scenario_id": "s1", "target": "trae:GPT-5.5", "side": "baseline",
                 "check_id": "c1", "outcome": "pass", "repetition": i,
                 "producer": {"tool": "trae", "model": "GPT-5.5"},
                 "evaluator": {"id": "rubric", "model": "GPT-5.5"},
                 "produced_output": produced,
                 "evidence": {"source_path": produced, "quote": "the produced answer"}}
                for i in (1, 2, 3)]
        (run / "results" / "out.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
        return run, manifest

    def test_clean_run_scores_ok_and_writes_scorecard(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, manifest = self._run_dir(tmp)
            records = ec._load_results(run)
            cases = ec._load_cases(run, manifest)
            report = ec._aggregate_results(records, manifest, cases)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["aggregate"]["passed"], 1)
            # write_scorecard emits Markdown + JSON; the gate/exit code is the
            # runner's policy, not the contract's, so it is not asserted here.
            report_path = run / "scorecard.md"
            ec.write_scorecard(report, report_path)
            self.assertTrue(report_path.is_file())
            self.assertTrue(report_path.with_suffix(".json").is_file())
            self.assertIn("- Runner: Agentry 0.5.1", report_path.read_text(encoding="utf-8"))

    def test_collect_public_entry_reads_manifest_and_scores(self):
        # The public collect() bundles the manifest read + load + aggregate that
        # a caller previously did inline, and returns the aggregated report.
        with tempfile.TemporaryDirectory() as tmp:
            run, _ = self._run_dir(tmp)
            report = ec.collect(run)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["aggregate"]["passed"], 1)

    def test_evidence_quote_absent_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, _ = self._run_dir(tmp)
            (run / "cases/s1/trae_GPT-5.5/baseline/produced/rep-1.md").write_text(
                "a different answer\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                ec._load_results(run)


class PrepareCurrentSideTests(unittest.TestCase):
    """Single-artifact current-side prepare from an already-resolved ScenarioSide."""

    def test_materializes_case_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "plugins" / "p" / "skills" / "s"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# S\n\nGuidance.\n", encoding="utf-8")
            scen_dir = root / "eval"
            scen_dir.mkdir(parents=True)
            scen_path = scen_dir / "demo.md"
            scen_path.write_text(
                "+++\n"
                'schema = "agentry.authoring-evaluation.scenario"\n'
                "schema_version = 1\n"
                'id = "demo"\n'
                'artifact = "plugins/p/skills/s/SKILL.md"\n'
                'kind = "skill"\n'
                'baseline_failure = "x"\n\n'
                "[[checks]]\n"
                'id = "c1"\n'
                'type = "rubric"\n'
                "required = true\n"
                'target = "final"\n'
                'expect = "does the thing"\n'
                "+++\n\n## Prompt\n\nDo the thing.\n",
                encoding="utf-8")
            scenario = ec.parse_scenario(scen_path)
            scenario["_dir"] = scen_dir
            scenario["_path"] = str(scen_path)
            run_dir = root / "run"
            # The caller resolves the artifact context and places the source; here
            # the skill dir is the on-disk source and the unit carries the tiny
            # context by hand (no repo/git resolution inside prepare).
            unit = ec.ScenarioSide(
                scenario=scenario,
                side="baseline",
                source_base=skill_dir,
                kind="skill",
                artifact="plugins/p/skills/s/SKILL.md",
                source_is_dir=True,
                artifact_absent=False,
                rule_envelope=None,
                suite_path="eval/demo.md",
            )
            run_manifest, manifest_path = ec.prepare(
                [unit], run_dir,
                targets=[{"id": "trae:m", "tool": "trae", "model": "m"}],
                mode="rendered", runner={"name": "Demo", "version": None})
            self.assertTrue(manifest_path.is_file())
            self.assertEqual(run_manifest["runner"], {"name": "Demo", "version": None})
            self.assertEqual(run_manifest["mode"], "rendered")
            case_rel = run_manifest["scenarios"][0]["cases"][0]["case"]
            case = json.loads((run_dir / case_rel).read_text(encoding="utf-8"))
            self.assertEqual(case["run_document"], "case")
            self.assertEqual(case["target"], "trae:m")
            self.assertTrue((run_dir / case_rel).parent.joinpath("artifact", "SKILL.md").is_file())


class SideValidationTests(unittest.TestCase):
    """`prepare` enforces the side contract from units alone, before any writes."""

    def _unit(self, scenario_id, side):
        # A minimal ScenarioSide; _validate_sides runs before any file access, so
        # source_base/etc. are never touched for these validation checks.
        return ec.ScenarioSide(
            scenario={"id": scenario_id, "schema_version": 1, "baseline_failure": "x"},
            side=side, source_base=Path("/nonexistent"), kind="skill",
            artifact="a", source_is_dir=True, artifact_absent=False, rule_envelope=None,
            suite_path="eval/x.md")

    def _prepare(self, units, side_labels=None):
        with tempfile.TemporaryDirectory() as tmp:
            return ec.prepare(
                units, Path(tmp) / "run",
                targets=[{"id": "trae:m", "tool": "trae", "model": "m"}],
                mode="rendered", runner={"name": "D", "version": None}, side_labels=side_labels)

    def test_constants(self):
        self.assertEqual(ec.COMPARISON_SIDES, ("baseline", "variant"))
        self.assertEqual(ec.SIDES, ("baseline", "variant"))

    def test_unknown_side_aborts(self):
        with self.assertRaises(SystemExit):
            self._prepare([self._unit("s1", "sideways")])

    def test_missing_baseline_aborts(self):
        with self.assertRaises(SystemExit):
            self._prepare([self._unit("s1", "variant")])

    def test_comparison_missing_a_side_aborts(self):
        # baseline present, variant absent for the scenario -> single-side run.
        ec._validate_sides([self._unit("s1", "baseline")])

    def test_artifact_absent_baseline_needs_variant(self):
        unit = self._unit("s1", "baseline")
        unit.artifact_absent = True
        with self.assertRaises(SystemExit):
            self._prepare([unit])

    def test_comparison_missing_side_for_one_scenario_aborts(self):
        # s1 has both; s2 only has baseline.
        units = [self._unit("s1", "baseline"), self._unit("s1", "variant"),
                 self._unit("s2", "baseline")]
        with self.assertRaises(SystemExit):
            self._prepare(units)


if __name__ == "__main__":
    unittest.main()
