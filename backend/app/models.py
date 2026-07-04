"""Portable SQLAlchemy models for PostgreSQL production and SQLite development."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Department(Base, TimestampMixin):
    __tablename__ = "departments"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(300), default="")


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    login_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    company_name: Mapped[str] = mapped_column(String(160), default="Aurora HR")
    phone: Mapped[str | None] = mapped_column(String(40))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="employee", index=True)
    oauth_provider: Mapped[str | None] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    refresh_token_hash: Mapped[str | None] = mapped_column(String(64))
    employee: Mapped["Employee | None"] = relationship(back_populates="user", uselist=False)


class Employee(Base, TimestampMixin):
    __tablename__ = "employees"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    employee_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id"))
    manager_id: Mapped[UUID | None] = mapped_column(ForeignKey("employees.id"))
    title: Mapped[str] = mapped_column(String(120), default="Team Member")
    address: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(100), default="Bengaluru")
    joining_date: Mapped[date] = mapped_column(Date, default=date.today)
    salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    profile_completion: Mapped[int] = mapped_column(default=70)
    health_score: Mapped[int] = mapped_column(default=85)
    user: Mapped[User] = relationship(back_populates="employee")
    department: Mapped[Department | None] = relationship()


class Attendance(Base, TimestampMixin):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("employee_id", "work_date", name="uq_attendance_employee_date"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    check_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="present")
    work_minutes: Mapped[int] = mapped_column(default=0)
    employee: Mapped[Employee] = relationship()


class LeaveRequest(Base, TimestampMixin):
    __tablename__ = "leave_requests"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    leave_type: Mapped[str] = mapped_column(String(30))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    remarks: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    approver_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    approver_comment: Mapped[str | None] = mapped_column(Text)
    employee: Mapped[Employee] = relationship()


class Payroll(Base, TimestampMixin):
    __tablename__ = "payroll"
    __table_args__ = (UniqueConstraint("employee_id", "period", name="uq_payroll_employee_period"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    period: Mapped[str] = mapped_column(String(7), index=True)
    basic: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    bonuses: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    deductions: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    net_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    components: Mapped[dict] = mapped_column(JSON, default=dict)
    employee: Mapped[Employee] = relationship()


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(30), default="in_app")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Document(Base, TimestampMixin):
    __tablename__ = "documents"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    employee_id: Mapped[UUID | None] = mapped_column(ForeignKey("employees.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[str] = mapped_column(String(60), index=True)
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    mime_type: Mapped[str] = mapped_column(String(120))
    extracted_text: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[UUID | None] = mapped_column(Uuid)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class AgentTask(Base, TimestampMixin):
    __tablename__ = "agent_tasks"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    agent_name: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    command: Mapped[str] = mapped_column(Text)
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    retry_count: Mapped[int] = mapped_column(default=0)
    duration_ms: Mapped[int | None] = mapped_column()


class AgentMemory(Base, TimestampMixin):
    __tablename__ = "agent_memory"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    agent_name: Mapped[str] = mapped_column(String(100), index=True)
    session_id: Mapped[str] = mapped_column(String(100), index=True)
    content: Mapped[dict] = mapped_column(JSON)
