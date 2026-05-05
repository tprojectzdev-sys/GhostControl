"""Local whitelist loader.

The whitelist lives in a YAML file on the PC. The agent reads it at startup
and re-reads it on file change. The relay never sees this file. The phone
never sees this file. Only the agent translates an alias into a real path.

YAML schema:

    apps:
      <alias>: <absolute exe path>
      # OR
      <alias>:
        path: <absolute exe path>
        args: ["--flag", "value"]   # optional fixed args

    groups:
      <alias>:
        - { cmd: app.open, args: { target: vscode } }
        - { cmd: url.open, args: { url: "https://github.com" } }

    url_policy:
      mode: "allow_any_https" | "allowlist"
      allowlist: ["youtube.com", "github.com", "*.notion.so"]
"""

from __future__ import annotations

import fnmatch
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import yaml


log = logging.getLogger("axon.agent.whitelist")


@dataclass
class AppEntry:
    alias: str
    path: str
    args: list[str] = field(default_factory=list)


@dataclass
class UrlPolicy:
    mode: str = "allow_any_https"   # or "allowlist"
    allowlist: list[str] = field(default_factory=list)


@dataclass
class Whitelist:
    apps: dict[str, AppEntry] = field(default_factory=dict)
    groups: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    url_policy: UrlPolicy = field(default_factory=UrlPolicy)
    loaded_at: float = 0.0
    source_path: str = ""

    def url_allowed(self, url: str) -> bool:
        if not url.startswith(("http://", "https://")):
            return False
        if self.url_policy.mode == "allow_any_https":
            return url.startswith("https://")
        try:
            host = (urlparse(url).hostname or "").lower()
        except Exception:
            return False
        if not host:
            return False
        for pattern in self.url_policy.allowlist:
            if fnmatch.fnmatch(host, pattern.lower()):
                return True
        return False


class WhitelistManager:
    """Loads the YAML whitelist and reloads it when the file mtime changes."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._wl = Whitelist(source_path=path)
        self._mtime: float = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def get(self) -> Whitelist:
        with self._lock:
            return self._wl

    def load(self) -> Whitelist:
        try:
            mtime = os.path.getmtime(self.path)
        except OSError as e:
            log.error("whitelist file %s missing: %s", self.path, e)
            wl = Whitelist(source_path=self.path, loaded_at=time.time())
            with self._lock:
                self._wl = wl
            return wl
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            log.error("whitelist YAML error in %s: %s — running with EMPTY whitelist", self.path, e)
            wl = Whitelist(source_path=self.path, loaded_at=time.time())
            with self._lock:
                self._wl = wl
            self._mtime = mtime
            return wl

        wl = self._parse(data)
        wl.source_path = self.path
        wl.loaded_at = time.time()
        with self._lock:
            self._wl = wl
        self._mtime = mtime
        log.info(
            "whitelist loaded: %d apps, %d groups, url_policy=%s",
            len(wl.apps), len(wl.groups), wl.url_policy.mode,
        )
        return wl

    def _parse(self, data: dict[str, Any]) -> Whitelist:
        wl = Whitelist()

        apps_in = data.get("apps") or {}
        if not isinstance(apps_in, dict):
            log.warning("whitelist 'apps' is not a mapping; ignored")
            apps_in = {}
        for alias, val in apps_in.items():
            if not isinstance(alias, str) or not alias:
                continue
            if isinstance(val, str):
                wl.apps[alias] = AppEntry(alias=alias, path=val)
            elif isinstance(val, dict):
                path = val.get("path")
                if not isinstance(path, str) or not path:
                    log.warning("app %r missing 'path'; skipped", alias)
                    continue
                args = val.get("args") or []
                if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
                    log.warning("app %r 'args' must be a list of strings; skipped", alias)
                    continue
                wl.apps[alias] = AppEntry(alias=alias, path=path, args=list(args))

        groups_in = data.get("groups") or {}
        if isinstance(groups_in, dict):
            for alias, steps in groups_in.items():
                if not isinstance(alias, str) or not isinstance(steps, list):
                    continue
                clean: list[dict[str, Any]] = []
                for step in steps:
                    if not isinstance(step, dict):
                        continue
                    cmd = step.get("cmd")
                    args = step.get("args") or {}
                    if not isinstance(cmd, str) or not isinstance(args, dict):
                        continue
                    clean.append({"cmd": cmd, "args": args})
                if clean:
                    wl.groups[alias] = clean

        policy = data.get("url_policy") or {}
        if isinstance(policy, dict):
            mode = policy.get("mode") or "allow_any_https"
            if mode not in ("allow_any_https", "allowlist"):
                mode = "allow_any_https"
            allowlist = policy.get("allowlist") or []
            if not isinstance(allowlist, list):
                allowlist = []
            allowlist = [s for s in allowlist if isinstance(s, str)]
            wl.url_policy = UrlPolicy(mode=mode, allowlist=allowlist)

        return wl

    # --- background watcher --------------------------------------------------

    def start_watcher(self, poll_seconds: float = 2.0) -> None:
        if self._thread is not None:
            return

        def _loop() -> None:
            while not self._stop.is_set():
                try:
                    mtime = os.path.getmtime(self.path)
                    if mtime != self._mtime:
                        log.info("whitelist file changed, reloading")
                        self.load()
                except OSError:
                    pass
                self._stop.wait(poll_seconds)

        t = threading.Thread(target=_loop, name="whitelist-watcher", daemon=True)
        t.start()
        self._thread = t

    def stop_watcher(self) -> None:
        self._stop.set()
        t = self._thread
        if t is not None:
            t.join(timeout=2.0)
        self._thread = None
