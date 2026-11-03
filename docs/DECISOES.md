# Decisões técnicas

## Marco 0 — fundação (2025)

1. **Escopo oficial:** este repositório segue a especificação do `ocr-historico-br`, com processamento local de documentos históricos. Os scripts e notebooks experimentais que já existiam na pasta de trabalho (PaddleOCR-VL/VLM) foram preservados sem integração: eles não fazem parte do Marco 0 e introduziriam uma dependência externa incompatível com a rota CPU-first Tesseract/Kraken.
2. **Python e distribuição:** o projeto requer Python 3.11 ou superior e usa um ambiente virtual local `.venv`. A instalação não baixa modelos silenciosamente; modelos e componentes opcionais serão tratados em comandos explícitos nos marcos posteriores.
3. **Configuração:** YAML é validado por Pydantic. Campos desconhecidos são permitidos para permitir evolução de perfis, mas os campos centrais (DPI, limiares e parâmetros de motor) possuem validação de tipo e limites.
4. **Banco:** SQLAlchemy cria todas as tabelas mínimas com `create_all`, operação idempotente adequada ao Marco 0. O banco padrão é `data/ocr_historico.sqlite3`; nenhum banco é criado em uma primeira execução de `setup` sem que o comando valide a configuração.
5. **Preservação:** `setup` apenas cria diretórios de entrada/saída quando `--criar-diretorios` é usado e confirmado. Nenhum arquivo de entrada é aberto para escrita neste marco.
6. **Dependências opcionais:** Kraken, OCRmyPDF, Ollama e `por_best` aparecem no diagnóstico como indisponíveis/aviso, sem transformar sua ausência em falha do diagnóstico.
7. **Diagnóstico:** é somente local e informativo. Não instala pacotes, não baixa modelos e inicializa apenas o banco configurado para verificar sua disponibilidade.
8. **CLI:** Typer é o ponto de entrada `ocrhist`, com mensagens em português e comandos somente do Marco 0 (`setup`, `diagnosticar`). Comandos de processamento serão adicionados com testes no Marco 1/2, evitando uma promessa de funcionalidade ainda não implementada.

## Marco 1 — ingestão + prévia da GUI (2025)

9. **Execução sequencial:** `processar` aceita `--workers`, mas executa em sequência neste marco; o aviso é explícito. Paralelismo real fica para os marcos de OCR, quando houver medição de contenção no SQLite.
10. **Renderização de PDF:** cada página vira um PNG em `data/processamento/renderizadas/<doc_id>/pNNNN.png`, no DPI da configuração. Imagens (inclusive TIFF multipágina) são referenciadas pelo caminho original, sem cópia, e cada quadro vira um registro de página com o número original preservado.
11. **Retomada:** documentos são deduplicados por SHA-256. Segunda execução pula o registrado; `--forcar` reingere tudo e `--retry-failed` tenta só os marcados como `erro`. Falha isolada por arquivo nunca aborta o lote.
12. **GUI prévia sem Gradio:** o painel `ocrhist web` usa só a stdlib (`http.server`), sem dependências novas e sem nada externo (funciona offline). É responsivo (grade fluida + layout de cartões no celular) e interativo (busca, filtro por status, detalhe por documento). A revisão de linhas com Gradio continua prevista no Marco 6; esta prévia é somente leitura.
13. **Bind seguro:** o servidor só escuta em `127.0.0.1`/`localhost`/`::1`; qualquer outro host exige `--expor-rede` explícito, que retorna erro claro sem ele.
14. **Alvo do mypy:** o `python_version` do mypy acompanha o interpretador de desenvolvimento (3.13), porque os stubs novos do numpy/Pillow usam sintaxe 3.12+ e quebravam a checagem com alvo 3.11. O código do projeto continua sem sintaxe pós-3.11 (`from __future__ import annotations`), mantendo compatibilidade de execução com 3.11+.

## Marco 2 — OCR impresso (2025)

