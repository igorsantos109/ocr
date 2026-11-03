/** Camada própria de mock: latência simulada + progressão de processamento.
 *  Nenhum dado OCR é alterado automaticamente; revisões exigem ação explícita. */

import type {
  EngineInfo,
  LlmState,
  OcrPage,
  OcrProfile,
  ProcessingSnapshot,
  QueueDocument,
  RevisionEvent,
} from '../types/ocr';
import {
  mockCollections,
  mockDocuments,
  mockPages,
  mockProfiles,
  mockReviewQueue,
} from '../data/mockDocuments';
import type { OcrApi } from './api';

const wait = (ms = 350) => new Promise((r) => setTimeout(r, ms));
let seq = 100;

const docs: QueueDocument[] = structuredClone(mockDocuments);
const profiles: OcrProfile[] = structuredClone(mockProfiles);
const history: RevisionEvent[] = [
  {
    id: 'ev1',
    wordId: 'l1w4',
    documentId: 'doc-img-4253',
    action: 'edited',
    previousValue: 'homtem',
    nextValue: 'hontem',
    createdAt: new Date(Date.now() - 86400000).toISOString(),
    actor: 'arquivista',
  },
];

const snapshot: ProcessingSnapshot = {
  state: 'running',
  message: 'OCR em andamento: página 5 de 8',
  percent: 62,
  documentsTotal: 1,
  documentsDone: 0,
  pagesOk: 4,
  pagesError: 0,
  reviewPending: 31,
  avgSecondsPerPage: 8.4,
  log: ['[info] Pré-processamento concluído', '[info] OCR em andamento: página 5 de 8'],
};

let timer: ReturnType<typeof setInterval> | null = null;
const listeners = new Set<() => void>();
function emit() {
  listeners.forEach((fn) => fn());
}

function tick() {
  if (snapshot.state !== 'running') return;
  const active = docs.find((d) => d.status === 'ocr');
  if (!active) {
    snapshot.state = 'done';
    snapshot.message = 'OCR técnico concluído';
    snapshot.percent = 100;
    emit();
    return;
  }
  active.progress = Math.min(100, active.progress + 3);
  active.stage = `OCR — página ${Math.min(active.pages, Math.floor((active.progress / 100) * active.pages) + 1)} de ${active.pages}`;
  snapshot.percent = active.progress;
  snapshot.message = active.stage;
  snapshot.pagesOk = Math.floor((active.progress / 100) * active.pages);
  if (active.progress >= 100) {
    active.status = 'needs_review';
    active.pendingReview = 6;
    active.confidence = 0.74;
    active.log = [...active.log, { id: `lg${seq++}`, at: new Date().toISOString(), level: 'info', message: 'OCR concluído; trechos enviados à revisão' }];
    snapshot.state = 'done';
    snapshot.message = 'OCR técnico concluído';
  }
  emit();
}

function ensureTimer() {
  if (!timer) timer = setInterval(tick, 1200);
}

