#!/usr/bin/env python3
"""Agentry maintenance CLI: install, status, uninstall, and generate.

Reads the canonical manifest (``agentry.json``) — the tool-agnostic source of
truth — and either installs a plugin's components into an AI coding tool's
directories or regenerates the per-tool packaging derived from the manifest.

Subcommands:

- ``install``   — copy or symlink a plugin's components into a tool's dirs.
- ``status``    — report each item's install state without writing; exit 1 on drift.
- ``uninstall`` — remove components this tool installed (owned copies/links).
- ``generate``  — regenerate Claude Code and/or Trae packaging from the manifest.

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

    # Regenerate packaging (or verify it in CI)
    python3 scripts/agentry.py generate
    python3 scripts/agentry.py generate --check
"""

import argparse
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "agentry.json"
PLUGINS_DIR = REPO_ROOT / "plugins"
RULES_DIR = REPO_ROOT / "rules"

CLAUDE_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
TRAE_MARKETPLACE = REPO_ROOT / ".trae-plugin" / "marketplace.json"

COMPONENTS = ("skills", "agents", "commands", "rules")
COMPONENT_CHOICES = COMPONENTS + ("all",)

COMPONENT_TITLE = {"rules": "Rules", "skills": "Skills", "agents": "Agents", "commands": "Commands"}

FILE_REPORT_TAGS = {"missing", "synced", "stale"}
PLUGIN_REPORT_TAGS = {
    "unknown", "added", "installed", "missing", "absent", "kept", "skipped", "failed",
}
PLUGIN_INSTALL_ACTION_TAGS = {"would install", "installed", "would add", "added"}
PLUGIN_REMOVE_ACTION_TAGS = {"would remove", "removed"}

# Per-tool target directory for each component, relative to the project root
# (project scope) or the home directory (global scope). Kept in sync with the
# rule-manager, subagent-manager, and command-manager skill conventions.
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


def select_plugins(plugins, plugin_name):
    if not plugin_name:
        return plugins
    match = next((p for p in plugins if p.get("name") == plugin_name), None)
    if match is None:
        names = ", ".join(p.get("name", "?") for p in plugins)
        sys.exit(f"error: unknown plugin '{plugin_name}'. Available: {names}")
    return [match]


def plugin_component_entries(plugin, components):
    """Yield (component, source, relative-destination) entries for one plugin."""
    if "skills" in components:
        for skill in plugin.get("skills", []):
            yield "skills", PLUGINS_DIR / plugin["name"] / "skills" / skill, skill
    if "agents" in components:
        for agent in plugin.get("agents", []):
            yield (
                "agents",
                PLUGINS_DIR / plugin["name"] / "agents" / f"{agent}.md",
                f"{agent}.md",
            )
    if "commands" in components:
        for command in plugin.get("commands", []):
            yield (
                "commands",
                PLUGINS_DIR / plugin["name"] / "commands" / f"{command}.md",
                f"{command}.md",
            )
    if "rules" in components:
        for rule in plugin.get("rules", []):
            yield "rules", RULES_DIR / rule, rule


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
    sys.exit("error: cannot derive marketplace source from agentry.json (need 'repository' or 'owner' + 'name')")


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
            ok, _, err = run_tool_command(binary, ["plugin", "marketplace", "add", source], args.dry_run)
            if ok:
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
        ok, _, err = run_tool_command(binary, build_install_args(args.tool, ref, assume_yes=True), args.dry_run)
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
        )
        if ok:
            removed.add(name)
            label = "would remove" if args.dry_run else "removed"
            rows.append(plugin_row(label, name, action_width))
        else:
            unresolved += 1
            rows.append(plugin_row("failed", name, action_width, err.strip() or "unknown error"))

    # Marketplace removal: only when no Agentry plugin remains.
    remaining_ok, remaining = list_ok, (installed - removed) & agentry_plugin_names(manifest)
    if not remaining_ok:
        unresolved += 1
        rows.append(plugin_row("kept", f"marketplace {mkt}", action_width, "could not verify remaining plugins"))
    elif remaining:
        rows.append(plugin_row("kept", f"marketplace {mkt}", action_width,
                               f"{len(remaining)} Agentry plugin(s) still installed"))
    elif orchestrate_confirm(f"{indent()}no Agentry plugins remain; remove marketplace '{mkt}'?", args, interactive, bulk=bulk):
        ok, _, err = run_tool_command(
            binary,
            ["plugin", "marketplace", "remove", mkt] + removal_confirm_flags(args.tool),
            args.dry_run,
        )
        if ok:
            label = "would remove" if args.dry_run else "removed"
            rows.append(plugin_row(label, f"marketplace {mkt}", action_width, "no Agentry plugins remain"))
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
        defaults_desc = [f"plugin: {args.plugin or 'all'}", f"components: {comps}"]
        if writes:
            defaults_desc.append(f"mode: {'symlink' if args.symlink else 'copy'}")
        args.defaults = confirm(f"Use defaults ({' · '.join(defaults_desc)})?", default=True)

    # Selection prompts fire interactively unless --defaults uses each default.
    ask_optional = interactive and not args.defaults

    if args.plugin is None and ask_optional:
        picked = choose("Which plugin?", ["all"] + [p["name"] for p in all_plugins], default="all")
        if picked != "all":
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
    plugins = select_plugins(load_plugins(), args.plugin)
    jobs = plan_copies(plugins, components)
    if not jobs:
        return []

    targets = TOOL_TARGETS[args.tool]
    plan = []
    for component, src, rel_dest in jobs:
        if not src.exists():
            sys.exit(f"error: source missing: {src}")
        dest = base / targets[component] / rel_dest
        rel = dest.relative_to(base)
        state = classify_state(src, dest)
        plan.append((component, src, dest, rel, state))
    return plan


