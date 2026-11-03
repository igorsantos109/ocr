/** Dados fictícios realistas: coleção "Jornais do Rio de Janeiro — 1927".
 *  Grafias históricas usadas apenas como material de teste (sem correção
 *  automática): hontem, approvado, illuminção, districto. */

import type {
  LogEntry,
  OcrCollection,
  OcrLine,
  OcrPage,
  OcrProfile,
  OcrWord,
  QueueDocument,
  ReviewItem,
} from '../types/ocr';

const now = new Date().toISOString();

/** Motores efetivamente disponíveis no host (mock espelha a máquina atual). */
export const AVAILABLE_ENGINES = ['tesseract', 'paddleocr', 'easyocr', 'kraken', 'deepseek_ocr2'];

export const mockCollections: OcrCollection[] = [
  {
    id: 'col-jornais-rj-1927',
    name: 'Jornais do Rio de Janeiro — 1927',
    description: 'Periódicos cariocas digitalizados: edições, suplementos e recortes.',
    createdAt: '2026-02-10T10:00:00.000Z',
    updatedAt: now,
  },
  {
    id: 'col-cartas-1891',
    name: 'Cartas manuscritas — 1891',
    description: 'Correspondência familiar para treino de HTR.',
    createdAt: '2026-03-02T10:00:00.000Z',
    updatedAt: now,
  },
];

export const mockProfiles: OcrProfile[] = [
  {
    id: 'impresso-moderno',
    name: 'Impresso moderno',
    description: 'Livros e textos atuais.',
    icon: 'book-open',
    builtIn: true,
    engine: 'auto',
    languages: ['pt-contemporaneo'],
    exportFormats: ['pdf', 'txt'],
    options: { deskew: true, denoise: false, clahe: false, preserveLayout: true, reviewLowConfidence: true },
  },
  {
    id: 'jornal-historico',
    name: 'Jornal histórico',
    description: 'Jornais e periódicos antigos.',
    icon: 'newspaper',
    builtIn: true,
    engine: 'auto',
    languages: ['pt-historico'],
    exportFormats: ['pdf', 'markdown'],
    options: { deskew: true, denoise: true, clahe: true, preserveLayout: true, detectTables: false, useHistoricalDictionary: true, reviewLowConfidence: true },
  },
  {
    id: 'manuscrito',
    name: 'Manuscrito',
    description: 'Cartas, atas e cadernos.',
    icon: 'pen-line',
    builtIn: true,
    engine: 'kraken',
    languages: ['pt-historico', 'latim'],
    exportFormats: ['txt', 'json'],
    options: { deskew: true, denoise: true, clahe: true, forceEngine: true, reviewLowConfidence: true },
  },
  {
    id: 'tabelas-formularios',
    name: 'Tabelas e formulários',
    description: 'Planilhas, registros e formulários.',
    icon: 'table',
    builtIn: true,
    engine: 'paddleocr',
    languages: ['pt-contemporaneo'],
    exportFormats: ['xlsx', 'tsv'],
    options: { deskew: true, preserveLayout: true, detectTables: true, detectOrientation: true, reviewLowConfidence: true },
  },
  {
    id: 'documento-danificado',
    name: 'Documento danificado',
    description: 'Manchas, rasgos, baixa qualidade.',
    icon: 'bandage',
    builtIn: true,
    engine: 'hybrid',
    languages: ['pt-historico'],
    exportFormats: ['pdf', 'txt'],
    options: { deskew: true, denoise: true, binarization: true, clahe: true, twoPass: true, reviewLowConfidence: true },
  },
  {
    id: 'personalizado',
    name: 'Personalizado',
    description: 'Perfil criado pelo usuário.',
    icon: 'sliders-horizontal',
    builtIn: false,
    engine: 'tesseract',
    languages: ['auto'],
    exportFormats: ['txt', 'json'],
    options: { deskew: true, denoise: false, reviewLowConfidence: true },
  },
];

function log(id: string, message: string, level: LogEntry['level'] = 'info'): LogEntry {
  return { id, at: now, level, message };
}

