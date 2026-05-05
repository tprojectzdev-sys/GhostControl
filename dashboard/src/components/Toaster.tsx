import { useEffect, useState } from "react";
import { CheckCircle2, AlertTriangle, X } from "lucide-react";

export interface Toast {
  id: number;
  level: "ok" | "warn" | "err";
  message: string;
}

interface Props {
  toasts: Toast[];
  onDismiss: (id: number) => void;
}

export function Toaster({ toasts, onDismiss }: Props) {
  return (
    <div className="fixed bottom-6 right-6 flex flex-col gap-2 z-50 pointer-events-none">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: number) => void }) {
  const [show, setShow] = useState(false);
  useEffect(() => {
    setShow(true);
    const t = setTimeout(() => onDismiss(toast.id), 4500);
    return () => clearTimeout(t);
  }, [toast.id, onDismiss]);

  const Icon = toast.level === "ok" ? CheckCircle2 : AlertTriangle;
  const tone =
    toast.level === "ok"
      ? "border-ok/30 bg-ok/10 text-ok"
      : toast.level === "warn"
      ? "border-warn/30 bg-warn/10 text-warn"
      : "border-err/30 bg-err/10 text-err";

  return (
    <div
      className={
        "pointer-events-auto card px-4 py-3 flex items-start gap-3 max-w-sm border " +
        tone +
        " transition-all duration-300 " +
        (show ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2")
      }
    >
      <Icon size={16} className="mt-0.5 shrink-0" />
      <div className="flex-1 text-sm text-ink-100 break-words">{toast.message}</div>
      <button
        type="button"
        onClick={() => onDismiss(toast.id)}
        className="text-ink-300 hover:text-ink-100 transition-colors"
        aria-label="Dismiss"
      >
        <X size={14} />
      </button>
    </div>
  );
}
