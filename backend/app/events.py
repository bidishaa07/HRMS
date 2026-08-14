from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from .models import EventOutbox, User

LEAVE_REQUESTED = "LEAVE_REQUESTED"
LEAVE_APPROVED = "LEAVE_APPROVED"
LEAVE_REJECTED = "LEAVE_REJECTED"
LEAVE_EVENTS = {LEAVE_REQUESTED, LEAVE_APPROVED, LEAVE_REJECTED}
EMPLOYEE_CREATED = "EMPLOYEE_CREATED"
EMPLOYEE_UPDATED = "EMPLOYEE_UPDATED"
EMPLOYEE_DEACTIVATED = "EMPLOYEE_DEACTIVATED"
ATTENDANCE_MARKED = "ATTENDANCE_MARKED"
ATTENDANCE_UPDATED = "ATTENDANCE_UPDATED"
EMPLOYEE_EVENTS = {EMPLOYEE_CREATED, EMPLOYEE_UPDATED, EMPLOYEE_DEACTIVATED}
ATTENDANCE_EVENTS = {ATTENDANCE_MARKED, ATTENDANCE_UPDATED}
REALTIME_EVENTS = LEAVE_EVENTS | EMPLOYEE_EVENTS | ATTENDANCE_EVENTS


def add_event(
    db: AsyncSession,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: UUID,
    aggregate_version: int,
    actor: User,
    employee_user_id: UUID,
    payload: dict,
    roles: list[str] | None = None,
) -> EventOutbox:
    if event_type not in REALTIME_EVENTS:
        raise ValueError(f"Unsupported realtime event type: {event_type}")
    event_id = uuid4()
    occurred_at = datetime.now(UTC)
    envelope = {
        "event_id": str(event_id),
        "event_type": event_type,
        "schema_version": 1,
        "occurred_at": occurred_at.isoformat(),
        "aggregate": {"type": aggregate_type, "id": str(aggregate_id), "version": aggregate_version},
        "actor": {"id": str(actor.id), "role": actor.role},
        "scope": {
            "company_name": actor.company_name,
            "employee_user_id": str(employee_user_id),
            "roles": roles or ["admin", "hr"],
        },
        "correlation_id": str(event_id),
        "payload": payload,
    }
    row = EventOutbox(
        id=event_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        actor_id=actor.id,
        payload=envelope,
        aggregate_version=aggregate_version,
        occurred_at=occurred_at,
    )
    db.add(row)
    return row


def add_leave_event(
    db: AsyncSession,
    *,
    event_type: str,
    aggregate_id: UUID,
    aggregate_version: int,
    actor: User,
    employee_user_id: UUID,
    payload: dict,
) -> EventOutbox:
    return add_event(
        db,
        event_type=event_type,
        aggregate_type="leave_request",
        aggregate_id=aggregate_id,
        aggregate_version=aggregate_version,
        actor=actor,
        employee_user_id=employee_user_id,
        payload=payload,
    )