def print_run_header(args, base, scope, components, action, channel=None):
    """Print the common title/detail block for install/status/uninstall."""
    title = ("📦 " if _USE_EMOJI else "") + f"Agentry — {args.tool}, {scope} scope ({base})"
    print(colorize(title, "cyan"))
    detail = [f"plugin: {args.plugin or 'all'}", f"components: {', '.join(sorted(components))}"]
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
    return f"GENERATED from agentry.json by 'scripts/agentry.py generate {tool}'. Do not edit by hand."


def serialize(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_or_check(path, content, check, changed):
    existing = path.read_text(encoding="utf-8") if path.exists() else None
    if existing == content:
        return
    rel = path.relative_to(REPO_ROOT)
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
        entry = {
            "name": plugin["name"],
            "source": f"./{plugin['name']}",
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
    out = {
        "$generated": generated_note("claude"),
        "name": plugin["name"],
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
        entry = {
            "name": plugin["name"],
            "description": plugin.get("description", ""),
        }
        if "version" in plugin:
            entry["version"] = plugin["version"]
        entry["source"] = f"./plugins/{plugin['name']}"
        catalog["plugins"].append(entry)
    return catalog


def generate_claude(manifest, check, changed):
    write_or_check(CLAUDE_MARKETPLACE, serialize(build_claude_marketplace(manifest)), check, changed)
    for plugin in manifest["plugins"]:
        path = PLUGINS_DIR / plugin["name"] / ".claude-plugin" / "plugin.json"
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
    src = RULES_DIR / rule_rel
    if not src.exists():
        sys.exit(f"error: skillReferences rule not found: {src}")
    note = (
        f"<!-- GENERATED from rules/{rule_rel} by 'scripts/agentry.py generate'. "
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
        for skill, rules in plugin.get("skillReferences", {}).items():
            for rule_rel in rules:
                dest = (
                    PLUGINS_DIR / plugin["name"] / "skills" / skill
                    / "references" / Path(rule_rel).name
                )
                write_or_check(dest, build_skill_reference(rule_rel), check, changed)


def cmd_generate(args):
    """generate: regenerate Claude Code and/or Trae packaging from the manifest."""
    resolve_colors(args.color)
    manifest = load_manifest()
    targets = ("claude", "trae") if args.target == "all" else (args.target,)
    changed = []
    for tool in targets:
        if tool == "claude":
            generate_claude(manifest, args.check, changed)
        else:
            generate_trae(manifest, args.check, changed)
    # Derived skill references are tool-agnostic (identical content for every
    # tool), so generate them once regardless of the selected target.
    generate_skill_references(manifest, args.check, changed)

    label = " + ".join(targets) if args.target == "all" else args.target
    if args.check:
        if changed:
            print("Out of date (run 'scripts/agentry.py generate'):")
            for path in changed:
                print(f"  {path}")
            return 1
        print(f"{label} packaging is up to date.")
    elif not changed:
        print("Already up to date.")
    return 0


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
    parser.add_argument("--plugin", help="Act on only this plugin's components (default: all plugins).")
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


class _SubcommandHelpFormatter(argparse.HelpFormatter):
    """Drop the redundant metavar pseudo-line above the subcommand list."""

    def _format_action(self, action):
        parts = super()._format_action(action)
        if action.nargs == argparse.PARSER:
            parts = "\n".join(parts.split("\n")[1:])
        return parts


def main():
    parser = argparse.ArgumentParser(
        prog="agentry.py",
        description="Agentry maintenance CLI.",
        formatter_class=_SubcommandHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", title="commands", metavar="<command>")

    install_help = "Install a plugin's components into a tool's directories."
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
        "plugins via the tool CLI and removes the marketplace once no Agentry plugin remains; it "
        "is user-scoped, so it forces --global and cannot be combined with --component. 'checkout' "
        "removes only checkout-copied files. Default: marketplace for a --global run with no "
        "--component, else checkout; passing --component selects checkout.",
    )
    p_uninstall.set_defaults(func=cmd_uninstall, status=False, symlink=False)

    generate_help = "Regenerate per-tool packaging from agentry.json."
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

    args = parser.parse_args()
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
