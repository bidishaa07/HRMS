from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Role(StrEnum):
    EMPLOYEE = "employee"
    HR = "hr"
    ADMIN = "admin"


class LeaveStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class Employee(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    employee_code: str
    name: str
    email: EmailStr
    role: Role = Role.EMPLOYEE
    department: str
    title: str
    manager: str | None = None
    location: str = "Bengaluru"
    profile_completion: int = Field(ge=0, le=100)
    health_score: int = Field(ge=0, le=100)


class LeaveRequestCreate(BaseModel):
    leave_type: str
    start_date: date
    end_date: date
    remarks: str = Field(min_length=3, max_length=500)


class LeaveRequest(LeaveRequestCreate):
    id: UUID
    employee_name: str
    status: LeaveStatus
    days: float
    recommendation: str
    created_at: datetime


class AgentCommand(BaseModel):
    command: str = Field(min_length=2, max_length=1000)


class AgentResponse(BaseModel):
    message: str
    agent: str
    tools_used: list[str]
    explainability: str
    task_id: UUID


class DashboardSummary(BaseModel):
    employees: int
    present_today: int
    on_leave: int
    pending_approvals: int
    payroll_total: int
    organization_health: int
    burnout_alerts: int
    late_arrivals: int
