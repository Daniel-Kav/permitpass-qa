"""M-Pesa STK push payments and the result callback.

Phone rules (same as the WireMock stubs, see mocks/README.md): 0700000032 cancelled, 0700000037 timeout,
0700000001 pays the wrong amount, 0700000002 callback sent twice, 0700000000 never answers,
0700000500 STK push fails. Any other valid number pays the exact fee. Traceability: US-08.
"""
import pytest

from conftest import CITIZEN, OFFICER, OTHER_CITIZEN, act, deliver, drive, new_application, settle

from permitpass.integrations.fakes import callback_body


def _state(client, app_id):
    return client.get(f"/applications/{app_id}", headers=CITIZEN).json()


def _payments(client, app_id, who=CITIZEN):
    return client.get(f"/applications/{app_id}/payments", headers=who).json()


def _events(client, app_id):
    return [(e["action"], e["to_state"], e["actor_id"]) for e in client.get(f"/applications/{app_id}/history", headers=CITIZEN).json()]


@pytest.fixture
def submitted(client):
    return new_application(client, ["submit"])


# ---------- starting a payment ----------

@pytest.mark.parametrize("phone,msisdn", [
    ("0712345678", "254712345678"),
    ("0112345678", "254112345678"),     # newer 01xx Safaricom range
    ("254712345678", "254712345678"),
    ("+254712345678", "254712345678"),
])
def test_valid_phone_formats_start_an_stk_push(client, mpesa, submitted, phone, msisdn):
    r = act(client, submitted, "pay", phone=phone)
    assert r.status_code == 200 and r.json()["state"] == "payment_pending"
    push = mpesa.pushes[-1]
    assert (push["phone"], push["amount"]) == (msisdn, 2500)
    assert len(push["account_ref"]) == 12
    assert "token=" in push["callback_url"]


@pytest.mark.parametrize("phone", [
    "0812345678",      # not a mobile prefix
    "071234567",       # 9 digits (boundary - 1)
    "07123456789",     # 11 digits (boundary + 1)
    "255712345678",    # Tanzania
    "07l2345678",      # letter l, not digit 1
    "",
])
def test_invalid_phone_is_refused_before_calling_mpesa(client, mpesa, submitted, phone):
    assert act(client, submitted, "pay", phone=phone).status_code == 422
    assert mpesa.pushes == [] and _state(client, submitted)["state"] == "submitted"


def test_phone_is_required(client, mpesa, submitted):
    r = client.post(f"/applications/{submitted}/pay", json={}, headers=CITIZEN)
    assert (r.status_code, r.json()["detail"]) == (422, "An M-Pesa phone number is required to pay")
    assert mpesa.pushes == []


def test_mpesa_down_changes_nothing(client, submitted):
    r = act(client, submitted, "pay", phone="0700000500")
    assert r.status_code == 503 and r.headers["retry-after"] == "30"
    assert _state(client, submitted)["state"] == "submitted"
    assert _payments(client, submitted) == []


def test_cannot_pay_twice_while_waiting(client, submitted):
    act(client, submitted, "pay", phone="0700000000")       # never answers
    assert act(client, submitted, "pay").status_code == 409


def test_officer_cannot_approve_while_payment_pending(client, submitted):
    act(client, submitted, "pay", phone="0700000000")
    assert act(client, submitted, "approve").status_code == 409


# ---------- callback outcomes ----------

def test_successful_payment(client, submitted):
    act(client, submitted, "pay")
    [r] = settle(client)
    assert r.json() == {"ResultCode": 0, "ResultDesc": "Accepted"}
    assert _state(client, submitted)["state"] == "paid"
    [p] = _payments(client, submitted)
    assert p["status"] == "succeeded" and p["mpesa_receipt"].startswith("FAKE")
    assert _events(client, submitted)[-1] == ("payment_confirmed", "paid", "system:mpesa")


@pytest.mark.parametrize("phone,code,desc", [
    ("0700000032", 1032, "Request cancelled by user"),
    ("0700000037", 1037, "DS timeout user cannot be reached"),
])
def test_failed_payment_returns_to_submitted_with_a_reason(client, submitted, phone, code, desc):
    act(client, submitted, "pay", phone=phone)
    settle(client)
    app = _state(client, submitted)
    assert app["state"] == "submitted"
    assert app["payment_note"] == f"Payment failed: {desc} (M-Pesa code {code})"
    assert _payments(client, submitted)[0]["status"] == "failed"


def test_citizen_can_retry_after_a_failed_payment(client, submitted):
    act(client, submitted, "pay", phone="0700000032")
    settle(client)
    act(client, submitted, "pay")
    settle(client)
    assert _state(client, submitted)["state"] == "paid"
    assert _state(client, submitted)["payment_note"] is None
    assert [p["status"] for p in _payments(client, submitted)] == ["failed", "succeeded"]


