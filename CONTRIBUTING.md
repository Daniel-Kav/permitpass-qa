# Contributing

Every change follows the same path: **issue → branch → pull request → CI green → merge**.

## Branches
| Prefix | Use for | Example |
| --- | --- | --- |
| `feat/` | New behaviour | `feat/jwt-auth` |
| `fix/` | Defect fixes (link the defect issue) | `fix/duplicate-payment` |
| `test/` | Tests or test tooling only | `test/pagination-boundaries` |
| `ci/` | Pipeline changes | `ci/postgres-matrix` |
| `chore/`, `docs/` | Maintenance, documentation | `docs/test-strategy` |

`main` is always releasable. Branches are short-lived and merged with a merge commit so history shows each feature.

## Commits
[Conventional Commits](https://www.conventionalcommits.org/): `feat(api): add audit trail`, `test(auth): cover expired tokens`, `fix: ...`.

## Pull requests
- Use the PR template and link the issue with `Closes #N`.
- CI must pass: API tests (SQLite + PostgreSQL), E2E, accessibility, perf smoke.
- New behaviour ships with tests, including negative and boundary cases.

## Defects
Raise with the **Defect** issue template; set severity using `docs/defects/severity.md`.

## Releasing
1. Open a `chore/release-vX.Y.Z` PR that adds a `## [X.Y.Z] - date: Title` section to `CHANGELOG.md`.
2. Merge it once CI is green, then tag `main`: `git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z`.
   (Or publish a release for the new tag in the GitHub UI.)
3. The **Release** workflow publishes (or updates) the GitHub release using that CHANGELOG section as the notes.
