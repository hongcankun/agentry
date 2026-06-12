#!/usr/bin/env python3
"""Generate Trae (traecli/coco) plugin packaging from the canonical manifest.

Reads ``agentry.json`` (the tool-agnostic source of truth) and writes the
Trae-native marketplace catalog derived from it:

- ``.trae-plugin/marketplace.json`` — the marketplace catalog, in Trae's schema.

Trae also reads ``.claude-plugin/marketplace.json`` as a fallback, but its
documented schema differs from Claude Code's (notably ``owner`` is a string),
so Agentry ships a first-class Trae catalog too.

Trae plugins auto-detect component directories (``skills/``, ``agents/``, …) and
do not use a per-plugin manifest file; metadata comes from the marketplace
entry. A per-plugin ``traecli.yaml`` is only needed for MCP servers, hooks,
models, or tool-permission rules — none of which Agentry's plugins currently
have — so this generator emits only the catalog.

These files are GENERATED; edit ``agentry.json`` and re-run. Use ``--check`` in
CI to verify the committed files are up to date.
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "agentry.json"
MARKETPLACE = REPO_ROOT / ".trae-plugin" / "marketplace.json"

GENERATED_NOTE = "GENERATED from agentry.json by scripts/generate_trae.py. Do not edit by hand."


def load_manifest():
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"error: manifest not found at {MANIFEST}")
    except json.JSONDecodeError as exc:
        sys.exit(f"error: invalid JSON in {MANIFEST}: {exc}")


def owner_string(manifest):
    """Trae's owner field is a string; derive it from the manifest owner."""
    owner = manifest.get("owner")
    if isinstance(owner, dict):
        return owner.get("name", "")
    return owner or ""


def build_marketplace(manifest):
    catalog = {
        "$generated": GENERATED_NOTE,
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
        description="Generate Trae plugin packaging from agentry.json.",
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

    if args.check:
        if changed:
            print("Out of date (run scripts/generate_trae.py):")
            for path in changed:
                print(f"  {path}")
            sys.exit(1)
        print("Trae packaging is up to date.")
    elif not changed:
        print("Already up to date.")


if __name__ == "__main__":
    main()