export const mockDocuments: QueueDocument[] = [
  {
    id: 'doc-jornal-png',
    name: 'jornal.png',
    collectionId: 'col-jornais-rj-1927',
    type: 'image',
    pages: 1,
    profileId: 'jornal-historico',
    engine: 'tesseract',
    status: 'completed',
    progress: 100,
    confidence: 0.91,
    pendingReview: 2,
    updatedAt: now,
    log: [log('l1', 'OCR concluído em 6,2 s'), log('l2', 'Exportados PDF pesquisável e TXT')],
  },
  {
    id: 'doc-img-4359',
    name: 'IMG_20260218_194359.jpg',
    collectionId: 'col-jornais-rj-1927',
    type: 'image',
    pages: 1,
    profileId: 'jornal-historico',
    engine: 'paddleocr',
    status: 'needs_review',
    progress: 100,
    stage: 'revisão humana',
    confidence: 0.63,
    pendingReview: 14,
    updatedAt: now,
    log: [log('l1', 'OCR concluído em 9,8 s'), log('l2', '14 trechos abaixo de 70% enviados à revisão', 'warning')],
  },
  {
    id: 'doc-img-4253',
    name: 'IMG_20260218_194253.jpg',
    collectionId: 'col-jornais-rj-1927',
    type: 'image',
    pages: 1,
    profileId: 'documento-danificado',
    engine: 'hybrid',
    status: 'needs_review',
    progress: 100,
    stage: 'revisão humana',
    confidence: 0.58,
    pendingReview: 17,
    updatedAt: now,
    log: [log('l1', 'Duas passagens aplicadas (binarização + CLAHE)'), log('l2', '17 trechos abaixo de 70% enviados à revisão', 'warning')],
  },
  {
    id: 'doc-suplemento-pdf',
    name: 'suplemento_literario.pdf',
    collectionId: 'col-jornais-rj-1927',
    type: 'pdf',
    pages: 8,
    profileId: 'jornal-historico',
    engine: 'auto',
    status: 'ocr',
    progress: 62,
    stage: 'OCR — página 5 de 8',
    confidence: null,
    pendingReview: 0,
    updatedAt: now,
    log: [log('l1', 'Pré-processamento concluído'), log('l2', 'OCR em andamento: página 5 de 8')],
  },
  {
    id: 'doc-ata-falha',
    name: 'ata_camara_1927_03.tif',
    collectionId: 'col-jornais-rj-1927',
    type: 'image',
    pages: 2,
    profileId: 'manuscrito',
    engine: 'kraken',
    status: 'failed',
    progress: 35,
    stage: 'OCR',
    confidence: null,
    pendingReview: 0,
    updatedAt: now,
    error: 'Falha recuperável: motor Kraken indisponível no mock — tente novamente com Tesseract.',
    log: [log('l1', 'Pré-processamento concluído'), log('l2', 'Motor Kraken indisponível no mock', 'error')],
  },
];

/** Página de revisão com caixas sincronizadas (doc-img-4253, página 1). */
function word(
  id: string,
  text: string,
  confidence: number,
  x: number,
  y: number,
  w: number,
  h: number,
  status: OcrWord['status'] = 'pending',
  alternatives?: OcrWord['alternatives'],
): OcrWord {
  return {
    id,
    pageId: 'pag-4253-1',
    lineId: 'lin-4253-1',
    text,
    originalText: text,
    confidence,
    boundingBox: { x, y, width: w, height: h },
    status,
    alternatives,
  };
}

const reviewLine1: OcrLine = {
  id: 'lin-4253-1',
  pageId: 'pag-4253-1',
  number: 1,
  boundingBox: { x: 60, y: 90, width: 680, height: 44 },
  confidence: 0.58,
  status: 'pending',
  words: [
    word('w1', 'O', 0.97, 60, 90, 28, 44, 'accepted'),
    word('l1w2', 'jornal', 0.88, 96, 90, 110, 44, 'accepted'),
    word('l1w3', 'de', 0.95, 214, 90, 44, 44, 'accepted'),
    word('l1w4', 'hontem', 0.52, 266, 90, 130, 44, 'pending', [
      { text: 'hontem', confidence: 0.52, source: 'ocr' },
      { text: 'ontem', confidence: 0.41, source: 'dicionário moderno' },
    ]),
    word('l1w5', 'approvado', 0.47, 404, 90, 170, 44, 'pending', [
      { text: 'approvado', confidence: 0.47, source: 'ocr' },
      { text: 'aprovado', confidence: 0.44, source: 'dicionário moderno' },
    ]),
  ],
};

const reviewLine2: OcrLine = {
  id: 'lin-4253-2',
  pageId: 'pag-4253-1',
  number: 2,
  boundingBox: { x: 60, y: 150, width: 680, height: 44 },
  confidence: 0.71,
  status: 'pending',
  words: [
    word('l2w1', 'pela', 0.93, 60, 150, 80, 44, 'accepted'),
    word('l2w2', 'illuminção', 0.61, 148, 150, 190, 44, 'pending', [
      { text: 'illuminção', confidence: 0.61, source: 'ocr' },
      { text: 'iluminação', confidence: 0.55, source: 'dicionário moderno' },
    ]),
    word('l2w3', 'do', 0.96, 346, 150, 44, 44, 'accepted'),
    word('l2w4', 'district', 0.38, 398, 150, 140, 44, 'pending', [
      { text: 'district', confidence: 0.38, source: 'ocr' },
      { text: 'districto', confidence: 0.35, source: 'ocr' },
      { text: 'distrito', confidence: 0.31, source: 'dicionário moderno' },
    ]),
    word('l2w5', 'o', 0.9, 546, 150, 28, 44, 'accepted'),
  ],
};

