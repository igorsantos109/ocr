/** Central de revisão: dois painéis redimensionáveis (desktop) ou abas (mobile).
 *  Atalhos respeitam inputs de texto (exceto Ctrl+S). */

import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../services';
import { ENGINE_LABELS } from '../data/mockDocuments';
import { useOcrStore } from '../store/useOcrStore';
import type { OcrPage, OcrWord, RevisionEvent } from '../types/ocr';
import { ImageViewer } from '../components/review/ImageViewer';
import { OcrTextPanel } from '../components/review/OcrTextPanel';

export function DocumentReviewPage() {
  const { documentId = '' } = useParams();
  const documents = useOcrStore((s) => s.documents);
  const reviewQueue = useOcrStore((s) => s.reviewQueue);
  const history = useOcrStore((s) => s.history);
  const applyWordAction = useOcrStore((s) => s.applyWordAction);
  const toast = useOcrStore((s) => s.toast);
  const [pages, setPages] = useState<OcrPage[]>([]);
  const [activePageId, setActivePageId] = useState('');
  const [selectedWordId, setSelectedWordId] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [mobileTab, setMobileTab] = useState<'original' | 'texto' | 'pendencias' | 'meta'>('texto');
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  const doc = documents.find((d) => d.id === documentId);
  const pendencias = reviewQueue.filter((r) => r.documentId === documentId);

  useEffect(() => {
    void api.getPages(documentId).then((p) => {
      setPages(p);
      if (p.length && !activePageId) setActivePageId(p[0].id);
    });
    void api.history(documentId).then((h) => useOcrStore.setState({ history: h })).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId]);

  const mutateWord = useCallback(
    (wordId: string, fn: (w: { text: string; status: OcrWord['status'] }) => { text: string; status: OcrWord['status'] }) => {
      setPages((prev) =>
        prev.map((p) => ({
          ...p,
          lines: p.lines.map((l) => ({
            ...l,
            words: l.words.map((w) =>
              w.id === wordId ? { ...w, ...fn({ text: w.text, status: w.status }) } : w,
            ),
          })),
        })),
      );
      setDirty(true);
      setTimeout(() => setDirty(false), 2500);
    },
    [],
  );

  async function onAction(wordId: string, action: RevisionEvent['action'], value?: string) {
    await applyWordAction(wordId, action, value);
    const status =
      action === 'accepted' ? 'accepted'
      : action === 'edited' ? 'edited'
      : action === 'illegible' ? 'illegible'
      : action === 'training' ? 'training'
      : action === 'proper_noun' ? 'proper_noun'
      : action === 'abbreviation' ? 'abbreviation'
      : 'ignored';
    mutateWord(wordId, (w) => ({ text: value ?? w.text, status }));
  }

  function nextPending(dir: 1 | -1) {
    if (!pendencias.length) return;
    const ids = pendencias.map((p) => p.lineId);
    const idx = ids.indexOf(pages.flatMap((p) => p.lines).find((l) => l.words.some((w) => w.id === selectedWordId))?.id ?? '');
    const next = pendencias[(idx + dir + pendencias.length) % pendencias.length];
    setActivePageId(next.pageId);
    const target = pages.flatMap((p) => p.lines).find((l) => l.id === next.lineId)?.words[0];
    if (target) setSelectedWordId(target.id);
    toast(`Trecho: ${next.text}`, 'info');
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const inInput = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target as HTMLElement)?.tagName ?? '');
      if (e.key === '?' && !inInput) {
        setShortcutsOpen((v) => !v);
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        setDirty(false);
        toast('Revisão salva', 'success');
        return;
      }
      if (inInput) return;
      if (e.altKey && e.key === 'ArrowRight') {
        e.preventDefault();
        nextPending(1);
      } else if (e.altKey && e.key === 'ArrowLeft') {
        e.preventDefault();
        nextPending(-1);
      } else if (e.key === 'Enter' && selectedWordId) {
        e.preventDefault();
        void onAction(selectedWordId, 'accepted');
      } else if (e.key === '1' && selectedWordId) {
        void onAction(selectedWordId, 'accepted');
      } else if (e.key === '2' && selectedWordId) {
        void onAction(selectedWordId, 'illegible');
      } else if (e.key === '3' && selectedWordId) {
        void onAction(selectedWordId, 'training');
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedWordId, pendencias, pages]);

  return (
    <div className="pt-4">
      <nav aria-label="Trilha" className="text-[13px] text-muted">
        <Link to="/" className="underline">Converter</Link> / <span>{doc?.name ?? documentId}</span>
      </nav>
      <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-[16px] font-medium">{doc?.name ?? 'Documento'}</h1>
        <button type="button" onClick={() => setShortcutsOpen((v) => !v)} aria-expanded={shortcutsOpen} className="rounded-lg border border-border px-3 py-1.5 text-[13px]" aria-label="Abrir ajuda de atalhos (?)">
          Atalhos (?)
        </button>
      </div>
      {shortcutsOpen ? (
        <ul className="mono mt-2 grid gap-1 rounded-lg border border-border bg-surface p-3 text-xs md:grid-cols-2" aria-label="Lista de atalhos">
          <li><b>Enter</b> aceitar leitura · <b>Ctrl+Enter</b> salvar e avançar</li>
          <li><b>Alt+→ / Alt+←</b> próximo / anterior pendente</li>
          <li><b>1</b> revisado · <b>2</b> ilegível · <b>3</b> treinamento</li>
          <li><b>Ctrl+S</b> salvar · <b>?</b> este painel</li>
        </ul>
      ) : null}

      <div className="mt-2 flex gap-1 md:hidden" role="tablist" aria-label="Painéis">
        {(['original', 'texto', 'pendencias', 'meta'] as const).map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={mobileTab === t}
            onClick={() => setMobileTab(t)}
            className={mobileTab === t ? 'rounded-lg bg-primary px-3 py-1.5 text-[13px] font-medium' : 'rounded-lg border border-border px-3 py-1.5 text-[13px]'}
          >
            {t === 'original' ? 'Original' : t === 'texto' ? 'Texto' : t === 'pendencias' ? `Pendências (${pendencias.length})` : 'Metadados'}
          </button>
        ))}
      </div>

      <div className="mt-3 hidden gap-0 overflow-hidden rounded-lg border border-border md:flex" style={{ height: '68vh' }}>
        <div className="flex w-1/2 min-w-0 flex-col border-r border-border">
          <ImageViewer pages={pages} activePageId={activePageId} onPage={setActivePageId} selectedWordId={selectedWordId} onSelectWord={setSelectedWordId} />
        </div>
        <div className="flex w-1/2 min-w-0 flex-col">
          <OcrTextPanel pages={pages} activePageId={activePageId} selectedWordId={selectedWordId} onSelectWord={setSelectedWordId} onAction={(w, a, v) => void onAction(w, a, v)} dirty={dirty} />
        </div>
      </div>

      <div className="mt-3 overflow-hidden rounded-lg border border-border md:hidden" style={{ height: '62vh' }}>
        {mobileTab === 'original' ? (
          <ImageViewer pages={pages} activePageId={activePageId} onPage={setActivePageId} selectedWordId={selectedWordId} onSelectWord={setSelectedWordId} />
        ) : mobileTab === 'texto' ? (
          <OcrTextPanel pages={pages} activePageId={activePageId} selectedWordId={selectedWordId} onSelectWord={setSelectedWordId} onAction={(w, a, v) => void onAction(w, a, v)} dirty={dirty} />
        ) : mobileTab === 'pendencias' ? (
          <PendingList pendencias={pendencias} />
        ) : (
          <div className="p-4 text-[13px] text-muted">
            <p><strong className="text-ink">Perfil:</strong> {doc?.profileId}</p>
            <p><strong className="text-ink">Motor:</strong> {doc ? (ENGINE_LABELS[doc.engine] ?? doc.engine) : '—'}</p>
            <p><strong className="text-ink">Páginas:</strong> {doc?.pages}</p>
            <HistoryList history={history} />
          </div>
        )}
      </div>

      <div className="mt-3 hidden gap-4 md:grid md:grid-cols-2">
        <PendingList pendencias={pendencias} />
        <div className="rounded-lg border border-border p-4">
          <h2 className="text-[15px] font-medium">Histórico auditado</h2>
          <HistoryList history={history} />
        </div>
      </div>
    </div>
  );
}

