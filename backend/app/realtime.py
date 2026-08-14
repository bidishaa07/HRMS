import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import WebSocket
from sqlalchemy import select

from .auth import decode_token
from .database import SessionLocal
from .models import EventOutbox, User


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[WebSocket, User] = {}

    async def connect(self, websocket: WebSocket, user: User) -> None:
        await websocket.accept()
        self.connections[websocket] = user
        await websocket.send_json({"type": "READY", "schema_version": 1, "status": "connected"})

    async def disconnect(self, websocket: WebSocket) -> None:
        self.connections.pop(websocket, None)

    @staticmethod
    def authorized(user: User, event: dict[str, Any]) -> bool:
        scope = event.get("scope", {})
        if user.company_name != scope.get("company_name"):
            return False
        if user.role in scope.get("roles", []):
            return True
        return str(user.id) == scope.get("employee_user_id")

    async def broadcast(self, event: dict[str, Any]) -> tuple[int, str | None]:
        recipients = [(socket, user) for socket, user in self.connections.items() if self.authorized(user, event)]
        delivered = 0
        errors: list[str] = []
        for websocket, _ in recipients:
            try:
                await websocket.send_json({"type": "EVENT", "event": event})
                delivered += 1
            except Exception as exc:  # pragma: no cover - depends on network failure timing
                errors.append(str(exc))
                await self.disconnect(websocket)
        return delivered, "; ".join(errors) if errors else None


manager = ConnectionManager()
dispatch_wakeup: asyncio.Event | None = None


async def authenticate_websocket(websocket: WebSocket, db) -> User | None:
    token = websocket.cookies.get("aurora_access")
    authorization = websocket.headers.get("authorization", "")
    if authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ")
    if not token:
        return None
    try:
        claims = decode_token(token, "access")
        user = await db.scalar(select(User).where(User.id == UUID(claims["sub"])))
    except (KeyError, ValueError):
        return None
    return user if user and user.is_active else None


def wake_dispatcher() -> None:
    if dispatch_wakeup is not None:
        dispatch_wakeup.set()


async def dispatch_outbox_once() -> None:
    async with SessionLocal() as db:
        rows = list(
            (
                await db.scalars(
                    select(EventOutbox)
                    .where(EventOutbox.published_at.is_(None))
                    .order_by(EventOutbox.occurred_at)
                    .limit(50)
                )
            ).all()
        )
        for row in rows:
            try:
                _, error = await manager.broadcast(row.payload)
                if error:
                    raise RuntimeError(error)
                row.published_at = datetime.now(UTC)
                row.last_error = None
            except Exception as exc:  # pragma: no cover - depends on network failure timing
                row.attempt_count += 1
                row.last_error = str(exc)[:1000]
        if rows:
            await db.commit()


async def dispatcher_loop(stop_event: asyncio.Event) -> None:
    global dispatch_wakeup
    wakeup = asyncio.Event()
    dispatch_wakeup = wakeup
    while not stop_event.is_set():
        wakeup.clear()
        await dispatch_outbox_once()
        try:
            await asyncio.wait_for(wakeup.wait(), timeout=1)
        except TimeoutError:
            pass
    dispatch_wakeup = None


async def stop_dispatcher(task: asyncio.Task, stop_event: asyncio.Event) -> None:
    stop_event.set()
    wake_dispatcher()
    with contextlib.suppress(asyncio.CancelledError):
        await task
