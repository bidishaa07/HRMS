from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .agents import AGENTS, orchestrator
from .auth import CurrentUser, generate_login_id, require_roles
from .auth import router as auth_router
from .config import settings
from .database import SessionLocal, close_database, create_schema, get_db
from .models import (
    AgentTask,
    Attendance,
    AuditLog,
    Department,
    Document,
    Employee,
    LeaveRequest,
    Notification,
    Payroll,
    User,
)
from .schemas import AgentCommand, AgentResponse
from .security import hash_password
from .seed import seed_database

DbSession = Annotated[AsyncSession, Depends(get_db)]
AdminOnly = Annotated[User, Depends(require_roles("admin"))]


@asynccontextmanager
async def lifespan(_: FastAPI):
    await create_schema()
    async with SessionLocal() as db:
        await seed_database(db)
    try:
        yield
    finally:
        await close_database()


app = FastAPI(
    title="Aurora HR API",
    version="2.0.0",
    lifespan=lifespan,
    description="Persisted HRMS API with JWT, OAuth 2.0, RBAC, and agent orchestration.",
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.include_router(auth_router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update(
        {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Content-Security-Policy": "frame-ancestors 'none'; base-uri 'self'",
        }
    )
    return response


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


def audit(db: AsyncSession, user: User, action: str, entity_type: str, entity_id: UUID | None = None) -> None:
    db.add(AuditLog(actor_id=user.id, action=action, entity_type=entity_type, entity_id=entity_id))


def employee_json(employee: Employee, attendance: Attendance | None = None) -> dict:
    user = employee.user
    return {
        "id": str(employee.id),
        "user_id": str(user.id),
        "employee_code": employee.employee_code,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
        "department": employee.department.name if employee.department else "Unassigned",
        "title": employee.title,
        "location": employee.location,
        "joining_date": employee.joining_date.isoformat(),
        "profile_completion": employee.profile_completion,
        "health_score": employee.health_score,
        "salary": float(employee.salary),
        "status": attendance.status if attendance else "absent",
        "check_in": attendance.check_in.isoformat() if attendance and attendance.check_in else None,
        "check_out": attendance.check_out.isoformat() if attendance and attendance.check_out else None,
    }


async def current_employee(db: AsyncSession, user: User) -> Employee:
    employee = await db.scalar(
        select(Employee)
        .options(selectinload(Employee.user), selectinload(Employee.department))
        .where(Employee.user_id == user.id)
    )
    if not employee:
        raise HTTPException(status_code=404, detail="Employee profile not found")
    return employee


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "aurora-api", "version": "2.0.0"}


@app.get("/api/v1/dashboard/summary", tags=["dashboard"])
async def dashboard_summary(db: DbSession, _: CurrentUser) -> dict:
    today = date.today()
    employees_count = int(await db.scalar(select(func.count(Employee.id))) or 0)
    present = int(
        await db.scalar(
            select(func.count(Attendance.id)).where(
                Attendance.work_date == today, Attendance.status.in_(["present", "late"])
            )
        )
        or 0
    )
    leave_count = int(
        await db.scalar(
            select(func.count(LeaveRequest.id)).where(
                LeaveRequest.status == "approved", LeaveRequest.start_date <= today, LeaveRequest.end_date >= today
            )
        )
        or 0
    )
    pending = int(await db.scalar(select(func.count(LeaveRequest.id)).where(LeaveRequest.status == "pending")) or 0)
    payroll = Decimal(
        await db.scalar(select(func.sum(Payroll.net_salary)).where(Payroll.period == today.strftime("%Y-%m"))) or 0
    )
    late = int(
        await db.scalar(
            select(func.count(Attendance.id)).where(Attendance.work_date == today, Attendance.status == "late")
        )
        or 0
    )
    return {
        "employees": employees_count,
        "present_today": present,
        "on_leave": leave_count,
        "pending_approvals": pending,
        "payroll_total": float(payroll),
        "organization_health": 87,
        "burnout_alerts": 3,
        "late_arrivals": late,
    }


class EmployeeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: str
    phone: str
    department: str
    title: str
    salary: Decimal = Field(ge=0)
    joining_date: date = Field(default_factory=date.today)


@app.get("/api/v1/employees", tags=["employees"])
async def list_employees(
    db: DbSession,
    _: CurrentUser,
    search: str = "",
    department: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
) -> list[dict]:
    query = select(Employee).options(selectinload(Employee.user), selectinload(Employee.department)).join(User)
    if search:
        pattern = f"%{search.lower()}%"
        query = query.where(
            or_(
                func.lower(User.name).like(pattern),
                func.lower(User.email).like(pattern),
                func.lower(Employee.employee_code).like(pattern),
            )
        )
    if department:
        query = query.join(Department).where(func.lower(Department.name) == department.lower())
    employees = list((await db.scalars(query.offset(offset).limit(limit))).all())
    today_rows = (
        list(
            (
                await db.scalars(
                    select(Attendance).where(
                        Attendance.work_date == date.today(),
                        Attendance.employee_id.in_([employee.id for employee in employees]),
                    )
                )
            ).all()
        )
        if employees
        else []
    )
    attendance_by_employee = {row.employee_id: row for row in today_rows}
    return [employee_json(employee, attendance_by_employee.get(employee.id)) for employee in employees]


@app.post("/api/v1/employees", status_code=201, tags=["employees"])
async def create_employee(payload: EmployeeCreate, db: DbSession, actor: AdminOnly) -> dict:
    if await db.scalar(select(User).where(func.lower(User.email) == payload.email.lower())):
        raise HTTPException(status_code=409, detail="An employee already exists for this email")
    department = await db.scalar(select(Department).where(func.lower(Department.name) == payload.department.lower()))
    if not department:
        department = Department(name=payload.department)
        db.add(department)
        await db.flush()
    login_id = await generate_login_id(db, actor.company_name, payload.name, payload.joining_date.year)
    user = User(
        email=payload.email.lower(),
        login_id=login_id,
        name=payload.name,
        company_name=actor.company_name,
        phone=payload.phone,
        password_hash=hash_password("Welcome@123"),
        role="employee",
    )
    db.add(user)
    await db.flush()
    employee = Employee(
        user_id=user.id,
        employee_code=login_id,
        department_id=department.id,
        title=payload.title,
        salary=payload.salary,
        joining_date=payload.joining_date,
        profile_completion=75,
    )
    db.add(employee)
    await db.flush()
    audit(db, actor, "employee.create", "employee", employee.id)
    await db.commit()
    await db.refresh(employee, ["user", "department"])
    return {**employee_json(employee), "temporary_password": "Welcome@123"}


@app.get("/api/v1/attendance", tags=["attendance"])
async def attendance_list(
    db: DbSession,
    user: CurrentUser,
    month: str | None = None,
    employee_id: UUID | None = None,
) -> list[dict]:
    query = select(Attendance).options(selectinload(Attendance.employee).selectinload(Employee.user))
    if user.role == "employee":
        employee = await current_employee(db, user)
        query = query.where(Attendance.employee_id == employee.id)
    elif employee_id:
        query = query.where(Attendance.employee_id == employee_id)
    if month:
        try:
            year, month_number = (int(part) for part in month.split("-"))
            start = date(year, month_number, 1)
            end = date(year + (month_number == 12), 1 if month_number == 12 else month_number + 1, 1)
            query = query.where(Attendance.work_date >= start, Attendance.work_date < end)
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="Month must use YYYY-MM format") from None
    rows = list((await db.scalars(query.order_by(Attendance.work_date.desc(), Attendance.check_in.desc()))).all())
    return [
        {
            "id": str(row.id),
            "employee_id": str(row.employee_id),
            "employee_name": row.employee.user.name,
            "date": row.work_date.isoformat(),
            "check_in": row.check_in.isoformat() if row.check_in else None,
            "check_out": row.check_out.isoformat() if row.check_out else None,
            "status": row.status,
            "work_minutes": row.work_minutes,
            "extra_minutes": max(0, row.work_minutes - 480),
        }
        for row in rows
    ]


