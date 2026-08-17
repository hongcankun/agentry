#!/usr/bin/env python3
"""Agentry maintenance CLI: install, status, uninstall, inventory, and generate.

Reads the canonical manifest (``agentry.json``) — the tool-agnostic source of
truth — and installs components, reports manifest/install state, or regenerates
the per-tool packaging derived from the manifest.

Subcommands:

- ``install``   — copy or symlink selected plugins' components into a tool's dirs.
- ``status``    — report each item's install state without writing; exit 1 on drift.
- ``uninstall`` — remove components this tool installed (owned copies/links).
- ``inventory`` — report manifest plugins, versions, and component membership.
- ``generate``  — regenerate Claude Code and/or Trae packaging from the manifest.
- ``validate``  — run repository consistency checks.
- ``evaluate``  — behavioral evaluation for authoring artifacts (prepare/collect/run).

Delivery channels. Neither tool's plugin format has a "rules" component, so
rules are never delivered by a marketplace install; ``install`` always copies
them. Skills/subagents/commands come through one of two channels:

- marketplace — orchestrate the tool's own CLI (``claude``/``traecli``) to add the
  Agentry marketplace and install the selected plugins. These plugins are
  user-scoped, so this channel forces ``--global`` (and never writes a tool's
  project config). Used by default for a ``--global`` run.
- checkout — copy the ``--component`` selection straight from this checkout and
  never touch the tool CLI — for development, or tools without marketplace
  support. An omitted ``--component`` means all components on this channel.
  Used by default at project scope. ``--source checkout`` forces it, and naming
  ``--component`` selects it (those files come from the checkout).

Pick a channel explicitly with ``--source {marketplace,checkout}``. Interactively,
a ``--global`` run defaults to the marketplace channel and does not prompt for
components; pass ``--source checkout`` (or ``--component``) to copy
skills/agents/commands from the checkout instead.

``uninstall`` mirrors this: the marketplace channel uninstalls the selected
plugins via the tool CLI and removes the marketplace only once no Agentry plugin
remains (to keep or force-remove it otherwise, use the tool's own CLI).
``status`` reports the marketplace and per-plugin install state read-only, at any
scope (plugins are user-scoped).

Downstream reuse. This module is the reusable engine: a downstream catalog
vendors it (e.g. via git submodule) and calls ``main(repo_root=..., manifest_name=...,
prog=..., brand=...)`` so every command, its generated provenance text, and its
help/header read that catalog's own root, manifest, program name, and brand. The
examples below show Agentry's own invocation (the defaults); a downstream wrapper
substitutes its program name (e.g. ``scripts/downstream.py``) and manifest.

Examples:
    # Global install: add the marketplace + install the plugin, then copy rules
    python3 scripts/agentry.py install --tool claude --global --plugin agentry-code-quality
    python3 scripts/agentry.py install --tool trae --global --plugin agentry-code-quality --yes

    # Copy all components at project scope (checkout channel, file-only)
    python3 scripts/agentry.py install --tool claude --plugin agentry-code-quality
    python3 scripts/agentry.py install --tool trae --plugin agentry-code-quality

    # Copy skills, subagents, and commands directly from a checkout (--component selects checkout)
    python3 scripts/agentry.py install --tool trae --component skills --component agents --component commands

    # Report-only check (exit 1 on drift), and global removal
    python3 scripts/agentry.py status --tool claude --global
    python3 scripts/agentry.py uninstall --tool trae --global --plugin agentry-code-quality

    # Inventory the canonical manifest contents
    python3 scripts/agentry.py inventory
    python3 scripts/agentry.py inventory --plugin agentry-code-quality --component skills --paths

    # Regenerate packaging, verify generated files, or run all consistency checks
    python3 scripts/agentry.py generate
    python3 scripts/agentry.py generate --check
    python3 scripts/agentry.py validate
"""

import argparse
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

# The behavioral-evaluation contract (schema constants and the collect stage)
# lives in a freestanding, stdlib-only sibling module so a byte-identical copy
# can run inside a skill. Import the moved names back here so existing
# ``agentry.<name>`` references keep working. Guard the sys.path insert so a
# repeated import does not shadow another checkout's copy.
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
import eval_contract as ec
# The evaluation contract lives in the freestanding eval_contract module; agentry
# reaches it only through the ``ec`` alias (ec.prepare/collect/parse_scenario/...)
# so the boundary is visible at every call site and nothing is re-exported here.

# Default repo root for Agentry's own checkout: the parent of scripts/. A
# downstream catalog reusing this module via git submodule keeps its own content
# elsewhere, so it injects its root/manifest via main(); see configure().
# __file__ would otherwise resolve inside the submodule and point every path at
# Agentry's own content.
DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST_NAME = "agentry.json"
# Program name shown in help/usage and woven into generated provenance text. A
# downstream wrapper passes its own (e.g. "downstream.py") via main(prog=...); the
# default reproduces `scripts/agentry.py` output byte-for-byte.
DEFAULT_PROG = "agentry.py"
# Display name shown in the CLI help banner and the install/status/uninstall run
# header. A downstream wrapper passes its own (e.g. "Downstream") via main(brand=...);
# the default reproduces Agentry's own help/header text exactly.
DEFAULT_BRAND = "Agentry"

# Resolved repo location and derived paths. These module globals are the runtime
# config every command reads; configure() recomputes them from a repo root and
# manifest name, and main() calls it once per invocation. They default to
# Agentry's own checkout so importing the module (and `scripts/agentry.py ...`)
# behaves exactly as before.
REPO_ROOT = DEFAULT_REPO_ROOT
MANIFEST = REPO_ROOT / DEFAULT_MANIFEST_NAME
PLUGINS_DIR = REPO_ROOT / "plugins"
RULES_DIR = REPO_ROOT / "rules"
# Program name woven into generated provenance text; see DEFAULT_PROG. Set by
# configure() so generated artifacts name the active wrapper, not this module.
PROG = DEFAULT_PROG
# Display name shown in CLI help/header text; see DEFAULT_BRAND. Set by
# configure() so a downstream catalog's interactive output reads its own name.
BRAND = DEFAULT_BRAND

CLAUDE_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
TRAE_MARKETPLACE = REPO_ROOT / ".trae-plugin" / "marketplace.json"


def configure(repo_root=None, manifest_name=DEFAULT_MANIFEST_NAME, prog=DEFAULT_PROG, brand=DEFAULT_BRAND):
    """Point the CLI at a repo root and manifest, recomputing derived paths.

    ``repo_root=None`` selects Agentry's own checkout (``DEFAULT_REPO_ROOT``),
    preserving the original behavior exactly. A downstream wrapper passes its own
    root and manifest filename so install/uninstall/generate/status/inventory all
    operate against that tree instead of the (submodule) location of this file.
    ``prog`` is the program name woven into generated provenance text, and
    ``brand`` is the display name shown in CLI help/header text, so those name the
    active wrapper rather than this module.
    """
    global REPO_ROOT, MANIFEST, PLUGINS_DIR, RULES_DIR, PROG, BRAND
    global CLAUDE_MARKETPLACE, TRAE_MARKETPLACE
    REPO_ROOT = (DEFAULT_REPO_ROOT if repo_root is None else Path(repo_root)).resolve()
    MANIFEST = REPO_ROOT / manifest_name
    PLUGINS_DIR = REPO_ROOT / "plugins"
    RULES_DIR = REPO_ROOT / "rules"
    PROG = prog
    BRAND = brand
    CLAUDE_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    TRAE_MARKETPLACE = REPO_ROOT / ".trae-plugin" / "marketplace.json"


def cli_name():
    """Return the path-form CLI name used in generated provenance text.

    ``PROG`` is the bare program name (``agentry.py``); generated artifacts and
    the ``generate --check`` hint refer to it by its in-repo path, so a
    downstream wrapper named ``downstream.py`` yields ``scripts/downstream.py``.
    """
    return f"scripts/{PROG}"


def manifest_label():
    """Return the active manifest filename (e.g. ``agentry.json``).

    Derived from the resolved ``MANIFEST`` path so generated provenance text and
    error messages name the manifest a downstream wrapper actually loaded.
    """
    return MANIFEST.name


COMPONENTS = ("skills", "agents", "commands", "rules")
COMPONENT_CHOICES = COMPONENTS + ("all",)

COMPONENT_TITLE = {"rules": "Rules", "skills": "Skills", "agents": "Agents", "commands": "Commands"}

# ---------------------------------------------------------------------------
# Behavioral evaluation (`evaluate`) contract constants.
#
# The evaluate subcommand is a structured-data broker: it prepares scenario
# cases, optionally invokes an external agent executor, and collects/validates
# JSONL result records into a scorecard. It never invokes an LLM or parses
# free-form agent prose. See docs/designs/0001-behavioral-evaluation-authoring-artifacts.md.

# Scenario directories mirror the component vocabulary but live under an `eval/`
# tree outside normal component roots, so marketplace/generate/install discovery
# never treats them as shippable artifacts.
EVAL_DIR_NAME = "eval"
# eval trees are keyed by artifact kind (plural component name) then artifact.
EVAL_COMPONENTS = ("skills", "commands", "agents", "rules")

# The evaluation contract constants (schema markers, versions, vocabularies,
# evidence tiers) are imported from the freestanding ``eval_contract`` module;
# see the import block after ``from pathlib import Path``.

# Execution modes. Rendered simulation is portable and fully built by the runner;
# true-activation sandbox is preferred for acceptance evidence and delegates
# tool isolation/transcript capture to the executor + evaluation-sandbox skill.
EVAL_MODES = ("rendered", "sandbox")
DEFAULT_EVAL_MODE = "rendered"

# Default location for evaluation run directories: a dedicated, self-describing,
# gitignored root under the repo (not a generic scratch dir), so scorecards stay
# discoverable for PR evidence and are easy to clean with `evaluate clean`.
EVAL_RUNS_DIRNAME = ".eval-runs"

FILE_REPORT_TAGS = {"missing", "synced", "stale"}
PLUGIN_REPORT_TAGS = {
    "unknown", "added", "installed", "missing", "absent", "kept", "skipped", "failed",
}
PLUGIN_INSTALL_ACTION_TAGS = {"would install", "installed", "would add", "added"}
PLUGIN_REMOVE_ACTION_TAGS = {"would remove", "removed"}

# Per-tool target directory for each component, relative to the project root
# (project scope) or the home directory (global scope). Kept in sync with the
# rule-authoring, subagent-authoring, and command-authoring skill conventions.
TOOL_TARGETS = {
    "claude": {
        "skills": ".claude/skills",
        "agents": ".claude/agents",
        "commands": ".claude/commands",
        "rules": ".claude/rules",
    },
    "trae": {
        "skills": ".trae/skills",
        "agents": ".trae/agents",
        "commands": ".trae/commands",
        "rules": ".trae/rules",
    },
}

# The CLI binary that manages each tool's plugins/marketplaces. agentry.py shells
# out to these (no shell) to add the marketplace and install/uninstall plugins
# when orchestrating; resolved on PATH via shutil.which at call time.
TOOL_BINARIES = {"claude": "claude", "trae": "traecli"}
MARKETPLACE_REFRESH_COMMANDS = {
    "claude": "claude plugin marketplace update {name}",
    "trae": "traecli plugin marketplace upgrade {name}",
}

# Install states for a planned (src -> dest) job that the installer must act on.
ACTION_STATES = ("missing", "copied-stale", "stale-link")
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

# ANSI color codes, applied only when stdout is a TTY and NO_COLOR is unset
# (https://no-color.org). Populated by init_colors().
_COLORS = {"green": "", "yellow": "", "red": "", "cyan": "", "dim": "", "reset": ""}

# Whether to prefix report lines with state emoji. Gated on the same condition
# as color so piped/CI output stays plain, aligned, and easy to parse.
_USE_EMOJI = False


def init_colors(enabled):
    global _USE_EMOJI
    if not enabled:
        return
    _USE_EMOJI = True
    _COLORS.update(
        green="\033[32m",
        yellow="\033[33m",
        red="\033[31m",
        cyan="\033[36m",
        dim="\033[2m",
        reset="\033[0m",
    )


def colorize(text, color):
    code = _COLORS[color]
    return f"{code}{text}{_COLORS['reset']}" if code else text


def _strip_color(text):
    """Remove ANSI color escape sequences from ``text``.

    Used when probing a pre-formatted row for its tag (e.g. in the
    Summary counter).
    """
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def prompt_rows(text):
    """Return how many terminal rows text occupies after line wrapping."""
    width = max(1, shutil.get_terminal_size(fallback=(80, 24)).columns)
    rows = 0
    for line in _strip_color(text).splitlines() or [""]:
        rows += max(1, (len(line) + width - 1) // width)
    return rows


def erase_tty_rows(rows):
    """Erase the last rows from a TTY and flush so cleanup is immediate."""
    if sys.stdout.isatty():
        sys.stdout.write(f"\033[{rows}F\033[J")
        sys.stdout.flush()


def indent():
    # Body lines (report rows, detail, prompts, actions) indent to align under
    # the header text. With the 📦 prefix (2 cols + space) that is 3, else 2.
    return "   " if _USE_EMOJI else "  "


# Color per install state, used for the status tag in the report.
STATE_COLOR = {
    "missing": "yellow",
    "linked": "green",
    "copied-current": "green",
    "copied-stale": "red",
    "stale-link": "red",
}


def resolve_colors(choice):
    """Map the --color choice to a bool and initialize the color/emoji state."""
    if choice == "always":
        use_color = True
    elif choice == "never":
        use_color = False
    else:
        use_color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    init_colors(use_color)
    return use_color


def load_manifest():
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"error: manifest not found at {MANIFEST}")
    except json.JSONDecodeError as exc:
        sys.exit(f"error: invalid JSON in {MANIFEST}: {exc}")


def load_plugins():
    return load_manifest().get("plugins", [])


def plugin_selection_label(plugin_names):
    """Return a compact human label for the current plugin selection."""
    if not plugin_names:
        return "all"
    if isinstance(plugin_names, str):
        return plugin_names
    return ", ".join(dict.fromkeys(plugin_names))


def select_plugins(plugins, plugin_names):
    if not plugin_names:
        return plugins
    if isinstance(plugin_names, str):
        plugin_names = [plugin_names]

    requested = list(dict.fromkeys(plugin_names))
    available = {p.get("name") for p in plugins}
    unknown = [name for name in requested if name not in available]
    if unknown:
        names = ", ".join(p.get("name", "?") for p in plugins)
        quoted = ", ".join(f"'{name}'" for name in unknown)
        sys.exit(f"error: unknown plugin(s) {quoted}. Available: {names}")

    requested_set = set(requested)
    return [p for p in plugins if p.get("name") in requested_set]


