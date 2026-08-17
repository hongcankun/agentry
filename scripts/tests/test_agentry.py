"""Unit tests for ``scripts/agentry.py``.

Uses only the Python standard library so tests run with:

    python3 -m unittest discover scripts/tests

Tests cover the pure-ish helpers (parsing, state classification, in-memory
builders) and small filesystem round-trips inside ``tempfile.TemporaryDirectory``.
The marketplace CLI orchestration is intentionally mocked: we fake the text
output of ``claude`` / ``traecli`` rather than shelling out to a real install.
"""

import argparse
import filecmp
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "agentry.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("agentry_module", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # ``agentry.py`` calls ``sys.exit`` on a missing manifest in the
    # import-path helpers it exposes; those are only reached at runtime, not
    # at import time, but guard anyway so a broken checkout surfaces clearly.
    spec.loader.exec_module(module)
    return module


agentry = _load_module()
# The evaluation contract is a freestanding sibling module; load it directly and
# reference it as ``ec`` (its own binding here, not agentry's). agentry's import
# already put scripts/ on sys.path.
import eval_contract as ec


# ---------------------------------------------------------------------------
# Color / small text helpers
# ---------------------------------------------------------------------------


class ColorTests(unittest.TestCase):
    def setUp(self):
        # Reset module-level mutable state so earlier tests don't leak into
        # later ones. ``init_colors`` mutates the global ``_COLORS`` dict
        # and flips ``_USE_EMOJI``; both are reset explicitly here.
        agentry._COLORS = {"green": "", "yellow": "", "red": "", "cyan": "", "dim": "", "reset": ""}
        agentry._USE_EMOJI = False

    def tearDown(self):
        self.setUp()

    def test_init_colors_disabled_leaves_ansi_empty(self):
        agentry.init_colors(False)
        # With color disabled, colorize returns the text unchanged because
        # every entry in _COLORS is the empty string.
        self.assertEqual(agentry.colorize("hello", "green"), "hello")

    def test_init_colors_enabled_populates_ansi(self):
        agentry.init_colors(True)
        self.assertIn("\033[32m", agentry.colorize("x", "green"))

    def test_strip_color_removes_ansi(self):
        agentry.init_colors(True)
        colored = agentry.colorize("row", "green")
        self.assertNotEqual(colored, "row")
        self.assertEqual(agentry._strip_color(colored), "row")

    def test_prompt_rows_counts_wrapped_rows(self):
        with mock.patch.object(shutil, "get_terminal_size", return_value=os.terminal_size((10, 24))):
            self.assertEqual(agentry.prompt_rows("short"), 1)
            self.assertEqual(agentry.prompt_rows("0123456789x"), 2)
            self.assertEqual(agentry.prompt_rows("one\n0123456789x"), 3)

    def test_indent_depends_on_emoji_flag(self):
        agentry.init_colors(False)
        no_emoji = agentry.indent()
        agentry.init_colors(True)
        with_emoji = agentry.indent()
        self.assertEqual(len(no_emoji), 2)
        self.assertEqual(len(with_emoji), 3)

    def test_resolve_colors_never_is_false(self):
        self.assertFalse(agentry.resolve_colors("never"))

    def test_resolve_colors_always_is_true(self):
        self.assertTrue(agentry.resolve_colors("always"))


# ---------------------------------------------------------------------------
# Manifest parsing: derive_marketplace_source / plugin metadata helpers
# ---------------------------------------------------------------------------


class MarketplaceSourceTests(unittest.TestCase):
    def test_https_repo_url_strips_host_and_git_suffix(self):
        manifest = {"repository": "https://github.com/example/agentry.git"}
        self.assertEqual(agentry.derive_marketplace_source(manifest), "example/agentry")

    def test_https_repo_url_without_dot_git(self):
        manifest = {"repository": "https://github.com/example/agentry/"}
        self.assertEqual(agentry.derive_marketplace_source(manifest), "example/agentry")

    def test_owner_and_name_used_when_repository_has_no_github_host(self):
        # Non-github-host URLs (e.g. internal Git, self-hosted) cannot be
        # parsed for owner/repo — fall back to the manifest's own fields.
        manifest = {"repository": "https://git.corp.invalid/team/agentry",
                    "owner": "example", "name": "agentry"}
        self.assertEqual(agentry.derive_marketplace_source(manifest), "example/agentry")

    def test_falls_back_to_owner_slash_name(self):
        manifest = {"owner": "example", "name": "agentry"}
        self.assertEqual(agentry.derive_marketplace_source(manifest), "example/agentry")

    def test_missing_both_aborts(self):
        manifest = {"name": "agentry"}  # no repository, no owner
        with self.assertRaises(SystemExit):
            agentry.derive_marketplace_source(manifest)

    def test_missing_both_error_names_active_manifest(self):
        # The abort message must name the active manifest filename (via
        # manifest_label()), so a downstream catalog's error points at its own
        # manifest rather than the hardcoded agentry.json.
        manifest = {"name": "x"}  # no repository, no owner
        with mock.patch.object(agentry, "MANIFEST", Path("/tmp/whatever/downstream.json")):
            with self.assertRaises(SystemExit) as cm:
                agentry.derive_marketplace_source(manifest)
        self.assertIn("downstream.json", str(cm.exception))
        self.assertNotIn("agentry.json", str(cm.exception))

    def test_plugin_ref_and_name_helpers(self):
        manifest = {
            "name": "agentry",
            "plugins": [{"name": "a"}, {"name": "b"}],
        }
        self.assertEqual(agentry.marketplace_name(manifest), "agentry")
        self.assertEqual(agentry.plugin_ref("code-review", "agentry"), "code-review@agentry")
        self.assertEqual(agentry.agentry_plugin_names(manifest), {"a", "b"})


# ---------------------------------------------------------------------------
# CLI-output parsing helpers
# ---------------------------------------------------------------------------


TOY_PLUGIN_LIST = """\
✓ code-review@agentry
    From marketplace: agentry
    description: ...
✗ spellcheck@internal
    From local: /tmp/spellcheck
other-thing
"""


class ParsePluginListTests(unittest.TestCase):
    def test_parse_installed_plugins_groups_by_origin(self):
        result = agentry.parse_installed_plugins(TOY_PLUGIN_LIST)
        self.assertEqual(result["code-review@agentry"], "marketplace")
        self.assertEqual(result["spellcheck@internal"], "local")
        # A plugin with no ``From`` line is skipped (caller treats it as
        # "not installed" for the purposes of origin-based decisions).
        self.assertNotIn("other-thing", result)

    def test_parse_installed_plugins_unknown_origin_defaults_to_marketplace(self):
        text = "✓ code-review@agentry\n    From registry: agentry\n"
        result = agentry.parse_installed_plugins(text)
        self.assertEqual(result["code-review@agentry"], "marketplace")

    def test_parse_installed_plugins_empty(self):
        self.assertEqual(agentry.parse_installed_plugins(""), {})
        self.assertEqual(agentry.parse_installed_plugins("\n\n  \n"), {})

    def test_parse_list_names_extracts_top_level_glyph_lines(self):
        text = "✓ agentry\n✗ other\n  detail line\n"
        self.assertEqual(agentry.parse_marketplaces(text), {"agentry", "other"})

    def test_parse_list_names_ignores_indented_detail(self):
        text = "✓ agentry\n  from github.com/foo/bar\n✗ second\n"
        names = agentry.parse_marketplaces(text)
        self.assertEqual(names, {"agentry", "second"})

    def test_build_install_args_differ_per_tool(self):
        # trae gets --yes when asked; claude gets --scope user.
        self.assertEqual(
            agentry.build_install_args("trae", "code@agentry", True),
            ["plugin", "install", "code@agentry", "--yes"],
        )
        self.assertEqual(
            agentry.build_install_args("trae", "code@agentry", False),
            ["plugin", "install", "code@agentry"],
        )
        self.assertEqual(
            agentry.build_install_args("claude", "code@agentry", True),
            ["plugin", "install", "code@agentry", "--scope", "user"],
        )

    def test_removal_confirm_flags_only_for_claude(self):
        self.assertEqual(agentry.removal_confirm_flags("claude"), ["--yes"])
        self.assertEqual(agentry.removal_confirm_flags("trae"), [])


# ---------------------------------------------------------------------------
# Generation builders (pure, in-memory)
# ---------------------------------------------------------------------------


SAMPLE_MANIFEST = {
    "name": "agentry",
    "version": "1.2.3",
    "description": "Test plugins",
    "owner": {"name": "Example", "url": "https://example.invalid"},
    "repository": "https://github.com/example/agentry.git",
    "license": "MIT",
    "homepage": "https://example.invalid/agentry",
    "plugins": [
        {
            "name": "code-review",
            "version": "0.1.0",
            "description": "Review changes",
            "category": "quality",
            "keywords": ["review"],
            "skills": ["code-review"],
            "agents": ["code-reviewer"],
            "rules": ["code-quality/code-review.md", "code-quality/code-style.md"],
        },
        {
            "name": "git-workflow",
            "version": "0.0.5",
            "description": "Branch and commit helpers",
            "skills": ["git-workflow"],
            "rules": ["vcs/conventional-commits.md"],
        },
    ],
}


class GenerationBuilderTests(unittest.TestCase):
    def test_serialize_is_pretty_json_with_trailing_newline(self):
        self.assertEqual(agentry.serialize({"a": 1}), '{\n  "a": 1\n}\n')
        self.assertTrue(agentry.serialize({}).endswith("\n"))

    def test_owner_string_flattens_dict(self):
        self.assertEqual(agentry.owner_string({"owner": {"name": "E"}}), "E")
        self.assertEqual(agentry.owner_string({"owner": "plain"}), "plain")
        self.assertEqual(agentry.owner_string({}), "")

    def test_build_claude_marketplace_has_schema_and_plugins(self):
        catalog = agentry.build_claude_marketplace(SAMPLE_MANIFEST)
        self.assertEqual(catalog["name"], "agentry")
        self.assertEqual(catalog["version"], "1.2.3")
        self.assertEqual(catalog["metadata"]["pluginRoot"], "./plugins")
        names = [p["name"] for p in catalog["plugins"]]
        self.assertEqual(names, ["code-review", "git-workflow"])
        # Optional fields bubble through only when present.
        self.assertEqual(catalog["plugins"][0]["keywords"], ["review"])
        self.assertNotIn("keywords", catalog["plugins"][1])
        self.assertNotIn("category", catalog["plugins"][1])
        self.assertEqual(catalog["plugins"][0]["category"], "quality")

    def test_build_claude_plugin_manifest_inherits_author_and_urls(self):
        out = agentry.build_claude_plugin_manifest(SAMPLE_MANIFEST, SAMPLE_MANIFEST["plugins"][0])
        self.assertEqual(out["name"], "code-review")
        self.assertEqual(out["version"], "0.1.0")
        self.assertEqual(out["author"], SAMPLE_MANIFEST["owner"])
        self.assertEqual(out["repository"], SAMPLE_MANIFEST["repository"])
        self.assertEqual(out["homepage"], SAMPLE_MANIFEST["homepage"])
        self.assertEqual(out["license"], SAMPLE_MANIFEST["license"])

    def test_build_claude_plugin_manifest_no_owner(self):
        manifest_minus_owner = {k: v for k, v in SAMPLE_MANIFEST.items() if k != "owner"}
        out = agentry.build_claude_plugin_manifest(manifest_minus_owner, manifest_minus_owner["plugins"][0])
        self.assertNotIn("author", out)

    def test_build_trae_marketplace_uses_owner_string_and_path_source(self):
        catalog = agentry.build_trae_marketplace(SAMPLE_MANIFEST)
        self.assertEqual(catalog["owner"], "Example")
        self.assertEqual(catalog["plugins"][0]["source"], "./plugins/code-review")
        self.assertEqual(catalog["plugins"][1]["source"], "./plugins/git-workflow")

    def test_strip_frontmatter_noop_without_markers(self):
        text = "# Title\n\nBody\n"
        self.assertEqual(agentry.strip_frontmatter(text), text)

    def test_strip_frontmatter_drops_block_and_leading_newlines(self):
        text = "---\nkey: value\n---\n\n# Body\n"
        self.assertEqual(agentry.strip_frontmatter(text), "# Body\n")

    def test_strip_frontmatter_unterminated_noop(self):
        text = "---\nkey: value\n# Body\n"
        # Not a properly closed frontmatter block — text is returned unchanged.
        self.assertEqual(agentry.strip_frontmatter(text), text)

    def test_strip_excluded_blocks_drops_between_markers(self):
        body = "# Title\n\nHello.\n\n" + agentry.EXCLUDE_BEGIN + "\nRelated stuff\n" + agentry.EXCLUDE_END + "\n\nMore.\n"
        stripped = agentry.strip_excluded_blocks(body)
        self.assertIn("# Title", stripped)
        self.assertIn("Hello.", stripped)
        self.assertIn("More.", stripped)
        self.assertNotIn("Related stuff", stripped)
        self.assertNotIn(agentry.EXCLUDE_BEGIN, stripped)
        self.assertNotIn(agentry.EXCLUDE_END, stripped)
        # The output is normalized to a single trailing newline.
        self.assertTrue(stripped.endswith("\n"))
        self.assertFalse(stripped.endswith("\n\n"))

    def test_strip_excluded_blocks_unterminated_aborts(self):
        text = "body\n" + agentry.EXCLUDE_BEGIN + "\nnever closed\n"
        with self.assertRaises(SystemExit):
            agentry.strip_excluded_blocks(text)


# ---------------------------------------------------------------------------
# Plan / state classification (filesystem-using, isolated in tmp dirs)
# ---------------------------------------------------------------------------


class InstallPlanAndStateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _mkfile(self, path: Path, content: str = "content"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_plan_copies_deduplicates_across_plugins(self):
        # plan_copies iterates over the plugin list but deduplicates by
        # (component, name) so a rule shared by two plugins yields one entry.
        plugins = [
            {"name": "a", "skills": ["one"], "rules": ["shared.md"]},
            {"name": "b", "rules": ["shared.md"], "agents": ["bot"]},
        ]
        plan = agentry.plan_copies(plugins, ("skills", "agents", "rules"))
        # Exactly one entry per unique (component, name) tuple.
        components_seen = {}
        for component, _src, rel in plan:
            components_seen.setdefault(component, []).append(rel)
        self.assertEqual(sorted(components_seen["skills"]), ["one"])
        self.assertEqual(sorted(components_seen["agents"]), ["bot.md"])
        self.assertEqual(sorted(components_seen["rules"]), ["shared.md"])

    def test_plan_copies_respects_components_filter(self):
        plugins = [
            {"name": "a", "skills": ["one"], "agents": ["bot"], "rules": ["r"]},
        ]
        plan = agentry.plan_copies(plugins, ("rules",))
        components = {component for component, _src, _rel in plan}
        self.assertEqual(components, {"rules"})

    def test_classify_state_missing_when_absent(self):
        src = self.tmp / "source.md"
        dest = self.tmp / "dest.md"
        self._mkfile(src, "hi")
        self.assertEqual(agentry.classify_state(src, dest), "missing")

    def test_classify_state_copied_current_when_identical_file(self):
        src = self.tmp / "source.md"
        dest = self.tmp / "dest.md"
        self._mkfile(src, "hi")
        self._mkfile(dest, "hi")
        self.assertEqual(agentry.classify_state(src, dest), "copied-current")

    def test_classify_state_copied_stale_when_file_differs(self):
        src = self.tmp / "source.md"
        dest = self.tmp / "dest.md"
        self._mkfile(src, "hi")
        self._mkfile(dest, "bye")
        self.assertEqual(agentry.classify_state(src, dest), "copied-stale")

    def test_classify_state_linked_when_symlink_points_at_src(self):
        src = self.tmp / "source.md"
        dest = self.tmp / "dest.md"
        self._mkfile(src, "hi")
        dest.symlink_to(src)
        self.assertEqual(agentry.classify_state(src, dest), "linked")

    def test_classify_state_stale_link_when_symlink_points_elsewhere(self):
        src = self.tmp / "source.md"
        other = self.tmp / "other.md"
        dest = self.tmp / "dest.md"
        self._mkfile(src, "hi")
        self._mkfile(other, "other")
        dest.symlink_to(other)
        self.assertEqual(agentry.classify_state(src, dest), "stale-link")

    def test_classify_state_stale_when_dir_vs_file(self):
        src_dir = self.tmp / "src"
        src_dir.mkdir()
        self._mkfile(src_dir / "a.txt", "a")
        dest = self.tmp / "dest"
        self._mkfile(dest, "stale file where a dir should be")
        self.assertEqual(agentry.classify_state(src_dir, dest), "copied-stale")

    def test_classify_state_copied_current_on_equal_dirs(self):
        src_dir = self.tmp / "src"
        dest_dir = self.tmp / "dest"
        src_dir.mkdir()
        dest_dir.mkdir()
        self._mkfile(src_dir / "a.txt", "a")
        self._mkfile(src_dir / "sub" / "b.txt", "b")
        self._mkfile(dest_dir / "a.txt", "a")
        self._mkfile(dest_dir / "sub" / "b.txt", "b")
        self.assertEqual(agentry.classify_state(src_dir, dest_dir), "copied-current")

    def test_classify_state_copied_stale_on_unequal_dirs(self):
        src_dir = self.tmp / "src"
        dest_dir = self.tmp / "dest"
        src_dir.mkdir()
        dest_dir.mkdir()
        self._mkfile(src_dir / "a.txt", "a")
        self._mkfile(dest_dir / "a.txt", "different")
        self.assertEqual(agentry.classify_state(src_dir, dest_dir), "copied-stale")

    def test_dirs_equal_false_when_destination_has_extra_file(self):
        src_dir = self.tmp / "src"
        dest_dir = self.tmp / "dest"
        src_dir.mkdir()
        dest_dir.mkdir()
        self._mkfile(src_dir / "a.txt", "a")
        self._mkfile(dest_dir / "a.txt", "a")
        self._mkfile(dest_dir / "extra.txt", "extra")
        self.assertFalse(agentry.dirs_equal(src_dir, dest_dir))

    def test_action_verbs_and_action_state_set(self):
        for state in ("missing", "copied-stale", "stale-link"):
            self.assertTrue(agentry.needs_action(state))
        for state in ("linked", "copied-current"):
            self.assertFalse(agentry.needs_action(state))
        self.assertEqual(agentry.action_verb("missing"), "install")
        self.assertEqual(agentry.action_verb("copied-stale"), "update")

    def test_validate_path_fragment_rejects_parent_traversal(self):
        with self.assertRaises(SystemExit):
            agentry.validate_path_fragment("../outside", "rule path", allow_nested=True)

    def test_validate_path_fragment_rejects_empty_and_non_string(self):
        for value in ("", None):
            with self.subTest(value=value):
                with self.assertRaises(SystemExit):
                    agentry.validate_path_fragment(value, "rule path", allow_nested=True)

    def test_validate_path_fragment_rejects_nested_component_name(self):
        with self.assertRaises(SystemExit):
            agentry.validate_path_fragment("nested/skill", "skill name", allow_nested=False)

    def test_confined_path_rejects_escaped_destination(self):
        with self.assertRaises(SystemExit):
            agentry.confined_path(self.tmp / "base", "../outside", "destination")

    def test_confined_leaf_path_rejects_escaped_parent_symlink(self):
        base = self.tmp / "base"
        outside = self.tmp / "outside"
        base.mkdir()
        outside.mkdir()
        (base / "link-dir").symlink_to(outside)
        with self.assertRaises(SystemExit):
            agentry.confined_leaf_path(base, "link-dir/dest.md", "destination")

    def test_confined_leaf_path_preserves_leaf_symlink(self):
        base = self.tmp / "base"
        outside = self.tmp / "outside.md"
        link = base / "link.md"
        base.mkdir()
        self._mkfile(outside, "outside")
        link.symlink_to(outside)
        self.assertEqual(
            agentry.confined_leaf_path(base, "link.md", "destination"),
            link,
        )

    def test_install_one_copy_round_trip(self):
        src = self.tmp / "source.md"
        dest = self.tmp / "nested" / "dest.md"
        self._mkfile(src, "body")
        result = agentry.install_one(src, dest, dry_run=False, force=False, symlink=False, quiet=True)
        self.assertEqual(result, "installed")
        self.assertTrue(filecmp.cmp(src, dest, shallow=False))

    def test_install_one_symlink_round_trip(self):
        src = self.tmp / "source.md"
        dest = self.tmp / "link.md"
        self._mkfile(src, "body")
        agentry.install_one(src, dest, dry_run=False, force=False, symlink=True, quiet=True)
        self.assertTrue(dest.is_symlink())
        # The link resolves back to src.
        self.assertEqual(dest.resolve(), src.resolve())

    def test_install_one_skips_existing_without_force(self):
        src = self.tmp / "source.md"
        dest = self.tmp / "dest.md"
        self._mkfile(src, "new")
        self._mkfile(dest, "old")
        result = agentry.install_one(src, dest, dry_run=False, force=False, symlink=False, quiet=True)
        self.assertEqual(result, "skipped")
        self.assertEqual(dest.read_text(encoding="utf-8"), "old")

    def test_install_one_skips_identical_path_without_force(self):
        src = self.tmp / "source.md"
        self._mkfile(src, "body")
        result = agentry.install_one(src, src, dry_run=False, force=False, symlink=False, quiet=True)
        self.assertEqual(result, "skipped")
        self.assertEqual(src.read_text(encoding="utf-8"), "body")

    def test_install_one_overwrites_with_force(self):
        src = self.tmp / "source.md"
        dest = self.tmp / "dest.md"
        self._mkfile(src, "new")
        self._mkfile(dest, "old")
        result = agentry.install_one(src, dest, dry_run=False, force=True, symlink=False, quiet=True)
        self.assertEqual(result, "installed")
        self.assertEqual(dest.read_text(encoding="utf-8"), "new")

    def test_install_one_dry_run_writes_nothing(self):
        src = self.tmp / "source.md"
        dest = self.tmp / "dest.md"
        self._mkfile(src, "body")
        result = agentry.install_one(src, dest, dry_run=True, force=False, symlink=False, quiet=True)
        self.assertEqual(result, "installed")
        self.assertFalse(dest.exists())

    def test_install_one_force_replaces_directory_with_file(self):
        src = self.tmp / "source.md"
        dest = self.tmp / "dest"
        self._mkfile(src, "new")
        dest.mkdir()
        self._mkfile(dest / "old.txt", "old")
        result = agentry.install_one(src, dest, dry_run=False, force=True, symlink=False, quiet=True)
        self.assertEqual(result, "installed")
        self.assertTrue(dest.is_file())
        self.assertEqual(dest.read_text(encoding="utf-8"), "new")

    def test_remove_one_deletes_file(self):
        dest = self.tmp / "dest.md"
        self._mkfile(dest, "body")
        agentry.remove_one(dest, dry_run=False)
        self.assertFalse(dest.exists())

    def test_remove_one_deletes_directory(self):
        dest = self.tmp / "dest"
        self._mkfile(dest / "nested" / "body.md", "body")
        agentry.remove_one(dest, dry_run=False)
        self.assertFalse(dest.exists())

    def test_remove_one_deletes_symlink(self):
        target = self.tmp / "target.md"
        link = self.tmp / "link.md"
        self._mkfile(target, "body")
        link.symlink_to(target)
        agentry.remove_one(link, dry_run=False)
        self.assertFalse(link.exists())
        # The target of the link is untouched.
        self.assertTrue(target.exists())

    def test_remove_one_dry_run_is_a_noop(self):
        dest = self.tmp / "dest.md"
        self._mkfile(dest, "body")
        agentry.remove_one(dest, dry_run=True)
        self.assertTrue(dest.exists())


# ---------------------------------------------------------------------------
# Generation round-trip: write_or_check detects drift and materializes files
# ---------------------------------------------------------------------------


class WriteOrCheckTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        # Patch REPO_ROOT so changed[] paths come out relative to our tmp.
        self._patch = mock.patch.object(agentry, "REPO_ROOT", self.tmp)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_writes_file_when_absent(self):
        dest = self.tmp / "a.json"
        changed = []
        agentry.write_or_check(dest, "{}", check=False, changed=changed)
        self.assertEqual(dest.read_text(encoding="utf-8"), "{}")
        self.assertEqual(changed, ["a.json"])

    def test_no_change_when_content_matches(self):
        dest = self.tmp / "a.json"
        dest.write_text("{}", encoding="utf-8")
        changed = []
        agentry.write_or_check(dest, "{}", check=False, changed=changed)
        self.assertEqual(changed, [])

    def test_check_mode_reports_drift_without_writing(self):
        dest = self.tmp / "a.json"
        dest.write_text("old", encoding="utf-8")
        changed = []
        agentry.write_or_check(dest, "new", check=True, changed=changed)
        # Content unchanged on disk, but drift is recorded.
        self.assertEqual(dest.read_text(encoding="utf-8"), "old")
        self.assertEqual(changed, ["a.json"])


# ---------------------------------------------------------------------------
# Argparse / CLI plumbing smoke tests (no subprocess, no real file I/O)
# ---------------------------------------------------------------------------


class ArgparseTests(unittest.TestCase):
    def _parser(self):
        parser = argparse.ArgumentParser(prog="agentry.py")
        sub = parser.add_subparsers(dest="command")
        add_selection_args = agentry.add_selection_args
        add_color_arg = agentry.add_color_arg

        p_install = sub.add_parser("install")
        add_selection_args(p_install, writes=True)
        p_install.add_argument("--dry-run", action="store_true")
        p_install.add_argument("--force", action="store_true")
        p_install.add_argument("--yes", "-y", action="store_true")
        p_install.add_argument("--symlink", action="store_true")
        p_install.add_argument("--source", choices=("marketplace", "checkout"))

        p_status = sub.add_parser("status")
        add_selection_args(p_status, writes=False)

        p_uninstall = sub.add_parser("uninstall")
        add_selection_args(p_uninstall, writes=False)
        p_uninstall.add_argument("--dry-run", action="store_true")
        p_uninstall.add_argument("--force", action="store_true")
        p_uninstall.add_argument("--yes", "-y", action="store_true")
        p_uninstall.add_argument("--source", choices=("marketplace", "checkout"))

        p_inventory = sub.add_parser("inventory")
        p_inventory.add_argument("--plugin", action="append")
        p_inventory.add_argument("--component", action="append", choices=agentry.COMPONENT_CHOICES)
        p_inventory.add_argument("--details", action="store_true")
        p_inventory.add_argument("--paths", action="store_true")
        p_inventory.add_argument("--json", action="store_true")
        add_color_arg(p_inventory)

        p_gen = sub.add_parser("generate")
        p_gen.add_argument("target", nargs="?", choices=("claude", "trae", "all"), default="all")
        p_gen.add_argument("--check", action="store_true")
        add_color_arg(p_gen)

        p_validate = sub.add_parser("validate")
        add_color_arg(p_validate)

        return parser

    def test_generate_parses_target_and_check_flag(self):
        args = self._parser().parse_args(["generate", "claude", "--check"])
        self.assertEqual(args.command, "generate")
        self.assertEqual(args.target, "claude")
        self.assertTrue(args.check)

    def test_generate_default_target_is_all(self):
        args = self._parser().parse_args(["generate"])
        self.assertEqual(args.target, "all")

    def test_validate_parses(self):
        args = self._parser().parse_args(["validate"])
        self.assertEqual(args.command, "validate")

    def test_install_parses_tool_and_global(self):
        args = self._parser().parse_args(["install", "--tool", "trae", "--global"])
        self.assertEqual(args.tool, "trae")
        self.assertTrue(args.global_scope)

    def test_unknown_command_rejected(self):
        with self.assertRaises(SystemExit):
            self._parser().parse_args(["nope"])

    def test_component_accumulates(self):
        args = self._parser().parse_args(["install", "--tool", "claude", "--component", "skills", "--component", "agents"])
        self.assertEqual(sorted(args.component), ["agents", "skills"])

    def test_plugin_accumulates(self):
        args = self._parser().parse_args(["install", "--tool", "claude", "--plugin", "b", "--plugin", "a"])
        self.assertEqual(args.plugin, ["b", "a"])

    def test_component_all_parses(self):
        args = self._parser().parse_args(["install", "--tool", "claude", "--component", "all"])
        self.assertEqual(args.component, ["all"])

    def test_inventory_parses_filters_and_output_flags(self):
        args = self._parser().parse_args([
            "inventory", "--plugin", "a", "--component", "skills", "--details", "--paths", "--json",
        ])
        self.assertEqual(args.command, "inventory")
        self.assertEqual(args.plugin, ["a"])
        self.assertEqual(args.component, ["skills"])
        self.assertTrue(args.details)
        self.assertTrue(args.paths)
        self.assertTrue(args.json)


# ---------------------------------------------------------------------------
# Orchestration helper: run_tool_command surface-behavior (no real binary)
# ---------------------------------------------------------------------------


class RunToolCommandTests(unittest.TestCase):
    def test_dry_run_is_noop_without_side_effects(self):
        ok, out, err = agentry.run_tool_command("/bin/definitely-not-a-real-binary",
                                                ["anything"], dry_run=True, capture=True)
        self.assertTrue(ok)
        self.assertEqual(out, "")
        self.assertEqual(err, "")

    def test_missing_binary_returns_ok_false_without_raising(self):
        # Passing a binary that does not exist must not blow up; the CLI
        # surface contract is "return ok=False with a diagnostic in stderr".
        binary = str(Path(__file__).with_name("definitely-not-real"))
        ok, out, err = agentry.run_tool_command(binary, ["list"], dry_run=False, capture=True)
        self.assertFalse(ok)
        self.assertEqual(out, "")
        self.assertTrue(err)  # non-empty diagnostic string

    def test_capture_true_passes_capture_output_to_subprocess(self):
        with mock.patch.object(subprocess, "run", return_value=mock.MagicMock(
                returncode=0, stdout="out", stderr="err")) as sr:
            ok, out, err = agentry.run_tool_command("/bin/echo", ["hi"],
                                                    dry_run=False, capture=True)
        sr.assert_called_once()
        self.assertTrue(sr.call_args.kwargs.get("capture_output"))
        self.assertTrue(ok)
        self.assertEqual(out, "out")
        self.assertEqual(err, "err")

    def test_capture_false_does_not_pass_capture_output(self):
        with mock.patch.object(subprocess, "run", return_value=mock.MagicMock(
                returncode=0, stdout=None, stderr=None)) as sr:
            ok, out, err = agentry.run_tool_command("/bin/echo", ["hi"],
                                                    dry_run=False, capture=False)
        sr.assert_called_once()
        self.assertFalse(sr.call_args.kwargs.get("capture_output", False))
        self.assertTrue(ok)
        self.assertEqual(out, "")
        self.assertEqual(err, "")


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Fake-repo fixture: sets up a tiny, self-contained "agentry-like" tree and
# patches the module-level constants (REPO_ROOT/MANIFEST/PLUGINS_DIR/RULES_DIR)
# so the CLI can be driven end-to-end without touching the real repo.
# ---------------------------------------------------------------------------


SAMPLE_MANIFEST_TWO = {
    "name": "test-agentry",
    "version": "0.1.0",
    "description": "Unit test manifest",
    "owner": "tester",
    "repository": "https://github.com/tester/test-agentry.git",
    "plugins": [
        {
            "name": "a",
            "description": "plugin a",
            "skills": ["skill-one"],
            "agents": ["agent-one"],
            "commands": ["command-one"],
            "rules": ["code-quality/a.md", "shared.md"],
        },
        {
            "name": "b",
            "description": "plugin b",
            "skills": ["skill-two"],
            "commands": [],
            "rules": ["shared.md"],
        },
    ],
}


def _make_namespace(**kwargs):
    """Build an argparse.Namespace, filling the bare minimum defaults."""
    ns = argparse.Namespace()
    ns.tool = kwargs.pop("tool", "trae")
    ns.plugin = kwargs.pop("plugin", None)
    ns.component = kwargs.pop("component", None)
    ns.global_scope = kwargs.pop("global_scope", False)
    ns.project_dir = kwargs.pop("project_dir", None)
    ns.defaults = kwargs.pop("defaults", True)
    ns.color = kwargs.pop("color", "never")
    ns.dry_run = kwargs.pop("dry_run", False)
    ns.force = kwargs.pop("force", False)
    ns.yes = kwargs.pop("yes", False)
    ns.symlink = kwargs.pop("symlink", False)
    ns.source = kwargs.pop("source", None)
    ns.status = kwargs.pop("status", False)
    for k, v in kwargs.items():
        setattr(ns, k, v)
    return ns


class _FakeRepo:
    """Helper: create a tiny checkout with a manifest/plugins/rules tree."""

    def __init__(self, tmp: Path, manifest=None):
        self.root = tmp
        self.manifest_dict = manifest or SAMPLE_MANIFEST_TWO
        self.manifest_path = self.root / "agentry.json"
        self.manifest_path.write_text(json.dumps(self.manifest_dict), encoding="utf-8")
        self.plugins_dir = self.root / "plugins"
        self.rules_dir = self.root / "rules"
        for plugin in self.manifest_dict["plugins"]:
            base = self.plugins_dir / plugin["name"]
            for skill in plugin.get("skills", []):
                skill_dir = base / "skills" / skill
                skill_dir.mkdir(parents=True, exist_ok=True)
                (skill_dir / "SKILL.md").write_text(f"# {skill}\n", encoding="utf-8")
            for agent in plugin.get("agents", []):
                agent_dir = base / "agents"
                agent_dir.mkdir(parents=True, exist_ok=True)
                (agent_dir / f"{agent}.md").write_text(f"# {agent}\n", encoding="utf-8")
            for command in plugin.get("commands", []):
                command_dir = base / "commands"
                command_dir.mkdir(parents=True, exist_ok=True)
                (command_dir / f"{command}.md").write_text(f"# {command}\n", encoding="utf-8")
            for rule in plugin.get("rules", []):
                p = self.rules_dir / rule
                p.parent.mkdir(parents=True, exist_ok=True)
                if not p.exists():
                    p.write_text(f"---\ndescription: rule {rule}\n---\n\n# {rule}\n\nbody\n",
                                 encoding="utf-8")
        # Skill references (used by generate_skill_references) only apply if
        # a plugin declares them; add a tiny one so the generator produces output.
        self.manifest_dict["plugins"][0]["skillReferences"] = {"skill-one": ["code-quality/a.md"]}
        self.manifest_path.write_text(json.dumps(self.manifest_dict), encoding="utf-8")

    def patches(self):
        """Yield mock.patch objects that redirect the module constants here."""
        new_claude = self.root / ".claude-plugin" / "marketplace.json"
        new_trae = self.root / ".trae-plugin" / "marketplace.json"
        return [
            mock.patch.object(agentry, "REPO_ROOT", self.root),
            mock.patch.object(agentry, "MANIFEST", self.manifest_path),
            mock.patch.object(agentry, "PLUGINS_DIR", self.plugins_dir),
            mock.patch.object(agentry, "RULES_DIR", self.rules_dir),
            mock.patch.object(agentry, "CLAUDE_MARKETPLACE", new_claude),
            mock.patch.object(agentry, "TRAE_MARKETPLACE", new_trae),
        ]

    def apply(self):
        for p in self.patches():
            p.start()
        self._patches = self.patches()


# ---------------------------------------------------------------------------
# Loader / selection helpers (manifest + plugin list)
# ---------------------------------------------------------------------------


class LoadManifestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _FakeRepo(Path(self._tmp.name))
        for p in self.repo.patches():
            p.start()

    def tearDown(self):
        for p in self.repo.patches():
            p.stop()
        self._tmp.cleanup()

    def test_load_manifest_round_trips(self):
        m = agentry.load_manifest()
        self.assertEqual(m["name"], "test-agentry")
        self.assertEqual(len(m["plugins"]), 2)

    def test_load_manifest_missing_file_aborts(self):
        self.repo.manifest_path.unlink()
        with self.assertRaises(SystemExit):
            agentry.load_manifest()

    def test_load_manifest_invalid_json_aborts(self):
        self.repo.manifest_path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(SystemExit):
            agentry.load_manifest()

    def test_load_plugins_returns_list(self):
        self.assertEqual(agentry.load_plugins(), self.repo.manifest_dict["plugins"])

    def test_select_plugins_all_when_none(self):
        self.assertEqual(agentry.select_plugins(self.repo.manifest_dict["plugins"], None),
                         self.repo.manifest_dict["plugins"])

    def test_select_plugins_specific_name(self):
        result = agentry.select_plugins(self.repo.manifest_dict["plugins"], "a")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "a")

    def test_select_plugins_multiple_names_preserves_manifest_order(self):
        result = agentry.select_plugins(self.repo.manifest_dict["plugins"], ["b", "a"])
        self.assertEqual([p["name"] for p in result], ["a", "b"])

    def test_select_plugins_dedupes_repeated_names(self):
        result = agentry.select_plugins(self.repo.manifest_dict["plugins"], ["a", "a"])
        self.assertEqual([p["name"] for p in result], ["a"])

    def test_select_plugins_unknown_aborts(self):
        with self.assertRaises(SystemExit):
            agentry.select_plugins(self.repo.manifest_dict["plugins"], "nope")

    def test_select_plugins_reports_all_unknown_names(self):
        with self.assertRaises(SystemExit) as cm:
            agentry.select_plugins(self.repo.manifest_dict["plugins"], ["nope", "missing"])
        self.assertIn("'nope'", str(cm.exception))
        self.assertIn("'missing'", str(cm.exception))


# ---------------------------------------------------------------------------
# Interactive prompts
# ---------------------------------------------------------------------------


class PromptTests(unittest.TestCase):
    def setUp(self):
        agentry.init_colors(False)

    def tearDown(self):
        agentry.init_colors(False)

    @contextmanager
    def _redirect_tty(self, isatty=True):
        stdin = mock.MagicMock(isatty=lambda: isatty)
        stdout = mock.MagicMock(isatty=lambda: isatty)
        with mock.patch.object(sys, "stdin", stdin), mock.patch.object(sys, "stdout", stdout):
            yield {"stdin": stdin, "stdout": stdout}

    def test_confirm_default_true_accepts_empty(self):
        with self._redirect_tty(isatty=False), mock.patch("builtins.input", return_value=""):
            self.assertTrue(agentry.confirm("ok?", default=True))

    def test_confirm_default_false_accepts_empty(self):
        with self._redirect_tty(isatty=False), mock.patch("builtins.input", return_value=""):
            self.assertFalse(agentry.confirm("ok?", default=False))

    def test_confirm_yes_and_no(self):
        with self._redirect_tty(isatty=False), mock.patch("builtins.input", return_value="y"):
            self.assertTrue(agentry.confirm("ok?", default=False))
        with self._redirect_tty(isatty=False), mock.patch("builtins.input", return_value="N"):
            self.assertFalse(agentry.confirm("ok?", default=True))

    def test_confirm_flushes_tty_erase(self):
        with self._redirect_tty(isatty=True) as streams, mock.patch("builtins.input", return_value=""):
            self.assertTrue(agentry.confirm("ok?", default=True))
        streams["stdout"].write.assert_called_with("\033[1F\033[J")
        streams["stdout"].flush.assert_called_once()

    def test_confirm_erases_wrapped_prompt_rows(self):
        with self._redirect_tty(isatty=True) as streams, \
                mock.patch("builtins.input", return_value=""), \
                mock.patch.object(shutil, "get_terminal_size", return_value=os.terminal_size((20, 24))):
            self.assertTrue(agentry.confirm("Use defaults (plugin: all · components: agents, commands, rules, skills · mode: copy)?", default=True))
        rows = int(streams["stdout"].write.call_args.args[0].removeprefix("\033[").split("F", 1)[0])
        self.assertGreater(rows, 1)
        streams["stdout"].flush.assert_called_once()

    def test_confirm_action_maps_all_variants(self):
        for user_input, expected in [
            ("", "yes"), ("y", "yes"), ("yes", "yes"),
            ("n", "no"), ("no", "no"),
            ("a", "all"), ("all", "all"),
            ("q", "none"), ("none", "none"),
        ]:
            with self._redirect_tty(isatty=False), mock.patch("builtins.input", return_value=user_input):
                self.assertEqual(agentry.confirm_action("?"), expected)

    def test_confirm_action_rejects_invalid_until_valid(self):
        inputs = iter(["maybe", "never", "y"])
        with self._redirect_tty(isatty=False), mock.patch("builtins.input", lambda *a, **kw: next(inputs)):
            self.assertEqual(agentry.confirm_action("?"), "yes")

    def test_confirm_action_flushes_tty_erase(self):
        with self._redirect_tty(isatty=True) as streams, mock.patch("builtins.input", return_value="a"):
            self.assertEqual(agentry.confirm_action("?"), "all")
        streams["stdout"].write.assert_called_with("\033[1F\033[J")
        streams["stdout"].flush.assert_called_once()

    def test_choose_picks_by_index(self):
        with self._redirect_tty(isatty=False), mock.patch("builtins.input", return_value="2"):
            self.assertEqual(agentry.choose("?", ["a", "b", "c"]), "b")

    def test_choose_picks_by_name(self):
        with self._redirect_tty(isatty=False), mock.patch("builtins.input", return_value="b"):
            self.assertEqual(agentry.choose("?", ["a", "b", "c"]), "b")

    def test_choose_rejects_invalid_until_valid(self):
        inputs = iter(["99", "b"])
        with self._redirect_tty(isatty=False), mock.patch("builtins.input", lambda *a, **kw: next(inputs)):
            self.assertEqual(agentry.choose("?", ["a", "b", "c"]), "b")

    def test_choose_default_when_empty(self):
        with self._redirect_tty(isatty=False), mock.patch("builtins.input", return_value=""):
            self.assertEqual(agentry.choose("?", ["a", "b", "c"], default="b"), "b")

    def test_choose_flushes_tty_erase(self):
        with self._redirect_tty(isatty=True) as streams, mock.patch("builtins.input", return_value="2"):
            self.assertEqual(agentry.choose("?", ["a", "b", "c"]), "b")
        streams["stdout"].write.assert_called_with("\033[5F\033[J")
        streams["stdout"].flush.assert_called_once()

    def test_choose_multi_parses_comma_and_space(self):
        with self._redirect_tty(isatty=False), mock.patch("builtins.input", return_value="1, 3"):
            self.assertEqual(agentry.choose("?", ["a", "b", "c"], multi=True), ["a", "c"])
        with self._redirect_tty(isatty=False), mock.patch("builtins.input", return_value="b c"):
            self.assertEqual(agentry.choose("?", ["a", "b", "c"], multi=True), ["b", "c"])

    def test_choose_multi_rejects_invalid_until_valid(self):
        inputs = iter(["zero", "99", "1"])
        with self._redirect_tty(isatty=False), mock.patch("builtins.input", lambda *a, **kw: next(inputs)):
            self.assertEqual(agentry.choose("?", ["a", "b"], multi=True), ["a"])

    def test_orchestrate_confirm_short_circuits_on_yes_force_dry_run(self):
        for flag in ("yes", "force", "dry_run"):
            ns = _make_namespace(**{flag: True})
            self.assertTrue(agentry.orchestrate_confirm("?", ns, interactive=True))

    def test_orchestrate_confirm_respects_bulk_all(self):
        ns = _make_namespace()
        bulk = {"value": True}
        self.assertTrue(agentry.orchestrate_confirm("?", ns, interactive=True, bulk=bulk))
        bulk = {"value": False}
        self.assertFalse(agentry.orchestrate_confirm("?", ns, interactive=True, bulk=bulk))

    def test_orchestrate_confirm_non_interactive_without_short_circuit_is_false(self):
        ns = _make_namespace()
        self.assertFalse(agentry.orchestrate_confirm("?", ns, interactive=False))

    def test_orchestrate_confirm_interactive_uses_confirm_action_for_all(self):
        ns = _make_namespace()
        with self._redirect_tty(isatty=False), mock.patch("builtins.input", return_value="a"):
            bulk = {"value": None}
            self.assertTrue(agentry.orchestrate_confirm("?", ns, interactive=True, bulk=bulk))
            # Subsequent calls short-circuit using the stored bulk value.
            self.assertTrue(agentry.orchestrate_confirm("?", ns, interactive=True, bulk=bulk))


# ---------------------------------------------------------------------------
# Report rendering: report_line / plugin_row / print_grouped_report / print_header
# ---------------------------------------------------------------------------


class ReportRenderingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _FakeRepo(Path(self._tmp.name))
        for p in self.repo.patches():
            p.start()
        agentry.init_colors(False)

    def tearDown(self):
        for p in self.repo.patches():
            p.stop()
        agentry.init_colors(False)
        self._tmp.cleanup()

    def test_report_line_has_state_and_rel(self):
        line = agentry.report_line("missing", "rules/x.md", 10)
        self.assertIn("missing", agentry._strip_color(line))
        self.assertIn("x.md", agentry._strip_color(line))

    def test_report_line_stale_includes_note(self):
        # "copied-stale" is the internal state; the rendered tag is "stale"
        # with a "differs from source" note appended.
        line = agentry.report_line("copied-stale", "skills/a", 10)
        self.assertIn("differs from source", agentry._strip_color(line))

    def test_report_line_stale_link_includes_note(self):
        line = agentry.report_line("stale-link", "rules/a.md", 10)
        self.assertIn("points elsewhere", agentry._strip_color(line))

    def test_plugin_row_pads_tag_and_includes_note(self):
        line = agentry.plugin_row("installed", "p", width=10, note="marketplace")
        content = agentry._strip_color(line)
        # The leading indentation is stripped, so the first word is the tag.
        self.assertEqual(content.strip().split(" ")[0], "installed")
        self.assertIn("p", content)
        self.assertIn("marketplace", content)

    def test_plugin_row_default_width_fits_longest_tag(self):
        # Default width accommodates the longest declared state-phase tag
        # ("unknown" / "missing" / "installed" / …), so a short tag like
        # "added" is padded to at least the longest tag's width.
        line = agentry.plugin_row("added", "p")
        # The tag column is delimited from the name by a single space. We
        # reconstruct the tag column by taking everything before " p".
        content = agentry._strip_color(line).strip()
        tag_col = content.split(" p", 1)[0]
        # "unknown" is the longest tag in the default list — 7 chars.
        self.assertGreaterEqual(len(tag_col), 7)

    def test_marketplace_refresh_hint_uses_native_cli_commands(self):
        self.assertEqual(
            agentry.marketplace_refresh_hint("claude", "agentry"),
            "claude plugin marketplace update agentry",
        )
        self.assertEqual(
            agentry.marketplace_refresh_hint("trae", "agentry"),
            "traecli plugin marketplace upgrade agentry",
        )

    def test_marketplace_refresh_hint_unknown_tool_is_none(self):
        self.assertIsNone(agentry.marketplace_refresh_hint("unknown", "agentry"))

    def test_marketplace_refresh_hint_line_only_when_marketplace_present(self):
        args = _make_namespace(tool="trae")
        manifest = {"name": "test-agentry"}
        self.assertIsNone(agentry.marketplace_refresh_hint_line(args, manifest, None))
        self.assertIsNone(
            agentry.marketplace_refresh_hint_line(args, manifest, {"mkt_ok": False, "markets": set()})
        )
        self.assertIsNone(
            agentry.marketplace_refresh_hint_line(args, manifest, {"mkt_ok": True, "markets": set()})
        )
        line = agentry.marketplace_refresh_hint_line(
            args, manifest, {"mkt_ok": True, "markets": {"test-agentry"}}
        )
        self.assertIn("traecli plugin marketplace upgrade test-agentry", line)

    def test_print_grouped_report_writes_all_states(self):
        # Fabricate a plan; we only care about print() output.
        plan = [
            ("rules", None, None, "rules/a.md", "missing"),
            ("skills", None, None, "skills/a", "copied-current"),
            ("agents", None, None, "agents/a.md", "copied-stale"),
            ("commands", None, None, "commands/a.md", "copied-current"),
            ("rules", None, None, "rules/b.md", "linked"),
            ("rules", None, None, "rules/c.md", "stale-link"),
        ]
        with mock.patch("builtins.print") as pr:
            agentry.print_grouped_report(plan, 10)
            joined = "\n".join(str(c.args[0]) if c.args else "" for c in pr.call_args_list)
        for token in ("missing", "synced", "stale", "rules", "skills", "agents", "commands"):
            self.assertIn(token, joined)

    def test_print_header_returns_plan_and_label_width(self):
        args = _make_namespace(tool="trae", plugin="a", component=["rules"],
                               project_dir=Path(self._tmp.name), dry_run=True)
        plan, lw = agentry.print_header(args, Path(self._tmp.name), {"rules"}, "install")
        self.assertIsInstance(lw, int)
        self.assertGreater(lw, 0)
        # Plugin "a" declares rule code-quality/a.md, so the plan must include it.
        rels = [str(rel) for _, _, _, rel, _ in plan]
        self.assertTrue(any("a.md" in r for r in rels))


