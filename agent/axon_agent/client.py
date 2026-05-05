"""WebSocket client that keeps the agent connected to the relay.

  * Outbound only (WSS to the relay's /v1/ws/agent).
  * Sends a hello frame with role + agent_id + token immediately on connect.
  * Receives command frames and pushes acks back.
  * Periodic status heartbeats.
  * Exponential backoff with jitter on reconnect.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import socket
import time
from collections import OrderedDict
from typing import Any

import websockets
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed

from .executor import CommandFailed, CommandRejected, execute
from .status import build_status
from .whitelist import WhitelistManager


log = logging.getLogger("axon.agent.client")


HEARTBEAT_SECONDS = 30
DEDUP_WINDOW_SECONDS = 300
MAX_DEDUP_ENTRIES = 256


class AgentConfig:
    def __init__(
        self,
        relay_url: str,
        agent_token: str,
        role: str = "pc",
        agent_id: str | None = None,
        whitelist_path: str = "./whitelist.yaml",
    ) -> None:
        self.relay_url = relay_url
        self.agent_token = agent_token
        self.role = role
        self.agent_id = agent_id or socket.gethostname()
        self.whitelist_path = whitelist_path

    @classmethod
    def from_env(cls) -> "AgentConfig":
        url = os.environ.get("AXON_RELAY_URL", "").strip()
        token = os.environ.get("AXON_AGENT_TOKEN", "").strip()
        if not url or not token:
            raise RuntimeError(
                "Missing AXON_RELAY_URL or AXON_AGENT_TOKEN environment variables. "
                "See agent/README.md for setup."
            )
        return cls(
            relay_url=url,
            agent_token=token,
            role=os.environ.get("AXON_AGENT_ROLE", "pc"),
            agent_id=os.environ.get("AXON_AGENT_ID") or None,
            whitelist_path=os.environ.get("AXON_WHITELIST_PATH", "./whitelist.yaml"),
        )


class Agent:
    def __init__(self, cfg: AgentConfig) -> None:
        self.cfg = cfg
        self.wl = WhitelistManager(cfg.whitelist_path)
        self._dedup: "OrderedDict[str, float]" = OrderedDict()
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        self.wl.load()
        self.wl.start_watcher()
        try:
            await self._run_loop()
        finally:
            self.wl.stop_watcher()

    async def _run_loop(self) -> None:
        delays = [1, 2, 5, 10, 30, 60]
        attempt = 0
        while not self._stop.is_set():
            try:
                await self._one_session()
                attempt = 0
            except asyncio.CancelledError:
                raise
            except Exception as e:  # broad: we want to log and back off, never die
                log.warning("session ended: %s", e)
                attempt += 1

            if self._stop.is_set():
                break
            base = delays[min(attempt, len(delays) - 1)]
            jitter = random.uniform(0, base * 0.3)
            wait = base + jitter
            log.info("reconnecting in %.1fs (attempt %d)", wait, attempt)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=wait)
            except asyncio.TimeoutError:
                pass

    async def _one_session(self) -> None:
        log.info("connecting to %s as role=%s id=%s", self.cfg.relay_url, self.cfg.role, self.cfg.agent_id)
        async with websockets.connect(
            self.cfg.relay_url,
            ping_interval=20,
            ping_timeout=20,
            max_size=1 << 20,
            close_timeout=5,
            open_timeout=15,
        ) as ws:
            await self._hello(ws)
            welcome = await asyncio.wait_for(ws.recv(), timeout=10)
            log.info("relay welcome: %s", welcome)
            await self._send_status(ws)

            recv_task = asyncio.create_task(self._receive_loop(ws))
            beat_task = asyncio.create_task(self._heartbeat_loop(ws))

            done, pending = await asyncio.wait(
                {recv_task, beat_task, asyncio.create_task(self._stop.wait())},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
            for t in pending:
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
            for t in done:
                exc = t.exception()
                if exc and not isinstance(exc, (ConnectionClosed, asyncio.CancelledError)):
                    raise exc

    async def _hello(self, ws: WebSocketClientProtocol) -> None:
        import platform

        hello = {
            "type": "hello",
            "role": self.cfg.role,
            "agent_id": self.cfg.agent_id,
            "token": self.cfg.agent_token,
            "version": "1.0",
            "os": f"{platform.system()} {platform.release()}",
            "hostname": socket.gethostname(),
        }
        await ws.send(json.dumps(hello, separators=(",", ":")))

    async def _heartbeat_loop(self, ws: WebSocketClientProtocol) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            await self._send_status(ws)

    async def _send_status(self, ws: WebSocketClientProtocol) -> None:
        try:
            payload = build_status()
            await ws.send(json.dumps(payload, separators=(",", ":")))
        except Exception as e:
            log.debug("status send failed: %s", e)

    async def _receive_loop(self, ws: WebSocketClientProtocol) -> None:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("bad json from relay: %r", raw[:200])
                continue
            mtype = msg.get("type")
            if mtype == "cmd":
                cmd = msg.get("command") or {}
                asyncio.create_task(self._handle_command(ws, cmd))
            elif mtype == "ping":
                await ws.send(json.dumps({"type": "pong", "now": int(time.time())}))
            elif mtype in ("welcome", "pong"):
                continue
            else:
                log.debug("unknown frame type: %r", mtype)

    async def _handle_command(self, ws: WebSocketClientProtocol, cmd: dict[str, Any]) -> None:
        cmd_id = cmd.get("id")
        cmd_name = cmd.get("cmd")
        args = cmd.get("args") or {}

        if not isinstance(cmd_id, str) or not isinstance(cmd_name, str):
            return

        if self._is_duplicate(cmd_id):
            log.info("duplicate command id, dropping: %s", cmd_id)
            return

        wl = self.wl.get()
        started = time.monotonic()
        try:
            data = execute(cmd_name, args, wl)
            ack: dict[str, Any] = {
                "type": "ack",
                "id": cmd_id,
                "status": "ok",
                "data": data if isinstance(data, dict) else {"value": data},
                "latency_ms": int((time.monotonic() - started) * 1000),
            }
        except CommandRejected as e:
            ack = {
                "type": "ack",
                "id": cmd_id,
                "status": "error",
                "code": "rejected",
                "message": str(e),
            }
        except CommandFailed as e:
            ack = {
                "type": "ack",
                "id": cmd_id,
                "status": "error",
                "code": "failed",
                "message": str(e),
            }
        except Exception as e:  # last-resort
            log.exception("unexpected executor error")
            ack = {
                "type": "ack",
                "id": cmd_id,
                "status": "error",
                "code": "internal",
                "message": str(e),
            }
        try:
            await ws.send(json.dumps(ack, separators=(",", ":")))
        except ConnectionClosed:
            log.warning("ack dropped, connection closed")

    # --- dedup ---------------------------------------------------------------

    def _is_duplicate(self, cmd_id: str) -> bool:
        now = time.monotonic()
        # purge expired
        cutoff = now - DEDUP_WINDOW_SECONDS
        while self._dedup:
            oldest_id, t = next(iter(self._dedup.items()))
            if t < cutoff:
                self._dedup.popitem(last=False)
            else:
                break
        if cmd_id in self._dedup:
            return True
        if len(self._dedup) >= MAX_DEDUP_ENTRIES:
            self._dedup.popitem(last=False)
        self._dedup[cmd_id] = now
        return False
