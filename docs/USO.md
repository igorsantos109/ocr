# Uso

## Ingestão (Marco 1)

```bash
# Ingerir sem executar OCR
ocrhist processar /home/igor/Desktop/OCRENTRADA --somente-ingestao

# Ingerir e executar OCR em lote
ocrhist processar /home/igor/Desktop/OCRENTRADA --perfil automatico
ocrhist processar carta_1891.tif --perfil manuscrito --dpi 400

# PDF com camada textual usa extração direta por padrão;
# compare com OCR visual explicitamente
ocrhist processar livro_1910.pdf --engine tesseract

# Segunda execução pula o que já foi processado
ocrhist processar /home/igor/Desktop/OCRENTRADA

# Reprocessar tudo ou somente falhas
ocrhist processar /home/igor/Desktop/OCRENTRADA --forcar
ocrhist processar /home/igor/Desktop/OCRENTRADA --retry-failed

# Acompanhar o lote
ocrhist listar
ocrhist listar --status erro
ocrhist status
ocrhist status jornal_1907.pdf
```

A ingestão nunca modifica os originais: PDFs são renderizados como cópias em
`data/processamento/renderizadas/` e imagens são apenas referenciadas. Um erro
em um arquivo marca aquele documento como `erro` e o lote continua.

## OCR em lote (Marco 2)

Para cada documento, `processar`:

1. pré-processa a página segundo o perfil YAML (tons de cinza, denoise, deskew,
   CLAHE, fundo, upscale, binarização opcional) e salva a derivada em
   `data/processamento/pre_processadas/`;
2. executa o motor (Tesseract por padrão; `pdf_texto` automático para PDF
   textual; `kraken`/`ensemble` disponíveis);
3. gera linhas com recortes, confiança e texto bruto/diplomático no banco;
4. exporta `_bruto.txt`, `_diplomatico.txt`, `_nome.md` e `_nome.json` em
   `OCRSAIDA/nome_do_documento/`.

Exportar novamente sem repetir o OCR:

```bash
ocrhist exportar <ID_DOCUMENTO>
ocrhist exportar <ID_DOCUMENTO> --config configs/jornal.yaml
```

## Exportação e metricas (Marco 3)

Cada documento concluído recebe, em `OCRSAIDA/nome_do_documento/`:

- `*_bruto.txt` e `*_diplomatico.txt`;
- `*.md` e `*.json` (auditoria);
- `*.tsv`, `*.hocr` e `*_page.xml` (PAGE-XML);
- `*_relatorio.html` e `baixa_confianca.csv` (fila de revisão);
- `overlays/` com caixas numeradas;
- `*_pesquisavel.pdf` (OCRmyPDF se instalado; fallback local).

Medir qualidade com CER/WER (taxa de erro menor é melhor; não é acurácia):

```bash
ocrhist avaliar \
  --referencia data/treinamento/teste/referencia.txt \
  --hipotese output/OCRSAIDA/documento/documento_diplomatico.txt \
  --normalizar --relatorio avaliacao.json
```

## Revisão humana e auditoria (Marco 4)

```bash
# Ver a fila ordenada por incerteza
ocrhist revisar
ocrhist revisar --status alta --limite 50

# Corrigir uma linha, gravando trilha de auditoria
ocrhist corrigir ID_DA_LINHA --texto "Illm. Snr. Presidente" --usuario ana

# Marcar uma linha
ocrhist marcar ID_DA_LINHA revisada
ocrhist marcar ID_DA_LINHA ilegivel --observacao "mancha impede leitura"
ocrhist marcar ID_DA_LINHA treinamento

# Linhas prioritárias por aprendizado ativo
ocrhist selecionar --limite 100
```

Toda correção registra anterior/corrigido, origem (`humana`, `regra` ou
`llm_sugerido`), usuário opcional, data e observação. **Corrigir nunca altera o
texto bruto**, apenas o diplomático; o status `treinamento` sinaliza linhas
revisadas para exportação de ground truth.

A interface local também permite corrigir e marcar linhas com auditoria.

## Dataset de linhas (Marco 4)

```bash
# Criar a estrutura de uma coleção
ocrhist dataset iniciar cartas_1891 --raiz data/treinamento

# Exportar linhas marcadas como treinamento
ocrhist dataset exportar data/treinamento/cartas_1891/ground_truth

# Validar e dividir sem vazamento
ocrhist dataset validar data/treinamento/cartas_1891/ground_truth
ocrhist dataset dividir data/treinamento/cartas_1891/ground_truth \
  --destino data/treinamento/cartas_1891
```