# ---------------------------------------------------------------------------
# Inventory command
# ---------------------------------------------------------------------------


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _FakeRepo(Path(self._tmp.name))
        for p in self.repo.patches():
            p.start()
        agentry.init_colors(False)

    def tearDown(self):
        for p in self.repo.patches():
            p.stop()
        agentry.init_colors(False)
        self._tmp.cleanup()

    def test_component_selection_defaults_to_all(self):
        self.assertEqual(agentry.component_selection(None), set(agentry.COMPONENTS))

    def test_component_selection_expands_all(self):
        self.assertEqual(agentry.component_selection(["skills", "all"]), set(agentry.COMPONENTS))

    def test_build_inventory_counts_selected_components(self):
        manifest = self.repo.manifest_dict
        plugins = agentry.select_plugins(manifest["plugins"], None)
        report = agentry.build_inventory(manifest, plugins, {"skills", "rules"}, include_paths=False)
        self.assertEqual(report["totals"]["plugins"], 2)
        self.assertEqual(report["totals"]["components"]["skills"], 2)
        self.assertEqual(report["totals"]["components"]["rules"], 3)
        self.assertEqual(report["totals"]["components"]["agents"], 0)
        self.assertEqual(report["totals"]["componentEntries"], 5)

    def test_build_inventory_includes_paths(self):
        plugin = self.repo.manifest_dict["plugins"][0]
        report = agentry.build_inventory(
            self.repo.manifest_dict, [plugin], {"skills", "commands", "rules"}, include_paths=True,
        )
        components = report["plugins"][0]["components"]
        self.assertEqual(components["skills"][0]["path"], "plugins/a/skills/skill-one")
        self.assertEqual(components["commands"][0]["path"], "plugins/a/commands/command-one.md")
        self.assertEqual(components["rules"][0]["path"], "rules/code-quality/a.md")

    def test_inventory_count_cell_dims_zero_when_color_enabled(self):
        agentry.init_colors(True)
        self.assertEqual(agentry.inventory_count_cell(0, 2), "\033[2m 0\033[0m")
        self.assertEqual(agentry.inventory_count_cell(3, 2), " 3")

    def test_cmd_inventory_prints_summary_table_by_default(self):
        ns = _make_namespace(plugin=None, component=None, color="never", paths=False, details=False, json=False)
        with mock.patch("builtins.print") as pr:
            rv = agentry.cmd_inventory(ns)
        self.assertEqual(rv, 0)
        joined = "\n".join(str(c.args[0]) if c.args else "" for c in pr.call_args_list)
        self.assertIn("Inventory: test-agentry 0.1.0", joined)
        self.assertIn("plugin", joined)
        self.assertIn("version", joined)
        self.assertIn("skills", joined)
        self.assertIn("a", joined)
        self.assertIn("b", joined)
        self.assertNotIn("plugin a", joined)
        self.assertNotIn("skill-one", joined)

    def test_inventory_summary_title_falls_back_to_brand_when_name_empty(self):
        # When the manifest has no name, the title falls back to BRAND, so a
        # downstream catalog shows its own brand rather than the literal Agentry.
        report = {
            "name": "",
            "version": "",
            "plugins": [],
            "totals": {
                "plugins": 0,
                "componentEntries": 0,
                "components": {c: 0 for c in agentry.COMPONENTS},
            },
        }
        with mock.patch.object(agentry, "BRAND", "Downstream"), \
                mock.patch("builtins.print") as pr:
            agentry.print_inventory_summary(report, set(agentry.COMPONENTS))
        joined = "\n".join(str(c.args[0]) if c.args else "" for c in pr.call_args_list)
        self.assertIn("Inventory: Downstream", joined)
        self.assertNotIn("Inventory: Agentry", joined)

    def test_cmd_inventory_details_prints_component_membership(self):
        ns = _make_namespace(plugin="a", component=["skills"], color="never", paths=False, details=True, json=False)
        with mock.patch("builtins.print") as pr:
            rv = agentry.cmd_inventory(ns)
        self.assertEqual(rv, 0)
        joined = "\n".join(str(c.args[0]) if c.args else "" for c in pr.call_args_list)
        self.assertIn("skills: 1 (skill-one)", joined)
        self.assertNotIn("agent-one", joined)

    def test_cmd_inventory_prints_json_report(self):
        ns = _make_namespace(plugin="a", component=["skills"], color="never", paths=True, details=False, json=True)
        with mock.patch("builtins.print") as pr:
            rv = agentry.cmd_inventory(ns)
        self.assertEqual(rv, 0)
        data = json.loads(pr.call_args.args[0])
        self.assertEqual(data["plugins"][0]["name"], "a")
        self.assertEqual(data["totals"]["components"]["skills"], 1)
        self.assertEqual(data["plugins"][0]["components"]["skills"][0]["path"], "plugins/a/skills/skill-one")


# ---------------------------------------------------------------------------
# Delivery-channel selection and component resolution
# ---------------------------------------------------------------------------


class DeliveryChannelTests(unittest.TestCase):
    def setUp(self):
        agentry.init_colors(False)

    def tearDown(self):
        agentry.init_colors(False)

    def test_resolve_marketplace_explicit_source(self):
        ns = _make_namespace(source="marketplace")
        self.assertTrue(agentry.resolve_marketplace(ns))
        self.assertTrue(ns.global_scope)

        ns = _make_namespace(source="checkout")
        self.assertFalse(agentry.resolve_marketplace(ns))

    def test_resolve_marketplace_default_global_is_marketplace(self):
        ns = _make_namespace(global_scope=True)
        self.assertTrue(agentry.resolve_marketplace(ns))

    def test_resolve_marketplace_default_project_is_checkout(self):
        ns = _make_namespace(global_scope=False)
        self.assertFalse(agentry.resolve_marketplace(ns))

    def test_resolve_marketplace_component_forces_checkout(self):
        # --component always selects checkout, regardless of --global.
        ns = _make_namespace(global_scope=True, component=["rules"])
        self.assertFalse(agentry.resolve_marketplace(ns))

    def test_resolve_marketplace_rejects_marketplace_plus_component(self):
        for component in ("skills", "agents", "commands", "rules"):
            ns = _make_namespace(source="marketplace", component=[component])
            with self.assertRaises(SystemExit):
                agentry.resolve_marketplace(ns)

    def test_resolve_marketplace_rejects_marketplace_plus_component_all(self):
        ns = _make_namespace(source="marketplace", component=["all"])
        with self.assertRaises(SystemExit):
            agentry.resolve_marketplace(ns)

    def test_resolve_selection_default_project_checkout_components(self):
        ns = _make_namespace()
        with mock.patch.object(agentry, "sys") as fake_sys:
            fake_sys.stdin.isatty.return_value = False
            fake_sys.stdout.isatty.return_value = False
            fake_sys.exit = sys.exit
            components = agentry.resolve_selection(ns, [{"name": "a"}], marketplace=False)
        self.assertEqual(components, set(agentry.COMPONENTS))

    def test_resolve_selection_default_global_checkout_components(self):
        ns = _make_namespace(global_scope=True, source="checkout")
        with mock.patch.object(agentry, "sys") as fake_sys:
            fake_sys.stdin.isatty.return_value = False
            fake_sys.stdout.isatty.return_value = False
            fake_sys.exit = sys.exit
            components = agentry.resolve_selection(ns, [{"name": "a"}], marketplace=False)
        self.assertEqual(components, set(agentry.COMPONENTS))

    def test_resolve_selection_default_marketplace_components(self):
        ns = _make_namespace(global_scope=True)
        with mock.patch.object(agentry, "sys") as fake_sys:
            fake_sys.stdin.isatty.return_value = False
            fake_sys.stdout.isatty.return_value = False
            fake_sys.exit = sys.exit
            components = agentry.resolve_selection(ns, [{"name": "a"}], marketplace=True)
        self.assertEqual(components, {"rules"})

    def test_resolve_selection_explicit_tool_required_when_non_interactive(self):
        ns = _make_namespace(tool=None)
        with mock.patch.object(agentry, "sys") as fake_sys:
            fake_sys.stdin.isatty.return_value = False
            fake_sys.stdout.isatty.return_value = False
            fake_sys.exit = lambda *a, **kw: (_ for _ in ()).throw(SystemExit())
            with self.assertRaises(SystemExit):
                agentry.resolve_selection(ns, [{"name": "a"}], marketplace=False)

    def test_resolve_selection_honors_explicit_component(self):
        ns = _make_namespace(component=["skills", "commands", "rules"])
        with mock.patch.object(agentry, "sys") as fake_sys:
            fake_sys.stdin.isatty.return_value = False
            fake_sys.stdout.isatty.return_value = False
            components = agentry.resolve_selection(ns, [{"name": "a"}], marketplace=False)
        self.assertEqual(components, {"skills", "commands", "rules"})

    def test_resolve_selection_expands_component_all(self):
        ns = _make_namespace(component=["all"])
        with mock.patch.object(agentry, "sys") as fake_sys:
            fake_sys.stdin.isatty.return_value = False
            fake_sys.stdout.isatty.return_value = False
            components = agentry.resolve_selection(ns, [{"name": "a"}], marketplace=False)
        self.assertEqual(components, set(agentry.COMPONENTS))

    def test_resolve_selection_component_all_dedupes_explicit_components(self):
        ns = _make_namespace(component=["all", "rules"])
        with mock.patch.object(agentry, "sys") as fake_sys:
            fake_sys.stdin.isatty.return_value = False
            fake_sys.stdout.isatty.return_value = False
            components = agentry.resolve_selection(ns, [{"name": "a"}], marketplace=False)
        self.assertEqual(components, set(agentry.COMPONENTS))

    def test_resolve_selection_interactive_prompts_for_tool_plugin_component_and_symlink(self):
        ns = _make_namespace(tool=None, defaults=False)
        choices = iter(["trae", ["a", "b"], ["rules"]])

        with mock.patch.object(sys.stdin, "isatty", return_value=True), \
                mock.patch.object(sys.stdout, "isatty", return_value=True), \
                mock.patch.object(agentry, "confirm", side_effect=[False, True]), \
                mock.patch.object(agentry, "choose", side_effect=lambda *a, **kw: next(choices)):
            components = agentry.resolve_selection(ns, [{"name": "a"}, {"name": "b"}], marketplace=False)

        self.assertEqual(ns.tool, "trae")
        self.assertEqual(ns.plugin, ["a", "b"])
        self.assertTrue(ns.symlink)
        self.assertEqual(components, {"rules"})

    def test_resolve_selection_interactive_plugin_prompt_is_multi_select(self):
        ns = _make_namespace(tool="trae", defaults=False)
        choices = iter([["a", "b"], ["rules"]])

        with mock.patch.object(sys.stdin, "isatty", return_value=True), \
                mock.patch.object(sys.stdout, "isatty", return_value=True), \
                mock.patch.object(agentry, "confirm", side_effect=[False, True]), \
                mock.patch.object(agentry, "choose", side_effect=lambda *a, **kw: next(choices)) as choose:
            components = agentry.resolve_selection(ns, [{"name": "a"}, {"name": "b"}], marketplace=False)

        self.assertEqual(ns.plugin, ["a", "b"])
        self.assertEqual(components, {"rules"})
        self.assertEqual(choose.call_args_list[0].args[0], "Which plugins?")
        self.assertTrue(choose.call_args_list[0].kwargs["multi"])

    def test_resolve_selection_interactive_plugin_all_keeps_default(self):
        ns = _make_namespace(tool="trae", defaults=False)
        choices = iter([["all"], ["rules"]])

        with mock.patch.object(sys.stdin, "isatty", return_value=True), \
                mock.patch.object(sys.stdout, "isatty", return_value=True), \
                mock.patch.object(agentry, "confirm", side_effect=[False, True]), \
                mock.patch.object(agentry, "choose", side_effect=lambda *a, **kw: next(choices)):
            components = agentry.resolve_selection(ns, [{"name": "a"}, {"name": "b"}], marketplace=False)

        self.assertIsNone(ns.plugin)
        self.assertEqual(components, {"rules"})


# ---------------------------------------------------------------------------
# Plugin orchestration helpers (marketplace queries, install/uninstall actions)
# ---------------------------------------------------------------------------


class PluginOrchestrationTests(unittest.TestCase):
    """Mock the tool-CLI gateway and drive report_plugin_state / act_on_*."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _FakeRepo(Path(self._tmp.name))
        for p in self.repo.patches():
            p.start()
        agentry.init_colors(False)

    def tearDown(self):
        for p in self.repo.patches():
            p.stop()
        agentry.init_colors(False)
        self._tmp.cleanup()

    def _run_patch(self, stdout_by_cmd):
        def fake_subprocess(argv, *args, **kwargs):
            key = " ".join(argv[1:])
            out, code = stdout_by_cmd.get(key, ("", 0))
            m = mock.MagicMock()
            m.returncode = code
            m.stdout = out
            m.stderr = ""
            return m
        return mock.patch.object(subprocess, "run", side_effect=fake_subprocess)

    def test_query_marketplaces_parses_list(self):
        out = "✓ test-agentry\n✓ other\n"
        with mock.patch.object(agentry, "run_tool_command",
                               return_value=(True, out, "")):
            ok, names = agentry.query_marketplaces("/bin/fake")
        self.assertTrue(ok)
        self.assertEqual(names, {"test-agentry", "other"})

    def test_query_installed_plugins_parses_name_and_origin(self):
        out = "✓ a\n    From marketplace: test-agentry\n✓ c\n    From local: /tmp/c\n"
        with mock.patch.object(agentry, "run_tool_command",
                               return_value=(True, out, "")):
            ok, installed = agentry.query_installed_plugins("/bin/fake")
        self.assertTrue(ok)
        self.assertEqual(installed["a"], "marketplace")
        self.assertEqual(installed["c"], "local")

    def test_resolve_tool_binary_uses_shutil_which(self):
        # Not found -> None
        with mock.patch.object(shutil, "which", return_value=None):
            self.assertIsNone(agentry.resolve_tool_binary("trae"))
        # Found -> returns the resolved path
        with mock.patch.object(shutil, "which", return_value="/usr/bin/traecli"):
            self.assertEqual(agentry.resolve_tool_binary("trae"), "/usr/bin/traecli")

    def test_report_plugin_state_returns_snapshot_when_binary_missing(self):
        args = _make_namespace(tool="trae")
        manifest = self.repo.manifest_dict
        plugins = manifest["plugins"]
        with mock.patch.object(agentry, "resolve_tool_binary", return_value=None), \
                mock.patch("builtins.print"):
            snap = agentry.report_plugin_state(args, manifest, plugins)
        self.assertIsNone(snap["binary"])
        self.assertEqual(snap["markets"], set())
        self.assertEqual(snap["installed"], {})
        self.assertFalse(snap["mkt_ok"])
        self.assertFalse(snap["list_ok"])

    def test_report_plugin_state_populates_markets_and_installed(self):
        args = _make_namespace(tool="trae")
        manifest = self.repo.manifest_dict
        plugins = manifest["plugins"]

        def fake_run(binary, cmd_args, dry_run, capture=False):
            if "marketplace" in cmd_args:
                return True, "✓ test-agentry\n", ""
            return True, "✓ a\n    From marketplace: test-agentry\n", ""
        with mock.patch.object(agentry, "run_tool_command", side_effect=fake_run), \
                mock.patch.object(agentry, "resolve_tool_binary", return_value="/bin/fake"), \
                mock.patch("builtins.print"):
            snap = agentry.report_plugin_state(args, manifest, plugins)
        self.assertIn("test-agentry", snap["markets"])
        self.assertIn("a", snap["installed"])

    def test_report_plugin_state_marks_query_failures_unknown(self):
        args = _make_namespace(tool="trae")
        manifest = self.repo.manifest_dict

        def fake_run(binary, cmd_args, dry_run, capture=False):
            return False, "", "failed"

        with mock.patch.object(agentry, "run_tool_command", side_effect=fake_run), \
                mock.patch.object(agentry, "resolve_tool_binary", return_value="/bin/fake"), \
                mock.patch("builtins.print") as pr:
            snap = agentry.report_plugin_state(args, manifest, manifest["plugins"])

        self.assertFalse(snap["mkt_ok"])
        self.assertFalse(snap["list_ok"])
        text = "\n".join(agentry._strip_color(str(c.args[0])) for c in pr.call_args_list if c.args)
        self.assertIn("query failed", text)

    def test_act_on_plugins_install_happy_path_yes(self):
        args = _make_namespace(tool="trae", yes=True, dry_run=False)
        manifest = self.repo.manifest_dict
        plugins = [plugins for plugins in manifest["plugins"] if plugins["name"] == "a"]
        snapshot = {
            "binary": "/bin/fake",
            "markets": {"test-agentry"},
            "installed": {},
            "mkt_ok": True,
            "list_ok": True,
        }
        call_log = []

        def fake_run(binary, cmd_args, dry_run, capture=False):
            call_log.append(cmd_args)
            return True, "", ""
        with mock.patch.object(agentry, "run_tool_command", side_effect=fake_run):
            unresolved, rows = agentry.act_on_plugins_install(
                args, manifest, plugins, interactive=False, action_width=15, state=snapshot
            )
        self.assertEqual(unresolved, 0)
        text = "\n".join(agentry._strip_color(r) for r in rows)
        self.assertIn("installed", text)
        # The marketplace is already present, so only plugin install commands
        # are expected — no "marketplace add".
        self.assertTrue(any("install" in " ".join(cmd) for cmd in call_log))

    def test_act_on_plugins_install_missing_marketplace_adds_it(self):
        args = _make_namespace(tool="trae", yes=True, dry_run=False)
        manifest = {
            "name": "test-agentry",
            "owner": "tester",
            "repository": "https://example.invalid/t/test-agentry.git",
            "plugins": [{"name": "a"}],
        }
        snapshot = {
            "binary": "/bin/fake",
            "markets": set(),  # marketplace not added yet
            "installed": {},
            "mkt_ok": True,
            "list_ok": True,
        }
        commands = []

        def fake_run(binary, cmd_args, dry_run, capture=False):
            commands.append(list(cmd_args))
            # Simulate the tool committing the marketplace: after a
            # successful "marketplace add", the marketplace is present.
            if cmd_args[:3] == ["plugin", "marketplace", "add"]:
                snapshot["markets"].add(manifest["name"])
            return True, "", ""
        with mock.patch.object(agentry, "run_tool_command", side_effect=fake_run):
            unresolved, rows = agentry.act_on_plugins_install(
                args, manifest, manifest["plugins"], interactive=False,
                action_width=15, state=snapshot
            )
        self.assertEqual(unresolved, 0)
        joined = " ".join(" ".join(c) for c in commands)
        self.assertIn("marketplace add", joined)
        self.assertIn("plugin install", joined)

    def test_act_on_plugins_install_adds_marketplace_and_installs_plugins_without_snapshot_mutation(self):
        """Plugins install after marketplace add even when the pre-action snapshot is not mutated.

        This guards against a regression where ``ready`` was never set to ``True``
        after a successful marketplace add, so the ``mkt not in present`` check
        (against the unchanged pre-action snapshot) caused all plugins to be
        skipped with "marketplace not ready".
        """
        args = _make_namespace(tool="trae", yes=True, dry_run=False)
        manifest = {
            "name": "test-agentry",
            "owner": "tester",
            "repository": "https://example.invalid/t/test-agentry.git",
            "plugins": [{"name": "a"}],
        }
        snapshot = {
            "binary": "/bin/fake",
            "markets": set(),  # marketplace not added yet
            "installed": {},
            "mkt_ok": True,
            "list_ok": True,
        }
        commands = []

        def fake_run(binary, cmd_args, dry_run, capture=False):
            commands.append(list(cmd_args))
            # Deliberately do NOT mutate snapshot["markets"] — the real CLI
            # updates its own state, but our pre-action snapshot is frozen.
            # The fix must track readiness via the ``ready`` flag, not by
            # relying on the snapshot being mutated.
            return True, "", ""
        with mock.patch.object(agentry, "run_tool_command", side_effect=fake_run):
            unresolved, rows = agentry.act_on_plugins_install(
                args, manifest, manifest["plugins"], interactive=False,
                action_width=15, state=snapshot
            )
        self.assertEqual(unresolved, 0)
        joined = " ".join(" ".join(c) for c in commands)
        self.assertIn("marketplace add", joined)
        self.assertIn("plugin install", joined)
        text = "\n".join(agentry._strip_color(r) for r in rows)
        self.assertNotIn("marketplace not ready", text)

    def test_act_on_plugins_install_declined_marketplace_skips_plugins(self):
        args = _make_namespace(tool="trae", yes=False, dry_run=False)
        manifest = self.repo.manifest_dict
        snapshot = {
            "binary": "/bin/fake",
            "markets": set(),
            "installed": {},
            "mkt_ok": True,
            "list_ok": True,
        }
        with mock.patch.object(agentry, "orchestrate_confirm", return_value=False), \
                mock.patch.object(agentry, "run_tool_command") as run:
            unresolved, rows = agentry.act_on_plugins_install(
                args, manifest, manifest["plugins"], interactive=False,
                action_width=15, state=snapshot
            )
        run.assert_not_called()
        self.assertEqual(unresolved, 1 + len(manifest["plugins"]))
        text = "\n".join(agentry._strip_color(r) for r in rows)
        self.assertIn("declined", text)
        self.assertIn("marketplace not ready", text)

    def test_act_on_plugins_install_failed_command_increments_unresolved(self):
        args = _make_namespace(tool="trae", yes=True, dry_run=False)
        manifest = self.repo.manifest_dict
        plugins = [p for p in manifest["plugins"] if p["name"] == "a"]
        snapshot = {
            "binary": "/bin/fake",
            "markets": {"test-agentry"},
            "installed": {},
            "mkt_ok": True,
            "list_ok": True,
        }

        def fake_run(binary, cmd_args, dry_run, capture=False):
            return False, "", "nope"
        with mock.patch.object(agentry, "run_tool_command", side_effect=fake_run):
            unresolved, rows = agentry.act_on_plugins_install(
                args, manifest, plugins, interactive=False, action_width=15, state=snapshot
            )
        self.assertGreater(unresolved, 0)
        text = "\n".join(agentry._strip_color(r) for r in rows)
        self.assertIn("failed", text)

    def test_act_on_plugins_install_skips_already_installed_without_force(self):
        args = _make_namespace(tool="trae", yes=True, dry_run=False)
        manifest = self.repo.manifest_dict
        snapshot = {
            "binary": "/bin/fake",
            "markets": {"test-agentry"},
            "installed": {"a": "marketplace"},
            "mkt_ok": True,
            "list_ok": True,
        }
        with mock.patch.object(agentry, "run_tool_command") as run:
            unresolved, rows = agentry.act_on_plugins_install(
                args, manifest, [manifest["plugins"][0]], interactive=False,
                action_width=15, state=snapshot
            )
        run.assert_not_called()
        self.assertEqual(unresolved, 0)
        self.assertEqual(rows, [])

    def test_act_on_plugins_uninstall_skips_absent_and_removes_present(self):
        args = _make_namespace(tool="trae", yes=True, dry_run=False)
        manifest = self.repo.manifest_dict
        plugins = manifest["plugins"]
        snapshot = {
            "binary": "/bin/fake",
            "markets": {"test-agentry"},
            "installed": {"a": "marketplace"},  # only "a" installed
            "mkt_ok": True,
            "list_ok": True,
        }
        calls = []

        def fake_run(binary, cmd_args, dry_run, capture=False):
            calls.append(list(cmd_args))
            return True, "", ""
        with mock.patch.object(agentry, "run_tool_command", side_effect=fake_run):
            unresolved, rows = agentry.act_on_plugins_uninstall(
                args, manifest, plugins, interactive=False, action_width=15, state=snapshot
            )
        self.assertEqual(unresolved, 0)
        text = "\n".join(agentry._strip_color(r) for r in rows)
        # plugin "a" is removed; plugin "b" was absent so no row.
        self.assertIn("removed", text)
        self.assertIn("a", text)
        # Plugin b is still absent (no remove command issued for it), but the
        # marketplace should remain because plugin "a" wasn't the last one —
        # wait: both plugins declared and only "a" was installed, so after
        # removal, no Agentry plugins remain. Marketplace should be removed.
        joined = " ".join(" ".join(c) for c in calls)
        self.assertIn("marketplace remove", joined)

    def test_act_on_plugins_uninstall_keeps_marketplace_when_other_agentry_plugins_remain(self):
        args = _make_namespace(tool="trae", yes=True, dry_run=False)
        manifest = self.repo.manifest_dict
        # Remove plugin "a" only; "b" is still installed -> marketplace stays.
        plugins = [p for p in manifest["plugins"] if p["name"] == "a"]
        snapshot = {
            "binary": "/bin/fake",
            "markets": {"test-agentry"},
            "installed": {"a": "marketplace", "b": "marketplace"},
            "mkt_ok": True,
            "list_ok": True,
        }
        calls = []

        def fake_run(binary, cmd_args, dry_run, capture=False):
            calls.append(list(cmd_args))
            return True, "", ""
        with mock.patch.object(agentry, "run_tool_command", side_effect=fake_run):
            unresolved, rows = agentry.act_on_plugins_uninstall(
                args, manifest, plugins, interactive=False, action_width=15, state=snapshot
            )
        self.assertEqual(unresolved, 0)
        joined = " ".join(" ".join(c) for c in calls)
        self.assertNotIn("marketplace remove", joined)
        text = "\n".join(agentry._strip_color(r) for r in rows)
        self.assertIn("kept", text)
        self.assertIn("marketplace", text)

    def test_act_on_plugins_uninstall_declined_plugin_keeps_marketplace(self):
        args = _make_namespace(tool="trae", yes=False, dry_run=False)
        manifest = self.repo.manifest_dict
        plugins = [manifest["plugins"][0]]
        snapshot = {
            "binary": "/bin/fake",
            "markets": {"test-agentry"},
            "installed": {"a": "marketplace"},
            "mkt_ok": True,
            "list_ok": True,
        }
        with mock.patch.object(agentry, "orchestrate_confirm", return_value=False), \
                mock.patch.object(agentry, "run_tool_command") as run:
            unresolved, rows = agentry.act_on_plugins_uninstall(
                args, manifest, plugins, interactive=False,
                action_width=15, state=snapshot
            )
        run.assert_not_called()
        self.assertEqual(unresolved, 1)
        text = "\n".join(agentry._strip_color(r) for r in rows)
        self.assertIn("declined", text)
        self.assertIn("Agentry plugin(s) still installed", text)

    def test_act_on_plugins_uninstall_remaining_note_honors_brand(self):
        # The "<brand> plugin(s) still installed" note must read the active
        # brand, so a downstream catalog's removal report names its own catalog.
        args = _make_namespace(tool="trae", yes=False, dry_run=False)
        manifest = self.repo.manifest_dict
        plugins = [manifest["plugins"][0]]
        snapshot = {
            "binary": "/bin/fake",
            "markets": {"test-agentry"},
            "installed": {"a": "marketplace"},
            "mkt_ok": True,
            "list_ok": True,
        }
        with mock.patch.object(agentry, "BRAND", "Downstream"), \
                mock.patch.object(agentry, "orchestrate_confirm", return_value=False), \
                mock.patch.object(agentry, "run_tool_command"):
            _, rows = agentry.act_on_plugins_uninstall(
                args, manifest, plugins, interactive=False,
                action_width=15, state=snapshot
            )
        text = "\n".join(agentry._strip_color(r) for r in rows)
        self.assertIn("Downstream plugin(s) still installed", text)
        self.assertNotIn("Agentry plugin(s) still installed", text)

    def test_act_on_plugins_uninstall_failed_plugin_keeps_marketplace(self):
        args = _make_namespace(tool="trae", yes=True, dry_run=False)
        manifest = self.repo.manifest_dict
        plugins = [manifest["plugins"][0]]
        snapshot = {
            "binary": "/bin/fake",
            "markets": {"test-agentry"},
            "installed": {"a": "marketplace"},
            "mkt_ok": True,
            "list_ok": True,
        }

        def fake_run(binary, cmd_args, dry_run, capture=False):
            return False, "", "boom"

        with mock.patch.object(agentry, "run_tool_command", side_effect=fake_run):
            unresolved, rows = agentry.act_on_plugins_uninstall(
                args, manifest, plugins, interactive=False,
                action_width=15, state=snapshot
            )
        self.assertEqual(unresolved, 1)
        text = "\n".join(agentry._strip_color(r) for r in rows)
        self.assertIn("failed", text)
        self.assertIn("boom", text)
        self.assertIn("Agentry plugin(s) still installed", text)

    def test_act_on_plugins_uninstall_keeps_marketplace_when_remaining_unknown(self):
        args = _make_namespace(tool="trae", yes=True, dry_run=False)
        manifest = self.repo.manifest_dict
        snapshot = {
            "binary": "/bin/fake",
            "markets": {"test-agentry"},
            "installed": {"a": "marketplace"},
            "mkt_ok": True,
            "list_ok": False,
        }

        with mock.patch.object(agentry, "run_tool_command", return_value=(True, "", "")):
            unresolved, rows = agentry.act_on_plugins_uninstall(
                args, manifest, [manifest["plugins"][0]], interactive=False,
                action_width=15, state=snapshot
            )
        self.assertEqual(unresolved, 1)
        text = "\n".join(agentry._strip_color(r) for r in rows)
        self.assertIn("could not verify remaining plugins", text)



    def test_act_on_plugins_install_passes_capture_true(self):
        """Marketplace add and plugin install must both capture tool output."""
        args = _make_namespace(tool="trae", yes=True, dry_run=False)
        manifest = {
            "name": "test-agentry",
            "owner": "tester",
            "repository": "https://example.invalid/t/test-agentry.git",
            "plugins": [{"name": "a"}],
        }
        snapshot = {
            "binary": "/bin/fake",
            "markets": set(),  # marketplace not present, so add runs
            "installed": {},
            "mkt_ok": True,
            "list_ok": True,
        }
        with mock.patch.object(agentry, "run_tool_command", return_value=(True, "", "")) as run:
            agentry.act_on_plugins_install(
                args, manifest, manifest["plugins"],
                interactive=False, action_width=15, state=snapshot
            )
        calls = run.call_args_list
        self.assertEqual(len(calls), 2)
        # First call: marketplace add — must have capture=True
        self.assertTrue(calls[0].kwargs.get("capture"),
                        f"capture=True missing for {' '.join(calls[0].args[1])}")
        # Second call: plugin install — must also have capture=True
        self.assertTrue(calls[1].kwargs.get("capture"),
                        f"capture=True missing for {' '.join(calls[1].args[1])}")

    def test_act_on_plugins_uninstall_passes_capture_true(self):
        """Plugin uninstall and marketplace remove must both capture tool output."""
        args = _make_namespace(tool="trae", yes=True, dry_run=False)
        manifest = self.repo.manifest_dict
        snapshot = {
            "binary": "/bin/fake",
            "markets": {"test-agentry"},
            "installed": {"a": "marketplace"},
            "mkt_ok": True,
            "list_ok": True,
        }
        with mock.patch.object(agentry, "run_tool_command", return_value=(True, "", "")) as run:
            agentry.act_on_plugins_uninstall(
                args, manifest, [manifest["plugins"][0]],
                interactive=False, action_width=15, state=snapshot
            )
        calls = run.call_args_list
        self.assertEqual(len(calls), 2)
        # First call: plugin uninstall — must have capture=True
        self.assertTrue(calls[0].kwargs.get("capture"),
                        f"capture=True missing for {' '.join(calls[0].args[1])}")
        # Second call: marketplace remove — must have capture=True
        self.assertTrue(calls[1].kwargs.get("capture"),
                        f"capture=True missing for {' '.join(calls[1].args[1])}")

    def test_act_on_plugins_install_suppresses_tool_stdout(self):
        """Tool CLI stdout must not bleed into Agentry's printed output."""
        args = _make_namespace(tool="trae", yes=True, dry_run=False)
        manifest = self.repo.manifest_dict
        plugins = [p for p in manifest["plugins"] if p["name"] == "a"]
        snapshot = {
            "binary": "/bin/fake",
            "markets": {"test-agentry"},
            "installed": {},
            "mkt_ok": True,
            "list_ok": True,
        }

        def fake_run(binary, cmd_args, dry_run, capture=False):
            # Simulate a noisy tool that prints to stdout when not captured
            if not capture:
                print("TOOL NOISE: installing plugin")
            return True, "tool stdout line", "tool stderr line"

        buf = io.StringIO()
        with mock.patch.object(agentry, "run_tool_command", side_effect=fake_run),                 redirect_stdout(buf):
            unresolved, rows = agentry.act_on_plugins_install(
                args, manifest, plugins, interactive=False, action_width=15, state=snapshot
            )
        output = buf.getvalue()
        self.assertNotIn("TOOL NOISE", output)
        self.assertNotIn("tool stdout line", output)
        # Agentry's own structured rows should still be present when printed
        for row in rows:
            print(agentry._strip_color(row), file=buf)
        self.assertIn("installed", buf.getvalue())

