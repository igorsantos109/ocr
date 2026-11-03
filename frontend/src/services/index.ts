import { API_MODE, type OcrApi } from './api';
import { liveApi } from './liveApi';
import { mockApi } from './mockApi';

/** Ponto único de acesso à API (mock padrão, live via VITE_API_MODE=live). */
export const api: OcrApi = API_MODE === 'live' ? liveApi : mockApi;
export { mockApi, liveApi, API_MODE };
export { subscribeProcessing } from './mockApi';