A divisão agrupa por documento (ou escrevente com `--grupo escrevente`) e nunca
mistura linhas do mesmo grupo entre treino, validação e teste. Detalhes em
`docs/TREINAMENTO_HTR.md`.

## Estação de revisão local (GUI)

```bash
ocrhist web --host 127.0.0.1 --port 7860
# ou
bash scripts/executar_web.sh
```

Interface de página única embarcada (sem dependências externas, funciona
offline e no celular), com identidade OCR Studio (fluxo ABBYY × paleta
Google Colab: fundo branco, laranja `#F9AB00`, azul `#1A73E8`). Do topo à base:

- barra superior com abas **Converter | Meus documentos**, busca, filtro,
  selo LLM e contadores;
- barra de ferramentas (**Enviar arquivos**, **Reprocessar** que recarrega do
  banco, **Baixar tudo** que exporta o ground truth) + progresso fino laranja;
- stepper **1 Enviar → 2 Configurar → 3 Converter e baixar** (derivado do
  banco: etapa 1 conclui com documentos, etapa 3 com fila zerada);
- zona de upload funcional: **clique para selecionar** (rótulo nativo, abre o
  seletor em qualquer navegador) ou **arraste e solte** PDF/JPG/PNG/TIFF; a
  lista mostra os pendentes e **Enviar e reconhecer** envia via
  `POST /api/upload` para `<entrada>/upload_web/`. Com **Executar OCR após
  enviar** ligado, o OCR entra na **fila em segundo plano** (sem travar a
  página) com **barra de progresso, log por página e botão Cancelar**;
  desmarque para só ingerir. O seletor de **motor** (`automático` = primeiro
  disponível entre paddleocr/tesseract/kraken) degrada sozinho quando o
  Tesseract está ausente. Limites: 50MB/arquivo, 64MB/envio, 20 arquivos;
  tipos fora de PDF/PNG/JPG/TIFF são recusados;
- **ações por documento**: ⟳ reconhece/reprocessa (com `retry_failed`, recupera
  documentos em erro), ⬇ baixa os produtos exportados (TXT/MD/JSON/PAGE-XML/
  PDF pesquisável via `/api/download`), 👁 abre a revisão;
- configuração (idiomas, formatos, opções) salva como **preferência local do
  navegador**; o lote continua usando o YAML e `--perfil`;
- **fila de documentos em tabela** (Miniatura | Nome | Páginas | Tipo |
  Status | Ações) com pills Na fila/Processando/Concluído/Erro, virando
  cartões abaixo de 900px;
- painel inicial com cartões (documentos, fila,
baixa confiança, revisadas, correções), distribuição por status e a **fila
prioritária global** com botão "Abrir" que salta direto para a linha.

A área do documento oferece:

- **visor de página** com camadas original / pré-processada / overlay, zoom
  (−/+/ajustar) e **caixas clicáveis** sincronizadas com a lista de linhas;
- faixa de miniaturas das páginas e navegação por setas;
- editor da linha com **recorte**, selo de confiança, bruto e normalizado em
  dobráveis, diplomático editável (detector de alteração + `Ctrl+Enter`);
- ações **Salvar e marcar revisada**, **Ilegível**, **Treinamento** e
  **sugestões LLM** (ver/pedir) em bloco separado — nunca alteram texto;
- histórico auditado por linha e aba **Fila do documento**;
- exportação das linhas de treinamento para `data/treinamento/<colecao>/`.

Atalhos: `↑`/`↓` linhas, `←`/`→` páginas, `Ctrl+Enter` salvar, `1` revisada,
`2` ilegível, `3` treinamento. Por segurança, só escuta em
`127.0.0.1`/`localhost`; expor na rede exige `--expor-rede` explícito.

## Revisor LLM local (Marco 6, `suggest_only` sempre)

O LLM é **opcional, local e somente sugestão**: nunca substitui o texto bruto
nem o diplomático. Neste host não há Ollama; o revisor fala com o servidor
local já ativo em **:8081 (Qwen3-8B)** via API OpenAI-compatível — `configs/web_local.yaml`
já vem assim (botão **Sugerir** da GUI funciona; ~20–30s por linha em CPU).
Configuração em `configs/llm_local.yaml`:

