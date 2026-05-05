import { useState } from "react";
import { AppWindow, Globe, Layers, Send } from "lucide-react";
import type { CommandName, CommandResponse, Session } from "../api";
import { sendCommand } from "../api";

interface Props {
  session: Session;
  pcOnline: boolean;
  apps: string[];
  groups: string[];
  onResult: (cmd: CommandName, res: CommandResponse, label?: string) => void;
}

export function AppsCard({ session, pcOnline, apps, groups, onResult }: Props) {
  const [pending, setPending] = useState<string | null>(null);
  const [url, setUrl] = useState("");
  const [tab, setTab] = useState<"apps" | "groups" | "url">("apps");

  async function launch(cmd: CommandName, args: Record<string, string>, label?: string) {
    const key = `${cmd}:${args.target ?? args.url ?? ""}`;
    setPending(key);
    try {
      const res = await sendCommand(session, cmd, args);
      onResult(cmd, res, label);
    } finally {
      setPending(null);
    }
  }

  async function submitUrl(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;
    let normalized = trimmed;
    if (!/^https?:\/\//i.test(normalized)) normalized = "https://" + normalized;
    await launch("url.open", { url: normalized }, normalized);
  }

  return (
    <div className="card p-6 flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div className="text-sm text-ink-300 uppercase tracking-[0.18em]">Launcher</div>
        <Tabs tab={tab} onChange={setTab} />
      </div>

      {tab === "apps" && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {apps.length === 0 && <Empty hint="No apps registered. Edit whitelist.yaml on the PC." />}
          {apps.map((alias) => {
            const key = `app.open:${alias}`;
            return (
              <button
                key={alias}
                type="button"
                disabled={!pcOnline || pending === key}
                onClick={() => launch("app.open", { target: alias }, alias)}
                className="action-tile h-24"
                title={"app.open " + alias}
              >
                <span className="w-8 h-8 rounded-lg bg-accent/10 text-accent grid place-items-center">
                  <AppWindow size={16} strokeWidth={1.7} />
                </span>
                <div className="text-sm font-medium truncate">{alias}</div>
              </button>
            );
          })}
        </div>
      )}

      {tab === "groups" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {groups.length === 0 && (
            <Empty hint="No groups registered. Add some under groups: in whitelist.yaml." />
          )}
          {groups.map((alias) => {
            const key = `group.run:${alias}`;
            return (
              <button
                key={alias}
                type="button"
                disabled={!pcOnline || pending === key}
                onClick={() => launch("group.run", { target: alias }, alias)}
                className="action-tile h-24"
                title={"group.run " + alias}
              >
                <span className="w-8 h-8 rounded-lg bg-accent/10 text-accent grid place-items-center">
                  <Layers size={16} strokeWidth={1.7} />
                </span>
                <div>
                  <div className="text-sm font-medium">{alias}</div>
                  <div className="text-[11px] text-ink-400">action group</div>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {tab === "url" && (
        <form onSubmit={submitUrl} className="flex flex-col gap-3">
          <label className="text-[11px] text-ink-400 uppercase tracking-wider">
            Open URL on PC
          </label>
          <div className="flex gap-2">
            <div className="flex-1 flex items-center gap-2 px-3 py-2 rounded-2xl bg-ink-800 border border-white/[0.04] focus-within:border-accent/40">
              <Globe size={16} className="text-ink-400" />
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://youtube.com"
                className="flex-1 bg-transparent outline-none text-sm placeholder-ink-400"
              />
            </div>
            <button
              type="submit"
              disabled={!pcOnline || !url.trim() || pending !== null}
              className="px-4 rounded-2xl bg-accent/15 text-accent hover:bg-accent/25 disabled:opacity-50 transition-colors flex items-center gap-2 text-sm font-medium"
            >
              <Send size={14} />
              Send
            </button>
          </div>
          <div className="text-[11px] text-ink-400">
            Subject to your <code className="text-ink-200">url_policy</code> on the PC.
          </div>
        </form>
      )}
    </div>
  );
}

function Tabs({
  tab,
  onChange,
}: {
  tab: "apps" | "groups" | "url";
  onChange: (t: "apps" | "groups" | "url") => void;
}) {
  const items: { id: "apps" | "groups" | "url"; label: string }[] = [
    { id: "apps", label: "Apps" },
    { id: "groups", label: "Groups" },
    { id: "url", label: "URL" },
  ];
  return (
    <div className="flex p-1 rounded-chip bg-ink-800/80 border border-white/[0.04]">
      {items.map((i) => (
        <button
          key={i.id}
          type="button"
          onClick={() => onChange(i.id)}
          className={
            "px-3 py-1 text-xs rounded-chip transition-colors " +
            (tab === i.id
              ? "bg-white/[0.08] text-ink-100"
              : "text-ink-300 hover:text-ink-100")
          }
        >
          {i.label}
        </button>
      ))}
    </div>
  );
}

function Empty({ hint }: { hint: string }) {
  return (
    <div className="col-span-full text-sm text-ink-400 py-6 text-center">
      {hint}
    </div>
  );
}
