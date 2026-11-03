/** Upload por botão ou drag-and-drop com validação local e diálogo de duplicata. */

import { FileUp, TriangleAlert } from 'lucide-react';
import { useRef, useState } from 'react';
import { cx } from '../../lib/utils';
import { api } from '../../services';
import { useOcrStore } from '../../store/useOcrStore';
import { ConfirmDialog } from '../common/ConfirmDialog';

const ACCEPT = ['pdf', 'jpg', 'jpeg', 'png', 'tiff', 'tif', 'bmp', 'webp'];
const MAX_MB = 200;

interface Pending {
  files: File[];
  duplicates: string[];
}

export function UploadDropzone({ compact }: { compact?: boolean }) {
  const activeCollectionId = useOcrStore((s) => s.activeCollectionId);
  const documents = useOcrStore((s) => s.documents);
  const refresh = useOcrStore((s) => s.refresh);
  const toast = useOcrStore((s) => s.toast);
  const [drag, setDrag] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [pending, setPending] = useState<Pending | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFiles(list: FileList | File[]) {
    const files = [...list];
    const errs: string[] = [];
    const valid = files.filter((f) => {
      const ext = f.name.split('.').pop()?.toLowerCase() ?? '';
      if (!ACCEPT.includes(ext)) {
        errs.push(`${f.name}: extensão .${ext} não suportada`);
        return false;
      }
      if (f.size > MAX_MB * 1024 * 1024) {
        errs.push(`${f.name}: excede ${MAX_MB} MB`);
        return false;
      }
      if (f.size === 0) {
        errs.push(`${f.name}: arquivo vazio ou corrompido`);
        return false;
      }
      return true;
    });
    setErrors(errs);
    if (!valid.length) return;
    const names = new Set(documents.map((d) => d.name.toLowerCase()));
    const duplicates = valid.filter((f) => names.has(f.name.toLowerCase())).map((f) => f.name);
    if (duplicates.length) {
      setPending({ files: valid, duplicates });
      return;
    }
    await send(valid);
  }

  async function send(files: File[]) {
    const created = await api.upload(files, activeCollectionId);
    await refresh();
    toast(`${created.length} arquivo(s) adicionado(s) · perfil: Jornal histórico`, 'success');
  }

  return (
    <section aria-label="Envio de arquivos" className={cx(!compact && 'rounded-lg border border-border bg-white p-5')}>
      {!compact ? <h2 className="text-[15px] font-medium">1 · Upload e coleção</h2> : null}
      <div
        role="button"
        tabIndex={0}
        aria-label="Arraste arquivos ou pressione Enter para selecionar"
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click();
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          void handleFiles(e.dataTransfer.files);
        }}
        className={cx(
          'mt-3 flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed border-border px-6 text-center transition-colors',
          compact ? 'py-3' : 'py-10',
          drag ? 'border-primary bg-primary-soft' : 'bg-surface hover:bg-surface-hover',
        )}
        onClick={() => inputRef.current?.click()}
      >
        <FileUp size={compact ? 18 : 28} aria-hidden className={drag ? 'text-warn' : 'text-muted'} />
        {!compact ? (
          <>
            <p className="font-medium">Arraste PDF ou imagens aqui</p>
            <p className="text-[13px] text-muted">PDF, JPG, PNG, TIFF, BMP, WEBP · até {MAX_MB} MB por arquivo</p>
          </>
        ) : null}
        <span className="rounded-lg bg-primary px-4 py-2 text-[13px] font-medium text-[#202124] hover:bg-primary-hover">
          {compact ? 'Adicionar arquivos' : 'Selecionar arquivos'}
        </span>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT.map((e) => `.${e}`).join(',')}
          className="sr-only"
          aria-label="Selecionar arquivos"
          onChange={(e) => {
            if (e.target.files) void handleFiles(e.target.files);
            e.target.value = '';
          }}
        />
      </div>
      {errors.length ? (
        <ul className="mt-3 space-y-1" aria-live="assertive">
          {errors.map((e) => (
            <li key={e} className="flex items-center gap-2 rounded-md border border-err bg-err-soft px-3 py-2 text-[13px] text-err">
              <TriangleAlert size={14} aria-hidden /> {e}
            </li>
          ))}
        </ul>
      ) : null}
      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(v) => {
          if (!v) setPending(null);
        }}
        title="Possível duplicata"
        description={`${pending?.duplicates.join(', ') ?? ''} já existe(m) nesta coleção (mesmo nome). Processar novamente, ignorar ou substituir? O mock processa novamente.`}
        confirmLabel="Processar novamente"
        onConfirm={() => {
          if (pending) void send(pending.files);
          setPending(null);
        }}
      />
    </section>
  );
}
