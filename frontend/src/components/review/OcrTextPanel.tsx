/** Painel de texto OCR editável: palavras com confiança, popover de ações. */

import * as Popover from '@radix-ui/react-popover';
import { Check } from 'lucide-react';
import { useState } from 'react';
import { cx, formatConfidence } from '../../lib/utils';
import type { OcrPage, OcrWord, RevisionEvent } from '../../types/ocr';

export function OcrTextPanel({
  pages,
  activePageId,
  selectedWordId,
  onSelectWord,
  onAction,
  dirty,
}: {
  pages: OcrPage[];
  activePageId: string;
  selectedWordId: string | null;
  onSelectWord: (wordId: string) => void;
  onAction: (wordId: string, action: RevisionEvent['action'], value?: string) => void;
  dirty: boolean;
}) {
  const [showNumbers, setShowNumbers] = useState(true);
  const page = pages.find((p) => p.id === activePageId) ?? pages[0];
  if (!page) return <p className="p-4 text-[13px] text-muted">Sem texto.</p>;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between border-b border-border p-2 text-[13px]">
        <label className="flex items-center gap-1.5 text-muted">
          <input type="checkbox" checked={showNumbers} onChange={(e) => setShowNumbers(e.target.checked)} />
          Numeração de linha
        </label>
        <span aria-live="polite" className={cx('rounded-full px-2.5 py-0.5 text-xs', dirty ? 'bg-warn-soft text-warn' : 'bg-ok-soft text-ok')}>
          {dirty ? 'Alterações não salvas' : 'Salvo agora'}
        </span>
      </div>
      <div className="mono min-h-0 flex-1 overflow-auto p-4 text-[13px] leading-8">
        {page.lines.map((line) => (
          <p key={line.id} className="mb-1">
            {showNumbers ? <span className="mr-2 select-none text-xs text-muted">{line.number}</span> : null}
            {line.words.map((w, i) => (
              <span key={w.id}>
                <WordToken word={w} selected={w.id === selectedWordId} onSelect={onSelectWord} onAction={onAction} />
                {i < line.words.length - 1 ? ' ' : ''}
              </span>
            ))}
          </p>
        ))}
        {!page.lines.length ? <p className="font-sans text-muted">Página sem linhas reconhecidas.</p> : null}
      </div>
    </div>
  );
}

function WordToken({
  word,
  selected,
  onSelect,
  onAction,
}: {
  word: OcrWord;
  selected: boolean;
  onSelect: (id: string) => void;
  onAction: (wordId: string, action: RevisionEvent['action'], value?: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(word.text);
  const weak = word.confidence < 0.7;
  const done = word.status === 'accepted' || word.status === 'edited';

  return (
    <Popover.Root
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (v) {
          onSelect(word.id);
          setDraft(word.text);
        }
      }}
    >
      <Popover.Trigger asChild>
        <button
          type="button"
          aria-label={`Palavra ${word.text}, confiança ${formatConfidence(word.confidence)}, status ${word.status}`}
          className={cx(
            'rounded px-0.5',
            weak && !done && 'bg-[#fff3c4] underline decoration-orange-500 decoration-dashed underline-offset-4',
            done && 'text-ok',
            selected && 'outline outline-2 outline-brand-blue',
          )}
        >
          {word.text}
          {done ? <Check size={11} aria-hidden className="ml-0.5 inline text-ok" /> : null}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content side="bottom" align="start" className="z-50 w-72 rounded-lg border border-border bg-white p-3 text-[13px] shadow-xl">
          <p><strong>Leitura:</strong> <span className="mono">{word.text}</span></p>
          <p className="text-muted">Confiança: {formatConfidence(word.confidence)}</p>
          {word.alternatives?.length ? (
            <ul className="mt-1.5 space-y-1">
              {word.alternatives.map((a) => (
                <li key={a.text}>
                  <button
                    type="button"
                    onClick={() => {
                      onAction(word.id, 'edited', a.text);
                      setOpen(false);
                    }}
                    className="w-full rounded border border-border px-2 py-1 text-left hover:bg-surface"
                  >
                    <span className="mono">{a.text}</span>
                    <span className="ml-2 text-xs text-muted">{formatConfidence(a.confidence)} · {a.source}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          <div className="mt-2 flex gap-1.5">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              aria-label="Editar texto da palavra"
              className="mono min-w-0 flex-1 rounded border border-border px-2 py-1"
            />
            <button
              type="button"
              onClick={() => {
                onAction(word.id, 'edited', draft);
                setOpen(false);
              }}
              className="rounded bg-primary px-2.5 py-1 font-medium text-[#202124]"
            >
              Salvar
            </button>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-1">
            <Act label="Aceitar leitura" onClick={() => { onAction(word.id, 'accepted'); setOpen(false); }} />
            <Act label="Aceitar sugestão IA" hint="Ação explícita; nada é aplicado sozinho" onClick={() => { onAction(word.id, 'edited', word.alternatives?.[0]?.text ?? word.text); setOpen(false); }} />
            <Act label="Ilegível" onClick={() => { onAction(word.id, 'illegible'); setOpen(false); }} />
            <Act label="Abrev. histórica" onClick={() => { onAction(word.id, 'abbreviation'); setOpen(false); }} />
            <Act label="Nome próprio" onClick={() => { onAction(word.id, 'proper_noun'); setOpen(false); }} />
            <Act label="P/ treinamento" onClick={() => { onAction(word.id, 'training'); setOpen(false); }} />
            <Act label="Ignorar" onClick={() => setOpen(false)} />
            <Act label="+ dicionário" onClick={() => { onAction(word.id, 'accepted'); setOpen(false); }} />
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

function Act({ label, hint, onClick }: { label: string; hint?: string; onClick: () => void }) {
  return (
    <button type="button" title={hint} onClick={onClick} className="rounded border border-border px-2 py-1 text-xs hover:bg-surface">
      {label}
    </button>
  );
}
