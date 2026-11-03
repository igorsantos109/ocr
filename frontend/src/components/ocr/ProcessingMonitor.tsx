/** Monitor de processamento: resumo técnico + revisão humana, progresso, logs. */

import * as Collapsible from '@radix-ui/react-collapsible';
import * as Progress from '@radix-ui/react-progress';
import { ChevronDown, Pause, Play, Trash2, X } from 'lucide-react';
import { useState } from 'react';
import { formatConfidence } from '../../lib/utils';
import { api } from '../../services';
import { useOcrStore } from '../../store/useOcrStore';

export function ProcessingMonitor() {
  const processing = useOcrStore((s) => s.processing);
  const refresh = useOcrStore((s) => s.refresh);
  const toast = useOcrStore((s) => s.toast);
  const [logQuery, setLogQuery] = useState('');
  const running = processing.state === 'running';

  async function act(fn: () => Promise<void>, msg: string) {
    await fn();
    await refresh();
    toast(msg, 'info');
  }

  const logs = processing.log.filter((l) => l.toLowerCase().includes(logQuery.toLowerCase()));

  return (
    <section aria-label="Acompanhamento de processamento" aria-live="polite" className="rounded-lg border border-border bg-white p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[15px] font-medium">3 · Acompanhamento</h2>
        <div className="flex gap-1.5">
          {running ? (
            <button type="button" onClick={() => void act(() => api.pauseProcessing(), 'Processamento pausado')} className="rounded-lg border border-border px-3 py-1.5 text-[13px]" aria-label="Pausar processamento">
              <Pause size={14} aria-hidden className="mr-1 inline" />Pausar
            </button>
          ) : (
            <button type="button" onClick={() => void act(() => api.resumeProcessing(), 'Processamento retomado')} className="rounded-lg border border-border px-3 py-1.5 text-[13px]" aria-label="Retomar processamento">
              <Play size={14} aria-hidden className="mr-1 inline" />Retomar
            </button>
          )}
          <button type="button" onClick={() => void act(() => api.cancelProcessing(), 'Processamento cancelado')} className="rounded-lg border border-border px-3 py-1.5 text-[13px]" aria-label="Cancelar processamento">
            <X size={14} aria-hidden className="mr-1 inline" />Cancelar
          </button>
          <button type="button" onClick={() => void act(() => api.startProcessing(), 'Fila enviada para processamento')} className="rounded-lg bg-primary px-3 py-1.5 text-[13px] font-medium text-[#202124] hover:bg-primary-hover">
            Processar fila
          </button>
          <button type="button" onClick={() => toast('Concluídos removidos da vista', 'info')} className="rounded-lg border border-border px-3 py-1.5 text-[13px]" aria-label="Limpar concluídos">
            <Trash2 size={14} aria-hidden className="mr-1 inline" />Limpar
          </button>
        </div>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div className="rounded-lg bg-surface p-3 text-[13px]">
          <p className="font-medium">OCR técnico: {processing.documentsDone} de {processing.documentsTotal} documentos</p>
          <p className="text-muted">{processing.message || 'Nenhum processamento em andamento'}</p>
          <Progress.Root value={processing.percent} aria-label="Progresso geral" className="mt-2 h-2 overflow-hidden rounded bg-border">
            <Progress.Indicator className="h-full bg-primary transition-all" style={{ width: `${processing.percent}%` }} />
          </Progress.Root>
        </div>
        <div className="rounded-lg bg-warn-soft p-3 text-[13px]">
          <p className="font-medium">Revisão humana: {processing.reviewPending} trechos pendentes</p>
          <p className="text-muted">Erros: {processing.pagesError} · Tempo médio: {processing.avgSecondsPerPage.toFixed(1)} s por página</p>
          <p className="mt-1 text-xs">Confiança média da fila: {formatConfidence(null)}</p>
        </div>
      </div>

      <Collapsible.Root className="mt-3 rounded-lg border border-border">
        <Collapsible.Trigger className="flex w-full items-center justify-between px-4 py-2 text-[13px] font-medium">
          Logs ({logs.length})
          <ChevronDown size={15} aria-hidden />
        </Collapsible.Trigger>
        <Collapsible.Content className="border-t border-border p-3">
          <input
            type="search"
            value={logQuery}
            onChange={(e) => setLogQuery(e.target.value)}
            placeholder="Filtrar logs…"
            aria-label="Filtrar logs"
            className="mb-2 w-full rounded-md border border-border bg-surface px-2.5 py-1.5 text-[13px]"
          />
          <ul className="mono max-h-40 space-y-1 overflow-y-auto text-xs">
            {logs.map((l, i) => (
              <li key={i} className={l.startsWith('[warning]') || l.startsWith('[error]') ? 'text-err' : 'text-muted'}>{l}</li>
            ))}
            {!logs.length ? <li className="text-muted">Sem registros para o filtro.</li> : null}
          </ul>
          <p className="mt-2 text-xs text-muted">Sistema (mock): CPU 34% · RAM 5,1/16 GB · GPU — · Disco 61%</p>
        </Collapsible.Content>
      </Collapsible.Root>
    </section>
  );
}