def validate_path_fragment(value, label, *, allow_nested):
    """Return ``value`` after rejecting absolute or parent-traversing paths."""
    if not isinstance(value, str) or not value:
        sys.exit(f"error: unsafe {label}: {value!r}")
    path = Path(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        sys.exit(f"error: unsafe {label}: {value}")
    if not allow_nested and (len(path.parts) != 1 or not SAFE_NAME_RE.fullmatch(value)):
        sys.exit(f"error: unsafe {label}: {value}")
    return value


def confined_path(base, rel_path, label):
    """Join ``rel_path`` under ``base`` and fail if the resolved path escapes."""
    root = base.resolve()
    candidate = (base / rel_path).resolve()
    if candidate != root and root not in candidate.parents:
        sys.exit(f"error: {label} escapes {base}: {rel_path}")
    return candidate


def confined_leaf_path(base, rel_path, label):
    """Join a destination leaf under ``base`` without resolving the leaf itself."""
    path = base / rel_path
    root = base.resolve()
    parent = path.parent.resolve()
    if parent != root and root not in parent.parents:
        sys.exit(f"error: {label} escapes {base}: {rel_path}")
    return path


def plugin_component_entries(plugin, components):
    """Yield (component, source, relative-destination) entries for one plugin."""
    plugin_name = validate_path_fragment(plugin["name"], "plugin name", allow_nested=False)
    if "skills" in components:
        for skill in plugin.get("skills", []):
            skill_name = validate_path_fragment(skill, "skill name", allow_nested=False)
            yield "skills", PLUGINS_DIR / plugin_name / "skills" / skill_name, skill_name
    if "agents" in components:
        for agent in plugin.get("agents", []):
            agent_name = validate_path_fragment(agent, "agent name", allow_nested=False)
            yield (
                "agents",
                PLUGINS_DIR / plugin_name / "agents" / f"{agent_name}.md",
                f"{agent_name}.md",
            )
    if "commands" in components:
        for command in plugin.get("commands", []):
            command_name = validate_path_fragment(command, "command name", allow_nested=False)
            yield (
                "commands",
                PLUGINS_DIR / plugin_name / "commands" / f"{command_name}.md",
                f"{command_name}.md",
            )
    if "rules" in components:
        for rule in plugin.get("rules", []):
            rule_path = validate_path_fragment(rule, "rule path", allow_nested=True)
            yield "rules", RULES_DIR / rule_path, rule_path


def plan_copies(plugins, components):
    """Return a list of (component, src_path, rel_dest) tuples to install."""
    jobs = []
    seen = set()
    for plugin in plugins:
        for component, src, rel_dest in plugin_component_entries(plugin, components):
            key = (component, rel_dest)
            if key not in seen:
                seen.add(key)
                jobs.append((component, src, rel_dest))
    return jobs


def component_selection(component_args):
    """Expand optional --component values into the component set to report."""
    if component_args and "all" in component_args:
        return set(COMPONENTS)
    return set(component_args) if component_args else set(COMPONENTS)


def dirs_equal(a, b):
    """Recursively compare two directory trees by content (skills are dirs)."""
    # ignore=[] overrides filecmp.DEFAULT_IGNORES (which hides .git, CVS, etc.)
    # so packaged dotfiles inside a skill are compared and cannot mask drift.
    cmp = filecmp.dircmp(a, b, ignore=[], hide=[os.curdir, os.pardir])
    if cmp.left_only or cmp.right_only or cmp.funny_files:
        return False
    # shallow=False forces content comparison, not just stat (size/mtime).
    _, mismatch, errors = filecmp.cmpfiles(a, b, cmp.common_files, shallow=False)
    if mismatch or errors:
        return False
    return all(dirs_equal(Path(a) / sub, Path(b) / sub) for sub in cmp.common_dirs)


def classify_state(src, dest):
    """Classify an installed dest against its canonical src.

    Returns one of: 'missing', 'linked', 'copied-current', 'copied-stale',
    'stale-link'. Symlinks are checked before exists() because a broken link
    reports exists()==False and would otherwise look 'missing'.
    """
    if dest.is_symlink():
        target = (dest.parent / os.readlink(dest)).resolve()
        return "linked" if target == src.resolve() else "stale-link"
    if not dest.exists():
        return "missing"
    if src.is_dir() != dest.is_dir():
        return "copied-stale"
    if src.is_dir():
        return "copied-current" if dirs_equal(src, dest) else "copied-stale"
    return "copied-current" if filecmp.cmp(src, dest, shallow=False) else "copied-stale"


def needs_action(state):
    return state in ACTION_STATES


def action_verb(state):
    return "install" if state == "missing" else "update"


def report_line(state, rel, width):
    """Aligned status line for the report pass; rel is the dest path under base.

    width is the shared label column width so report tags line up with the
    action labels printed later.
    """
    tags = {
        "missing": "missing",
        "linked": "synced",
        "copied-current": "synced",
        "copied-stale": "stale",
        "stale-link": "stale",
    }
    notes = {
        "linked": "linked",
        "copied-current": "copied",
        "copied-stale": "differs from source",
        "stale-link": "points elsewhere",
    }
    # Pad before coloring so ANSI codes don't break column alignment.
    tag = colorize(f"{tags[state]:<{width}}", STATE_COLOR[state])
    line = f"{indent()}{tag} {rel}"
    if state in notes:
        line += colorize(f"  ({notes[state]})", "dim")
    return line


# Color per outcome tag used in the marketplace/plugin section, so its rows read
# with the same vocabulary as the file report: green = present/done/intended,
# yellow = absent/skipped/unknown, red = failed. The "would …" tags are the
# dry-run previews, mirroring the file report's "would install"/"would remove".
PLUGIN_TAG_COLOR = {
    "added": "green",
    "installed": "green",
    "removed": "green",
    "would add": "green",
    "would install": "green",
    "would remove": "green",
    "missing": "yellow",
    "absent": "yellow",
    "skipped": "yellow",
    "kept": "yellow",
    "unknown": "yellow",
    "failed": "red",
}


def plugin_row(tag, name, width=None, note=None):
    """Aligned, colored row for the marketplace/plugin section.

    Mirrors ``report_line`` so plugin rows read like file rows: a padded
    color tag, the entity name, then an optional dim note. ``width`` is the
    tag-column width; when omitted it is sized to the longest state-phase
    tag (``unknown`` / ``missing`` / ``installed`` / …), which is all most
    call sites need. Action-phase call sites (the "Changes" block) pass a
    shared width so plugin and file action rows line up. Pad before
    coloring so ANSI codes do not throw off alignment.
    """
    if width is None:
        width = max(len(t) for t in (
            "unknown", "missing", "absent", "added", "installed", "removed",
            "kept", "skipped", "failed",
        ))
    cell = colorize(f"{tag:<{width}}", PLUGIN_TAG_COLOR.get(tag, "cyan"))
    line = f"{indent()}{cell} {name}"
    if note:
        line += colorize(f"  ({note})", "dim")
    return line


def plugin_section_header():
    """Print the cyan section header shared by the marketplace/plugin reports.

    The tool name is already shown in the run header above, so it is omitted here.
    """
    print(colorize(f"{indent()}Plugins", "cyan"))


def marketplace_refresh_hint(tool, name):
    """Return the native CLI command that refreshes marketplace metadata."""
    template = MARKETPLACE_REFRESH_COMMANDS.get(tool)
    if template is None:
        return None
    return template.format(name=name)


def marketplace_refresh_hint_line(args, manifest, state):
    """Return the post-summary marketplace refresh hint, when state is known."""
    if not state or not state.get("mkt_ok"):
        return None
    mkt = marketplace_name(manifest)
    if mkt not in state.get("markets", set()):
        return None
    refresh = marketplace_refresh_hint(args.tool, mkt)
    if refresh is None:
        return None
    return f"{indent()}Hint: refresh with `{refresh}`"


def print_marketplace_refresh_hint(args, manifest, state):
    """Print a dim post-summary hint for refreshing a configured marketplace."""
    line = marketplace_refresh_hint_line(args, manifest, state)
    if line:
        print(colorize(line, "dim"))


def print_grouped_report(plan, label_width):
    """Print the file report rows grouped under a cyan per-component header.

    ``plan`` rows are ``(component, src, dest, rel, state)``. Groups preserve the
    fixed COMPONENT order and are separated by a blank line, mirroring the
    "Plugins" section so every part of the report is a labeled group.
    """
    by_component = {}
    for row in plan:
        by_component.setdefault(row[0], []).append(row)
    first = True
    for component in COMPONENTS:
        rows = by_component.get(component)
        if not rows:
            continue
        if not first:
            print()
        first = False
        print(colorize(f"{indent()}{COMPONENT_TITLE[component]}", "cyan"))
        for _, _, _, rel, state in rows:
            print(report_line(state, rel, label_width))


# ---- inventory --------------------------------------------------------------

def inventory_entries(plugin, components, include_paths=False):
    """Return manifest component entries for one plugin."""
    entries = {component: [] for component in COMPONENTS}
    for component in COMPONENTS:
        if component not in components:
            continue
        for name in plugin.get(component, []):
            item = {"name": name}
            if include_paths:
                item["path"] = inventory_component_path(plugin, component, name)
            entries[component].append(item)
    return entries


def inventory_component_path(plugin, component, name):
    """Return the canonical source path for a manifest component entry."""
    plugin_name = validate_path_fragment(plugin["name"], "plugin name", allow_nested=False)
    if component == "skills":
        item_name = validate_path_fragment(name, "skill name", allow_nested=False)
        return str(Path("plugins") / plugin_name / "skills" / item_name)
    if component == "agents":
        item_name = validate_path_fragment(name, "agent name", allow_nested=False)
        return str(Path("plugins") / plugin_name / "agents" / f"{item_name}.md")
    if component == "commands":
        item_name = validate_path_fragment(name, "command name", allow_nested=False)
        return str(Path("plugins") / plugin_name / "commands" / f"{item_name}.md")
    if component == "rules":
        return str(Path("rules") / validate_path_fragment(name, "rule path", allow_nested=True))
    sys.exit(f"error: unknown component: {component}")


def build_inventory(manifest, plugins, components, include_paths=False):
    """Build a structured, read-only report from the canonical manifest."""
    report_plugins = []
    totals = {component: 0 for component in COMPONENTS}
    for plugin in plugins:
        component_items = inventory_entries(plugin, components, include_paths)
        for component, items in component_items.items():
            totals[component] += len(items)
        report_plugins.append(
            {
                "name": plugin.get("name", ""),
                "version": plugin.get("version", ""),
                "description": plugin.get("description", ""),
                "components": component_items,
            }
        )
    return {
        "name": manifest.get("name", ""),
        "version": manifest.get("version", ""),
        "repository": manifest.get("repository", ""),
        "plugins": report_plugins,
        "totals": {
            "plugins": len(report_plugins),
            "components": totals,
            "componentEntries": sum(totals.values()),
        },
    }


def inventory_count_cell(count, width):
    """Right-align an inventory count and dim zeroes."""
    text = f"{count:>{width}}"
    return colorize(text, "dim") if count == 0 else text


def print_inventory_summary(report, components):
    """Render a compact table for scanning plugin component counts."""
    totals = report["totals"]
    component_summary = ", ".join(
        f"{component}: {totals['components'][component]}" for component in COMPONENTS if component in components
    )
    title = report["name"] or BRAND
    version = f" {report['version']}" if report.get("version") else ""
    print(colorize(f"Inventory: {title}{version}", "cyan"))
    print(f"{indent()}plugins: {totals['plugins']}")
    print(f"{indent()}components: {totals['componentEntries']} ({component_summary})")
    if report.get("repository"):
        print(colorize(f"{indent()}repository: {report['repository']}", "dim"))

    columns = [("plugin", "name"), ("version", "version")]
    columns.extend((component, component) for component in COMPONENTS if component in components)
    widths = {}
    for label, key in columns:
        if key in COMPONENTS:
            values = [str(len(plugin["components"][key])) for plugin in report["plugins"]]
        else:
            values = [plugin.get(key, "") for plugin in report["plugins"]]
        widths[key] = max(len(label), *(len(value) for value in values)) if values else len(label)

    print()
    header = "  ".join(f"{label:<{widths[key]}}" for label, key in columns)
    print(colorize(f"{indent()}{header}", "dim"))
    for plugin in report["plugins"]:
        cells = []
        for _label, key in columns:
            if key in COMPONENTS:
                cells.append(inventory_count_cell(len(plugin["components"][key]), widths[key]))
            else:
                cells.append(f"{plugin.get(key, ''):<{widths[key]}}")
        print(f"{indent()}{'  '.join(cells)}")


def print_inventory_details(report, components, include_paths=False):
    """Render expanded component membership for narrowed or detailed reports."""
    for plugin in report["plugins"]:
        print()
        version = f" {plugin['version']}" if plugin.get("version") else ""
        print(colorize(f"{indent()}{plugin['name']}{version}", "cyan"))
        if plugin.get("description"):
            print(colorize(f"{indent()}  {plugin['description']}", "dim"))
        for component in COMPONENTS:
            if component not in components:
                continue
            items = plugin["components"][component]
            label = COMPONENT_TITLE[component].lower()
            if not items:
                print(f"{indent()}  {colorize(label, 'cyan')}: {colorize('0', 'dim')}")
                continue
            if include_paths:
                print(f"{indent()}  {colorize(label, 'cyan')}: {len(items)}")
                for item in items:
                    print(f"{indent()}    {item['name']} -> {colorize(item['path'], 'dim')}")
            else:
                names = ", ".join(item["name"] for item in items)
                print(f"{indent()}  {colorize(label, 'cyan')}: {len(items)} ({names})")


def print_inventory(report, components, include_paths=False, details=False):
    """Render the human-readable component inventory."""
    if details or include_paths:
        print_inventory_summary(report, components)
        print_inventory_details(report, components, include_paths=include_paths)
    else:
        print_inventory_summary(report, components)


def cmd_inventory(args):
    """inventory: report manifest plugins, versions, and component membership."""
    resolve_colors(args.color)
    manifest = load_manifest()
    plugins = select_plugins(manifest.get("plugins", []), args.plugin)
    components = component_selection(args.component)
    report = build_inventory(manifest, plugins, components, include_paths=args.paths)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_inventory(report, components, include_paths=args.paths, details=args.details)
    return 0


def confirm(question, default):
    """Prompt y/n on a TTY. Callers must only invoke this when interactive.

    The prompt line is fully erased after answering (on a TTY); the choice is
    surfaced later in the run header, not left on screen here.
    """
    suffix = "[Y/n]" if default else "[y/N]"
    prompt = f"{colorize(question, 'cyan')} {colorize(suffix, 'dim')} "
    reply = input(prompt).strip().lower()
    erase_tty_rows(prompt_rows(prompt))
    if not reply:
        return default
    return reply in ("y", "yes")


def confirm_action(question):
    """Per-item action prompt; returns 'yes', 'no', 'all', or 'none'.

    'all'/'none' let the caller apply the same answer to every remaining item
    without prompting again. Only call when interactive. Self-erases on a TTY.
    """
    replies = {"": "yes", "y": "yes", "yes": "yes", "n": "no", "no": "no",
               "a": "all", "all": "all", "q": "none", "none": "none"}
    prompt = f"{colorize(question, 'cyan')} {colorize('[Y/n/a/q]', 'dim')} "
    printed = 0
    while True:
        reply = input(prompt).strip().lower()
        printed += prompt_rows(prompt)
        if reply in replies:
            break
        error = colorize("error: answer y (yes), n (no), a (yes to all), or q (no to all)", "red")
        print(error)
        printed += prompt_rows(error)
    erase_tty_rows(printed)
    return replies[reply]


def choose(question, options, default=None, multi=False):
    """Prompt the user to pick one of options. Only call when interactive.

    If default (an option value) is given, it is marked in the list and chosen
    when the user enters an empty line. With multi=True the user may pick several
    (comma/space-separated numbers or names) and a list is returned. The whole
    prompt block is erased after answering (on a TTY); the choice is surfaced
    later in the run header.
    """
    printed = 0  # lines emitted, so we can erase them after the choice

    def emit(line=""):
        nonlocal printed
        print(line)
        printed += 1

    def resolve(token):
        # Map a single token (1-based index or name) to an option, or None.
        if token.isdigit() and 1 <= int(token) <= len(options):
            return options[int(token) - 1]
        return token if token in options else None

    emit(colorize(question, "cyan"))
    for i, option in enumerate(options, 1):
        marker = colorize(" (default)", "dim") if option == default else ""
        emit(f"  {colorize(str(i), 'cyan')}) {option}{marker}")
    hint = colorize(f"[1-{len(options)}]" + (", comma-separated" if multi else ""), "dim")
    prompt = f"{colorize('Choose', 'cyan')} {hint}: "
    while True:
        reply = input(prompt).strip()
        printed += prompt_rows(prompt)
        if not reply and default is not None:
            choice = [default] if multi else default
        elif multi:
            tokens = [t for t in reply.replace(",", " ").split() if t]
            resolved = [resolve(t) for t in tokens]
            if not tokens or None in resolved:
                emit(colorize(f"error: choose number(s) 1-{len(options)} or name(s)", "red"))
                continue
            # De-dupe while preserving order.
            choice = list(dict.fromkeys(resolved))
        elif resolve(reply) is not None:
            choice = resolve(reply)
        else:
            emit(colorize(f"error: choose a number 1-{len(options)} or a name", "red"))
            continue
        break
    # Move to the start of the question line and clear to end of screen,
    # fully erasing the prompt block.
    erase_tty_rows(printed)
    return choice


def install_one(src, dest, dry_run, force, symlink, quiet=False):
    """Copy or symlink src to dest. Returns 'installed' or 'skipped'."""
    # Safety: never let dest operations touch the source itself (e.g. when dest
    # is an existing symlink pointing back into the source tree).
    if dest.is_symlink():
        link_target = (dest.parent / os.readlink(dest)).resolve()
        same = link_target == src.resolve()
    else:
        same = dest.exists() and dest.resolve() == src.resolve()
    if same and not force:
        if not quiet:
            print(f"skip (already linked/identical): {dest}")
        return "skipped"

    exists = dest.exists() or dest.is_symlink()
    if exists and not force:
        if not quiet:
            print(f"skip (exists): {dest}  [use --force to overwrite]")
        return "skipped"
    if dry_run:
        if not quiet:
            print(f"{'would link' if symlink else 'would copy'}: {src}  ->  {dest}")
        return "installed"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if exists:
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        else:
            shutil.rmtree(dest)
    if symlink:
        # Relative target so the link survives the repo being moved.
        dest.symlink_to(os.path.relpath(src, dest.parent))
        if not quiet:
            print(f"linked: {dest}  ->  {src}")
    elif src.is_dir():
        shutil.copytree(src, dest)
        if not quiet:
            print(f"installed: {dest}")
    else:
        shutil.copy2(src, dest)
        if not quiet:
            print(f"installed: {dest}")
    return "installed"


def remove_one(dest, dry_run):
    """Delete an installed dest (symlink, file, or dir tree)."""
    if dry_run:
        return
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    else:
        shutil.rmtree(dest)


# ---- plugin orchestration ---------------------------------------------------
#
# On the marketplace channel, install/uninstall additionally drive the tool's
# own CLI (claude / traecli) to add the marketplace and install/remove plugins —
# the parts no plugin format delivers as files. These helpers derive the
# marketplace identity from the manifest, shell out without a shell, and parse
# the tools' (brittle) text output defensively so a parse miss never deletes.


def derive_marketplace_source(manifest):
    """Return the ``owner/repo`` marketplace source derived from the manifest.

    Prefers the ``repository`` URL (strips a host prefix and a trailing ``.git``);
    falls back to ``<owner>/<name>``. Fails loudly if neither yields ``owner/repo``.
    """
    repo = manifest.get("repository", "")
    if repo:
        path = repo.split("github.com/", 1)[-1].rstrip("/")
        if path.endswith(".git"):
            path = path[: -len(".git")]
        if path.count("/") == 1 and all(path.split("/")):
            return path
    owner = owner_string(manifest)
    name = manifest.get("name", "")
    if owner and name:
        return f"{owner}/{name}"
    sys.exit(f"error: cannot derive marketplace source from {manifest_label()} (need 'repository' or 'owner' + 'name')")


def marketplace_name(manifest):
    return manifest["name"]


def plugin_ref(plugin_name, mkt_name):
    return f"{plugin_name}@{mkt_name}"


def agentry_plugin_names(manifest):
    return {p["name"] for p in manifest.get("plugins", [])}


def resolve_tool_binary(tool):
    """Return the tool's CLI binary path on PATH, or None if not found."""
    return shutil.which(TOOL_BINARIES[tool])


def run_tool_command(binary, cmd_args, dry_run, capture=False):
    """Run ``binary cmd_args`` without a shell. Return (ok, stdout, stderr).

    On --dry-run, skip execution and return ok=True without output; the caller
    prints an aligned "would …" preview row instead of the raw command. Never
    raises on a non-zero exit or a missing binary: the caller turns ok=False into
    a finding so a CLI failure cannot abort the file-handling step.
    """
    if dry_run:
        return True, "", ""
    argv = [binary, *cmd_args]
    try:
        proc = subprocess.run(argv, capture_output=capture, text=True, check=False)
    except (FileNotFoundError, OSError) as exc:
        return False, "", str(exc)
    return proc.returncode == 0, proc.stdout or "", proc.stderr or ""


def empty_plugin_state(binary=None):
    """Return the default read-only snapshot for tool plugin state."""
    return {"binary": binary, "markets": set(), "installed": {}, "mkt_ok": False, "list_ok": False}


def _parse_list_names(text):
    """Yield top-level entry names from a ``plugin list``/``marketplace list`` dump.

    Entry lines are non-indented and begin with a status glyph (✓/✗); detail lines
    are indented and skipped. Defensive: unexpected lines are ignored so a format
    drift degrades to "not present" rather than raising.
    """
    names = set()
    for raw in text.splitlines():
        if not raw.strip() or raw[:1].isspace():
            continue  # blank or indented detail line
        stripped = raw.strip()
        first = stripped.split(None, 1)[0]
        if first in ("✓", "✗"):
            rest = stripped[len(first):].strip()
            if rest:
                names.add(rest.split()[0])
    return names


def _parse_plugin_origins(text):
    """Yield ``(name, origin)`` pairs from a ``plugin list`` dump.

    Plugin entries are introduced by a non-indented line starting with
    ``✓``/``✗`` followed by the plugin name. Immediately after (on any
    non-empty subsequent line starting with ``From``) is the origin:
    ``From local: <path>`` / ``From tar: <url>`` /
    ``From marketplace: <marketplace name> …``. ``From`` is followed by
    the origin token (up to the first colon); the token is lowered and
    returned as the origin. A plugin with no ``From`` line is skipped
    (callers treat absence as "not installed").
    """
    current = None
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        first = stripped.split(None, 1)[0]
        if first in ("✓", "✗"):
            rest = stripped[len(first):].strip()
            current = rest.split()[0] if rest else None
            continue
        if stripped.lower().startswith("from ") and current is not None:
            rest = stripped.split(None, 1)[1]
            origin_value = rest.split(":", 1)[0].strip().lower()
            if origin_value in ("local", "tar", "marketplace"):
                origin = origin_value
            else:
                origin = "marketplace"
            yield current, origin
            current = None


def parse_installed_plugins(text):
    """Parse ``plugin list`` output into ``{name: origin_type}``.

    ``origin_type`` is one of ``local`` / ``marketplace`` / ``tar``.
    Callers can still test membership with ``name in installed`` (dict
    key lookup).
    """
    return dict(_parse_plugin_origins(text))


def parse_marketplaces(text):
    """Parse ``marketplace list`` output into a set of marketplace names."""
    return _parse_list_names(text)


def build_install_args(tool, ref, assume_yes):
    """Per-tool ``plugin install`` argv tail. trae takes --yes; claude --scope user.

    claude's install (unlike its uninstall/remove — see removal_confirm_flags) has
    no --yes and does not prompt for confirmation, so none is added; it installs at
    --scope user, matching the marketplace channel's user scope.
    """
    args = ["plugin", "install", ref]
    if tool == "trae" and assume_yes:
        args.append("--yes")
    elif tool == "claude":
        args += ["--scope", "user"]
    return args


def removal_confirm_flags(tool):
    """Non-interactive confirm flags for ``plugin uninstall`` / ``marketplace remove``.

    Once orchestrate_confirm has approved a removal, claude's uninstall/remove
    still abort on a non-TTY stdin/stdout unless ``--yes`` is passed, so add it.
    trae's removal commands take no such flag (they do not prompt), so add none.
    """
    return ["--yes"] if tool == "claude" else []


def query_marketplaces(binary):
    """Return (ok, names). ok is False when the CLI call failed (vs. genuinely empty)."""
    ok, out, _ = run_tool_command(binary, ["plugin", "marketplace", "list"], dry_run=False, capture=True)
    return ok, (parse_marketplaces(out) if ok else set())


def query_installed_plugins(binary):
    """Return (ok, names). ok is False when the CLI call failed (vs. genuinely empty)."""
    ok, out, _ = run_tool_command(binary, ["plugin", "list"], dry_run=False, capture=True)
    return ok, (parse_installed_plugins(out) if ok else set())


def orchestrate_confirm(question, args, interactive, bulk=None):
    """Confirm a mutating CLI action, honoring --yes, --dry-run, and bulk.

    Returns True to proceed, and (as a side effect) may mutate ``bulk`` in the
    caller's scope via a shared mutable container — so callers pass
    ``bulk={'value': None}`` rather than a plain bool, and after the user
    types ``a``/``all`` or ``q``/``none`` every subsequent call short-circuits
    on that stored answer. This lets a single ``a``/``q`` answer cover every
    plugin (and the marketplace) in a phase, mirroring the file-loop's bulk
    semantics. ``--yes`` and ``--dry-run`` always short-circuit immediately.
    """
    if args.yes or args.force or args.dry_run:
        return True
    if bulk is not None and bulk["value"] is not None:
        return bulk["value"]
    if not interactive:
        return False
    # Interactive: use confirm_action so the user can pick "all" / "none" and
    # have it stick for the rest of the phase.
    answer = confirm_action(question)
    if answer in ("all", "none"):
        if bulk is not None:
            bulk["value"] = answer == "all"
        return answer == "all"
    return answer == "yes"


# Plugin orchestration is split into two phases, mirroring the file flow:
#
#   Phase 1 (report_plugin_state)   — query and print current-state rows under
#                                     the "Plugins" header. No prompts, no CLI
#                                     mutations. Runs for every channel and every
#                                     command (install/uninstall/status) so the
#                                     report always describes the world as it
#                                     stands before any action.
#
#   Phase 2 (act_on_plugins_install / act_on_plugins_uninstall) — prompt and
#                                     execute, returning (unresolved_count,
#                                     action_rows). ``action_rows`` are printed
#                                     later under the "Changes" section; the
#                                     caller is responsible for the section
#                                     header. Dry-run emits "would …" labels
#                                     instead of "installed"/"removed".
#
# This separation keeps the report consistent: every run shows state first,
# then (optionally) what changed, then a summary. It also avoids dangling
# headers above slow CLI queries and makes dry-run previews use the same
# aligned row format as real actions.

def report_plugin_state(args, manifest, plugins, label_width=None):
    """Phase 1: print a "Plugins" section describing current state (read-only).

    Used by install, uninstall, and status. ``label_width`` is the shared
    tag-column width; when provided, plugin rows line up with the file rows
    rendered elsewhere in the same report. Returns a snapshot ``dict`` with
    ``binary`` (or ``None``), ``markets`` (set), ``installed`` (set), and
    their two ``*_ok`` flags — the same values the action phase needs, so a
    second round-trip to the tool CLI is avoided. Query results are gathered
    before the cyan ``Plugins`` header prints, so a slow CLI call never
    leaves a dangling header.
    """
    mkt = marketplace_name(manifest)
    binary = resolve_tool_binary(args.tool)
    snapshot = empty_plugin_state(binary)
    if binary is None:
        plugin_section_header()
        print(plugin_row("unknown", f"marketplace {mkt}", width=label_width, note=f"{TOOL_BINARIES[args.tool]} not on PATH"))
        for plugin in plugins:
            print(plugin_row("unknown", plugin["name"], width=label_width, note="cannot query"))
        return snapshot
    mkt_ok, markets = query_marketplaces(binary)
    list_ok, installed = query_installed_plugins(binary)
    snapshot.update({"markets": markets, "installed": installed, "mkt_ok": mkt_ok, "list_ok": list_ok})
    plugin_section_header()
    if not mkt_ok:
        print(plugin_row("unknown", f"marketplace {mkt}", width=label_width, note="query failed"))
    else:
        print(plugin_row("added" if mkt in markets else "missing", f"marketplace {mkt}", width=label_width, note="marketplace" if mkt in markets else None))
    for plugin in plugins:
        name = plugin["name"]
        if not list_ok:
            print(plugin_row("unknown", name, width=label_width, note="query failed"))
        elif name in installed:
            print(plugin_row("installed", name, width=label_width, note=installed.get(name) or "unknown"))
        else:
            print(plugin_row("missing", name, width=label_width, note="not installed"))
    return snapshot


def act_on_plugins_install(args, manifest, plugins, interactive, action_width, state=None, bulk=None):
    """Phase 2 (install): prompt and execute marketplace + plugin installs.

    Returns ``(unresolved_count, action_rows)``. ``action_rows`` are pre-formatted
    aligned lines suitable for the "Changes" section (no header is printed here).
    ``action_width`` is the shared tag-column width so rows line up with file
    actions in the same section. Never exits on CLI error — a failed command
    becomes a "failed" row and increments the unresolved count (the caller folds
    it into the run's final verdict). ``state`` is the ``report_plugin_state``
    snapshot; when provided, it replaces the two list queries (saving one
    tool CLI round-trip each). ``bulk`` lets the caller carry over a file-loop
    "all"/"none" decision (``True``/``False``) so the user isn't re-prompted for
    every plugin after committing to all files.
    """
    if state is not None:
        binary = state["binary"]
        present = state["markets"]
        installed = state["installed"]
    else:
        binary = resolve_tool_binary(args.tool)
        if binary is None:
            return len(plugins) + 1, []
        _, present = query_marketplaces(binary)
        _, installed = query_installed_plugins(binary)
    if binary is None:
        return len(plugins) + 1, []
    source = derive_marketplace_source(manifest)
    mkt = marketplace_name(manifest)
    unresolved = 0
    rows = []

    # Marketplace: add if not present.
    ready = mkt in present
    if not ready:
        if orchestrate_confirm(f"{indent()}add marketplace '{mkt}' ({source})?", args, interactive, bulk=bulk):
            ok, _, err = run_tool_command(binary, ["plugin", "marketplace", "add", source], args.dry_run, capture=True)
            if ok:
                ready = True
                label = "would add" if args.dry_run else "added"
                rows.append(plugin_row(label, f"marketplace {mkt}", action_width, source if not args.dry_run else None))
            else:
                unresolved += 1
                rows.append(plugin_row("failed", f"marketplace {mkt}", action_width, err.strip() or "unknown error"))
        else:
            unresolved += 1
            rows.append(plugin_row("skipped", f"marketplace {mkt}", action_width, "declined"))
            ready = False  # block plugin installs below; same semantics as failure

    if not ready and mkt not in present:
        # Marketplace is genuinely not ready — surface one line per plugin so
        # the caller's "acted" count reflects the intended scope.
        for plugin in plugins:
            unresolved += 1
            rows.append(plugin_row("skipped", plugin["name"], action_width, "marketplace not ready"))
        return unresolved, rows

    # Plugin installs.
    for plugin in plugins:
        name = plugin["name"]
        # --force acts on every plugin (mirrors the file step), reinstalling an
        # already-installed plugin. It does not bypass the confirm below — that
        # gate is governed only by --yes.
        if name in installed and not args.force:
            continue  # already installed: no state change, no Changes row
        ref = plugin_ref(name, mkt)
        if not orchestrate_confirm(f"{indent()}install plugin '{ref}'?", args, interactive, bulk=bulk):
            unresolved += 1
            rows.append(plugin_row("skipped", name, action_width, "declined"))
            continue
        # Confirm already passed, so tell trae's install not to prompt again.
        ok, _, err = run_tool_command(binary, build_install_args(args.tool, ref, assume_yes=True), args.dry_run, capture=True)
        if ok:
            label = "would install" if args.dry_run else "installed"
            rows.append(plugin_row(label, name, action_width))
        else:
            unresolved += 1
            rows.append(plugin_row("failed", name, action_width, err.strip() or "unknown error"))
    return unresolved, rows


def act_on_plugins_uninstall(args, manifest, plugins, interactive, action_width, state=None, bulk=None):
    """Phase 2 (uninstall): prompt and execute plugin + marketplace removal.

    Same return contract as ``act_on_plugins_install``:
    ``(unresolved_count, action_rows)``. ``state`` is the
    ``report_plugin_state`` snapshot; when provided, the "what remains"
    check uses it instead of re-querying, and the post-action re-query is
    skipped entirely (both the `installed - removed` is correct since only
    this function's removals ran in between). ``bulk`` carries over a
    file-loop "all"/"none" decision so the user isn't re-prompted for
    every plugin.
    """
    if state is not None:
        binary = state["binary"]
        list_ok = state["list_ok"]
        installed = set(state["installed"])
    else:
        binary = resolve_tool_binary(args.tool)
        if binary is None:
            return len(plugins) + 1, []
        list_ok, installed = query_installed_plugins(binary)
    if binary is None:
        return len(plugins) + 1, []
    mkt = marketplace_name(manifest)
    unresolved = 0
    rows = []

    removed = set()
    for plugin in plugins:
        name = plugin["name"]
        if list_ok and name not in installed:
            continue  # absent: no state change, no Changes row
        if not orchestrate_confirm(f"{indent()}uninstall plugin '{name}'?", args, interactive, bulk=bulk):
            unresolved += 1
            rows.append(plugin_row("skipped", name, action_width, "declined"))
            continue
        ok, _, err = run_tool_command(
            binary,
            ["plugin", "uninstall", name] + removal_confirm_flags(args.tool),
            args.dry_run,
            capture=True,
        )
        if ok:
            removed.add(name)
            label = "would remove" if args.dry_run else "removed"
            rows.append(plugin_row(label, name, action_width))
        else:
            unresolved += 1
            rows.append(plugin_row("failed", name, action_width, err.strip() or "unknown error"))

    # Marketplace removal: only when no plugin from this catalog remains.
    remaining_ok, remaining = list_ok, (installed - removed) & agentry_plugin_names(manifest)
    if not remaining_ok:
        unresolved += 1
        rows.append(plugin_row("kept", f"marketplace {mkt}", action_width, "could not verify remaining plugins"))
    elif remaining:
        rows.append(plugin_row("kept", f"marketplace {mkt}", action_width,
                               f"{len(remaining)} {BRAND} plugin(s) still installed"))
    elif orchestrate_confirm(f"{indent()}no {BRAND} plugins remain; remove marketplace '{mkt}'?", args, interactive, bulk=bulk):
        ok, _, err = run_tool_command(
            binary,
            ["plugin", "marketplace", "remove", mkt] + removal_confirm_flags(args.tool),
            args.dry_run,
            capture=True,
        )
        if ok:
            label = "would remove" if args.dry_run else "removed"
            rows.append(plugin_row(label, f"marketplace {mkt}", action_width, f"no {BRAND} plugins remain"))
        else:
            unresolved += 1
            rows.append(plugin_row("failed", f"marketplace {mkt}", action_width, err.strip() or "unknown error"))
    else:
        unresolved += 1
        rows.append(plugin_row("kept", f"marketplace {mkt}", action_width, "declined"))
    return unresolved, rows


def resolve_marketplace(args):
    """Decide the delivery channel from the command line. Returns True for marketplace.

    Two channels deliver a plugin's skills/subagents/commands: the marketplace
    (the tool's own plugin system) and the checkout (copied from this repo).
    Rules are copied in either. ``--source`` picks one explicitly; otherwise
    naming ``--component`` implies checkout (those files come from the checkout),
    and failing that a ``--global`` run uses the marketplace while a project-scope
    run uses the checkout. Marketplace plugins are inherently user-scoped, so
    that channel forces ``--global`` (its rules follow to the user dirs).
    ``--source marketplace`` therefore cannot be combined with an explicit
    ``--component``. Decided before any interactive prompt, so the component
    prompt can be skipped on the marketplace channel.
    """
    if args.source == "marketplace" and args.component is not None:
        sys.exit(
            "error: --source marketplace installs plugins via the tool CLI; it cannot copy "
            "--component files. Use '--source checkout' (or drop --source) to copy components."
        )
    if args.source is not None:
        marketplace = args.source == "marketplace"
    else:
        marketplace = args.component is None and args.global_scope
    if marketplace:
        args.global_scope = True  # marketplace plugins are user-scoped; rules follow
    return marketplace


def resolve_selection(args, all_plugins, marketplace, removing=False):
    """Resolve tool/plugin/component (and symlink) via prompts when interactive.

    Shared by install/status/uninstall. ``removing`` and ``args.status`` tailor
    which prompts apply: symlink only affects writes, so it is skipped for both.
    On the marketplace channel components do not apply (the tool delivers them),
    so that prompt is skipped and only rules are copied. Returns the components set.
    """
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    args._interactive = interactive

    if args.tool is None:
        if not interactive:
            sys.exit("error: --tool is required when not running interactively")
        args.tool = choose("Which tool?", sorted(TOOL_TARGETS))

    writes = not getattr(args, "status", False) and not removing
    default_components = set(COMPONENTS) if not marketplace else {"rules"}

    # On the marketplace channel, components do not apply to a *write* (the tool
    # delivers skills/agents/commands; only rules are copied), so never prompt
    # for them — pin to rules and exclude them from the "use defaults?" shortcut below.
    # status is read-only: components only pick which file types it reports, so
    # it stays promptable on either channel.
    component_unset = args.component is None and (not marketplace or getattr(args, "status", False))

    # Offer a single shortcut up front: if any selection is still unset and we'd
    # otherwise prompt for each, ask once whether to just use the defaults.
    # Accepting is equivalent to --defaults.
    unset = args.plugin is None or component_unset or (writes and not args.symlink)
    if interactive and not args.defaults and unset:
        comps = ", ".join(sorted(args.component)) if args.component else ", ".join(sorted(default_components))
        defaults_desc = [f"plugin: {plugin_selection_label(args.plugin)}", f"components: {comps}"]
        if writes:
            defaults_desc.append(f"mode: {'symlink' if args.symlink else 'copy'}")
        args.defaults = confirm(f"Use defaults ({' · '.join(defaults_desc)})?", default=True)

    # Selection prompts fire interactively unless --defaults uses each default.
    ask_optional = interactive and not args.defaults

    if args.plugin is None and ask_optional:
        picked = choose("Which plugins?", ["all"] + [p["name"] for p in all_plugins], default="all", multi=True)
        if "all" not in picked:
            args.plugin = picked

    if component_unset and ask_optional:
        args.component = choose(
            "Which components?",
            ["rules", "skills", "agents", "commands", "all"],
            default="all" if default_components == set(COMPONENTS) else "rules",
            multi=True,
        )

    if writes and not args.symlink and ask_optional:
        args.symlink = confirm("Symlink instead of copy?", default=False)

    if args.component and "all" in args.component:
        return set(COMPONENTS)
    return set(args.component) if args.component else default_components


def file_action_labels(action, args):
    """Return the action labels this run may emit for file changes."""
    if action == "install":
        if args.dry_run:
            return ["would install", "would update"]
        return ["linked"] if args.symlink else ["installed", "updated"]
    return ["would remove"] if args.dry_run else ["removed"]


def report_label_width(action, args):
    """Shared tag-column width for plugin/file state and action rows."""
    all_labels = (
        set(file_action_labels(action, args)) |
        FILE_REPORT_TAGS |
        PLUGIN_REPORT_TAGS |
        PLUGIN_INSTALL_ACTION_TAGS |
        PLUGIN_REMOVE_ACTION_TAGS
    )
    return max(len(t) for t in all_labels)


def run_scope(args):
    """Return (base_path, scope_label) for the selected project/global scope."""
    if args.global_scope:
        return Path.home(), "global"
    return args.project_dir.resolve(), "project"


def delivery_channel(args, marketplace):
    """Return the write channel label, or None for read-only status."""
    if getattr(args, "status", False):
        return None
    return "marketplace" if marketplace else "checkout"


def should_report_plugins(args, marketplace):
    """Plugin state is useful only for status or marketplace-channel writes."""
    return getattr(args, "status", False) or marketplace


def selected_file_plan(args, base, components):
    """Build classified file-copy plan rows for the selected plugin/components."""
    base = base.resolve()
    plugins = select_plugins(load_plugins(), args.plugin)
    jobs = plan_copies(plugins, components)
    if not jobs:
        return []

    targets = TOOL_TARGETS[args.tool]
    plan = []
    for component, src, rel_dest in jobs:
        if not src.exists():
            sys.exit(f"error: source missing: {src}")
        dest_base = base / targets[component]
        dest = confined_leaf_path(dest_base, rel_dest, f"{component} destination")
        rel = dest.relative_to(base)
        state = classify_state(src, dest)
        plan.append((component, src, dest, rel, state))
    return plan


def print_run_header(args, base, scope, components, action, channel=None):
    """Print the common title/detail block for install/status/uninstall."""
    title = ("📦 " if _USE_EMOJI else "") + f"{BRAND} — {args.tool}, {scope} scope ({base})"
    print(colorize(title, "cyan"))
    detail = [f"plugin: {plugin_selection_label(args.plugin)}", f"components: {', '.join(sorted(components))}"]
    if channel is not None:
        detail.append(f"source: {channel}")
    if action == "install":
        detail.append(f"mode: {'symlink' if args.symlink else 'copy'}")
    print(colorize(indent() + " · ".join(detail), "dim"))
    print()


def print_no_files_message(plan):
    """Tell the user when a selection has no file-delivered components."""
    if not plan:
        print(colorize(indent() + "No files for the given selection.", "dim"))


def print_header(args, base, components, action, section=None, channel=None):
    """Print the run header, optional plugin-state section, and plan file jobs.

    ``section`` is an optional callback that renders the plugin/marketplace
    state block (the "Plugins" section) after the title line. It is called
    with a single ``label_width`` argument — the shared tag-column width used
    for every report row in the run, so plugin rows line up with file rows.
    The header and section are printed first so the section still renders
    when there are no file jobs (e.g. a rules-less plugin on the marketplace
    channel, whose work is the section). ``channel`` is the resolved delivery
    channel ("marketplace"/"checkout"); omitted for read-only status.

    Returns ``(plan, label_width)``. ``plan`` is the list of file rows as
    ``(component, src, dest, rel, state)``; ``label_width`` is the
    shared tag-column width to use when rendering grouped-report rows and
    action rows later.
    """
    _, scope = run_scope(args)
    print_run_header(args, base, scope, components, action, channel)
    label_width = report_label_width(action, args)

    if section is not None:
        section(label_width)
        print()

    plan = selected_file_plan(args, base, components)
    print_no_files_message(plan)
    return plan, label_width


def print_changes(acted, first_prompt):
    """Print the common Changes section and preserve legacy blank-line behavior."""
    if acted:
        if first_prompt:
            print()
        print(colorize(f"{indent()}Changes", "cyan"))
        for line in acted:
            print(line)
        print()
    elif first_prompt:
        print()


def plugin_action_tag(row, label_width):
    """Extract the padded action tag from a formatted plugin action row."""
    content = _strip_color(row).lstrip()
    if not content:
        return ""
    return content[:label_width].strip()


def merge_plugin_install_counts(counts, plugin_action_rows, label_width):
    """Fold plugin install rows into the shared install summary counters."""
    for row in plugin_action_rows:
        if plugin_action_tag(row, label_width) in PLUGIN_INSTALL_ACTION_TAGS:
            counts["installed"] += 1


def merge_plugin_remove_counts(counts, plugin_action_rows, label_width):
    """Fold plugin removal rows into the shared uninstall summary counters."""
    for row in plugin_action_rows:
        if plugin_action_tag(row, label_width) in PLUGIN_REMOVE_ACTION_TAGS:
            counts["removed"] += 1


def suppress_missing_binary_dry_run_unresolved(args, plugin_state, unresolved):
    """Do not count unavailable tool-CLI state as skipped during dry-run previews."""
    if args.dry_run and plugin_state is not None and plugin_state.get("binary") is None:
        return 0
    return unresolved


def cmd_install(args):
    """install / status: classify, report, then write (unless --status)."""
    resolve_colors(args.color)
    all_plugins = load_plugins()
    marketplace = resolve_marketplace(args)
    components = resolve_selection(args, all_plugins, marketplace)
    interactive = args._interactive

    # Two-phase plugin section: state (rendered inside print_header as the
    # "Plugins" report block), then action rows merged into the shared
    # "Changes" section after the file action loop. On the checkout channel,
    # no plugin actions run (skills/agents/commands come from the checkout), so the
    # Plugins section is also skipped — it is pure tool CLI status and only
    # adds latency on a file-only run.
    manifest = load_manifest()
    selected = select_plugins(all_plugins, args.plugin)
    plugin_unresolved = 0
    plugin_state = {"snapshot": None}

    def section(lw):
        plugin_state["snapshot"] = report_plugin_state(args, manifest, selected, label_width=lw)

    base, _ = run_scope(args)
    channel = delivery_channel(args, marketplace)
    # The Plugins section only runs for commands that actually depend on
    # plugin/marketplace state: status (always reports it), install on the
    # marketplace channel, and uninstall on the marketplace channel. A
    # file-only checkout run otherwise has no tool CLI to query and skipping
    # it saves ~2s.
    if should_report_plugins(args, marketplace):
        section_cb = section
    else:
        section_cb = None
    plan, label_width = print_header(
        args, base, components, "status" if args.status else "install", section_cb, channel)
    if plan is None:
        return 0

    # Guard a missing tool binary *after* print_header so the report (the
    # useful part of a dry-run or status run) still prints; the hard error
    # only blocks CLI-driven writes. On --dry-run we keep going even if the
    # binary isn't installed so the user can preview what the tool would do
    # once it is.
    if marketplace and not args.status and not args.dry_run:
        binary = resolve_tool_binary(args.tool)
        if binary is None:
            sys.exit(
                f"error: '{TOOL_BINARIES[args.tool]}' not found on PATH. Install it, or pass "
                "'--source checkout' to copy components from this checkout instead."
            )
    print_grouped_report(plan, label_width)

    counts = {"current": 0, "installed": 0, "updated": 0, "skipped": 0}
    acted = []
    first_prompt = True
    bulk = {"value": None}
    for component, src, dest, rel, state in plan:
        action_needed = needs_action(state)
        if not action_needed and not args.force:
            counts["current"] += 1
            continue
        if args.status:
            continue

        verb = action_verb(state)
        if args.force or args.yes:
            act = True
        elif bulk["value"] is not None:
            act = bulk["value"]
        elif interactive and not args.dry_run:
            if first_prompt:
                print()
                first_prompt = False
            answer = confirm_action(f"{indent()}{verb} {component} '{rel}'?")
            if answer in ("all", "none"):
                bulk["value"] = answer == "all"
                act = bulk["value"]
            else:
                act = answer == "yes"
        else:
            act = args.dry_run

        if not act:
            counts["skipped"] += 1
            continue
        install_one(src, dest, args.dry_run, force=True, symlink=args.symlink, quiet=True)
        if args.dry_run:
            label = f"would {verb}"
        elif args.symlink:
            label = "linked"
        else:
            label = "installed" if state == "missing" else "updated"
        acted.append(f"{indent()}{colorize(f'{label:<{label_width}}', 'green')} {rel}")
        counts["installed" if state == "missing" else "updated"] += 1

    # Phase 2: plugin actions after file actions. Rules ship via files
    # (above), skills/agents/commands via plugins — so the Changes section lists
    # file work first (deterministic from the plan), then plugin work
    # (in plugin selection order). The missing-binary case is guarded above.
    if marketplace and not args.status:
        plugin_unresolved, plugin_action_rows = act_on_plugins_install(
            args, manifest, selected, interactive, label_width,
            state=plugin_state["snapshot"],
            bulk=bulk,
        )
        # On --dry-run, a missing tool binary (reported in the state phase as
        # "unknown") is unavailable info, not a declined action.
        plugin_unresolved = suppress_missing_binary_dry_run_unresolved(
            args, plugin_state["snapshot"], plugin_unresolved)
        acted.extend(plugin_action_rows)
        merge_plugin_install_counts(counts, plugin_action_rows, label_width)

    print_changes(acted, first_prompt)

    linked = 0 if args.force else sum(1 for *_, state in plan if state == "linked")
    current_label = f"{counts['current']} synced"
    if linked:
        current_label += colorize(f" ({linked} linked)", "dim")
    if args.status:
        drift = sum(1 for *_, state in plan if needs_action(state))
        parts = [colorize(current_label, "green")]
        if drift:
            stale = any(state in ("copied-stale", "stale-link") for *_, state in plan)
            parts.append(colorize(f"{drift} need attention", "red" if stale else "yellow"))
    else:
        iv = "would install" if args.dry_run else "installed"
        uv = "would update" if args.dry_run else "updated"
        parts = [
            colorize(current_label, "green"),
            colorize(f"{counts['installed']} {iv}", "green"),
            colorize(f"{counts['updated']} {uv}", "green"),
        ]
        if counts["skipped"] or plugin_unresolved:
            parts.append(colorize(f"{counts['skipped'] + plugin_unresolved} skipped", "dim"))
    unresolved = (args.status and any(needs_action(s) for *_, s in plan)) or \
        (not args.status and (counts["skipped"] > 0 or plugin_unresolved > 0))
    mark = ("⚠️  " if unresolved else "✅ ") if _USE_EMOJI else ""
    print(mark + colorize("Summary: ", "cyan") + ", ".join(parts))
    if should_report_plugins(args, marketplace):
        print_marketplace_refresh_hint(args, manifest, plugin_state["snapshot"])

    if args.status and any(needs_action(state) for *_, state in plan):
        return 1
    return 0


def cmd_uninstall(args):
    """uninstall: remove components this tool installed (owned copies/links)."""
    resolve_colors(args.color)
    all_plugins = load_plugins()
    marketplace = resolve_marketplace(args)
    components = resolve_selection(args, all_plugins, marketplace, removing=True)
    interactive = args._interactive
    manifest = load_manifest()
    selected = select_plugins(all_plugins, args.plugin)
    plugin_unresolved = 0

    # Phase 1: capture the query snapshot for the action phase to reuse,
    # and print the Plugins section. On a file-only checkout run, skip the
    # section entirely — no tool CLI to query, so no plugin state to report.
    plugin_state = {"snapshot": None}

    def section(lw):
        plugin_state["snapshot"] = report_plugin_state(args, manifest, selected, label_width=lw)

    base, _ = run_scope(args)
    channel = delivery_channel(args, marketplace)
    section_cb = section if marketplace else None
    plan, label_width = print_header(args, base, components, "uninstall", section_cb, channel)
    if plan is None:
        return 0

    if marketplace and not args.dry_run:
        binary = resolve_tool_binary(args.tool)
        if binary is None:
            sys.exit(
                f"error: '{TOOL_BINARIES[args.tool]}' not found on PATH. Install it, or pass "
                "'--source checkout' to manage only checkout-copied files."
            )
    print_grouped_report(plan, label_width)

    counts = {"absent": 0, "removed": 0, "skipped": 0}
    acted = []
    first_prompt = True
    bulk = {"value": None}
    for component, src, dest, rel, state in plan:
        if state == "missing":
            counts["absent"] += 1
            continue
        owned = state in ("linked", "copied-current")
        if not owned and not args.force:
            kept_tag = colorize(f"{'kept':<{label_width}}", "yellow")
            acted.append(
                f"{indent()}{kept_tag} {rel}" + colorize("  (drifted; use --force to remove)", "dim")
            )
            counts["skipped"] += 1
            continue

        if args.yes or args.force:
            act = True
        elif bulk["value"] is not None:
            act = bulk["value"]
        elif interactive and not args.dry_run:
            if first_prompt:
                print()
                first_prompt = False
            answer = confirm_action(f"{indent()}remove {component} '{rel}'?")
            if answer in ("all", "none"):
                bulk["value"] = answer == "all"
                act = bulk["value"]
            else:
                act = answer == "yes"
        else:
            act = args.dry_run

        if not act:
            counts["skipped"] += 1
            continue
        remove_one(dest, args.dry_run)
        label = "would remove" if args.dry_run else "removed"
        acted.append(f"{indent()}{colorize(f'{label:<{label_width}}', 'green')} {rel}")
        counts["removed"] += 1

    if marketplace:
        plugin_unresolved, plugin_action_rows = act_on_plugins_uninstall(
            args, manifest, selected, interactive, label_width,
            state=plugin_state["snapshot"],
            bulk=bulk,
        )
        # On --dry-run, a missing tool binary (reported in the state phase as
        # "unknown") is unavailable info, not a declined action.
        plugin_unresolved = suppress_missing_binary_dry_run_unresolved(
            args, plugin_state["snapshot"], plugin_unresolved)
        acted.extend(plugin_action_rows)
        merge_plugin_remove_counts(counts, plugin_action_rows, label_width)

    print_changes(acted, first_prompt)

    rv = "would remove" if args.dry_run else "removed"
    parts = [
        colorize(f"{counts['removed']} {rv}", "green"),
        colorize(f"{counts['absent']} absent", "dim"),
    ]
    if counts["skipped"] or plugin_unresolved:
        parts.append(colorize(f"{counts['skipped'] + plugin_unresolved} kept/skipped", "yellow"))
    unresolved = counts["skipped"] > 0 or plugin_unresolved > 0
    mark = ("⚠️  " if unresolved else "✅ ") if _USE_EMOJI else ""
    print(mark + colorize("Summary: ", "cyan") + ", ".join(parts))
    return 0


# ---- generate ---------------------------------------------------------------

def generated_note(tool):
    return f"GENERATED from {manifest_label()} by '{cli_name()} generate {tool}'. Do not edit by hand."


def serialize(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_or_check(path, content, check, changed):
    root = REPO_ROOT.resolve()
    path = path.resolve()
    if path != root and root not in path.parents:
        sys.exit(f"error: generated output escapes {REPO_ROOT}: {path}")
    existing = path.read_text(encoding="utf-8") if path.exists() else None
    if existing == content:
        return
    rel = path.relative_to(root)
    changed.append(str(rel))
    if check:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"wrote: {rel}")


def build_claude_marketplace(manifest):
    catalog = {
        "$schema": "https://json.schemastore.org/claude-code-marketplace.json",
        "$generated": generated_note("claude"),
        "name": manifest["name"],
        "description": manifest.get("description", ""),
    }
    if "version" in manifest:
        catalog["version"] = manifest["version"]
    catalog["owner"] = manifest.get("owner", {})
    catalog["metadata"] = {"pluginRoot": "./plugins"}
    catalog["plugins"] = []
    for plugin in manifest["plugins"]:
        plugin_name = validate_path_fragment(plugin["name"], "plugin name", allow_nested=False)
        entry = {
            "name": plugin_name,
            "source": f"./{plugin_name}",
            "description": plugin.get("description", ""),
        }
        if "version" in plugin:
            entry["version"] = plugin["version"]
        if "category" in plugin:
            entry["category"] = plugin["category"]
        if plugin.get("keywords"):
            entry["keywords"] = plugin["keywords"]
        catalog["plugins"].append(entry)
    return catalog


def build_claude_plugin_manifest(manifest, plugin):
    plugin_name = validate_path_fragment(plugin["name"], "plugin name", allow_nested=False)
    out = {
        "$generated": generated_note("claude"),
        "name": plugin_name,
        "description": plugin.get("description", ""),
    }
    if "version" in plugin:
        out["version"] = plugin["version"]
    if "owner" in manifest:
        out["author"] = manifest["owner"]
    for key in ("homepage", "repository", "license"):
        if key in manifest:
            out[key] = manifest[key]
    return out


def owner_string(manifest):
    """Trae's owner field is a string; derive it from the manifest owner."""
    owner = manifest.get("owner")
    if isinstance(owner, dict):
        return owner.get("name", "")
    return owner or ""


def build_trae_marketplace(manifest):
    catalog = {
        "$generated": generated_note("trae"),
        "name": manifest["name"],
        "owner": owner_string(manifest),
        "plugins": [],
    }
    for plugin in manifest["plugins"]:
        plugin_name = validate_path_fragment(plugin["name"], "plugin name", allow_nested=False)
        entry = {
            "name": plugin_name,
            "description": plugin.get("description", ""),
        }
        if "version" in plugin:
            entry["version"] = plugin["version"]
        entry["source"] = f"./plugins/{plugin_name}"
        catalog["plugins"].append(entry)
    return catalog


def generate_claude(manifest, check, changed):
    write_or_check(CLAUDE_MARKETPLACE, serialize(build_claude_marketplace(manifest)), check, changed)
    for plugin in manifest["plugins"]:
        plugin_name = validate_path_fragment(plugin["name"], "plugin name", allow_nested=False)
        path = PLUGINS_DIR / plugin_name / ".claude-plugin" / "plugin.json"
        write_or_check(path, serialize(build_claude_plugin_manifest(manifest, plugin)), check, changed)


def generate_trae(manifest, check, changed):
    write_or_check(TRAE_MARKETPLACE, serialize(build_trae_marketplace(manifest)), check, changed)


def strip_frontmatter(text):
    """Drop a leading YAML frontmatter block (--- ... ---) from rule content.

    A rule's frontmatter carries tool-specific load directives that are
    meaningless inside a skill reference, so the derived copy embeds the body
    only. Returns the text unchanged when there is no frontmatter.
    """
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    return text[end + len("\n---\n"):].lstrip("\n")


# Paired HTML-comment markers that fence content out of a derived skill
# reference. Anything between them (inclusive) is dropped by the generator, so a
# rule can keep maintainer-only prose (e.g. a Related section of ecosystem
# cross-links) that is meaningless inside a delivered, self-contained skill.
# HTML comments render invisibly, so the markers do not affect the rule itself.
EXCLUDE_BEGIN = "<!-- skill-reference:exclude:begin -->"
EXCLUDE_END = "<!-- skill-reference:exclude:end -->"


def strip_excluded_blocks(text):
    """Remove every ``EXCLUDE_BEGIN``..``EXCLUDE_END`` block from rule content.

    Markers must be paired; an unterminated begin marker is a content error, so
    fail loudly rather than guess where the block ends. Returns the text
    unchanged when no markers are present.
    """
    while EXCLUDE_BEGIN in text:
        start = text.index(EXCLUDE_BEGIN)
        close = text.find(EXCLUDE_END, start)
        if close == -1:
            sys.exit(f"error: unterminated '{EXCLUDE_BEGIN}' (missing '{EXCLUDE_END}')")
        text = text[:start].rstrip("\n") + "\n\n" + text[close + len(EXCLUDE_END):].lstrip("\n")
    return text.rstrip("\n") + "\n"


def build_skill_reference(rule_rel):
    """Build the derived skill-reference content for a canonical rule path.

    Strips the rule's frontmatter (tool-specific load directives) and any
    marker-fenced exclude blocks (maintainer-only prose), leaving the portable
    body, then prepends a note pointing back to the canonical source.
    """
    rule_path = validate_path_fragment(rule_rel, "skillReferences rule path", allow_nested=True)
    src = confined_path(RULES_DIR, rule_path, "skillReferences rule path")
    if not src.exists():
        sys.exit(f"error: skillReferences rule not found: {src}")
    note = (
        f"<!-- GENERATED from rules/{rule_path} by '{cli_name()} generate'. "
        "Do not edit by hand; edit the canonical rule. -->\n\n"
    )
    body = strip_excluded_blocks(strip_frontmatter(src.read_text(encoding="utf-8")))
    return note + body


def generate_skill_references(manifest, check, changed):
    """Materialize each plugin's skillReferences into the skill's references/.

    The mapping in agentry.json associates a skill with canonical rule paths;
    this embeds a derived copy so the reference travels with the (copied)
    plugin, while the rule stays the single source of truth under rules/.
    """
    for plugin in manifest["plugins"]:
        plugin_name = validate_path_fragment(plugin["name"], "plugin name", allow_nested=False)
        for skill, rules in plugin.get("skillReferences", {}).items():
            skill_name = validate_path_fragment(skill, "skill name", allow_nested=False)
            for rule_rel in rules:
                rule_path = validate_path_fragment(rule_rel, "skillReferences rule path", allow_nested=True)
                dest = (
                    PLUGINS_DIR / plugin_name / "skills" / skill_name
                    / "references" / Path(rule_path).name
                )
                write_or_check(dest, build_skill_reference(rule_rel), check, changed)


def build_skill_script(script_rel):
    """Return the content a skill's bundled copy of a canonical script must hold.

    The script under ``scripts/`` is the single source of truth (imported by
    this module); ``generate`` embeds a byte-identical copy inside the skill so
    the skill is self-contained on any install, and ``generate --check`` fails
    on drift. The copy is verbatim: the script is stdlib-only and freestanding
    precisely so it runs unchanged inside the skill.
    """
    script_path = validate_path_fragment(script_rel, "skillScripts path", allow_nested=True)
    src = confined_path(REPO_ROOT, script_path, "skillScripts path")
    if not src.exists():
        sys.exit(f"error: skillScripts source not found: {src}")
    return src.read_text(encoding="utf-8")


def generate_skill_scripts(manifest, check, changed):
    """Materialize each plugin's skillScripts into the skill's scripts/ dir.

    The mapping in agentry.json associates a skill with canonical script paths
    (under scripts/); this embeds a byte-identical copy so the script travels
    with the (copied) skill, while the canonical script stays the single source
    of truth that this module imports.
    """
    for plugin in manifest["plugins"]:
        plugin_name = validate_path_fragment(plugin["name"], "plugin name", allow_nested=False)
        for skill, scripts in plugin.get("skillScripts", {}).items():
            skill_name = validate_path_fragment(skill, "skill name", allow_nested=False)
            for script_rel in scripts:
                script_path = validate_path_fragment(script_rel, "skillScripts path", allow_nested=True)
                dest = (
                    PLUGINS_DIR / plugin_name / "skills" / skill_name
                    / "scripts" / Path(script_path).name
                )
                write_or_check(dest, build_skill_script(script_rel), check, changed)


def check_plugin_readmes(manifest, missing):
    """Require each declared plugin to have a root README.md."""
    for plugin in manifest["plugins"]:
        plugin_name = validate_path_fragment(plugin["name"], "plugin name", allow_nested=False)
        readme = PLUGINS_DIR / plugin_name / "README.md"
        if not readme.is_file():
            missing.append(str(readme.relative_to(REPO_ROOT)))


def check_generated_packaging(manifest, targets):
    """Return generated files that differ from the manifest-derived output."""
    changed = []
    for tool in targets:
        if tool == "claude":
            generate_claude(manifest, check=True, changed=changed)
        else:
            generate_trae(manifest, check=True, changed=changed)
    generate_skill_references(manifest, check=True, changed=changed)
    generate_skill_scripts(manifest, check=True, changed=changed)
    return changed


def cmd_generate(args):
    """generate: regenerate Claude Code and/or Trae packaging from the manifest."""
    resolve_colors(args.color)
    manifest = load_manifest()
    targets = ("claude", "trae") if args.target == "all" else (args.target,)
    changed = []
    if args.check:
        changed = check_generated_packaging(manifest, targets)
    else:
        for tool in targets:
            if tool == "claude":
                generate_claude(manifest, check=False, changed=changed)
            else:
                generate_trae(manifest, check=False, changed=changed)
        # Derived skill references are tool-agnostic (identical content for
        # every tool), so generate them once regardless of the selected target.
        generate_skill_references(manifest, check=False, changed=changed)
        # Bundled skill scripts (canonical copies) are likewise tool-agnostic.
        generate_skill_scripts(manifest, check=False, changed=changed)

    label = " + ".join(targets) if args.target == "all" else args.target
    if args.check:
        if changed:
            print(f"Out of date (run '{cli_name()} generate'):")
            for path in changed:
                print(f"  {path}")
            return 1
        print(f"{label} packaging is up to date.")
    elif not changed:
        print("Already up to date.")
    return 0


def cmd_validate(args):
    """validate: run repository consistency checks."""
    resolve_colors(args.color)
    manifest = load_manifest()
    targets = ("claude", "trae")
    changed = check_generated_packaging(manifest, targets)
    missing = []
    check_plugin_readmes(manifest, missing)
    leaked = []
    check_eval_exclusion(manifest, leaked)

    if changed or missing or leaked:
        if changed:
            print(f"Out of date (run '{cli_name()} generate'):")
            for path in changed:
                print(f"  {path}")
        if missing:
            print("Missing required plugin README files (author these manually):")
            for path in missing:
                print(f"  {path}")
        if leaked:
            print("Evaluation assets must stay under plugins/*/eval/ (not shippable artifacts):")
            for path in leaked:
                print(f"  {path}")
        return 1
    print("Repository validation passed.")
    return 0


# ---------------------------------------------------------------------------
# evaluate: behavioral evaluation for authoring artifacts
#
# The runner brokers structured data only. `prepare` discovers plugin-local
# scenarios, resolves artifact/rule context, materializes before/after artifact
# source, and writes a run manifest plus producer-facing execution cases.
# `/evaluate-authoring` (an active agent runtime) produces outputs and writes
# JSONL result records. `collect` validates and aggregates those records into a
# scorecard. The runner never invokes an LLM or parses free-form agent prose.
# ---------------------------------------------------------------------------


def eval_root(plugin_name):
    """Return the ``plugins/<plugin>/eval`` directory for a plugin."""
    plugin_name = validate_path_fragment(plugin_name, "plugin name", allow_nested=False)
    return PLUGINS_DIR / plugin_name / EVAL_DIR_NAME


def discover_scenarios(plugins):
    """Yield scenario descriptors under each plugin's ``eval/`` tree.

    Descriptors are dicts with the plugin name, eval-tree kind directory
    (skills/commands/agents/rules), artifact key path, and the scenario file.
    Fixtures and tool-mocks subtrees are skipped; only ``*.md`` files directly
    under an artifact directory are scenarios.
    """
    for plugin in plugins:
        plugin_name = plugin["name"]
        base = eval_root(plugin_name)
        if not base.is_dir():
            continue
        for kind_dir in EVAL_COMPONENTS:
            kind_base = base / kind_dir
            if not kind_base.is_dir():
                continue
            for scenario_file in sorted(kind_base.rglob("*.md")):
                parts = scenario_file.relative_to(kind_base).parts
                # Skip fixtures/ and tool-mocks/ material nested under an artifact.
                if any(part in ("fixtures", "tool-mocks") for part in parts):
                    continue
                artifact_key = "/".join(parts[:-1])
                if not artifact_key:
                    continue  # scenario file must live under an artifact directory
                yield {
                    "plugin": plugin_name,
                    "kind_dir": kind_dir,
                    "artifact_key": artifact_key,
                    "path": scenario_file,
                }


def _artifact_path_matches(scenario, artifact_arg):
    """Return True when a parsed scenario belongs to the given artifact path."""
    if not artifact_arg:
        return True
    target = str(Path(artifact_arg)).rstrip("/")
    scenario_artifact = str(scenario.get("artifact", "")).rstrip("/")
    return scenario_artifact == target or scenario_artifact.startswith(target + "/")


def resolve_scenario_scope(args, plugins):
    """Resolve the ordered, deduped scenario file list for a scope selection."""
    artifact_arg = getattr(args, "artifact", None)
    plugin_args = getattr(args, "plugin", None)
    component_args = getattr(args, "component", None)
    scenario_args = getattr(args, "scenario", None)

    has_scope = bool(artifact_arg or plugin_args or component_args or scenario_args)
    if not has_scope and not getattr(args, "all", False):
        sys.exit("error: refusing to evaluate every scenario without an artifact path, "
                 "scope filter (--plugin/--component/--scenario), or explicit --all")

    selected = select_plugins(plugins, plugin_args)
    components = component_selection(component_args)
    wanted_kinds = {kind for kind in EVAL_COMPONENTS if kind in components}
    wanted_scenarios = list(dict.fromkeys(scenario_args)) if scenario_args else None

    descriptors = []
    seen = set()
    for descriptor in discover_scenarios(selected):
        if descriptor["kind_dir"] not in wanted_kinds:
            continue
        key = str(descriptor["path"])
        if key in seen:
            continue
        # Parse once, then apply the artifact-path and scenario-id filters.
        scenario = ec.parse_scenario(descriptor["path"])
        if not _artifact_path_matches(scenario, artifact_arg):
            continue
        if wanted_scenarios is not None and scenario["id"] not in wanted_scenarios:
            continue
        seen.add(key)
        descriptor["scenario"] = scenario
        descriptors.append(descriptor)
    return descriptors


# --- side source materialization (side-effect-free, object-history only) ----


def _git(args_list, *, check=True):
    """Run ``git -C REPO_ROOT`` returning (returncode, stdout, stderr)."""
    binary = shutil.which("git")
    if not binary:
        sys.exit("error: git is required to materialize ref:<git-ref> artifact sources")
    argv = [binary, "-C", str(REPO_ROOT), *args_list]
    proc = subprocess.run(argv, capture_output=True, text=True, check=False)
    if check and proc.returncode != 0:
        sys.exit(f"error: git {' '.join(args_list)} failed: {proc.stderr.strip()}")
    return proc.returncode, proc.stdout, proc.stderr


def git_blob_id(ref, rel_path):
    """Return the object id for ``ref:rel_path`` or None when absent at that ref."""
    # --end-of-options stops a leading-dash ref from being parsed as a git option.
    code, out, _ = _git(
        ["rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}:{rel_path}"],
        check=False,
    )
    return out.strip() if code == 0 and out.strip() else None


def snapshot_artifact_source(ref, source_rel, dest_dir):
    """Materialize ``ref``'s artifact source under ``dest_dir`` via git archive.

    ``git archive`` reads object history only: it never touches the working
    tree, index, or HEAD, so ref snapshots are safe and repeatable.
    """
    # Confine the destination so a traversing source_rel cannot create dirs
    # outside the run's sources tree, even before git validates the pathspec.
    dest = confined_leaf_path(dest_dir, source_rel, "artifact source")
    dest.parent.mkdir(parents=True, exist_ok=True)
    binary = shutil.which("git")
    if not binary:
        sys.exit("error: git is required to materialize ref:<git-ref> artifact sources")
    if not shutil.which("tar"):
        sys.exit("error: tar is required to materialize ref:<git-ref> artifact sources")
    # A clear message when the artifact does not exist at this ref: git archive
    # would otherwise abort with a raw "pathspec" error.
    if git_blob_id(ref, source_rel) is None:
        sys.exit(
            f"error: artifact source {source_rel!r} does not exist at ref {ref!r}; "
            "use an artifact-absent side with source 'absent' when intentionally "
            "comparing against no artifact."
        )
    # --end-of-options stops a leading-dash ref from being parsed as a git
    # option; source_rel is already confined, so it is safe as a positional path.
    tar = subprocess.run(
        [binary, "-C", str(REPO_ROOT), "archive", "--end-of-options", ref, source_rel],
        capture_output=True, check=False,
    )
    if tar.returncode != 0:
        sys.exit(f"error: git archive {ref}:{source_rel} failed: {tar.stderr.decode(errors='replace').strip()}")
    extract_root = dest_dir
    extract_root.mkdir(parents=True, exist_ok=True)
    untar = subprocess.run(
        ["tar", "-x", "-C", str(extract_root)], input=tar.stdout, capture_output=True, check=False,
    )
    if untar.returncode != 0:
        sys.exit(f"error: extracting {ref}:{source_rel} failed: {untar.stderr.decode(errors='replace').strip()}")
    return dest


def assert_fixtures_stable(scenario, refs, allow_drift):
    """Abort when a scenario's fixtures differ across compared git refs.

    v1 uses the current working-tree suite, fixtures, and checks for both sides;
    only artifact source is snapshotted per ref. A fixture that changed across
    compared refs would make the comparison ambiguous, so reject unless
    explicitly allowed.
    """
    refs = [ref for ref in refs if ref]
    if allow_drift or len(refs) < 2:
        return
    fixtures = scenario.get("fixtures", {})
    scenario_dir = scenario["_dir"].relative_to(REPO_ROOT)
    for name, rel in fixtures.items():
        fixture_rel = str(scenario_dir / rel)
        blob_ids = {git_blob_id(ref, fixture_rel) for ref in refs}
        if len(blob_ids) > 1:
            joined = ", ".join(refs)
            sys.exit(f"error: fixture {name!r} ({fixture_rel}) differs across refs {joined}; "
                     "pass --allow-fixture-drift to compare anyway")


# --- artifact context resolution -------------------------------------------
#
# These resolvers are the repo-coupled half of prepare: they use this checkout's
# paths to turn a scenario into an artifact identity, on-disk source, and rule
# envelope. They live here — not in the freestanding ``eval_contract`` module —
# so the contract module carries no repo-path or manifest coupling;
# ``prepare_run`` feeds their output to ``eval_contract.prepare`` as
# ``ScenarioSide`` inputs.


def resolve_rule_context(rule_path, *, rules_dir):
    """Return the activation envelope for a canonical rule under evaluation.

    Rules are evaluated as active guidance in context. Plugin membership is
    Agentry distribution metadata, not part of the evaluation case contract.
    """
    rule_path = validate_path_fragment(rule_path, "rule path", allow_nested=True)
    src = confined_path(rules_dir, rule_path, "rule path")
    if not src.exists():
        sys.exit(f"error: rule not found: {src}")
    return {"rule_path": f"rules/{rule_path}"}


def resolve_artifact_context(scenario, *, repo_root, rules_dir):
    """Resolve artifact kind, canonical source, and manifest/rule context."""
    artifact_rel = scenario["artifact"]
    kind = scenario["kind"]
    context = {"kind": kind, "artifact": artifact_rel, "rule_envelope": None}
    if kind == "rule":
        rule_rel = artifact_rel[len("rules/"):] if artifact_rel.startswith("rules/") else artifact_rel
        context["rule_envelope"] = resolve_rule_context(rule_rel, rules_dir=rules_dir)
        # Rule source travels as the whole (nested) rule file.
        context["source_rel"] = f"rules/{validate_path_fragment(rule_rel, 'rule path', allow_nested=True)}"
        context["source_is_dir"] = False
        return context
    # Non-rule artifacts point at a file inside plugins/<plugin>/...; a skill
    # snapshot travels as its whole directory so references/ come along. Confine
    # the artifact path the same way fixtures and rules are confined, so a
    # scenario cannot read (or later snapshot) a file outside the repo.
    validate_path_fragment(artifact_rel, "artifact path", allow_nested=True)
    confined_path(repo_root, artifact_rel, "artifact path")
    if kind == "skill":
        context["source_rel"] = str(Path(artifact_rel).parent)
        context["source_is_dir"] = True
    else:
        context["source_rel"] = artifact_rel
        context["source_is_dir"] = False
    return context


def runner_tag(manifest, *, brand):
    """Return the ``{name, version}`` provenance tag for the run generator.

    ``name`` is the active runner's display brand (so a downstream wrapper that
    reuses this module stamps its own name), and ``version`` is the project
    version from the manifest (which moves per release), or ``None`` when the
    manifest declares none. This is honest, moving provenance — unlike a frozen
    contract-version constant — recording which runner and release produced a run.
    """
    return {"name": brand, "version": manifest.get("version")}


# --- case / manifest construction -----------------------------------------
#
# The scenario/case/manifest builders and the single ``prepare`` entry point
# live in the freestanding ``eval_contract`` module and are imported at the top
# of this file so a byte-identical copy can run inside a skill. ``prepare``
# consumes already-resolved ``ScenarioSide`` inputs, so all repo/git resolution
# (artifact context, per-side source placement, the runner tag) happens here in
# ``prepare_run`` before the contract module is called.


def write_json(path, data):
    """Write ``data`` as pretty JSON, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize(data), encoding="utf-8")


def _slug(value):
    """Return a filesystem-safe slug for a target/scenario id."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)


EVAL_WORKTREE_SOURCE = "worktree"
EVAL_ABSENT_SOURCE = "absent"


def parse_side_source(value, label):
    """Parse an evaluation side source spec.

    Accepted forms are:
    - ``worktree``: materialize the current working-tree artifact.
    - ``absent``: omit the artifact for this side.
    - ``ref:<git-ref>``: snapshot the artifact from a git ref.
    """
    if value == EVAL_WORKTREE_SOURCE:
        return {"kind": "worktree", "label": EVAL_WORKTREE_SOURCE, "ref": None}
    if value == EVAL_ABSENT_SOURCE:
        return {"kind": "absent", "label": EVAL_ABSENT_SOURCE, "ref": None}
    if isinstance(value, str) and value.startswith("ref:") and value[4:]:
        ref = value[4:]
        return {"kind": "ref", "label": ref, "ref": ref}
    sys.exit(
        f"error: {label} must be one of 'worktree', 'absent', or 'ref:<git-ref>'; got {value!r}"
    )


def _resolve_side_sources(args):
    baseline = parse_side_source(getattr(args, "baseline", None) or EVAL_WORKTREE_SOURCE, "--baseline")
    variant_arg = getattr(args, "variant", None)
    variant = parse_side_source(variant_arg, "--variant") if variant_arg is not None else None
    if baseline["kind"] == "absent" and variant is None:
        sys.exit("error: --baseline absent requires --variant for a comparison run")
    return {ec.BASELINE_SIDE: baseline, **({ec.VARIANT_SIDE: variant} if variant else {})}


def prepare_run(descriptors, manifest, run_dir, *, side_sources, targets, mode, allow_fixture_drift, evaluator=None, evidence_override=None):
    """Resolve sources into units, then materialize a run via ``eval_contract.prepare``.

    This function owns every repo/git concern so the contract module stays
    freestanding: it resolves each descriptor's artifact context from the
    manifest and this checkout, places each side's on-disk source, and builds a
    ``ScenarioSide`` per (descriptor, side). Worktree sources read the current
    working tree, ref sources are snapshotted into the run's ``sources/`` tree,
    and absent sources intentionally omit the artifact. ``eval_contract.prepare``
    then copies files and stamps records from those units. Returns
    ``(run_manifest, manifest_path)``.
    """
    sides = [side for side in (ec.BASELINE_SIDE, ec.VARIANT_SIDE) if side in side_sources]

    # Fail-fast: when comparing two git-ref sides, assert every scenario's
    # fixtures are stable across the refs before anything is written, so a drift
    # abort never leaves a partial dir.
    git_refs = [source["ref"] for source in side_sources.values() if source["kind"] == "ref"]
    if git_refs:
        for descriptor in descriptors:
            assert_fixtures_stable(descriptor["scenario"], git_refs, allow_fixture_drift)

    # Build units grouped by descriptor (all sides of a descriptor consecutive)
    # so eval_contract.prepare, which groups consecutive same-scenario units into
    # one manifest entry, reproduces the prior scenario order and case grouping.
    units = []
    for descriptor in descriptors:
        scenario = descriptor["scenario"]
        ctx = resolve_artifact_context(scenario, repo_root=REPO_ROOT, rules_dir=RULES_DIR)
        suite_path = str(descriptor["path"].relative_to(REPO_ROOT))
        for side in sides:
            source = side_sources[side]
            artifact_absent = source["kind"] == "absent"
            if source["kind"] == "worktree" or artifact_absent:
                source_base = REPO_ROOT / ctx["source_rel"]
            else:
                # Snapshot the per-side source before prepare copies from it.
                snapshot_artifact_source(source["ref"], ctx["source_rel"], run_dir / "sources" / side)
                source_base = run_dir / "sources" / side / ctx["source_rel"]
            units.append(ec.ScenarioSide(
                scenario=scenario,
                side=side,
                source_base=source_base,
                kind=ctx["kind"],
                artifact=ctx["artifact"],
                source_is_dir=ctx["source_is_dir"],
                artifact_absent=artifact_absent,
                rule_envelope=ctx.get("rule_envelope"),
                suite_path=suite_path,
            ))

    side_labels = {side: source["label"] for side, source in side_sources.items()}
    return ec.prepare(
        units, run_dir, targets=targets, mode=mode,
        runner=runner_tag(manifest, brand=BRAND), side_labels=side_labels,
        evaluator=evaluator, evidence_override=evidence_override,
    )


# --- executor seam -----------------------------------------------------------


def parse_target(value):
    """Parse a ``tool:model`` target into a descriptor dict."""
    if ":" not in value:
        sys.exit(f"error: target {value!r} must be 'tool:model' (e.g. trae:GPT-5.5)")
    tool, model = value.split(":", 1)
    if not tool or not model:
        sys.exit(f"error: target {value!r} must be 'tool:model' (e.g. trae:GPT-5.5)")
    return {"id": value, "tool": tool, "model": model}


# Map an evaluation executor tool to the CLI that runs /evaluate-authoring
# non-interactively, and how that CLI takes a model. v1 automates Trae only;
# other tools can still be driven by --executor-command with a freeform argv.
EVAL_EXECUTOR_TOOLS = {"trae": {"binary": "traecli", "argv": ["exec"], "model_flag": "--model"}}


class UnsupportedExecutor(Exception):
    """Raised when a structured executor names a tool with no known CLI."""


class ExecutorUnavailable(Exception):
    """Raised when a supported executor tool's binary is not on PATH."""


class NoExecutor(Exception):
    """Raised when neither executor form was provided."""


def resolve_executor(structured, command):
    """Return an argv list to run /evaluate-authoring for the orchestrator.

    Exactly one form is given (the caller enforces the mutex):

    - ``structured`` is a ``tool:model`` descriptor (from ``parse_target``): the
      orchestrator runs through that tool's known CLI with the model pinned.
      An unknown tool raises ``UnsupportedExecutor``; a known tool whose binary
      is absent raises ``ExecutorUnavailable``.
    - ``command`` is a freeform argv string, split on whitespace and used as-is
      (the escape hatch for custom binaries, extra flags, or wrappers).

    Neither form raises ``NoExecutor``. The orchestrator is the process host,
    independent of the evaluation ``--target`` (the producing tool/model); its
    identity is never inferred from a target.
    """
    if command:
        return command.split()
    if not structured:
        raise NoExecutor()
    spec = EVAL_EXECUTOR_TOOLS.get(structured["tool"])
    if not spec:
        raise UnsupportedExecutor(structured["tool"])
    binary = shutil.which(spec["binary"])
    if not binary:
        raise ExecutorUnavailable(structured["tool"])
    return [binary, *spec["argv"], spec["model_flag"], structured["model"]]


def eval_runs_root():
    """Return the default root for evaluation run directories."""
    return REPO_ROOT / EVAL_RUNS_DIRNAME


def _resolve_run_dir(args):
    """Resolve the run directory for prepare/run.

    An explicit --run-dir wins; otherwise default to a timestamped directory
    under the runs root so both subcommands share one location policy.
    """
    explicit = getattr(args, "run_dir", None)
    if explicit:
        return explicit.resolve()
    return eval_runs_root() / datetime.now().strftime("run-%Y%m%d-%H%M%S")


def cmd_evaluate(args):
    """evaluate: dispatch to the prepare/collect/run/clean subcommand."""
    subcommand = getattr(args, "evaluate_command", None)
    if subcommand is None:
        # Bare `evaluate` (no subcommand) has no --color of its own; print help.
        args.parser.print_help()
        return 0
    resolve_colors(args.color)
    if subcommand == "prepare":
        return cmd_evaluate_prepare(args)
    if subcommand == "collect":
        return cmd_evaluate_collect(args)
    if subcommand == "run":
        return cmd_evaluate_run(args)
    if subcommand == "clean":
        return cmd_evaluate_clean(args)
    args.parser.print_help()
    return 0


def _resolve_targets(args):
    # A target names the tool/model that produced the output; it is not the same
    # axis as --mode. Both rendered and sandbox runs must name their target so
    # cases, results, and the scorecard carry a real tool/model identity rather
    # than a placeholder, so at least one --target is required.
    target_args = getattr(args, "target", None)
    if not target_args:
        sys.exit("error: at least one --target 'tool:model' is required (e.g. trae:GPT-5.5)")
    seen = {}
    for value in target_args:
        target = parse_target(value)
        seen.setdefault(target["id"], target)
    return list(seen.values())


def _resolve_evaluator(args):
    """Return the rubric-evaluator descriptor from --evaluator, or None.

    Optional and non-repeatable: it pins the judge's tool/model as a run-level
    policy (the same judge across both sides of a scenario). When unset, the
    orchestrator judges with its own runtime. The actual judge identity is
    always recorded in results regardless of this directive.
    """
    value = getattr(args, "evaluator", None)
    if not value:
        return None
    return parse_target(value)


def _resolve_evidence_override(args):
    """Return the run-time evidence bar from --evidence as ``(consistent, reps)``.

    ``--evidence`` is a single paired value ``consistent/total`` (e.g. ``4/5``,
    read "4 of 5") so a run cannot set one half of the bar without the other.
    Returns ``None`` when unset. This parses only the CLI format; the contract
    coherence rule (``1 <= consistent <= total``) is enforced by
    ``eval_contract.prepare`` up front, so it stays single-sourced there.
    """
    value = getattr(args, "evidence", None)
    if not value:
        return None
    if value.count("/") != 1:
        sys.exit(f"error: --evidence must be 'consistent/total' (e.g. 4/5), got {value!r}")
    consistent_s, total_s = value.split("/", 1)
    try:
        consistent, total = int(consistent_s), int(total_s)
    except ValueError:
        sys.exit(f"error: --evidence must be two integers 'consistent/total' (e.g. 4/5), got {value!r}")
    return (consistent, total)


def _executor_structured(args):
    """Return the structured executor descriptor from --executor, or None.

    ``--executor tool:model`` is the common, structured form (symmetric with
    --target); the freeform ``--executor-command`` escape hatch is handled by
    ``resolve_executor``. The argparse mutex guarantees at most one is set.
    """
    value = getattr(args, "executor", None)
    if not value:
        return None
    return parse_target(value)


def _attach_scenario_paths(descriptors):
    """Attach convenience keys (_dir/_path) each scenario needs for fixtures."""
    for descriptor in descriptors:
        scenario = descriptor["scenario"]
        scenario["_path"] = str(descriptor["path"])
        scenario["_dir"] = descriptor["path"].parent


def cmd_evaluate_prepare(args):
    """evaluate prepare: validate scenarios and write a run manifest + cases."""
    manifest = load_manifest()
    plugins = load_plugins()
    descriptors = resolve_scenario_scope(args, plugins)
    if not descriptors:
        print("No scenarios matched the given scope.")
        return 1
    _attach_scenario_paths(descriptors)
    side_sources = _resolve_side_sources(args)
    targets = _resolve_targets(args)
    evaluator = _resolve_evaluator(args)
    evidence_override = _resolve_evidence_override(args)
    run_dir = _resolve_run_dir(args)
    run_manifest, manifest_path = prepare_run(
        descriptors, manifest, run_dir,
        side_sources=side_sources, targets=targets, mode=args.mode,
        allow_fixture_drift=getattr(args, "allow_fixture_drift", False),
        evaluator=evaluator, evidence_override=evidence_override,
    )
    print(f"Prepared {len(descriptors)} scenario(s) under {run_dir}")
    print(f"Run manifest: {manifest_path}")
    print(f"Next: run /evaluate-authoring against the manifest, then '{cli_name()} evaluate collect {run_dir}'.")
    return 0


def _print_scorecard_summary(report, report_path):
    """Print the scorecard path, status, aggregate line, and a failure reason."""
    agg = report["aggregate"]
    print(f"Scorecard: {report_path}")
    print(f"Status: {report.get('status', 'ok')}")
    print(f"Aggregate: {agg['passed']} passed / {agg['failed']} failed / "
          f"{agg['needs_review']} needs-review ({agg['pass_pct']}% pass)")
    # Surface why the run is failing, so exit 1 with 0 fails isn't a mystery.
    reasons = []
    if agg.get("integrity"):
        reasons.append(f"{agg['integrity']} integrity finding(s)")
    if agg.get("missing"):
        reasons.append(f"{agg['missing']} declared case(s) produced no results")
    if agg.get("short"):
        reasons.append(f"{agg['short']} required check(s) ran fewer than the expected repetitions")
    if agg["passed"] == 0 and not agg["failed"] and not agg["needs_review"] and not agg.get("missing"):
        reasons.append("no scenario results were scored")
    if reasons:
        # An integrity finding invalidates the run; otherwise it is incomplete.
        headline = "Invalid run" if agg.get("integrity") else "Incomplete run"
        print(f"{headline}: {'; '.join(reasons)}.")
        for f in report.get("integrity_findings") or []:
            where = f"{f['check']} rep {f['repetition']}" if f.get("check") else "(both sides)"
            print(f"  integrity: {f['scenario']} [{f['target']}/{f['side']}] {where} — {f['finding']}")
        for m in report.get("missing_coverage") or []:
            print(f"  missing: {m['scenario']} [{m['target']}/{m['side']}]")
        for s in report.get("short_checks") or []:
            print(f"  short: {s['scenario']} [{s['target']}/{s['side']}] {s['check']} "
                  f"(got {s['got']}/{s['expected']})")


def scorecard_exit_status(report: "ec.Report") -> int:
    """Return 0 only for a complete run with no failing or needs-review scenario.

    This is the project runner's gate policy: it maps the contract's factual
    report to a pass/fail exit code. A scenario side fails or is needs-review
    when a gating check does; a declared case that produced no results counts as
    missing coverage, as does a required check that ran fewer than the firm
    expected repetitions; and an integrity finding (a producer that is not the
    case target, an unhonored pinned evaluator, or an evaluator that differs
    across a scenario's baseline/variant sides) also fails the run, since it makes the
    evidence untrustworthy. Any of these yields a nonzero status so the exit code
    is a trustworthy gate rather than a false pass on an incomplete or
    low-integrity run. The contract describes the outcome; deciding what counts
    as a pass lives here, in the runner.
    """
    agg = report["aggregate"]
    if (agg["failed"] or agg["needs_review"] or agg.get("missing")
            or agg.get("short") or agg.get("integrity")):
        return 1
    # A run that scored nothing at all is not a pass.
    if agg["passed"] == 0:
        return 1
    return 0


def cmd_evaluate_collect(args):
    """evaluate collect: aggregate JSONL results into a scorecard + exit status."""
    run_dir = args.run_dir.resolve()
    report = ec.collect(run_dir)
    report_path = args.report.resolve() if getattr(args, "report", None) else (run_dir / "scorecard.md")
    ec.write_scorecard(report, report_path)
    _print_scorecard_summary(report, report_path)
    return scorecard_exit_status(report)


def cmd_evaluate_run(args):
    """evaluate run: drive prepare -> executor -> collect."""
    manifest = load_manifest()
    plugins = load_plugins()
    descriptors = resolve_scenario_scope(args, plugins)
    if not descriptors:
        print("No scenarios matched the given scope.")
        return 1
    _attach_scenario_paths(descriptors)
    side_sources = _resolve_side_sources(args)
    targets = _resolve_targets(args)
    evaluator = _resolve_evaluator(args)
    evidence_override = _resolve_evidence_override(args)
    # Resolve the orchestrator executor up front so a bad executor fails before
    # a run dir is materialized. The executor is the process host, independent
    # of --target; exactly one form is required by the argparse mutex.
    try:
        executor = resolve_executor(_executor_structured(args), getattr(args, "executor_command", None))
    except NoExecutor:
        sys.exit(
            "error: an executor is required; pass --executor tool:model or "
            "--executor-command, or run 'evaluate prepare' and orchestrate manually."
        )
    except UnsupportedExecutor as exc:
        sys.exit(
            f"error: --executor tool {str(exc)!r} has no known CLI (supported: "
            f"{', '.join(sorted(EVAL_EXECUTOR_TOOLS))}); use --executor-command to name a "
            "non-interactive command, or run 'evaluate prepare' and orchestrate manually."
        )
    except ExecutorUnavailable as exc:
        sys.exit(
            f"error: executor tool {str(exc)!r} is not installed on PATH; install it, use "
            "--executor-command to name an available command, or run 'evaluate prepare' and "
            "orchestrate manually."
        )
    run_dir = _resolve_run_dir(args)
    run_manifest, manifest_path = prepare_run(
        descriptors, manifest, run_dir,
        side_sources=side_sources, targets=targets, mode=args.mode,
        allow_fixture_drift=getattr(args, "allow_fixture_drift", False),
        evaluator=evaluator, evidence_override=evidence_override,
    )
    print(f"Prepared {len(descriptors)} scenario(s) under {run_dir}")

    # The `/evaluate-authoring` slash form is Trae's flat command-invocation
    # syntax (per `traecli exec --help`: prefix `/name` to invoke a command);
    # it is not universal — other tools namespace or prefix commands differently.
    # This is safe today because `EVAL_EXECUTOR_TOOLS` only maps Trae; when a
    # second executor tool is added, move this invocation template into that
    # tool's executor spec (beside binary/argv/model_flag) rather than hardcoding
    # one tool's form for every executor.
    argv = [*executor, f"/evaluate-authoring --run {manifest_path}"]
    proc = subprocess.run(argv, check=False)
    executor_failed = proc.returncode != 0
    if executor_failed:
        print(f"Executor exited with status {proc.returncode}; results may be incomplete.")

    report = ec.collect(run_dir, run_manifest)
    report_path = args.report.resolve() if getattr(args, "report", None) else (run_dir / "scorecard.md")
    ec.write_scorecard(report, report_path)
    _print_scorecard_summary(report, report_path)
    # A failed executor never yields a passing run, even if partial results scored.
    return 1 if executor_failed else scorecard_exit_status(report)


def _is_run_dir(path):
    """Return True when ``path`` looks like an evaluation run directory."""
    return path.is_dir() and (path / "manifest.json").is_file()


def cmd_evaluate_clean(args):
    """evaluate clean: remove evaluation run directories under the runs root."""
    root = args.runs_root.resolve() if getattr(args, "runs_root", None) else eval_runs_root()
    if not root.is_dir():
        print(f"Nothing to clean: {root} does not exist.")
        return 0
    # Only touch actual run dirs (those with a manifest), so an explicit
    # --runs-root pointed at a shared dir cannot delete unrelated content.
    runs = sorted((p for p in root.iterdir() if _is_run_dir(p)), key=lambda p: p.name)
    keep_last = getattr(args, "keep_last", 0) or 0
    to_remove = runs[:-keep_last] if keep_last else runs
    if not to_remove:
        print(f"Nothing to clean: {len(runs)} run(s) under {root}, keeping last {keep_last}.")
        return 0
    for run in to_remove:
        if getattr(args, "dry_run", False):
            print(f"would remove {run}")
        else:
            shutil.rmtree(run)
            print(f"removed {run}")
    kept = len(runs) - len(to_remove)
    verb = "would remove" if getattr(args, "dry_run", False) else "removed"
    print(f"{verb} {len(to_remove)} run(s); kept {kept}.")
    return 0


def _iter_manifest_component_paths(manifest):
    """Yield every repo-relative path a plugin declares as a shippable artifact."""
    for plugin in manifest.get("plugins", []):
        for _, src, _ in plugin_component_entries(plugin, set(COMPONENTS)):
            yield src
        plugin_name = plugin["name"]
        for skill, rules in plugin.get("skillReferences", {}).items():
            for rule_rel in rules:
                yield PLUGINS_DIR / plugin_name / "skills" / skill / "references" / Path(rule_rel).name


def check_eval_exclusion(manifest, findings):
    """Lock in that eval assets never resolve as shippable artifacts.

    Discovery is manifest-driven, so eval trees are already invisible to
    generate/install/inventory; this regression guard fails loudly if a declared
    component path ever points under an eval/ segment, or a discovered scenario
    file collides with a manifest-derived shippable path.
    """
    eval_segment = f"{os.sep}{EVAL_DIR_NAME}{os.sep}"
    shippable = set()
    for path in _iter_manifest_component_paths(manifest):
        resolved = str(path.resolve())
        shippable.add(resolved)
        if eval_segment in resolved or resolved.endswith(f"{os.sep}{EVAL_DIR_NAME}"):
            findings.append(f"{path} (declared component resolves under eval/)")
    for descriptor in discover_scenarios(manifest.get("plugins", [])):
        resolved = str(descriptor["path"].resolve())
        if resolved in shippable:
            findings.append(f"{descriptor['path']} (scenario collides with a shippable artifact path)")


def add_color_arg(parser):
    parser.add_argument(
        "--color",
        nargs="?",
        const="always",
        choices=("auto", "always", "never"),
        default="auto",
        help="Colorize output: omitted is 'auto' (color only on a TTY); a bare --color means "
        "'always' (force color); --color never disables it. NO_COLOR is honored unless "
        "--color always is given.",
    )


def add_selection_args(parser, *, writes):
    """Add the tool/plugin/component/scope args shared by install/status/uninstall."""
    parser.add_argument(
        "--tool",
        choices=sorted(TOOL_TARGETS),
        help="Target AI coding tool. Optional when running interactively (you will be "
        "prompted); required otherwise.",
    )
    parser.add_argument(
        "--plugin",
        action="append",
        help="Plugin to act on (repeatable; default: all plugins).",
    )
    parser.add_argument(
        "--component",
        action="append",
        choices=COMPONENT_CHOICES,
        help="Component types to act on (repeatable; use 'all' for skills, agents, commands, "
        "and rules). Default: all components for checkout runs; rules only for marketplace "
        "runs, since skills, subagents, and commands are delivered by the plugin marketplace.",
    )
    parser.add_argument(
        "--global",
        dest="global_scope",
        action="store_true",
        help="Use the user/global dirs instead of the project dirs (default: project).",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path.cwd(),
        help="Project root for project scope (default: current directory).",
    )
    parser.add_argument(
        "--defaults",
        action="store_true",
        help="Skip the interactive selection prompts (plugin/component"
        + ("/symlink" if writes else "") + ") and use their defaults. Flags you pass still override.",
    )
    add_color_arg(parser)


def add_evaluate_scope_args(parser):
    """Add the repeatable scope args shared by 'evaluate prepare' and 'run'."""
    parser.add_argument("artifact", nargs="?", help="Artifact path to scope scenarios to (optional).")
    parser.add_argument("--plugin", action="append", help="Plugin to scope to (repeatable; default: all plugins).")
    parser.add_argument(
        "--component", action="append", choices=COMPONENT_CHOICES,
        help="Component kinds to scope to (repeatable; use 'all' for every kind).",
    )
    parser.add_argument("--scenario", action="append", help="Scenario id to scope to (repeatable).")
    parser.add_argument(
        "--target", action="append",
        help="Evaluation target as 'tool:model' (required, repeatable; produces a target matrix).",
    )
    parser.add_argument(
        "--evaluator",
        help="Pin the rubric evaluator as 'tool:model' (optional). When unset, the "
        "orchestrator judges with its own runtime; the actual judge is recorded either way.",
    )
    parser.add_argument(
        "--evidence", metavar="CONSISTENT/TOTAL",
        help="Override the evidence bar for this run as consistent/total (e.g. 4/5 = "
        "4 of 5 repetitions must agree), overriding each scenario's tier default.",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Evaluate every discovered scenario (required when no artifact or scope filter is given).",
    )


class _SubcommandHelpFormatter(argparse.HelpFormatter):
    """Drop the redundant metavar pseudo-line above the subcommand list."""

    def _format_action(self, action):
        parts = super()._format_action(action)
        if action.nargs == argparse.PARSER:
            parts = "\n".join(parts.split("\n")[1:])
        return parts


def main(argv=None, *, repo_root=None, manifest_name=DEFAULT_MANIFEST_NAME, prog=DEFAULT_PROG, brand=DEFAULT_BRAND):
    """Run the CLI against ``repo_root``/``manifest_name`` (Agentry's own by default).

    Keyword-only ``repo_root``/``manifest_name``/``prog``/``brand`` are the
    reusable seam: a downstream catalog reusing this module via git submodule
    calls ``main(repo_root=<its root>, manifest_name=<its manifest>,
    prog=<its name>, brand=<its display name>)`` so every command operates on its
    tree and its help/header read its own program and display names. The defaults
    reproduce ``scripts/agentry.py`` behavior byte-for-byte. ``argv`` defaults to
    ``sys.argv[1:]``.
    """
    # Configure from this call's arguments on every invocation, so the result
    # never depends on a previous in-process call: a plain main() resets to
    # Agentry's own checkout, and an injected one targets the given tree. (Tests
    # that drive cmd_* directly still patch the globals; they do not go through
    # main().)
    configure(repo_root, manifest_name, prog, brand)
    parser = argparse.ArgumentParser(
        prog=prog,
        description=f"{BRAND} maintenance CLI.",
        formatter_class=_SubcommandHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", title="commands", metavar="<command>")

    install_help = "Install selected plugins' components into a tool's directories."
    p_install = sub.add_parser("install", help=install_help, description=install_help)
    add_selection_args(p_install, writes=True)
    p_install.add_argument("--dry-run", action="store_true", help="Show what would be installed without writing.")
    p_install.add_argument("--force", action="store_true", help="Overwrite existing files at the destination.")
    p_install.add_argument(
        "--yes", "-y", action="store_true",
        help="Assume yes: install missing and update stale items without prompting.",
    )
    p_install.add_argument(
        "--symlink", action="store_true",
        help="Symlink components back to this checkout instead of copying, so they track the "
        "source with no drift. The link target is relative. Not portable to Windows checkouts.",
    )
    p_install.add_argument(
        "--source",
        choices=("marketplace", "checkout"),
        default=None,
        help="Delivery channel for skills/subagents/commands (rules are copied either way). 'marketplace' "
        "orchestrates the tool CLI to add the marketplace and install plugins; it is user-scoped, "
        "so it forces --global and cannot be combined with --component. 'checkout' copies "
        "components from this checkout, touching no marketplace. Default: marketplace for a "
        "--global run with no --component, else checkout; passing --component selects checkout.",
    )
    p_install.set_defaults(func=cmd_install, status=False)

    status_help = "Report each item's install state without writing; exit 1 on drift."
    p_status = sub.add_parser("status", help=status_help, description=status_help)
    add_selection_args(p_status, writes=False)
    p_status.set_defaults(
        func=cmd_install, status=True, dry_run=False, force=False, yes=False, symlink=False, source=None,
    )

    uninstall_help = "Remove components this tool installed."
    p_uninstall = sub.add_parser("uninstall", help=uninstall_help, description=uninstall_help)
    add_selection_args(p_uninstall, writes=False)
    p_uninstall.add_argument("--dry-run", action="store_true", help="Show what would be removed without deleting.")
    p_uninstall.add_argument(
        "--force", action="store_true",
        help="Also remove drifted items (copied-stale/stale-link) that may not be ours.",
    )
    p_uninstall.add_argument(
        "--yes", "-y", action="store_true", help="Assume yes: remove owned items without prompting.")
    p_uninstall.add_argument(
        "--source",
        choices=("marketplace", "checkout"),
        default=None,
        help="Delivery channel to undo (rules are removed either way). 'marketplace' uninstalls "
        f"plugins via the tool CLI and removes the marketplace once no {BRAND} plugin remains; it "
        "is user-scoped, so it forces --global and cannot be combined with --component. 'checkout' "
        "removes only checkout-copied files. Default: marketplace for a --global run with no "
        "--component, else checkout; passing --component selects checkout.",
    )
    p_uninstall.set_defaults(func=cmd_uninstall, status=False, symlink=False)

    inventory_help = "Report manifest plugins, versions, and component membership."
    p_inventory = sub.add_parser("inventory", help=inventory_help, description=inventory_help)
    p_inventory.add_argument("--plugin", action="append", help="Plugin to report (repeatable; default: all plugins).")
    p_inventory.add_argument(
        "--component",
        action="append",
        choices=COMPONENT_CHOICES,
        help="Component types to report (repeatable; use 'all' for every component).",
    )
    p_inventory.add_argument("--details", action="store_true", help="Include component names below the summary table.")
    p_inventory.add_argument("--paths", action="store_true", help="Include canonical source paths.")
    p_inventory.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    add_color_arg(p_inventory)
    p_inventory.set_defaults(func=cmd_inventory)

    generate_help = f"Regenerate per-tool packaging from {manifest_label()}."
    p_generate = sub.add_parser("generate", help=generate_help, description=generate_help)
    p_generate.add_argument(
        "target", nargs="?", choices=("claude", "trae", "all"), default="all", metavar="<target>",
        help="Which packaging to generate: claude, trae, or all (default: all).",
    )
    p_generate.add_argument(
        "--check", action="store_true",
        help="Verify generated files are up to date without writing; exit 1 if not.",
    )
    add_color_arg(p_generate)
    p_generate.set_defaults(func=cmd_generate)

    validate_help = "Run repository consistency checks."
    p_validate = sub.add_parser("validate", help=validate_help, description=validate_help)
    add_color_arg(p_validate)
    p_validate.set_defaults(func=cmd_validate)

    evaluate_help = "Run behavioral evaluation for authoring artifacts (prepare/collect/run)."
    p_evaluate = sub.add_parser(
        "evaluate", help=evaluate_help, description=evaluate_help,
        formatter_class=_SubcommandHelpFormatter,
    )
    eval_sub = p_evaluate.add_subparsers(
        dest="evaluate_command", title="evaluate commands", metavar="<subcommand>",
    )
    # Bare `evaluate` prints its own help via cmd_evaluate dispatch.
    p_evaluate.set_defaults(func=cmd_evaluate, parser=p_evaluate)

    prepare_help = "Validate scenarios and write a run manifest plus execution cases."
    p_prepare = eval_sub.add_parser("prepare", help=prepare_help, description=prepare_help)
    add_evaluate_scope_args(p_prepare)
    p_prepare.add_argument(
        "--baseline", default=EVAL_WORKTREE_SOURCE, metavar="SOURCE",
        help="Baseline side source: 'worktree', 'absent', or 'ref:<git-ref>' (default: worktree).",
    )
    p_prepare.add_argument(
        "--variant", metavar="SOURCE",
        help="Optional variant side source for comparison: 'worktree', 'absent', or 'ref:<git-ref>'.",
    )
    p_prepare.add_argument(
        "--run-dir", type=Path,
        help=f"Run directory (default: a timestamped dir under {EVAL_RUNS_DIRNAME}/).",
    )
    p_prepare.add_argument(
        "--mode", choices=EVAL_MODES, default=DEFAULT_EVAL_MODE,
        help="Execution mode: 'rendered' builds cases from source/fixtures (default); "
        "'sandbox' also scaffolds an isolated sandbox for true-activation runs.",
    )
    p_prepare.add_argument(
        "--allow-fixture-drift", action="store_true",
        help="Permit fixtures that differ across compared ref:<git-ref> sources (default: reject).",
    )
    add_color_arg(p_prepare)
    p_prepare.set_defaults(func=cmd_evaluate, parser=p_prepare)

    collect_help = "Aggregate JSONL result records into a scorecard and set exit status."
    p_collect = eval_sub.add_parser("collect", help=collect_help, description=collect_help)
    p_collect.add_argument("run_dir", type=Path, help="Run directory produced by 'evaluate prepare'.")
    p_collect.add_argument("--report", type=Path, help="Scorecard Markdown path (a .json is written alongside).")
    add_color_arg(p_collect)
    p_collect.set_defaults(func=cmd_evaluate, parser=p_collect)

    run_help = "Run prepare, invoke the runtime executor, then collect."
    p_run = eval_sub.add_parser("run", help=run_help, description=run_help)
    add_evaluate_scope_args(p_run)
    p_run.add_argument(
        "--baseline", default=EVAL_WORKTREE_SOURCE, metavar="SOURCE",
        help="Baseline side source: 'worktree', 'absent', or 'ref:<git-ref>' (default: worktree).",
    )
    p_run.add_argument(
        "--variant", metavar="SOURCE",
        help="Optional variant side source for comparison: 'worktree', 'absent', or 'ref:<git-ref>'.",
    )
    p_run.add_argument(
        "--run-dir", type=Path,
        help=f"Run directory (default: a timestamped dir under {EVAL_RUNS_DIRNAME}/).",
    )
    p_run.add_argument("--mode", choices=EVAL_MODES, default=DEFAULT_EVAL_MODE, help="Execution mode (see 'prepare').")
    # The orchestrator executor is required and mutually exclusive: the common
    # structured form pins tool+model; the freeform command is the escape hatch.
    executor_group = p_run.add_mutually_exclusive_group(required=True)
    executor_group.add_argument(
        "--executor", metavar="TOOL:MODEL",
        help="Orchestrator as 'tool:model' (e.g. trae:GPT-5.5); runs that tool's CLI with the model pinned.",
    )
    executor_group.add_argument(
        "--executor-command", dest="executor_command", metavar="ARGV",
        help="Orchestrator as a freeform command argv (space-separated); the escape hatch for custom binaries.",
    )
    p_run.add_argument("--allow-fixture-drift", action="store_true", help="Permit fixtures that differ across refs.")
    p_run.add_argument("--report", type=Path, help="Scorecard Markdown path (a .json is written alongside).")
    add_color_arg(p_run)
    p_run.set_defaults(func=cmd_evaluate, parser=p_run)

    clean_help = f"Remove evaluation run directories under {EVAL_RUNS_DIRNAME}/."
    p_clean = eval_sub.add_parser("clean", help=clean_help, description=clean_help)
    p_clean.add_argument(
        "--runs-root", type=Path,
        help=f"Directory holding run dirs to prune (default: {EVAL_RUNS_DIRNAME}/). "
        "Only subdirectories containing a manifest.json are removed.",
    )
    p_clean.add_argument(
        "--keep-last", type=int, default=0, metavar="N",
        help="Keep the N most recent run directories; remove the rest (default: remove all).",
    )
    p_clean.add_argument("--dry-run", action="store_true", help="Show what would be removed without deleting.")
    add_color_arg(p_clean)
    p_clean.set_defaults(func=cmd_evaluate, parser=p_clean)

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    try:
        code = main()
        # Flush inside the guard: piped stdout is block-buffered, so a closed
        # downstream pipe (e.g. `... | head`) only errors on flush, not on the
        # earlier print() calls. Catch it here rather than at interpreter exit.
        sys.stdout.flush()
    except BrokenPipeError:
        # Redirect remaining stdout to devnull so the final shutdown flush does
        # not re-raise on the dead pipe. Exit with the conventional SIGPIPE code
        # (128 + 13) so a closed pipe is not mistaken for a real failure/drift.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        code = 141
    except (KeyboardInterrupt, EOFError):
        # Cancelled at an interactive prompt (Ctrl-C / Ctrl-D): exit quietly
        # without a traceback. 130 is the conventional code for SIGINT.
        print()
        code = 130
    sys.exit(code)