export const mockPages: OcrPage[] = [
  {
    id: 'pag-4253-1',
    documentId: 'doc-img-4253',
    number: 1,
    width: 800,
    height: 1000,
    status: 'done',
    lines: [reviewLine1, reviewLine2],
  },
];

export const mockReviewQueue: ReviewItem[] = [
  { id: 'rv1', documentId: 'doc-img-4253', documentName: 'IMG_20260218_194253.jpg', pageId: 'pag-4253-1', page: 1, lineId: 'lin-4253-2', line: 2, text: 'district', confidence: 0.38, severity: 'high', kind: 'low_confidence', status: 'pending' },
  { id: 'rv2', documentId: 'doc-img-4253', documentName: 'IMG_20260218_194253.jpg', pageId: 'pag-4253-1', page: 1, lineId: 'lin-4253-1', line: 1, text: 'approvado', confidence: 0.47, severity: 'high', kind: 'possible_error', status: 'pending' },
  { id: 'rv3', documentId: 'doc-img-4253', documentName: 'IMG_20260218_194253.jpg', pageId: 'pag-4253-1', page: 1, lineId: 'lin-4253-1', line: 1, text: 'hontem', confidence: 0.52, severity: 'medium', kind: 'possible_error', status: 'pending' },
  { id: 'rv4', documentId: 'doc-img-4253', documentName: 'IMG_20260218_194253.jpg', pageId: 'pag-4253-1', page: 1, lineId: 'lin-4253-2', line: 2, text: 'illuminção', confidence: 0.61, severity: 'medium', kind: 'low_confidence', status: 'pending' },
  { id: 'rv5', documentId: 'doc-img-4359', documentName: 'IMG_20260218_194359.jpg', pageId: 'pag-4359-1', page: 1, lineId: 'lin-4359-3', line: 3, text: 'Bernardo', confidence: 0.66, severity: 'medium', kind: 'engine_conflict', status: 'pending' },
  { id: 'rv6', documentId: 'doc-img-4359', documentName: 'IMG_20260218_194359.jpg', pageId: 'pag-4359-1', page: 1, lineId: 'lin-4359-5', line: 5, text: '[trecho manchado]', confidence: null, severity: 'high', kind: 'illegible', status: 'pending' },
  { id: 'rv7', documentId: 'doc-jornal-png', documentName: 'jornal.png', pageId: 'pag-jornal-1', page: 1, lineId: 'lin-jornal-9', line: 9, text: 'tabela de preços', confidence: 0.69, severity: 'low', kind: 'incomplete_table', status: 'pending' },
];

export const ENGINE_LABELS: Record<string, string> = {
  auto: 'Automático',
  tesseract: 'Tesseract',
  paddleocr: 'PaddleOCR',
  kraken: 'Kraken / HTR',
  easyocr: 'EasyOCR',
  hybrid: 'Pipeline híbrido',
  deepseek_ocr2: 'DeepSeek-OCR-2 — documentos e Markdown',
};

/** O que cada motor FAZ (texto de ajuda exibido no painel e nas configurações). */
export const ENGINE_DESCRIPTIONS: Record<string, string> = {
  auto: 'Escolhe o melhor motor por página',
  tesseract: 'OCR clássico rápido para impressos nítidos',
  paddleocr: 'OCR clássico com boa detecção de layout',
  kraken: 'HTR para manuscritos e impressos históricos',
  easyocr: 'OCR leve multilíngue para fotos',
  hybrid: 'Combina motores clássicos em duas passagens',
  deepseek_ocr2: 'MoE 3,4B especializado em documentos; página inteira, sem caixas por linha · revisão obrigatória',
};

/** Motores visuais (página inteira, sem caixas por linha) × clássicos/HTR. */
export const ENGINE_GROUPS: Record<'visual' | 'classic', string[]> = {
  visual: ['deepseek_ocr2'],
  classic: ['auto', 'tesseract', 'paddleocr', 'kraken', 'easyocr', 'hybrid'],
};

/** Endpoints locais dos motores que rodam como servidor próprio (sem chamadas novas em runtime). */
export const ENGINE_ENDPOINTS: Record<string, string> = {
  deepseek_ocr2: 'http://127.0.0.1:8084',
};
