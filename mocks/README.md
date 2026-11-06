# Service virtualisation (WireMock)

Stubs for the external systems PermitPass calls. Compose serves them on `http://localhost:8089`; CI runs the
**contract tests** (`tests/contract/`) with the real clients against these same files.

## Test-data rules

The unit-test fakes (`app/api/permitpass/integrations/fakes.py`) follow **the same rules**, and a contract test
(`test_fake_and_stubs_agree`) fails if they drift apart.

### KRA PIN Checker (SOAP): rule is the 9 digits in the PIN

| PIN digits | Example | KRA answer | PermitPass behaviour |
| --- | --- | --- | --- |
| `999999999` | `A999999999Z` | `NotFound` | 422 "KRA PIN is not registered" |
| `666666666` | `P666666666Q` | `Inactive` | 422 "KRA PIN is not active" |
| `888888888` | `A888888888Z` | SOAP fault (HTTP 500) | 503, nothing stored |
| `777777777` | `A777777777Z` | answers after 5 s (> 3 s timeout) | 503, nothing stored |
| anything else | `A123456789Z` | `Active` | application created |

### M-Pesa Daraja (OAuth + STK push): rule is the phone number

The STK stub answers immediately, then a **webhook** POSTs the result to whatever `CallBackURL` the request
carried (after about 1 s), exactly like Safaricom. `CheckoutRequestID` is `ws_CO_<AccountReference>`.

| Phone | Callback | PermitPass behaviour |
| --- | --- | --- |
| `0700000032` | ResultCode 1032 "Request cancelled by user" | back to `submitted`, reason shown |
| `0700000037` | ResultCode 1037 "DS timeout user cannot be reached" | back to `submitted`, reason shown |
| `0700000001` | success, but **Amount 1** | not paid; payment flagged `amount_mismatch` |
| `0700000002` | success callback sent **twice** | paid once; second is "Already processed" |
| `0700000000` | **none** | stays `payment_pending` |
| `0700000500` | STK request fails (HTTP 500) | 503, nothing changes |
| `0700000003` | **none**, but the **STK query** says success | sweep marks it `paid` (no receipt in query answers) |
| `0700000004` | **none**, but the **STK query** says cancelled (1032) | sweep returns it to `submitted` |
| any other valid number | success for the exact amount | `paid`, receipt stored |

**STK Push Query** (`/mpesa/stkpushquery/v1/query`): `CheckoutRequestID`s starting `ws_CO_QOK_` (phone 0700000003)
answer success, `ws_CO_QCX_` (0700000004) answer cancelled, and anything else answers *"The transaction is being
processed"* (HTTP 500, error 500.001.1001), so 0700000000 eventually **expires**.

OAuth: `GET /oauth/v1/generate?grant_type=client_credentials` with Basic auth returns `wiremock-token`. STK requests
must carry `Authorization: Bearer wiremock-token` and every required Daraja field (`BusinessShortCode`, `Password`,
14-digit `Timestamp`, `TransactionType`, `Amount`, `PartyA`, `PartyB`, `PhoneNumber`, `CallBackURL`,
`AccountReference` ≤ 12 chars, `TransactionDesc`).

> **Handlebars tip:** never let a template end right before a JSON `}`. `{{x}}}` parses as a triple-stash.
> Write `{{x}} }`.

A request that breaks the contract (wrong `SOAPAction`, wrong `Content-Type`, no `ValidatePIN/KRAPIN`) hits a
**catch-all stub** that returns `400 CONTRACT VIOLATION`, and the contract tests fail.

## Adding a stub
1. Add the mapping under `mappings/` with a descriptive `"name"` starting with the system (`KRA:`, `M-Pesa:`).
2. Add the same rule to the fake.
3. Add a contract test case.
