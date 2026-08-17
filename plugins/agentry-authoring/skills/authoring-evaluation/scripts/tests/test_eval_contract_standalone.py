#!/usr/bin/env python3
"""Standalone smoke test for the skill's bundled ``eval_contract.py`` copy.

This proves the copied module runs self-contained — imported by path from the
skill's own ``scripts/`` directory, with no repo tooling present. It is the guard
that the extraction stays freestanding: if the canonical module ever grows a
dependency on the maintenance CLI or a repo-path global, the copy breaks here
even though ``generate --check`` (byte-identical) would still pass.

Run from the skill's scripts/ directory:

    python3 -m unittest tests.test_eval_contract_standalone
"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "eval_contract.py"
_spec = importlib.util.spec_from_file_location("eval_contract_bundled", MODULE)
ec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ec)


class StandaloneSmokeTests(unittest.TestCase):
    def test_no_repo_coupling(self):
        # No maintenance-CLI import and no repo-path globals: the copy must run
        # with nothing else present.
        self.assertFalse(hasattr(ec, "agentry"))
        for forbidden in ("REPO_ROOT", "RULES_DIR", "PLUGINS_DIR", "MANIFEST", "BRAND"):
            self.assertFalse(hasattr(ec, forbidden))

    def test_collect_runs_standalone(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "results").mkdir()
            produced = "cases/s1/trae_m/baseline/produced/rep-1.md"
            (run / produced).parent.mkdir(parents=True, exist_ok=True)
            (run / produced).write_text("hello world\n", encoding="utf-8")
            case_rel = "cases/s1/trae_m/baseline/case.json"
            (run / case_rel).parent.mkdir(parents=True, exist_ok=True)
            (run / case_rel).write_text(ec._serialize({
                "schema": ec.RUN_SCHEMA, "schema_version": 1, "run_document": "case",
                "run_id": "t", "scenario_id": "s1", "side": "baseline", "target": "trae:m",
                "mode": "rendered", "repetitions": 1, "min_consistent": 1,
                "evidence_tier": "exploratory", "judge": {"evaluator": None},
                "checks": [{"id": "c1", "type": "rubric", "required": True}],
            }), encoding="utf-8")
            manifest = {
                "schema": ec.RUN_SCHEMA, "schema_version": 1, "run_document": "manifest",
                "run_id": "t", "runner": {"name": "x", "version": "0"},
                "mode": "rendered", "sides": {"baseline": {"label": "current"}},
                "targets": [{"id": "trae:m", "tool": "trae", "model": "m"}],
                "evaluator": None, "evidence_override": None,
                "scenarios": [{"id": "s1", "artifact": "x", "artifact_kind": "skill",
                               "cases": [{"side": "baseline", "target": "trae:m", "case": case_rel}]}],
            }
            (run / "manifest.json").write_text(ec._serialize(manifest), encoding="utf-8")
            (run / "results" / "out.jsonl").write_text(json.dumps({
                "schema": ec.RESULT_SCHEMA, "schema_version": 1, "record_type": "check",
                "run_id": "t", "scenario_id": "s1", "target": "trae:m", "side": "baseline",
                "check_id": "c1", "outcome": "pass", "repetition": 1,
                "producer": {"tool": "trae", "model": "m"},
                "evaluator": {"id": "rubric", "model": "m"},
                "produced_output": produced,
                "evidence": {"source_path": produced, "quote": "hello world"},
            }) + "\n", encoding="utf-8")

            report = ec.collect(run)
            self.assertEqual(report["status"], "ok")
            # Emission is the contract's job; the pass/fail gate is the runner's,
            # so a standalone consumer emits the scorecard and reads report status.
            ec.write_scorecard(report, run / "scorecard.md")
            self.assertTrue((run / "scorecard.md").is_file())
            self.assertTrue((run / "scorecard.json").is_file())


class PrepareStandaloneTests(unittest.TestCase):
    """Prove single-artifact current-side prepare runs self-contained.

    Builds a tiny artifact + scenario inside a temp dir acting as the repo root,
    parses the scenario with the bundled module, and materializes a run from a
    hand-built ScenarioSide — no git, no discovery, no maintenance CLI. This is
    the Option-2 promise: a plugin/checkout install can prepare a run on its own.
    """

    def test_prepare_materializes_a_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # A minimal skill artifact under a plugins/ tree the scenario points at.
            skill_dir = root / "plugins" / "p" / "skills" / "s"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# S\n\nGuidance.\n", encoding="utf-8")
            # A scenario file with fixtures beside it.
            scen_dir = root / "eval"
            (scen_dir / "fixtures").mkdir(parents=True)
            (scen_dir / "fixtures" / "d.txt").write_text("data\n", encoding="utf-8")
            scenario_md = (
                "+++\n"
                'schema = "agentry.authoring-evaluation.scenario"\n'
                "schema_version = 1\n"
                'id = "demo"\n'
                'artifact = "plugins/p/skills/s/SKILL.md"\n'
                'kind = "skill"\n'
                'baseline_failure = "x"\n'
                "\n"
                "[fixtures]\n"
                'data = "fixtures/d.txt"\n'
                "\n"
                "[[checks]]\n"
                'id = "c1"\n'
                'type = "rubric"\n'
                "required = true\n"
                'target = "final"\n'
                'expect = "does the thing"\n'
                "+++\n\n## Prompt\n\nDo the thing.\n"
            )
            scen_path = scen_dir / "demo.md"
            scen_path.write_text(scenario_md, encoding="utf-8")

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
                mode="rendered", runner={"name": "Demo", "version": None},
            )
            self.assertTrue(manifest_path.is_file())
            self.assertEqual(run_manifest["runner"], {"name": "Demo", "version": None})
            case_rel = run_manifest["scenarios"][0]["cases"][0]["case"]
            case = json.loads((run_dir / case_rel).read_text(encoding="utf-8"))
            self.assertEqual(case["run_document"], "case")
            # The artifact and fixture traveled into the case as real files.
            self.assertTrue((run_dir / case_rel).parent.joinpath("artifact", "SKILL.md").is_file())
            self.assertEqual(case["fixtures"]["data"], "fixtures/d.txt")


if __name__ == "__main__":
    unittest.main()