15. **Tesseract por subprocesso:** o adaptador chama o binário com lista de argumentos (sem shell), idioma/OEM/PSM configuráveis, timeout de 300 s e TSV no stdout. Ausência ou falha vira `MotorIndisponivel` com orientação de instalação; não há download automático.
16. **Camadas textuais:** PDF com texto utilizável usa `pdf_texto` por padrão para preservar o texto existente; `--engine tesseract` força comparação visual. Nenhuma votação cega substitui o texto.
17. **Diplomático conservador:** somente espaços horizontais duplicados são colapsados. Grafia, acentos, abreviaturas, nomes e números não são modernizados.
18. **Persistência de OCR:** linhas e caixas são gravadas em `linhas`, com texto bruto separado do diplomático, confiança do TSV, status de revisão pendente e imagem pré-processada preservada. O JSON contém a auditoria mínima e a qualidade registrada.
19. **Sem Tesseract no host:** testes reais do binário são marcados `skip` com mensagem clara; testes de parsing TSV e pipeline usam fixture/motor simulado, nunca fingindo saída de uma execução real. No Linux do usuário, `scripts/instalar.sh` apenas sugere `tesseract-ocr`/`tesseract-ocr-por` e o comando explícito de instalação fica sob controle do usuário.

## Marco 3 — qualidade e exportação (2025)

20. **Exportadores independentes e recuperáveis:** cada produto (TSV, hOCR, PAGE-XML, HTML, CSV, overlays, PDF) é uma função pura sobre os dados do banco, chamada após o OCR; falha em um produto não interrompe o documento. `ocrhist exportar <ID>` regenera todos sem repetir o OCR.
21. **PDF pesquisável em degradação elegante:** OCRmyPDF é usado apenas quando instalado e para PDF; o fallback PyMuPDF insere o texto diplomático invisível (`render_mode=3`) sobre cada imagem de página, sem nenhuma chamada de rede.
22. **CER/WER próprios, sem API:** programação dinâmica com contagem de inserções/deleções/substituições; a CLI deixa explícito que taxa de erro não é acurácia e permite normalização configurável antes da medição.
23. **Confiança conservadora:** o motor é o sinal principal; nitidez, contraste, caracteres anormais e divergência apenas reduzem a nota. Valores fora de 0–1 são limitados e a ausência de confiança do motor continua exigindo revisão.

## Marco 4 — avaliação, correção e dataset (2025)

24. **Correção auditável:** uma correção humana atualiza somente `texto_diplomatico`, preserva `texto_bruto` e cria registro em `correcoes` com anterior, corrigido, origem, usuário, data e observação.
25. **Fila:** `revisar` considera apenas linhas com `exige_revisao`; confiança ausente é priorizada antes de notas menores, sem declarar certeza histórica.
26. **Seleção ativa:** a pontuação é `1 - confiança` (ou 1 sem confiança); não inventa texto nem substitui julgamento visual.
27. **Ground truth:** somente linhas explicitamente marcadas `treinamento` são exportadas. Imagem e transcrição são copiadas para a coleção e o manifesto é idempotente por identificador.
28. **Splits:** grupos por documento (padrão) ou escrevente são ordenados deterministicamente e nunca divididos entre treino, validação e teste. Com poucas coleções, um conjunto pode ficar vazio; isso é reportado pela contagem, não preenchido artificialmente.
29. **GUI:** endpoints POST de correção/marcação usam a mesma camada de serviço da CLI e, portanto, a mesma auditoria. O bind permanece local por padrão.

## Marco 5 — manuscritos e HTR (2025)

30. **Segmentação de linhas:** `layout.linhas.segmentar_linhas` é o ponto único. Quando Kraken + modelo `blla.mlmodel` estão presentes, usa `kraken.blla.segment` (CPU); caso contrário, aplica fallback OpenCV por projeção horizontal + contornos, sempre com `metodo="fallback"` para penalizar confiança e forçar revisão. Nunca levanta; página sem linhas detectadas vira linha única com aviso.
31. **Kraken degradável:** `KrakenEngine` só opera se `kraken` importável e `.mlmodel` local existir; nunca baixa modelo. `pipeline.processar_documentos` detecta `kraken` indisponível no perfil `manuscrito` e, se Tesseract estiver disponível, faz fallback com `fallback_aviso` registrado em `execucoes.parametros_json` e log `warning`. Sem ambos, marca erro com mensagem acionável.
32. **Pré-processamento manuscrito:** `configs/manuscrito.yaml` mantém `binarizacao: false` por padrão (exigência da especificação). `deskew`, `clahe`, `remover_fundo` e `upscale: 1.5` preservam traço manuscrito.
33. **Treino/fine-tuning:** `treinamento.kraken_train.preparar_treino` apenas monta o comando (`ketos train` ou `kraken train`) em CPU, validando o manifesto; `executar_treino` exige binário no PATH e grava `.log`. `treinar_avaliar` usa CER/WER próprios sobre o conjunto de teste separado, sem vazamento (splits já garantem separação por documento/escrevente).
34. **Versões:** `versoes.jsonl` registra `id, modelo_path, dataset, epocas, cer, wer` de forma append-only, sem sobrescrever modelos.
35. **PAGE-XML e auditoria:** cada linha segmentada vira `<TextLine>` com `Coords` e `Unicode`; fallback ainda gera PAGE-XML auditável, permitindo inspeção mesmo sem Kraken.

