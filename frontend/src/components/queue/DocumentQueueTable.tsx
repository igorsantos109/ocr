/** Tabela da fila com seleção, filtros, ordenação, ações por linha e em lote. */

import * as Checkbox from '@radix-ui/react-checkbox';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import * as Progress from '@radix-ui/react-progress';
import { ArrowUpDown, Check, FileImage, FileText, MoreVertical } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ENGINE_LABELS } from '../../data/mockDocuments';
import { cx, formatConfidence, formatDateTime } from '../../lib/utils';
import { api } from '../../services';
import { useOcrStore } from '../../store/useOcrStore';
import type { QueueDocument } from '../../types/ocr';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { EmptyState } from '../common/EmptyState';
import { StatusBadge } from '../common/StatusBadge';

type SortKey = 'updatedAt' | 'name' | 'confidence';

export function DocumentQueueTable({ collectionId }: { collectionId?: string }) {
  const documents = useOcrStore((s) => s.documents);
  const query = useOcrStore((s) => s.query);
  const statusFilter = useOcrStore((s) => s.statusFilter);
  const selectedIds = useOcrStore((s) => s.selectedIds);
  const toggleSelect = useOcrStore((s) => s.toggleSelect);
  const clearSelection = useOcrStore((s) => s.clearSelection);
  const refresh = useOcrStore((s) => s.refresh);
  const toast = useOcrStore((s) => s.toast);
  const navigate = useNavigate();
  const [sortKey, setSortKey] = useState<SortKey>('updatedAt');
  const [sortDir, setSortDir] = useState<1 | -1>(-1);
  const [typeFilter, setTypeFilter] = useState('');
  const [confirmDelete, setConfirmDelete] = useState<QueueDocument | null>(null);

  const rows = useMemo(() => {
    let out = collectionId ? documents.filter((d) => d.collectionId === collectionId) : documents;
    if (query) {
      const q = query.toLowerCase();
      out = out.filter((d) => d.name.toLowerCase().includes(q));
    }
    if (statusFilter) out = out.filter((d) => d.status === statusFilter);
    if (typeFilter) out = out.filter((d) => d.type === typeFilter);
    const sorted = [...out].sort((a, b) => {
      if (sortKey === 'name') return a.name.localeCompare(b.name) * sortDir;
      if (sortKey === 'confidence') return ((a.confidence ?? -1) - (b.confidence ?? -1)) * sortDir;
      return (a.updatedAt < b.updatedAt ? -1 : 1) * sortDir;
    });
    return sorted;
  }, [documents, collectionId, query, statusFilter, typeFilter, sortKey, sortDir]);

  function cycleSort(k: SortKey) {
    if (sortKey === k) setSortDir((d) => (d === 1 ? -1 : 1));
    else {
      setSortKey(k);
      setSortDir(-1);
    }
  }
  const sortBtn = (label: string, k: SortKey) => (
    <button type="button" onClick={() => cycleSort(k)} className="inline-flex items-center gap-1 font-medium hover:underline" aria-label={`Ordenar por ${label}`}>
      {label} <ArrowUpDown size={12} aria-hidden />
    </button>
  );

  async function batch(fn: (d: QueueDocument) => Promise<void>, msg: string) {
    for (const d of documents.filter((x) => selectedIds.includes(x.id))) {
      await fn(d).catch(() => undefined);
    }
    clearSelection();
    await refresh();
    toast(msg, 'success');
  }

  if (!rows.length) {
    return (
      <EmptyState
        title="Fila sem documentos"
        hint="Envie arquivos acima ou ajuste busca e filtros."
        action={<button type="button" onClick={() => { useOcrStore.setState({ query: '', statusFilter: '' }); setTypeFilter(''); }} className="rounded-lg border border-border px-3 py-1.5 text-[13px]">Limpar filtros</button>}
      />
    );
  }

  return (
    <section aria-label="Fila de documentos">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-[13px]">
        <label>Tipo
          <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="ml-1 rounded-md border border-border bg-surface px-2 py-1" aria-label="Filtrar por tipo">
            <option value="">Todos</option>
            <option value="pdf">PDF</option>
            <option value="image">Imagem</option>
          </select>
        </label>
        {selectedIds.length ? (
          <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-primary bg-primary-soft px-2.5 py-1.5" role="toolbar" aria-label="Ações em lote">
            <strong>{selectedIds.length} selecionado(s)</strong>
            <button type="button" onClick={() => void batch(() => api.startProcessing(selectedIds), 'Lote enviado')} className="rounded border border-border bg-white px-2 py-0.5">Processar</button>
            <button type="button" onClick={() => void batch((d) => api.retryDocument(d.id), 'Lote reprocessado')} className="rounded border border-border bg-white px-2 py-0.5">Reprocessar</button>
            <button type="button" onClick={() => void batch((d) => api.removeDocument(d.id), 'Lote excluído')} className="rounded border border-border bg-white px-2 py-0.5">Excluir</button>
            <button type="button" onClick={clearSelection} className="rounded px-2 py-0.5 underline">Limpar</button>
          </div>
        ) : null}
      </div>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[880px] text-left text-[13px]">
          <thead className="bg-surface text-muted">
            <tr>
              <th className="w-9 px-3 py-2"><span className="sr-only">Selecionar</span></th>
              <th className="px-2 py-2">Tipo</th>
              <th className="px-2 py-2">{sortBtn('Nome', 'name')}</th>
              <th className="px-2 py-2">Páginas</th>
              <th className="px-2 py-2">Perfil</th>
              <th className="px-2 py-2">Motor</th>
              <th className="px-2 py-2">{sortBtn('Atualizado', 'updatedAt')}</th>
              <th className="px-2 py-2">Status</th>
              <th className="px-2 py-2">{sortBtn('Conf.', 'confidence')}</th>
              <th className="px-2 py-2">Progresso</th>
              <th className="px-2 py-2"><span className="sr-only">Ações</span></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((d) => (
              <tr key={d.id} className="border-t border-border hover:bg-surface">
                <td className="px-3 py-2">
                  <Checkbox.Root
                    checked={selectedIds.includes(d.id)}
                    onCheckedChange={() => toggleSelect(d.id)}
                    aria-label={`Selecionar ${d.name}`}
                    className="flex h-4.5 w-4.5 items-center justify-center rounded border border-muted bg-white data-[state=checked]:border-primary data-[state=checked]:bg-primary"
                  >
                    <Checkbox.Indicator><Check size={12} aria-hidden /></Checkbox.Indicator>
                  </Checkbox.Root>
                </td>
                <td className="px-2 py-2" title={d.type === 'pdf' ? 'PDF' : 'Imagem'}>
                  {d.type === 'pdf' ? <FileText size={16} aria-hidden className="text-muted" /> : <FileImage size={16} aria-hidden className="text-muted" />}
                </td>
                <td className="max-w-56 truncate px-2 py-2 font-medium">{d.name}</td>
                <td className="px-2 py-2">{d.pages}</td>
                <td className="px-2 py-2 text-muted">{d.profileId}</td>
                <td className="px-2 py-2 text-muted">{ENGINE_LABELS[d.engine] ?? d.engine}</td>
                <td className="whitespace-nowrap px-2 py-2 text-muted">{formatDateTime(d.updatedAt)}</td>
                <td className="px-2 py-2"><StatusBadge status={d.status} title={d.error} /></td>
                <td className="px-2 py-2">{formatConfidence(d.confidence)}</td>
                <td className="min-w-24 px-2 py-2">
                  <Progress.Root value={d.progress} aria-label={`Progresso de ${d.name}`} className="h-1.5 overflow-hidden rounded bg-border">
                    <Progress.Indicator className="h-full bg-primary" style={{ width: `${d.progress}%` }} />
                  </Progress.Root>
                </td>
                <td className="px-2 py-2">
                  <DropdownMenu.Root>
                    <DropdownMenu.Trigger asChild>
                      <button type="button" aria-label={`Ações de ${d.name}`} className="rounded p-1.5 hover:bg-surface-hover">
                        <MoreVertical size={15} aria-hidden />
                      </button>
                    </DropdownMenu.Trigger>
                    <DropdownMenu.Portal>
                      <DropdownMenu.Content align="end" className="z-50 min-w-52 rounded-lg border border-border bg-white p-1.5 text-[13px] shadow-lg">
                        <MenuItem label="Abrir/revisar" onClick={() => navigate(`/documentos/${d.id}`)} />
                        <MenuItem label="Baixar resultado" onClick={() => void api.exportDocument(d.id).then(() => toast('Exportação pronta (mock)', 'success'))} />
                        <MenuItem label="Reprocessar" onClick={() => void api.retryDocument(d.id).then(() => { void refresh(); toast('Reprocessamento iniciado', 'info'); })} />
                        <MenuItem label="Duplicar com outro perfil" onClick={() => void api.duplicateWithProfile(d.id, 'impresso-moderno').then(() => { void refresh(); toast('Cópia criada', 'success'); })} />
                        <MenuItem label="Ver log" onClick={() => toast(d.log[d.log.length - 1]?.message ?? 'Sem log', 'info')} />
                        <MenuItem label="Excluir" danger onClick={() => setConfirmDelete(d)} />
                      </DropdownMenu.Content>
                    </DropdownMenu.Portal>
                  </DropdownMenu.Root>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ConfirmDialog
        open={confirmDelete !== null}
        onOpenChange={(v) => {
          if (!v) setConfirmDelete(null);
        }}
        title="Excluir documento"
        description={`Remover "${confirmDelete?.name}" da fila? Arquivos locais e revisões associadas também serão excluídos.`}
        confirmLabel="Excluir"
        onConfirm={() => {
          if (confirmDelete) void api.removeDocument(confirmDelete.id).then(() => { void refresh(); toast('Documento excluído', 'info'); });
          setConfirmDelete(null);
        }}
      />
    </section>
  );
}

function MenuItem({ label, onClick, danger }: { label: string; onClick: () => void; danger?: boolean }) {
  return (
    <DropdownMenu.Item
      onSelect={onClick}
      className={cx('cursor-pointer rounded px-2.5 py-1.5 outline-none hover:bg-surface', danger && 'text-err')}
    >
      {label}
    </DropdownMenu.Item>
  );
}
