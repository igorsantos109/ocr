import type { DocumentStatus } from '../../types/ocr';
import { cx } from '../../lib/utils';

const MAP: Record<DocumentStatus, { label: string; cls: string }> = {
  draft: { label: 'Rascunho', cls: 'bg-surface text-muted border-border' },
  queued: { label: 'Na fila', cls: 'bg-surface text-muted border-border' },
  preprocessing: { label: 'Pré-processando', cls: 'bg-primary-soft text-warn border-primary' },
  ocr: { label: 'OCR', cls: 'bg-primary-soft text-warn border-primary' },
  layout_analysis: { label: 'Layout', cls: 'bg-primary-soft text-warn border-primary' },
  exporting: { label: 'Exportando', cls: 'bg-primary-soft text-warn border-primary' },
  completed: { label: 'Concluído', cls: 'bg-ok-soft text-ok border-ok' },
  needs_review: { label: 'Revisão pendente', cls: 'bg-warn-soft text-warn border-primary' },
  failed: { label: 'Falha', cls: 'bg-err-soft text-err border-err' },
  cancelled: { label: 'Cancelado', cls: 'bg-surface text-muted border-border' },
};

export function StatusBadge({ status, title }: { status: DocumentStatus; title?: string }) {
  const m = MAP[status];
  return (
    <span
      title={title ?? m.label}
      className={cx('inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-3 py-0.5 text-xs font-medium', m.cls)}
    >
      <span aria-hidden className="inline-block h-1.5 w-1.5 rounded-full bg-current" />
      {m.label}
    </span>
  );
}
