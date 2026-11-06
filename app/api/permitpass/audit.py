"""Audit trail writer, shared by user actions and system events (e.g. M-Pesa callbacks)."""
from sqlalchemy.orm import Session

from . import clock
from .domain import State
from .models import ApplicationRow, AuditEventRow


def record(db: Session, row: ApplicationRow, actor_id: str, action: str,
           from_state: State | None, reason: str | None = None) -> None:
    """Add an audit event in the same transaction as the change it describes."""
    db.add(AuditEventRow(application_id=row.id, actor_id=actor_id, action=action, from_state=from_state,
                         to_state=row.state, reason=reason, at=clock.now()))