@app.post("/api/v1/attendance/check-in", tags=["attendance"])
async def check_in(db: DbSession, user: CurrentUser) -> dict:
    employee = await current_employee(db, user)
    today = date.today()
    existing = await db.scalar(
        select(Attendance).where(Attendance.employee_id == employee.id, Attendance.work_date == today)
    )
    if existing and existing.check_in:
        raise HTTPException(status_code=409, detail="You are already checked in today")
    now = datetime.now(UTC)
    row = existing or Attendance(employee_id=employee.id, work_date=today)
    row.check_in = now
    row.status = "late" if (now.hour, now.minute) > (9, 30) else "present"
    db.add(row)
    audit(db, user, "attendance.check_in", "attendance", row.id)
    await db.commit()
    return {"message": "Checked in successfully", "check_in": now.isoformat(), "status": row.status}


@app.post("/api/v1/attendance/check-out", tags=["attendance"])
async def check_out(db: DbSession, user: CurrentUser) -> dict:
    employee = await current_employee(db, user)
    row = await db.scalar(
        select(Attendance).where(Attendance.employee_id == employee.id, Attendance.work_date == date.today())
    )
    if not row or not row.check_in:
        raise HTTPException(status_code=409, detail="Check in before checking out")
    if row.check_out:
        raise HTTPException(status_code=409, detail="You are already checked out today")
    now = datetime.now(UTC)
    check_in_value = row.check_in.replace(tzinfo=UTC) if row.check_in.tzinfo is None else row.check_in
    row.check_out = now
    row.work_minutes = max(0, int((now - check_in_value).total_seconds() / 60))
    audit(db, user, "attendance.check_out", "attendance", row.id)
    await db.commit()
    return {"message": "Checked out successfully", "check_out": now.isoformat(), "work_minutes": row.work_minutes}


