"""Build a status report payload describing the local PC."""

from __future__ import annotations

import ctypes
import platform
import socket
import time
from typing import Any

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]


_BOOT_TIME: float | None = None


def _boot_time() -> float:
    global _BOOT_TIME
    if _BOOT_TIME is None:
        if psutil is not None:
            _BOOT_TIME = psutil.boot_time()
        else:
            _BOOT_TIME = time.time()
    return _BOOT_TIME


def _idle_seconds_windows() -> int | None:
    """Seconds since last keyboard/mouse input (whole desktop). None on non-Windows."""
    if platform.system() != "Windows":
        return None
    try:
        class _LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(lii)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):  # type: ignore[attr-defined]
            return None
        tick = ctypes.windll.kernel32.GetTickCount()  # type: ignore[attr-defined]
        millis = tick - lii.dwTime
        return max(0, int(millis / 1000))
    except Exception:
        return None


def _foreground_app_windows() -> str | None:
    if platform.system() != "Windows":
        return None
    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        psapi = ctypes.windll.psapi  # type: ignore[attr-defined]

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = ctypes.c_uint(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = kernel32.OpenProcess(0x0410, False, pid.value)  # PROCESS_QUERY_INFO|PROCESS_VM_READ
        if not h:
            return None
        try:
            buf = ctypes.create_unicode_buffer(512)
            length = psapi.GetModuleFileNameExW(h, 0, buf, 512)
            if length == 0:
                return None
            full = buf.value
            return full.rsplit("\\", 1)[-1]
        finally:
            kernel32.CloseHandle(h)
    except Exception:
        return None


def build_status() -> dict[str, Any]:
    now = time.time()
    cpu_pct: float | None = None
    ram_pct: float | None = None
    if psutil is not None:
        try:
            # cpu_percent without an interval returns 0.0 on first call but is non-blocking;
            # for a heartbeat that's fine (next call gets the real number).
            cpu_pct = float(psutil.cpu_percent(interval=None))
            ram_pct = float(psutil.virtual_memory().percent)
        except Exception:
            pass

    return {
        "type": "status",
        "online": True,
        "uptime_seconds": int(now - _boot_time()),
        "cpu_pct": cpu_pct,
        "ram_pct": ram_pct,
        "idle_seconds": _idle_seconds_windows(),
        "foreground_app": _foreground_app_windows(),
        "os": f"{platform.system()} {platform.release()} {platform.version()}".strip(),
        "hostname": socket.gethostname(),
    }
