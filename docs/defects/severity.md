# Defect severity

| Severity | Definition | PermitPass example |
| --- | --- | --- |
| Critical | Money, security or legal validity is wrong; no workaround | A duplicate M-Pesa callback credits the payment twice |
| High | A core journey is blocked or produces a wrong result | A revoked certificate still shows as valid on the verify page |
| Medium | A feature misbehaves but a workaround exists | Officer can't filter applications by date; can still search by name |
| Low | Cosmetic or minor wording issue | Fee shows as "2500" instead of "KES 2,500" |

Release rule: no open Critical or High defects at go/no-go.
