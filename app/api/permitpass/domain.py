"""Business rules for the permit lifecycle, independent of storage and HTTP."""
from enum import Enum


class Role(str, Enum):
    citizen = "citizen"
    officer = "officer"
    admin = "admin"


class State(str, Enum):
    draft = "draft"
    submitted = "submitted"
    payment_pending = "payment_pending"
    paid = "paid"
    approved = "approved"
    issued = "issued"
    rejected = "rejected"
    revoked = "revoked"


# Allowed transitions: (from_state, action) -> to_state
TRANSITIONS: dict[tuple[State, str], State] = {
    (State.draft, "submit"): State.submitted,
    (State.submitted, "pay"): State.payment_pending,          # STK push sent; waiting for M-Pesa
    (State.payment_pending, "payment_confirmed"): State.paid,  # system: M-Pesa callback, success
    (State.payment_pending, "payment_failed"): State.submitted,  # system: cancelled, failed or wrong amount
    (State.paid, "approve"): State.approved,
    (State.submitted, "reject"): State.rejected,
    (State.paid, "reject"): State.rejected,
    (State.approved, "issue"): State.issued,
    (State.issued, "revoke"): State.revoked,
}

# Which role may perform which action
ACTION_ROLES: dict[str, set[Role]] = {
    "submit": {Role.citizen},
    "pay": {Role.citizen},
    "approve": {Role.officer},
    "reject": {Role.officer},
    "issue": {Role.officer},
    "revoke": {Role.officer},
}

# Transitions only the system may perform (from the M-Pesa callback), never via the API's action endpoint
SYSTEM_ACTIONS = {"payment_confirmed", "payment_failed"}
SYSTEM_ACTOR_MPESA = "system:mpesa"
SYSTEM_ACTOR_MIGRATION = "system:migration"

# Actions that must carry a reason
REASON_REQUIRED = {"reject", "revoke"}

PERMIT_FEE_KES = 2500
