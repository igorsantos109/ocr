/** Painel de configuração OCR: perfis, idiomas, motores, formatos e avançadas. */

import * as Collapsible from '@radix-ui/react-collapsible';
import * as Tooltip from '@radix-ui/react-tooltip';
import {
  Bandage,
  BookOpen,
  Check,
  ChevronDown,
  Newspaper,
  PenLine,
  SlidersHorizontal,
  Table,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { cx } from '../../lib/utils';
import { ENGINE_DESCRIPTIONS, ENGINE_ENDPOINTS, ENGINE_GROUPS, ENGINE_LABELS } from '../../data/mockDocuments';
import { api } from '../../services';
import { useOcrStore } from '../../store/useOcrStore';
import type { ExportFormatId, OcrEngineId } from '../../types/ocr';import { z } from 'zod';

const ICONS: Record<string, typeof BookOpen> = {
  'book-open': BookOpen,
  newspaper: Newspaper,
  'pen-line': PenLine,
  table: Table,
  bandage: Bandage,
  'sliders-horizontal': SlidersHorizontal,
};

const LANGS = [
  { id: 'auto', label: 'Automático' },
  { id: 'pt-contemporaneo', label: 'Português contemporâneo' },
  { id: 'pt-historico', label: 'Português histórico' },
  { id: 'en', label: 'Inglês' },
  { id: 'es', label: 'Espanhol' },
  { id: 'fr', label: 'Francês' },
  { id: 'de', label: 'Alemão' },
  { id: 'la', label: 'Latim' },
];

const FORMATS: Array<{ id: ExportFormatId; label: string; hint: string }> = [
  { id: 'docx', label: 'DOCX', hint: 'Texto editável com layout' },
  { id: 'pdf', label: 'PDF pesquisável', hint: 'Imagem + camada de texto' },
  { id: 'txt', label: 'TXT', hint: 'Texto puro' },
  { id: 'tsv', label: 'TSV', hint: 'Coordenadas e confiança' },
  { id: 'xlsx', label: 'XLSX', hint: 'Tabelas estruturadas' },
  { id: 'markdown', label: 'Markdown', hint: 'Leitura e publicação' },
  { id: 'json', label: 'JSON', hint: 'Auditoria e metadados' },
  { id: 'alto', label: 'ALTO XML', hint: 'Interoperabilidade' },
];

const ADVANCED: Array<{ id: string; label: string; hint: string }> = [
  { id: 'deskew', label: 'Corrigir inclinação (deskew)', hint: 'Endireita páginas escaneadas tortas' },
  { id: 'denoise', label: 'Remover ruído', hint: 'Suaviza manchas e granulação' },
  { id: 'binarization', label: 'Binarização adaptativa', hint: 'Converte para P&B com limiar local' },
  { id: 'clahe', label: 'Melhorar contraste / CLAHE', hint: 'Realça texto apagado' },
  { id: 'detectOrientation', label: 'Detectar orientação', hint: 'Gira páginas de ponta-cabeça' },
  { id: 'preserveLayout', label: 'Preservar layout e colunas', hint: 'Mantém ordem de leitura' },
  { id: 'detectTables', label: 'Detectar tabelas', hint: 'Extrai células para XLSX/TSV' },
  { id: 'twoPass', label: 'OCR em duas passagens', hint: 'Segunda passada nos trechos fracos' },
  { id: 'useHistoricalDictionary', label: 'Usar dicionário histórico', hint: 'Sugestões sem modernizar grafia' },
  { id: 'forceEngine', label: 'Forçar motor selecionado', hint: 'Desativa fallback automático' },
  { id: 'reviewLowConfidence', label: 'Enviar baixa confiança p/ revisão', hint: 'Fila humana para trechos fracos' },
];

const profileSchema = z.object({
  name: z.string().min(2, 'Nome com ao menos 2 caracteres'),
});

export function OcrConfigurationPanel() {
  const profiles = useOcrStore((s) => s.profiles);
  const activeProfileId = useOcrStore((s) => s.activeProfileId);
  const activeEngine = useOcrStore((s) => s.activeEngine);
  const activeLanguages = useOcrStore((s) => s.activeLanguages);
  const activeFormats = useOcrStore((s) => s.activeFormats);
  const advancedOptions = useOcrStore((s) => s.advancedOptions);
  const saveProfile = useOcrStore((s) => s.saveProfile);
  const [engines, setEngines] = useState<Record<string, { available: boolean; reason: string }>>({});
  const [nameError, setNameError] = useState('');

  useEffect(() => {
    void api.listEngines().then((r) => {
      const map: Record<string, { available: boolean; reason: string }> = {};
      for (const e of r.engines) map[e.id] = { available: e.available, reason: e.reason };
      setEngines(map);
    });
  }, []);

  const profile = profiles.find((p) => p.id === activeProfileId);

  function toggleLang(id: string) {
    const langs = activeLanguages.includes(id)
      ? activeLanguages.filter((l) => l !== id)
      : [...activeLanguages, id];
    useOcrStore.setState({ activeLanguages: langs });
  }
  function toggleFormat(id: ExportFormatId) {
    const fmts = activeFormats.includes(id)
      ? activeFormats.filter((f) => f !== id)
      : [...activeFormats, id];
    useOcrStore.setState({ activeFormats: fmts });
  }
  function toggleOption(id: string) {
    useOcrStore.setState({ advancedOptions: { ...advancedOptions, [id]: !advancedOptions[id] } });
  }

  async function saveAsCustom() {
    const parsed = profileSchema.safeParse({ name: `${profile?.name ?? 'Perfil'} (cópia)` });
    if (!parsed.success) {
      setNameError(parsed.error.issues[0]?.message ?? 'Nome inválido');
      return;
    }
    setNameError('');
    await saveProfile({
      id: `custom-${Date.now()}`,
      name: parsed.data.name,
      description: 'Perfil criado pelo usuário.',
      icon: 'sliders-horizontal',
      builtIn: false,
      engine: (activeEngine as OcrEngineId) ?? 'auto',
      languages: activeLanguages,
      exportFormats: activeFormats,
      options: advancedOptions,
    });
  }

  return (
    <section aria-label="Configuração de OCR" className="rounded-lg border border-border bg-white p-5">
      <h2 className="text-[15px] font-medium">2 · Configuração de OCR</h2>

      <h3 className="mt-4 text-[13px] font-medium text-muted">Perfil</h3>
      <div className="mt-2 grid grid-cols-2 gap-2 xl:grid-cols-3" role="radiogroup" aria-label="Perfis de OCR">
        {profiles.map((p) => {
          const Icon = ICONS[p.icon] ?? SlidersHorizontal;
          const active = p.id === activeProfileId;
          return (
            <button
              key={p.id}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => useOcrStore.setState({ activeProfileId: p.id })}
              className={cx(
                'rounded-lg border p-3 text-left transition-colors',
                active ? 'border-primary bg-primary-soft' : 'border-border hover:border-muted',
              )}
            >
              <span className="flex items-center gap-1.5 font-medium">
                <Icon size={15} aria-hidden /> {p.name}
                {active ? <Check size={14} aria-label="Selecionado" className="text-warn" /> : null}
              </span>
              <span className="mt-0.5 block text-xs text-muted">{p.description}</span>
            </button>
          );
        })}
      </div>
      {nameError ? <p className="mt-1 text-xs text-err" role="alert">{nameError}</p> : null}
      <div className="mt-2 flex gap-2">
        <button type="button" onClick={() => void saveAsCustom()} className="rounded-lg border border-brand-blue px-3 py-1.5 text-[13px] text-brand-blue">
          Duplicar perfil atual
        </button>
      </div>

      <h3 className="mt-4 text-[13px] font-medium text-muted">Idiomas</h3>
      <div className="mt-2 flex flex-wrap gap-1.5" role="group" aria-label="Idiomas">
        {LANGS.map((l) => {
          const on = activeLanguages.includes(l.id);
          return (
            <button
              key={l.id}
              type="button"
              aria-pressed={on}
              onClick={() => toggleLang(l.id)}
              className={cx(
                'rounded-full border px-3 py-1 text-[13px]',
                on ? 'border-primary bg-primary-soft font-medium' : 'border-border text-muted',
              )}
            >
              {on ? <Check size={12} aria-hidden className="mr-1 inline" /> : null}{l.label}
            </button>
          );
        })}
      </div>

      <h3 className="mt-4 text-[13px] font-medium text-muted">Motor — o que cada um faz</h3>
      <div className="mt-2 space-y-3" role="radiogroup" aria-label="Motores OCR">
        {(
          [
            { key: 'classic', legend: 'Automático e clássicos / HTR — com caixas por linha', ids: ENGINE_GROUPS.classic },
            { key: 'visual', legend: 'Visuais — página inteira, sem caixas por linha · revisão obrigatória', ids: ENGINE_GROUPS.visual },
          ] as const
        ).map((g) => (
          <fieldset key={g.key}>
            <legend className="text-xs font-medium text-muted">{g.legend}</legend>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {g.ids.map((e) => {
                const info = engines[e];
                const off = info && e !== 'auto' && !info.available;
                const active = activeEngine === e;
                const desc = ENGINE_DESCRIPTIONS[e] ?? '';
                const endpoint = ENGINE_ENDPOINTS[e];
                return (
                  <Tooltip.Provider key={e}>
                    <Tooltip.Root>
                      <Tooltip.Trigger asChild>
                        <button
                          type="button"
                          role="radio"
                          aria-checked={active}
                          title={endpoint ? `${desc} · Servidor local ${endpoint}` : desc}
                          onClick={() => useOcrStore.setState({ activeEngine: e })}
                          className={cx(
                            'rounded-lg border px-3 py-1.5 text-left text-[13px]',
                            active ? 'border-primary bg-primary-soft font-medium' : 'border-border',
                            off && 'opacity-70',
                          )}
                        >
                          {ENGINE_LABELS[e] ?? e}{off ? ' · Não instalado' : ''}
                          <span className="block text-xs font-normal text-muted">{desc}{endpoint ? ` · ${endpoint}` : ''}</span>
                        </button>
                      </Tooltip.Trigger>
                      {off ? (
                        <Tooltip.Content side="bottom" className="z-50 max-w-60 rounded border border-border bg-white px-2 py-1 text-xs shadow">
                          {info.reason} <span className="text-brand-blue underline">Ver instruções</span> — o mock continua funcionando.
                        </Tooltip.Content>
                      ) : null}
                    </Tooltip.Root>
                  </Tooltip.Provider>
                );
              })}
            </div>
          </fieldset>
        ))}
      </div>

      <h3 className="mt-4 text-[13px] font-medium text-muted">Exportação</h3>
      <div className="mt-2 grid grid-cols-2 gap-1.5 xl:grid-cols-4" role="group" aria-label="Formatos de exportação">
        {FORMATS.map((f) => {
          const on = activeFormats.includes(f.id);
          return (
            <button
              key={f.id}
              type="button"
              aria-pressed={on}
              title={f.hint}
              onClick={() => toggleFormat(f.id)}
              className={cx('rounded-lg border px-2 py-1.5 text-left text-[13px]', on ? 'border-primary bg-primary-soft font-medium' : 'border-border')}
            >
              {f.label}
              <span className="block text-xs font-normal text-muted">{f.hint}</span>
            </button>
          );
        })}
      </div>

      <Collapsible.Root className="mt-4 rounded-lg border border-border">
        <Collapsible.Trigger className="flex w-full items-center justify-between px-4 py-2.5 text-[13px] font-medium">
          Configurações avançadas
          <ChevronDown size={15} aria-hidden />
        </Collapsible.Trigger>
        <Collapsible.Content className="border-t border-border px-4 py-3">
          <ul className="grid gap-2 md:grid-cols-2">
            {ADVANCED.map((o) => (
              <li key={o.id} className="flex items-start gap-2.5" title={o.hint}>
                <button
                  type="button"
                  role="switch"
                  aria-checked={!!advancedOptions[o.id]}
                  aria-label={o.label}
                  onClick={() => toggleOption(o.id)}
                  className={cx('mt-0.5 flex h-5 w-9 flex-none items-center rounded-full px-0.5 transition-colors', advancedOptions[o.id] ? 'bg-primary' : 'bg-border')}
                >
                  <span className={cx('h-4 w-4 rounded-full bg-white shadow transition-transform', advancedOptions[o.id] && 'translate-x-4')} />
                </button>
                <span className="text-[13px]">{o.label}<span className="block text-xs text-muted">{o.hint}</span></span>
              </li>
            ))}
          </ul>
        </Collapsible.Content>
      </Collapsible.Root>
      <p className="mt-3 text-xs text-muted">
        Resumo: {documentsSummary()} · Saída: {activeFormats.map((f) => f.toUpperCase()).join(', ') || '—'}
      </p>
    </section>
  );

  function documentsSummary() {
    return `Perfil ${profile?.name ?? '—'} · Motor ${ENGINE_LABELS[activeEngine] ?? activeEngine}`;
  }
}
