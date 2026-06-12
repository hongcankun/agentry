#!/usr/bin/env python3
"""Generate Claude Code plugin packaging from the canonical manifest.

Reads ``agentry.json`` (the tool-agnostic source of truth) and writes the
Claude-Code-specific packaging derived from it:

- ``.claude-plugin/marketplace.json`` — the marketplace catalog.
- ``plugins/<name>/.claude-plugin/plugin.json`` — one manifest per plugin.

Claude Code is just one packaging target; these files are GENERATED and should
not be hand-edited. Edit ``agentry.json`` and re-run this script instead. Run
with ``--check`` in CI to verify the committed files are up to date.
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "agentry.json"
PLUGINS_DIR = REPO_ROOT / "plugins"
MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"

GENERATED_NOTE = "GENERATED from agentry.json by scripts/generate_claude.py. Do not edit by hand."


def load_manifest():
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"error: manifest not found at {MANIFEST}")
    except json.JSONDecodeError as exc:
        sys.exit(f"error: invalid JSON in {MANIFEST}: {exc}")


def build_marketplace(manifest):
    catalog = {
        "$schema": "https://json.schemastore.org/claude-code-marketplace.json",
        "$generated": GENERATED_NOTE,
        "name": manifest["name"],
        "description": manifest.get("description", ""),
        "owner": manifest.get("owner", {}),
        "metadata": {"pluginRoot": "./plugins"},
        "plugins": [],
    }
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


def build_plugin_manifest(manifest, plugin):
    out = {
        "$generated": GENERATED_NOTE,
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


def main():
    parser = argparse.ArgumentParser(
        description="Generate Claude Code plugin packaging from agentry.json.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify generated files are up to date without writing; exit 1 if not.",
    )
    args = parser.parse_args()

    manifest = load_manifest()
    changed = []

    write_or_check(MARKETPLACE, serialize(build_marketplace(manifest)), args.check, changed)
    for plugin in manifest["plugins"]:
        path = PLUGINS_DIR / plugin["name"] / ".claude-plugin" / "plugin.json"
        write_or_check(path, serialize(build_plugin_manifest(manifest, plugin)), args.check, changed)

    if args.check:
        if changed:
            print("Out of date (run scripts/generate_claude.py):")
            for path in changed:
                print(f"  {path}")
            sys.exit(1)
        print("Claude Code packaging is up to date.")
    elif not changed:
        print("Already up to date.")


if __name__ == "__main__":
    main()
