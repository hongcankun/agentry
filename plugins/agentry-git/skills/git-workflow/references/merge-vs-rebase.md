# Merge vs rebase

Decide how to integrate one branch into another.

## The core difference

- **Merge** combines two branches with a merge commit, preserving the true, branching history.
- **Rebase** replays your commits on top of another branch, producing a linear history but rewriting commit hashes.

## When to merge

- Integrating a shared branch that others may have based work on.
- Bringing a completed feature branch into `main` (a merge commit records the integration point).
- Any time preserving the actual sequence of events matters.

## When to rebase

- Updating your own local, unpushed branch onto the latest `main` before opening or updating a PR.
- Cleaning up local commits (`git rebase -i`) before sharing them.
- Keeping a feature branch's history linear and easy to review.

## The golden rule

**Never rebase commits that exist outside your local repository** — that is, shared, pushed, or protected branches. Rewriting published history forces everyone else to reconcile divergent history.

If you must update a pushed branch that is solely yours after rebasing, use:

```
git push --force-with-lease
```

`--force-with-lease` refuses the push if the remote moved unexpectedly (e.g. a teammate pushed), unlike `--force`, which overwrites unconditionally.

## Typical rebase workflow

```
git checkout feature/login
git fetch origin
git rebase origin/main
# resolve any conflicts, then:
git rebase --continue
git push --force-with-lease
```

## Decision summary

| Situation                                   | Use     |
| ------------------------------------------- | ------- |
| Branch is shared / pushed / protected       | Merge   |
| Integrating a finished feature into `main`  | Merge   |
| Local-only branch, syncing with `main`      | Rebase  |
| Tidying local commits before a PR           | Rebase  |
| In doubt                                     | Merge   |

## Squash on merge

Many teams squash a feature branch into a single commit when merging the PR. This keeps `main` history concise while leaving the branch's detailed commits in the PR record. Choose per repository convention.
