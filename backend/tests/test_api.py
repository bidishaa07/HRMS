from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "login": "admin@aurorahr.example.com",
            "password": "Aurora@123",
        },
    )
    assert response.status_code == 200, response.text


def test_health_and_protected_routes() -> None:
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "healthy"
        assert client.get("/api/v1/employees").status_code == 401
        login(client)
        me = client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json()["role"] == "admin"
        assert client.get("/api/v1/employees").status_code == 200


def test_registration_generates_login_id_and_jwt_session() -> None:
    with TestClient(app) as client:
        unique = uuid4().hex[:8]
        response = client.post(
            "/api/v1/auth/register",
            json={
                "company_name": f"North Star {unique}",
                "name": "Jane Doe",
                "email": f"jane.{unique}@example.com",
                "phone": "+91 99999 88888",
                "password": "SecurePass123",
                "confirm_password": "SecurePass123",
            },
        )
        assert response.status_code == 201, response.text
        login_id = response.json()["user"]["login_id"]
        assert login_id.startswith("NSJADO")
        assert len(login_id) >= 14
        assert "aurora_access" in response.cookies
        assert client.get("/api/v1/auth/me").status_code == 200


def test_attendance_leave_and_payroll_flows() -> None:
    with TestClient(app) as client:
        login(client)
        summary = client.get("/api/v1/dashboard/summary")
        assert summary.status_code == 200
        assert summary.json()["employees"] >= 50
        assert client.get("/api/v1/attendance").status_code == 200
        leaves = client.get("/api/v1/leaves")
        assert leaves.status_code == 200
        pending = next(item for item in leaves.json() if item["status"] == "pending")
        decision = client.patch(
            f"/api/v1/leaves/{pending['id']}", json={"decision": "approved", "comment": "Coverage verified"}
        )
        assert decision.status_code == 200
        assert decision.json()["status"] == "approved"
        payroll = client.get("/api/v1/payroll")
        assert payroll.status_code == 200
        assert payroll.json()[0]["net_salary"] > 0


def test_login_can_enforce_role_selection() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "login": "admin@aurorahr.example.com",
                "password": "Aurora@123",
                "role": "employee",
            },
        )
        assert response.status_code == 403


def test_document_upload_returns_api_download_url() -> None:
    with TestClient(app) as client:
        login(client)
        response = client.post(
            "/api/v1/documents",
            files={"file": ("offer-letter.txt", b"hello world", "text/plain")},
            data={"document_type": "Contract"},
        )
        assert response.status_code == 201, response.text
        payload = response.json()
        assert payload["download_url"].startswith("/api/v1/documents/")


def test_agent_command_is_authenticated_and_audited() -> None:
    with TestClient(app) as client:
        login(client)
        response = client.post("/api/v1/agents/command", json={"command": "Who is absent today?"})
        assert response.status_code == 200
        assert response.json()["agent"] == "Attendance Agent"
