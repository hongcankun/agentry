#!/usr/bin/env python3
"""Tests for the skill-only prepare/collect runner.

Run from the skill's scripts/ directory:

    python3 -m unittest tests.test_eval_runner
"""
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]

_contract_spec = importlib.util.spec_from_file_location("eval_contract", SCRIPT_DIR / "eval_contract.py")
ec = importlib.util.module_from_spec(_contract_spec)
_contract_spec.loader.exec_module(ec)

_runner_spec = importlib.util.spec_from_file_location("eval_runner", SCRIPT_DIR / "eval_runner.py")
eval_runner = importlib.util.module_from_spec(_runner_spec)
_runner_spec.loader.exec_module(eval_runner)


SCENARIO_TMPL = """+++
schema = "agentry.authoring-evaluation.scenario"
schema_version = 1
id = "{scenario_id}"
artifact = "{artifact}"
kind = "{kind}"
baseline_failure = "The producer omits the expected phrase."
evidence_tier = "exploratory"

[[checks]]
id = "mentions-phrase"
type = "required-text"
required = true
target = "final"
value = "expected phrase"
+++

## Prompt

Return the expected phrase.
"""


class EvalRunnerTests(unittest.TestCase):
    def _write_skill_fixture(self, root):
        skill_dir = root / "plugins" / "p" / "skills" / "s"
        (skill_dir / "references").mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: s\ndescription: Test skill.\n---\n\n# S\n\nSay the expected phrase.\n",
            encoding="utf-8",
        )
        (skill_dir / "references" / "extra.md").write_text("More guidance.\n", encoding="utf-8")
        return skill_dir

    def _write_scenario(self, root, *, kind="skill", artifact="plugins/p/skills/s/SKILL.md",
                        scenario_id="demo"):
        scen_dir = root / "eval"
        scen_dir.mkdir(parents=True)
        scenario = scen_dir / f"{scenario_id}.md"
        scenario.write_text(
            SCENARIO_TMPL.format(scenario_id=scenario_id, artifact=artifact, kind=kind),
            encoding="utf-8",
        )
        return scenario

    def _prepare(self, root, scenario, *extra):
        run_dir = root / "run"
        argv = [
            "prepare", str(scenario),
            "--target", "trae:GPT-5.5",
            "--artifact-root", str(root),
            "--run-dir", str(run_dir),
            *extra,
        ]
        with redirect_stdout(io.StringIO()):
            rc = eval_runner.main(argv)
        self.assertEqual(rc, 0)
        return run_dir

    def test_prepare_materializes_current_side_skill_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_skill_fixture(root)
            scenario = self._write_scenario(root)

            run_dir = self._prepare(root, scenario, "--evaluator", "trae:judge", "--evidence", "1/1")

            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["runner"], {"name": "authoring-evaluation", "version": "0.1.0"})
            self.assertEqual(manifest["mode"], "rendered")
            self.assertEqual(manifest["targets"], [
                {"id": "trae:GPT-5.5", "tool": "trae", "model": "GPT-5.5"}
            ])
            self.assertEqual(manifest["evaluator"], {"id": "trae:judge", "tool": "trae", "model": "judge"})
            case_rel = manifest["scenarios"][0]["cases"][0]["case"]
            self.assertEqual(manifest["scenarios"][0]["cases"][0]["side"], "baseline")
            self.assertEqual(manifest["sides"], {"baseline": {"label": "current"}})

            case = json.loads((run_dir / case_rel).read_text(encoding="utf-8"))
            case_dir = (run_dir / case_rel).parent
            self.assertEqual(case["artifact_kind"], "skill")
            self.assertEqual(case["artifact_bundle"]["entry"], "artifact/SKILL.md")
            self.assertIn("artifact/references/extra.md", case["artifact_bundle"]["files"])
            self.assertEqual(case["context"], {"rule": None})
            self.assertEqual(case["repetitions"], 1)
            self.assertEqual(case["min_consistent"], 1)
            self.assertTrue((case_dir / "artifact" / "SKILL.md").is_file())
            self.assertTrue((case_dir / "prompt" / "prompt.md").is_file())
            self.assertFalse((case_dir / "sandbox").exists())

    def test_prepare_sandbox_mode_creates_anchor_and_mode_aware_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_skill_fixture(root)
            scenario = self._write_scenario(root)

            run_dir = self._prepare(root, scenario, "--mode", "sandbox")

            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            case_rel = manifest["scenarios"][0]["cases"][0]["case"]
            case_dir = (run_dir / case_rel).parent
            case = json.loads((run_dir / case_rel).read_text(encoding="utf-8"))
            brief = (case_dir / "prompt" / "producer-brief.md").read_text(encoding="utf-8")
            self.assertEqual(case["mode"], "sandbox")
            self.assertTrue((case_dir / "sandbox").is_dir())
            self.assertIn("install it into the target tool", brief)
            self.assertIn("behave normally", brief)

    def test_prepare_accepts_named_scenario_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_skill_fixture(root)
            scenario = self._write_scenario(root)
            run_dir = root / "run"

            with redirect_stdout(io.StringIO()):
                rc = eval_runner.main([
                    "prepare", "--scenario", str(scenario),
                    "--target", "trae:GPT-5.5",
                    "--artifact-root", str(root),
                    "--run-dir", str(run_dir),
                ])

            self.assertEqual(rc, 0)
            self.assertTrue((run_dir / "manifest.json").is_file())

    def test_prepare_rule_scenario_materializes_independent_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "rules" / "authoring").mkdir(parents=True)
            (root / "rules" / "authoring" / "x.md").write_text("# Rule\n\nGuidance.\n", encoding="utf-8")
            scenario = self._write_scenario(
                root, kind="rule", artifact="rules/authoring/x.md", scenario_id="rule-demo"
            )

            run_dir = self._prepare(root, scenario)

            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            case_rel = manifest["scenarios"][0]["cases"][0]["case"]
            case = json.loads((run_dir / case_rel).read_text(encoding="utf-8"))
            case_dir = (run_dir / case_rel).parent
            self.assertEqual(case["artifact_kind"], "rule")
            self.assertEqual(case["artifact_bundle"]["entry"], "artifact/x.md")
            self.assertEqual(case["context"]["rule"], {"rule_path": "rules/authoring/x.md"})
            self.assertIn("Guidance.", (case_dir / "artifact" / "x.md").read_text(encoding="utf-8"))

    def test_prepare_requires_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_skill_fixture(root)
            scenario = self._write_scenario(root)
            err = io.StringIO()
            with self.assertRaises(SystemExit) as cm, redirect_stderr(err):
                eval_runner.main([
                    "prepare", str(scenario),
                    "--artifact-root", str(root),
                    "--run-dir", str(root / "run"),
                ])
            self.assertNotEqual(cm.exception.code, 0)
            self.assertIn("--target", err.getvalue())

    def test_version_flag_reports_runner_version(self):
        out = io.StringIO()
        with self.assertRaises(SystemExit) as cm, redirect_stdout(out):
            eval_runner.main(["--version"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("0.1.0", out.getvalue())

    def test_collect_writes_scorecards_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_skill_fixture(root)
            scenario = self._write_scenario(root)
            run_dir = self._prepare(root, scenario, "--evidence", "1/1")

            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            case_rel = manifest["scenarios"][0]["cases"][0]["case"]
            produced = str(Path(case_rel).parent / "produced" / "rep-1.md")
            (run_dir / produced).write_text("the expected phrase appears\n", encoding="utf-8")
            (run_dir / "results" / "out.jsonl").write_text(json.dumps({
                "schema": ec.RESULT_SCHEMA,
                "schema_version": 1,
                "record_type": "check",
                "run_id": manifest["run_id"],
                "scenario_id": "demo",
                "target": "trae:GPT-5.5",
                "side": "baseline",
                "check_id": "mentions-phrase",
                "outcome": "pass",
                "repetition": 1,
                "producer": {"tool": "trae", "model": "GPT-5.5"},
                "evaluator": {"id": "matcher", "model": "deterministic"},
                "produced_output": produced,
                "evidence": {"source_path": produced, "quote": "expected phrase"},
            }) + "\n", encoding="utf-8")

            out = io.StringIO()
            with redirect_stdout(out):
                rc = eval_runner.main(["collect", str(run_dir)])

            self.assertEqual(rc, 0)
            self.assertTrue((run_dir / "scorecard.md").is_file())
            self.assertTrue((run_dir / "scorecard.json").is_file())
            report = json.loads((run_dir / "scorecard.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "ok")
            self.assertIn("status: ok", out.getvalue())


if __name__ == "__main__":
    unittest.main()
