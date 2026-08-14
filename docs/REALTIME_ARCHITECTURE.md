# Aurora HR Real-Time Architecture Audit

## Scope and conclusion

This is a Phase 0 audit of the existing Aurora HR application. No application source code was changed as part of this audit.

The application currently persists most mutations in the backend database and several screens refetch data after a successful mutation. It does not currently synchronize separate browser sessions automatically. There is no WebSocket endpoint, Server-Sent Events endpoint, polling loop, central domain-event dispatcher, transactional outbox, or frontend cache invalidation layer in use.

The recommended direction is:

```text
HTTP mutation
  -> authentication and RBAC
  -> domain service validation
  -> database transaction
  -> commit
  -> durable domain event/outbox record
  -> event dispatcher
  -> authorized WebSocket broadcast
  -> clients invalidate/refetch authoritative data
```

The database remains the source of truth. WebSocket messages are change notifications and synchronization hints, not client-owned copies of the database.

## 1. Current architecture

### Runtime boundaries

The repository is a monorepo with a Next.js frontend and a FastAPI backend.

```text
Browser
  Next.js App Router page
    React component state and useEffect data loading
      fetch-based API client
        FastAPI REST endpoints
          JWT cookie authentication and role checks
            SQLAlchemy AsyncSession
              SQLite + aiosqlite locally
              local uploads directory for document bytes
```

The current local database is SQLite at `backend/aurora.db`. PostgreSQL was previously configured but is not installed in the current environment. The backend runs with `sqlite+aiosqlite` for the local application.

### Backend structure

- `backend/app/main.py` contains the FastAPI application, startup/shutdown lifecycle, most REST route handlers, request validation models, authorization dependencies, database queries, mutations, audit writes, file storage, DOCX generation, notifications, and agent command handling.
- `backend/app/auth.py` contains registration, password login, JWT access/refresh cookie handling, logout, Google OAuth, current-user lookup, and role guards.
- `backend/app/database.py` creates the async SQLAlchemy engine/session factory, creates the schema at startup, and disposes the engine at shutdown.
- `backend/app/models.py` defines users, employees, departments, attendance, leave requests, payroll, documents, notifications, audit logs, agent tasks, and agent memory.
- `backend/app/agents.py` defines agent metadata and the orchestrator. OpenRouter is the primary model path with local/deterministic fallbacks.
- `backend/app/seed.py` populates the local database on first startup and adds a pending leave request when needed.
- `backend/app/schemas.py` contains several Pydantic contracts, although many route-local Pydantic models are defined directly in `main.py`.
- `backend/tests/test_api.py` is the current backend API test suite.

### API surface

The main route groups are:

- Authentication: register, login, current user, profile update, password change, provider status, refresh, logout, Google OAuth start/callback.
- Dashboard: summary metrics.
- Employees: list/search and admin-only creation.
- Attendance: list, check-in, check-out.
- Leave: list, apply, admin-only approve/reject.
- Payroll: list and DOCX payslip download.
- Organization: department list.
- Documents: list, detail, download, upload.
- Notifications: list and mark read.
- Agents: list, command execution, search.

These are implemented primarily as route handlers in `backend/app/main.py`, rather than as feature services called by both HTTP routes and agents.

### Data model

The SQLAlchemy model graph is:

```text
User 1 -- 0..1 Employee
Department 1 -- many Employee
Employee 1 -- many Attendance
Employee 1 -- many LeaveRequest
Employee 1 -- many Payroll
Employee 1 -- many Document
User 1 -- many Notification
User 1 -- many AuditLog
AgentTask and AgentMemory are persisted agent records
```

The models have `created_at` and `updated_at` timestamps through `TimestampMixin`, but there is no event sequence, version number, or mutation revision exposed to clients. Audit logs record actions, but they are not an event transport or replayable outbox.

### Authentication and authorization

