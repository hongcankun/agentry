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
