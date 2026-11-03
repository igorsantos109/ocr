# Arquitetura

O pacote `ocr_historico` separa configuração, diagnóstico, banco/modelos, ingestão, qualidade, reconhecimento, pós-processamento, avaliação, exportação e CLI.

- **Ingestão** descobre arquivos, calcula SHA-256 e registra documentos/páginas sem tocar nos originais.
- **Reconhecimento** usa adaptadores (Tesseract via subprocesso, PDF textual, Kraken, PaddleOCR-VL via llama-server local, ensemble) que retornam texto, caixas e confiança padronizados.
- **Qualidade** aplica o pipeline por perfil YAML e preserva as derivadas em `data/processamento/`.
- **Pós-processamento** calcula confiança combinada e prioridade da fila de revisão. No Marco 6, `llm_revisor` adiciona sugestões locais `suggest_only` (schema Pydantic, auditoria em `correcoes` com origem `llm_sugerido`), sem mutar texto.
- **Web** (`web/app.py`, Marco 6) serve painel stdlib + Pillow com imagens/overlays/recortes sob demanda, três camadas de texto, filtros e exportação de ground truth; `POST /api/sugerir` e `POST /api/exportar-dataset` reutilizam os mesmos serviços da CLI.
- **Avaliação** mede CER/WER com programação dinâmica, sem API externa.
- **Exportação** gera produtos auditáveis, recuperáveis via `ocrhist exportar`, todos em `OCRSAIDA/nome/`.
- **Revisão** (`revisao.py`) prioriza a fila, grava correções na tabela `correcoes` sem alterar texto bruto, e alimenta conjuntos de treinamento.
- **Seleção ativa** ordena linhas por incerteza (confiança ausente primeiro).
- **Treinamento** cria datasets de linhas com `manifest.jsonl`, valida referências e divide por documento/escrevente sem vazamento. No Marco 5, `kraken_train` prepara `ketos train`/`kraken train` em CPU e avalia no split de teste separado, registrando versões em `versoes.jsonl`.
- **Layout/segmentação** (`layout.linhas`) isola a detecção de linhas manuscritas: Kraken blla quando disponível, fallback OpenCV por contornos caso contrário, sempre com `metodo` auditável.
- **VLM experimental** (`reconhecimento.paddle_vl_engine`) transcreve a página colorida original via servidor local, sem caixas inventadas (bloco único, confiança nula, revisão obrigatória) e com checagem de modelo em `/v1/models` antes de transcrever.

A CLI é deliberadamente fina: valida configuração e delega as etapas a módulos testáveis. Componentes opcionais (Kraken, OCRmyPDF, Ollama, GPU) não são dependências do fluxo básico e são informados no diagnóstico sem falhar. O `diagnosticar` também lista modelos `.mlmodel` locais em `data/modelos/kraken/`.