Authentication uses short-lived JWT access and refresh tokens stored in HTTP-only cookies. The API also accepts a Bearer access token. The frontend API client retries a 401 once through `/auth/refresh` and then retries the original request.

Role values are `admin`, `hr`, and `employee`. Admin-only enforcement exists for employee creation and leave decisions. Employee list, attendance, leave, payroll, and document queries apply employee scoping where appropriate. Authorization must be applied again at WebSocket subscription and event delivery time; a connected client must not receive events merely because it authenticated earlier.

Google OAuth is the only configured external SSO provider. No real-time behavior currently depends on authentication events.

### Frontend structure and state

The primary shell is `frontend/src/components/aurora-app.tsx`. It owns the authenticated user, active view, notifications, and check-in/check-out display state. Feature modules under `frontend/src/components/modules/` use local `useState` and `useEffect` calls.

The API client is `frontend/src/lib/api.ts`. It uses `fetch`, credentials included, and a single refresh-and-retry path for expired access cookies. Although TanStack Query and Zustand appear in `package.json`, the current application does not use them as the central server-state layer.

The frontend generally:

- loads user, notifications, and attendance once when the shell mounts;
- loads feature data when a feature view mounts;
- updates local state immediately for some small actions;
- refetches after selected mutations, such as employee creation or document upload;
- has no shared cache, event subscription, query invalidation, version comparison, or cross-tab synchronization.

## 2. Current weaknesses

### No cross-session synchronization

There is no backend WebSocket/SSE route and no frontend `WebSocket`, `EventSource`, or polling implementation. User B will not learn about User A's change until a view remounts, the user manually refreshes, or that view happens to refetch.

### Mutations are concentrated in route handlers

Most database reads and writes are directly embedded in `main.py`. This makes it difficult to guarantee that every mutation emits the same event, applies the same transaction rules, or can be reused safely by an agent, background job, REST route, or future WebSocket command.

### No transactional event record

Audit logs are written in the same session as some mutations, but they are action records rather than a durable event queue. There is no record containing event type, payload, aggregate version, delivery status, or retry state. If a process commits a database mutation and then exits before broadcasting, there is nothing to replay.

### Commit and broadcast are not defined as separate stages

Existing routes commit directly and return. Because no event system exists, there is currently no explicit policy for what happens when event publication fails. The target behavior must be: a successful database commit is never rolled back because a broadcast failed; the event must be retried or recovered independently.

### Stale and concurrent UI state

Feature data is held in independent component state. Two browser tabs can show different employee, leave, attendance, payroll, or document lists. A local optimistic update can also become stale if another user changes the same record before the next refetch. There is no entity version or last-write/conflict policy.

### Notification system is pull-only

Notifications are stored in the database and read through `/api/v1/notifications`. The shell loads them once and marks individual notifications read. Notification creation is currently coupled to selected operations, such as leave decisions, but notifications are not delivered live.

### Document storage is not transactional with the database

Document bytes are written to the local `uploads` directory before the document metadata row is committed. A process failure between those two steps can leave an orphaned file; a database failure after the file write can leave the same problem. A later event design should define file finalization and cleanup behavior.

### Agent actions are not domain-service mediated

The agent command endpoint authenticates the caller and records an `AgentTask`, but the current architecture does not provide a shared domain-service/event boundary for all agent tools. Future agents must call the same authorized services as REST routes and must not write tables or emit business events directly.

### Documentation drift

`docs/ARCHITECTURE.md` describes PostgreSQL, Redis, MinIO, TanStack Query, and a service/repository architecture that does not match the current local implementation. Phase 1 should either update that document or clearly mark it as target architecture so operators do not mistake it for the current runtime.

## 3. Existing real-time capabilities

The existing application has no native real-time transport.

What does exist:

- REST responses return committed mutation results for most write routes.
- The API client includes credentials and attempts access-token refresh after a 401.
- Feature modules refetch after some successful mutations.
- Database timestamps can support future freshness checks, although they are not currently used for synchronization.
- Audit logs can help investigate changes, but cannot replay live updates.
- Notifications are persisted and can be refetched.

