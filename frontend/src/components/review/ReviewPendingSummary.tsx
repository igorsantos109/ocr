/** Resumo das pendências: top crítico + links para a central. */

import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { formatConfidence } from '../../lib/utils';
import { useOcrStore } from '../../store/useOcrStore';

const KIND_LABEL: Record<string, string> = {
  low_confidence: 'Baixa confiança',
  possible_error: 'Possível erro',
  engine_conflict: 'Conflito entre motores',
  illegible: 'Ilegível',
  incomplete_table: 'Tabela incompleta',
};

const SEV_LABEL: Record<string, string> = { low: 'Baixa', medium: 'Média', high: 'Alta' };

export function ReviewPendingSummary() {
  const reviewQueue = useOcrStore((s) => s.reviewQueue);
  const top = [...reviewQueue].sort((a, b) => (a.confidence ?? -1) - (b.confidence ?? -1)).slice(0, 6);

  return (
    <section aria-label="Pendências de revisão" className="rounded-lg border border-border bg-white p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-[15px] font-medium">4 · Pendências de revisão ({reviewQueue.length})</h2>
        <Link to="/documentos/doc-img-4253" className="inline-flex items-center gap-1 rounded-lg border border-brand-blue px-3 py-1.5 text-[13px] text-brand-blue">
          Abrir central de revisão <ArrowRight size={14} aria-hidden />
        </Link>
      </div>
      {!top.length ? (
        <p className="mt-3 rounded-lg bg-ok-soft px-3 py-2 text-[13px] text-ok">Sem pendências de revisão. Bom trabalho.</p>
      ) : (
        <ul className="mt-3 space-y-1.5">
          {top.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-2 rounded-lg border border-border px-3 py-2 text-[13px]">
              <span className="rounded-full bg-err-soft px-2 py-0.5 text-xs font-medium text-err">{SEV_LABEL[r.severity]}</span>
              <span className="font-medium">{r.documentName}</span>
              <span className="text-muted">p. {r.page} · linha {r.line}</span>
              <span className="mono rounded bg-surface px-1.5 py-0.5 text-xs">“{r.text}”</span>
              <span className="text-muted">{KIND_LABEL[r.kind]} · {formatConfidence(r.confidence)}</span>
              <Link to={`/documentos/${r.documentId}`} className="ml-auto text-brand-blue underline">Abrir</Link>
            </li>
          ))}
        </ul>
      )}
      <Link to="/documentos/doc-img-4253" className="mt-3 inline-block text-[13px] text-brand-blue underline">
        Ver todas as pendências
      </Link>
    </section>
  );
}