```yaml
llm:
  enabled: false
  provider: ollama
  model: qwen2.5:7b-instruct
  base_url: http://127.0.0.1:11434
  timeout_seconds: 120
  mode: suggest_only
```

```bash
# uma linha (sem confirmação extra)
ocrhist sugerir --linha ID_DA_LINHA --usuario ana

# algumas linhas: exige confirmação explícita do lote
ocrhist sugerir --linha ID1 --linha ID2 --confirmar-lote

# primeiras N linhas da fila de um documento
ocrhist sugerir --documento ID_DOC --limite 5 --confirmar-lote
```

Cada sugestão é validada (schema Pydantic) e registrada em `correcoes` com
origem `llm_sugerido`, guardando prompt, resposta, modelo e data — erros de
rede ou JSON inválido falham só naquela linha, sem interromper o lote.

## Paddle VL — motor experimental (requer servidor local)

A GUI e a CLI expõem o motor interno `paddle_vl`, que usa a API OpenAI do
`llama-server` para visão de página. Neste host, o perfil configurado usa
**Qwen3-VL-8B-Instruct em :8082**; o nome do adaptador não deve ser lido como
promessa de que o GGUF instalado seja o PaddleOCR-VL-1.6 original. Não há
pacote `paddleocr`, downloads automáticos ou tráfego para a nuvem.

```bash
# 1. Suba o servidor visual (requer GGUF + mmproj locais)
bash scripts/servidor_qwen3vl.sh --port 8082
.venv/bin/ocrhist diagnosticar | grep PaddleOCR-VL

# 2. Transcreva (usa configs/paddle_vl.yaml ou flags)
ocrhist processar carta_1891.tif --engine paddle_vl
ocrhist processar carta_1891.tif --config configs/paddle_vl.yaml
ocrhist processar lote/ --engine paddle_vl --vl-url http://127.0.0.1:8082
```

Na GUI, escolha **Paddle VL (visão de página)** no seletor de motor. O painel exibe
endpoint, modelo e disponibilidade. Quando o servidor está desligado, aparece o
botão **Iniciar servidor visual**; a GUI inicia o `llama-server` local sem
bloquear a página, acompanha o carregamento e permite pará-lo depois. O botão
**Atualizar motores** força uma nova sondagem sem recarregar a GUI. Cada página
vira um bloco único sem confiança por linha — revisão visual obrigatória — e o
motor recusa servidores com modelo sem visão.

Limites honestos: o VLM não retorna caixas, então cada página vira **uma linha
em bloco único com confiança nula** — cai direto na fila de revisão alta e o
aviso fica registrado. O motor **recusa** servidores com modelo sem visão
(ex. um LLM de texto na mesma porta) e o diagnóstico mostra `AVISO` nomeando
o modelo servido. Sem servidor VL ativo, as páginas são marcadas como erro
com mensagem acionável e o lote com outros motores segue normal.

## olmOCR — motor incorporado (servidor visual local)

O motor `olmocr` está disponível na CLI e na GUI. Ele prioriza ordem natural de
leitura e saída em Markdown pelo caminho local `llama-server` + GGUF + mmproj,
na porta padrão **8082**. Neste host, `configs/olmocr.yaml` usa o Qwen3-VL
local como backend compatível; para usar o GGUF oficial olmOCR-2-7B, ajuste o
modelo no YAML e use `scripts/servidor_olmocr.sh`.

Na GUI, selecione **olmOCR** no seletor de motor. O painel exibe o modelo e
endpoint efetivos; o botão **Iniciar olmOCR** inicia o servidor visual adequado
e o botão **Atualizar motores** acompanha quando ele fica pronto.

```bash
# 1. Alternativa pela linha de comando (requer GGUF + mmproj locais)
bash scripts/servidor_olmocr.sh --port 8082
.venv/bin/ocrhist diagnosticar | grep olmOCR

# 2. Transcreva (usa configs/olmocr.yaml ou flags)
ocrhist processar carta_1891.tif --engine olmocr
ocrhist processar carta_1891.tif --config configs/olmocr.yaml
ocrhist processar lote/ --engine olmocr --vl-url http://127.0.0.1:8082
```

Valem os mesmos limites honestos do `paddle_vl` (bloco único, confiança nula,
recusa de modelo sem visão), mais um: aqui há **uma passada com
`temperature=0`** — o toolkit oficial aplica "ancoragem" (várias amostragens),
portanto a revisão humana continua obrigatória.