/** Tipos centrais do OCR Studio V2. Espelham o backend Python atual
 *  (/api/documentos, /api/revisao, /api/pagina, /api/linha) e estendem para
 *  coleções, perfis, fila e eventos de revisão da V2. */

export type DocumentStatus =
  | 'draft'
  | 'queued'
  | 'preprocessing'
  | 'ocr'
  | 'layout_analysis'
  | 'exporting'
  | 'completed'
  | 'needs_review'
  | 'failed'
  | 'cancelled';

export type WordStatus =
  | 'pending'
  | 'accepted'
  | 'edited'
  | 'illegible'
  | 'historical'
  | 'proper_noun'
  | 'abbreviation'
  | 'ignored'
  | 'training';

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface OcrWord {
  id: string;
  pageId: string;
  lineId: string;
  text: string;
  originalText: string;
  confidence: number;
  boundingBox: BoundingBox;
  status: WordStatus;
  alternatives?: Array<{ text: string; confidence: number; source: string }>;
}

export interface OcrLine {
  id: string;
  pageId: string;
  number: number;
  boundingBox: BoundingBox;
  words: OcrWord[];
  status: WordStatus;
  confidence: number | null;
}

export interface OcrPage {
  id: string;
  documentId: string;
  number: number;
  width: number;
  height: number;
  status: 'pending' | 'processing' | 'done' | 'error';
  imageUrl?: string;
  lines: OcrLine[];
}

export type OcrEngineId = 'auto' | 'tesseract' | 'paddleocr' | 'kraken' | 'easyocr' | 'hybrid' | 'deepseek_ocr2';
export type ExportFormatId = 'docx' | 'pdf' | 'txt' | 'tsv' | 'xlsx' | 'markdown' | 'json' | 'alto';

export interface OcrProfile {
  id: string;
  name: string;
  description: string;
  icon: string;
  builtIn: boolean;
  engine: OcrEngineId;
  languages: string[];
  exportFormats: ExportFormatId[];
  options: Record<string, boolean>;
}

export interface OcrCollection {
  id: string;
  name: string;
  description: string;
  createdAt: string;
  updatedAt: string;
}

export interface QueueDocument {
  id: string;
  name: string;
  collectionId: string;
  type: 'pdf' | 'image';
  pages: number;
  estimatedPages?: number;
  profileId: string;
  engine: OcrEngineId;
  status: DocumentStatus;
  progress: number;
  stage?: string;
  confidence: number | null;
  pendingReview: number;
  updatedAt: string;
  error?: string;
  log: LogEntry[];
}

export interface ReviewItem {
  id: string;
  documentId: string;
  documentName: string;
  pageId: string;
  page: number;
  lineId: string;
  line: number;
  text: string;
  confidence: number | null;
  severity: 'low' | 'medium' | 'high';
  kind:
    | 'low_confidence'
    | 'possible_error'
    | 'engine_conflict'
    | 'illegible'
    | 'incomplete_table';
  status: WordStatus;
}

export interface RevisionEvent {
  id: string;
  wordId?: string;
  lineId?: string;
  documentId: string;
  action: 'accepted' | 'edited' | 'illegible' | 'historical' | 'training' | 'proper_noun' | 'abbreviation';
  previousValue?: string;
  nextValue?: string;
  createdAt: string;
  actor: string;
}

export interface LogEntry {
  id: string;
  at: string;
  level: 'info' | 'warning' | 'error';
  message: string;
}

export interface ProcessingSnapshot {
  state: 'idle' | 'running' | 'paused' | 'done' | 'error' | 'cancelled';
  message: string;
  percent: number;
  documentsTotal: number;
  documentsDone: number;
  pagesOk: number;
  pagesError: number;
  reviewPending: number;
  avgSecondsPerPage: number;
  log: string[];
}

export interface EngineInfo {
  id: string;
  available: boolean;
  reason: string;
}

export interface LlmState {
  enabled: boolean;
  model: string;
}
