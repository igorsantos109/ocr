/** Estado global (Zustand): documentos, coleções, perfis, fila de revisão,
 *  processamento, toasts. Persistência de coleções/perfis/revisões em Dexie. */

import { create } from 'zustand';
import { db } from '../db';
import { api, subscribeProcessing } from '../services';
import type {
  ExportFormatId,
  OcrCollection,
  OcrPage,
  OcrProfile,
  ProcessingSnapshot,
  QueueDocument,
  ReviewItem,
  RevisionEvent,
} from '../types/ocr';

export interface Toast {
  id: number;
  message: string;
  kind: 'success' | 'error' | 'info';
}

interface OcrState {
  ready: boolean;
  documents: QueueDocument[];
  collections: OcrCollection[];
  profiles: OcrProfile[];
  reviewQueue: ReviewItem[];
  processing: ProcessingSnapshot;
  history: RevisionEvent[];
  toasts: Toast[];
  selectedIds: string[];
  query: string;
  statusFilter: string;
  activeCollectionId: string;
  activeProfileId: string;
  activeEngine: string;
  activeLanguages: string[];
  activeFormats: ExportFormatId[];
  advancedOptions: Record<string, boolean>;

  boot(): Promise<void>;
  refresh(): Promise<void>;
  setQuery(q: string): void;
  setStatusFilter(s: string): void;
  setCollection(id: string): void;
  toggleSelect(id: string): void;
  clearSelection(): void;
  toast(message: string, kind?: Toast['kind']): void;
  dismissToast(id: number): void;
  saveProfile(p: OcrProfile): Promise<void>;
  removeProfile(id: string): Promise<void>;
  applyWordAction(wordId: string, action: RevisionEvent['action'], value?: string): Promise<void>;
}

let toastSeq = 1;
let subscribed = false;

export const useOcrStore = create<OcrState>()((set, get) => ({
  ready: false,
  documents: [],
  collections: [],
  profiles: [],
  reviewQueue: [],
  processing: {
    state: 'idle', message: '', percent: 0, documentsTotal: 0, documentsDone: 0,
    pagesOk: 0, pagesError: 0, reviewPending: 0, avgSecondsPerPage: 0, log: [],
  },
  history: [],
  toasts: [],
  selectedIds: [],
  query: '',
  statusFilter: '',
  activeCollectionId: 'col-jornais-rj-1927',
  activeProfileId: 'jornal-historico',
  activeEngine: 'auto',
  activeLanguages: ['pt-historico'],
  activeFormats: ['pdf'],
  advancedOptions: { deskew: true, denoise: true, clahe: true, preserveLayout: true },

  async boot() {
    if (!subscribed) {
      subscribed = true;
      subscribeProcessing(() => {
        void get().refresh();
      });
    }
    const [collections, profiles, documents, reviewQueue, processing] = await Promise.all([
      api.listCollections(),
      api.listProfiles(),
      api.listDocuments(),
      api.getReviewQueue(undefined, 50),
      api.processing(),
    ]);
    try {
      const savedCols = await db.collections.toArray();
      const savedProfiles = await db.profiles.toArray();
      if (savedCols.length) {
        const ids = new Set(collections.map((c) => c.id));
        collections.push(...savedCols.filter((c) => !ids.has(c.id)));
      }
      if (savedProfiles.length) {
        const ids = new Set(profiles.map((p) => p.id));
        profiles.push(...savedProfiles.filter((p) => !ids.has(p.id)));
      }
    } catch {
      /* IndexedDB indisponível: segue com mocks */
    }
    set({ collections, profiles, documents, reviewQueue, processing, ready: true });
  },

  async refresh() {
    const [documents, reviewQueue, processing] = await Promise.all([
      api.listDocuments(),
      api.getReviewQueue(undefined, 50),
      api.processing(),
    ]);
    set({ documents, reviewQueue, processing });
  },

  setQuery: (query) => set({ query }),
  setStatusFilter: (statusFilter) => set({ statusFilter }),
  setCollection: (activeCollectionId) => set({ activeCollectionId }),
  toggleSelect: (id) =>
    set((s) => ({
      selectedIds: s.selectedIds.includes(id)
        ? s.selectedIds.filter((x) => x !== id)
        : [...s.selectedIds, id],
    })),
  clearSelection: () => set({ selectedIds: [] }),

  toast: (message, kind = 'info') => {
    const id = toastSeq++;
    set((s) => ({ toasts: [...s.toasts, { id, message, kind }] }));
    setTimeout(() => get().dismissToast(id), 4500);
  },
  dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),

  async saveProfile(p) {
    const saved = await api.saveProfile(p);
    try {
      await db.profiles.put(saved);
    } catch {
      /* sem IndexedDB */
    }
    set((s) => ({
      profiles: s.profiles.some((x) => x.id === saved.id)
        ? s.profiles.map((x) => (x.id === saved.id ? saved : x))
        : [...s.profiles, saved],
    }));
    get().toast('Perfil salvo', 'success');
  },
  async removeProfile(id) {
    await api.deleteProfile(id);
    try {
      await db.profiles.delete(id);
    } catch {
      /* sem IndexedDB */
    }
    set((s) => ({ profiles: s.profiles.filter((p) => p.id !== id) }));
    get().toast('Perfil excluído', 'info');
  },
  async applyWordAction(wordId, action, value) {
    await api.applyWordAction(wordId, action, value);
    const h = await api.history('doc-img-4253');
    const reviewQueue = await api.getReviewQueue(undefined, 50);
    set({ history: h, reviewQueue });
    get().toast('Correção registrada', 'success');
  },
}));

export async function loadPages(documentId: string): Promise<OcrPage[]> {
  return api.getPages(documentId);
}