export function subscribeProcessing(fn: () => void) {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export const mockApi: OcrApi = {
  async listCollections() {
    await wait(200);
    return structuredClone(mockCollections);
  },
  async listDocuments(collectionId, query) {
    await wait();
    let out = docs;
    if (collectionId) out = out.filter((d) => d.collectionId === collectionId);
    if (query) {
      const q = query.toLowerCase();
      out = out.filter((d) => d.name.toLowerCase().includes(q));
    }
    return structuredClone(out);
  },
  async getDocument(id) {
    await wait(200);
    const d = docs.find((x) => x.id === id);
    if (!d) throw new Error('Documento não encontrado');
    return structuredClone(d);
  },
  async getPages(documentId) {
    await wait();
    const pages: OcrPage[] = mockPages.filter((p) => p.documentId === documentId);
    if (pages.length) return structuredClone(pages);
    const doc = docs.find((d) => d.id === documentId);
    const n = doc?.pages ?? 1;
    return Array.from({ length: n }, (_, i) => ({
      id: `${documentId}-p${i + 1}`,
      documentId,
      number: i + 1,
      width: 800,
      height: 1000,
      status: 'done' as const,
      lines: [],
    }));
  },
  async getReviewQueue(documentId, limit = 50) {
    await wait();
    let items = mockReviewQueue;
    if (documentId) items = items.filter((i) => i.documentId === documentId);
    return structuredClone(items.slice(0, limit));
  },
  async listProfiles() {
    await wait(200);
    return structuredClone(profiles);
  },
  async saveProfile(p) {
    await wait(200);
    const i = profiles.findIndex((x) => x.id === p.id);
    if (i >= 0) profiles[i] = structuredClone(p);
    else profiles.push(structuredClone(p));
    return structuredClone(p);
  },
  async deleteProfile(id) {
    await wait(200);
    const i = profiles.findIndex((x) => x.id === id);
    if (i >= 0) profiles.splice(i, 1);
  },
  async listEngines() {
    await wait(200);
    const engines: EngineInfo[] = [
      { id: 'auto', available: true, reason: '' },
      { id: 'tesseract', available: true, reason: '' },
      { id: 'paddleocr', available: true, reason: '' },
      { id: 'kraken', available: true, reason: '' },
      { id: 'easyocr', available: true, reason: '' },
      { id: 'hybrid', available: true, reason: '' },
      { id: 'deepseek_ocr2', available: true, reason: '' },
    ];
    return { engines, recommended: 'auto' };
  },
  async llmState() {
    await wait(150);
    const s: LlmState = { enabled: false, model: 'huihui-qwen3-8b-abliterated-v2' };
    return s;
  },
  async processing() {
    ensureTimer();
    return structuredClone(snapshot);
  },
  async upload(files, collectionId) {
    await wait(600);
    const created: QueueDocument[] = files.map((f) => {
      const id = `doc-${Date.now()}-${seq++}`;
      const isPdf = /\.pdf$/i.test(f.name);
      return {
        id,
        name: f.name,
        collectionId,
        type: isPdf ? ('pdf' as const) : ('image' as const),
        pages: isPdf ? 4 : 1,
        estimatedPages: isPdf ? 4 : 1,
        profileId: 'jornal-historico',
        engine: 'auto' as const,
        status: 'queued' as const,
        progress: 0,
        confidence: null,
        pendingReview: 0,
        updatedAt: new Date().toISOString(),
        log: [{ id: `lg${seq++}`, at: new Date().toISOString(), level: 'info' as const, message: `Adicionado (${(f.size / 1024).toFixed(0)} KB)` }],
      };
    });
    docs.unshift(...created);
    emit();
    return structuredClone(created);
  },
  async startProcessing(ids) {
    await wait(200);
    const targets = ids?.length ? docs.filter((d) => ids.includes(d.id)) : docs.filter((d) => d.status === 'queued' || d.status === 'draft');
    for (const t of targets) {
      t.status = 'ocr';
      t.progress = 5;
      t.stage = 'Pré-processamento';
    }
    snapshot.state = 'running';
    snapshot.documentsTotal = targets.length;
    snapshot.documentsDone = 0;
    ensureTimer();
    emit();
  },
  async pauseProcessing() {
    snapshot.state = 'paused';
    snapshot.message = 'Processamento pausado';
    emit();
  },
  async resumeProcessing() {
    snapshot.state = 'running';
    emit();
  },
  async cancelProcessing() {
    snapshot.state = 'cancelled';
    snapshot.message = 'Processamento cancelado';
    for (const d of docs) if (d.status === 'ocr') d.status = 'cancelled';
    emit();
  },
  async retryDocument(id) {
    const d = docs.find((x) => x.id === id);
    if (!d) throw new Error('Documento não encontrado');
    d.status = 'ocr';
    d.progress = 5;
    d.error = undefined;
    snapshot.state = 'running';
    ensureTimer();
    emit();
  },
  async removeDocument(id) {
    const i = docs.findIndex((x) => x.id === id);
    if (i >= 0) docs.splice(i, 1);
    emit();
  },
  async moveDocument(id, collectionId) {
    const d = docs.find((x) => x.id === id);
    if (!d) throw new Error('Documento não encontrado');
    d.collectionId = collectionId;
    d.updatedAt = new Date().toISOString();
    emit();
  },
  async duplicateWithProfile(id, profileId) {
    const d = docs.find((x) => x.id === id);
    if (!d) throw new Error('Documento não encontrado');
    const copy: QueueDocument = { ...structuredClone(d), id: `doc-${Date.now()}`, name: `${d.name} (cópia)`, profileId, status: 'draft', progress: 0 };
    docs.unshift(copy);
    emit();
    return structuredClone(copy);
  },
  async applyWordAction(wordId, action, value) {
    await wait(150);
    history.unshift({
      id: `ev${seq++}`,
      wordId,
      documentId: 'doc-img-4253',
      action,
      previousValue: undefined,
      nextValue: value,
      createdAt: new Date().toISOString(),
      actor: 'revisora',
    });
    emit();
  },
  async markLine(lineId, status) {
    await wait(150);
    history.unshift({
      id: `ev${seq++}`,
      lineId,
      documentId: 'doc-img-4253',
      action: status as RevisionEvent['action'],
      createdAt: new Date().toISOString(),
      actor: 'revisora',
    });
    emit();
  },
  async history() {
    await wait(200);
    return structuredClone(history);
  },
  async exportDocument() {
    await wait(400);
    return { files: ['documento.pdf', 'documento.txt', 'documento.json'] };
  },
  async logs(documentId) {
    await wait(200);
    return structuredClone(docs.find((d) => d.id === documentId)?.log ?? []);
  },
};
