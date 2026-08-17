#!/usr/bin/env python3
"""Tests for the deterministic-check matcher (check_output.py).

Run from the skill's scripts/ directory:

    python3 -m unittest tests.test_check_output

These are skill-local so the matcher stays self-contained and portable: they
load the sibling script by path and exercise each deterministic check type,
both outcomes, and the invariant that the evidence quote is always a genuine
substring of the captured output (what the project runner's provenance gate
requires).
"""
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check_output.py"
_spec = importlib.util.spec_from_file_location("check_output", SCRIPT)
check_output = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_output)


class MatcherTests(unittest.TestCase):
    def _run(self, text, *argv):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
            fh.write(text)
            path = fh.name
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = check_output.main(["--output", path, *argv])
        self.assertEqual(rc, 0)
        result = json.loads(buf.getvalue())
        # Invariant: the evidence quote is always a substring of the output, so
        # the record the orchestrator writes passes the runner's provenance gate.
        self.assertIn(result["evidence"]["quote"], text)
        return result

    def test_required_text_pass_quotes_match(self):
        r = self._run("the diff shows a regression here", "--type", "required-text", "--value", "regression")
        self.assertEqual(r["outcome"], "pass")
        self.assertEqual(r["evidence"]["quote"], "regression")

    def test_required_text_fail_anchors_output(self):
        r = self._run("nothing relevant", "--type", "required-text", "--value", "regression")
        self.assertEqual(r["outcome"], "fail")

    def test_forbidden_text_absent_passes(self):
        r = self._run("a clean summary", "--type", "forbidden-text", "--value", "TODO")
        self.assertEqual(r["outcome"], "pass")

    def test_forbidden_text_present_fails_and_quotes_offender(self):
        r = self._run("has a TODO left in", "--type", "forbidden-text", "--value", "TODO")
        self.assertEqual(r["outcome"], "fail")
        self.assertEqual(r["evidence"]["quote"], "TODO")

    def test_forbidden_text_pass_on_empty_output(self):
        # Empty output: quote is the empty string, still a substring.
        r = self._run("", "--type", "forbidden-text", "--value", "TODO")
        self.assertEqual(r["outcome"], "pass")

    def test_regex_pass_quotes_matched_span(self):
        r = self._run("status: 200 OK", "--type", "regex", "--pattern", r"\d{3}")
        self.assertEqual(r["outcome"], "pass")
        self.assertEqual(r["evidence"]["quote"], "200")

    def test_regex_fail(self):
        r = self._run("no digits here", "--type", "regex", "--pattern", r"\d{3}")
        self.assertEqual(r["outcome"], "fail")

    def test_json_field_present_passes(self):
        r = self._run('{"result": {"status": "ok"}}', "--type", "json-field", "--field", "result.status")
        self.assertEqual(r["outcome"], "pass")

    def test_json_field_expected_value_matches(self):
        r = self._run('{"status": "ok"}', "--type", "json-field", "--field", "status", "--value", "ok")
        self.assertEqual(r["outcome"], "pass")

    def test_json_field_expected_value_mismatch_fails(self):
        r = self._run('{"status": "bad"}', "--type", "json-field", "--field", "status", "--value", "ok")
        self.assertEqual(r["outcome"], "fail")

    def test_json_field_missing_fails(self):
        r = self._run('{"status": "ok"}', "--type", "json-field", "--field", "missing")
        self.assertEqual(r["outcome"], "fail")

    def test_json_field_invalid_json_fails(self):
        r = self._run("not json", "--type", "json-field", "--field", "status")
        self.assertEqual(r["outcome"], "fail")

    def test_ordered_pass_quotes_full_span(self):
        r = self._run("first the diff, then the comments", "--type", "ordered",
                      "--phrases", json.dumps(["diff", "comments"]))
        self.assertEqual(r["outcome"], "pass")
        self.assertEqual(r["evidence"]["quote"], "diff, then the comments")

    def test_ordered_wrong_order_fails(self):
        r = self._run("comments before the diff", "--type", "ordered",
                      "--phrases", json.dumps(["diff", "comments"]))
        self.assertEqual(r["outcome"], "fail")

    def test_ordered_missing_phrase_fails(self):
        r = self._run("only the diff", "--type", "ordered",
                      "--phrases", json.dumps(["diff", "comments"]))
        self.assertEqual(r["outcome"], "fail")


class UsageTests(unittest.TestCase):
    def _write(self, text="x"):
        fh = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        fh.write(text)
        fh.close()
        return fh.name

    def test_missing_value_for_required_text_errors(self):
        with self.assertRaises(SystemExit):
            check_output.main(["--output", self._write(), "--type", "required-text"])

    def test_missing_pattern_for_regex_errors(self):
        with self.assertRaises(SystemExit):
            check_output.main(["--output", self._write(), "--type", "regex"])

    def test_bad_phrases_json_errors(self):
        with self.assertRaises(SystemExit):
            check_output.main(["--output", self._write(), "--type", "ordered", "--phrases", "not-json"])

    def test_empty_phrases_list_errors(self):
        with self.assertRaises(SystemExit):
            check_output.main(["--output", self._write(), "--type", "ordered", "--phrases", "[]"])

    def test_unreadable_output_errors(self):
        with self.assertRaises(SystemExit):
            check_output.main(["--output", "/no/such/file", "--type", "required-text", "--value", "x"])


if __name__ == "__main__":
    unittest.main()
