#!/usr/bin/env python3
import argparse
import re
import sys

# Valid types (common ones from Conventional Commits)
VALID_TYPES = {
    "feat", "fix", "docs", "style", "refactor", "perf", "test", "chore",
    "build", "ci", "revert"
}

# Regex for Conventional Commits (v1.0.0) - matches the first line (type/scope/breaking/description)
CONVENTIONAL_COMMITS_REGEX = re.compile(
    r"^"
    r"(?P<type>[a-zA-Z]+)"
    r"(?:\((?P<scope>[^\)]+)\))?"
    r"(?P<breaking>!)?"
    r": "
    r"(?P<description>[^\n]+)"
    r"$"
)

# Regex for a single footer line (token-separator-value)
FOOTER_REGEX = re.compile(
    r"^"
    r"(?P<token>[A-Za-z0-9-]+|BREAKING CHANGE)"
    r"(?P<separator>: | #)"
    r"(?P<value>.*)"
    r"$"
)


def validate_commit_message(commit_message: str) -> bool:
    """Validate a commit message against Conventional Commits v1.0.0."""
    # Strip leading/trailing whitespace
    commit_message = commit_message.strip()

    # Split into lines
    lines = commit_message.split("\n")
    if not lines:
        print("❌ Commit message is empty.")
        return False

    # Validate the first line (type/scope/breaking/description)
    first_line = lines[0]
    match = CONVENTIONAL_COMMITS_REGEX.match(first_line)
    if not match:
        print("❌ First line does not match Conventional Commits structure.")
        print("   Expected: <type>(<scope>): <description>")
        return False

    # Extract groups from first line
    commit_type = match.group("type")
    description = match.group("description")

    # Validate type
    if commit_type.lower() not in VALID_TYPES:
        print(f"❌ Invalid type '{commit_type}'. Valid types are: {', '.join(sorted(VALID_TYPES))}")
        return False

    # Validate the subject line: keep it short. 72 is the hard ceiling,
    # matching Git's terminal-friendly convention (~50 aim, 72 max) so the
    # validator agrees with the SKILL.md guidance instead of contradicting it.
    if len(first_line) > 72:
        print("❌ Subject line should be 72 characters or less.")
        return False

    # Validate description: should not start with uppercase, no trailing dot
    if description[0].isupper():
        print("❌ Description should not start with an uppercase letter.")
        return False

    if description.endswith("."):
        print("❌ Description should not end with a dot.")
        return False

    # Process the rest of the lines (body and footers)
    # Body is everything until the first footer line
    # Footers are consecutive lines that match FOOTER_REGEX, possibly with multi-line values
    in_footer = False
    current_footer_token = None
    current_footer_value = []
    footers = []

    for line in lines[1:]:
        stripped_line = line.strip()

        if not stripped_line:
            # Empty line: if we were in a footer, this ends the footer's value
            if in_footer:
                footers.append((current_footer_token, "\n".join(current_footer_value).strip()))
                in_footer = False
            continue

        footer_match = FOOTER_REGEX.match(stripped_line)
        if footer_match:
            # This is a new footer line
            if in_footer:
                # Save the previous footer
                footers.append((current_footer_token, "\n".join(current_footer_value).strip()))
            # Start new footer
            current_footer_token = footer_match.group("token")
            current_footer_value = [footer_match.group("value")]
            in_footer = True
        else:
            if in_footer:
                # This is a continuation of the current footer's value
                current_footer_value.append(stripped_line)
            else:
                # This is part of the body (no validation needed for body content)
                pass

    # If we were still in a footer at the end, save it
    if in_footer:
        footers.append((current_footer_token, "\n".join(current_footer_value).strip()))

    # Validate footers
    for token, _ in footers:
        if token != "BREAKING CHANGE" and " " in token:
            print(f"❌ Invalid footer token '{token}'. Footer tokens must use '-' instead of spaces (except BREAKING CHANGE).")
            return False

    # Check if there's a breaking change (either in the prefix or in a footer)
    has_breaking_change = match.group("breaking") is not None
    for token, _ in footers:
        if token in ("BREAKING CHANGE", "BREAKING-CHANGE"):
            has_breaking_change = True
            break

    print("✅ Commit message follows Conventional Commits!")
    if has_breaking_change:
        print("⚠️  Breaking change detected (bumps SemVer MAJOR).")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a commit message against Conventional Commits.")
    parser.add_argument("commit_message", help="Commit message to validate (or path to file with -f)")
    parser.add_argument("-f", "--file", action="store_true", help="Treat commit_message as a file path")
    args = parser.parse_args()

    if args.file:
        with open(args.commit_message, encoding="utf-8") as f:
            commit_message = f.read()
    else:
        commit_message = args.commit_message

    success = validate_commit_message(commit_message)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
