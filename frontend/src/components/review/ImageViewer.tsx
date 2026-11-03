/** Painel da imagem: miniaturas, zoom/pan/rotação, brilho, caixas sincronizadas.
 *  O mock desenha a página como SVG (fundo + linhas + caixas das bboxes). */

import { Hand, RotateCw, Sun, ZoomIn, ZoomOut } from 'lucide-react';
import { useState } from 'react';
import { cx } from '../../lib/utils';
import type { OcrPage } from '../../types/ocr';

export function ImageViewer({
  pages,
  activePageId,
  onPage,
  selectedWordId,
  onSelectWord,
}: {
  pages: OcrPage[];
  activePageId: string;
  onPage: (id: string) => void;
  selectedWordId: string | null;
  onSelectWord: (wordId: string) => void;
}) {
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [brightness, setBrightness] = useState(100);
  const [showBoxes, setShowBoxes] = useState(true);
  const page = pages.find((p) => p.id === activePageId) ?? pages[0];

  if (!page) return <p className="p-4 text-[13px] text-muted">Sem páginas.</p>;
  const W = page.width;
  const H = page.height;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-1 border-b border-border p-2" role="toolbar" aria-label="Controles da imagem">
        {pages.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => onPage(p.id)}
            aria-label={`Página ${p.number}`}
            aria-current={p.id === page.id}
            className={cx('rounded border px-2 py-1 text-xs', p.id === page.id ? 'border-primary bg-primary-soft font-medium' : 'border-border')}
          >
            {p.number}
          </button>
        ))}
        <span className="mx-1 h-5 w-px bg-border" aria-hidden />
        <ToolBtn label="Reduzir zoom" onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.25).toFixed(2)))}><ZoomOut size={15} /></ToolBtn>
        <ToolBtn label="Ampliar zoom" onClick={() => setZoom((z) => Math.min(3, +(z + 0.25).toFixed(2)))}><ZoomIn size={15} /></ToolBtn>
        <button type="button" onClick={() => setZoom(1)} className="rounded px-2 py-1 text-xs hover:bg-surface" aria-label="Zoom 100%">100%</button>
        <ToolBtn label="Pan (arraste a imagem)" onClick={() => undefined}><Hand size={15} /></ToolBtn>
        <ToolBtn label="Girar 90 graus" onClick={() => setRotation((r) => (r + 90) % 360)}><RotateCw size={15} /></ToolBtn>
        <label className="flex items-center gap-1 rounded px-1.5 py-1 text-xs text-muted" title="Brilho simulado">
          <Sun size={15} aria-hidden />
          <input type="range" min={60} max={140} value={brightness} onChange={(e) => setBrightness(Number(e.target.value))} aria-label="Brilho" className="w-20" />
        </label>
        <button
          type="button"
          role="switch"
          aria-checked={showBoxes}
          aria-label="Sobreposição de caixas OCR"
          onClick={() => setShowBoxes((v) => !v)}
          className={cx('rounded border px-2 py-1 text-xs', showBoxes ? 'border-primary bg-primary-soft' : 'border-border')}
        >
          Caixas
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto bg-surface p-4" style={{ cursor: 'grab' }}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label={`Imagem da página ${page.number} (simulada)`}
          style={{ width: `${Math.round(W * zoom * 0.7)}px`, maxWidth: 'none', filter: `brightness(${brightness}%)`, transform: `rotate(${rotation}deg)` }}
          className="mx-auto rounded border border-border bg-white shadow"
        >
          <rect x={0} y={0} width={W} height={H} fill="#fdfdf8" />
          {page.lines.flatMap((l) => l.words).map((w, i) => (
            <rect key={w.id} x={w.boundingBox.x} y={w.boundingBox.y + 260} width={w.boundingBox.width} height={10} fill="#e8e4d8" rx={2}>
              <title>{`linha simulada ${i + 1}`}</title>
            </rect>
          ))}
          {showBoxes
            ? page.lines.map((l) => (
              <g key={l.id}>
                <rect x={l.boundingBox.x} y={l.boundingBox.y} width={l.boundingBox.width} height={l.boundingBox.height} fill="none" stroke="#1a73e8" strokeWidth={2} strokeDasharray="6 3" opacity={0.7} />
                {l.words.map((w) => {
                  const sel = w.id === selectedWordId;
                  const weak = w.confidence < 0.7;
                  return (
                    <rect
                      key={w.id}
                      x={w.boundingBox.x}
                      y={w.boundingBox.y}
                      width={w.boundingBox.width}
                      height={w.boundingBox.height}
                      fill={sel ? '#f9ab00' : weak ? '#feefc3' : 'transparent'}
                      fillOpacity={sel ? 0.45 : weak ? 0.55 : 0}
                      stroke={sel ? '#b06000' : weak ? '#f29900' : '#188038'}
                      strokeWidth={sel ? 2.5 : 1.5}
                      style={{ cursor: 'pointer' }}
                      onClick={() => onSelectWord(w.id)}
                    >
                      <title>{`${w.text} (${Math.round(w.confidence * 100)}%)`}</title>
                    </rect>
                  );
                })}
              </g>
            ))
            : null}
        </svg>
      </div>
    </div>
  );
}

function ToolBtn({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} aria-label={label} title={label} className="rounded p-1.5 hover:bg-surface">
      {children}
    </button>
  );
}
