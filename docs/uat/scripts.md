# UAT scripts

Mark each step **P** (pass), **F** (fail) or **B** (blocked). ★ = must pass for sign-off.

## Citizen

### UAT-01 ★ Apply for a permit
| # | Action | Expected result | P/F/B | Notes |
| --- | --- | --- | --- | --- |
| 1 | Log in as `citizen@permitpass.test` | *My applications* opens | | |
| 2 | Enter business name **Mombasa Spice Traders**, KRA PIN **A123456789Z**, press *Create application* | "created as a draft" message; row shows **draft** | | |
| 3 | Press *Submit* on that row | Status becomes **submitted**; button changes to *Pay KES 2,500* | | |

### UAT-02 ★ Pay by M-Pesa
| # | Action | Expected result | P/F/B | Notes |
| --- | --- | --- | --- | --- |
| 1 | On a **submitted** application press *Pay KES 2,500* | A phone-number field appears, focused | | |
| 2 | Enter **0712 345 678**, press *Send payment request* | "Payment request sent…"; status **payment_pending**; "Check your phone…" | | |
| 3 | Wait (do not refresh) | Within a few seconds the status becomes **paid**, with "Payment received" | | |

### UAT-03 Payment cancelled on the phone
| # | Action | Expected result | P/F/B | Notes |
| --- | --- | --- | --- | --- |
| 1 | Pay a submitted application with **0700 000 032** | Status goes to payment_pending, then back to **submitted** | | |
| 2 | Read the row | "Payment failed: Request cancelled by user (M-Pesa code 1032)" | | |
| 3 | Pay again with 0712 345 678 | Becomes **paid**; the failure message disappears | | |

### UAT-04 Mistyped phone number
| # | Action | Expected result | P/F/B | Notes |
| --- | --- | --- | --- | --- |
| 1 | Pay with **0812 345 678** | Error explaining the number is invalid; status stays **submitted**; no payment starts | | |

### UAT-05 ★ KRA PIN problems are explained
| # | Action | Expected result | P/F/B | Notes |
| --- | --- | --- | --- | --- |
| 1 | Create an application with PIN **B123** | Error mentioning kra_pin format; nothing created | | |
| 2 | Create one with PIN **A999999999Z** | "KRA PIN is not registered"; nothing created | | |
| 3 | Create one with PIN **P666666666Q** | "KRA PIN is not active" | | |

### UAT-06 ★ See the permit once issued
| # | Action | Expected result | P/F/B | Notes |
| --- | --- | --- | --- | --- |
| 1 | Find **Kibanda Coffee House** (seeded, issued) | Row shows **issued** and a *Certificate PP-…* link | | |
| 2 | Click the certificate link | Verify page shows **Valid permit**, business name and expiry date | | |

## Licensing officer

### UAT-07 ★ Approve and issue
| # | Action | Expected result | P/F/B | Notes |
| --- | --- | --- | --- | --- |
| 1 | Log in as `officer@permitpass.test` | *Officer queue* shows **Paid, awaiting review** | | |
| 2 | Press *Approve* on **Mama Ngina Tailors** | "now approved"; it leaves the paid list | | |
| 3 | Filter *Approved, ready to issue*; press *Issue permit* | "now issued" | | |

### UAT-08 ★ Reject with a reason
| # | Action | Expected result | P/F/B | Notes |
| --- | --- | --- | --- | --- |
| 1 | Press *Reject* on **Rift Valley Hardware** | A reason field appears, focused | | |
| 2 | Press *Confirm reject* with the field empty | Nothing happens; the field is required | | |
| 3 | Enter "Business address missing", confirm | "now rejected" | | |
| 4 | Log in as the citizen | Row shows "Rejected: Business address missing" | | |

### UAT-09 Revoke a permit
| # | Action | Expected result | P/F/B | Notes |
| --- | --- | --- | --- | --- |
| 1 | Filter *Issued*; press *Revoke* on **Nyeri Fresh Produce**, reason "Business closed" | "now revoked" | | |
| 2 | Verify its certificate (UAT-11 steps) | **This permit has been revoked** | | |

### UAT-10 ★ Officers can't do citizens' actions, and vice versa
| # | Action | Expected result | P/F/B | Notes |
| --- | --- | --- | --- | --- |
| 1 | As officer, look for any way to create or pay an application | No such option | | |
| 2 | As citizen, type `/queue.html` in the address bar | You're sent back to *My applications* | | |

## Public verification

### UAT-11 ★ Check a genuine permit
| # | Action | Expected result | P/F/B | Notes |
| --- | --- | --- | --- | --- |
| 1 | Without logging in, open *Verify a permit* | Form with certificate number and security code | | |
| 2 | Enter a valid number and code printed by `seed_uat.py` | **Valid permit**, business name, valid-until date | | |
| 3 | Enter **Malindi Beach Hotel**'s number and code | **This permit has been revoked** | | |

### UAT-12 ★ A forged permit is caught
| # | Action | Expected result | P/F/B | Notes |
| --- | --- | --- | --- | --- |
| 1 | Use a real certificate number but change one character of the code | **Not a valid PermitPass certificate**; no business details shown | | |
| 2 | Use a made-up number **PP-2026-00000000** | Same message, nothing else | | |