def test_wrong_amount_is_not_accepted_as_payment(client, submitted):
    act(client, submitted, "pay", phone="0700000001")       # M-Pesa reports KES 1
    settle(client)
    app = _state(client, submitted)
    assert app["state"] == "submitted"
    assert "Amount mismatch: expected KES 2500, M-Pesa reported 1" in app["payment_note"]
    assert _payments(client, submitted)[0]["status"] == "amount_mismatch"


def test_success_without_receipt_is_not_accepted(client, mpesa, submitted):
    act(client, submitted, "pay", phone="0700000000")
    checkout = f"ws_CO_{mpesa.pushes[-1]['account_ref']}"
    body = callback_body(checkout, 2500, "254700000000", None, receipt="X")
    body["Body"]["stkCallback"]["CallbackMetadata"]["Item"] = [{"Name": "Amount", "Value": 2500}]
    deliver(client, body)
    assert _state(client, submitted)["state"] == "submitted"


def test_duplicate_callback_has_no_extra_effect(client, submitted):
    act(client, submitted, "pay", phone="0700000002")       # M-Pesa sends the callback twice
    first, second = settle(client)
    assert first.json()["ResultDesc"] == "Accepted"
    assert second.json() == {"ResultCode": 0, "ResultDesc": "Already processed"}
    assert [e for e in _events(client, submitted) if e[0] == "payment_confirmed"] == [("payment_confirmed", "paid", "system:mpesa")]


def test_late_failure_after_success_is_ignored(client, mpesa, submitted):
    act(client, submitted, "pay")
    settle(client)
    checkout = f"ws_CO_{mpesa.pushes[-1]['account_ref']}"
    r = deliver(client, callback_body(checkout, 2500, "254712345678", "cancelled", receipt="X"))
    assert r.json()["ResultDesc"] == "Already processed"
    assert _state(client, submitted)["state"] == "paid"


@pytest.mark.parametrize("result,amount,duplicate,expected_state,expected_payment", [
    ("success",   "exact", False, "paid",      "succeeded"),
    ("success",   "exact", True,  "paid",      "succeeded"),
    ("success",   "wrong", False, "submitted", "amount_mismatch"),
    ("success",   "wrong", True,  "submitted", "amount_mismatch"),
    ("cancelled", "exact", False, "submitted", "failed"),
    ("cancelled", "exact", True,  "submitted", "failed"),
])
def test_callback_decision_table(client, mpesa, submitted, result, amount, duplicate, expected_state, expected_payment):
    act(client, submitted, "pay", phone="0700000000")         # we deliver the callback ourselves
    checkout = f"ws_CO_{mpesa.pushes[-1]['account_ref']}"
    rule = "cancelled" if result == "cancelled" else ("wrong_amount" if amount == "wrong" else None)
    body = callback_body(checkout, 2500, "254700000000", rule, receipt="QWE123RTY0")
    for _ in range(2 if duplicate else 1):
        assert deliver(client, body).status_code == 200
    assert _state(client, submitted)["state"] == expected_state
    assert _payments(client, submitted)[0]["status"] == expected_payment


# ---------- callback security and robustness ----------

@pytest.mark.parametrize("token", ["", "wrong-token", "dev-callback-token-012345678"])   # last: one char short
def test_callback_needs_the_shared_secret(client, mpesa, submitted, token):
    act(client, submitted, "pay", phone="0700000000")
    body = callback_body(f"ws_CO_{mpesa.pushes[-1]['account_ref']}", 2500, "254700000000", None, receipt="R1")
    assert deliver(client, body, token=token).status_code == 401
    assert _state(client, submitted)["state"] == "payment_pending"


def test_unknown_checkout_id_is_404_and_changes_nothing(client, submitted):
    act(client, submitted, "pay", phone="0700000000")
    r = deliver(client, callback_body("ws_CO_NOTOURS00000", 2500, "254700000000", None, receipt="R2"))
    assert r.status_code == 404
    assert _state(client, submitted)["state"] == "payment_pending"


@pytest.mark.parametrize("body", [{}, {"Body": {}}, {"Body": {"stkCallback": {"ResultCode": "zero"}}}])
def test_malformed_callback_is_rejected(client, body):
    assert deliver(client, body).status_code == 422


def test_other_citizens_cannot_see_payments(client, submitted):
    act(client, submitted, "pay")
    assert client.get(f"/applications/{submitted}/payments", headers=OTHER_CITIZEN).status_code == 404
    assert client.get(f"/applications/{submitted}/payments", headers=OFFICER).status_code == 200


def test_system_transitions_cannot_be_called_by_users(client, submitted):
    act(client, submitted, "pay", phone="0700000000")
    for action in ("payment_confirmed", "payment_failed"):
        assert client.post(f"/applications/{submitted}/{action}", headers=OFFICER).status_code == 404


def test_receipt_numbers_are_unique_per_payment(client):
    a, b = new_application(client, ["submit", "pay"]), new_application(client, ["submit", "pay"])
    ra, rb = _payments(client, a)[0]["mpesa_receipt"], _payments(client, b)[0]["mpesa_receipt"]
    assert ra != rb
