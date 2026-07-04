# AI workforce

Aurora uses OpenRouter as the primary model endpoint for agent reasoning. If OpenRouter is unavailable, it falls back to the local Microsoft Agent Framework `OllamaChatClient`, and then to deterministic demo insights so the HRMS remains usable.

The orchestrator performs four steps: classify intent, select the least-privilege specialist, offer typed tools, and record the plan/result with an explanation. If no model endpoint is ready, the same route produces deterministic insights from demo data instead of failing the HRMS.

| Agent | Primary workflows | Tools |
|---|---|---|
| HR Copilot | natural-language HR operations | employee search, delegation |
| Attendance | missing checkout, late arrival, reports | attendance read, reminders |
| Leave | balance, conflicts, recommendations | balance read, leave update |
| Payroll | payslip and deduction explanations | payroll read, PDF generation |
| Onboarding | employee provisioning and checklist | create employee, email |
| Employee Insights | health and burnout scoring | score and risk calculators |
| Analytics | executive and departmental reports | metric aggregation, export |
| Notification | email, in-app, escalations | notification and SMTP tools |
| Policy Assistant | grounded policy Q&A | vector search and citations |
| Resume Intelligence | structured resume extraction | text extraction, profile update |

## RAG design

Documents are extracted, split into 500–800 token chunks, embedded locally with `bge-small-en`, and saved in pgvector with document/organization ACL metadata. Retrieval filters by the caller's access before similarity search. Answers cite document name and section; insufficient evidence produces an explicit “not found” response.

## Explainability and safety

Every task stores agent, requester, intent, plan, selected tools, inputs hash, result, latency, retries, and approval state. Salary changes, leave decisions, employee creation, and outbound bulk email are human-in-the-loop operations.
