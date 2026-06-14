#!/usr/bin/env python3
"""Install Agentry extensions into an AI coding tool's directories.

Reads the canonical manifest (``agentry.json``) and copies a plugin's components
into the target tool's directories.

Primary use — install a plugin's rules. Plugin formats for Claude Code and Trae
have no "rules" component, so rules are not delivered when you install a plugin
from a marketplace. After installing such a plugin, run this to add its rules
(the default when no ``--component`` is given).

Secondary use — install skills and subagents directly from a checkout (pass
``--component skills``/``agents``). Useful for development, or for tools without
marketplace support. Components map to the same plugins as the marketplace.

Examples:
    # Add a plugin's rules after installing it from a marketplace (rules by default)
    python3 scripts/install.py --tool claude --plugin agentry-code-quality
    python3 scripts/install.py --tool trae --plugin agentry-code-quality

    # Install skills and subagents directly from a checkout
    python3 scripts/install.py --tool trae --plugin agentry-code-quality \\
        --component skills --component agents

    # Preview, at user/global scope
    python3 scripts/install.py --tool claude --global --dry-run
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

COMPONENTS = ("skills", "agents", "rules")

# Per-tool target directory for each component, relative to the project root
# (project scope) or the home directory (global scope). Kept in sync with the
# rule-manager and subagent-manager skill conventions.
TOOL_TARGETS = {
    "claude": {"skills": ".claude/skills", "agents": ".claude/agents", "rules": ".claude/rules"},
    "trae": {"skills": ".trae/skills", "agents": ".trae/agents", "rules": ".trae/rules"},
}

# The tool command that updates marketplace-delivered plugins/skills. install.py
# only manages files it copies/links (rules, and dev-installed skills/agents), so
# it reminds the user to run this for the parts it cannot see or update.
TOOL_MARKETPLACE_UPDATE = {
    "claude": "/plugin marketplace update agentry",
    "trae": "traecli plugin marketplace update agentry",
}

# Install states for a planned (src -> dest) job.
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


def load_plugins():
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"error: manifest not found at {MANIFEST}")
    except json.JSONDecodeError as exc:
        sys.exit(f"error: invalid JSON in {MANIFEST}: {exc}")
    return data.get("plugins", [])


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


def main():
    parser = argparse.ArgumentParser(
        description="Install Agentry skills, agents, and rules into an AI coding tool's directories.",
    )
    parser.add_argument(
        "--tool",
        choices=sorted(TOOL_TARGETS),
        help="Target AI coding tool. Optional when running interactively (you will be "
        "prompted); required otherwise.",
    )
    parser.add_argument("--plugin", help="Install only this plugin's components (default: all plugins).")
    parser.add_argument(
        "--component",
        action="append",
        choices=COMPONENTS,
        help="Component types to install (repeatable). Default: rules only, since skills "
        "and subagents are delivered by the plugin marketplace. Pass e.g. "
        "--component skills to install those directly from a checkout.",
    )
    parser.add_argument(
        "--global",
        dest="global_scope",
        action="store_true",
        help="Install into the user/global dirs instead of the project dirs (default: project).",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path.cwd(),
        help="Project root for project scope (default: current directory).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be copied without writing.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files at the destination.")
    parser.add_argument(
        "--status",
        action="store_true",
        help="Report each item's install state (missing/synced/stale) without writing or "
        "prompting; exit 1 if anything is missing or stale, else 0. Cannot be combined with "
        "--yes/--force.",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Assume yes: install missing and update stale items without prompting "
        "(non-interactive). By default a bare run prompts per item on a TTY.",
    )
    parser.add_argument(
        "--defaults",
        action="store_true",
        help="Skip the interactive selection prompts (plugin/component/symlink) and use "
        "their defaults (all plugins, rules, copy). Flags you pass still override the default.",
    )
    parser.add_argument(
        "--symlink",
        action="store_true",
        help="Symlink components back to this checkout instead of copying, so they track the "
        "source with no drift. The link target is relative. Not portable to Windows checkouts.",
    )
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
    args = parser.parse_args()

    if args.status and (args.yes or args.force):
        sys.exit("error: --status is report-only; do not combine with --yes/--force")

    if args.color == "always":
        use_color = True
    elif args.color == "never":
        use_color = False
    else:
        use_color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    init_colors(use_color)

    all_plugins = load_plugins()

    interactive = sys.stdin.isatty() and sys.stdout.isatty()

    if args.tool is None:
        if not interactive:
            sys.exit("error: --tool is required when not running interactively")
        args.tool = choose("Which tool?", sorted(TOOL_TARGETS))

    # Offer a single shortcut up front: if any selection is still unset and we'd
    # otherwise prompt for each, ask once whether to just use the defaults.
    # Accepting is equivalent to --defaults. The description mirrors the header
    # detail format and omits the copy/symlink mode under --status.
    unset = args.plugin is None or args.component is None or (not args.symlink and not args.status)
    if interactive and not args.defaults and unset:
        comps = ", ".join(sorted(args.component)) if args.component else "rules"
        defaults_desc = [f"plugin: {args.plugin or 'all'}", f"components: {comps}"]
        if not args.status:
            defaults_desc.append(f"mode: {'symlink' if args.symlink else 'copy'}")
        args.defaults = confirm(f"Use defaults ({' · '.join(defaults_desc)})?", default=True)

    # Selection prompts (plugin/component/symlink) fire interactively unless
    # --defaults is given, which uses each option's default without asking.
    # (--yes is separate: it only assumes "yes" to the per-item install/update
    # confirms below, not to these selection choices.)
    ask_optional = interactive and not args.defaults

    if args.plugin is None and ask_optional:
        picked = choose("Which plugin?", ["all"] + [p["name"] for p in all_plugins], default="all")
        if picked != "all":
            args.plugin = picked

    if args.component is None and ask_optional:
        args.component = choose("Which components?", ["rules", "skills", "agents"], default="rules", multi=True)

    # Symlink only affects writes, so skip the prompt in report-only --status mode.
    if not args.symlink and ask_optional and not args.status:
        args.symlink = confirm("Symlink instead of copy?", default=False)

    components = set(args.component) if args.component else {"rules"}
    plugins = select_plugins(all_plugins, args.plugin)
    jobs = plan_copies(plugins, components)
    if not jobs:
        print("Nothing to install for the given selection.")
        return

    base = Path.home() if args.global_scope else args.project_dir.resolve()
    targets = TOOL_TARGETS[args.tool]

    # First pass: classify and report every planned item.
    scope = "global" if args.global_scope else "project"
    title = ("📦 " if _USE_EMOJI else "") + f"Agentry — {args.tool}, {scope} scope ({base})"
    print(colorize(title, "cyan"))
    detail = [
        f"plugin: {args.plugin or 'all'}",
        f"components: {', '.join(sorted(components))}",
        f"mode: {'symlink' if args.symlink else 'copy'}",
    ]
    print(colorize(indent() + " · ".join(detail), "dim"))
    print()

    # Shared width so report tags and action labels share one aligned column.
    action_labels = ["would install", "would update"] if args.dry_run else (
        ["linked"] if args.symlink else ["installed", "updated"])
    label_width = max(len(s) for s in ["missing", "synced", "stale", *action_labels])

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
        print(report_line(state, rel, label_width))
        plan.append((component, src, dest, rel, state))

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
    drift = sum(1 for *_, state in plan if needs_action(state))
    if args.status:
        parts = [colorize(current_label, "green")]
        if drift:
            # Red if any item is stale (the more severe state), else yellow for
            # missing-only — matching the per-row report colors.
            stale = any(state in ("copied-stale", "stale-link") for *_, state in plan)
            parts.append(colorize(f"{drift} need attention", "red" if stale else "yellow"))
        unresolved = drift > 0
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
        unresolved = counts["skipped"] > 0
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
    sys.exit(code)
