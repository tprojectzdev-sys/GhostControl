import { useState } from "react";
import { ArrowRight, Loader2, ShieldCheck } from "lucide-react";
import { probeRelay, saveSession, type Session } from "../api";

interface Props {
  initial?: Partial<Session>;
  onSuccess: (s: Session) => void;
}

export function Login({ initial, onSuccess }: Props) {
  const [baseUrl, setBaseUrl] = useState(initial?.baseUrl ?? "https://your-relay.up.railway.app");
  const [token, setToken] = useState(initial?.token ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const trimmed = baseUrl.replace(/\/+$/, "");
      const ok = await probeRelay(trimmed);
      if (!ok) {
        setError("Could not reach relay /healthz. Check the URL.");
        return;
      }
      // Validate token by hitting /v1/status
      const res = await fetch(`${trimmed}/v1/status`, {
        headers: { Authorization: `Bearer ${token.trim()}` },
      });
      if (res.status === 401) {
        setError("Token rejected by the relay.");
        return;
      }
      if (!res.ok) {
        setError(`Relay returned ${res.status}.`);
        return;
      }
      const session: Session = { baseUrl: trimmed, token: token.trim() };
      saveSession(session);
      onSuccess(session);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen grid place-items-center p-6">
      <form
        onSubmit={submit}
        className="card-elevated p-8 w-full max-w-md flex flex-col gap-5"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-accent/15 text-accent grid place-items-center font-semibold text-lg">
            A
          </div>
          <div>
            <div className="text-lg font-semibold leading-tight">Axon Remote</div>
            <div className="text-xs text-ink-400">Sign in with your relay credentials</div>
          </div>
        </div>

        <Field label="Relay URL">
          <input
            type="url"
            required
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://your-relay.up.railway.app"
            className="bg-ink-800 px-3 py-2 rounded-xl outline-none border border-white/[0.06] focus:border-accent/40 text-sm"
          />
        </Field>

        <Field label="Bearer token (USER_API_KEY)">
          <input
            type="password"
            required
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="64 hex characters"
            className="bg-ink-800 px-3 py-2 rounded-xl outline-none border border-white/[0.06] focus:border-accent/40 text-sm font-mono"
            autoComplete="off"
          />
        </Field>

        {error && (
          <div className="text-xs text-err bg-err/10 border border-err/20 px-3 py-2 rounded-xl">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={busy}
          className="mt-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-accent/15 text-accent hover:bg-accent/25 transition-colors disabled:opacity-60 text-sm font-medium"
        >
          {busy ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />}
          Sign in
        </button>

        <div className="flex items-center gap-2 text-[11px] text-ink-400">
          <ShieldCheck size={12} />
          Token stays in this browser&apos;s local storage. HTTPS only.
        </div>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[11px] text-ink-400 uppercase tracking-wider">{label}</span>
      {children}
    </label>
  );
}
