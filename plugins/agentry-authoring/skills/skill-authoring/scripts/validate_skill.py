#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

ALLOWED_FIELDS = {"name", "description"}
OPTIONAL_DIRS = {"scripts", "references", "assets"}
KEBAB_CASE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ValidationError(Exception):
    pass


def parse_frontmatter(text: str) -> dict:
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        raise ValidationError("SKILL.md must start with YAML frontmatter delimited by ---")

    try:
        end = lines[1:].index("---") + 1
    except ValueError as exc:
        raise ValidationError("YAML frontmatter must end with ---") from exc

    data = {}
    for raw in lines[1:end]:
        if not raw.strip():
            continue
        if ":" not in raw:
            raise ValidationError(f"Invalid YAML line: {raw}")
        key, value = raw.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key not in ALLOWED_FIELDS:
            raise ValidationError(f"Unsupported metadata field: {key}")
        if not value:
            raise ValidationError(f"Metadata field '{key}' cannot be empty")
        data[key] = value

    for required in ("name", "description"):
        if required not in data:
            raise ValidationError(f"Missing required metadata field: {required}")

    if not KEBAB_CASE.fullmatch(data["name"]):
        raise ValidationError("Metadata 'name' must use kebab-case")

    return data


def validate_structure(skill_dir: Path) -> None:
    entries = {p.name for p in skill_dir.iterdir()}
    if "SKILL.md" not in entries:
        raise ValidationError("Missing SKILL.md")

    for entry in skill_dir.iterdir():
        if entry.name == "SKILL.md":
            continue
        if entry.name.startswith("."):
            continue
        if entry.is_dir() and entry.name in OPTIONAL_DIRS:
            continue
        # Allow extra packaged content, but forbid obvious junk files.
        if entry.is_file() and entry.suffix in {".tmp", ".swp", ".bak"}:
            raise ValidationError(f"Unexpected temporary file: {entry.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an Agent Skill folder.")
    parser.add_argument("skill_directory", help="Path to the skill directory")
    args = parser.parse_args()

    skill_dir = Path(args.skill_directory).expanduser().resolve()
    if not skill_dir.exists() or not skill_dir.is_dir():
        raise SystemExit(f"Skill directory not found: {skill_dir}")

    validate_structure(skill_dir)
    metadata = parse_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))

    print("Validation passed")
    print(f"name: {metadata['name']}")
    print(f"description: {metadata['description']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        print(f"Validation failed: {exc}")
        raise SystemExit(1)
