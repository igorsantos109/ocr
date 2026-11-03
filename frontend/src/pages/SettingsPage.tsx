/** Configurações: motores, perfis (CRUD + JSON), preferências. */

import { useEffect, useState } from 'react';
import { ENGINE_DESCRIPTIONS, ENGINE_ENDPOINTS, ENGINE_LABELS } from '../data/mockDocuments';
import { api } from '../services';
import { useOcrStore } from '../store/useOcrStore';
import type { EngineInfo } from '../types/ocr';

export function SettingsPage() {
  const profiles = useOcrStore((s) => s.profiles);
  const saveProfile = useOcrStore((s) => s.saveProfile);
  const removeProfile = useOcrStore((s) => s.removeProfile);
  const toast = useOcrStore((s) => s.toast);
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [recommended, setRecommended] = useState('');
  const [enginesError, setEnginesError] = useState(false);
  const [json, setJson] = useState('');

  useEffect(() => {
    void api.listEngines().then((r) => {
      setEngines(r.engines);
      setRecommended(r.recommended);
    }).catch(() => setEnginesError(true));
  }, []);

  function exportProfiles() {
    setJson(JSON.stringify(profiles, null, 2));
    toast('Perfis exportados em JSON abaixo', 'info');
  }

  async function importProfiles() {
    try {
      const parsed = JSON.parse(json) as unknown;
      if (!Array.isArray(parsed)) throw new Error('JSON deve ser uma lista de perfis');
      for (const p of parsed) {
        // eslint-disable-next-line no-await-in-loop
        await saveProfile(p as (typeof profiles)[number]);
      }
    } catch (e) {
      toast(`Importação falhou: ${(e as Error).message}`, 'error');
    }
  }

  return (
    <div className="space-y-4 pt-6">
      <h1 className="text-[16px] font-medium">Configurações, motores e perfis</h1>

      <section aria-label="Motores" className="rounded-lg border border-border p-5">
        <h2 className="text-[15px] font-medium">Motores OCR</h2>
        <p className="text-[13px] text-muted">Recomendado: {ENGINE_LABELS[recommended] ?? recommended}</p>
        {enginesError && !engines.length ? (
          <p className="mt-3 rounded-lg bg-warn-soft px-3 py-2 text-[13px]">Não foi possível carregar os motores do backend — o mock continua funcionando.</p>
        ) : null}
        <ul className="mt-3 grid gap-2 md:grid-cols-2">
          {engines.map((e) => (
            <li key={e.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-[13px]">
              <span>
                <span className="font-medium">{ENGINE_LABELS[e.id] ?? e.id}</span>
                <span className="block text-xs text-muted">
                  {ENGINE_DESCRIPTIONS[e.id] ?? e.id}{ENGINE_ENDPOINTS[e.id] ? ` · Servidor local ${ENGINE_ENDPOINTS[e.id]}` : ''}
                </span>
              </span>
              {e.available ? (
                <span className="rounded-full bg-ok-soft px-2.5 py-0.5 text-xs text-ok">Disponível</span>
              ) : (
                <span className="rounded-full bg-surface px-2.5 py-0.5 text-xs text-muted" title={e.reason}>
                  Não instalado · <span className="text-brand-blue underline">Ver instruções</span>
                </span>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section aria-label="Perfis" className="rounded-lg border border-border p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-medium">Perfis ({profiles.length})</h2>
          <div className="flex gap-1.5">
            <button type="button" onClick={exportProfiles} className="rounded-lg border border-border px-3 py-1.5 text-[13px]">Exportar JSON</button>
            <button type="button" onClick={() => void importProfiles()} className="rounded-lg border border-border px-3 py-1.5 text-[13px]">Importar JSON</button>
          </div>
        </div>
        <ul className="mt-3 space-y-1.5">
          {profiles.map((p) => (
            <li key={p.id} className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-[13px]">
              <span><strong>{p.name}</strong> <span className="text-muted">· {p.description} {p.builtIn ? '(embutido)' : ''}</span></span>
              {!p.builtIn ? (
                <button type="button" onClick={() => void removeProfile(p.id)} className="rounded border border-border px-2 py-0.5 text-xs text-err" aria-label={`Excluir perfil ${p.name}`}>
                  Excluir
                </button>
              ) : null}
            </li>
          ))}
        </ul>
        <label className="mt-3 block text-[13px] font-medium" htmlFor="perfis-json">JSON de perfis (importar/exportar)</label>
        <textarea
          id="perfis-json"
          value={json}
          onChange={(e) => setJson(e.target.value)}
          rows={8}
          placeholder='[{"id": "...", "name": "...", ...}]'
          className="mono mt-1 w-full rounded-lg border border-border p-2.5 text-xs"
        />
      </section>

      <section aria-label="Preferências" className="rounded-lg border border-border p-5">
        <h2 className="text-[15px] font-medium">Preferências</h2>
        <p className="mt-1 text-[13px] text-muted">Tema claro (padrão Colab). Tema escuro e densidade de interface: previstos, sem dependência de backend.</p>
      </section>
    </div>
  );
}
