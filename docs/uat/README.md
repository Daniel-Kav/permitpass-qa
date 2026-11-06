# User acceptance testing (UAT)

UAT is where **business users**, not testers, confirm PermitPass does what the county needs. The automated
suites prove the system works as built; UAT confirms it was built right for the people using it.

## Who takes part
| Role | Represents | Runs scripts |
| --- | --- | --- |
| Citizen tester | a business owner applying for a permit | UAT-01 to UAT-06 |
| Licensing officer | county staff reviewing applications | UAT-07 to UAT-10 |
| Inspector / member of the public | anyone checking a permit | UAT-11, UAT-12 |
| UAT lead | product owner | runs the session, records results, chairs sign-off |

## Environment
```bash
make up                                   # API + PostgreSQL + M-Pesa/KRA stubs
pip install httpx && python scripts/seed_uat.py   # sample data; prints certificate numbers and codes
```
Portal: <http://localhost:8000>. Accounts: `citizen@permitpass.test`, `officer@permitpass.test` (password `PermitPass!2026`).
Payments and KRA checks use the stubs; the special phone numbers and PINs are in each script and in `mocks/README.md`.

## Entry criteria
- [ ] All CI checks green on the release candidate (API on both databases, contract, E2E × 3 browsers, ZAP, perf smoke)
- [ ] No open Critical or High defects
- [ ] UAT environment up and seeded; testers have accounts and these scripts

## During the session
- Follow each script step by step; mark **Pass**, **Fail** or **Blocked** and note anything surprising, even if it passes
- Raise every failure as a GitHub issue with the **Defect** template, add the UAT script ID, and attach a screenshot
- The UAT lead triages severity on the day (`docs/defects/severity.md`)

## Exit criteria
- [ ] Every script run, with a result recorded
- [ ] 100% of **must-pass** scripts passed (marked ★)
- [ ] No open Critical or High defects; any Medium or Low have an agreed owner and date
- [ ] Sign-off form completed (`sign-off.md`)

Scripts: [`scripts.md`](scripts.md) · Sign-off: [`sign-off.md`](sign-off.md)