class LeaveCreate(BaseModel):
    leave_type: str = Field(pattern="^(Paid|Sick|Casual|Unpaid)$")
    start_date: date
    end_date: date
    remarks: str = Field(min_length=3, max_length=500)


class LeaveDecision(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    comment: str = Field(default="", max_length=500)


def leave_json(row: LeaveRequest) -> dict:
    return {
        "id": str(row.id),
        "employee_id": str(row.employee_id),
        "employee_name": row.employee.user.name,
        "leave_type": row.leave_type,
        "start_date": row.start_date.isoformat(),
        "end_date": row.end_date.isoformat(),
        "remarks": row.remarks,
        "status": row.status,
        "comment": row.approver_comment,
        "days": (row.end_date - row.start_date).days + 1,
    }


@app.get("/api/v1/leaves", tags=["leave"])
async def list_leaves(db: DbSession, user: CurrentUser, state: str | None = None) -> list[dict]:
    query = select(LeaveRequest).options(selectinload(LeaveRequest.employee).selectinload(Employee.user))
    if user.role == "employee":
        employee = await current_employee(db, user)
        query = query.where(LeaveRequest.employee_id == employee.id)
    if state:
        query = query.where(LeaveRequest.status == state)
    rows = list((await db.scalars(query.order_by(LeaveRequest.created_at.desc()))).all())
    return [leave_json(row) for row in rows]


@app.post("/api/v1/leaves", status_code=201, tags=["leave"])
async def apply_leave(payload: LeaveCreate, db: DbSession, user: CurrentUser) -> dict:
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="End date cannot be before start date")
    employee = await current_employee(db, user)
    conflict = await db.scalar(
        select(LeaveRequest).where(
            LeaveRequest.employee_id == employee.id,
            LeaveRequest.status.in_(["pending", "approved"]),
            LeaveRequest.start_date <= payload.end_date,
            LeaveRequest.end_date >= payload.start_date,
        )
    )
    if conflict:
        raise HTTPException(status_code=409, detail="This request overlaps an existing leave request")
    row = LeaveRequest(employee_id=employee.id, **payload.model_dump())
    db.add(row)
    await db.flush()
    audit(db, user, "leave.apply", "leave_request", row.id)
    await db.commit()
    await db.refresh(row, ["employee"])
    await db.refresh(row.employee, ["user"])
    return leave_json(row)


