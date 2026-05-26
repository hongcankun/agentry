# Conventional Commits 1.0.0

## Summary
This specification is a lightweight convention on top of commit messages, creating an explicit history and dovetailing with SemVer by describing features, fixes, and breaking changes.

The commit message should be structured as follows:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Key structural elements to communicate intent:
1. **fix:** a commit of this type patches a codebase bug, correlating with SemVer’s PATCH.
2. **feat:** a commit of this type introduces a new codebase feature, correlating with SemVer’s MINOR.
3. **BREAKING CHANGE:** a commit with a `BREAKING CHANGE:` footer, or a `!` after type/scope, introduces a breaking API change, correlating with SemVer’s MAJOR; it can be part of any type.
4. Other types are allowed, for example `build:`, `chore:`, `ci:`, `docs:`, `style:`, `refactor:`, `perf:`, `test:`, etc.
5. Footers other than `BREAKING CHANGE: <description>` may follow a git trailer-like format.

Additional types are not mandated and have no implicit SemVer effect unless including a BREAKING CHANGE. A scope may be added after type in parentheses for context, e.g., `feat(parser): add ability to parse arrays`.

## Examples

### Commit message with description and breaking change footer
```
feat: allow provided config object to extend other configs

BREAKING CHANGE: `extends` key in config file is now used for extending other config files
```

### Commit message with `!` to draw attention to breaking change
```
feat!: send an email to the customer when a product is shipped
```

### Commit message with scope and `!` to draw attention to breaking change
```
feat(api)!: send an email to the customer when a product is shipped
```

### Commit message with both `!` and BREAKING CHANGE footer
```
feat!: drop support for Node 6

BREAKING CHANGE: use JavaScript features not available in Node 6.
```

### Commit message with no body
```
docs: correct spelling of CHANGELOG
```

### Commit message with scope
```
feat(lang): add Polish language
```

### Commit message with multi-paragraph body and multiple footers
```
fix: prevent racing of requests

Introduce a request id and a reference to latest request. Dismiss
incoming responses other than from latest request.

Remove timeouts which were used to mitigate the racing issue but are
obsolete now.

Reviewed-by: Z
Refs: #123
```

## Specification
The key words “MUST”, “MUST NOT”, “REQUIRED”, “SHALL”, “SHALL NOT”, “SHOULD”, “SHOULD NOT”, “RECOMMENDED”, “MAY”, and “OPTIONAL” are interpreted as described in RFC 2119.

1. Commits MUST be prefixed with a noun type, followed by OPTIONAL scope, OPTIONAL `!`, and REQUIRED terminal colon and space.
2. The `feat` type MUST be used for new application/library features.
3. The `fix` type MUST be used for application/library bug fixes.
4. A scope MAY follow a type, consisting of a noun describing a codebase section in parentheses.
5. A short summary description MUST immediately follow the colon/space after type/scope.
6. A longer contextual body MAY be provided after one blank line following the description.
7. The body is free-form and MAY have any number of newline-separated paragraphs.
8. One or more footers MAY be provided after one blank line following the body; each has a word token, then `:<space>` or `<space>#` separator, then a string value.
9. A footer’s token MUST use `-` instead of whitespace, except `BREAKING CHANGE` MAY also be used.
10. A footer’s value MAY contain spaces/newlines; parsing ends when next valid token/separator is seen.
11. Breaking changes MUST be indicated in type/scope prefix or footer.
12. A footer breaking change MUST be uppercase `BREAKING CHANGE`, colon, space, and description.
13. A prefix breaking change MUST have `!` right before `:`; if used, `BREAKING CHANGE:` MAY be omitted, with the description summarizing it.
14. Types other than `feat`/`fix` MAY be used.
15. Information units are NOT case-sensitive to implementors, EXCEPT `BREAKING CHANGE` MUST be uppercase.
16. `BREAKING-CHANGE` MUST be synonymous with `BREAKING CHANGE` as a footer token.

## Why Use Conventional Commits
- Automatically generate CHANGELOGs.
- Automatically determine SemVer bumps.
- Communicate change nature to teammates, public, stakeholders.
- Trigger build/publish processes.
- Make projects easier to contribute to via structured history.

## FAQ
### Initial development phase commits
Proceed as if the product is already released—somebody is likely using it.
### Casing for commit title types
Any casing works, but consistency is best.
### Commits fitting multiple types
Split into multiple commits whenever possible.
### Discouraging rapid iteration?
No—it discourages *disorganized* rapid movement and helps long-term cross-project work.
### Limiting commit types?
No—it encourages certain types (like fixes) and lets teams create/change their own over time.
### SemVer relation
`fix` → PATCH, `feat` → MINOR, any BREAKING CHANGE → MAJOR.
### Versioning extensions
Use SemVer for your own extensions.
### Accidental wrong commit type
- Spec-adjacent wrong type (e.g., `fix` instead of `feat`): use `git rebase -i` before merge/release; post-release depends on tools/processes.
- Non-spec type (e.g., `feet`): not catastrophic, just missed by spec-based tools.
### Requiring all contributors to use it
No—lead maintainers can clean up messages with squash workflows or PR forms.
### Revert commits
No explicit spec definition—use tool flexibility; one recommendation is `revert` type and footer with reverted SHA refs.

---

License: Creative Commons - CC BY 3.0
