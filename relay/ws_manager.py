"""WebSocket connection registry.

Tracks the (at most one) PC agent and (at most one) bridge agent connected
at any time. Forwards commands to the right agent and awaits an ACK with
a timeout.

The relay is single-user, single-PC, single-bridge in this MVP. Multi-PC
support is purely additive (key the registry on agent_id) and is out of
scope for now.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket


@dataclass
class AgentConn:
    role: str
    agent_id: str
    ws: WebSocket
    connected_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    last_status: dict[str, Any] | None = None
    pending: dict[str, asyncio.Future] = field(default_factory=dict)

    def is_alive(self) -> bool:
        # FastAPI wraps starlette; client_state == 1 means CONNECTED.
        try:
            return self.ws.client_state.value == 1
        except Exception:
            return False


class WSManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._pc: AgentConn | None = None
        self._bridge: AgentConn | None = None

    async def attach(self, role: str, agent_id: str, ws: WebSocket) -> AgentConn:
        async with self._lock:
            old: AgentConn | None = None
            conn = AgentConn(role=role, agent_id=agent_id, ws=ws)
            if role == "pc":
                old, self._pc = self._pc, conn
            elif role == "bridge":
                old, self._bridge = self._bridge, conn
            else:
                raise ValueError(f"unknown role {role!r}")
        if old is not None:
            try:
                await old.ws.close(code=4001, reason="replaced")
            except Exception:
                pass
        return conn

    async def detach(self, conn: AgentConn) -> None:
        async with self._lock:
            if conn.role == "pc" and self._pc is conn:
                self._pc = None
            elif conn.role == "bridge" and self._bridge is conn:
                self._bridge = None
        for fut in conn.pending.values():
            if not fut.done():
                fut.set_exception(ConnectionResetError("agent disconnected"))
        conn.pending.clear()

    def status(self) -> dict[str, Any]:
        def _info(c: AgentConn | None) -> dict[str, Any] | None:
            if c is None:
                return None
            return {
                "agent_id": c.agent_id,
                "role": c.role,
                "connected_at": int(c.connected_at),
                "last_seen": int(c.last_seen),
                "uptime_seconds": int(time.time() - c.connected_at),
                "status": c.last_status or {},
            }

        return {
            "pc": _info(self._pc),
            "bridge": _info(self._bridge),
            "now": int(time.time()),
        }

    def get_target(self, role: str) -> AgentConn | None:
        return self._pc if role == "pc" else self._bridge if role == "bridge" else None

    async def send_and_wait(
        self,
        role: str,
        command: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        """Push a command frame to the target agent and wait for an ACK.

        Raises:
            LookupError when no agent of that role is connected.
            asyncio.TimeoutError when the agent fails to ack in time.
        """
        target = self.get_target(role)
        if target is None or not target.is_alive():
            raise LookupError(f"no {role} agent connected")

        loop = asyncio.get_running_loop()
        fut: asyncio.Future[dict[str, Any]] = loop.create_future()
        cmd_id = command["id"]
        target.pending[cmd_id] = fut

        frame = {"type": "cmd", "command": command}
        try:
            await target.ws.send_text(json.dumps(frame, separators=(",", ":")))
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            target.pending.pop(cmd_id, None)

    def resolve_ack(self, conn: AgentConn, ack: dict[str, Any]) -> bool:
        cmd_id = ack.get("id")
        if not cmd_id:
            return False
        fut = conn.pending.get(cmd_id)
        if fut is None or fut.done():
            return False
        fut.set_result(ack)
        return True
