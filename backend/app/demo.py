from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta
from uuid import NAMESPACE_DNS, UUID, uuid5

from .schemas import Employee, LeaveRequest, LeaveStatus, Role

DEPARTMENTS = ["Engineering", "HR", "Marketing", "Finance", "Sales", "Operations"]
FIRST_NAMES = ["Aarav", "Aditi", "Ananya", "Arjun", "Diya", "Ishaan", "Kavya", "Meera", "Neha", "Rahul"]
LAST_NAMES = ["Sharma", "Patel", "Rao", "Singh", "Gupta"]


def stable_id(value: str) -> UUID:
    return uuid5(NAMESPACE_DNS, f"aurora.hr/{value}")


def employees() -> list[Employee]:
    rng = random.Random(42)
    result: list[Employee] = []
    for index in range(50):
        first = FIRST_NAMES[index % len(FIRST_NAMES)]
        last = LAST_NAMES[(index // len(FIRST_NAMES)) % len(LAST_NAMES)]
        department = DEPARTMENTS[index % len(DEPARTMENTS)]
        result.append(
            Employee(
                id=stable_id(f"employee-{index}"),
                employee_code=f"AUR-{index + 1:04d}",
                name=f"{first} {last}",
                email=f"{first.lower()}.{last.lower()}{index}@aurora.example.com",
                role=Role.ADMIN if index == 0 else (Role.HR if index < 4 else Role.EMPLOYEE),
                department=department,
                title="People Partner" if department == "HR" else "Senior Associate",
                manager=None if index < 6 else result[index % 6].name,
                profile_completion=rng.randint(72, 100),
                health_score=rng.randint(68, 98),
            )
        )
    return result


def leave_requests() -> list[LeaveRequest]:
    people = employees()
    today = date.today()
    return [
        LeaveRequest(
            id=stable_id(f"leave-{index}"),
            employee_name=people[index + 4].name,
            leave_type=["Paid", "Sick", "Casual", "Unpaid"][index % 4],
            start_date=today + timedelta(days=index + 1),
            end_date=today + timedelta(days=index + 2),
            remarks=["Family commitment", "Medical appointment", "Personal work", "Travel"][index % 4],
            status=LeaveStatus.PENDING if index < 5 else LeaveStatus.APPROVED,
            days=2,
            recommendation="Approve — sufficient balance and no team conflict",
            created_at=datetime.now(UTC) - timedelta(hours=index * 3),
        )
        for index in range(8)
    ]
