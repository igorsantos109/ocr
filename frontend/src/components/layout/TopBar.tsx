/** Barra superior global de 64px: marca, navegação, busca, modelo, fila, avatar. */

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import * as Tooltip from '@radix-ui/react-tooltip';
import { Menu, ScanText, Search, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { cx } from '../../lib/utils';
import { api } from '../../services';
import { useOcrStore } from '../../store/useOcrStore';

const NAV = [
  { to: '/', label: 'Converter', end: true },
  { to: '/colecoes', label: 'Coleções' },
  { to: '/documentos', label: 'Meus documentos' },
];

export function TopBar() {
  const query = useOcrStore((s) => s.query);
  const setQuery = useOcrStore((s) => s.setQuery);
  const statusFilter = useOcrStore((s) => s.statusFilter);
  const setStatusFilter = useOcrStore((s) => s.setStatusFilter);
  const processing = useOcrStore((s) => s.processing);
  const reviewQueue = useOcrStore((s) => s.reviewQueue);
  const documents = useOcrStore((s) => s.documents);
  const [llm, setLlm] = useState<{ enabled: boolean; model: string } | null>(null);
  const [drawer, setDrawer] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    void api.llmState().then(setLlm).catch(() => setLlm(null));
  }, []);

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-white">
      <div className="mx-auto flex h-16 max-w-[1200px] items-center gap-4 px-6">
        <button
          type="button"
          className="rounded p-2 hover:bg-surface md:hidden"
          aria-label="Abrir navegação"
          onClick={() => setDrawer(true)}
        >
          <Menu size={18} aria-hidden />
        </button>
        <button type="button" onClick={() => navigate('/')} className="flex items-center gap-2.5" aria-label="OCR Studio V2 — início">
          <span className="inline-flex h-[34px] w-[34px] items-center justify-center rounded-lg bg-primary font-bold text-[#202124]" aria-hidden>
            <ScanText size={18} />
          </span>
          <span className="whitespace-nowrap text-left text-[18px] font-medium leading-tight">
            OCR Studio V2
            <small className="block text-[11px] font-normal tracking-wide text-muted">ocr-historico-br · revisão local</small>
          </span>
        </button>
        <nav className="hidden flex-1 items-stretch gap-1 self-stretch md:flex" aria-label="Navegação principal">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                cx(
                  'flex items-center border-b-[3px] border-transparent px-3.5 text-[14px] font-medium text-muted hover:text-ink',
                  isActive && 'border-primary text-ink',
                )
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="relative hidden lg:block">
          <Search size={14} aria-hidden className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar nome, coleção, conteúdo…"
            aria-label="Busca global"
            className="w-52 rounded-md border border-border bg-surface py-1.5 pl-8 pr-7 text-[13px]"
          />
          {query ? (
            <button type="button" aria-label="Limpar busca" onClick={() => setQuery('')} className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-muted hover:bg-surface-hover">
              <X size={13} aria-hidden />
            </button>
          ) : null}
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Filtrar por status"
          className="hidden max-w-44 rounded-md border border-border bg-surface px-2 py-1.5 text-[13px] xl:block"
        >
          <option value="">Todos os status</option>
          <option value="completed">Concluído</option>
          <option value="needs_review">Revisão pendente</option>
          <option value="ocr">Em OCR</option>
          <option value="failed">Falha</option>
        </select>
        <Tooltip.Provider>
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <span className={cx('whitespace-nowrap rounded-full border px-3 py-1 text-xs font-medium', llm?.enabled ? 'border-ok bg-ok-soft text-ok' : 'border-border bg-surface text-muted')}>
                {llm ? (llm.enabled ? `LLM · ${llm.model}` : 'LLM desativado') : 'LLM…'}
              </span>
            </Tooltip.Trigger>
            <Tooltip.Content side="bottom" className="z-50 rounded border border-border bg-white px-2 py-1 text-xs shadow">
              Modelo de revisão local (sugestões apenas)
            </Tooltip.Content>
          </Tooltip.Root>
        </Tooltip.Provider>
        <span className="hidden whitespace-nowrap rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted md:inline" title="Documentos e pendências">
          {documents.length} docs · {reviewQueue.length} na fila
        </span>
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button type="button" aria-label="Menu do usuário" title="Conta local" className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-brand-blue text-[13px] text-white">
              OC
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content align="end" className="z-50 min-w-48 rounded-lg border border-border bg-white p-1.5 text-[13px] shadow-lg">
              <DropdownMenu.Item className="rounded px-2.5 py-1.5 outline-none hover:bg-surface" onSelect={() => navigate('/configuracoes')}>
                Preferências
              </DropdownMenu.Item>
              <DropdownMenu.Item className="rounded px-2.5 py-1.5 outline-none hover:bg-surface" onSelect={() => navigate('/configuracoes')}>
                Tema
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
      {drawer ? (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Navegação">
          <div className="absolute inset-0 bg-black/40" onClick={() => setDrawer(false)} />
          <nav className="absolute left-0 top-0 flex h-full w-64 flex-col gap-1 bg-white p-4 shadow-xl" aria-label="Menu lateral">
            <div className="mb-2 flex items-center justify-between">
              <strong>OCR Studio V2</strong>
              <button type="button" aria-label="Fechar menu" onClick={() => setDrawer(false)} className="rounded p-1.5 hover:bg-surface">
                <X size={16} aria-hidden />
              </button>
            </div>
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                onClick={() => setDrawer(false)}
                className={({ isActive }) => cx('rounded-lg px-3 py-2 text-[14px]', isActive ? 'bg-primary-soft font-medium' : 'text-muted')}
              >
                {n.label}
              </NavLink>
            ))}
            <NavLink to="/configuracoes" onClick={() => setDrawer(false)} className="rounded-lg px-3 py-2 text-[14px] text-muted">
              Configurações
            </NavLink>
          </nav>
        </div>
      ) : null}
      <div className="border-t border-border bg-surface" aria-hidden={processing.state === 'idle'}>
        <div className={cx('h-1 bg-primary transition-all', processing.state === 'idle' && 'w-0')} style={{ width: `${processing.percent}%` }} />
      </div>
    </header>
  );
}
