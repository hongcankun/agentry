# Releases

Versioning, tagging, and changelog guidance.

## Semantic Versioning

Use `MAJOR.MINOR.PATCH` (see https://semver.org/):

- **MAJOR**: incompatible API changes.
- **MINOR**: backward-compatible new functionality.
- **PATCH**: backward-compatible bug fixes.

Pre-release and build metadata may be appended, e.g. `1.4.0-rc.1`.

## Tagging

Create annotated tags so the tag carries a message and author:

```
git tag -a v1.4.0 -m "Release 1.4.0"
git push origin v1.4.0
```

- Tag the commit that represents the released state.
- Use a consistent prefix (commonly `v`).
- Do not move or delete published tags; cut a new version instead.
- Push tags only after confirming the release is intentional and the target commit is correct.

## Annotated Tag Messages

A short tag message is enough for small releases when detailed notes live in a pull request, hosted release, or changelog:

```
Release v1.4.2
```

Add a body when the tag should carry standalone release context, or when the release includes breaking changes, migrations, compatibility notes, security fixes, or multiple user-visible changes:

```
Release v1.4.2

- Fix CLI install path detection on macOS.
- Add retry handling for marketplace downloads.
```

Use explicit sections such as `Breaking changes:`, `Migration:`, `Compatibility:`, or `Security:` only when the release needs that context. Avoid routine validation details in tag messages unless the repository uses tags as the primary release record.

## Changelog

- Maintain a human-readable changelog (e.g. `CHANGELOG.md`).
- Group entries by version and by type (Added, Changed, Fixed, Removed).
- Prefer the repository's existing release-note workflow when one exists.
- Do not maintain competing generated and hand-written release notes unless the repository defines which source wins.

## Release Notes and Changelog Tooling

For repositories that enforce Conventional Commits, prefer generating release notes from structured commit history or merged pull requests instead of hand-copying every change.

Common options:

- `git-cliff`: good fit for Conventional Commits. It generates changelogs from commit history and supports grouping by type, scope, breaking changes, templates, and tag ranges.
- `github-changelog-generator`: useful for GitHub-hosted projects that organize releases around pull requests, issues, labels, and milestones.
- GitHub Release Drafter: useful when teams want draft release notes maintained continuously from merged pull requests and labels, then published at release time.

Choose the source of truth deliberately:

- Commit-driven notes work best when commits are clean, conventional, and preserved on the release branch.
- Pull-request-driven notes work best when squash merges, labels, and PR titles carry the release semantics.
- If no tooling is configured, draft concise notes from the compare range, merged pull requests, and user-facing changes.

## Release steps (GitHub Flow example)

1. Ensure `main` is green (tests and CI pass).
2. Update the changelog and bump the version where it is declared.
3. Merge any release-prep changes into `main`.
4. Create and push an annotated tag.
5. Publish a release from the tag (release notes, artifacts) if applicable.
