import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { Greeting } from "./components/Greeting";
import { StatusCard } from "./components/StatusCard";
import { StatsCard } from "./components/StatsCard";
import { PowerCard } from "./components/PowerCard";
import { AppsCard } from "./components/AppsCard";
import { ActivityCard } from "./components/ActivityCard";
import { Login } from "./components/Login";
import { Toaster, type Toast } from "./components/Toaster";
import {
  AuthError,
  clearSession,
  getSession,
  getStatus,
  sendCommand,
  type CommandName,
  type CommandResponse,
  type RelayStatus,
  type Session,
} from "./api";

const STATUS_POLL_MS = 4000;

export function App() {
  const [session, setSession] = useState<Session | null>(() => getSession());
  const [status, setStatus] = useState<RelayStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [tab, setTab] = useState("overview");
  const [auditTrigger, setAuditTrigger] = useState(0);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [whitelist, setWhitelist] = useState<{ apps: string[]; groups: string[] }>(
    { apps: [], groups: [] }
  );
  const toastSeq = useRef(0);

  const handleSignout = useCallback(() => {
    clearSession();
    setSession(null);
    setStatus(null);
    setWhitelist({ apps: [], groups: [] });
  }, []);

  const pushToast = useCallback((level: Toast["level"], message: string) => {
    toastSeq.current += 1;
    const id = toastSeq.current;
    setToasts((t) => [...t, { id, level, message }]);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  // Poll /v1/status
  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    let timer: number | null = null;

    async function tick() {
      try {
        const s = await getStatus(session!);
        if (cancelled) return;
        setStatus(s);
        setStatusError(null);
      } catch (e) {
        if (cancelled) return;
        if (e instanceof AuthError) {
          handleSignout();
          return;
        }
        setStatusError(String(e));
      }
      if (!cancelled) timer = window.setTimeout(tick, STATUS_POLL_MS);
    }
    tick();
    return () => {
      cancelled = true;
      if (timer != null) window.clearTimeout(timer);
    };
  }, [session, handleSignout]);

  // Whenever PC comes online, ask for status.get to refresh whitelist hints.
  // For the MVP we don't have a /v1/whitelist endpoint, so we infer apps/groups
  // from successful audit entries the user has triggered. To make the dashboard
  // immediately useful, we ALSO let the user define a local UI list via env
  // variable VITE_DEFAULT_APPS / VITE_DEFAULT_GROUPS at build time.
  useEffect(() => {
    const defaultApps = (import.meta.env.VITE_DEFAULT_APPS as string | undefined)?.split(",").map((s) => s.trim()).filter(Boolean) ?? [];
    const defaultGroups = (import.meta.env.VITE_DEFAULT_GROUPS as string | undefined)?.split(",").map((s) => s.trim()).filter(Boolean) ?? [];
    setWhitelist((prev) => ({
      apps: Array.from(new Set([...prev.apps, ...defaultApps])),
      groups: Array.from(new Set([...prev.groups, ...defaultGroups])),
    }));
  }, []);

  const onResult = useCallback(
    (cmd: CommandName, res: CommandResponse, label?: string) => {
      const nice = label ? `${cmd} (${label})` : cmd;
      if (res.status === "ok") {
        pushToast("ok", `${nice} — ok`);
      } else if (res.status === "agent_offline") {
        pushToast("warn", `${nice} — agent offline`);
      } else if (res.status === "timeout") {
        pushToast("warn", `${nice} — timeout`);
      } else if (res.status === "rate_limited") {
        pushToast("warn", `${nice} — rate limited`);
      } else {
        pushToast("err", `${nice} — ${res.message ?? res.code ?? "error"}`);
      }
      // Remember new app/group aliases the user has actually tried.
      const args = (res as unknown as { args?: { target?: string } }).args;
      const inferred = args?.target ?? label;
      if (inferred && cmd === "app.open") {
        setWhitelist((w) =>
          w.apps.includes(inferred) ? w : { ...w, apps: [...w.apps, inferred] }
        );
      }
      if (inferred && cmd === "group.run") {
        setWhitelist((w) =>
          w.groups.includes(inferred) ? w : { ...w, groups: [...w.groups, inferred] }
        );
      }
      setAuditTrigger((n) => n + 1);
    },
    [pushToast]
  );

  // Manual "refresh" → fire status.get (which is real on the agent) and bump audit.
  const refreshNow = useCallback(async () => {
    if (!session) return;
    const res = await sendCommand(session, "status.get", {});
    onResult("status.get", res);
  }, [session, onResult]);

  const pcOnline = Boolean(status?.pc);
  const bridgeOnline = Boolean(status?.bridge);
  const anyOnline = pcOnline || bridgeOnline;
  const hostname = useMemo(
    () => status?.pc?.status?.hostname ?? status?.pc?.agent_id,
    [status]
  );
  const nowMs = useMemo(() => (status ? status.now * 1000 : Date.now()), [status]);

  if (!session) {
    return <Login onSuccess={(s) => setSession(s)} />;
  }

  return (
    <div className="min-h-screen p-4 md:p-6 bg-ink-950">
      <div className="flex gap-4 md:gap-6">
        <Sidebar active={tab} onChange={setTab} onLogout={handleSignout} />

        <main className="flex-1 grid gap-4 md:gap-6 grid-cols-1 lg:grid-cols-3">
          {/* row 1 */}
          <Greeting online={anyOnline} hostname={hostname ?? undefined} />
          <StatusCard pc={status?.pc ?? null} bridge={status?.bridge ?? null} nowMs={nowMs} />

          {/* row 2 */}
          <div className="lg:col-span-2">
            <PowerCard
              session={session}
              pcOnline={pcOnline}
              bridgeOnline={bridgeOnline}
              onResult={onResult}
            />
          </div>
          <StatsCard pc={status?.pc ?? null} />

          {/* row 3 */}
          <div className="lg:col-span-2">
            <AppsCard
              session={session}
              pcOnline={pcOnline}
              apps={whitelist.apps}
              groups={whitelist.groups}
              onResult={onResult}
            />
          </div>
          <ActivityCard session={session} trigger={auditTrigger} />

          {/* footer */}
          <div className="lg:col-span-3 flex flex-wrap items-center justify-between text-[11px] text-ink-400 px-2">
            <div className="flex items-center gap-2">
              <span>Connected to</span>
              <code className="text-ink-200">{session.baseUrl}</code>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={refreshNow}
                className="hover:text-ink-100 transition-colors"
              >
                Refresh
              </button>
              {statusError && <span className="text-err">status: {statusError}</span>}
            </div>
          </div>
        </main>
      </div>

      <Toaster toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
