import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';
import { useOcrStore } from '../../store/useOcrStore';

/** Toasts no canto inferior esquerdo (aria-live). */
export function Toasts() {
  const toasts = useOcrStore((s) => s.toasts);
  const dismiss = useOcrStore((s) => s.dismissToast);
  return (
    <div className="fixed bottom-5 left-5 z-50 flex flex-col gap-2" aria-live="polite">
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          className="flex max-w-sm items-center gap-2 rounded-lg border-l-4 border-primary bg-[#202124] px-4 py-3 text-[13px] text-white shadow-lg"
        >
          {t.kind === 'success' ? <CheckCircle2 size={16} aria-hidden /> : t.kind === 'error' ? <AlertCircle size={16} aria-hidden /> : <Info size={16} aria-hidden />}
          <span className="flex-1">{t.message}</span>
          <button
            type="button"
            onClick={() => dismiss(t.id)}
            aria-label="Fechar notificação"
            className="rounded p-1 hover:bg-white/10"
          >
            <X size={14} aria-hidden />
          </button>
        </div>
      ))}
    </div>
  );
}
