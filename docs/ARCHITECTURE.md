# Architecture

Aurora is a modular monorepo with a Next.js presentation layer and a FastAPI application layer. The backend follows feature-oriented clean architecture: HTTP handlers validate contracts; services own use cases; repositories own persistence; agents can invoke services only through registered tools.

## Runtime boundaries

```mermaid
flowchart TB
  subgraph Browser
    UI[Responsive App Router UI]
    Q[TanStack Query / Forms]
  end
  subgraph API
    H[Versioned REST handlers]
    Auth[JWT + OAuth + RBAC]
    D[HR domain services]
    Audit[Audit service]
  end
  subgraph AI_Control_Plane
    Router[Intent router]
    Workflow[Agent Framework workflows]
    Memory[Session memory]
    Tools[Typed HR tools]
  end
  subgraph Data
    DB[(PostgreSQL + pgvector)]
    Cache[(Redis)]
    Files[(MinIO)]
  end
  UI --> H
  Q --> H
  H --> Auth
  Auth --> D
  H --> Router
  Router --> Workflow
  Workflow --> Memory
  Workflow --> Tools
  Tools --> D
  D --> DB
  D --> Cache
  D --> Files
  D --> Audit
```

## Data model

```mermaid
erDiagram
  USERS ||--o| EMPLOYEES : owns
  DEPARTMENTS ||--o{ EMPLOYEES : contains
  EMPLOYEES ||--o{ ATTENDANCE : records
  EMPLOYEES ||--o{ LEAVE_REQUESTS : requests
  EMPLOYEES ||--o{ PAYROLL : receives
  EMPLOYEES ||--o{ DOCUMENTS : uploads
  USERS ||--o{ NOTIFICATIONS : receives
  USERS ||--o{ AUDIT_LOGS : performs
  AGENT_TASKS ||--o{ AUDIT_LOGS : produces
  AGENT_TASKS ||--o{ AGENT_MEMORY : uses
```

Core models are in `backend/app/models.py`. PostgreSQL JSONB stores explainable agent plans and salary component breakdowns; pgvector is reserved for policy/document embeddings.

## Security decisions

- Short-lived access tokens and rotated refresh tokens; refresh token hashes are stored, never raw tokens.
- RBAC is checked at use-case boundaries, not only route middleware.
- Agent tools are least-privilege and auditable. Destructive operations require an explicit user confirmation stage.
- Uploads use allowlisted MIME types, generated object keys, size limits, and malware scanning in production.
- CORS is allowlisted; responses include anti-sniffing, frame, referrer, and browser-permission headers.
- Salary, government ID, and token fields must be encrypted at rest in production.

