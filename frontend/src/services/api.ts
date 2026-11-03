/** Contrato da API. Modo `mock` (padrão, offline) ou `live` (backend Python).
 *  Variáveis: VITE_API_MODE=mock|live, VITE_API_BASE=http://127.0.0.1:7861 */

import type {
  EngineInfo,
  LlmState,
  LogEntry,
  OcrCollection,
  OcrPage,
  OcrProfile,
  ProcessingSnapshot,
  QueueDocument,
  ReviewItem,
  RevisionEvent,
} from '../types/ocr';

export interface OcrApi {
  listCollections(): Promise<OcrCollection[]>;
  listDocuments(collectionId?: string, query?: string): Promise<QueueDocument[]>;
  getDocument(id: string): Promise<QueueDocument>;
  getPages(documentId: string): Promise<OcrPage[]>;
  getReviewQueue(documentId?: string, limit?: number): Promise<ReviewItem[]>;
  listProfiles(): Promise<OcrProfile[]>;
  saveProfile(p: OcrProfile): Promise<OcrProfile>;
  deleteProfile(id: string): Promise<void>;
  listEngines(): Promise<{ engines: EngineInfo[]; recommended: string }>;
  llmState(): Promise<LlmState>;
  processing(): Promise<ProcessingSnapshot>;
  upload(files: File[], collectionId: string): Promise<QueueDocument[]>;
  startProcessing(ids?: string[], engine?: string): Promise<void>;
  pauseProcessing(): Promise<void>;
  resumeProcessing(): Promise<void>;
  cancelProcessing(): Promise<void>;
  retryDocument(id: string): Promise<void>;
  removeDocument(id: string): Promise<void>;
  moveDocument(id: string, collectionId: string): Promise<void>;
  duplicateWithProfile(id: string, profileId: string): Promise<QueueDocument>;
  applyWordAction(wordId: string, action: RevisionEvent['action'], value?: string): Promise<void>;
  markLine(lineId: string, status: string): Promise<void>;
  history(documentId: string): Promise<RevisionEvent[]>;
  exportDocument(id: string, formats?: string[]): Promise<{ files: string[] }>;
  logs(documentId: string): Promise<LogEntry[]>;
}

export const API_MODE = (import.meta.env.VITE_API_MODE as string) || 'mock';
export const API_BASE = (import.meta.env.VITE_API_BASE as string) || 'http://127.0.0.1:7861';
