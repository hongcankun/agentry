# Designs

This directory stores design proposals for accepted changes. A design proposal may be an inline note elsewhere, a lightweight design doc, or a full RFC; files in this directory are for written proposals that should remain discoverable after review.

## Index

| ID | Form | Title | Status | Answers |
| --- | --- | --- | --- | --- |
| _None yet_ |  |  |  |  |

## Convention

- Use one shared `docs/designs/` sequence for lightweight design docs and full RFCs; distinguish weight with `Form:` metadata, not separate folders or filename prefixes.
- Assign the next four-digit zero-padded ID by incrementing the highest existing ID in this index.
- Name files as `<id>-<short-kebab-title>.md`, for example `0001-behavioral-evaluation-authoring-artifacts.md`.
- Use `# Design <id>: <Title>` as the document title.
- Include metadata near the top: `ID`, `Form`, `Status`, `Answers`, and `Author(s)`.
- Keep `Status` current using one of: `Draft`, `In review`, `Accepted`, `Accepted with conditions`, `Rejected`, or `Superseded`.
- Link each design back to the accepted change request it answers through `Answers`.
- Supersede rather than delete accepted or reviewed designs; mark the older design `Superseded` and link to the replacement.
