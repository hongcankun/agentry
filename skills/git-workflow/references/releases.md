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

## Changelog

- Maintain a human-readable changelog (e.g. `CHANGELOG.md`).
- Group entries by version and by type (Added, Changed, Fixed, Removed).
- When commits follow Conventional Commits, the changelog can be generated from history.

## Release steps (GitHub Flow example)

1. Ensure `main` is green (tests and CI pass).
2. Update the changelog and bump the version where it is declared.
3. Merge any release-prep changes into `main`.
4. Create and push an annotated tag.
5. Publish a release from the tag (release notes, artifacts) if applicable.
