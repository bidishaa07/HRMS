from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from random import Random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Attendance, Department, Employee, LeaveRequest, Notification, Payroll, User
from .security import hash_password

DEPARTMENTS = ["Engineering", "HR", "Marketing", "Finance", "Sales", "Operations"]
FIRST_NAMES = ["Aarav", "Aditi", "Ananya", "Arjun", "Diya", "Ishaan", "Kavya", "Meera", "Neha", "Rahul"]
LAST_NAMES = ["Sharma", "Patel", "Rao", "Singh", "Gupta"]


async def seed_database(db: AsyncSession) -> None:
    user_count = await db.scalar(select(func.count(User.id)))
    if user_count:
        pending_leave_count = await db.scalar(select(func.count(LeaveRequest.id)).where(LeaveRequest.status == "pending"))
        if not pending_leave_count:
            employee = await db.scalar(select(Employee.id).join(User).where(User.role == "employee").order_by(Employee.id))
            if employee is not None:
                db.add(
                    LeaveRequest(
                        employee_id=employee,
                        leave_type="Casual",
                        start_date=date.today() + timedelta(days=30),
                        end_date=date.today() + timedelta(days=31),
                        remarks="Planned family visit",
                        status="pending",
                    )
                )
                await db.commit()
        return

    departments: dict[str, Department] = {}
    for name in [*DEPARTMENTS, "Unassigned"]:
        department = Department(name=name, description=f"Aurora {name} team")
        departments[name] = department
        db.add(department)
    await db.flush()

    password = hash_password("Aurora@123")
    rng = Random(42)
    people: list[tuple[User, Employee]] = []
    year = date.today().year
    for index in range(50):
        first = FIRST_NAMES[index % len(FIRST_NAMES)]
        last = LAST_NAMES[(index // len(FIRST_NAMES)) % len(LAST_NAMES)]
        name = f"{first} {last}"
        department_name = DEPARTMENTS[index % len(DEPARTMENTS)]
        role = "admin" if index == 0 else ("hr" if index < 4 else "employee")
        login_id = f"AU{first[:2]}{last[:2]}{year}{index + 1:04d}".upper()
        user = User(
            email=(
                "admin@aurorahr.example.com"
                if index == 0
                else f"{first.lower()}.{last.lower()}{index}@aurorahr.example.com"
            ),
            login_id=login_id,
            name=name,
            company_name="Aurora HR",
            phone=f"+91 98765 {index:05d}",
            password_hash=password,
            role=role,
        )
        db.add(user)
        await db.flush()
        employee = Employee(
            user_id=user.id,
            employee_code=login_id,
            department_id=departments[department_name].id,
            title="Administrator"
            if index == 0
            else ("People Partner" if department_name == "HR" else "Senior Associate"),
            joining_date=date(year - rng.randint(0, 4), rng.randint(1, 12), rng.randint(1, 27)),
            salary=Decimal(65000 + index * 1250),
            profile_completion=rng.randint(75, 100),
            health_score=rng.randint(68, 98),
            location=["Bengaluru", "Mumbai", "Delhi", "Remote"][index % 4],
        )
        db.add(employee)
        people.append((user, employee))
    await db.flush()

    now = datetime.now(UTC)
    today = date.today()
    for index, (_, employee) in enumerate(people):
        if index < 43:
            check_in_hour = 10 if index < 6 else 9
            check_in = now.replace(hour=check_in_hour, minute=index % 45, second=0, microsecond=0)
            attendance = Attendance(
                employee_id=employee.id,
                work_date=today,
                check_in=check_in,
                status="late" if index < 6 else "present",
            )
            db.add(attendance)
        for days_ago in range(1, 8):
            work_day = today - timedelta(days=days_ago)
            if work_day.weekday() < 5:
                check_in = datetime.combine(work_day, datetime.min.time(), tzinfo=UTC).replace(
                    hour=9, minute=index % 30
                )
                check_out = check_in + timedelta(hours=8, minutes=15 + index % 40)
                db.add(
                    Attendance(
                        employee_id=employee.id,
                        work_date=work_day,
                        check_in=check_in,
                        check_out=check_out,
                        status="present",
                        work_minutes=int((check_out - check_in).total_seconds() / 60),
                    )
                )
        salary = employee.salary
        deductions = (salary * Decimal("0.12")).quantize(Decimal("0.01"))
        bonus = Decimal(2500 if index % 5 == 0 else 0)
        db.add(
            Payroll(
                employee_id=employee.id,
                period=today.strftime("%Y-%m"),
                basic=salary,
                bonuses=bonus,
                deductions=deductions,
                net_salary=salary + bonus - deductions,
                components={"basic": float(salary), "hra": float(salary * Decimal("0.4")), "pf": float(deductions)},
            )
        )

    leave_types = ["Paid", "Sick", "Casual", "Unpaid"]
    for index in range(8):
        db.add(
            LeaveRequest(
                employee_id=people[index + 4][1].id,
                leave_type=leave_types[index % 4],
                start_date=today + timedelta(days=index + 1),
                end_date=today + timedelta(days=index + 2),
                remarks=["Family commitment", "Medical appointment", "Personal work", "Travel"][index % 4],
                status="pending" if index < 5 else "approved",
            )
        )
    pending_leave_count = await db.scalar(select(func.count(LeaveRequest.id)).where(LeaveRequest.status == "pending"))
    if not pending_leave_count:
        db.add(
            LeaveRequest(
                employee_id=people[4][1].id,
                leave_type="Casual",
                start_date=today + timedelta(days=30),
                end_date=today + timedelta(days=31),
                remarks="Planned family visit",
                status="pending",
            )
        )
    admin = people[0][0]
    db.add(Notification(user_id=admin.id, title="Welcome to Aurora HR", body="Your workforce command center is ready."))
    db.add(
        Notification(
            user_id=admin.id,
            title="5 leave requests require review",
            body="Open Time Off to approve or reject requests.",
        )
    )
    await db.commit()
