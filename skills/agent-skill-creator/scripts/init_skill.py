#!/usr/bin/env python3
import argparse
from pathlib import Path

SKILL_TEMPLATE = """---
name: {name}
description: Describe what this skill is, what it can do, and when to use it.
---

# {title}

Replace this template with concise, actionable instructions.

## When to use

Describe the trigger situations.

## Workflow

1. Define the task boundary.
2. Execute the core steps.
3. Validate the result.

## References

Add relative paths to files in `references/` when needed.
"""


def to_title(name: str) -> str:
    return " ".join(part.capitalize() for part in name.split("-"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize an Agent Skill folder.")
    parser.add_argument("skill_name", help="Skill name in kebab-case")
    parser.add_argument("--path", default=".", help="Output directory")
    args = parser.parse_args()

    skill_dir = Path(args.path).expanduser().resolve() / args.skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    for subdir in ("scripts", "references", "assets"):
        (skill_dir / subdir).mkdir(exist_ok=True)

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        skill_md.write_text(
            SKILL_TEMPLATE.format(
                name=args.skill_name,
                title=to_title(args.skill_name),
            ),
            encoding="utf-8",
        )

    print(f"Initialized skill at: {skill_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