What does not exist:

- WebSocket or SSE endpoint.
- Connection manager.
- Central domain event type registry.
- Durable outbox/event table.
- Event IDs or sequence numbers.
- Per-user/per-role event authorization.
- Client event deduplication.
- Reconnect and authoritative resync protocol.
- Cross-tab BroadcastChannel synchronization.
- Real-time tests.

## 4. Recommended real-time architecture

### Core rule

Every business mutation should follow this sequence:

1. Authenticate the request.
2. Authorize the actor for the operation and target record.
3. Validate business rules in a domain service.
4. Mutate the database in one transaction.
5. Write an outbox/domain-event record in that same transaction.
6. Commit the transaction.
7. Treat the event as publishable only after commit succeeds.
8. Dispatch the event to connected clients and background consumers.
9. Let clients invalidate or refetch the affected authoritative resource.

The event dispatcher must never cause a successful database transaction to fail. If broadcasting fails, the outbox record remains available for retry.

### Transactional outbox

For the first implementation, add an `event_outbox` table containing at least:

- `id`: UUID event ID.
- `event_type`.
- `aggregate_type` and `aggregate_id`.
- `organization_id` or tenant boundary when multi-company data is introduced.
- `actor_id`.
- `payload` as JSON.
- `aggregate_version` or mutation version.
- `occurred_at`.
- `published_at`.
- `attempt_count`.
- `last_error`.

The domain service inserts this record in the same transaction as the business mutation. A dispatcher publishes committed, unpublished records and marks them published only after the delivery handoff succeeds. At-least-once delivery should be assumed; consumers and clients must be idempotent.

For a single local SQLite process, an in-process dispatcher can be sufficient for development, but the outbox should still be the durable recovery point. Do not rely only on an in-memory list or `asyncio.create_task`.

### Service boundary

Move mutations from `main.py` into feature services, for example:

- `employee_service.create_employee`.
- `attendance_service.check_in` and `check_out`.
- `leave_service.apply` and `decide`.
- `payroll_service.generate` and `approve`.
- `document_service.upload` and `delete`.
- `organization_service.update_department`.
- `settings_service.update`.
- `agent_service.run_command` and domain-specific tools.

Each service should own authorization checks, validation, transaction boundaries, audit writes, and event creation. REST handlers, background jobs, and agent tools should call services rather than duplicate the logic.

## 5. WebSocket strategy

### Endpoint

Add a versioned endpoint such as:

```text
GET /api/v1/realtime/ws
```

The connection should authenticate using the existing access cookie where same-origin deployment permits it. For a separate frontend/backend origin, validate the allowed Origin and use a short-lived WebSocket ticket obtained through an authenticated REST call rather than placing a long-lived JWT in a URL.

At connection time:

1. Authenticate the user.
2. Load role and scope information.
3. Register the connection in a connection manager.
4. Send a `READY` message with the server time and current event cursor.
5. Optionally send a small initial invalidation/resync instruction rather than the entire application state.

The server must validate the browser Origin, enforce connection limits, remove dead connections, and avoid leaking employee/payroll/document events across authorization boundaries.

### Broadcast scope

The connection manager should support targeted delivery:

- user-specific, for private notifications and employee-scoped data;
- role-specific, for admin approvals and configuration changes;
- organization/company-specific, once tenant identity is explicit;
- resource-specific, for a focused detail view.

The server should filter an event for each recipient, not broadcast every event to every authenticated connection.

### Delivery semantics

Use at-least-once delivery. The client must tolerate duplicate events. The server should not claim durable delivery merely because bytes were written to a socket. The outbox is the durable source for retry; WebSockets are a low-latency delivery path.

## 6. Event structure

Use a stable envelope with a versioned schema:

