#!/usr/bin/env python3
"""Decide one deterministic evaluation check by computation over captured output.

Deterministic checks (required-text, forbidden-text, regex, json-field, ordered)
must be settled by code, not by a model reading the output, so their outcome is
reproducible and free of rubric-evaluator variance. The orchestrator runs this
matcher against a captured produced-output file and records the emitted outcome
and evidence; rubric checks are judged separately by the rubric evaluator.

The script is self-contained and stdlib-only so it stays portable to any repo
that vendors the skill. It reads one check's operand from CLI flags, prints a
JSON object to stdout, and exits 0 when it could decide the check (pass or fail
are both a decision) or 2 on a usage error.

Output shape:

    {"outcome": "pass" | "fail", "evidence": {"quote": "<substring of output>"}}

The evidence quote is always a genuine substring of the captured output — the
matched span when there is one, otherwise a short head anchor — so the record
the orchestrator writes satisfies the project runner's provenance gate (the
quote must appear in the produced output) for every type and outcome, including
a forbidden-text pass where nothing matched.
"""
import argparse
import json
import re
import sys

DETERMINISTIC_TYPES = ("required-text", "forbidden-text", "regex", "json-field", "ordered")
# Head-anchor length for evidence when there is no matched span (e.g. a
# required-text miss). Kept short so the quote is a stable, quotable prefix.
ANCHOR_LEN = 120


def _anchor(text):
    """Return a short leading span of ``text`` (always a substring, may be '')."""
    return text[:ANCHOR_LEN]


def _result(outcome, quote):
    return {"outcome": outcome, "evidence": {"quote": quote}}


def check_required_text(text, value):
    idx = text.find(value)
    if idx >= 0:
        return _result("pass", value)
    return _result("fail", _anchor(text))


def check_forbidden_text(text, value):
    idx = text.find(value)
    if idx >= 0:
        # Present when it must be absent: fail, and quote the offending span.
        return _result("fail", value)
    # Absent as required: pass. No matched span, so anchor the output (an empty
    # output yields an empty quote, which is trivially a substring).
    return _result("pass", _anchor(text))


def check_regex(text, pattern):
    match = re.search(pattern, text)
    if match:
        return _result("pass", match.group(0))
    return _result("fail", _anchor(text))


def _navigate(data, dotted):
    """Return (found, value) for a dotted path into parsed JSON."""
    cur = data
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return False, None
    return True, cur


def check_json_field(text, field, expected):
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return _result("fail", _anchor(text))
    found, value = _navigate(data, field)
    if not found:
        return _result("fail", _anchor(text))
    if expected is not None and str(value) != expected:
        return _result("fail", _anchor(text))
    # Quote the field's key token from the raw text when locatable, so the
    # evidence points at the field; otherwise anchor.
    key = field.split(".")[-1]
    token = f'"{key}"'
    return _result("pass", token if token in text else _anchor(text))


def check_ordered(text, phrases):
    pos = 0
    first_start = None
    last_end = None
    for phrase in phrases:
        idx = text.find(phrase, pos)
        if idx < 0:
            return _result("fail", _anchor(text))
        if first_start is None:
            first_start = idx
        last_end = idx + len(phrase)
        pos = last_end
    return _result("pass", text[first_start:last_end])


def decide(check_type, text, args):
    if check_type == "required-text":
        return check_required_text(text, args.value)
    if check_type == "forbidden-text":
        return check_forbidden_text(text, args.value)
    if check_type == "regex":
        return check_regex(text, args.pattern)
    if check_type == "json-field":
        return check_json_field(text, args.field, args.value)
    if check_type == "ordered":
        return check_ordered(text, args.phrases)
    raise AssertionError(f"unhandled type {check_type!r}")  # pragma: no cover


def _require(condition, message):
    if not condition:
        sys.exit(f"error: {message}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", required=True, help="Path to the captured produced-output file.")
    parser.add_argument("--type", required=True, choices=DETERMINISTIC_TYPES, dest="check_type")
    parser.add_argument("--value", help="Operand for required-text/forbidden-text; optional expected value for json-field.")
    parser.add_argument("--pattern", help="Operand for regex.")
    parser.add_argument("--field", help="Dotted JSON path for json-field.")
    parser.add_argument("--phrases", help="JSON array of phrases for ordered.")
    args = parser.parse_args(argv)

    if args.check_type in ("required-text", "forbidden-text"):
        _require(args.value is not None, f"{args.check_type} requires --value")
    elif args.check_type == "regex":
        _require(args.pattern is not None, "regex requires --pattern")
    elif args.check_type == "json-field":
        _require(args.field is not None, "json-field requires --field")
    elif args.check_type == "ordered":
        _require(args.phrases is not None, "ordered requires --phrases (JSON array)")
        try:
            args.phrases = json.loads(args.phrases)
        except json.JSONDecodeError as exc:
            sys.exit(f"error: --phrases must be a JSON array: {exc}")
        _require(isinstance(args.phrases, list) and args.phrases, "ordered --phrases must be a non-empty JSON array")

    try:
        with open(args.output, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        sys.exit(f"error: cannot read --output {args.output}: {exc}")

    result = decide(args.check_type, text, args)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