@app.patch("/api/v1/leaves/{leave_id}", tags=["leave"])
async def decide_leave(leave_id: UUID, payload: LeaveDecision, db: DbSession, actor: AdminOnly) -> dict:
    row = await db.scalar(
        select(LeaveRequest)
        .options(selectinload(LeaveRequest.employee).selectinload(Employee.user))
        .where(LeaveRequest.id == leave_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Leave request not found")
    row.status = payload.decision
    row.approver_id = actor.id
    row.approver_comment = payload.comment
    db.add(
        Notification(
            user_id=row.employee.user_id,
            title=f"Leave {payload.decision}",
            body=f"Your {row.leave_type.lower()} leave request was {payload.decision}.",
        )
    )
    audit(db, actor, f"leave.{payload.decision}", "leave_request", row.id)
    await db.commit()
    return leave_json(row)


@app.get("/api/v1/payroll", tags=["payroll"])
async def payroll_list(db: DbSession, user: CurrentUser, period: str | None = None) -> list[dict]:
    query = select(Payroll).options(selectinload(Payroll.employee).selectinload(Employee.user))
    if user.role == "employee":
        employee = await current_employee(db, user)
        query = query.where(Payroll.employee_id == employee.id)
    if period:
        query = query.where(Payroll.period == period)
    rows = list((await db.scalars(query.order_by(Payroll.period.desc()))).all())
    return [
        {
            "id": str(row.id),
            "employee_id": str(row.employee_id),
            "employee_name": row.employee.user.name,
            "period": row.period,
            "basic": float(row.basic),
            "bonuses": float(row.bonuses),
            "deductions": float(row.deductions),
            "net_salary": float(row.net_salary),
            "components": row.components,
        }
        for row in rows
    ]


def money(value: Decimal) -> str:
    return f"INR {float(value):,.0f}"


def docx_paragraph(text: str, bold: bool = False, color: str | None = None, size: int = 22) -> str:
    props = f"<w:sz w:val=\"{size}\"/>"
    if bold:
        props += "<w:b/>"
    if color:
        props += f"<w:color w:val=\"{color}\"/>"
    return f"<w:p><w:r><w:rPr>{props}</w:rPr><w:t>{escape(text)}</w:t></w:r></w:p>"


def docx_cell(text: str, shade: str = "FFFFFF", bold: bool = False) -> str:
    props = "<w:b/>" if bold else ""
    return (
        "<w:tc><w:tcPr><w:tcW w:w=\"3600\" w:type=\"dxa\"/>"
        f"<w:shd w:fill=\"{shade}\"/></w:tcPr><w:p><w:r><w:rPr>{props}</w:rPr>"
        f"<w:t>{escape(text)}</w:t></w:r></w:p></w:tc>"
    )


def docx_row(label: str, value: str, shade: str = "FFFFFF", bold: bool = False) -> str:
    return f"<w:tr>{docx_cell(label, shade, bold)}{docx_cell(value, shade, bold)}</w:tr>"


def build_payslip_docx(row: Payroll) -> bytes:
    employee = row.employee
    user = employee.user
    rows = [
        docx_row("Employee", user.name, "F4F0FF", True),
        docx_row("Employee Code", employee.employee_code),
        docx_row("Department", employee.department.name if employee.department else "Unassigned"),
        docx_row("Period", row.period),
        docx_row("Basic Salary", money(row.basic)),
        docx_row("Bonuses", money(row.bonuses), "ECFDF5"),
        docx_row("Deductions", money(row.deductions), "FEF2F2"),
        docx_row("Net Salary", money(row.net_salary), "EEF2FF", True),
    ]
    for key, value in sorted((row.components or {}).items()):
        rows.append(docx_row(key.upper(), money(Decimal(str(value)))))
    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:shd w:fill="17191F"/></w:pPr><w:r><w:rPr><w:b/><w:color w:val="FFFFFF"/><w:sz w:val="38"/></w:rPr><w:t>Aurora HR Payslip</w:t></w:r></w:p>
    {docx_paragraph("Private payroll statement", color="765CF4", size=24)}
    {docx_paragraph(f"Generated on {date.today().strftime('%d %b %Y')}", color="68707D", size=18)}
    <w:tbl>
      <w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="7200" w:type="dxa"/><w:tblBorders><w:top w:val="single" w:sz="6" w:color="D9DDE7"/><w:left w:val="single" w:sz="6" w:color="D9DDE7"/><w:bottom w:val="single" w:sz="6" w:color="D9DDE7"/><w:right w:val="single" w:sz="6" w:color="D9DDE7"/><w:insideH w:val="single" w:sz="6" w:color="D9DDE7"/><w:insideV w:val="single" w:sz="6" w:color="D9DDE7"/></w:tblBorders></w:tblPr>
      {''.join(rows)}
    </w:tbl>
    {docx_paragraph("This is a system-generated statement from Aurora HR.", color="68707D", size=18)}
    <w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1000" w:right="1000" w:bottom="1000" w:left="1000"/></w:sectPr>
  </w:body>
</w:document>"""
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


@app.get("/api/v1/payroll/{payroll_id}/payslip.docx", tags=["payroll"])
async def payroll_docx(payroll_id: UUID, db: DbSession, user: CurrentUser) -> StreamingResponse:
    row = await db.scalar(
        select(Payroll)
        .options(selectinload(Payroll.employee).selectinload(Employee.user), selectinload(Payroll.employee).selectinload(Employee.department))
        .where(Payroll.id == payroll_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Payroll record not found")
    if user.role == "employee":
        employee = await current_employee(db, user)
        if row.employee_id != employee.id:
            raise HTTPException(status_code=403, detail="You can only download your own payslip")
    filename = f"aurora-payslip-{row.period}-{row.employee.employee_code}.docx"
    return StreamingResponse(
        BytesIO(build_payslip_docx(row)),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/v1/departments", tags=["organization"])
async def departments(db: DbSession, _: CurrentUser) -> list[dict]:
    rows = list((await db.scalars(select(Department).order_by(Department.name))).all())
    result = []
    for row in rows:
        count = int(await db.scalar(select(func.count(Employee.id)).where(Employee.department_id == row.id)) or 0)
        result.append({"id": str(row.id), "name": row.name, "description": row.description, "employees": count})
    return result


@app.get("/api/v1/documents", tags=["documents"])
async def documents(db: DbSession, user: CurrentUser) -> list[dict]:
    query = select(Document)
    if user.role == "employee":
        employee = await current_employee(db, user)
        query = query.where(or_(Document.employee_id == employee.id, Document.employee_id.is_(None)))
    rows = list((await db.scalars(query.order_by(Document.created_at.desc()))).all())
    return [
        {
            "id": str(row.id),
            "name": row.name,
            "document_type": row.document_type,
            "mime_type": row.mime_type,
            "download_url": f"/api/v1/documents/{row.id}/download",
        }
        for row in rows
    ]


async def document_for_user(document_id: UUID, db: AsyncSession, user: User) -> Document:
    query = select(Document).where(Document.id == document_id)
    if user.role == "employee":
        employee = await current_employee(db, user)
        query = query.where(or_(Document.employee_id == employee.id, Document.employee_id.is_(None)))
    row = await db.scalar(query)
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return row


@app.get("/api/v1/documents/{document_id}", tags=["documents"])
async def document_detail(document_id: UUID, db: DbSession, user: CurrentUser) -> dict:
    row = await document_for_user(document_id, db, user)
    return {
        "id": str(row.id),
        "name": row.name,
        "document_type": row.document_type,
        "mime_type": row.mime_type,
        "download_url": f"/api/v1/documents/{row.id}/download",
    }


@app.get("/api/v1/documents/{document_id}/download", tags=["documents"])
async def download_document(document_id: UUID, db: DbSession, user: CurrentUser) -> FileResponse:
    row = await document_for_user(document_id, db, user)
    path = Path(__file__).resolve().parents[2] / "uploads" / row.object_key
    if not path.exists():
        raise HTTPException(status_code=404, detail="Stored file not found")
    return FileResponse(path, media_type=row.mime_type, filename=row.name)


@app.post("/api/v1/documents", status_code=201, tags=["documents"])
async def upload_document(
    db: DbSession,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    document_type: Annotated[str, Form()] = "Other",
) -> dict:
    content = await file.read(25_000_001)
    if len(content) > 25_000_000:
        raise HTTPException(status_code=413, detail="File size exceeds 25 MB")
    employee = await current_employee(db, user)
    upload_dir = Path(__file__).resolve().parents[2] / "uploads"
    upload_dir.mkdir(exist_ok=True)
    filename = Path(file.filename or "document").name
    suffix = Path(filename).suffix.lower()
    object_key = f"{uuid4()}{suffix}"
    (upload_dir / object_key).write_bytes(content)
    row = Document(
        employee_id=employee.id,
        name=filename,
        document_type=document_type,
        object_key=object_key,
        mime_type=file.content_type or "application/octet-stream",
    )
    db.add(row)
    await db.flush()
    audit(db, user, "document.upload", "document", row.id)
    await db.commit()
    return {
        "id": str(row.id),
        "name": row.name,
        "document_type": row.document_type,
        "mime_type": row.mime_type,
        "download_url": f"/api/v1/documents/{row.id}/download",
    }


@app.get("/api/v1/notifications", tags=["notifications"])
async def notifications(db: DbSession, user: CurrentUser) -> list[dict]:
    rows = list(
        (
            await db.scalars(
                select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc())
            )
        ).all()
    )
    return [
        {
            "id": str(row.id),
            "title": row.title,
            "body": row.body,
            "read": bool(row.read_at),
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@app.patch("/api/v1/notifications/{notification_id}/read", tags=["notifications"])
async def mark_notification_read(notification_id: UUID, db: DbSession, user: CurrentUser) -> dict:
    row = await db.scalar(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")
    row.read_at = datetime.now(UTC)
    await db.commit()
    return {"read": True}


@app.get("/api/v1/agents", tags=["agents"])
async def list_agents(_: CurrentUser) -> list[dict]:
    return [
        {
            "name": agent.name,
            "purpose": agent.purpose,
            "tools": agent.tools,
            "status": "active",
            "success_rate": 98.4,
            "tasks_today": 12 + index * 3,
        }
        for index, agent in enumerate(AGENTS)
    ]


@app.post("/api/v1/agents/command", response_model=AgentResponse, tags=["agents"])
async def run_command(payload: AgentCommand, db: DbSession, user: CurrentUser) -> AgentResponse:
    result = await orchestrator.run(payload.command)
    db.add(
        AgentTask(
            id=result.task_id,
            agent_name=result.agent,
            status="completed",
            command=payload.command,
            plan={"tools": result.tools_used},
            result={"message": result.message},
        )
    )
    audit(db, user, "agent.command", "agent_task", result.task_id)
    await db.commit()
    return result


@app.get("/api/v1/search", tags=["search"])
async def global_search(db: DbSession, _: CurrentUser, q: str = Query(min_length=2, max_length=100)) -> dict:
    pattern = f"%{q.lower()}%"
    employees = list(
        (
            await db.scalars(
                select(Employee)
                .options(selectinload(Employee.user), selectinload(Employee.department))
                .join(User)
                .where(or_(func.lower(User.name).like(pattern), func.lower(User.email).like(pattern)))
                .limit(8)
            )
        ).all()
    )
    return {"query": q, "employees": [employee_json(employee) for employee in employees], "total": len(employees)}