```json
{
  "event_id": "uuid",
  "event_type": "LEAVE_APPROVED",
  "schema_version": 1,
  "occurred_at": "2026-08-14T12:34:56Z",
  "aggregate": {
    "type": "leave_request",
    "id": "uuid",
    "version": 3
  },
  "actor": {
    "id": "uuid",
    "role": "admin"
  },
  "scope": {
    "user_ids": ["uuid"],
    "roles": ["admin"]
  },
  "correlation_id": "uuid",
  "payload": {
    "status": "approved"
  }
}
```

The event payload should be minimal and safe. It may contain identifiers, changed fields, and display hints, but should not become an untrusted replacement for an API response. Payroll amounts, documents, and private employee data require explicit recipient filtering.

Initial event registry:

| Event | Produced after | Primary client invalidations | Initial recipients |
|---|---|---|---|
| `EMPLOYEE_CREATED` | employee commit | employees, dashboard, organization | admins/HR, relevant organization |
| `EMPLOYEE_UPDATED` | employee/profile commit | employee detail, employees, dashboard | authorized viewers |
| `EMPLOYEE_DEACTIVATED` | status commit | employees, dashboard, auth state | admins/HR, affected user |
| `ATTENDANCE_MARKED` | check-in/check-out commit | attendance, dashboard, employee status | affected user, admins/HR |
| `ATTENDANCE_UPDATED` | attendance correction commit | attendance, dashboard, analytics | authorized viewers |
| `LEAVE_REQUESTED` | leave request commit | leave, dashboard, notifications | requester, admins/HR |
| `LEAVE_APPROVED` | approval commit | leave, dashboard, notifications | requester, admins/HR |
| `LEAVE_REJECTED` | rejection commit | leave, dashboard, notifications | requester, admins/HR |
| `PAYROLL_GENERATED` | payroll commit | payroll, dashboard, analytics | affected employee, admins |
| `PAYROLL_APPROVED` | approval commit | payroll, notifications, analytics | affected employee, admins |
| `DOCUMENT_UPLOADED` | metadata commit and file finalization | documents, employee detail | owner, admins/HR |
| `DOCUMENT_DELETED` | metadata/file deletion commit | documents, employee detail | owner, admins/HR |
| `DEPARTMENT_UPDATED` | department commit | organization, employees, dashboard | admins/HR, affected viewers |
| `AI_INSIGHT_CREATED` | insight commit | agents, notifications, analytics | authorized viewers |
| `AI_APPROVAL_REQUIRED` | approval task commit | agents, notifications | authorized approvers |
| `SETTINGS_UPDATED` | settings commit | settings, relevant feature caches | admins or affected user |

Avoid emitting an event before the transaction has committed. For a mutation that writes several related records, emit one domain event representing the completed business operation, not a stream of low-level SQL changes.

## 7. Client synchronization strategy

The client should treat events as invalidation messages:

```text
event received
  -> validate envelope and event_id
  -> ignore duplicate event_id
  -> map event type to affected query keys
  -> invalidate/refetch authoritative REST data
  -> update local notification badge or focused view
```

Adopt one shared server-state approach in Phase 1. TanStack Query is already present in `package.json` and is a suitable choice. It should own query keys, cache state, mutation invalidation, stale times, retries, and refetch-on-reconnect. Zustand can remain for UI-only state such as the active sidebar view, but should not become a second server-data cache.

Suggested query keys:

- `dashboard-summary`.
- `employees` with search/department parameters.
- `attendance` with month/employee parameters.
- `leaves` with status/user scope.
- `payroll` with period/user scope.
- `documents` and `document/:id`.
- `departments`.
- `notifications`.
- `agents` and agent task/insight data.
- `settings` and provider status.

After a local mutation, invalidate the same keys on the REST response. When the event arrives from another session, apply the same invalidation path. This keeps local and remote update behavior consistent.

Use an event cursor or `occurred_at` plus event ID for reconnect diagnostics. Do not apply an older event over newer server data. When a focused detail view receives a conflicting event, refetch the detail resource and let the server response win.

