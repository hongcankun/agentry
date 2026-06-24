---
description: Create or verify an annotated release tag, and push it only after explicit confirmation.
argument-hint: "[version] [target-ref]"
---

# Tag Release

Use this command when the user wants help creating or verifying a git release tag.

## Inputs

- `[version]`: Optional release version. Accepts `1.4.0`, `v1.4.0`, or another repository-established tag naming pattern.
- `[target-ref]`: Optional commit, branch, or tag target. If omitted, use the current `HEAD` after confirming it is the intended released state.

If the version, tag name, target commit, or release-note source is unclear, ask one concise clarifying question before creating a tag.

## Workflow

1. Inspect repository state with `git status --short --branch`. Stop if there are uncommitted changes unless the user explicitly chooses how to handle them.
2. Identify the current branch and target commit:
   - use `git branch --show-current`;
   - use `git rev-parse --short <target-ref>` or `git rev-parse --short HEAD`;
   - use `git log -1 --oneline <target-ref>` to confirm the release commit.
3. Determine the tag name from the input or repository convention. Prefer `vX.Y.Z` when the project uses SemVer release tags with a `v` prefix.
4. Inspect existing release conventions before drafting tag metadata:
   - check existing tags with `git tag --list`;
   - look for release-note or changelog configuration such as `CHANGELOG.md`, `cliff.toml`, `.github/release-drafter.yml`, or GitHub release workflows when relevant.
5. Check whether the tag already exists locally or remotely:
   - use `git tag --list <tag>`;
   - use `git ls-remote --tags origin <tag>` when a remote check is needed.
6. Draft the annotated tag message:
   - use `Release <tag>` for a small release where detailed notes live elsewhere;
   - add a concise body when the tag should carry standalone context, or when the release includes breaking changes, migrations, compatibility notes, security fixes, or multiple user-visible changes;
   - follow the repository's existing changelog or release-note tooling when one is configured instead of inventing a competing format.
7. Present the target commit, tag name, and exact tag message before creating the tag. If the target and message are straightforward and local-only, create the local annotated tag; stop and ask when the release target, version, or message is questionable.
8. Create the local annotated tag:
   - use `git tag -a <tag> <target-ref> -m "<subject>"` for a single-line message;
   - use a message file when the tag needs a body.
9. Ask for explicit confirmation before pushing the tag. Pushing a tag is shared remote state.
10. If confirmed, push only the tag with `git push origin <tag>`.
11. Verify the result:
   - use `git show --no-patch --format=fuller <tag>`;
   - if pushed, verify the remote tag with `git ls-remote --tags origin <tag>`.

## Constraints

- Do not create a tag on a dirty worktree unless the user explicitly chooses a safe handling path.
- Do not overwrite, move, delete, or force-push tags unless the user explicitly asks and accepts the release-history risk.
- Do not push tags without explicit confirmation.
- Do not invent detailed release notes when the repository has configured release-note tooling; follow the existing workflow.
- Do not claim tests or CI passed unless verified.

## Output

Return:
- the tag name and target commit;
- whether the tag was created locally, already existed, or was pushed;
- the tag message used or proposed;
- release-note or changelog tooling detected;
- validation performed, skipped, or blocked.
