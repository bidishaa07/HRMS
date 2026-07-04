from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import uuid4

import httpx

from .demo import employees, leave_requests
from .schemas import AgentResponse


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    purpose: str
    tools: tuple[str, ...]


AGENTS = (
    AgentDefinition(
        "HR Copilot", "Natural-language HR operations and delegation", ("search_employees", "delegate_task")
    ),
    AgentDefinition("Attendance Agent", "Attendance monitoring and escalation", ("get_attendance", "send_reminder")),
    AgentDefinition("Leave Agent", "Leave validation and recommendations", ("get_leave_balance", "update_leave")),
    AgentDefinition("Payroll Agent", "Payslip generation and salary explanation", ("get_payroll", "generate_payslip")),
    AgentDefinition(
        "Onboarding Agent", "New employee provisioning", ("create_employee", "create_checklist", "send_email")
    ),
    AgentDefinition("Employee Insights Agent", "Health and burnout signals", ("calculate_health", "detect_burnout")),
    AgentDefinition("Analytics Agent", "Executive and departmental reporting", ("aggregate_metrics", "export_report")),
    AgentDefinition("Notification Agent", "In-app and SMTP communication", ("create_notification", "send_email")),
    AgentDefinition("Policy Assistant", "RAG answers grounded in HR policy", ("search_policy", "cite_document")),
    AgentDefinition(
        "Resume Intelligence Agent", "Resume extraction and profile completion", ("extract_resume", "update_profile")
    ),
)


class AgentOrchestrator:
    """Microsoft Agent Framework adapter with safe offline demo fallback.

    Agents receive only callable tools; domain writes remain behind service methods. The optional
    framework import is intentionally lazy so the HRMS can start before Ollama/model setup.
    """

    async def run(self, command: str) -> AgentResponse:
        routed = self._route(command)
        try:
            result = await self._run_openrouter(routed, command)
            return AgentResponse(
                message=result,
                agent=routed.name,
                tools_used=list(routed.tools[:2]),
                explainability="Routed by intent and answered with OpenRouter using least-privilege HR context.",
                task_id=uuid4(),
            )
        except Exception:
            try:
                result = await self._run_framework(routed, command)
                return AgentResponse(
                    message=result,
                    agent=routed.name,
                    tools_used=list(routed.tools[:1]),
                    explainability="Routed by intent; OpenRouter was unavailable, so the local Microsoft Agent Framework adapter handled the task.",
                    task_id=uuid4(),
                )
            except Exception:
                return self._fallback(routed, command)

    async def _run_openrouter(self, definition: AgentDefinition, command: str) -> str:
        from .config import settings

        if not settings.openrouter_api_key:
            raise RuntimeError("OpenRouter API key is not configured")
        context = "\n".join(
            [
                "Known employees:",
                self.search_employees("").replace("; ", "\n"),
                "Pending leave:",
                self.list_pending_leave() or "No pending leave requests.",
            ]
        )
        payload = {
            "model": settings.openrouter_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"You are Aurora's {definition.name}. {definition.purpose}. "
                        "Use only the supplied HR context, say when data is unavailable, "
                        "and keep responses concise, auditable, and action-oriented."
                    ),
                },
                {"role": "user", "content": f"{context}\n\nRequest: {command}"},
            ],
            "temperature": 0.2,
            "max_tokens": 500,
        }
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": settings.frontend_url,
            "X-Title": settings.app_name,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.openrouter_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
        data = response.json()
        return str(data["choices"][0]["message"]["content"]).strip()

    async def _run_framework(self, definition: AgentDefinition, command: str) -> str:
        from agent_framework.ollama import OllamaChatClient

        from .config import settings

        agent = OllamaChatClient(host=settings.ollama_host, model_id=settings.ollama_model_id).as_agent(
            name=definition.name.replace(" ", ""),
            instructions=(
                f"You are Aurora's {definition.name}. {definition.purpose}. "
                "Explain decisions and never invent employee records."
            ),
            tools=[self.search_employees, self.list_pending_leave],
        )
        response = await agent.run(command)
        return str(response)

    @staticmethod
    def search_employees(query: str) -> str:
        """Search employees by name, department, title, or employee code."""
        query = query.lower()
        matches = [p for p in employees() if query in f"{p.name} {p.department} {p.title} {p.employee_code}".lower()]
        return "; ".join(f"{p.name} — {p.title}, {p.department}" for p in matches[:10]) or "No matching employees"

    @staticmethod
    def list_pending_leave() -> str:
        """List pending leave requests with recommendation."""
        pending = [item for item in leave_requests() if item.status == "pending"]
        return "; ".join(f"{item.employee_name}: {item.days} days, {item.recommendation}" for item in pending)

    @staticmethod
    def _route(command: str) -> AgentDefinition:
        lowered = command.lower()
        routes = {
            "attendance": 1,
            "absent": 1,
            "late": 1,
            "check in": 1,
            "leave": 2,
            "holiday": 2,
            "time off": 2,
            "salary": 3,
            "payroll": 3,
            "payslip": 3,
            "deduction": 3,
            "onboard": 4,
            "joining": 4,
            "new employee": 4,
            "burnout": 5,
            "health": 5,
            "workload": 5,
            "report": 6,
            "analytics": 6,
            "summary": 6,
            "notify": 7,
            "email": 7,
            "reminder": 7,
            "policy": 8,
            "handbook": 8,
            "benefit": 8,
            "resume": 9,
            "skills": 9,
            "experience": 9,
        }
        for phrase, index in routes.items():
            if phrase in lowered:
                return AGENTS[index]
        return AGENTS[0]

    def _fallback(self, definition: AgentDefinition, command: str) -> AgentResponse:
        lowered = command.lower()
        if "absent" in lowered:
            message = "4 employees are absent today: Kavya Sharma, Rahul Patel, Meera Rao, and Arjun Singh. Two are on approved leave."
            tools = ["get_attendance"]
        elif "leave" in lowered:
            pending = [item for item in leave_requests() if item.status == "pending"]
            message = f"There are {len(pending)} pending requests. All currently have sufficient balance; 1 needs a team-coverage review."
            tools = ["get_leave_balance", "detect_conflicts"]
        elif re.search(r"salary|payroll|payslip", lowered):
            message = "June payroll is ₹4.82M for 50 employees. Net pay reflects basic, HRA, allowances, PF, professional tax, TDS, bonuses, and deductions."
            tools = ["get_payroll"]
        elif "burnout" in lowered or "health" in lowered:
            message = "Organization health is 87/100. Three employees show medium burnout risk due to long hours and no recent leave; no high-risk cases detected."
            tools = ["calculate_health", "detect_burnout"]
        else:
            message = f"I routed this to {definition.name}. The task is ready for review: \"{command}\". Configure OpenRouter or Ollama to execute generative planning."
            tools = list(definition.tools[:1])
        return AgentResponse(
            message=message,
            agent=definition.name,
            tools_used=tools,
            explainability="Intent matched to the least-privileged specialist; response uses deterministic demo data because OpenRouter and Ollama are unavailable.",
            task_id=uuid4(),
        )


orchestrator = AgentOrchestrator()
