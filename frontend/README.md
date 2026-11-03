# OCR Studio V2 — frontend local

Painel web do `ocr-historico-br`: upload → configuração → fila → revisão
humana → exportação. React + TypeScript + Vite, Tailwind v4, Radix UI,
lucide-react, Zustand + Dexie (IndexedDB), React Router, Zod.

## Executar localmente

Pré-requisito: Node 20+. Neste host o npm exige que `npm_config_allow_scripts`
do ambiente seja removido (o harness injeta um valor incompatível com o npm 11):

```bash
cd frontend
export NPM_CONFIG_CACHE=/home/igor/ia-sh/OCR/.deps/npm-cache
env -u npm_config_allow_scripts npm install   # uma vez (.npmrc já ignora postinstall scripts)
env -u npm_config_allow_scripts npm run dev   # http://localhost:5173
env -u npm_config_allow_scripts npm run build # dist/ (tsc + bundle)
env -u npm_config_allow_scripts npm run preview
```

## Modos de API

| Modo | Variáveis | Comportamento |
|---|---|---|
| `mock` (padrão) | — | Dados fictícios + progressão simulada, 100% offline |
| `live` | `VITE_API_MODE=live`, `VITE_API_BASE=http://127.0.0.1:7861` | Lê o backend Python real; coleções/perfis seguem locais |

O `vite.config.ts` já proxya `/api` para `:7861` no `dev`.

## Estrutura

```
src/
  app/        router.tsx, providers.tsx
  components/ layout/ upload/ ocr/ queue/ review/ common/
  pages/      DashboardPage, CollectionsPage, CollectionDetailPage,
              DocumentsPage, DocumentReviewPage, SettingsPage
  store/      useOcrStore.ts (Zustand + Dexie)
  services/   api.ts (contrato), mockApi.ts, liveApi.ts, index.ts
  db/         index.ts (Dexie: collections, profiles, revisions)
  types/      ocr.ts
  data/       mockDocuments.ts (coleção Jornais do RJ — 1927)
  lib/        utils.ts
```

## Pontos de integração (backend Python atual → FastAPI futura)

- `liveApi.ts` mapeia as rotas existentes: `/api/documentos`,
  `/api/documento`, `/api/pagina`, `/api/linha`, `/api/revisao`,
  `/api/resumo`, `/api/motores`, `/api/llm-estado`, `/api/trabalho`,
  `/api/upload`, `/api/processar`, `/api/cancelar`, `/api/corrigir`,
  `/api/marcar`, `/api/produtos`, `/api/pagina/imagem`, `/api/linha/imagem`.
- Endpoints a criar no backend para paridade total: CRUD de coleções e
  perfis, fila de revisão agregada, histórico por documento, exportação por
  formato, eventos de processamento (SSE/WebSocket no lugar do polling).
- Motores reais: Tesseract, PaddleOCR, Kraken/HTR e EasyOCR entram via
  `/api/motores` + `engine` em `/api/processar` (o seletor já envia o id).
- LLM local: `/api/llm-estado` + `/api/sugerir` alimentam o chip do modelo e
  as alternativas do popover — sempre com aplicação explícita, nunca
  automática (regra preservada no mock).

## Limitações do mock atual

- Imagens das páginas são SVG simulados com as bboxes reais do mock
  (sincronização palavra↔caixa funcional, pixels ilustrativos).
- Processamento avança por timer (~3%/1,2 s); tempos e métricas de sistema
  são fictícios; sem paginação real na fila (limit 50 na revisão).
- Sem i18n além de pt-BR; tema escuro previsto, não implementado.
- Avatar do menu é composto pelas iniciais "OC" (sem anexo de imagem
  recebido); troque pelo componente de imagem quando houver o arquivo.