Cross-tab synchronization within one browser can optionally use `BroadcastChannel` to avoid duplicate REST refetches, but it is supplementary and must not replace server-side WebSocket delivery.

## 8. Reconnect strategy

The client should expose connection state without blocking normal REST use:

- `connected`: events are arriving.
- `connecting`: attempting a socket connection.
- `degraded`: REST still works but live delivery is unavailable.
- `offline`: browser/network unavailable.

On socket close:

1. Mark the connection degraded.
2. Retry with exponential backoff and jitter, for example 1s, 2s, 5s, 10s, then a capped interval.
3. Refresh the JWT session if the server reports authentication expiry.
4. Reconnect and send the last acknowledged event cursor if supported.
5. Refetch all active authoritative queries after reconnect, regardless of whether a replay was available.
6. Reset the cursor only after the resync completes.

On malformed, unauthorized, or unknown events, log a safe diagnostic and continue. Never let one bad event terminate all query synchronization.

The server should remove dead sockets, bound per-user connections, and make dispatcher retries observable. A failed broadcast must not roll back the original database commit.

## 9. SQLite considerations

### Safe for the current local application

SQLite is adequate for a single local backend process with modest traffic. It can safely provide:

- durable local persistence;
- transactional business mutations;
- a transactional outbox table;
- one in-process WebSocket connection manager;
- development and single-user testing of event ordering and reconnect behavior.

Use short transactions, avoid holding a transaction while calling OpenRouter or SMTP, enable appropriate SQLite busy timeout/WAL settings, and keep file writes outside the database transaction with explicit cleanup/finalization handling.

SQLite does not itself broadcast changes to WebSocket clients. The application must create and dispatch events after commit.

### Limits when scaling beyond one backend process

An in-memory connection manager is process-local. If two backend workers are running, User A connected to worker 1 will not receive an event broadcast by worker 2 unless both workers share a broker or a database-backed dispatcher. SQLite also has limited write concurrency and is a poor fit for multiple application instances sharing a filesystem database.

For local Phase 1, keep one backend process and use the outbox plus an in-process dispatcher. Add an explicit configuration guard so a multi-worker deployment cannot be mistaken for a supported SQLite realtime topology.

## 10. PostgreSQL migration considerations

PostgreSQL should be the production source of truth when the application supports concurrent users or multiple backend instances. It provides stronger concurrent write behavior, row-level locking, richer indexing, durable JSON operations, and operational tooling.

A production topology could be:

```text
FastAPI instances
  -> PostgreSQL primary
  -> Redis or PostgreSQL-backed event relay
  -> WebSocket connections on each instance
  -> object storage for documents
```

Migration work should include:

- Alembic migrations instead of startup-only `create_all`.
- Explicit indexes and constraints for event outbox records.
- PostgreSQL UUID, JSONB, timestamp, and numeric behavior verification.
- A shared event relay such as Redis Pub/Sub, Redis Streams, or a PostgreSQL `LISTEN/NOTIFY` bridge. `LISTEN/NOTIFY` is useful for low-latency wakeups but should not be the only durable event store.
- Shared object storage for document bytes and a database record for upload state.
- Connection pool sizing and transaction timeout policy.
- Idempotency keys for retried mutations.
- Observability for outbox lag, websocket counts, event delivery failures, and resync frequency.

## 11. AI event integration strategy

AI agents should consume the same committed domain events as the user-facing realtime layer, either through an outbox consumer or a typed event subscription service.

Example:

```text
ATTENDANCE_UPDATED
  -> Attendance Agent receives authorized event
  -> reads authoritative attendance/team data through a domain service
  -> analyzes anomaly
  -> writes an AI insight through an authorized service
  -> creates AI_INSIGHT_CREATED or AI_APPROVAL_REQUIRED
  -> notifies authorized admins
```

Agent rules:

