---
description: Prepare a project release commit by updating version, generated metadata, and release notes.
argument-hint: "[version] [target-ref]"
---

# Prepare Release

Use this command when the user wants help preparing the local release commit before opening a release pull request.

## Inputs

- `[version]`: Optional release version. Accepts `1.4.0`, `v1.4.0`, or another repository-established version/tag naming pattern.
- `[target-ref]`: Optional commit or branch to inspect when recommending a release version. If omitted, inspect the current `HEAD`.

If the version, target range, release-note source, or release-prep commit scope is unclear, ask one concise clarifying question before changing files or committing.

## Workflow

1. Inspect repository state with `git status --short --branch`. Stop if there are uncommitted changes unless the user explicitly chooses how to handle them.
2. Identify the current branch, target commit, and latest release tag:
   - use `git branch --show-current`;
   - use `git rev-parse --short <target-ref>` or `git rev-parse --short HEAD`;
   - use `git log -1 --oneline <target-ref>` to confirm the release commit;
   - use `git tag --list` to identify existing release tags.
3. Determine the release version from the input, repository files, or repository convention. Prefer `X.Y.Z` in version files and `vX.Y.Z` only for tag names.
4. Inspect unreleased changes since the previous release tag and recommend a version bump when the repository uses Conventional Commits:
   - breaking changes imply a major bump;
   - `feat` commits imply a minor bump;
   - `fix`, `perf`, or smaller changes imply a patch bump;
   - present the recommendation and the evidence before editing version files.
5. Inspect existing release-note conventions before editing release files:
   - look for release-note or changelog configuration such as `CHANGELOG.md`, `cliff.toml`, `.github/release-drafter.yml`, or host release workflows when relevant;
   - if configured release-note tooling exists, use it instead of inventing competing notes.
6. Update release files only when the target version and release-note source are clear:
   - update project version files only when the user asked for release preparation and the intended version is confirmed or unambiguous;
   - update `CHANGELOG.md` or equivalent generated notes using the repository's configured tooling when applicable;
   - regenerate derived packaging when version files feed generated metadata;
   - do not bump per-plugin/package versions unless the repository release workflow explicitly calls for it.
7. Validate release-prep files using the repository's normal checks for generated metadata and release notes. If checks fail, report the failure and do not commit.
8. Create a focused local release-prep commit when release files changed and the scope is clear:
   - inspect the diff and stage only release files such as project version files, generated metadata affected by the version, and generated changelog or release-note files;
   - use a Conventional Commit such as `chore(release): prepare vX.Y.Z`;
   - because the commit is local and reversible, proceed when the changed files and message are unambiguous; stop when unrelated changes are present.
9. For PR-based workflows, run `prepare-pr` next and use `publish-release` only after the release PR is merged.
10. Verify the result with `git log -1 --oneline` and `git status --short --branch`.

## Constraints

- Do not create a release-prep commit that includes unrelated changes.
- Do not create tags, push tags, or create hosted releases; those belong to `publish-release`.
- Do not invent detailed release notes when the repository has configured release-note tooling; follow the existing workflow.
- Do not claim tests or CI passed unless verified.

## Output

Return:
- the release version and recommended bump, if applicable;
- the release-prep commit hash and subject when created;
- release-note tooling detected and files changed or proposed;
- the recommended next steps, usually `prepare-pr`, merge, then `publish-release`;
- validation performed, skipped, or blocked.
