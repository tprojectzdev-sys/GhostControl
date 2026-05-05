"""Axon Remote — Wake-on-LAN bridge.

Run this on a tiny always-on box on your home LAN (Raspberry Pi Zero 2 W is
ideal). It connects out to the cloud relay and waits for a power.wake
command, at which point it emits a Wake-on-LAN magic packet on the local
broadcast address for the configured PC MAC.

Why this exists: a magic packet is a layer-2 broadcast. Routers don't
forward it from the WAN. Something has to be on the LAN to send it. This
bridge is that thing — and nothing more.

Required env vars:
    AXON_RELAY_URL        wss://<your-relay>.up.railway.app/v1/ws/agent
    AXON_BRIDGE_TOKEN     same value as the relay's BRIDGE_AGENT_TOKEN
    AXON_TARGET_MAC       MAC of the PC NIC, any of: AA:BB:CC:DD:EE:FF, AA-BB-..., AABBCC..

Optional env vars:
    AXON_AGENT_ID         default: hostname
    AXON_BROADCAST        default: 255.255.255.255  (use your subnet, e.g. 192.168.1.255, if your router drops 255.255.255.255)
    AXON_WOL_PORT         default: 9
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import socket
import sys
import time
from typing import Any

import websockets
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed


log = logging.getLogger("axon.bridge")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def _normalize_mac(mac: str) -> bytes:
    cleaned = re.sub(r"[^0-9a-fA-F]", "", mac)
    if len(cleaned) != 12:
        raise ValueError(f"MAC must have 12 hex digits, got {mac!r}")
    return bytes.fromhex(cleaned)


def _build_magic_packet(mac: str) -> bytes:
    return b"\xff" * 6 + _normalize_mac(mac) * 16


def send_wol(mac: str, broadcast: str, port: int) -> None:
    packet = _build_magic_packet(mac)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(packet, (broadcast, port))
        # Some NICs need the packet a couple of times.
        sock.sendto(packet, (broadcast, port))
    finally:
        sock.close()


class BridgeConfig:
    def __init__(self) -> None:
        self.relay_url = os.environ.get("AXON_RELAY_URL", "").strip()
        self.token = os.environ.get("AXON_BRIDGE_TOKEN", "").strip()
        self.agent_id = os.environ.get("AXON_AGENT_ID") or socket.gethostname()
        self.target_mac = os.environ.get("AXON_TARGET_MAC", "").strip()
        self.broadcast = os.environ.get("AXON_BROADCAST", "255.255.255.255").strip()
        self.port = int(os.environ.get("AXON_WOL_PORT", "9"))
        if not self.relay_url or not self.token or not self.target_mac:
            raise RuntimeError(
                "Missing AXON_RELAY_URL / AXON_BRIDGE_TOKEN / AXON_TARGET_MAC. See bridge/README.md."
            )
        # validate MAC up front
        _normalize_mac(self.target_mac)


async def run() -> None:
    cfg = BridgeConfig()
    delays = [1, 2, 5, 10, 30, 60]
    attempt = 0
    while True:
        try:
            await _one_session(cfg)
            attempt = 0
        except Exception as e:
            log.warning("session ended: %s", e)
            attempt += 1
        base = delays[min(attempt, len(delays) - 1)]
        wait = base + random.uniform(0, base * 0.3)
        log.info("reconnecting in %.1fs", wait)
        await asyncio.sleep(wait)


async def _one_session(cfg: BridgeConfig) -> None:
    log.info("connecting to %s as bridge id=%s", cfg.relay_url, cfg.agent_id)
    async with websockets.connect(
        cfg.relay_url,
        ping_interval=20,
        ping_timeout=20,
        max_size=1 << 20,
        open_timeout=15,
        close_timeout=5,
    ) as ws:
        await ws.send(json.dumps({
            "type": "hello",
            "role": "bridge",
            "agent_id": cfg.agent_id,
            "token": cfg.token,
            "version": "1.0",
            "hostname": socket.gethostname(),
        }))
        welcome = await asyncio.wait_for(ws.recv(), timeout=10)
        log.info("relay welcome: %s", welcome)

        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "ping":
                await ws.send(json.dumps({"type": "pong", "now": int(time.time())}))
                continue
            if msg.get("type") != "cmd":
                continue
            cmd = msg.get("command") or {}
            await _handle(ws, cmd, cfg)


async def _handle(ws: WebSocketClientProtocol, cmd: dict[str, Any], cfg: BridgeConfig) -> None:
    cmd_id = cmd.get("id")
    cmd_name = cmd.get("cmd")
    if not isinstance(cmd_id, str):
        return

    if cmd_name != "power.wake":
        ack = {
            "type": "ack",
            "id": cmd_id,
            "status": "error",
            "code": "rejected",
            "message": f"bridge only handles power.wake, got {cmd_name!r}",
        }
        try:
            await ws.send(json.dumps(ack))
        except ConnectionClosed:
            pass
        return

    started = time.monotonic()
    try:
        send_wol(cfg.target_mac, cfg.broadcast, cfg.port)
        ack = {
            "type": "ack",
            "id": cmd_id,
            "status": "ok",
            "data": {
                "action": "wol_sent",
                "mac": cfg.target_mac,
                "broadcast": cfg.broadcast,
                "port": cfg.port,
            },
            "latency_ms": int((time.monotonic() - started) * 1000),
        }
        log.info("sent magic packet to %s via %s:%d", cfg.target_mac, cfg.broadcast, cfg.port)
    except Exception as e:
        log.exception("WoL send failed")
        ack = {
            "type": "ack",
            "id": cmd_id,
            "status": "error",
            "code": "failed",
            "message": str(e),
        }
    try:
        await ws.send(json.dumps(ack))
    except ConnectionClosed:
        pass


def main() -> int:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
