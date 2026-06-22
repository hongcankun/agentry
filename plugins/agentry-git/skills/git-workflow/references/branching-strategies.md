# Branching strategies

Guidance for selecting and applying a branching model.

## GitHub Flow

- `main` is always deployable.
- Create a short-lived branch from `main` for each change.
- Open a pull request, review, and merge back into `main`.
- Deploy from `main` after merge.

Best for: most teams, continuous delivery, web applications.

## Trunk-Based Development

- Everyone integrates into a single trunk (`main`) frequently.
- Branches live for hours to a day, not weeks.
- Incomplete work hides behind feature flags rather than long-lived branches.

Best for: high-velocity teams with strong automated testing and CI.

## GitFlow

- Long-lived `main` (released code) and `develop` (integration).
- `feature/*` branches off `develop`.
- `release/*` branches stabilize a release, then merge into `main` and `develop`.
- `hotfix/*` branches off `main` for urgent production fixes.

Best for: scheduled, versioned releases; software shipped to customers in distinct versions.

## Selection guide

| Strategy     | Team size      | Release cadence        | Best for                                   |
| ------------ | -------------- | ---------------------- | ------------------------------------------ |
| GitHub Flow  | Small–medium   | Continuous             | Most projects, web apps                    |
| Trunk-Based  | Any (with CI)  | Continuous / on-demand | High-velocity teams, strong test coverage  |
| GitFlow      | Medium–large   | Scheduled / versioned  | Versioned products, enterprise releases    |

## Branch naming conventions

Use a `type/short-description` form with hyphenated lowercase descriptions:

- `feat/user-login`
- `fix/null-pointer-on-logout`
- `docs/api-readme`
- `refactor/payment-service`
- `release/1.4.0`
- `hotfix/1.4.1`

Optionally prefix with an issue id: `feat/123-user-login`.

For feature and fix work, keep the branch `type` consistent with the Conventional Commit `type` the branch's commits will carry (`feat`, `fix`, `docs`, `refactor`, …), so the branch name and its commits agree. `release/*` and `hotfix/*` are GitFlow branch types with no commit-type equivalent and are exempt from this alignment.

## Branch hygiene

- Keep branches small and focused on one change.
- Rebase or merge `main` into long-running branches regularly to limit drift.
- Delete branches after they merge (`git branch -d <branch>` locally; remove the remote branch as well).
