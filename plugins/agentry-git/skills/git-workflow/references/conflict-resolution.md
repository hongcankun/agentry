# Conflict resolution

Resolve merge and rebase conflicts deliberately.

## Steps

1. Start the integration (`git merge <branch>` or `git rebase <branch>`).
2. Run `git status` to see which files conflict.
3. Open each conflicted file. Conflict markers look like:

   ```
   <<<<<<< HEAD
   current branch content
   =======
   incoming content
   >>>>>>> other-branch
   ```

4. Edit to the correct combined result and remove all markers.
5. Stage resolved files with `git add <file>`.
6. Continue:
   - Rebase: `git rebase --continue`
   - Merge: commit the merge (`git commit`).
7. Run tests to confirm the resolution is correct.

## Tools

- `git mergetool` launches a configured visual merge tool.
- `git checkout --ours <file>` / `--theirs <file>` takes one full side when that is genuinely correct. During a rebase, "ours" and "theirs" are inverted relative to a merge, so verify before using.

## When unsure

- Abort and reassess rather than committing a guessed resolution:
  - `git merge --abort`
  - `git rebase --abort`

## Prevention

- Integrate the base branch into long-lived branches frequently.
- Keep branches small and short-lived.
- Coordinate on files that multiple people edit heavily.
- Format and structure code consistently to reduce noise conflicts.
