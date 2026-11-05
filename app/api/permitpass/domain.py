"""Business rules for the permit lifecycle, independent of storage and HTTP."""
from enum import Enum


class Role(str, Enum):
    citizen = "citizen"
    officer = "officer"
    admin = "admin"


class State(str, Enum):
    draft = "draft"
    submitted = "submitted"
    paid = "paid"
    approved = "approved"
    issued = "issued"
    rejected = "rejected"


# Allowed transitions: (from_state, action) -> to_state
TRANSITIONS: dict[tuple[State, str], State] = {
    (State.draft, "submit"): State.submitted,
    (State.submitted, "pay"): State.paid,
    (State.paid, "approve"): State.approved,
    (State.submitted, "reject"): State.rejected,
    (State.paid, "reject"): State.rejected,
    (State.approved, "issue"): State.issued,
}

# Which role may perform which action
ACTION_ROLES: dict[str, set[Role]] = {
    "submit": {Role.citizen},
    "pay": {Role.citizen},
    "approve": {Role.officer},
    "reject": {Role.officer},
    "issue": {Role.officer},
}

PERMIT_FEE_KES = 2500
