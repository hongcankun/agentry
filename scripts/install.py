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
    python3 scripts/install.py --tool claude --scope global --dry-run
"""

import argparse
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


def install_one(src, dest, dry_run, force, symlink):
    """Copy or symlink src to dest. Returns 'installed' or 'skipped'."""
    # Safety: never let dest operations touch the source itself (e.g. when dest
    # is an existing symlink pointing back into the source tree).
    if dest.is_symlink():
        link_target = (dest.parent / os.readlink(dest)).resolve()
        same = link_target == src.resolve()
    else:
        same = dest.exists() and dest.resolve() == src.resolve()
    if same and not force:
        print(f"skip (already linked/identical): {dest}")
        return "skipped"

    exists = dest.exists() or dest.is_symlink()
    if exists and not force:
        print(f"skip (exists): {dest}  [use --force to overwrite]")
        return "skipped"
    if dry_run:
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
        print(f"linked: {dest}  ->  {src}")
    elif src.is_dir():
        shutil.copytree(src, dest)
        print(f"installed: {dest}")
    else:
        shutil.copy2(src, dest)
        print(f"installed: {dest}")
    return "installed"


def main():
    parser = argparse.ArgumentParser(
        description="Install Agentry skills, agents, and rules into an AI coding tool's directories.",
    )
    parser.add_argument("--tool", required=True, choices=sorted(TOOL_TARGETS), help="Target AI coding tool.")
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
        "--scope",
        choices=("project", "global"),
        default="project",
        help="Install into the project dirs or the user/global dirs (default: project).",
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
        "--symlink",
        action="store_true",
        help="Symlink components back to this checkout instead of copying, so they track the "
        "source with no drift. The link target is relative. Not portable to Windows checkouts.",
    )
    args = parser.parse_args()

    components = set(args.component) if args.component else {"rules"}
    plugins = select_plugins(load_plugins(), args.plugin)
    jobs = plan_copies(plugins, components)
    if not jobs:
        print("Nothing to install for the given selection.")
        return

    base = Path.home() if args.scope == "global" else args.project_dir.resolve()
    targets = TOOL_TARGETS[args.tool]

    counts = {"installed": 0, "skipped": 0}
    for component, src, rel_dest in jobs:
        if not src.exists():
            sys.exit(f"error: source missing: {src}")
        # Do not resolve() the full path: if dest is already a symlink into the
        # source tree, resolving would point operations (e.g. unlink) at the
        # source itself. base is already absolute.
        dest = base / targets[component] / rel_dest
        counts[install_one(src, dest, args.dry_run, args.force, args.symlink)] += 1

    verb = "would install" if args.dry_run else "installed"
    summary = f"{verb} {counts['installed']} item(s) into {base} ({args.tool})"
    if counts["skipped"]:
        summary += f", skipped {counts['skipped']} existing"
    print(summary)


if __name__ == "__main__":
    main()
