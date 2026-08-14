from datetime import date
import secrets
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .events import (
    ATTENDANCE_MARKED,
    ATTENDANCE_UPDATED,
    EMPLOYEE_CREATED,
    EMPLOYEE_DEACTIVATED,
    EMPLOYEE_UPDATED,
    LEAVE_APPROVED,
    LEAVE_REJECTED,
    LEAVE_REQUESTED,
    add_event,
    add_leave_event,
)
from .models import Attendance, Department, Employee, LeaveRequest, Notification, User


def audit(db: AsyncSession, user: User, action: str, entity_id: UUID, entity_type: str = "leave_request") -> None:
    from .models import AuditLog

    db.add(AuditLog(actor_id=user.id, action=action, entity_type=entity_type, entity_id=entity_id))


async def employee_for_user(db: AsyncSession, user: User) -> Employee:
    employee = await db.scalar(
        select(Employee).options(selectinload(Employee.user)).where(Employee.user_id == user.id)
    )
    if not employee:
        raise HTTPException(status_code=404, detail="Employee profile not found")
    return employee


async def create_employee(db: AsyncSession, *, actor: User, payload: dict) -> tuple[Employee, str]:
    if actor.role != "admin":
        raise HTTPException(status_code=403, detail="You do not have permission for this action")
    if await db.scalar(select(User).where(func.lower(User.email) == payload["email"].lower())):
        raise HTTPException(status_code=409, detail="An employee already exists for this email")
    department = await db.scalar(select(Department).where(func.lower(Department.name) == payload["department"].lower()))
    if not department:
        department = Department(name=payload["department"])
        db.add(department)
        await db.flush()
    from .auth import generate_login_id
    from .security import hash_password

    login_id = await generate_login_id(db, actor.company_name, payload["name"], payload["joining_date"].year)
    temporary_password = secrets.token_urlsafe(12)
    user = User(
        email=payload["email"].lower(), login_id=login_id, name=payload["name"], company_name=actor.company_name,
        phone=payload["phone"], password_hash=hash_password(temporary_password), role="employee",
    )
    db.add(user)
    await db.flush()
    employee = Employee(
        user_id=user.id, employee_code=login_id, department_id=department.id, title=payload["title"],
        salary=payload["salary"], joining_date=payload["joining_date"], profile_completion=75,
    )
    db.add(employee)
    await db.flush()
    audit(db, actor, "employee.create", employee.id, "employee")
    add_event(
        db, event_type=EMPLOYEE_CREATED, aggregate_type="employee", aggregate_id=employee.id,
        aggregate_version=1, actor=actor, employee_user_id=user.id,
        payload={"employee_id": str(employee.id), "status": "active"},
    )
    await db.commit()
    await db.refresh(employee, ["user", "department"])
    return employee, temporary_password


async def update_employee(db: AsyncSession, *, actor: User, employee_id: UUID, payload: dict) -> Employee:
    if actor.role != "admin":
        raise HTTPException(status_code=403, detail="You do not have permission for this action")
    employee = await db.scalar(select(Employee).options(selectinload(Employee.user), selectinload(Employee.department)).where(Employee.id == employee_id))
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    user = employee.user
    for field in ("name", "email", "phone"):
        if payload.get(field) is not None:
            setattr(user, field, payload[field].lower() if field == "email" else payload[field])
    if payload.get("department") is not None:
        department = await db.scalar(select(Department).where(func.lower(Department.name) == payload["department"].lower()))
        if not department:
            department = Department(name=payload["department"])
            db.add(department)
            await db.flush()
        employee.department_id = department.id
    for field in ("title", "salary", "joining_date"):
        if payload.get(field) is not None:
            setattr(employee, field, payload[field])
    audit(db, actor, "employee.update", employee.id, "employee")
    add_event(
        db, event_type=EMPLOYEE_UPDATED, aggregate_type="employee", aggregate_id=employee.id,
        aggregate_version=1, actor=actor, employee_user_id=user.id,
        payload={"employee_id": str(employee.id), "status": "active"},
    )
    await db.commit()
    await db.refresh(employee, ["user", "department"])
    return employee


async def deactivate_employee(db: AsyncSession, *, actor: User, employee_id: UUID) -> Employee:
    if actor.role != "admin":
        raise HTTPException(status_code=403, detail="You do not have permission for this action")
    employee = await db.scalar(select(Employee).options(selectinload(Employee.user), selectinload(Employee.department)).where(Employee.id == employee_id))
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    employee.user.is_active = False
    audit(db, actor, "employee.deactivate", employee.id, "employee")
    add_event(
        db, event_type=EMPLOYEE_DEACTIVATED, aggregate_type="employee", aggregate_id=employee.id,
        aggregate_version=1, actor=actor, employee_user_id=employee.user.id,
        payload={"employee_id": str(employee.id), "status": "inactive"},
    )
    await db.commit()
    return employee


