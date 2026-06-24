---
description: Publish a prepared release by verifying the merged release state, tagging it, and optionally creating hosted release notes.
argument-hint: "[version] [target-ref]"
---

# Publish Release

Use this command after a release-prep commit or pull request has landed and the user wants help publishing the release.

## Inputs

- `[version]`: Optional release version. Accepts `1.4.0`, `v1.4.0`, or another repository-established version/tag naming pattern.
- `[target-ref]`: Optional commit or branch to publish. If omitted, use the current `HEAD` after confirming it is the intended released state.

If the version, tag name, target commit, release-note source, or publication action is unclear, ask one concise clarifying question before creating tags or mutating remote state.

## Workflow

1. Inspect repository state with `git status --short --branch`. Stop if there are uncommitted changes unless the user explicitly chooses how to handle them.
2. Identify the current branch and target commit:
   - use `git branch --show-current`;
   - use `git rev-parse --short <target-ref>` or `git rev-parse --short HEAD`;
   - use `git log -1 --oneline <target-ref>` to confirm the release commit.
3. Determine the release version and tag name from the input, repository files, or repository convention. Prefer `vX.Y.Z` when the project uses SemVer release tags with a `v` prefix.
4. Verify release notes before tagging:
   - look for configured release-note tooling such as `CHANGELOG.md`, `cliff.toml`, `.github/release-drafter.yml`, or host release workflows;
   - confirm the release notes include the target version when the repository keeps committed release notes;
   - do not generate or edit release notes in this command unless the repository explicitly releases directly from the current branch.
5. Check whether the tag already exists locally or remotely:
   - use `git tag --list <tag>`;
   - use `git ls-remote --tags origin <tag>` when a remote check is needed.
6. Draft the annotated tag message:
   - use `Release <tag>` for a small release where detailed notes live elsewhere;
   - add a concise body when the tag should carry standalone context, or when the release includes breaking changes, migrations, compatibility notes, security fixes, or multiple user-visible changes;
   - follow the repository's existing changelog or release-note tooling when one is configured instead of inventing a competing format.
7. Present the target commit, tag name, release-note source, and exact tag message before creating the tag. If the target, version, notes, and message are straightforward and local-only, create or verify the local annotated tag; stop and ask when any release input is questionable.
8. Create the local annotated tag when needed:
   - use `git tag -a <tag> <target-ref> -m "<subject>"` for a single-line message;
   - use a message file when the tag needs a body.
9. Ask for explicit confirmation before pushing the tag. Pushing a tag is shared remote state.
10. If confirmed, push only the tag with `git push origin <tag>`.
11. If the repository is hosted on GitHub and `gh` is available, offer to draft a GitHub Release from the generated release notes after the tag is pushed. Creating a draft requires explicit confirmation; publishing a non-draft release requires separate confirmation.
12. Verify the result:
   - use `git show --no-patch --format=fuller <tag>`;
   - if pushed, verify the remote tag with `git ls-remote --tags origin <tag>`;
   - if a hosted release draft was created, report its URL.

## Constraints

- Do not publish from a dirty worktree unless the user explicitly chooses a safe handling path.
- Do not overwrite, move, delete, or force-push tags unless the user explicitly asks and accepts the release-history risk.
- Do not push tags without explicit confirmation.
- Do not create or publish hosted releases, including drafts, without explicit confirmation.
- Do not edit release files; use `prepare-release` for release-prep commits.
- Do not claim tests, CI, or release publication passed unless verified.

## Output

Return:
- the release version, tag name, and target commit;
- release-note tooling detected and release-note verification result;
- whether the tag was created locally, already existed, or was pushed;
- any hosted release draft/publication action created, proposed, skipped, or blocked;
- the tag message used or proposed;
- validation performed, skipped, or blocked.