- Agents never bypass normal service authorization.
- Agents never write database tables directly.
- Agent reads are scoped to the requesting user and task authorization.
- Destructive or consequential operations remain approval-gated.
- Agent outputs are persisted with task ID, source event ID, model/provider, plan, tools used, latency, status, and retry count.
- Duplicate event delivery must not create duplicate insights; use source event ID plus agent name as an idempotency key where appropriate.
- AI processing must be asynchronous and must not hold the originating business transaction open.
- OpenRouter failure, timeout, or malformed output must update task state and retry/degrade without affecting the original business commit.

## 12. Exact files to change in Phase 1

The following are the recommended Phase 1 change points. This audit does not modify them.

### Backend additions

- `backend/app/events.py`: event envelope, event type constants, payload validation, event ID/correlation helpers, and outbox write helpers.
- `backend/app/realtime.py`: connection manager, recipient authorization/filtering, broadcast adapter, connection lifecycle, and dispatcher retry behavior.
- `backend/app/services/`: feature services for employee, attendance, leave, payroll, document, organization, notification, and agent mutations.
- `backend/app/realtime_routes.py` or `backend/app/main.py`: authenticated WebSocket route registration. A dedicated router is preferred.

### Backend changes

- `backend/app/models.py`: add the transactional outbox/event model and any aggregate version columns required for conflict detection.
- `backend/app/database.py`: add transaction/session helpers and outbox dispatcher lifecycle hooks without holding database transactions across network calls.
- `backend/app/main.py`: reduce route handlers to request parsing, dependency injection, service invocation, and response mapping; route all mutations through services.
- `backend/app/auth.py`: add WebSocket authentication/origin validation support and ensure refresh/session expiry behavior is explicit for sockets.
- `backend/app/config.py`: add realtime enablement, websocket limits, retry intervals, SQLite single-process guard, and event retention settings.
- `backend/app/agents.py`: consume typed events through services/consumers and enforce idempotency and approval boundaries.
- `backend/app/schemas.py`: add event envelope and realtime connection contracts if Pydantic contracts are kept centralized.

### Frontend additions/changes

- `frontend/src/lib/realtime.ts`: WebSocket client, connection state, reconnect backoff, event validation, deduplication, and resync callback.
- `frontend/src/lib/api.ts`: expose authoritative query functions, optional event cursor/resync calls, and consistent API error handling.
- `frontend/src/components/aurora-app.tsx`: start/stop the authenticated realtime subscription and surface degraded/reconnecting state.
- `frontend/src/lib/query-client.ts` or `frontend/src/app/providers.tsx`: introduce a single TanStack Query client/provider if TanStack Query is selected.
- `frontend/src/components/modules/*.tsx`: migrate feature fetches/mutations to shared query keys and invalidation callbacks. Prioritize overview, people, attendance, leave, payroll, documents, organization, agents, and settings.
- `frontend/src/components/modules/documents-view.tsx`: use event invalidation for upload/delete and show authoritative upload state; later coordinate database metadata and file lifecycle states.

### Tests and documentation

- `backend/tests/test_api.py`: retain current REST coverage and add mutation/outbox assertions.
- `backend/tests/test_realtime.py`: WebSocket authentication, authorization, event filtering, duplicate handling, reconnect cursor, and failed broadcast behavior.
- `backend/tests/test_services.py`: transaction, authorization, event creation, and rollback behavior for each domain service.
- `frontend` test setup: add tests for event-to-query invalidation, reconnect resync, deduplication, and degraded mode.
- `docs/ARCHITECTURE.md`: reconcile current implementation versus target architecture.
- `docs/REALTIME_ARCHITECTURE.md`: update the audit with implementation decisions as Phase 1 lands.

## 13. Recommended implementation order