function PendingList({ pendencias }: { pendencias: ReturnType<typeof useOcrStore.getState>['reviewQueue'] }) {
  const [sort, setSort] = useState<'confidence' | 'recent'>('confidence');
  const items = [...pendencias].sort((a, b) =>
    sort === 'confidence' ? (a.confidence ?? -1) - (b.confidence ?? -1) : b.id.localeCompare(a.id),
  );
  if (!items.length) return <p className="rounded-lg bg-ok-soft p-4 text-[13px] text-ok">Sem pendências de revisão.</p>;
  return (
    <div className="rounded-lg border border-border p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-[15px] font-medium">Pendências ({items.length})</h2>
        <label className="text-[13px] text-muted">Ordenar
          <select value={sort} onChange={(e) => setSort(e.target.value as 'confidence' | 'recent')} className="ml-1 rounded border border-border px-1.5 py-1" aria-label="Ordenar pendências">
            <option value="confidence">Menor confiança</option>
            <option value="recent">Mais recente</option>
          </select>
        </label>
      </div>
      <ul className="mt-2 max-h-56 space-y-1.5 overflow-y-auto">
        {items.map((r) => (
          <li key={r.id} className="flex items-center gap-2 rounded border border-border px-2.5 py-1.5 text-[13px]">
            <span className="mono rounded bg-surface px-1.5 py-0.5 text-xs">“{r.text}”</span>
            <span className="text-muted">p. {r.page} · linha {r.line} · {r.confidence == null ? 'sem conf.' : `${Math.round(r.confidence * 100)}%`}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function HistoryList({ history }: { history: RevisionEvent[] }) {
  if (!history.length) return <p className="mt-2 text-[13px] text-muted">Nenhuma correção registrada ainda.</p>;
  return (
    <ul className="mt-2 max-h-56 space-y-1.5 overflow-y-auto text-[13px]">
      {history.map((h) => (
        <li key={h.id} className="rounded border border-border px-2.5 py-1.5">
          <strong>{h.action}</strong> por {h.actor} · {new Date(h.createdAt).toLocaleString('pt-BR')}
          <br />
          <span className="mono text-xs">{h.previousValue ?? '—'} → {h.nextValue ?? '—'}</span>
        </li>
      ))}
    </ul>
  );
}
