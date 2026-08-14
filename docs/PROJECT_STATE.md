# Aurora HR Project State

## Realtime

IMPLEMENTED FOR PHASE 1A AND PHASE 1B

## Leave realtime

IMPLEMENTED

## Outbox

IMPLEMENTED

## WebSocket

IMPLEMENTED

## TanStack Query

IMPLEMENTED FOR LEAVE, EMPLOYEES, AND ATTENDANCE

## Scope

Phase 1A implemented the leave vertical slice. Phase 1B adds employee create/update/deactivate and attendance check-in/check-out events through the same transactional outbox, dispatcher, scoped WebSocket, and TanStack Query invalidation path. Payroll, documents, departments, settings, analytics, and AI agents remain on their existing REST/state paths.

## Local runtime

The supported local topology is one FastAPI process using SQLite and a local uploads directory. The transactional outbox is durable in SQLite; the WebSocket connection manager and dispatcher are process-local. Multi-process realtime requires a shared database and event relay, as described in `docs/REALTIME_ARCHITECTURE.md`.