# ---------------------------------------------------------------------------
# Generation: generate_claude / generate_trae / generate_skill_references
# ---------------------------------------------------------------------------


class GenerationRoundTripTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _FakeRepo(Path(self._tmp.name))
        for p in self.repo.patches():
            p.start()
        agentry.init_colors(False)

    def tearDown(self):
        for p in self.repo.patches():
            p.stop()
        agentry.init_colors(False)
        self._tmp.cleanup()

    def test_generate_claude_writes_marketplace_and_plugin_manifests(self):
        manifest = self.repo.manifest_dict
        changed = []
        agentry.generate_claude(manifest, check=False, changed=changed)
        marketplace_path = self.repo.root / ".claude-plugin" / "marketplace.json"
        self.assertTrue(marketplace_path.exists())
        data = json.loads(marketplace_path.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], manifest["name"])
        # Every plugin gets a generated plugin.json.
        for plugin in manifest["plugins"]:
            p = self.repo.plugins_dir / plugin["name"] / ".claude-plugin" / "plugin.json"
            self.assertTrue(p.exists(), f"missing {p}")
            pd = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(pd["name"], plugin["name"])
            self.assertIn("GENERATED", pd.get("$generated", ""))

    def test_generate_claude_rejects_traversing_plugin_name(self):
        manifest = {
            **self.repo.manifest_dict,
            "plugins": [{"name": "../outside", "description": "bad"}],
        }
        with self.assertRaises(SystemExit):
            agentry.generate_claude(manifest, check=False, changed=[])
        self.assertFalse((self.repo.root.parent / "outside").exists())

    def test_generate_trae_writes_marketplace(self):
        manifest = self.repo.manifest_dict
        agentry.generate_trae(manifest, check=False, changed=[])
        p = self.repo.root / ".trae-plugin" / "marketplace.json"
        self.assertTrue(p.exists())
        data = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(data["owner"], "tester")
        self.assertEqual(data["plugins"][0]["source"], f"./plugins/{manifest['plugins'][0]['name']}")

    def test_build_skill_reference_strips_frontmatter_and_exclude_blocks(self):
        # Build a rule with frontmatter and an exclude block; verify both are gone.
        self.repo.rules_dir.joinpath("x.md").write_text(
            "---\nfoo: bar\n---\n\nhello\n\n<!-- skill-reference:exclude:begin -->\n"
            "secret\n<!-- skill-reference:exclude:end -->\n\nworld\n",
            encoding="utf-8",
        )
        text = agentry.build_skill_reference("x.md")
        self.assertNotIn("foo: bar", text)
        self.assertNotIn("secret", text)
        self.assertIn("hello", text)
        self.assertIn("world", text)
        self.assertIn("GENERATED", text)

    def test_build_skill_reference_missing_rule_aborts(self):
        with self.assertRaises(SystemExit):
            agentry.build_skill_reference("does/not/exist.md")

    def test_build_skill_reference_rejects_traversing_rule_path(self):
        with self.assertRaises(SystemExit):
            agentry.build_skill_reference("../outside.md")

    def test_write_or_check_rejects_output_outside_repo(self):
        with self.assertRaises(SystemExit):
            agentry.write_or_check(self.repo.root.parent / "outside.json", "{}", check=False, changed=[])

    def test_generate_skill_references_materializes_derived_files(self):
        manifest = self.repo.manifest_dict
        agentry.generate_skill_references(manifest, check=False, changed=[])
        target = self.repo.plugins_dir / "a" / "skills" / "skill-one" / "references" / "a.md"
        self.assertTrue(target.exists())
        self.assertNotIn("foo: bar", target.read_text(encoding="utf-8"))

    def test_generate_skill_references_rejects_traversing_skill_name(self):
        manifest = {
            **self.repo.manifest_dict,
            "plugins": [
                {
                    "name": "a",
                    "description": "plugin a",
                    "skillReferences": {"../outside": ["code-quality/a.md"]},
                }
            ],
        }
        with self.assertRaises(SystemExit):
            agentry.generate_skill_references(manifest, check=False, changed=[])

    def test_check_plugin_readmes_reports_missing_manifest_plugin_readmes(self):
        changed = []
        agentry.check_plugin_readmes(self.repo.manifest_dict, changed)
        self.assertEqual(changed, ["plugins/a/README.md", "plugins/b/README.md"])

    def test_check_plugin_readmes_accepts_existing_manifest_plugin_readmes(self):
        for plugin in self.repo.manifest_dict["plugins"]:
            readme = self.repo.plugins_dir / plugin["name"] / "README.md"
            readme.write_text(f"# {plugin['name']}\n", encoding="utf-8")
        changed = []
        agentry.check_plugin_readmes(self.repo.manifest_dict, changed)
        self.assertEqual(changed, [])

    def test_cmd_generate_runs_end_to_end(self):
        ns = _make_namespace(target="all", check=False)
        # cmd_generate reads MANIFEST and writes files relative to REPO_ROOT.
        rv = agentry.cmd_generate(ns)
        self.assertEqual(rv, 0)
        # Assert the files expected by the other tests are present.
        self.assertTrue((self.repo.root / ".claude-plugin" / "marketplace.json").exists())
        self.assertTrue((self.repo.root / ".trae-plugin" / "marketplace.json").exists())


# ---------------------------------------------------------------------------
# Install / uninstall / status commands: end-to-end in the fake repo
# ---------------------------------------------------------------------------


class InstallUninstallTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.repo = _FakeRepo(Path(self._tmp.name))
        for p in self.repo.patches():
            p.start()
        agentry.init_colors(False)
        # Always run from an empty project dir so tests don't collide.
        self.project = self.tmp / "project"
        self.project.mkdir()
        # Patch stdout to avoid noise.
        self._patcher = mock.patch("builtins.print")
        self.print_mock = self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        for p in self.repo.patches():
            p.stop()
        agentry.init_colors(False)
        self._tmp.cleanup()

    def test_cmd_install_checkout_copies_rules(self):
        args = _make_namespace(
            tool="trae", plugin="a", component=["rules"],
            project_dir=self.project, yes=True, dry_run=False,
        )
        agentry.cmd_install(args)
        # The "rules" target for trae is `.trae/rules` relative to the project.
        rule_a = self.project / ".trae" / "rules" / "code-quality" / "a.md"
        self.assertTrue(rule_a.exists(), f"expected {rule_a}")
        shared = self.project / ".trae" / "rules" / "shared.md"
        self.assertTrue(shared.exists())
        # Skills/agents are not copied because components=["rules"].
        skill_dir = self.project / ".trae" / "skills"
        self.assertFalse(skill_dir.exists())
        command_dir = self.project / ".trae" / "commands"
        self.assertFalse(command_dir.exists())

    def test_cmd_install_project_checkout_defaults_to_all_components(self):
        args = _make_namespace(
            tool="trae", plugin="a",
            project_dir=self.project, yes=True, dry_run=False,
        )
        agentry.cmd_install(args)
        expected = [
            self.project / ".trae" / "skills" / "skill-one" / "SKILL.md",
            self.project / ".trae" / "agents" / "agent-one.md",
            self.project / ".trae" / "commands" / "command-one.md",
            self.project / ".trae" / "rules" / "code-quality" / "a.md",
            self.project / ".trae" / "rules" / "shared.md",
        ]
        for path in expected:
            self.assertTrue(path.exists(), f"expected {path}")

    def test_cmd_install_checkout_copies_commands(self):
        args = _make_namespace(
            tool="trae", plugin="a", component=["commands"],
            project_dir=self.project, yes=True, dry_run=False,
        )
        agentry.cmd_install(args)
        command = self.project / ".trae" / "commands" / "command-one.md"
        self.assertTrue(command.exists(), f"expected {command}")
        self.assertEqual(command.read_text(encoding="utf-8"), "# command-one\n")

    def test_cmd_install_checkout_skips_identical_rerun(self):
        args = _make_namespace(
            tool="trae", plugin="a", component=["rules"],
            project_dir=self.project, yes=True, dry_run=False,
        )
        # Run twice; second run is a no-op for writing.
        mtime_before = None
        agentry.cmd_install(args)
        target = self.project / ".trae" / "rules" / "code-quality" / "a.md"
        mtime_before = target.stat().st_mtime_ns
        agentry.cmd_install(args)
        self.assertEqual(target.stat().st_mtime_ns, mtime_before)

    def test_cmd_install_symlink_mode(self):
        args = _make_namespace(
            tool="trae", plugin="a", component=["rules"],
            project_dir=self.project, yes=True, symlink=True, dry_run=False,
        )
        agentry.cmd_install(args)
        link = self.project / ".trae" / "rules" / "code-quality" / "a.md"
        self.assertTrue(link.is_symlink())
        # The resolved link must point at the canonical rule.
        canonical = self.repo.rules_dir / "code-quality" / "a.md"
        self.assertEqual(link.resolve(), canonical.resolve())

    def test_cmd_install_handles_existing_symlinked_rule(self):
        args = _make_namespace(
            tool="trae", plugin="a", component=["rules"],
            project_dir=self.project, yes=True, symlink=True, dry_run=False,
        )
        agentry.cmd_install(args)
        args.dry_run = True
        agentry.cmd_install(args)
        link = self.project / ".trae" / "rules" / "code-quality" / "a.md"
        self.assertTrue(link.is_symlink())

    def test_cmd_install_dry_run_writes_nothing(self):
        args = _make_namespace(
            tool="trae", plugin="a", component=["rules"],
            project_dir=self.project, yes=True, dry_run=True,
        )
        agentry.cmd_install(args)
        self.assertFalse((self.project / ".trae").exists())

    def test_cmd_install_rejects_traversing_rule_path(self):
        manifest = {
            **SAMPLE_MANIFEST_TWO,
            "plugins": [
                {
                    "name": "a",
                    "description": "plugin a",
                    "rules": ["../outside.md"],
                }
            ],
        }
        self.repo.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        args = _make_namespace(
            tool="trae", plugin="a", component=["rules"],
            project_dir=self.project, yes=True, dry_run=False,
        )
        with self.assertRaises(SystemExit):
            agentry.cmd_install(args)
        self.assertFalse((self.project / ".trae").exists())
        self.assertFalse((self.project / "outside.md").exists())

    def test_cmd_install_rejects_missing_source_file(self):
        (self.repo.rules_dir / "code-quality" / "a.md").unlink()
        args = _make_namespace(
            tool="trae", plugin="a", component=["rules"],
            project_dir=self.project, yes=True, dry_run=False,
        )
        with self.assertRaises(SystemExit):
            agentry.cmd_install(args)
        self.assertFalse((self.project / ".trae").exists())

    def test_cmd_uninstall_removes_components(self):
        args_install = _make_namespace(
            tool="trae", plugin="a", component=["rules"],
            project_dir=self.project, yes=True, dry_run=False,
        )
        agentry.cmd_install(args_install)
        target = self.project / ".trae" / "rules" / "code-quality" / "a.md"
        self.assertTrue(target.exists())

        args_uninstall = _make_namespace(
            tool="trae", plugin="a", component=["rules"],
            project_dir=self.project, yes=True, dry_run=False,
        )
        agentry.cmd_uninstall(args_uninstall)
        self.assertFalse(target.exists())

    def test_cmd_uninstall_refuses_to_remove_drifted_files_without_force(self):
        # Install, then modify the destination so it's no longer linked/current.
        args = _make_namespace(
            tool="trae", plugin="a", component=["rules"],
            project_dir=self.project, yes=True, dry_run=False,
        )
        agentry.cmd_install(args)
        target = self.project / ".trae" / "rules" / "code-quality" / "a.md"
        target.write_text("DRIFTED", encoding="utf-8")
        agentry.cmd_uninstall(args)
        # Without --force, drifted files should be kept in place.
        self.assertTrue(target.exists())

        args_force = _make_namespace(
            tool="trae", plugin="a", component=["rules"],
            project_dir=self.project, yes=True, force=True, dry_run=False,
        )
        agentry.cmd_uninstall(args_force)
        self.assertFalse(target.exists())

    def test_cmd_status_reports_without_writing(self):
        # On a fresh project dir every component is "missing", so status
        # reports drift and exits with 1 (per agentry.py's spec: exit 1
        # on drift). Most importantly, no files are written.
        args = _make_namespace(
            tool="trae", plugin="a", component=["rules"],
            project_dir=self.project, status=True,
        )
        rv = agentry.cmd_install(args)
        self.assertFalse((self.project / ".trae").exists())
        self.assertEqual(rv, 1)

    def test_cmd_status_prints_marketplace_refresh_hint_after_summary(self):
        args = _make_namespace(
            tool="trae", plugin="a", component=["rules"],
            project_dir=self.project, status=True,
        )

        def fake_run(binary, cmd_args, dry_run, capture=False):
            if "marketplace" in cmd_args:
                return True, "✓ test-agentry\n", ""
            return True, "", ""
        with mock.patch.object(agentry, "run_tool_command", side_effect=fake_run), \
                mock.patch.object(agentry, "resolve_tool_binary", return_value="/bin/fake"):
            agentry.cmd_install(args)
        lines = [
            agentry._strip_color(str(c.args[0]))
            for c in self.print_mock.call_args_list
            if c.args
        ]
        summary_index = next(i for i, line in enumerate(lines) if "Summary:" in line)
        hint_index = next(i for i, line in enumerate(lines) if "Hint: refresh with" in line)
        self.assertGreater(hint_index, summary_index)
        self.assertIn("traecli plugin marketplace upgrade test-agentry", lines[hint_index])

    def test_cmd_install_marketplace_aborts_when_binary_missing_and_not_dry_run(self):
        args = _make_namespace(
            tool="trae", plugin="a", source="marketplace",
            project_dir=self.project, yes=True, dry_run=False,
        )
        with mock.patch.object(agentry, "resolve_tool_binary", return_value=None):
            with self.assertRaises(SystemExit):
                agentry.cmd_install(args)

    def test_cmd_install_marketplace_dry_run_does_not_require_binary(self):
        # On --dry-run the installer tolerates a missing binary so the user
        # can preview a workflow that isn't set up yet.
        args = _make_namespace(
            tool="trae", plugin="a", source="marketplace",
            project_dir=self.project, yes=True, dry_run=True,
        )
        with mock.patch.object(agentry, "resolve_tool_binary", return_value=None):
            rv = agentry.cmd_install(args)
        # No SystemExit raised; any clean return is acceptable.
        self.assertIn(rv, (0, None))

    def test_cmd_install_without_yes_skips_existing_in_non_interactive(self):
        # Install once with --yes, then run again without --yes and without
        # --force. The existing files must be left untouched (skipped), not
        # overwritten.
        args_first = _make_namespace(
            tool="trae", plugin="a", component=["rules"],
            project_dir=self.project, yes=True, dry_run=False,
        )
        agentry.cmd_install(args_first)
        target = self.project / ".trae" / "rules" / "code-quality" / "a.md"
        self.assertTrue(target.exists())
        mtime_before = target.stat().st_mtime_ns

        args_second = _make_namespace(
            tool="trae", plugin="a", component=["rules"],
            project_dir=self.project, yes=False, dry_run=False,
        )
        agentry.cmd_install(args_second)
        self.assertEqual(target.stat().st_mtime_ns, mtime_before)



    def test_cmd_install_marketplace_happy_path_captures_output(self):
        """End-to-end marketplace install must pass capture=True to every run_tool_command call."""
        args = _make_namespace(
            tool="trae", plugin="a", source="marketplace",
            project_dir=self.project, yes=True, dry_run=True,
        )
        call_log = []

        def fake_run(binary, cmd_args, dry_run, capture=False):
            call_log.append((list(cmd_args), capture))
            return True, "", ""

        def fake_resolve(tool):
            return "/bin/fake"

        def fake_query_markets(binary):
            return True, set()  # marketplace not present

        def fake_query_installed(binary):
            return True, {}

        # Patch home to a temp dir so even if dry_run didn't prevent writes,
        # we wouldn't touch the real user home.
        fake_home = self.tmp / "fakehome"
        fake_home.mkdir()
        with mock.patch.object(Path, "home", return_value=fake_home), \
                mock.patch.object(agentry, "run_tool_command", side_effect=fake_run), \
                mock.patch.object(agentry, "resolve_tool_binary", side_effect=fake_resolve), \
                mock.patch.object(agentry, "query_marketplaces", side_effect=fake_query_markets), \
                mock.patch.object(agentry, "query_installed_plugins", side_effect=fake_query_installed):
            rv = agentry.cmd_install(args)

        self.assertEqual(rv, 0)
        # Verify every run_tool_command call used capture=True
        for cmd_args, capture in call_log:
            self.assertTrue(capture, f"capture=True missing for {' '.join(cmd_args)}")