## Marco 6 — interface e LLM local (2025)

36. **LLM somente sugestão:** `posprocessamento.llm_revisor` opera com `llm.enabled=false` por padrão; `ocrhist sugerir` recusa sem o flag e exige `--confirmar-lote` para >1 linha (máx. 20/call). O endpoint local (Ollama `/api/generate`, depois OpenAI-local `/v1/chat/completions`) é chamado via stdlib `urllib`, sem nova dependência. A resposta passa por `_extrair_json` (remove cercas ```json) e validação Pydantic `SugestaoLLM` (`extra=forbid`, `confianca` 0–1); erro de rede ou JSON inválido falha só na linha, sem abortar o lote.
37. **Auditoria sem mutação:** cada sugestão gera um registro `correcoes` com `origem=llm_sugerido` e `tipo_correcao=sugestao_llm`, guardando prompt, resposta bruta, modelo, base_url e data na observação, além de log em `data/processamento/cache/llm/<linha_id>.json`. O texto diplomático e o bruto permanecem intactos; a confirmação é sempre humana (CLI `corrigir` ou botão web).
38. **Web sem dependências novas:** o painel continua stdlib `http.server` + Pillow (já obrigatória) para thumbnails: `GET /api/pagina/imagem?tipo=original|pre|overlay` gera overlay em memória (caixas escaladas) e `GET /api/linha/imagem` serve o recorte salvo ou deriva do bbox + margem de 4px. `GET /api/linha` expõe bruto/diplomático/normalizado, sugestões e histórico; `GET /api/revisao` aceita `status`, `q` e `baixa=1`. `POST /api/sugerir` respeita `llm.enabled` e `POST /api/exportar-dataset` reutiliza `iniciar_dataset` + `exportar_linhas_revisadas`.
39. **Diagnóstico honesto:** `Ollama` informa `desabilitado` quando `llm.enabled=false`; quando ativado sem pacote, vira `AVISO` explicando que o revisor usa HTTP stdlib. Nova linha `LLM` resume modo `suggest_only`.
40. **Lint pragmático:** o template HTML/JS embarcado em `web/app.py` usa `# ruff: noqa: E501` no topo do arquivo, pois quebrar strings JS prejudicaria a manutenção; o Python do projeto segue o limite de 120 colunas.

## PaddleOCR-VL — motor experimental local (2026)

41. **Sem pacote `paddleocr`, sem download:** o adaptador `paddle_vl` fala com o `llama-server` local via API OpenAI-compatível (stdlib `urllib` + Pillow, zero dependência nova). Nada é baixado; o GGUF precisa estar em `/home/igor/ia-sh/models/PaddleOCR-VL-1.6/` e o servidor é subido por `scripts/servidor_vl.sh` (o `start_vlm_server.sh` antigo foi preservado intacto).
42. **Sem caixas inventadas:** o endpoint de chat do VLM não retorna coordenadas; o resultado é UMA linha cobrindo a página, com `confianca=None` (fila alta) e aviso explícito. Caixas proporcionais fabricadas violariam a §20 e a auditoria PAGE-XML.
43. **Honestidade de modelo:** antes de transcrever, o motor confere `/v1/models`; servidor com modelo sem visão (ex. Qwen/DeepSeek de texto, hoje nas portas 8080/8081) é recusado com mensagem que nomeia o modelo servido. O `diagnosticar` aplica a mesma checagem (OK só com VL; AVISO nomeando o modelo caso contrário). Portas 8080/8081 já ocupadas por LLMs de texto foram a prova real dessa necessidade.
44. **Imagem colorida original:** o pipeline pula o pré-processamento em cinza para `paddle_vl` (mancha vs. tinta se distingue em cor). `configs/paddle_vl.yaml` documenta que seu bloco `preprocessamento` é ignorado.
45. **Interface estável:** `RecognitionConfig` ganhou `base_url`/`timeout_segundos` com defaults (motores antigos ignoram); o pipeline usa `available_com_config` quando o motor oferece, sem quebrar os demais. Flags `--vl-url`/`--vl-modelo` e seção `paddlevl:` no YAML permitem apontar outro servidor/modelo.

## GUI — estação de revisão (2026)

46. **Sem dependência nova:** o frontend é HTML+CSS+JS embarcado em `web/interface.py`, sem CDN nem framework — funciona offline e mantém o bind local. O JS passou em `node --check`; o backend continua stdlib + Pillow.
47. **Dois endpoints de apoio:** `GET /api/resumo` (agregados do painel) e `GET /api/pagina` (página + linhas com caixas e estado). `GET /api/revisao` passou a incluir `documento_id`/`documento` para o salto direto da fila global.
48. **Sem caixa inventada na GUI:** o SVG do visor usa as caixas reais do banco (`viewBox` nas dimensões da página); zoom é só CSS, sem recalcular coordenadas. Toda ação (corrigir/marcar/sugerir/exportar) reutiliza os mesmos serviços auditados da CLI.
49. **Upload drag-and-drop real:** `POST /api/upload` com parser multipart próprio em `web/upload.py` (só stdlib — o `cgi` foi removido no Python 3.13). Nomes passam por `nome_seguro` (NFKD, confinamento, 120 chars); extensões validadas contra `EXTENSOES_SUPORTADAS` antes de tocar o disco; escrita com `xb` + comparação de conteúdo (idempotente, tolera corrida de nome); ingestão escopada a `<entrada>/upload_web/` (nunca revarre a entrada inteira); 413 precoce por `Content-Length` sem ler o corpo. O frontend envia `FormData` com flag `processar` (agora enfileira, ver §50). `OSError` em mkdir/escrita/ingestão responde JSON 500/por-arquivo em vez de matar a conexão (regressão do "Failed to fetch" travada por teste).
50. **OCR em segundo plano com fallback de motor:** `resolver_engine` (`reconhecimento/factory.py`) escolhe o primeiro disponível (paddleocr → tesseract → kraken) e `_processar_um` degrada com `fallback_aviso` auditado em `execucoes` — Tesseract ausente não é mais erro fatal. `web/trabalho.py` executa um lote por vez em thread daemon com `progresso` por documento/página, percentual, log e cancelamento cooperativo; a GUI sonda `GET /api/trabalho` a cada 800ms. `POST /api/processar` (409 se ocupado), `POST /api/cancelar`, `GET /api/motores`, `GET /api/produtos` + `GET /api/download` (confinado à pasta de saída, sem traversal). O seletor de arquivos é `<label for>` + input sr-only — `hidden` bloqueava o diálogo em alguns navegadores.
51. **olmOCR como segundo VLM opcional:** `reconhecimento/olmoc_engine.py` espelha `paddle_vl` (mesma API OpenAI-compatível, mesma honestidade: bloco único, `confianca=None`, recusa de modelo sem visão via `/v1/models`). Diferenças: prompt pede Markdown em ordem de leitura (ponto forte do modelo), porta padrão 8082, seção `olmocr:` no YAML, `configs/olmocr.yaml`, `scripts/servidor_olmocr.sh` (GGUF + mmproj locais, nada baixado) e linha `olmOCR` no diagnóstico. Passada única com `temperature=0` — sem a ancoragem do toolkit oficial, revisão obrigatória. Fora do `auto`/fallback: VLM exige servidor explícito.
52. **LLM funcional sem Ollama + fim do toast repetido:** o revisor tenta Ollama e cai para OpenAI-local, então `configs/web_local.yaml` aponta para o Qwen3-8B já servido em :8081 (`suggest_only` mantido). Três ajustes de compatibilidade com modelos de raciocínio: `temperature=0` + `max_tokens=1024` no corpo do chat, sufixo `/no_think` para modelos Qwen3 (resposta em ~5s em vez de ~30s, probado), remoção de blocos `<think>` antes do parse e normalização do campo `tipo` (acentos/variações → enum). **PaddleOCR clássico verificado funcional** (transcreve corretamente); o que "não funcionava" era o `paddle_vl` selecionado com modelo de texto na porta — agora `listar_motores` usa `available_com_config` e a GUI desabilita a opção com o motivo ("servidor ativo com modelo sem visão"). Toast de conclusão com assinatura (notifica 1 vez) e `iniciarSondagem()` elimina intervalos empilhados.