async def check_in(db: AsyncSession, *, actor: User) -> tuple[Attendance, str, str]:
    employee = await employee_for_user(db, actor)
    today = date.today()
    existing = await db.scalar(select(Attendance).where(Attendance.employee_id == employee.id, Attendance.work_date == today))
    if existing and existing.check_in:
        raise HTTPException(status_code=409, detail="You are already checked in today")
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    row = existing or Attendance(employee_id=employee.id, work_date=today)
    row.check_in = now
    row.status = "late" if (now.hour, now.minute) > (9, 30) else "present"
    db.add(row)
    await db.flush()
    audit(db, actor, "attendance.check_in", row.id, "attendance")
    add_event(
        db, event_type=ATTENDANCE_MARKED, aggregate_type="attendance", aggregate_id=row.id,
        aggregate_version=1, actor=actor, employee_user_id=actor.id,
        payload={"employee_id": str(employee.id), "status": row.status, "date": today.isoformat()},
    )
    await db.commit()
    return row, now.isoformat(), row.status


async def check_out(db: AsyncSession, *, actor: User) -> tuple[Attendance, str]:
    employee = await employee_for_user(db, actor)
    row = await db.scalar(select(Attendance).where(Attendance.employee_id == employee.id, Attendance.work_date == date.today()))
    if not row or not row.check_in:
        raise HTTPException(status_code=409, detail="Check in before checking out")
    if row.check_out:
        raise HTTPException(status_code=409, detail="You are already checked out today")
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    check_in_value = row.check_in.replace(tzinfo=UTC) if row.check_in.tzinfo is None else row.check_in
    row.check_out = now
    row.work_minutes = max(0, int((now - check_in_value).total_seconds() / 60))
    audit(db, actor, "attendance.check_out", row.id, "attendance")
    add_event(
        db, event_type=ATTENDANCE_UPDATED, aggregate_type="attendance", aggregate_id=row.id,
        aggregate_version=2, actor=actor, employee_user_id=actor.id,
        payload={"employee_id": str(employee.id), "status": row.status, "date": row.work_date.isoformat()},
    )
    await db.commit()
    return row, now.isoformat()


async def create_leave(
    db: AsyncSession,
    *,
    actor: User,
    leave_type: str,
    start_date: date,
    end_date: date,
    remarks: str,
) -> LeaveRequest:
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="End date cannot be before start date")
    employee = await employee_for_user(db, actor)
    conflict = await db.scalar(
        select(LeaveRequest).where(
            LeaveRequest.employee_id == employee.id,
            LeaveRequest.status.in_(["pending", "approved"]),
            LeaveRequest.start_date <= end_date,
            LeaveRequest.end_date >= start_date,
        )
    )
    if conflict:
        raise HTTPException(status_code=409, detail="This request overlaps an existing leave request")
    row = LeaveRequest(
        employee_id=employee.id,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        remarks=remarks,
        status="pending",
    )
    db.add(row)
    await db.flush()
    audit(db, actor, "leave.apply", row.id)
    add_leave_event(
        db,
        event_type=LEAVE_REQUESTED,
        aggregate_id=row.id,
        aggregate_version=1,
        actor=actor,
        employee_user_id=actor.id,
        payload={"status": "pending", "leave_type": leave_type},
    )
    await db.commit()
    await db.refresh(row, ["employee"])
    await db.refresh(row.employee, ["user"])
    return row


async def decide_leave(
    db: AsyncSession,
    *,
    actor: User,
    leave_id: UUID,
    decision: str,
    comment: str,
) -> LeaveRequest:
    if actor.role != "admin":
        raise HTTPException(status_code=403, detail="You do not have permission for this action")
    row = await db.scalar(
        select(LeaveRequest)
        .options(selectinload(LeaveRequest.employee).selectinload(Employee.user))
        .where(LeaveRequest.id == leave_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending leave requests can be decided")
    row.status = decision
    row.approver_id = actor.id
    row.approver_comment = comment
    db.add(
        Notification(
            user_id=row.employee.user_id,
            title=f"Leave {decision}",
            body=f"Your {row.leave_type.lower()} leave request was {decision}.",
        )
    )
    audit(db, actor, f"leave.{decision}", row.id)
    add_leave_event(
        db,
        event_type=LEAVE_APPROVED if decision == "approved" else LEAVE_REJECTED,
        aggregate_id=row.id,
        aggregate_version=2,
        actor=actor,
        employee_user_id=row.employee.user_id,
        payload={"status": decision},
    )
    await db.commit()
    return row