# ---------------------------------------------------------------------------
# main() / argparse wiring: exercise the top-level entry point
# ---------------------------------------------------------------------------


class MainTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        # main() reconfigures from its own arguments, so drive it through the
        # public seam (repo_root=self.tmp) rather than patching the globals. The
        # fixture manifest keeps the default name (agentry.json), so manifest_name
        # stays at its default.
        self.repo = _FakeRepo(self.tmp)
        agentry.init_colors(False)
        self.project = self.tmp / "project"
        self.project.mkdir()
        self._patcher = mock.patch("builtins.print")
        self.print_mock = self._patcher.start()
        self._orig_argv = sys.argv[:]

    def tearDown(self):
        sys.argv = self._orig_argv
        self._patcher.stop()
        # Restore the module to its default configuration for later test classes.
        agentry.configure()
        agentry.init_colors(False)
        self._tmp.cleanup()

    def _main(self, *argv):
        """Drive main() against the fixture checkout via the public seam."""
        sys.argv = ["agentry.py", *argv]
        return agentry.main(repo_root=self.tmp)

    def test_main_generate_all_runs_to_completion(self):
        self.assertEqual(self._main("generate"), 0)
        self.assertTrue((self.tmp / ".claude-plugin" / "marketplace.json").exists())

    def test_main_generate_check_detects_drift(self):
        # Run once to generate, then mutate a generated file, then run
        # --check and confirm the return code.
        self._main("generate")
        target = self.tmp / ".claude-plugin" / "marketplace.json"
        target.write_text("DRIFTED", encoding="utf-8")
        self.assertEqual(self._main("generate", "--check"), 1)

    def test_main_generate_check_ignores_plugin_readmes(self):
        self._main("generate")
        self.print_mock.reset_mock()
        self.assertEqual(self._main("generate", "--check"), 0)
        out = "\n".join(str(call.args[0]) for call in self.print_mock.call_args_list if call.args)
        self.assertIn("packaging is up to date", out)
        self.assertNotIn("Missing required plugin README files", out)

    def test_main_validate_requires_plugin_readmes(self):
        self._main("generate")
        self.print_mock.reset_mock()
        self.assertEqual(self._main("validate"), 1)
        out = "\n".join(str(call.args[0]) for call in self.print_mock.call_args_list if call.args)
        self.assertIn("Missing required plugin README files", out)
        self.assertIn("plugins/a/README.md", out)
        self.assertNotIn("Out of date (run", out)
        for plugin in self.repo.manifest_dict["plugins"]:
            readme = self.repo.plugins_dir / plugin["name"] / "README.md"
            readme.write_text(f"# {plugin['name']}\n", encoding="utf-8")
        self.print_mock.reset_mock()
        self.assertEqual(self._main("validate"), 0)
        out = "\n".join(str(call.args[0]) for call in self.print_mock.call_args_list if call.args)
        self.assertIn("Repository validation passed.", out)

    def test_main_install_and_uninstall_checkout_default_flow(self):
        self.assertEqual(self._main(
            "install",
            "--tool", "trae", "--plugin", "a",
            "--component", "rules", "--yes", "--defaults",
            "--project-dir", str(self.project),
            "--color", "never",
        ), 0)
        self.assertTrue((self.project / ".trae" / "rules" / "code-quality" / "a.md").exists())

        self.assertEqual(self._main(
            "uninstall",
            "--tool", "trae", "--plugin", "a",
            "--component", "rules", "--yes", "--defaults",
            "--project-dir", str(self.project),
            "--color", "never",
        ), 0)
        self.assertFalse((self.project / ".trae" / "rules" / "code-quality" / "a.md").exists())

    def test_main_status_does_not_write(self):
        self._main(
            "status",
            "--tool", "trae", "--defaults",
            "--project-dir", str(self.project),
            "--color", "never",
        )
        self.assertFalse((self.project / ".trae").exists())

    def test_main_unknown_command_exits_nonzero(self):
        with self.assertRaises(SystemExit) as cm:
            self._main("nope")
        self.assertNotEqual(cm.exception.code, 0)
        self.assertNotEqual(cm.exception.code, None)

    def test_main_no_subcommand_prints_help_and_returns_zero(self):
        # When no subcommand is given, main() prints help and returns 0
        # (rather than erroring out).
        self.assertEqual(self._main(), 0)


# ---------------------------------------------------------------------------
# Reusable seam: main(repo_root=..., manifest_name=...) lets a downstream
# catalog (reusing this module via git submodule) drive the CLI against its own
# tree and manifest filename. These tests do NOT patch the module globals — they
# rely on main()/configure() to resolve every path from the injected root, so
# they prove the seam works on its own.
# ---------------------------------------------------------------------------


class DownstreamSeamTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        # A fixture catalog whose manifest is intentionally NOT named
        # agentry.json, so a path leak back to the default manifest would fail.
        self.repo = _FakeRepo(self.tmp)
        self.manifest_name = "downstream.json"
        self.repo.manifest_path.rename(self.tmp / self.manifest_name)
        self.project = self.tmp / "project"
        self.project.mkdir()
        self._orig_argv = sys.argv[:]
        # Capture the resolved defaults so we can assert isolation: the module
        # globals must point back at Agentry's own checkout after each run.
        self._default_root = agentry.DEFAULT_REPO_ROOT
        agentry.init_colors(False)

    def tearDown(self):
        sys.argv = self._orig_argv
        # Restore the module to its default configuration for later tests.
        agentry.configure()
        agentry.init_colors(False)
        self._tmp.cleanup()

    def _run(self, *argv):
        """Run main() against the fixture catalog, swallowing stdout."""
        with redirect_stdout(io.StringIO()):
            return agentry.main(
                list(argv),
                repo_root=self.tmp,
                manifest_name=self.manifest_name,
            )

    def test_generate_reads_injected_manifest_not_agentry_json(self):
        # No agentry.json exists in the fixture; generate must read the injected
        # manifest and write packaging under the injected root, not the submodule
        # dir.
        self.assertFalse((self.tmp / "agentry.json").exists())
        rv = self._run("generate")
        self.assertEqual(rv, 0)
        self.assertTrue((self.tmp / ".claude-plugin" / "marketplace.json").exists())
        self.assertTrue((self.tmp / ".trae-plugin" / "marketplace.json").exists())
        # The generated catalog reflects the fixture manifest's name.
        data = json.loads((self.tmp / ".trae-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(data["name"], self.repo.manifest_dict["name"])

    def test_install_writes_under_injected_root(self):
        rv = self._run(
            "install", "--tool", "trae", "--plugin", "a",
            "--component", "rules", "--yes", "--defaults",
            "--project-dir", str(self.project), "--color", "never",
        )
        self.assertEqual(rv, 0)
        self.assertTrue((self.project / ".trae" / "rules" / "code-quality" / "a.md").exists())

    def test_default_main_after_injected_run_resets_to_agentry_checkout(self):
        # The real regression guard for sequential / repeated main() calls: an
        # injected run must not leave the module globals pointed at the fixture.
        # A subsequent plain main() must operate on Agentry's own checkout.
        self._run("generate")
        self.assertNotEqual(agentry.REPO_ROOT, self._default_root.resolve())  # injection took effect
        sys.argv = ["agentry.py", "inventory", "--color", "never"]
        with redirect_stdout(io.StringIO()):
            rv = agentry.main()  # plain call, no kwargs
        self.assertEqual(rv, 0)
        self.assertEqual(agentry.REPO_ROOT, self._default_root.resolve())
        self.assertEqual(agentry.MANIFEST, self._default_root.resolve() / "agentry.json")

    def test_default_main_still_targets_agentry_checkout(self):
        # A plain main() call (no kwargs) must resolve to Agentry's own root and
        # agentry.json, preserving existing `scripts/agentry.py ...` behavior.
        sys.argv = ["agentry.py", "inventory", "--color", "never"]
        with redirect_stdout(io.StringIO()):
            rv = agentry.main()
        self.assertEqual(rv, 0)
        self.assertEqual(agentry.REPO_ROOT, self._default_root.resolve())
        self.assertEqual(agentry.MANIFEST, self._default_root.resolve() / "agentry.json")

    def test_inject_root_only_uses_default_manifest_name(self):
        # repo_root given, manifest_name defaulted: must read <root>/agentry.json
        # (the `repo_root is not None` arm of the seam, exercised in isolation).
        default_manifest = self.tmp / "agentry.json"
        default_manifest.write_text(
            (self.tmp / self.manifest_name).read_text(encoding="utf-8"), encoding="utf-8")
        sys.argv = ["agentry.py", "inventory", "--color", "never"]
        with redirect_stdout(io.StringIO()):
            rv = agentry.main(repo_root=self.tmp)
        self.assertEqual(rv, 0)
        self.assertEqual(agentry.REPO_ROOT, self.tmp.resolve())
        self.assertEqual(agentry.MANIFEST, self.tmp.resolve() / "agentry.json")

    def test_inject_manifest_name_only_targets_default_root(self):
        # manifest_name given, repo_root defaulted: must target the default root
        # with the given manifest filename (the manifest_name arm in isolation).
        sys.argv = ["agentry.py", "--help"]
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            agentry.main(["--help"], manifest_name="other.json")
        self.assertEqual(agentry.REPO_ROOT, self._default_root.resolve())
        self.assertEqual(agentry.MANIFEST, self._default_root.resolve() / "other.json")

    def test_prog_kwarg_sets_help_program_name(self):
        # The downstream program name must propagate into the usage/prog line.
        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit):
            agentry.main(["--help"], repo_root=self.tmp,
                         manifest_name=self.manifest_name, prog="downstream")
        out = buf.getvalue()
        self.assertIn("usage: downstream", out)
        self.assertNotIn("agentry.py", out)

    def test_default_prog_is_agentry_py(self):
        # prog defaults to agentry.py in the usage line even when the manifest
        # name (which legitimately appears elsewhere in help) differs.
        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit):
            agentry.main(["--help"], repo_root=self.tmp, manifest_name=self.manifest_name)
        out = buf.getvalue()
        self.assertIn("usage: agentry.py", out)
        self.assertNotIn("usage: downstream", out)

    def test_brand_kwarg_sets_help_banner_and_run_header(self):
        # The downstream brand must replace "Agentry" in the help banner and in
        # the install/status/uninstall run-header title.
        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit):
            agentry.main(["--help"], repo_root=self.tmp,
                         manifest_name=self.manifest_name, prog="downstream.py", brand="Downstream")
        help_out = buf.getvalue()
        self.assertIn("Downstream maintenance CLI.", help_out)
        self.assertNotIn("Agentry maintenance CLI.", help_out)

        buf = io.StringIO()
        with redirect_stdout(buf):
            rv = agentry.main(
                ["status", "--tool", "trae", "--defaults",
                 "--project-dir", str(self.project), "--color", "never"],
                repo_root=self.tmp, manifest_name=self.manifest_name,
                prog="downstream.py", brand="Downstream")
        header = buf.getvalue()
        self.assertEqual(rv, 1)  # fresh project: everything missing -> drift
        self.assertIn("Downstream — trae,", header)
        self.assertNotIn("Agentry — trae,", header)

    def test_default_brand_keeps_agentry_in_help_and_header(self):
        # With brand defaulted, help/header text stays "Agentry" even for an
        # injected downstream root, preserving Agentry's own output.
        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit):
            agentry.main(["--help"], repo_root=self.tmp, manifest_name=self.manifest_name)
        self.assertIn("Agentry maintenance CLI.", buf.getvalue())

    def test_generate_help_names_downstream_manifest(self):
        # The generate subcommand help must name the active manifest filename.
        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit):
            agentry.main(["generate", "--help"], repo_root=self.tmp,
                         manifest_name=self.manifest_name, prog="downstream.py")
        out = buf.getvalue()
        self.assertIn("Regenerate per-tool packaging from downstream.json.", out)
        self.assertNotIn("agentry.json", out)

    def test_explicit_argv_overrides_sys_argv(self):
        # An explicit argv list must win over a poisoned sys.argv.
        sys.argv = ["agentry.py", "this-would-error"]
        rv = self._run("inventory", "--color", "never")
        self.assertEqual(rv, 0)

    def test_generate_output_confinement_uses_injected_root(self):
        # Prove the write_or_check escape guard re-anchors to the INJECTED root.
        # A static "../.." rule path would be rejected earlier by
        # validate_path_fragment and never reach the output guard, so instead
        # symlink the skill's references/ dir to a location outside the injected
        # root: the rule path stays a valid fragment, but the resolved write
        # destination escapes, which only write_or_check (keyed on REPO_ROOT) can
        # catch. The fixture manifest already declares
        # skillReferences {"skill-one": ["code-quality/a.md"]}.
        escape_dir = self.tmp.parent
        refs = self.tmp / "plugins" / "a" / "skills" / "skill-one" / "references"
        refs.symlink_to(escape_dir, target_is_directory=True)
        with self.assertRaises(SystemExit) as cm:
            self._run("generate")
        self.assertIn("escapes", str(cm.exception))
        # Nothing was written through the escaping symlink.
        self.assertFalse((escape_dir / "a.md").exists())

    def test_missing_injected_manifest_aborts_with_manifest_error(self):
        (self.tmp / self.manifest_name).unlink()
        with self.assertRaises(SystemExit) as cm:
            self._run("inventory")
        self.assertIn("manifest not found", str(cm.exception))

    # --- generated provenance text names the active manifest/CLI -------------
    # The seam threads repo_root/manifest_name/prog through path resolution AND
    # the human-facing text baked into generated artifacts, so a downstream
    # catalog's files point a maintainer at its own manifest/CLI rather than the
    # (read-only, submodule) agentry.json / scripts/agentry.py.

    def _generated_blobs(self):
        """Return every generated artifact's text after a downstream generate."""
        return {
            "trae": (self.tmp / ".trae-plugin" / "marketplace.json").read_text(encoding="utf-8"),
            "claude": (self.tmp / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"),
            "plugin": (self.tmp / "plugins" / "a" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"),
            "skillref": (
                self.tmp / "plugins" / "a" / "skills" / "skill-one" / "references" / "a.md"
            ).read_text(encoding="utf-8"),
        }

    def _generate(self, *argv, prog="downstream.py"):
        """Run generate against the fixture as a downstream catalog named ``prog``."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            rv = agentry.main(
                list(argv), repo_root=self.tmp,
                manifest_name=self.manifest_name, prog=prog)
        return rv, buf.getvalue()

    def test_generated_text_names_downstream_manifest_and_cli(self):
        # The $generated banner (both marketplaces) and the skillReferences note
        # must name the injected manifest filename and downstream CLI path.
        rv, _ = self._generate("generate")
        self.assertEqual(rv, 0)
        blobs = self._generated_blobs()
        self.assertEqual(
            json.loads(blobs["trae"])["$generated"],
            "GENERATED from downstream.json by 'scripts/downstream.py generate trae'. Do not edit by hand.",
        )
        self.assertEqual(
            json.loads(blobs["claude"])["$generated"],
            "GENERATED from downstream.json by 'scripts/downstream.py generate claude'. Do not edit by hand.",
        )
        self.assertIn("by 'scripts/downstream.py generate'", blobs["skillref"])

    def test_generated_text_never_leaks_agentry_literals(self):
        # The negative guard: no generated artifact may reference Agentry's own
        # manifest filename or CLI path when a downstream catalog generated it.
        self._generate("generate")
        for label, blob in self._generated_blobs().items():
            self.assertNotIn("agentry.json", blob, f"agentry.json leaked into {label}")
            self.assertNotIn("scripts/agentry.py", blob, f"scripts/agentry.py leaked into {label}")

    def test_check_message_names_downstream_cli(self):
        # The `generate --check` "out of date" hint must point at the downstream
        # CLI so a maintainer runs the right command to refresh packaging.
        self._generate("generate")
        trae = self.tmp / ".trae-plugin" / "marketplace.json"
        trae.write_text(trae.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        rv, out = self._generate("generate", "--check")
        self.assertEqual(rv, 1)
        self.assertIn("run 'scripts/downstream.py generate'", out)
        self.assertNotIn("scripts/agentry.py", out)

    def test_default_prog_keeps_agentry_cli_in_generated_text(self):
        # With prog defaulted, generated text uses scripts/agentry.py while the
        # manifest name still follows the injected manifest: proves the manifest
        # label derives from MANIFEST and the CLI name from prog, independently.
        self._generate("generate", prog=agentry.DEFAULT_PROG)
        self.assertEqual(
            json.loads((self.tmp / ".trae-plugin" / "marketplace.json").read_text(encoding="utf-8"))["$generated"],
            "GENERATED from downstream.json by 'scripts/agentry.py generate trae'. Do not edit by hand.",
        )


# ---------------------------------------------------------------------------
# evaluate: behavioral evaluation for authoring artifacts
# ---------------------------------------------------------------------------


VALID_SCENARIO = """\
+++
schema = "agentry.authoring-evaluation.scenario"
schema_version = 1
id = "seq"
artifact = "plugins/a/skills/skill-one/SKILL.md"
kind = "skill"
baseline_failure = "Reads existing threads before deriving findings."

[fixtures]
diff = "fixtures/change.diff"

[[checks]]
id = "findings-first"
type = "rubric"
required = true
target = "transcript"
expect = "Derives findings before dedupe."

[[checks]]
id = "mentions-cache"
type = "required-text"
required = false
target = "final"
value = "cache"
+++

## Prompt

Review this PR.

## Context

The diff contains a regression.
"""


def _write_scenario(repo_root, plugin, kind_dir, artifact_key, name, body,
                    fixtures=None):
    """Write a scenario file (and optional fixtures) under a plugin eval tree."""
    scenario_dir = (Path(repo_root) / "plugins" / plugin / "eval" / kind_dir / artifact_key)
    scenario_dir.mkdir(parents=True, exist_ok=True)
    path = scenario_dir / f"{name}.md"
    path.write_text(body, encoding="utf-8")
    for rel, content in (fixtures or {}).items():
        fpath = scenario_dir / rel
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content, encoding="utf-8")
    return path


class ScenarioParseTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.path = _write_scenario(
            self.root, "a", "skills", "skill-one", "seq", VALID_SCENARIO,
            fixtures={"fixtures/change.diff": "diff --git ...\n"},
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_valid_single_turn_scenario_parses(self):
        scenario = ec.parse_scenario(self.path)
        self.assertEqual(scenario["id"], "seq")
        self.assertEqual(scenario["kind"], "skill")
        self.assertEqual(scenario["_sections"]["Prompt"], "Review this PR.")
        self.assertEqual(len(scenario["checks"]), 2)

    def test_missing_frontmatter_fence_aborts(self):
        self.path.write_text("no frontmatter here\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            ec.parse_scenario(self.path)

    def test_unterminated_frontmatter_fence_aborts(self):
        self.path.write_text("+++\nid = 'x'\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            ec.parse_scenario(self.path)

    def test_invalid_toml_aborts(self):
        self.path.write_text("+++\nid = = broken\n+++\n\n## Prompt\nx\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            ec.parse_scenario(self.path)

    def test_missing_required_field_aborts(self):
        body = VALID_SCENARIO.replace('baseline_failure = "Reads existing threads before deriving findings."\n', "")
        self.path.write_text(body, encoding="utf-8")
        with self.assertRaises(SystemExit):
            ec.parse_scenario(self.path)

    def test_rubric_check_missing_expect_aborts(self):
        body = VALID_SCENARIO.replace('expect = "Derives findings before dedupe."\n', "")
        self.path.write_text(body, encoding="utf-8")
        with self.assertRaises(SystemExit):
            ec.parse_scenario(self.path)

    def test_check_targeting_undeclared_turn_aborts(self):
        body = VALID_SCENARIO.replace('target = "transcript"', 'target = "turn:missing"', 1)
        self.path.write_text(body, encoding="utf-8")
        with self.assertRaises(SystemExit):
            ec.parse_scenario(self.path)

    def test_override_without_reason_is_allowed(self):
        # override_reason is no longer required: a coherent override (normal tier
        # threshold 3, repetitions 7 -> 3/7) parses fine without a reason.
        body = VALID_SCENARIO.replace(
            'baseline_failure = "Reads existing threads before deriving findings."\n',
            'baseline_failure = "x"\nrepetitions = 7\n',
        )
        self.path.write_text(body, encoding="utf-8")
        scenario = ec.parse_scenario(self.path)  # must not raise
        self.assertEqual(ec._evidence_threshold(scenario), (7, 3))

    def test_incoherent_evidence_pair_aborts(self):
        # threshold > repetitions is unsatisfiable and must abort at parse time.
        body = VALID_SCENARIO.replace(
            'baseline_failure = "Reads existing threads before deriving findings."\n',
            'baseline_failure = "x"\nrepetitions = 2\nstability_threshold = 4\n',
        )
        self.path.write_text(body, encoding="utf-8")
        with self.assertRaises(SystemExit):
            ec.parse_scenario(self.path)

    def test_multi_turn_scenario_resolves_turns(self):
        body = """\
+++
schema = "agentry.authoring-evaluation.scenario"
schema_version = 1
id = "confirm"
artifact = "plugins/a/skills/skill-one/SKILL.md"
kind = "skill"
baseline_failure = "Publishes without confirmation."

[interaction]
mode = "multi-turn"

[[turns]]
id = "initial"
body = "Initial Request"

[[turns]]
id = "confirmation"
body = "Confirmation"

[[checks]]
id = "asks-first"
type = "rubric"
required = true
target = "turn:initial"
expect = "Asks for confirmation."
+++

## Initial Request

Publish these findings.

## Confirmation

Confirmed. Publish.
"""
        self.path.write_text(body, encoding="utf-8")
        scenario = ec.parse_scenario(self.path)
        self.assertEqual(scenario["interaction"]["mode"], "multi-turn")
        self.assertEqual([t["id"] for t in scenario["turns"]], ["initial", "confirmation"])
        self.assertEqual(scenario["_sections"]["Initial Request"], "Publish these findings.")

    def _deterministic(self, check_toml):
        return (
            "+++\n"
            'schema = "agentry.authoring-evaluation.scenario"\n'
            "schema_version = 1\n"
            'id = "det"\n'
            'artifact = "plugins/a/skills/skill-one/SKILL.md"\n'
            'kind = "skill"\n'
            'baseline_failure = "x"\n\n'
            + check_toml
            + "\n+++\n\n## Prompt\n\ngo\n"
        )

    def test_required_text_check_needs_value(self):
        self.path.write_text(self._deterministic(
            '[[checks]]\nid = "c"\ntype = "required-text"\nrequired = true\ntarget = "final"\n'),
            encoding="utf-8")
        with self.assertRaises(SystemExit):
            ec.parse_scenario(self.path)

    def test_regex_check_needs_pattern(self):
        self.path.write_text(self._deterministic(
            '[[checks]]\nid = "c"\ntype = "regex"\nrequired = true\ntarget = "final"\n'),
            encoding="utf-8")
        with self.assertRaises(SystemExit):
            ec.parse_scenario(self.path)

    def test_json_field_check_needs_field(self):
        self.path.write_text(self._deterministic(
            '[[checks]]\nid = "c"\ntype = "json-field"\nrequired = true\ntarget = "final"\n'),
            encoding="utf-8")
        with self.assertRaises(SystemExit):
            ec.parse_scenario(self.path)

    def test_ordered_check_needs_phrases_list(self):
        self.path.write_text(self._deterministic(
            '[[checks]]\nid = "c"\ntype = "ordered"\nrequired = true\ntarget = "final"\n'),
            encoding="utf-8")
        with self.assertRaises(SystemExit):
            ec.parse_scenario(self.path)

    def test_valid_deterministic_check_parses(self):
        self.path.write_text(self._deterministic(
            '[[checks]]\nid = "c"\ntype = "required-text"\nrequired = true\ntarget = "final"\nvalue = "cache"\n'),
            encoding="utf-8")
        scenario = ec.parse_scenario(self.path)
        self.assertEqual(scenario["checks"][0]["type"], "required-text")

    def test_unknown_check_type_aborts(self):
        self.path.write_text(self._deterministic(
            '[[checks]]\nid = "c"\ntype = "bogus"\nrequired = true\ntarget = "final"\n'),
            encoding="utf-8")
        with self.assertRaises(SystemExit):
            ec.parse_scenario(self.path)

    def test_unknown_target_aborts(self):
        self.path.write_text(self._deterministic(
            '[[checks]]\nid = "c"\ntype = "rubric"\nrequired = true\ntarget = "nowhere"\nexpect = "y"\n'),
            encoding="utf-8")
        with self.assertRaises(SystemExit):
            ec.parse_scenario(self.path)

    def test_duplicate_check_id_aborts(self):
        dup = ('[[checks]]\nid = "c"\ntype = "rubric"\nrequired = true\ntarget = "final"\nexpect = "y"\n\n'
               '[[checks]]\nid = "c"\ntype = "rubric"\nrequired = true\ntarget = "final"\nexpect = "z"\n')
        self.path.write_text(self._deterministic(dup), encoding="utf-8")
        with self.assertRaises(SystemExit):
            ec.parse_scenario(self.path)

    def test_unknown_kind_aborts(self):
        body = VALID_SCENARIO.replace('kind = "skill"', 'kind = "widget"')
        self.path.write_text(body, encoding="utf-8")
        with self.assertRaises(SystemExit):
            ec.parse_scenario(self.path)

    def test_unknown_evidence_tier_aborts(self):
        body = VALID_SCENARIO.replace(
            'baseline_failure = "Reads existing threads before deriving findings."\n',
            'baseline_failure = "x"\nevidence_tier = "gold"\n')
        self.path.write_text(body, encoding="utf-8")
        with self.assertRaises(SystemExit):
            ec.parse_scenario(self.path)

    def test_section_parser_ignores_headings_in_code_fence(self):
        body = (
            "+++\n"
            'schema = "agentry.authoring-evaluation.scenario"\n'
            "schema_version = 1\n"
            'id = "fenced"\n'
            'artifact = "plugins/a/skills/skill-one/SKILL.md"\n'
            'kind = "skill"\n'
            'baseline_failure = "x"\n\n'
            '[[checks]]\nid = "c"\ntype = "rubric"\nrequired = true\ntarget = "final"\nexpect = "y"\n'
            "+++\n\n"
            "## Prompt\n\n"
            "Review this.\n\n"
            "```markdown\n"
            "## Not A Heading\n"
            "sample body\n"
            "```\n\n"
            "trailing prompt line\n"
        )
        self.path.write_text(body, encoding="utf-8")
        scenario = ec.parse_scenario(self.path)
        # The fenced `## Not A Heading` stays inside the Prompt section.
        self.assertIn("## Not A Heading", scenario["_sections"]["Prompt"])
        self.assertIn("trailing prompt line", scenario["_sections"]["Prompt"])
        self.assertNotIn("Not A Heading", scenario["_sections"])


class SchemaGuardTests(unittest.TestCase):
    def test_accepts_supported_version(self):
        ec._require_schema(
            {"schema": ec.RESULT_SCHEMA, "schema_version": 1}, ec.RESULT_SCHEMA, "x")

    def test_rejects_unknown_schema(self):
        with self.assertRaises(SystemExit):
            ec._require_schema({"schema": "other", "schema_version": 1}, ec.RESULT_SCHEMA, "x")

    def test_rejects_unsupported_major(self):
        with self.assertRaises(SystemExit):
            ec._require_schema(
                {"schema": ec.RESULT_SCHEMA, "schema_version": 2}, ec.RESULT_SCHEMA, "x")

    def test_rejects_non_int_version(self):
        with self.assertRaises(SystemExit):
            ec._require_schema(
                {"schema": ec.RESULT_SCHEMA, "schema_version": "1"}, ec.RESULT_SCHEMA, "x")

    def test_schemas_version_independently(self):
        # Three schema markers; run manifest and case share the run schema and
        # are told apart by run_document, so there is no separate case marker.
        self.assertIn(ec.SCENARIO_SCHEMA, ec.SUPPORTED_SCHEMA_VERSIONS)
        self.assertIn(ec.RUN_SCHEMA, ec.SUPPORTED_SCHEMA_VERSIONS)
        self.assertIn(ec.RESULT_SCHEMA, ec.SUPPORTED_SCHEMA_VERSIONS)
        self.assertFalse(hasattr(agentry, "PACKET_SCHEMA"))


class _EvalRepo:
    """A fake repo with a manifest, artifacts, and an eval scenario tree."""

    def __init__(self, tmp):
        self.root = Path(tmp)
        self.manifest_dict = {
            "name": "test", "version": "0.1.0", "description": "t",
            "owner": "tester", "repository": "https://github.com/tester/test.git",
            "plugins": [
                {"name": "a", "description": "plugin a", "skills": ["skill-one"],
                 "agents": [], "commands": [], "rules": ["cq/a.md"]},
            ],
        }
        self.manifest_path = self.root / "agentry.json"
        self.manifest_path.write_text(json.dumps(self.manifest_dict), encoding="utf-8")
        self.plugins_dir = self.root / "plugins"
        self.rules_dir = self.root / "rules"
        skill_dir = self.plugins_dir / "a" / "skills" / "skill-one"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text("# skill-one\n\nBody.\n", encoding="utf-8")
        (skill_dir / "references").mkdir(exist_ok=True)
        (skill_dir / "references" / "extra.md").write_text("ref\n", encoding="utf-8")
        rule = self.rules_dir / "cq" / "a.md"
        rule.parent.mkdir(parents=True, exist_ok=True)
        rule.write_text("---\ndescription: rule a\n---\n\n# Rule A\n\nGuidance.\n", encoding="utf-8")

    def add_scenarios(self):
        _write_scenario(self.root, "a", "skills", "skill-one", "seq", VALID_SCENARIO,
                        fixtures={"fixtures/change.diff": "diff --git ...\n"})
        return self

    def patches(self):
        return [
            mock.patch.object(agentry, "REPO_ROOT", self.root),
            mock.patch.object(agentry, "MANIFEST", self.manifest_path),
            mock.patch.object(agentry, "PLUGINS_DIR", self.plugins_dir),
            mock.patch.object(agentry, "RULES_DIR", self.rules_dir),
        ]


class ScenarioDiscoveryScopeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _EvalRepo(self._tmp.name).add_scenarios()
        # A second scenario under a different artifact for scope tests.
        _write_scenario(self.repo.root, "a", "commands", "publish-review", "confirm",
                        VALID_SCENARIO.replace('id = "seq"', 'id = "confirm"')
                        .replace('artifact = "plugins/a/skills/skill-one/SKILL.md"',
                                 'artifact = "plugins/a/commands/publish-review.md"')
                        .replace('kind = "skill"', 'kind = "command"'),
                        fixtures={"fixtures/change.diff": "d\n"})
        self._patches = self.repo.patches()
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()

    def _args(self, **kw):
        return _make_namespace(**kw)

    def test_discovers_all_with_all_flag(self):
        args = self._args(artifact=None, plugin=None, component=None, scenario=None, all=True)
        found = agentry.resolve_scenario_scope(args, agentry.load_plugins())
        self.assertEqual({d["scenario"]["id"] for d in found}, {"seq", "confirm"})

    def test_missing_all_without_scope_aborts(self):
        args = self._args(artifact=None, plugin=None, component=None, scenario=None, all=False)
        with self.assertRaises(SystemExit):
            agentry.resolve_scenario_scope(args, agentry.load_plugins())

    def test_component_filter_selects_kind(self):
        args = self._args(artifact=None, plugin=None, component=["skills"], scenario=None, all=False)
        found = agentry.resolve_scenario_scope(args, agentry.load_plugins())
        self.assertEqual({d["scenario"]["id"] for d in found}, {"seq"})

    def test_scenario_filter_selects_by_id(self):
        args = self._args(artifact=None, plugin=None, component=None, scenario=["confirm"], all=False)
        found = agentry.resolve_scenario_scope(args, agentry.load_plugins())
        self.assertEqual({d["scenario"]["id"] for d in found}, {"confirm"})

    def test_artifact_path_filter(self):
        args = self._args(artifact="plugins/a/skills/skill-one", plugin=None, component=None,
                          scenario=None, all=False)
        found = agentry.resolve_scenario_scope(args, agentry.load_plugins())
        self.assertEqual({d["scenario"]["id"] for d in found}, {"seq"})

    def test_fixtures_subtree_not_discovered_as_scenario(self):
        # A stray .md under fixtures/ must not be treated as a scenario.
        (self.repo.plugins_dir / "a" / "eval" / "skills" / "skill-one" / "fixtures" / "note.md").write_text(
            "# not a scenario\n", encoding="utf-8")
        descriptors = list(agentry.discover_scenarios(agentry.load_plugins()))
        ids = {str(d["path"].name) for d in descriptors}
        self.assertNotIn("note.md", ids)


class EvalExclusionRegressionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _EvalRepo(self._tmp.name).add_scenarios()
        self._patches = self.repo.patches()
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()

    def test_plan_copies_never_touches_eval_tree(self):
        jobs = agentry.plan_copies(agentry.load_plugins(), set(agentry.COMPONENTS))
        for _, src, _ in jobs:
            self.assertNotIn("eval", Path(src).parts, f"eval leaked into install plan: {src}")

    def test_inventory_never_lists_eval_files(self):
        report = agentry.build_inventory(
            agentry.load_manifest(), agentry.load_plugins(), set(agentry.COMPONENTS), include_paths=True)
        blob = json.dumps(report)
        self.assertNotIn("/eval/", blob)

    def test_check_eval_exclusion_passes_for_clean_repo(self):
        findings = []
        agentry.check_eval_exclusion(agentry.load_manifest(), findings)
        self.assertEqual(findings, [])

    def test_check_eval_exclusion_flags_component_under_eval(self):
        # Point a declared rule at a path under an eval/ segment and assert the
        # guard reports it: eval assets must never be shippable artifacts.
        manifest = agentry.load_manifest()
        manifest["plugins"][0]["rules"] = ["cq/a.md", "eval/leak.md"]
        (self.repo.rules_dir / "eval").mkdir(parents=True, exist_ok=True)
        (self.repo.rules_dir / "eval" / "leak.md").write_text("x\n", encoding="utf-8")
        findings = []
        agentry.check_eval_exclusion(manifest, findings)
        self.assertTrue(any("eval" in f for f in findings), findings)


class MaterializeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _EvalRepo(self._tmp.name).add_scenarios()
        self._patches = self.repo.patches()
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()

    def test_assert_fixtures_stable_passes_when_blobs_match(self):
        scenario = ec.parse_scenario(
            self.repo.plugins_dir / "a" / "eval" / "skills" / "skill-one" / "seq.md")
        scenario["_dir"] = self.repo.plugins_dir / "a" / "eval" / "skills" / "skill-one"
        with mock.patch.object(agentry, "git_blob_id", return_value="same"):
            agentry.assert_fixtures_stable(scenario, ["A", "B"], allow_drift=False)

    def test_assert_fixtures_stable_aborts_on_drift(self):
        scenario = ec.parse_scenario(
            self.repo.plugins_dir / "a" / "eval" / "skills" / "skill-one" / "seq.md")
        scenario["_dir"] = self.repo.plugins_dir / "a" / "eval" / "skills" / "skill-one"
        with mock.patch.object(agentry, "git_blob_id", side_effect=["one", "two"]):
            with self.assertRaises(SystemExit):
                agentry.assert_fixtures_stable(scenario, ["A", "B"], allow_drift=False)

    def test_allow_drift_bypasses_stability(self):
        scenario = ec.parse_scenario(
            self.repo.plugins_dir / "a" / "eval" / "skills" / "skill-one" / "seq.md")
        scenario["_dir"] = self.repo.plugins_dir / "a" / "eval" / "skills" / "skill-one"
        with mock.patch.object(agentry, "git_blob_id", side_effect=AssertionError("should not be called")):
            agentry.assert_fixtures_stable(scenario, ["A", "B"], allow_drift=True)


class PreparePacketTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _EvalRepo(self._tmp.name).add_scenarios()
        self._patches = self.repo.patches()
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()

    def _prepare(self, **kw):
        run_dir = self.repo.root / "run"
        args = _make_namespace(
            artifact=kw.pop("artifact", None), plugin=kw.pop("plugin", ["a"]),
            component=kw.pop("component", None), scenario=kw.pop("scenario", None),
            all=kw.pop("all", False), run_dir=run_dir,
            target=kw.pop("target", ["trae:GPT-5.5"]), evaluator=kw.pop("evaluator", None),
            mode=kw.pop("mode", "rendered"), allow_fixture_drift=False, **kw)
        rv = agentry.cmd_evaluate_prepare(args)
        return rv, run_dir

    def test_prepare_writes_manifest_and_cases(self):
        rv, run_dir = self._prepare(scenario=["seq"])
        self.assertEqual(rv, 0)
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        ec._require_schema(manifest, ec.RUN_SCHEMA, "manifest")
        self.assertEqual(len(manifest["scenarios"]), 1)
        case_rel = manifest["scenarios"][0]["cases"][0]["case"]
        case = json.loads((run_dir / case_rel).read_text(encoding="utf-8"))
        case_dir = (run_dir / case_rel).parent
        # Case shares the run schema with the manifest and is identified by
        # run_document == "case" (no separate marker, no packet_type).
        ec._require_schema(case, ec.RUN_SCHEMA, "case")
        self.assertEqual(case["run_document"], "case")
        self.assertEqual(manifest["run_document"], "manifest")
        self.assertNotIn("packet_type", case)
        # The manifest carries a runner provenance tag: the generator's brand
        # name and the project version (from the manifest), not a frozen constant.
        self.assertEqual(manifest["runner"]["name"], "Agentry")
        self.assertIn("version", manifest["runner"])
        self.assertNotIn("runner_version", manifest)
        # Self-contained case carries full checks (with expect) and execution
        # params; the manifest is an index and holds no check definitions.
        self.assertTrue(any("expect" in c for c in case["checks"]))
        self.assertEqual(case["repetitions"], 3)
        self.assertEqual(case["evidence_tier"], "normal")
        self.assertNotIn("checks", manifest["scenarios"][0])
        # Content-shaped inputs are referenced files, not inlined; no artifact_source.
        self.assertNotIn("artifact_source", case)
        self.assertEqual(case["artifact_bundle"]["entry"], "artifact/SKILL.md")
        self.assertIn("skill-one", (case_dir / "artifact" / "SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual(case["fixtures"]["diff"], "fixtures/change.diff")
        self.assertTrue((case_dir / "fixtures" / "change.diff").exists())
        self.assertEqual(case["prompt_file"], "prompt/prompt.md")
        self.assertTrue((case_dir / "prompt" / "prompt.md").exists())

    def test_prepare_defaults_run_dir_under_runs_root(self):
        # Omitting --run-dir mirrors 'run': default to a timestamped dir under
        # the runs root, so neither subcommand forces the caller to name a path.
        args = _make_namespace(
            artifact=None, plugin=["a"], component=None, scenario=["seq"],
            all=False, run_dir=None,
            target=["trae:GPT-5.5"], mode="rendered", allow_fixture_drift=False)
        with redirect_stdout(io.StringIO()):
            rv = agentry.cmd_evaluate_prepare(args)
        self.assertEqual(rv, 0)
        runs_root = agentry.eval_runs_root()
        run_dirs = [p for p in runs_root.iterdir() if p.is_dir()]
        self.assertEqual(len(run_dirs), 1)
        self.assertTrue(run_dirs[0].name.startswith("run-"))
        self.assertTrue((run_dirs[0] / "manifest.json").exists())
        # Sandbox is per-case: prepare pre-creates the empty sandbox/ anchor
        # under the case, records no sandbox field (mode is the signal; the
        # skill owns the layout), and creates no run-level dir.
        rv, run_dir = self._prepare(scenario=["seq"], mode="sandbox")
        self.assertEqual(rv, 0)
        self.assertFalse((run_dir / "sandbox").exists())
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        case_rel = manifest["scenarios"][0]["cases"][0]["case"]
        case = json.loads((run_dir / case_rel).read_text(encoding="utf-8"))
        self.assertNotIn("sandbox", case)
        self.assertEqual(case["mode"], "sandbox")
        # The empty anchor exists under the case, but no runtime subdirs.
        anchor = (run_dir / case_rel).parent / "sandbox"
        self.assertTrue(anchor.is_dir())
        self.assertEqual(list(anchor.iterdir()), [])

    def test_prepare_rendered_mode_has_no_sandbox(self):
        rv, run_dir = self._prepare(scenario=["seq"], mode="rendered")
        self.assertEqual(rv, 0)
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        case_rel = manifest["scenarios"][0]["cases"][0]["case"]
        case = json.loads((run_dir / case_rel).read_text(encoding="utf-8"))
        self.assertNotIn("sandbox", case)
        self.assertFalse(((run_dir / case_rel).parent / "sandbox").exists())

    def test_prepare_rule_scenario_references_body(self):
        _write_scenario(
            self.repo.root, "a", "rules", "cq/a", "rule-scenario",
            VALID_SCENARIO.replace('id = "seq"', 'id = "rule-scenario"')
            .replace('artifact = "plugins/a/skills/skill-one/SKILL.md"', 'artifact = "rules/cq/a.md"')
            .replace('kind = "skill"', 'kind = "rule"'),
            fixtures={"fixtures/change.diff": "d\n"})
        rv, run_dir = self._prepare(scenario=["rule-scenario"], component=["rules"])
        self.assertEqual(rv, 0)
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        case_rel = manifest["scenarios"][0]["cases"][0]["case"]
        case = json.loads((run_dir / case_rel).read_text(encoding="utf-8"))
        case_dir = (run_dir / case_rel).parent
        self.assertEqual(case["artifact_kind"], "rule")
        # Rule metadata is referenced; the body travels once as a copied file.
        self.assertEqual(case["context"]["rule"], {"rule_path": "rules/cq/a.md"})
        self.assertNotIn("plugin", case["context"])
        self.assertEqual(case["artifact_bundle"]["entry"], "artifact/a.md")
        self.assertIn("Guidance.", (case_dir / "artifact" / "a.md").read_text(encoding="utf-8"))

    def test_prepare_rejects_traversing_artifact_path(self):
        # A scenario artifact must not read a file outside the repo. Confinement
        # mirrors the fixture/rule path guards.
        _write_scenario(
            self.repo.root, "a", "commands", "c", "leak",
            VALID_SCENARIO.replace('id = "seq"', 'id = "leak"')
            .replace('artifact = "plugins/a/skills/skill-one/SKILL.md"', 'artifact = "../secret.txt"')
            .replace('kind = "skill"', 'kind = "command"'),
            fixtures={"fixtures/change.diff": "d\n"})
        (self.repo.root / "secret.txt").write_text("SECRET\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            self._prepare(scenario=["leak"], component=["commands"])

    def test_prepare_copies_skill_files_into_case(self):
        # The whole skill directory (SKILL.md + references/) travels as standalone
        # files under the case's artifact/ dir, and the case references them.
        (self.repo.plugins_dir / "a" / "skills" / "skill-one" / "references" / "extra.md").write_text(
            "reference body\n", encoding="utf-8")
        rv, run_dir = self._prepare(scenario=["seq"])
        self.assertEqual(rv, 0)
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        case_rel = manifest["scenarios"][0]["cases"][0]["case"]
        case_dir = (run_dir / case_rel).parent
        case = json.loads((run_dir / case_rel).read_text(encoding="utf-8"))
        self.assertEqual(case["artifact_bundle"]["entry"], "artifact/SKILL.md")
        self.assertIn("artifact/references/extra.md", case["artifact_bundle"]["files"])
        self.assertTrue((case_dir / "artifact" / "SKILL.md").exists())
        self.assertTrue((case_dir / "artifact" / "references" / "extra.md").exists())

    def test_prepare_copies_scenario_tool_mocks_into_case(self):
        # A scenario's tool-mocks/ travel per-case (collision-free across
        # scenarios) and are referenced by case.json.
        mock_src = (self.repo.plugins_dir / "a" / "eval" / "skills" / "skill-one" / "tool-mocks")
        mock_src.mkdir(parents=True, exist_ok=True)
        (mock_src / "gh").write_text("#!/bin/sh\necho mocked\n", encoding="utf-8")
        rv, run_dir = self._prepare(scenario=["seq"])
        self.assertEqual(rv, 0)
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        case_rel = manifest["scenarios"][0]["cases"][0]["case"]
        case_dir = (run_dir / case_rel).parent
        case = json.loads((run_dir / case_rel).read_text(encoding="utf-8"))
        self.assertIn("tool-mocks/gh", case["tool_mocks"])
        self.assertTrue((case_dir / "tool-mocks" / "gh").exists())

    def test_prepare_writes_producer_brief_and_produced_dir(self):
        rv, run_dir = self._prepare(scenario=["seq"])
        self.assertEqual(rv, 0)
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        case_rel = manifest["scenarios"][0]["cases"][0]["case"]
        case_dir = (run_dir / case_rel).parent
        case = json.loads((run_dir / case_rel).read_text(encoding="utf-8"))
        # Orchestrator brief lives under prompt/ (case.json stays the only loose
        # file at the case root) and is referenced.
        self.assertEqual(case["produce"]["producer_brief"], "prompt/producer-brief.md")
        self.assertEqual(case["produce"]["produced_dir"], "produced")
        brief = (case_dir / "prompt" / "producer-brief.md").read_text(encoding="utf-8")
        # It is orchestrator-facing: explicitly not for the producer, and carries
        # composition + blinding rules.
        self.assertIn("Do NOT hand this file to the producer", brief)
        self.assertIn("Composition rules", brief)
        # It must not name the true secrets (scenario id, check ids).
        self.assertNotIn("seq", brief)
        self.assertNotIn("findings-first", brief)
        # produced/ anchor pre-created for captured outputs.
        self.assertTrue((case_dir / "produced").is_dir())
        # case.json is the only loose file at the case root.
        loose = [p.name for p in case_dir.iterdir() if p.is_file()]
        self.assertEqual(loose, ["case.json"])
        # Rendered mode: inline the guidance and return proposed output (draft-only).
        self.assertIn("inline the content", brief)
        self.assertIn("draft only", brief)
        self.assertEqual(
            case["produce"]["side_effect_policy"],
            "return proposed outputs or fake-sink writes only; do not mutate real state")

    def test_prepare_brief_is_sandbox_aware(self):
        # Sandbox mode: the artifact is installed/activated by the tool (not
        # inlined) and the producer acts normally under containment, not draft-only.
        rv, run_dir = self._prepare(scenario=["seq"], mode="sandbox")
        self.assertEqual(rv, 0)
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        case_rel = manifest["scenarios"][0]["cases"][0]["case"]
        case_dir = (run_dir / case_rel).parent
        case = json.loads((run_dir / case_rel).read_text(encoding="utf-8"))
        brief = (case_dir / "prompt" / "producer-brief.md").read_text(encoding="utf-8")
        self.assertIn("install it into the target tool", brief)
        self.assertIn("behave normally", brief)
        self.assertNotIn("draft only", brief)
        self.assertNotIn("inline the content", brief)
        self.assertIn("isolated sandbox", case["produce"]["side_effect_policy"])

    def test_prepare_target_matrix_fans_out_cases(self):
        rv, run_dir = self._prepare(scenario=["seq"], target=["trae:GPT-5.5", "trae:GPT-6"])
        self.assertEqual(rv, 0)
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        cases = manifest["scenarios"][0]["cases"]
        self.assertEqual({p["target"] for p in cases}, {"trae:GPT-5.5", "trae:GPT-6"})
        self.assertEqual(len(cases), 2)

    def test_prepare_dedupes_repeated_targets(self):
        rv, run_dir = self._prepare(scenario=["seq"], target=["trae:GPT-5.5", "trae:GPT-5.5"])
        self.assertEqual(rv, 0)
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["targets"]), 1)

    def test_prepare_pins_evaluator_in_manifest_and_case(self):
        rv, run_dir = self._prepare(scenario=["seq"], evaluator="trae:strong")
        self.assertEqual(rv, 0)
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["evaluator"],
                         {"id": "trae:strong", "tool": "trae", "model": "strong"})
        case_rel = manifest["scenarios"][0]["cases"][0]["case"]
        case = json.loads((run_dir / case_rel).read_text(encoding="utf-8"))
        self.assertEqual(case["judge"]["evaluator"],
                         {"id": "trae:strong", "tool": "trae", "model": "strong"})

    def test_prepare_evaluator_defaults_to_null(self):
        # Unset --evaluator: the judge policy is null (orchestrator judges with
        # its own runtime); the block still exists so the case is self-describing.
        rv, run_dir = self._prepare(scenario=["seq"])
        self.assertEqual(rv, 0)
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertIsNone(manifest["evaluator"])
        case_rel = manifest["scenarios"][0]["cases"][0]["case"]
        case = json.loads((run_dir / case_rel).read_text(encoding="utf-8"))
        self.assertIsNone(case["judge"]["evaluator"])

    def test_prepare_evidence_override_sets_case_and_manifest(self):
        # --evidence 9/10 overrides the scenario tier for the run: the case's
        # effective reps/threshold reflect it and the manifest records the override.
        rv, run_dir = self._prepare(scenario=["seq"], evidence="9/10")
        self.assertEqual(rv, 0)
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["evidence_override"],
                         {"min_consistent": 9, "repetitions": 10})
        case_rel = manifest["scenarios"][0]["cases"][0]["case"]
        case = json.loads((run_dir / case_rel).read_text(encoding="utf-8"))
        self.assertEqual((case["repetitions"], case["min_consistent"]), (10, 9))

    def test_prepare_evidence_override_defaults_to_null(self):
        rv, run_dir = self._prepare(scenario=["seq"])
        self.assertEqual(rv, 0)
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertIsNone(manifest["evidence_override"])

    def test_prepare_incoherent_evidence_override_aborts(self):
        # The override parses (format OK) but is incoherent (threshold > total);
        # the contract's prepare rejects it up front rather than building an
        # unsatisfiable bar.
        with self.assertRaises(SystemExit):
            self._prepare(scenario=["seq"], evidence="5/4")

    def test_prepare_fixture_drift_aborts_without_partial_dir(self):
        # Comparison-mode fixture drift must abort before any run dir is written,
        # so prepare stays fail-fast (no partial dir left behind).
        descriptors = agentry.resolve_scenario_scope(
            _make_namespace(artifact=None, plugin=["a"], component=None,
                            scenario=["seq"], all=False),
            agentry.load_plugins())
        agentry._attach_scenario_paths(descriptors)
        run_dir = self.repo.root / "run-drift"
        with mock.patch.object(agentry, "git_blob_id", side_effect=["one", "two"]):
            with self.assertRaises(SystemExit):
                agentry.prepare_run(
                    descriptors, agentry.load_manifest(), run_dir,
                    side_sources={
                        ec.BASELINE_SIDE: agentry.parse_side_source("ref:A", "--baseline"),
                        ec.VARIANT_SIDE: agentry.parse_side_source("ref:B", "--variant"),
                    },
                    targets=[{"id": "trae:GPT-5.5", "tool": "trae", "model": "GPT-5.5"}],
                    mode="rendered", allow_fixture_drift=False)
        self.assertFalse(run_dir.exists())

    def test_prepare_comparison_materializes_both_sides(self):
        # Comparison mode drives prepare_run's snapshot branch to completion
        # through the shared materialize_run: both baseline/variant cases exist, and
        # each side's case reads from its snapshotted source.
        descriptors = agentry.resolve_scenario_scope(
            _make_namespace(artifact=None, plugin=["a"], component=None,
                            scenario=["seq"], all=False),
            agentry.load_plugins())
        agentry._attach_scenario_paths(descriptors)
        run_dir = self.repo.root / "run-cmp"

        def fake_snapshot(ref, source_rel, dest_root):
            # Mimic snapshot_artifact_source: copy the working-tree source into
            # the per-side snapshot dir so build_case finds the artifact files.
            src = self.repo.root / source_rel
            dst = dest_root / source_rel
            dst.mkdir(parents=True, exist_ok=True)
            for p in sorted(x for x in src.rglob("*") if x.is_file()):
                target = dst / p.relative_to(src)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

        with mock.patch.object(agentry, "git_blob_id", return_value="same"), \
                mock.patch.object(agentry, "snapshot_artifact_source", side_effect=fake_snapshot):
            run_manifest, manifest_path = agentry.prepare_run(
                descriptors, agentry.load_manifest(), run_dir,
                side_sources={
                    ec.BASELINE_SIDE: agentry.parse_side_source("ref:A", "--baseline"),
                    ec.VARIANT_SIDE: agentry.parse_side_source("ref:B", "--variant"),
                },
                targets=[{"id": "trae:GPT-5.5", "tool": "trae", "model": "GPT-5.5"}],
                mode="rendered", allow_fixture_drift=False)
        self.assertTrue(manifest_path.is_file())
        sides = {c["side"] for c in run_manifest["scenarios"][0]["cases"]}
        self.assertEqual(sides, {"baseline", "variant"})
        self.assertEqual(run_manifest["sides"], {
            "baseline": {"label": "A"},
            "variant": {"label": "B"},
        })
        for ref in run_manifest["scenarios"][0]["cases"]:
            case = json.loads((run_dir / ref["case"]).read_text(encoding="utf-8"))
            self.assertEqual(case["run_document"], "case")
            self.assertTrue((run_dir / ref["case"]).parent.joinpath("artifact", "SKILL.md").is_file())

    def test_prepare_variant_can_omit_artifact(self):
        descriptors = agentry.resolve_scenario_scope(
            _make_namespace(artifact=None, plugin=["a"], component=None,
                            scenario=["seq"], all=False),
            agentry.load_plugins())
        agentry._attach_scenario_paths(descriptors)
        run_dir = self.repo.root / "run-absent"

        run_manifest, manifest_path = agentry.prepare_run(
            descriptors, agentry.load_manifest(), run_dir,
            side_sources={
                ec.BASELINE_SIDE: agentry.parse_side_source("worktree", "--baseline"),
                ec.VARIANT_SIDE: agentry.parse_side_source("absent", "--variant"),
            },
            targets=[{"id": "trae:GPT-5.5", "tool": "trae", "model": "GPT-5.5"}],
            mode="rendered", allow_fixture_drift=False)

        self.assertTrue(manifest_path.is_file())
        self.assertEqual(run_manifest["sides"], {
            "baseline": {"label": "worktree"},
            "variant": {"label": "absent", "without_artifact": True},
        })
        cases = {
            ref["side"]: json.loads((run_dir / ref["case"]).read_text(encoding="utf-8"))
            for ref in run_manifest["scenarios"][0]["cases"]
        }
        self.assertEqual(cases["baseline"]["artifact_bundle"]["entry"], "artifact/SKILL.md")
        self.assertEqual(cases["variant"]["artifact_bundle"], {"entry": None, "files": []})

    def test_prepare_multi_turn_case_has_turns(self):
        multi = """\
+++
schema = "agentry.authoring-evaluation.scenario"
schema_version = 1
id = "confirm"
artifact = "plugins/a/skills/skill-one/SKILL.md"
kind = "skill"
baseline_failure = "Publishes without confirmation."

[interaction]
mode = "multi-turn"

[[turns]]
id = "initial"
body = "Initial Request"

[[turns]]
id = "confirmation"
body = "Confirmation"

[[checks]]
id = "asks-first"
type = "rubric"
required = true
target = "turn:initial"
expect = "Asks for confirmation."
+++

## Initial Request

Publish these findings.

## Confirmation

Confirmed. Publish.
"""
        _write_scenario(self.repo.root, "a", "skills", "skill-one", "confirm", multi)
        rv, run_dir = self._prepare(scenario=["confirm"])
        self.assertEqual(rv, 0)
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        case_rel = manifest["scenarios"][0]["cases"][0]["case"]
        case = json.loads((run_dir / case_rel).read_text(encoding="utf-8"))
        case_dir = (run_dir / case_rel).parent
        self.assertEqual(case["interaction"]["mode"], "multi-turn")
        self.assertEqual([t["id"] for t in case["turns"]], ["initial", "confirmation"])
        # Turn bodies are files; there is no single prompt in multi-turn mode.
        self.assertIsNone(case["prompt_file"])
        self.assertEqual(case["turns"][0]["file"], "prompt/turns/initial.md")
        self.assertIn("Publish these findings.",
                      (case_dir / "prompt" / "turns" / "initial.md").read_text(encoding="utf-8"))


class EvaluateDispatchTests(unittest.TestCase):
    def test_bare_evaluate_prints_help_without_color_arg(self):
        # The top-level `evaluate` parser has no --color of its own, so the
        # dispatch must print help before touching args.color.
        ns = _make_namespace(evaluate_command=None, parser=mock.Mock())
        del ns.color  # bare evaluate never sets --color
        rv = agentry.cmd_evaluate(ns)
        self.assertEqual(rv, 0)
        ns.parser.print_help.assert_called_once()


class AggregateCollectTests(unittest.TestCase):
    def _manifest(self, comparison=True, min_consistent=3, required=True):
        side_meta = (
            {"baseline": {"label": "A"}, "variant": {"label": "B"}}
            if comparison else {"baseline": {"label": "current"}}
        )
        sides = ["baseline", "variant"] if comparison else ["baseline"]
        return {
            "schema": ec.RUN_SCHEMA, "schema_version": 1, "run_document": "manifest", "run_id": "t",
            "runner": {"name": "Agentry", "version": "0.5.1"}, "mode": "rendered", "sides": side_meta,
            "targets": [{"id": "trae:GPT-5.5", "tool": "trae", "model": "GPT-5.5"}],
            # Manifest is an index: identity + case pointers only.
            "scenarios": [{
                "id": "s1", "artifact": "x", "artifact_kind": "skill",
                "cases": [{"side": s, "target": "trae:GPT-5.5",
                             "case": f"cases/s1/trae_GPT-5.5/{s}/case.json"} for s in sides],
            }],
        }

    def _case(self, side, min_consistent=3, required=True, reps=3, pinned=None):
        # Self-contained case: checks + execution params live here.
        return {
            "schema": ec.RUN_SCHEMA, "schema_version": 1, "run_document": "case", "run_id": "t",
            "scenario_id": "s1", "side": side, "target": "trae:GPT-5.5", "mode": "rendered",
            "repetitions": reps, "min_consistent": min_consistent, "evidence_tier": "normal",
            "judge": {"evaluator": pinned},
            "checks": [{"id": "c1", "type": "rubric", "required": required}],
        }

    def _cases(self, manifest, min_consistent=3, required=True, reps=3, pinned=None):
        out = {}
        for sinfo in manifest["scenarios"]:
            for ref in sinfo["cases"]:
                out[(sinfo["id"], ref["target"], ref["side"])] = self._case(
                    ref["side"], min_consistent, required, reps, pinned)
        return out

    def _agg(self, recs, manifest, **kw):
        return ec._aggregate_results(recs, manifest, self._cases(manifest, **kw))

    def _write_run(self, run_dir, manifest, **kw):
        # Materialize manifest + the case files it references, matching a real run.
        (run_dir / "results").mkdir(parents=True, exist_ok=True)
        agentry.write_json(run_dir / "manifest.json", manifest)
        for (sid, target, side), case in self._cases(manifest, **kw).items():
            ref = next(r for s in manifest["scenarios"] if s["id"] == sid
                       for r in s["cases"] if r["target"] == target and r["side"] == side)
            agentry.write_json(run_dir / ref["case"], case)

    def _rec(self, side, outcome, rep, producer=None, evaluator=None):
        # Provenance-complete check record: references a produced output and
        # carries a quote that appears in it (see _write_results).
        produced = f"cases/s1/trae_GPT-5.5/{side}/produced/rep-{rep}.md"
        return {"schema": ec.RESULT_SCHEMA, "schema_version": 1, "record_type": "check",
                "run_id": "t", "scenario_id": "s1", "target": "trae:GPT-5.5", "side": side,
                "check_id": "c1", "check_type": "rubric", "outcome": outcome, "repetition": rep,
                "producer": producer or {"tool": "trae", "model": "GPT-5.5"},
                "evaluator": evaluator or {"id": "rubric-eval", "model": "GPT-5.5"},
                "produced_output": produced,
                "evidence": {"source_path": produced, "quote": "the produced answer"}}

    def _write_results(self, run_dir, recs):
        # Write the produced-output files each record references, then the JSONL.
        for r in recs:
            po = r.get("produced_output")
            if po:
                path = run_dir / po
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("the produced answer\n", encoding="utf-8")
        (run_dir / "results").mkdir(parents=True, exist_ok=True)
        (run_dir / "results" / "out.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")

    def test_all_pass_is_pass(self):
        recs = [self._rec("baseline", "pass", i) for i in (1, 2, 3)]
        report = self._agg(recs, self._manifest(comparison=False))
        self.assertEqual(report["scenarios"][0]["sides"]["baseline"]["outcome"], "pass")
        self.assertEqual(agentry.scorecard_exit_status(report), 0)

    def test_mixed_is_needs_review(self):
        recs = [self._rec("baseline", "pass", 1), self._rec("baseline", "fail", 2),
                self._rec("baseline", "pass", 3)]
        report = self._agg(recs, self._manifest(comparison=False))
        self.assertEqual(report["scenarios"][0]["sides"]["baseline"]["outcome"], "needs-review")
        self.assertEqual(agentry.scorecard_exit_status(report), 1)

    def test_all_fail_is_fail(self):
        recs = [self._rec("baseline", "fail", i) for i in (1, 2, 3)]
        report = self._agg(recs, self._manifest(comparison=False))
        self.assertEqual(report["scenarios"][0]["sides"]["baseline"]["outcome"], "fail")

    def test_before_fail_after_pass_improved(self):
        recs = ([self._rec("baseline", "fail", i) for i in (1, 2, 3)]
                + [self._rec("variant", "pass", i) for i in (1, 2, 3)])
        report = self._agg(recs, self._manifest())
        self.assertEqual(report["scenarios"][0]["delta"], "improved")
        self.assertEqual(report["comparison"]["improved"], 1)

    def test_before_pass_after_fail_regressed(self):
        recs = ([self._rec("baseline", "pass", i) for i in (1, 2, 3)]
                + [self._rec("variant", "fail", i) for i in (1, 2, 3)])
        report = self._agg(recs, self._manifest())
        self.assertEqual(report["scenarios"][0]["delta"], "regressed")
        self.assertEqual(agentry.scorecard_exit_status(report), 1)

    def test_required_needs_review_never_passes(self):
        # 4/5-style threshold: 2 pass / 1 fail under min_consistent 3 -> needs-review.
        recs = [self._rec("baseline", "pass", 1), self._rec("baseline", "pass", 2),
                self._rec("baseline", "fail", 3)]
        report = self._agg(recs, self._manifest(comparison=False))
        self.assertEqual(report["scenarios"][0]["sides"]["baseline"]["outcome"], "needs-review")

    def test_integrity_pinned_evaluator_not_honored_invalidates(self):
        # Case pins trae:strong but the judge recorded a different model: the
        # directed evaluator was not the one that ran.
        pinned = {"id": "trae:strong", "tool": "trae", "model": "strong"}
        wrong = {"id": "rubric", "tool": "trae", "model": "weak"}
        recs = [self._rec("baseline", "pass", i, evaluator=wrong) for i in (1, 2, 3)]
        report = self._agg(recs, self._manifest(comparison=False), pinned=pinned)
        self.assertEqual(report["aggregate"]["integrity"], 3)
        self.assertEqual(report["status"], "invalid")
        self.assertEqual(report["integrity_findings"][0]["finding"], "evaluator-not-honored")

    def test_integrity_producer_not_target_model_invalidates(self):
        # Target is trae:GPT-5.5 but the producer recorded a different model:
        # the wrong model produced the output.
        wrong = {"tool": "trae", "model": "GPT-6"}
        recs = [self._rec("baseline", "pass", i, producer=wrong) for i in (1, 2, 3)]
        report = self._agg(recs, self._manifest(comparison=False))
        self.assertEqual(report["aggregate"]["integrity"], 3)
        self.assertEqual(report["status"], "invalid")
        self.assertEqual(report["integrity_findings"][0]["finding"], "producer-not-honored")

    def test_integrity_producer_not_target_tool_invalidates(self):
        # A producer tool that is not the target tool is a violation too.
        wrong = {"tool": "claude-code", "model": "GPT-5.5"}
        recs = [self._rec("baseline", "pass", i, producer=wrong) for i in (1, 2, 3)]
        report = self._agg(recs, self._manifest(comparison=False))
        self.assertEqual(report["status"], "invalid")
        self.assertIn("producer-not-honored",
                      [f["finding"] for f in report["integrity_findings"]])

    def test_integrity_producer_missing_model_is_tolerated(self):
        # A producer that reports its tool but no model is not a positive
        # contradiction, so it is tolerated like the evaluator check.
        partial = {"tool": "trae"}
        recs = [self._rec("baseline", "pass", i, producer=partial) for i in (1, 2, 3)]
        report = self._agg(recs, self._manifest(comparison=False))
        self.assertEqual(report["aggregate"]["integrity"], 0)
        self.assertEqual(report["status"], "ok")

    def test_integrity_pinned_evaluator_honored_is_clean(self):
        # Judge recorded the pinned model: honored, no finding.
        pinned = {"id": "trae:strong", "tool": "trae", "model": "strong"}
        honored = {"id": "rubric", "tool": "trae", "model": "strong"}
        recs = [self._rec("baseline", "pass", i, evaluator=honored) for i in (1, 2, 3)]
        report = self._agg(recs, self._manifest(comparison=False), pinned=pinned)
        self.assertEqual(report["aggregate"]["integrity"], 0)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(agentry.scorecard_exit_status(report), 0)

    def test_integrity_pinned_evaluator_missing_model_passes(self):
        # A pinned evaluator with no recorded model is tolerated: the judge
        # simply did not report its model, which is not a positive mismatch.
        pinned = {"id": "trae:strong", "tool": "trae", "model": "strong"}
        no_model = {"id": "rubric"}
        recs = [self._rec("baseline", "pass", i, evaluator=no_model) for i in (1, 2, 3)]
        report = self._agg(recs, self._manifest(comparison=False), pinned=pinned)
        self.assertEqual(report["aggregate"]["integrity"], 0)
        self.assertEqual(report["status"], "ok")

    def test_integrity_evaluator_inconsistent_across_sides_invalidates(self):
        # A baseline/variant comparison judged by different evaluators could measure
        # judge variance, not behavior: flag it as invalid.
        before_judge = {"id": "rubric", "tool": "trae", "model": "strong"}
        after_judge = {"id": "rubric", "tool": "trae", "model": "weak"}
        recs = ([self._rec("baseline", "fail", i, evaluator=before_judge) for i in (1, 2, 3)]
                + [self._rec("variant", "pass", i, evaluator=after_judge) for i in (1, 2, 3)])
        report = self._agg(recs, self._manifest())
        self.assertEqual(report["status"], "invalid")
        self.assertEqual(agentry.scorecard_exit_status(report), 1)
        findings = [f["finding"] for f in report["integrity_findings"]]
        self.assertIn("evaluator-inconsistent-across-sides", findings)

    def test_integrity_same_evaluator_across_sides_is_clean(self):
        # Same judge label on both sides: no cross-side finding.
        judge = {"id": "rubric", "tool": "trae", "model": "strong"}
        recs = ([self._rec("baseline", "fail", i, evaluator=judge) for i in (1, 2, 3)]
                + [self._rec("variant", "pass", i, evaluator=judge) for i in (1, 2, 3)])
        report = self._agg(recs, self._manifest())
        self.assertEqual(report["aggregate"]["integrity"], 0)
        self.assertEqual(report["scenarios"][0]["delta"], "improved")

    def test_firm_count_shortfall_is_needs_review(self):
        # Manifest expects 3 reps; only 2 pass records -> incomplete, not a pass.
        recs = [self._rec("baseline", "pass", 1), self._rec("baseline", "pass", 2)]
        report = self._agg(recs, self._manifest(comparison=False))
        self.assertEqual(report["scenarios"][0]["sides"]["baseline"]["outcome"], "needs-review")
        self.assertEqual(report["aggregate"]["short"], 1)
        self.assertEqual(agentry.scorecard_exit_status(report), 1)
        short = report["short_checks"][0]
        self.assertEqual((short["got"], short["expected"]), (2, 3))

    def test_firm_count_stable_fail_still_stands_when_short(self):
        # A stable fail (3/3 style) is authoritative even if reps < expected is
        # impossible here; a short run that is already all-fail stays fail.
        self.assertEqual(ec._classify_check(["fail", "fail", "fail"], 3, expected=5), "fail")

    def test_classify_check_expected_blocks_short_pass(self):
        # 3 passes but 5 expected -> cannot confirm pass.
        self.assertEqual(ec._classify_check(["pass"] * 3, 3, expected=5), "needs-review")
        # Meeting the expected count with a stable pass -> pass.
        self.assertEqual(ec._classify_check(["pass"] * 5, 4, expected=5), "pass")

    def test_acceptance_tier_four_of_five(self):
        # Acceptance tier needs 4 of 5 consistent; a lone fail collapses to needs-review.
        self.assertEqual(ec._classify_check(["pass"] * 4 + ["fail"], 4), "needs-review")
        self.assertEqual(ec._classify_check(["pass"] * 4, 4), "pass")

    def test_unchanged_when_both_sides_pass(self):
        recs = ([self._rec("baseline", "pass", i) for i in (1, 2, 3)]
                + [self._rec("variant", "pass", i) for i in (1, 2, 3)])
        report = self._agg(recs, self._manifest())
        self.assertEqual(report["scenarios"][0]["delta"], "unchanged")
        self.assertEqual(report["comparison"]["unchanged"], 1)

    def test_newly_covered_when_only_after_has_records(self):
        recs = [self._rec("variant", "pass", i) for i in (1, 2, 3)]
        report = self._agg(recs, self._manifest())
        self.assertEqual(report["scenarios"][0]["delta"], "newly-covered")
        self.assertEqual(report["comparison"]["newly_covered"], 1)
        # The baseline case produced nothing -> missing coverage -> nonzero exit.
        self.assertEqual(report["aggregate"]["missing"], 1)
        self.assertEqual(agentry.scorecard_exit_status(report), 1)

    def test_empty_results_do_not_pass(self):
        report = self._agg([], self._manifest(comparison=False))
        self.assertEqual(report["aggregate"]["passed"], 0)
        self.assertEqual(report["aggregate"]["missing"], 1)
        self.assertEqual(agentry.scorecard_exit_status(report), 1)

    def test_optional_only_scenario_gates_on_all_checks(self):
        # No required checks -> _scenario_outcome gates on every check instead.
        manifest = self._manifest(comparison=False, required=False)
        recs = [self._rec("baseline", "fail", i) for i in (1, 2, 3)]
        report = self._agg(recs, manifest, required=False)
        self.assertEqual(report["scenarios"][0]["sides"]["baseline"]["outcome"], "fail")

    def test_evidence_threshold_maps_tiers(self):
        self.assertEqual(ec._evidence_threshold({"evidence_tier": "acceptance"}), (5, 4))
        self.assertEqual(ec._evidence_threshold({"evidence_tier": "normal"}), (3, 3))
        self.assertEqual(
            ec._evidence_threshold({"repetitions": 2, "stability_threshold": 2}),
            (2, 2))
        # A run-time override (min_consistent, reps) wins over the tier default.
        self.assertEqual(
            ec._evidence_threshold({"evidence_tier": "normal"}, override=(9, 10)),
            (10, 9))

    def test_resolve_evidence_override_parses_format_only(self):
        self.assertIsNone(agentry._resolve_evidence_override(_make_namespace(evidence=None)))
        self.assertEqual(
            agentry._resolve_evidence_override(_make_namespace(evidence="4/5")), (4, 5))
        # Only CLI *format* errors abort here; coherence (1 <= consistent <=
        # total) is the contract's job, enforced by eval_contract.prepare.
        for bad in ("3", "a/b", "4/5/6"):
            with self.assertRaises(SystemExit):
                agentry._resolve_evidence_override(_make_namespace(evidence=bad))
        # Coherent-format but incoherent-value pairs now parse; prepare rejects them.
        self.assertEqual(
            agentry._resolve_evidence_override(_make_namespace(evidence="5/4")), (5, 4))
        self.assertEqual(
            agentry._resolve_evidence_override(_make_namespace(evidence="0/5")), (0, 5))

    def test_parse_target_and_dedupe(self):
        self.assertEqual(agentry.parse_target("trae:GPT-5.5"),
                         {"id": "trae:GPT-5.5", "tool": "trae", "model": "GPT-5.5"})
        with self.assertRaises(SystemExit):
            agentry.parse_target("no-colon")
        args = _make_namespace(target=["trae:GPT-5.5", "trae:GPT-5.5", "trae:GPT-6"])
        ids = [t["id"] for t in agentry._resolve_targets(args)]
        self.assertEqual(ids, ["trae:GPT-5.5", "trae:GPT-6"])

    def test_resolve_targets_requires_at_least_one(self):
        # A target names the producing tool/model; it is a separate axis from
        # --mode, so both rendered and sandbox runs must name one explicitly.
        with self.assertRaises(SystemExit):
            agentry._resolve_targets(_make_namespace(target=None))
        with self.assertRaises(SystemExit):
            agentry._resolve_targets(_make_namespace(target=[]))

    def test_resolve_side_sources(self):
        self.assertEqual(
            agentry._resolve_side_sources(_make_namespace(baseline=None, variant=None)),
            {ec.BASELINE_SIDE: {"kind": "worktree", "label": "worktree", "ref": None}},
        )
        self.assertEqual(
            agentry._resolve_side_sources(_make_namespace(baseline="ref:A", variant="absent")),
            {
                ec.BASELINE_SIDE: {"kind": "ref", "label": "A", "ref": "A"},
                ec.VARIANT_SIDE: {"kind": "absent", "label": "absent", "ref": None},
            },
        )
        self.assertEqual(
            agentry._resolve_side_sources(_make_namespace(baseline="worktree", variant="ref:B")),
            {
                ec.BASELINE_SIDE: {"kind": "worktree", "label": "worktree", "ref": None},
                ec.VARIANT_SIDE: {"kind": "ref", "label": "B", "ref": "B"},
            },
        )
        with self.assertRaises(SystemExit):
            agentry._resolve_side_sources(_make_namespace(baseline="absent", variant=None))
        with self.assertRaises(SystemExit):
            agentry._resolve_side_sources(_make_namespace(baseline="main", variant=None))

    def test_collect_rejects_bad_schema(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            run_dir = Path(tmp.name)
            (run_dir / "results").mkdir()
            (run_dir / "results" / "r.jsonl").write_text(
                json.dumps({"schema": "wrong", "schema_version": 1, "record_type": "check",
                            "check_id": "c1"}) + "\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                ec._load_results(run_dir)
        finally:
            tmp.cleanup()

    def test_collect_rejects_check_record_without_check_id(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            run_dir = Path(tmp.name)
            (run_dir / "results").mkdir()
            (run_dir / "results" / "r.jsonl").write_text(
                json.dumps({"schema": ec.RESULT_SCHEMA, "schema_version": 1,
                            "record_type": "check"}) + "\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                ec._load_results(run_dir)
        finally:
            tmp.cleanup()

    def _write_one_result(self, run_dir, rec):
        (run_dir / "results").mkdir(parents=True, exist_ok=True)
        (run_dir / "results" / "r.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")

    def test_collect_rejects_check_without_produced_output(self):
        # A hand-written record with no captured output must not be accepted.
        tmp = tempfile.TemporaryDirectory()
        try:
            run_dir = Path(tmp.name)
            rec = self._rec("baseline", "pass", 1)
            del rec["produced_output"]
            self._write_one_result(run_dir, rec)
            with self.assertRaises(SystemExit):
                ec._load_results(run_dir)
        finally:
            tmp.cleanup()

    def test_collect_rejects_missing_produced_output_file(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            run_dir = Path(tmp.name)
            # Reference a produced output that was never written.
            self._write_one_result(run_dir, self._rec("baseline", "pass", 1))
            with self.assertRaises(SystemExit):
                ec._load_results(run_dir)
        finally:
            tmp.cleanup()

    def test_collect_rejects_evidence_quote_not_in_output(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            run_dir = Path(tmp.name)
            rec = self._rec("baseline", "pass", 1)
            (run_dir / rec["produced_output"]).parent.mkdir(parents=True, exist_ok=True)
            (run_dir / rec["produced_output"]).write_text("a totally different answer\n", encoding="utf-8")
            self._write_one_result(run_dir, rec)
            with self.assertRaises(SystemExit):
                ec._load_results(run_dir)
        finally:
            tmp.cleanup()

    def test_collect_accepts_quote_with_reflowed_whitespace(self):
        # Whitespace/EOL differences must not fail a genuinely present quote.
        tmp = tempfile.TemporaryDirectory()
        try:
            run_dir = Path(tmp.name)
            rec = self._rec("baseline", "pass", 1)
            (run_dir / rec["produced_output"]).parent.mkdir(parents=True, exist_ok=True)
            (run_dir / rec["produced_output"]).write_text("the   produced\r\n   answer here\n", encoding="utf-8")
            self._write_one_result(run_dir, rec)
            records = ec._load_results(run_dir)  # must not raise
            self.assertEqual(len(records), 1)
        finally:
            tmp.cleanup()

    def test_collect_rejects_duplicate_repetition_record(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            run_dir = Path(tmp.name)
            recs = [self._rec("baseline", "pass", 1), self._rec("baseline", "pass", 1)]
            for r in recs:
                p = run_dir / r["produced_output"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("the produced answer\n", encoding="utf-8")
            (run_dir / "results").mkdir(parents=True, exist_ok=True)
            (run_dir / "results" / "r.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
            with self.assertRaises(SystemExit):
                ec._load_results(run_dir)
        finally:
            tmp.cleanup()

    def test_cmd_collect_comparison_improved_end_to_end(self):
        # Exercise cmd_evaluate_collect: read manifest + JSONL, render scorecard,
        # write .md/.json, and return exit status. baseline fail -> variant pass.
        tmp = tempfile.TemporaryDirectory()
        try:
            run_dir = Path(tmp.name)
            self._write_run(run_dir, self._manifest(comparison=True))
            recs = ([self._rec("baseline", "fail", i) for i in (1, 2, 3)]
                    + [self._rec("variant", "pass", i) for i in (1, 2, 3)])
            self._write_results(run_dir, recs)
            args = _make_namespace(run_dir=run_dir, report=None)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rv = agentry.cmd_evaluate_collect(args)
            self.assertEqual(rv, 0)
            self.assertTrue((run_dir / "scorecard.md").exists())
            report = json.loads((run_dir / "scorecard.json").read_text(encoding="utf-8"))
            self.assertEqual(report["scenarios"][0]["delta"], "improved")
            self.assertEqual(report["comparison"]["improved"], 1)
            self.assertEqual(report["status"], "ok")
        finally:
            tmp.cleanup()

    def test_cmd_collect_missing_manifest_aborts(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            args = _make_namespace(run_dir=Path(tmp.name), report=None)
            with self.assertRaises(SystemExit):
                agentry.cmd_evaluate_collect(args)
        finally:
            tmp.cleanup()

    def test_cmd_collect_prints_missing_coverage_reason(self):
        # A partial run (only variant results in comparison mode) must exit 1 and
        # print why, so a 1-passed/100% line is not mistaken for success.
        tmp = tempfile.TemporaryDirectory()
        try:
            run_dir = Path(tmp.name)
            self._write_run(run_dir, self._manifest(comparison=True))
            recs = [self._rec("variant", "pass", i) for i in (1, 2, 3)]
            self._write_results(run_dir, recs)
            args = _make_namespace(run_dir=run_dir, report=None)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rv = agentry.cmd_evaluate_collect(args)
            out = buf.getvalue()
            self.assertEqual(rv, 1)
            self.assertIn("Incomplete run", out)
            self.assertIn("missing: s1 [trae:GPT-5.5/baseline]", out)
        finally:
            tmp.cleanup()

    def test_cmd_collect_prints_no_results_reason(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            run_dir = Path(tmp.name)
            (run_dir / "results").mkdir()
            # Manifest with no declared cases: an all-empty run scores nothing.
            manifest = self._manifest(comparison=False)
            manifest["scenarios"][0]["cases"] = []
            agentry.write_json(run_dir / "manifest.json", manifest)
            (run_dir / "results" / "out.jsonl").write_text("", encoding="utf-8")
            args = _make_namespace(run_dir=run_dir, report=None)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rv = agentry.cmd_evaluate_collect(args)
            self.assertEqual(rv, 1)
            self.assertIn("no scenario results were scored", buf.getvalue())
        finally:
            tmp.cleanup()


class ScorecardRenderTests(unittest.TestCase):
    def _report(self, comparison=True):
        return {
            "run_id": "r", "runner": {"name": "Agentry", "version": "0.5.1"}, "mode": "rendered",
            "sides": (
                {"baseline": {"label": "A"}, "variant": {"label": "B"}}
                if comparison else {"baseline": {"label": "current"}}
            ),
            "comparison_mode": comparison, "targets": ["trae:GPT-5.5"],
            "aggregate": {"passed": 1, "failed": 0, "needs_review": 0, "pass_pct": 100.0},
            "comparison": {"improved": 1, "regressed": 0, "unchanged": 0, "newly_covered": 0},
            "scenarios": [{
                "id": "s1", "target": "trae:GPT-5.5", "evidence_tier": "normal",
                "repetitions": 3, "min_consistent": 3, "delta": "improved",
                "sides": {
                    "baseline": {"outcome": "fail", "checks": [
                        {"id": "c1", "type": "rubric", "required": True, "outcome": "fail", "repetitions": 3}]},
                    "variant": {"outcome": "pass", "checks": [
                        {"id": "c1", "type": "rubric", "required": True, "outcome": "pass", "repetitions": 3}]},
                },
            }],
        }

    def test_markdown_has_aggregate_and_comparison(self):
        md = ec._render_scorecard_markdown(self._report())
        self.assertIn("Aggregate:", md)
        self.assertIn("Comparison:", md)
        self.assertIn("| s1 | trae:GPT-5.5 | fail | pass | improved", md)
        self.assertIn("Non-passing checks", md)
        # The runner provenance tag (name + moving project version) is surfaced.
        self.assertIn("- Runner: Agentry 0.5.1", md)

    def test_markdown_renders_evidence_override_line(self):
        report = self._report(comparison=False)
        report["evidence_override"] = {"min_consistent": 4, "repetitions": 5}
        md = ec._render_scorecard_markdown(report)
        self.assertIn("- Evidence override: 4/5 (consistent/total) applied at run time", md)

    def test_markdown_omits_evidence_line_when_no_override(self):
        md = ec._render_scorecard_markdown(self._report(comparison=False))
        self.assertNotIn("Evidence override", md)

    def test_json_round_trips(self):
        report = self._report(comparison=False)
        parsed = json.loads(ec._render_scorecard_json(report))
        self.assertEqual(parsed["run_id"], "r")

    def test_markdown_renders_integrity_section(self):
        report = self._report(comparison=False)
        report["aggregate"]["integrity"] = 1
        report["integrity_findings"] = [{
            "scenario": "s1", "target": "trae:GPT-5.5", "side": "baseline",
            "check": "c1", "repetition": 2, "finding": "evaluator-not-honored"}]
        md = ec._render_scorecard_markdown(report)
        self.assertIn("## Integrity", md)
        self.assertIn("evidence is untrustworthy", md)
        self.assertIn("| s1 | trae:GPT-5.5 | baseline | c1 | 2 | evaluator-not-honored |", md)

    def test_markdown_integrity_renders_empty_cells_for_cross_side(self):
        # A cross-side finding has no check/rep; those cells render empty.
        report = self._report(comparison=False)
        report["aggregate"]["integrity"] = 1
        report["integrity_findings"] = [{
            "scenario": "s1", "target": "trae:GPT-5.5", "side": "baseline/variant",
            "check": None, "repetition": None,
            "finding": "evaluator-inconsistent-across-sides"}]
        md = ec._render_scorecard_markdown(report)
        self.assertIn("| s1 | trae:GPT-5.5 | baseline/variant |  |  | evaluator-inconsistent-across-sides |", md)


class EvaluateRunOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _EvalRepo(self._tmp.name).add_scenarios()
        self._patches = self.repo.patches()
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()

    def _args(self, **kw):
        run_dir = self.repo.root / "run"
        return _make_namespace(
            artifact=None, plugin=["a"], component=None,
            scenario=kw.pop("scenario", ["seq"]), all=False,
            target=kw.pop("target", ["trae:GPT-5.5"]), evaluator=kw.pop("evaluator", None),
            baseline=kw.pop("baseline", None), variant=kw.pop("variant", None),
            run_dir=run_dir, mode="rendered",
            executor=kw.pop("executor", None),
            executor_command=kw.pop("executor_command", None),
            allow_fixture_drift=False,
            report=kw.pop("report", None), **kw)

    def test_run_requires_an_executor_form(self):
        # The executor is required; neither form given is a usage error and no
        # run dir should be materialized.
        args = self._args()
        with self.assertRaises(SystemExit):
            agentry.cmd_evaluate_run(args)
        self.assertFalse((self.repo.root / "run" / "manifest.json").exists())

    def test_run_unavailable_executor_tool_aborts(self):
        # A supported tool whose binary is absent from PATH aborts clearly and
        # does not materialize a run dir.
        args = self._args(executor="trae:GPT-5.5")
        with mock.patch.object(agentry.shutil, "which", return_value=None):
            with self.assertRaises(SystemExit):
                agentry.cmd_evaluate_run(args)
        self.assertFalse((self.repo.root / "run" / "manifest.json").exists())

    def test_run_with_executor_collects_results(self):
        args = self._args(executor_command="fake-exec")
        run_dir = self.repo.root / "run"

        def fake_run(argv, check=False):
            # The executor "produces" a captured output, then a passing record
            # that references it (provenance the collector requires).
            produced = "cases/seq/trae_GPT-5.5/baseline/produced/rep-1.md"
            ppath = run_dir / produced
            ppath.parent.mkdir(parents=True, exist_ok=True)
            ppath.write_text("the produced answer\n", encoding="utf-8")
            (run_dir / "results").mkdir(parents=True, exist_ok=True)
            rec = {"schema": ec.RESULT_SCHEMA, "schema_version": 1, "record_type": "check",
                   "run_id": "run", "scenario_id": "seq", "target": "trae:GPT-5.5",
                   "side": "baseline", "check_id": "findings-first", "outcome": "pass", "repetition": 1,
                   "producer": {"tool": "trae", "model": "GPT-5.5"},
                   "evaluator": {"id": "rubric-eval"},
                   "produced_output": produced,
                   "evidence": {"source_path": produced, "quote": "the produced answer"}}
            (run_dir / "results" / "out.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")
            return mock.Mock(returncode=0)

        with mock.patch.object(agentry.subprocess, "run", side_effect=fake_run):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rv = agentry.cmd_evaluate_run(args)
        self.assertIn("Scorecard:", buf.getvalue())
        # findings-first is required and passed 1/1; default tier is normal (3),
        # so 1 rep is below threshold -> needs-review -> nonzero exit.
        self.assertEqual(rv, 1)

    def test_run_unsupported_executor_tool_aborts(self):
        # A structured executor naming a tool with no known CLI aborts.
        args = self._args(executor="claude-code:opus")
        with self.assertRaises(SystemExit):
            agentry.cmd_evaluate_run(args)

    def test_run_failed_executor_returns_nonzero(self):
        args = self._args(executor_command="fake-exec")
        run_dir = self.repo.root / "run"

        def fake_run(argv, check=False):
            # Executor "fails" but writes a provenance-complete passing record;
            # run must still not pass because the executor exited nonzero.
            produced = "cases/seq/trae_GPT-5.5/baseline/produced/rep-1.md"
            ppath = run_dir / produced
            ppath.parent.mkdir(parents=True, exist_ok=True)
            ppath.write_text("the produced answer\n", encoding="utf-8")
            (run_dir / "results").mkdir(parents=True, exist_ok=True)
            rec = {"schema": ec.RESULT_SCHEMA, "schema_version": 1, "record_type": "check",
                   "run_id": "run", "scenario_id": "seq", "target": "trae:GPT-5.5",
                   "side": "baseline", "check_id": "findings-first", "outcome": "pass", "repetition": 1,
                   "producer": {"tool": "trae", "model": "GPT-5.5"},
                   "evaluator": {"id": "rubric-eval"},
                   "produced_output": produced,
                   "evidence": {"source_path": produced, "quote": "the produced answer"}}
            (run_dir / "results" / "out.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")
            return mock.Mock(returncode=3)

        with mock.patch.object(agentry.subprocess, "run", side_effect=fake_run):
            with redirect_stdout(io.StringIO()):
                rv = agentry.cmd_evaluate_run(args)
        self.assertEqual(rv, 1)

    def test_run_no_matching_scenarios_returns_one(self):
        args = self._args(scenario=["does-not-exist"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            rv = agentry.cmd_evaluate_run(args)
        self.assertEqual(rv, 1)
        self.assertIn("No scenarios matched", buf.getvalue())

    def test_resolve_executor_structured_pins_model(self):
        # Structured tool:model resolves to the tool's CLI with the model pinned.
        with mock.patch.object(agentry.shutil, "which", return_value="/usr/bin/traecli"):
            argv = agentry.resolve_executor(
                {"id": "trae:GPT-5.5", "tool": "trae", "model": "GPT-5.5"}, None)
        self.assertEqual(argv, ["/usr/bin/traecli", "exec", "--model", "GPT-5.5"])

    def test_resolve_executor_unknown_tool_raises(self):
        with self.assertRaises(agentry.UnsupportedExecutor):
            agentry.resolve_executor(
                {"id": "claude-code:opus", "tool": "claude-code", "model": "opus"}, None)

    def test_resolve_executor_unavailable_binary_raises(self):
        with mock.patch.object(agentry.shutil, "which", return_value=None):
            with self.assertRaises(agentry.ExecutorUnavailable):
                agentry.resolve_executor(
                    {"id": "trae:GPT-5.5", "tool": "trae", "model": "GPT-5.5"}, None)

    def test_resolve_executor_command_wins(self):
        # Freeform command is used as-is, regardless of any structured descriptor.
        argv = agentry.resolve_executor(None, "my exec here")
        self.assertEqual(argv, ["my", "exec", "here"])


class EvaluateCleanTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _make_run(self, name):
        run = self.root / name
        run.mkdir(parents=True)
        (run / "manifest.json").write_text("{}", encoding="utf-8")
        return run

    def _args(self, **kw):
        return _make_namespace(runs_root=self.root, keep_last=kw.pop("keep_last", 0),
                               dry_run=kw.pop("dry_run", False), **kw)

    def test_clean_removes_all_runs(self):
        self._make_run("run-a")
        self._make_run("run-b")
        with redirect_stdout(io.StringIO()):
            rv = agentry.cmd_evaluate_clean(self._args())
        self.assertEqual(rv, 0)
        self.assertFalse((self.root / "run-a").exists())
        self.assertFalse((self.root / "run-b").exists())

    def test_clean_keep_last_retains_newest(self):
        self._make_run("run-a")
        self._make_run("run-b")
        self._make_run("run-c")
        with redirect_stdout(io.StringIO()):
            agentry.cmd_evaluate_clean(self._args(keep_last=1))
        # Sorted by name, run-c is newest and kept.
        self.assertFalse((self.root / "run-a").exists())
        self.assertFalse((self.root / "run-b").exists())
        self.assertTrue((self.root / "run-c").exists())

    def test_clean_dry_run_deletes_nothing(self):
        self._make_run("run-a")
        with redirect_stdout(io.StringIO()):
            agentry.cmd_evaluate_clean(self._args(dry_run=True))
        self.assertTrue((self.root / "run-a").exists())

    def test_clean_ignores_non_run_dirs(self):
        # A directory without a manifest.json must not be removed.
        (self.root / "not-a-run").mkdir()
        (self.root / "not-a-run" / "keep.txt").write_text("x", encoding="utf-8")
        self._make_run("run-a")
        with redirect_stdout(io.StringIO()):
            agentry.cmd_evaluate_clean(self._args())
        self.assertTrue((self.root / "not-a-run").exists())
        self.assertFalse((self.root / "run-a").exists())

    def test_clean_missing_root_is_noop(self):
        args = _make_namespace(runs_root=self.root / "nope", keep_last=0, dry_run=False)
        with redirect_stdout(io.StringIO()):
            rv = agentry.cmd_evaluate_clean(args)
        self.assertEqual(rv, 0)


class EvaluateCliWiringTests(unittest.TestCase):
    def _parser(self):
        parser = argparse.ArgumentParser(prog="agentry.py")
        sub = parser.add_subparsers(dest="command")
        p_evaluate = sub.add_parser("evaluate")
        eval_sub = p_evaluate.add_subparsers(dest="evaluate_command")
        p_prepare = eval_sub.add_parser("prepare")
        agentry.add_evaluate_scope_args(p_prepare)
        p_prepare.add_argument("--baseline", default=agentry.EVAL_WORKTREE_SOURCE)
        p_prepare.add_argument("--variant")
        p_prepare.add_argument("--run-dir", type=Path)
        p_prepare.add_argument("--mode", choices=agentry.EVAL_MODES, default="rendered")
        p_prepare.add_argument("--allow-fixture-drift", action="store_true")
        agentry.add_color_arg(p_prepare)
        p_collect = eval_sub.add_parser("collect")
        p_collect.add_argument("run_dir", type=Path)
        p_collect.add_argument("--report", type=Path)
        agentry.add_color_arg(p_collect)
        return parser

    def test_prepare_parses_repeatable_scope(self):
        args = self._parser().parse_args([
            "evaluate", "prepare", "plugins/a/skills/skill-one",
            "--plugin", "a", "--plugin", "b", "--component", "skills",
            "--scenario", "seq", "--target", "trae:GPT-5.5", "--run-dir", "run",
            "--baseline", "ref:A", "--variant", "worktree",
        ])
        self.assertEqual(args.evaluate_command, "prepare")
        self.assertEqual(args.plugin, ["a", "b"])
        self.assertEqual(args.component, ["skills"])
        self.assertEqual(args.scenario, ["seq"])
        self.assertEqual(args.target, ["trae:GPT-5.5"])
        self.assertEqual(args.baseline, "ref:A")
        self.assertEqual(args.variant, "worktree")

    def test_collect_parses_run_dir(self):
        args = self._parser().parse_args(["evaluate", "collect", "run", "--report", "sc.md"])
        self.assertEqual(args.evaluate_command, "collect")
        self.assertEqual(args.run_dir, Path("run"))

    def test_prepare_parses_evaluator(self):
        args = self._parser().parse_args([
            "evaluate", "prepare", "--scenario", "seq",
            "--target", "trae:GPT-5.5", "--evaluator", "trae:strong", "--run-dir", "run",
        ])
        self.assertEqual(args.evaluator, "trae:strong")

    def test_run_executor_mutex_accepts_structured(self):
        args = self._build_run_args(["--executor", "trae:GPT-5.5"])
        self.assertEqual(args.executor, "trae:GPT-5.5")
        self.assertIsNone(args.executor_command)

    def test_run_executor_mutex_accepts_command(self):
        args = self._build_run_args(["--executor-command", "traecli exec"])
        self.assertEqual(args.executor_command, "traecli exec")
        self.assertIsNone(args.executor)

    def test_run_executor_mutex_rejects_both(self):
        # Drive the real main() parser: the required mutex must reject both forms.
        with self.assertRaises(SystemExit):
            agentry.main([
                "evaluate", "run", "--scenario", "seq", "--target", "trae:GPT-5.5",
                "--executor", "trae:GPT-5.5", "--executor-command", "x",
            ])

    def test_run_executor_required(self):
        # Drive the real main() parser: omitting both forms is a usage error.
        with self.assertRaises(SystemExit):
            agentry.main([
                "evaluate", "run", "--scenario", "seq", "--target", "trae:GPT-5.5",
            ])

    def _build_run_args(self, extra):
        # Reproduce the real 'run' subparser wiring for isolated arg parsing.
        parser = argparse.ArgumentParser(prog="agentry.py")
        sub = parser.add_subparsers(dest="command")
        p_evaluate = sub.add_parser("evaluate")
        eval_sub = p_evaluate.add_subparsers(dest="evaluate_command")
        p_run = eval_sub.add_parser("run")
        agentry.add_evaluate_scope_args(p_run)
        p_run.add_argument("--baseline", default=agentry.EVAL_WORKTREE_SOURCE)
        p_run.add_argument("--variant")
        p_run.add_argument("--run-dir", type=Path)
        p_run.add_argument("--mode", choices=agentry.EVAL_MODES, default="rendered")
        group = p_run.add_mutually_exclusive_group(required=True)
        group.add_argument("--executor")
        group.add_argument("--executor-command", dest="executor_command")
        p_run.add_argument("--allow-fixture-drift", action="store_true")
        p_run.add_argument("--report", type=Path)
        agentry.add_color_arg(p_run)
        return parser.parse_args([
            "evaluate", "run", "--scenario", "seq", "--target", "trae:GPT-5.5", *extra,
        ])

    def test_main_wires_clean_subcommand(self):
        # Drive the real main() parser so the clean wiring is exercised end to end.
        tmp = tempfile.TemporaryDirectory()
        try:
            repo = _EvalRepo(tmp.name)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rv = agentry.main(["evaluate", "clean", "--dry-run"], repo_root=repo.root)
            self.assertEqual(rv, 0)
            self.assertIn("Nothing to clean", buf.getvalue())
        finally:
            tmp.cleanup()


class EvaluateGitIntegrationTests(unittest.TestCase):
    """Real git snapshot fidelity, guarded so the suite has no hard git dep."""

    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_snapshot_reads_object_history(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            root = Path(tmp.name)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
            skill = root / "plugins" / "a" / "skills" / "s"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("v1\n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "v1"], cwd=root, check=True)
            (skill / "SKILL.md").write_text("v2\n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "v2"], cwd=root, check=True)
            with mock.patch.object(agentry, "REPO_ROOT", root):
                dest = root / "snap"
                agentry.snapshot_artifact_source("HEAD~1", "plugins/a/skills/s", dest)
                self.assertEqual((dest / "plugins/a/skills/s/SKILL.md").read_text(encoding="utf-8"), "v1\n")
        finally:
            tmp.cleanup()

