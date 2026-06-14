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

Install detail. Plugin formats for Claude Code and Trae have no "rules"
component, so rules are not delivered when you install a plugin from a
marketplace. After installing such a plugin, run ``install`` to add its rules
(the default when no ``--component`` is given). Pass ``--component skills``/
``agents`` to install those directly from a checkout (useful for development, or
for tools without marketplace support).

Examples:
    # Add a plugin's rules after installing it from a marketplace (rules by default)
    python3 scripts/agentry.py install --tool claude --plugin agentry-code-quality
    python3 scripts/agentry.py install --tool trae --plugin agentry-code-quality

    # Install skills and subagents directly from a checkout
    python3 scripts/agentry.py install --tool trae --plugin agentry-code-quality \\
        --component skills --component agents

    # Report-only check (exit 1 on drift), and removal
    python3 scripts/agentry.py status --tool claude
    python3 scripts/agentry.py uninstall --tool trae --plugin agentry-code-quality

    # Regenerate packaging (or verify it in CI)
    python3 scripts/agentry.py generate
    python3 scripts/agentry.py generate --check
"""

import argparse
import filecmp
import json
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "agentry.json"
PLUGINS_DIR = REPO_ROOT / "plugins"
RULES_DIR = REPO_ROOT / "rules"

CLAUDE_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
TRAE_MARKETPLACE = REPO_ROOT / ".trae-plugin" / "marketplace.json"

COMPONENTS = ("skills", "agents", "rules")

# Per-tool target directory for each component, relative to the project root
# (project scope) or the home directory (global scope). Kept in sync with the
# rule-manager and subagent-manager skill conventions.
TOOL_TARGETS = {
    "claude": {"skills": ".claude/skills", "agents": ".claude/agents", "rules": ".claude/rules"},
    "trae": {"skills": ".trae/skills", "agents": ".trae/agents", "rules": ".trae/rules"},
}

# The tool command that updates marketplace-delivered plugins/skills. install
# only manages files it copies/links (rules, and dev-installed skills/agents),
# so it reminds the user to run this for the parts it cannot see or update.
TOOL_MARKETPLACE_UPDATE = {
    "claude": "/plugin marketplace update agentry",
    "trae": "traecli plugin marketplace update agentry",
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


def plan_copies(plugins, components):
    """Return a list of (component, src_path, rel_dest) tuples to install."""
    jobs = []
    seen = set()
    for plugin in plugins:
        for skill in plugin.get("skills", []) if "skills" in components else []:
            src = PLUGINS_DIR / plugin["name"] / "skills" / skill
            key = ("skills", skill)
            if key not in seen:
                seen.add(key)
                jobs.append(("skills", src, skill))
        for agent in plugin.get("agents", []) if "agents" in components else []:
            src = PLUGINS_DIR / plugin["name"] / "agents" / f"{agent}.md"
            key = ("agents", agent)
            if key not in seen:
                seen.add(key)
                jobs.append(("agents", src, f"{agent}.md"))
        for rule in plugin.get("rules", []) if "rules" in components else []:
            src = RULES_DIR / rule
            key = ("rules", rule)
            if key not in seen:
                seen.add(key)
                jobs.append(("rules", src, rule))
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


def confirm(question, default):
    """Prompt y/n on a TTY. Callers must only invoke this when interactive.

    The prompt line is fully erased after answering (on a TTY); the choice is
    surfaced later in the run header, not left on screen here.
    """
    suffix = "[Y/n]" if default else "[y/N]"
    reply = input(f"{colorize(question, 'cyan')} {colorize(suffix, 'dim')} ").strip().lower()
    if sys.stdout.isatty():
        sys.stdout.write("\033[1F\033[J")  # erase the prompt line
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
    printed = 1  # the prompt/input line
    while True:
        reply = input(f"{colorize(question, 'cyan')} {colorize('[Y/n/a/q]', 'dim')} ").strip().lower()
        if reply in replies:
            break
        print(colorize("error: answer y (yes), n (no), a (yes to all), or q (no to all)", "red"))
        printed += 2  # the error line plus the next prompt line
    if sys.stdout.isatty():
        sys.stdout.write(f"\033[{printed}F\033[J")  # erase the prompt block
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
    while True:
        reply = input(f"{colorize('Choose', 'cyan')} {hint}: ").strip()
        printed += 1  # the prompt/input line
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
    if sys.stdout.isatty():
        # Move to the start of the question line and clear to end of screen,
        # fully erasing the prompt block.
        sys.stdout.write(f"\033[{printed}F\033[J")
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


def resolve_selection(args, all_plugins, removing=False):
    """Resolve tool/plugin/component (and symlink) via prompts when interactive.

    Shared by install/status/uninstall. ``removing`` and ``args.status`` tailor
    which prompts apply: symlink only affects writes, so it is skipped for both.
    Returns the components set after resolution.
    """
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    args._interactive = interactive

    if args.tool is None:
        if not interactive:
            sys.exit("error: --tool is required when not running interactively")
        args.tool = choose("Which tool?", sorted(TOOL_TARGETS))

    writes = not getattr(args, "status", False) and not removing

    # Offer a single shortcut up front: if any selection is still unset and we'd
    # otherwise prompt for each, ask once whether to just use the defaults.
    # Accepting is equivalent to --defaults.
    unset = args.plugin is None or args.component is None or (writes and not args.symlink)
    if interactive and not args.defaults and unset:
        comps = ", ".join(sorted(args.component)) if args.component else "rules"
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

    if args.component is None and ask_optional:
        args.component = choose("Which components?", ["rules", "skills", "agents"], default="rules", multi=True)

    if writes and not args.symlink and ask_optional:
        args.symlink = confirm("Symlink instead of copy?", default=False)

    return set(args.component) if args.component else {"rules"}


def print_header(args, base, components, action):
    """Print the run header and the per-job report; return (plan, label_width)."""
    plugins = select_plugins(load_plugins(), args.plugin)
    jobs = plan_copies(plugins, components)
    if not jobs:
        print("Nothing to do for the given selection.")
        return None, None

    scope = "global" if args.global_scope else "project"
    title = ("📦 " if _USE_EMOJI else "") + f"Agentry — {args.tool}, {scope} scope ({base})"
    print(colorize(title, "cyan"))
    detail = [f"plugin: {args.plugin or 'all'}", f"components: {', '.join(sorted(components))}"]
    if action == "install":
        detail.append(f"mode: {'symlink' if args.symlink else 'copy'}")
    print(colorize(indent() + " · ".join(detail), "dim"))
    print()

    targets = TOOL_TARGETS[args.tool]
    plan = []
    for component, src, rel_dest in jobs:
        if not src.exists():
            sys.exit(f"error: source missing: {src}")
        # Do not resolve() the full path: if dest is already a symlink into the
        # source tree, resolving would point operations (e.g. unlink) at the
        # source itself. base is already absolute.
        dest = base / targets[component] / rel_dest
        rel = dest.relative_to(base)
        state = classify_state(src, dest)
        plan.append((component, src, dest, rel, state))
    return plan, targets


def cmd_install(args):
    """install / status: classify, report, then write (unless --status)."""
    resolve_colors(args.color)
    all_plugins = load_plugins()
    components = resolve_selection(args, all_plugins)
    interactive = args._interactive

    base = Path.home() if args.global_scope else args.project_dir.resolve()
    result = print_header(args, base, components, "status" if args.status else "install")
    if result[0] is None:
        return 0
    plan, _ = result

    # Shared width so report tags and action labels share one aligned column.
    action_labels = ["would install", "would update"] if args.dry_run else (
        ["linked"] if args.symlink else ["installed", "updated"])
    label_width = max(len(s) for s in ["missing", "synced", "stale", *action_labels])
    for _, _, _, rel, state in plan:
        print(report_line(state, rel, label_width))

    counts = {"current": 0, "installed": 0, "updated": 0, "skipped": 0}
    acted = []
    first_prompt = True
    bulk = None  # set to True/False once the user answers 'all'/'none'
    for component, src, dest, rel, state in plan:
        action = needs_action(state)
        # --force acts on every job (today's behavior), e.g. to convert a
        # current copy into a symlink under --symlink --force.
        if not action and not args.force:
            counts["current"] += 1
            continue
        if args.status:
            continue  # report-only

        verb = action_verb(state)
        if args.force or args.yes:
            act = True
        elif bulk is not None:
            act = bulk  # a previous 'all'/'none' answer applies to the rest
        elif interactive and not args.dry_run:
            # Blank line separates the prompts from the report list above. The
            # prompt itself self-erases, so this blank persists as the separator.
            if first_prompt:
                print()
                first_prompt = False
            answer = confirm_action(f"{indent()}{verb} {component} '{rel}'?")
            if answer in ("all", "none"):
                bulk = answer == "all"
                act = bulk
            else:
                act = answer == "yes"
        else:
            # Non-interactive fallback (and --dry-run preview, which never
            # prompts): install missing, but never overwrite stale without an
            # explicit signal (--yes/--force). Keeps the dry-run preview honest
            # about what a real non-interactive run would do.
            act = state == "missing"

        if not act:
            counts["skipped"] += 1
            continue
        # force=True so install_one overwrites stale copies / relinks stale links.
        install_one(src, dest, args.dry_run, force=True, symlink=args.symlink, quiet=True)
        if args.dry_run:
            label = f"would {verb}"  # e.g. "would install" / "would update"
        elif args.symlink:
            label = "linked"
        else:
            label = "installed" if state == "missing" else "updated"
        acted.append(f"{indent()}{colorize(f'{label:<{label_width}}', 'green')} {rel}")
        counts["installed" if state == "missing" else "updated"] += 1

    # Separate the report/actions from the summary with exactly one blank line.
    # An interactive run already printed a blank before its first (self-erasing)
    # prompt; reuse it instead of adding another.
    if acted:
        if first_prompt:
            print()  # no prompt separator was printed; add one before actions
        for line in acted:
            print(line)
        print()
    elif first_prompt:
        print()  # non-interactive / nothing prompted: add the summary separator
    # else: the lingering prompt separator already serves as the summary blank

    # Of the items counted as current, how many are symlinks (vs copies)? Mirrors
    # the current-count condition above: current means not needing action, and
    # --force re-acts on everything so nothing stays merely "current".
    linked = 0 if args.force else sum(1 for *_, state in plan if state == "linked")
    current_label = f"{counts['current']} synced"
    if linked:
        current_label += colorize(f" ({linked} linked)", "dim")
    if args.status:
        drift = sum(1 for *_, state in plan if needs_action(state))
        parts = [colorize(current_label, "green")]
        if drift:
            # Red if any item is stale (the more severe state), else yellow for
            # missing-only — matching the per-row report colors.
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
        if counts["skipped"]:
            parts.append(colorize(f"{counts['skipped']} skipped", "dim"))
    unresolved = (args.status and any(needs_action(s) for *_, s in plan)) or \
        (not args.status and counts["skipped"] > 0)
    # ⚠️ is a narrow (1-cell) emoji vs ✅ (2-cell); pad it so the text aligns.
    mark = ("⚠️  " if unresolved else "✅ ") if _USE_EMOJI else ""
    print(mark + colorize("Summary: ", "cyan") + ", ".join(parts))

    # The reminder is a standing action hint (not a detail of the summary), so
    # it stays flush-left with its own marker rather than dimmed/indented.
    reminder = f"run '{TOOL_MARKETPLACE_UPDATE[args.tool]}' to update marketplace plugins/skills."
    print(("💡 " if _USE_EMOJI else "Reminder: ") + reminder)

    if args.status and any(needs_action(state) for *_, state in plan):
        return 1
    return 0


def cmd_uninstall(args):
    """uninstall: remove components this tool installed (owned copies/links)."""
    resolve_colors(args.color)
    all_plugins = load_plugins()
    components = resolve_selection(args, all_plugins, removing=True)
    interactive = args._interactive

    base = Path.home() if args.global_scope else args.project_dir.resolve()
    result = print_header(args, base, components, "uninstall")
    if result[0] is None:
        return 0
    plan, _ = result

    action_labels = ["would remove"] if args.dry_run else ["removed"]
    label_width = max(len(s) for s in ["missing", "synced", "stale", *action_labels])
    for _, _, _, rel, state in plan:
        print(report_line(state, rel, label_width))

    counts = {"absent": 0, "removed": 0, "skipped": 0}
    acted = []
    first_prompt = True
    bulk = None
    for component, src, dest, rel, state in plan:
        if state == "missing":
            counts["absent"] += 1
            continue
        # We only own items that match the canonical source: 'linked' symlinks
        # and 'copied-current' copies. Drifted items ('copied-stale',
        # 'stale-link') may be the user's own edits, so skip unless --force.
        owned = state in ("linked", "copied-current")
        if not owned and not args.force:
            kept = colorize(f"{'kept':<{label_width}}", "yellow")
            acted.append(
                f"{indent()}{kept} {rel}" + colorize("  (drifted; use --force to remove)", "dim")
            )
            counts["skipped"] += 1
            continue

        if args.yes or args.force:
            act = True
        elif bulk is not None:
            act = bulk
        elif interactive and not args.dry_run:
            if first_prompt:
                print()
                first_prompt = False
            answer = confirm_action(f"{indent()}remove {component} '{rel}'?")
            if answer in ("all", "none"):
                bulk = answer == "all"
                act = bulk
            else:
                act = answer == "yes"
        else:
            # Non-interactive without --yes: do not delete implicitly.
            act = False

        if not act:
            counts["skipped"] += 1
            continue
        remove_one(dest, args.dry_run)
        label = "would remove" if args.dry_run else "removed"
        acted.append(f"{indent()}{colorize(f'{label:<{label_width}}', 'green')} {rel}")
        counts["removed"] += 1

    if acted:
        if first_prompt:
            print()
        for line in acted:
            print(line)
        print()
    elif first_prompt:
        print()

    rv = "would remove" if args.dry_run else "removed"
    parts = [
        colorize(f"{counts['removed']} {rv}", "green"),
        colorize(f"{counts['absent']} absent", "dim"),
    ]
    if counts["skipped"]:
        parts.append(colorize(f"{counts['skipped']} kept", "yellow"))
    unresolved = counts["skipped"] > 0
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
        choices=COMPONENTS,
        help="Component types to act on (repeatable). Default: rules only, since skills "
        "and subagents are delivered by the plugin marketplace.",
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
    p_install.set_defaults(func=cmd_install, status=False)

    status_help = "Report each item's install state without writing; exit 1 on drift."
    p_status = sub.add_parser("status", help=status_help, description=status_help)
    add_selection_args(p_status, writes=False)
    p_status.set_defaults(func=cmd_install, status=True, dry_run=False, force=False, yes=False, symlink=False)

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