1. Freeze the event contract and recipient/RBAC rules. Decide whether events are invalidations only or include safe changed-field hints; use invalidations for the first version.
2. Introduce domain service boundaries for one vertical slice, preferably leave requests, because leave mutations already create notifications and have clear admin/employee authorization.
3. Add the outbox model and write the event in the same transaction as the leave service mutation.
4. Add a single-process dispatcher and authenticated WebSocket connection manager. Keep broadcast failure independent from database commit success.
5. Add the frontend realtime client and query invalidation for leave, notifications, and dashboard summary.
6. Add reconnect plus authoritative refetch and test two browser sessions.
7. Extend the service/outbox/event pattern to attendance and employees.
8. Extend it to documents, including file finalization, orphan cleanup, and a future `DOCUMENT_DELETED` operation.
9. Extend it to payroll, departments, settings, analytics, and agent insights.
10. Add idempotency, aggregate versions, event retention, metrics, structured logs, and failure injection tests.
11. Only then evaluate multi-worker deployment, shared broker requirements, PostgreSQL, and shared object storage.

### Phase 1 acceptance criteria

- User A's leave request appears in User B's authorized leave/admin view without manual refresh.
- Approval/rejection updates the requester notification and leave view without manual refresh.
- A committed mutation remains committed if WebSocket delivery fails.
- Reconnecting a browser causes authoritative refetch and removes stale data.
- Duplicate events do not duplicate rows, notifications, or AI insights.
- Unauthorized users receive neither restricted events nor restricted refetch results.
- The same service path is used by REST routes, background jobs, and AI tools.
- Two browser sessions work under the supported single-process SQLite topology.

## Audit evidence

The conclusions above are based on the current files:

- `backend/app/main.py`
- `backend/app/auth.py`
- `backend/app/database.py`
- `backend/app/models.py`
- `backend/app/agents.py`
- `backend/app/schemas.py`
- `backend/tests/test_api.py`
- `frontend/src/lib/api.ts`
- `frontend/src/components/aurora-app.tsx`
- `frontend/src/components/modules/*.tsx`
- `frontend/package.json`

No application source code was modified during Phase 0.

## Phase 1A implementation decisions

Phase 1A implements the first leave-only vertical slice without migrating SQLite or changing unrelated modules.

- `backend/app/services.py` now owns leave creation and admin decisions, including validation, authorization, audit logging, commit, and outbox creation.
- `backend/app/models.py` now includes the SQLite-compatible `event_outbox` table with event payload, aggregate version, publish status, retry count, and last error.
- `backend/app/events.py` defines `LEAVE_REQUESTED`, `LEAVE_APPROVED`, and `LEAVE_REJECTED` and creates the versioned event envelope.
- `backend/app/realtime.py` provides the authenticated connection manager and a durable-outbox-backed single-process dispatcher.
- `backend/app/main.py` exposes `/api/v1/realtime/ws` and starts/stops the dispatcher with the FastAPI lifespan.
- `frontend/src/lib/realtime.ts` handles WebSocket status, reconnect backoff, event validation, event-ID deduplication, and leave/notification query invalidation.
- `frontend/src/components/modules/leave-view.tsx` uses TanStack Query for leave data and invalidates authoritative REST queries after local mutations or realtime events.
- `frontend/src/components/query-provider.tsx` and `frontend/src/app/layout.tsx` provide the query client; other modules have not been migrated.

The event payload is intentionally minimal. Clients do not replace leave state from the payload; they refetch authoritative leave and notification data. Admin/HR events are scoped to the actor's company, while employee delivery is restricted to the employee associated with the leave request.

The dispatcher marks an outbox row published only after the current broadcast handoff succeeds. If delivery fails after the leave transaction commits, the row remains committed, unpublished, and retryable with `attempt_count` and `last_error` updated.

Phase 1A tests cover authenticated WebSocket readiness, unauthenticated rejection, leave event delivery to an authorized admin, outbox creation/publication, existing REST behavior, frontend lint, and frontend typecheck. Two-browser manual validation remains the final acceptance check for the local running application.
