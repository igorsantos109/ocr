/** Cliente `live`: fala com o backend Python real (FastAPI futura / stdlib atual).
 *  Rotas cobertas: /api/documentos, /api/documento, /api/pagina, /api/linha,
 *  /api/revisao, /api/resumo, /api/motores, /api/llm-estado, /api/trabalho,
 *  /api/upload, /api/processar, /api/cancelar, /api/corrigir, /api/marcar,
 *  /api/produtos. Coleções e perfis seguem locais (Dexie) até o backend tê-los. */

import type {
  OcrPage,
  OcrProfile,
  ProcessingSnapshot,
  QueueDocument,
  ReviewItem,
} from '../types/ocr';
import { API_BASE } from './api';
import type { OcrApi } from './api';
import { mockApi } from './mockApi';

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) throw new Error(`HTTP ${r.status} em ${path}`);
  return (await r.json()) as T;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status} em ${path}`);
  return (await r.json()) as T;
}

interface BackendDoc {
  id: string;
  nome: string;
  tipo: string;
  paginas: number;
  status: string;
}
interface BackendReview {
  id: string;
  documento_id: string;
  documento: string;
  pagina: number;
  numero: number;
  texto: string;
  confianca: number | null;
  status: string;
}

const STATUS_MAP: Record<string, QueueDocument['status']> = {
  aguardando_ocr: 'queued',
  concluido: 'completed',
  parcial: 'needs_review',
  erro: 'failed',
};

export const liveApi: OcrApi = {
  ...mockApi,
  async listDocuments(_collectionId, query) {
    const params = new URLSearchParams();
    if (query) params.set('busca', query);
    const data = await get<{ documentos: BackendDoc[] }>(`/api/documentos?${params}`);
    return data.documentos.map((d) => ({
      id: d.id,
      name: d.nome,
      collectionId: 'col-jornais-rj-1927',
      type: d.tipo === 'pdf' ? ('pdf' as const) : ('image' as const),
      pages: d.paginas,
      profileId: 'jornal-historico',
      engine: 'auto' as const,
      status: STATUS_MAP[d.status] ?? 'draft',
      progress: d.status === 'concluido' ? 100 : 0,
      confidence: null,
      pendingReview: 0,
      updatedAt: new Date().toISOString(),
      log: [],
    }));
  },
  async getReviewQueue(documentId, limit = 50) {
    const params = new URLSearchParams({ limite: String(limit) });
    if (documentId) params.set('documento', documentId);
    const data = await get<{ linhas: BackendReview[] }>(`/api/revisao?${params}`);
    return data.linhas.map((l): ReviewItem => ({
      id: l.id,
      documentId: l.documento_id,
      documentName: l.documento,
      pageId: '',
      page: l.pagina,
      lineId: l.id,
      line: l.numero,
      text: l.texto,
      confidence: l.confianca,
      severity: l.confianca == null || l.confianca < 0.6 ? 'high' : l.confianca < 0.8 ? 'medium' : 'low',
      kind: 'low_confidence',
      status: 'pending',
    }));
  },
  async getPages(documentId) {
    const doc = await get<{ paginas: Array<{ id: string; numero: number; status: string }> }>(
      `/api/documento?id=${encodeURIComponent(documentId)}`,
    );
    const pages: OcrPage[] = [];
    for (const p of doc.paginas) {
      const det = await get<{ linhas: Array<{ id: string; numero: number; x: number; y: number; largura: number; altura: number; texto: string; confianca: number | null; status: string }> }>(
        `/api/pagina?id=${encodeURIComponent(p.id)}`,
      );
      pages.push({
        id: p.id,
        documentId,
        number: p.numero,
        width: 800,
        height: 1000,
        status: p.status === 'concluida' ? 'done' : 'pending',
        imageUrl: `${API_BASE}/api/pagina/imagem?id=${encodeURIComponent(p.id)}&tipo=overlay`,
        lines: det.linhas.map((l) => ({
          id: l.id,
          pageId: p.id,
          number: l.numero,
          boundingBox: { x: l.x, y: l.y, width: l.largura, height: l.altura },
          confidence: l.confianca,
          status: 'pending' as const,
          words: [
            {
              id: l.id,
              pageId: p.id,
              lineId: l.id,
              text: l.texto,
              originalText: l.texto,
              confidence: l.confianca ?? 0,
              boundingBox: { x: l.x, y: l.y, width: l.largura, height: l.altura },
              status: 'pending' as const,
            },
          ],
        })),
      });
    }
    return pages;
  },
  async listEngines() {
    // Repassa os ids do backend sem filtrar (inclui `deepseek_ocr2` desde o novo motor);
    // rótulos/descrições ficam em ENGINE_LABELS/ENGINE_DESCRIPTIONS no frontend.
    const data = await get<{ motores: Array<{ nome: string; disponivel: boolean; motivo: string }>; recomendado: string }>(
      '/api/motores',
    );
    return {
      engines: data.motores.map((m) => ({ id: m.nome, available: m.disponivel, reason: m.motivo })),
      recommended: data.recomendado,
    };
  },
  async llmState() {
    return get<{ enabled: boolean; model: string }>('/api/llm-estado');
  },
  async processing() {
    const t = await get<{ estado: string; mensagem: string; percentual: number; resumo?: { documentos?: number; paginas_ok?: number; paginas_erro?: number } }>('/api/trabalho');
    const s: ProcessingSnapshot = {
      state: t.estado === 'rodando' ? 'running' : t.estado === 'concluido' ? 'done' : t.estado === 'erro' ? 'error' : 'idle',
      message: t.mensagem,
      percent: t.percentual,
      documentsTotal: t.resumo?.documentos ?? 0,
      documentsDone: t.resumo?.documentos ?? 0,
      pagesOk: t.resumo?.paginas_ok ?? 0,
      pagesError: t.resumo?.paginas_erro ?? 0,
      reviewPending: 0,
      avgSecondsPerPage: 0,
      log: [],
    };
    return s;
  },
  async startProcessing(ids, engine) {
    await post('/api/processar', { ids, engine: engine ?? 'auto', forcar: false, retry_failed: true });
  },
  async cancelProcessing() {
    await post('/api/cancelar', {});
  },
  async applyWordAction(wordId, action, value) {
    if (action === 'edited' && value != null) {
      await post('/api/corrigir', { linha_id: wordId, texto: value, usuario: 'web' });
    } else {
      const map: Record<string, string> = { accepted: 'revisada', illegible: 'ilegivel', training: 'treinamento', historical: 'revisada', proper_noun: 'revisada', abbreviation: 'revisada' };
      await post('/api/marcar', { linha_id: wordId, status: map[action] ?? 'revisada', usuario: 'web' });
    }
  },
  async upload(files, _collectionId) {
    const form = new FormData();
    for (const f of files) form.append('arquivos', f);
    const r = await fetch(`${API_BASE}/api/upload`, { method: 'POST', body: form });
    if (!r.ok) throw new Error(`HTTP ${r.status} em /api/upload`);
    return mockApi.listDocuments();
  },
  async exportDocument(id) {
    const data = await get<{ arquivos: Array<{ nome: string }> }>(`/api/produtos?id=${encodeURIComponent(id)}`);
    return { files: data.arquivos.map((a) => a.nome) };
  },
  async listProfiles(): Promise<OcrProfile[]> {
    return mockApi.listProfiles();
  },
};
