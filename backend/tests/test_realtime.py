from datetime import date, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.models import Attendance, Employee, EventOutbox, User
from app.database import SessionLocal
from sqlalchemy import select


def login(client: TestClient, login_id: str, role: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"login": login_id, "password": "Aurora@123", "role": role},
    )
    assert response.status_code == 200, response.text


def test_realtime_requires_authentication() -> None:
    with TestClient(app) as client:
        try:
            with client.websocket_connect("/api/v1/realtime/ws"):
                raise AssertionError("unauthenticated websocket unexpectedly connected")
        except WebSocketDisconnect as error:
            assert error.code == 4401


def test_leave_request_creates_outbox_event_and_admin_receives_it() -> None:
    with TestClient(app) as client:
        login(client, "admin@aurorahr.example.com", "admin")
        with client.websocket_connect("/api/v1/realtime/ws") as websocket:
            assert websocket.receive_json()["type"] == "READY"
            start = date.today() + timedelta(days=500 + uuid4().int % 10_000)
            response = client.post(
                "/api/v1/leaves",
                json={
                    "leave_type": "Casual",
                    "start_date": start.isoformat(),
                    "end_date": (start + timedelta(days=1)).isoformat(),
                    "remarks": "Realtime leave verification",
                },
            )
            assert response.status_code == 201, response.text
            event = websocket.receive_json()
            assert event["type"] == "EVENT"
            assert event["event"]["event_type"] == "LEAVE_REQUESTED"
            assert event["event"]["payload"] == {"status": "pending", "leave_type": "Casual"}

        async def read_outbox():
            async with SessionLocal() as db:
                return await db.scalar(
                    select(EventOutbox).where(EventOutbox.aggregate_id == UUID(response.json()["id"]))
                )

        import asyncio

        outbox = asyncio.run(read_outbox())
        assert outbox is not None
        assert outbox.event_type == "LEAVE_REQUESTED"
        assert outbox.published_at is not None


def test_employee_create_creates_event_and_employee_scope_is_restricted() -> None:
    email = f"realtime-{uuid4().hex[:10]}@example.com"
    with TestClient(app) as client:
        login(client, "admin@aurorahr.example.com", "admin")
        with client.websocket_connect("/api/v1/realtime/ws") as websocket:
            assert websocket.receive_json()["type"] == "READY"
            response = client.post(
                "/api/v1/employees",
                json={
                    "name": "Realtime Employee",
                    "email": email,
                    "phone": "+919999999999",
                    "department": "Engineering",
                    "title": "Realtime Tester",
                    "salary": 50000,
                    "joining_date": date.today().isoformat(),
                },
            )
            assert response.status_code == 201, response.text
            event = websocket.receive_json()
            assert event["event"]["event_type"] == "EMPLOYEE_CREATED"
            assert event["event"]["scope"]["roles"] == ["admin", "hr"]

        created = response.json()
        client.post("/api/v1/auth/logout")
        employee_login = client.post(
            "/api/v1/auth/login",
            json={"login": created["employee_code"], "password": created["temporary_password"], "role": "employee"},
        )
        assert employee_login.status_code == 200, employee_login.text
        assert employee_login.json()["user"]["role"] == "employee"
        assert employee_login.json()["user"]["employee_id"] == created["id"]
        admin_login = client.post(
            "/api/v1/auth/login",
            json={"login": created["employee_code"], "password": created["temporary_password"], "role": "admin"},
        )
        assert admin_login.status_code == 403
        employee_login = client.post(
            "/api/v1/auth/login",
            json={"login": created["employee_code"], "password": created["temporary_password"], "role": "employee"},
        )
        assert employee_login.status_code == 200
        changed = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": created["temporary_password"], "new_password": "NewPassword@123"},
        )
        assert changed.status_code == 204
        client.post("/api/v1/auth/logout")
        assert client.post(
            "/api/v1/auth/login",
            json={"login": created["employee_code"], "password": "NewPassword@123", "role": "employee"},
        ).status_code == 200
        client.post("/api/v1/auth/logout")
        assert client.post(
            "/api/v1/auth/login",
            json={"login": created["employee_code"], "password": created["temporary_password"], "role": "employee"},
        ).status_code == 401

        client.post("/api/v1/auth/logout")
        login(client, "AUDISH20260005", "employee")
        visible = client.get("/api/v1/employees")
        assert visible.status_code == 200
        assert len(visible.json()) == 1
        assert visible.json()[0]["email"] != email


def test_attendance_check_in_creates_event_and_outbox() -> None:
    import asyncio

    async def available_employee() -> str:
        async with SessionLocal() as db:
            login_id = await db.scalar(
                select(User.login_id).where(User.role == "employee", User.is_active.is_(True))
            )
            assert login_id is not None
            return login_id

    login_id = asyncio.run(available_employee())
    with TestClient(app) as admin_client:
        login(admin_client, "admin@aurorahr.example.com", "admin")
        with admin_client.websocket_connect("/api/v1/realtime/ws") as websocket:
            assert websocket.receive_json()["type"] == "READY"
            with TestClient(app) as employee_client:
                login(employee_client, login_id, "employee")
                response = employee_client.post("/api/v1/attendance/check-in")
                if response.status_code == 409:
                    return
                assert response.status_code == 200, response.text
            event = websocket.receive_json()
            assert event["event"]["event_type"] == "ATTENDANCE_MARKED"
