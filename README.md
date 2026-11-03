# OCR STUDIO V1 — ocr-historico-br

Aplicação **local**, auditável e CPU-first para OCR e HTR de documentos históricos brasileiros. O projeto não envia documentos ou textos para a nuvem, não exige conta/API paga e não promete uma precisão fixa: a qualidade será medida por CER/WER e por revisão humana.

> **Estado atual:** Marco 6 — interface de revisão completa e revisor LLM local `suggest_only` (desativado por padrão, auditável). Os notebooks e scripts experimentais antigos mantidos nesta pasta não fazem parte do fluxo oficial.

## O que o Marco 0 entrega

- projeto instalável em modo editável por `pyproject.toml`;
- configuração YAML validada com Pydantic;
- banco SQLite local idempotente com as tabelas mínimas de auditoria;
- CLI `ocrhist` em português com `--help`, `setup` e `diagnosticar`;
- diagnóstico que informa componentes opcionais sem falhar quando ausentes;
- testes unitários e de integração do núcleo.

## Requisitos

- Linux Mint Debian Edition (ou Linux compatível);
- Python 3.11 ou superior;
- `apt` é recomendado para Tesseract, idioma português e Poppler, mas não é executado silenciosamente pelo projeto;
- GPU não é necessária.

## Instalação rápida

```bash
cd /home/igor/ia-sh/OCR
bash scripts/instalar.sh
# opcional: criar os diretórios Desktop somente mediante opção explícita
bash scripts/instalar.sh --criar-links-desktop
```

O instalador cria `.venv`, instala o pacote e dependências do Marco 0, valida Python e executa o diagnóstico. A instalação de pacotes do sistema é apenas sugerida:

```bash
sudo apt install tesseract-ocr tesseract-ocr-por poppler-utils
```

### Motores locais sem root (este host)

Sem `sudo`, os motores foram ativados em espaço de usuário. O ambiente é
carregado com:

```bash
source scripts/ativar_modelos.sh
# Tesseract 5.5 + por (best) em .deps/tess; XDG_CACHE_HOME no workspace
```

Estado atual (`ocrhist diagnosticar`): Tesseract OK (por best),
PaddleOCR OK (RapidOCR/ONNX), Kraken instalado com segmentação `blla`
(HTR aguarda modelo treinado via `ocrhist treinar kraken`), OCRmyPDF OK,
`paddle_vl` + `olmocr` OK via Qwen3-VL-8B local:

```bash
bash scripts/servidor_qwen3vl.sh   # :8082, usado pelos perfis configs/paddle_vl.yaml e configs/olmocr.yaml
```

O LLM de revisão segue desativado (`llm.enabled=false`). Surya/Calamari
permanecem como adaptadores opcionais (requerem pacotes + modelos
explícitos e adaptador dedicado). O painel web precisa ser reiniciado após
essas mudanças para listar os motores atualizados (`bash
scripts/executar_web.sh`).

## Diagnóstico

```bash
.venv/bin/ocrhist diagnosticar
# ou
bash scripts/diagnosticar.sh
```

O comando informa Python, ambiente virtual, Tesseract/idioma `por`, Poppler, PyMuPDF, OpenCV e opcionais Kraken/OCRmyPDF/Ollama. A ausência de opcionais é esperada no Marco 0.

## Configuração e pastas

O arquivo inicial é `configs/default.yaml`. Os padrões documentais estão em `configs/`. Os caminhos padrão são `/home/igor/Desktop/OCRENTRADA` e `/home/igor/Desktop/OCRSAIDA`, mas podem ser alterados no YAML. `setup` não cria esses diretórios automaticamente:

```bash
.venv/bin/ocrhist setup
.venv/bin/ocrhist setup --criar-diretorios --sim
.venv/bin/ocrhist diagnosticar --config configs/impresso_historico.yaml
```

O banco padrão é `data/ocr_historico.sqlite3`. Nenhum conteúdo existente é apagado ou sobrescrito.

## Testes, lint e tipagem

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/mypy src/ocr_historico
```

O teste de integração usa o ambiente local e não depende de GPU. Quando Tesseract não está instalado, o diagnóstico ainda funciona e informa `INDISPONÍVEL`.

## Inventário, preservação e Docker

A varredura pode ser executada sem OCR, produzindo `inventario.json` e
`inventario.csv`:

```bash
ocrhist inventariar "$HOME/Área de trabalho/OCRENTRADA" --destino data/inventario
```

O inventário registra arquivos suportados e ignorados, caminhos relativos,
tamanho, data de modificação e SHA-256. Para preservar cópias verificadas,
ative o bloco abaixo em um YAML:

```yaml
preservacao:
  modo: copy              # none, copy ou content_addressed
  raiz: data/originais
  verificar_hash: true
```

O processamento também gera um `manifest.json` por documento, além dos
artefatos legados. A cópia preservada nunca substitui silenciosamente a
origem e é validada por hash.

Existe uma imagem CPU-first opcional:

```bash
docker compose --profile ocr build
docker compose --profile ocr run --rm ocr doctor
docker compose --profile ocr run --rm ocr processar /dados/entrada
```

O container inclui Tesseract/português, Poppler, OCRmyPDF, Ghostscript, qpdf
e unpaper. Motores pesados de layout/HTR permanecem extras opcionais e não
baixam modelos automaticamente.

### Usar PaddleOCR clássico (PP-OCR)

O PaddleOCR clássico pode ser escolhido explicitamente no YAML ou pela CLI. O extra instala `paddleocr` 3.x, `paddlepaddle` CPU e `rapidocr_onnxruntime`; o segundo é o fallback local para CPUs sem AVX2:

```bash
# instalação opcional do adaptador; não baixa modelos durante a instalação do projeto
.venv/bin/pip install -e ".[paddle]"

# rota recomendada para execução local
.venv/bin/ocrhist processar "$HOME/Área de trabalho/OCRENTRADA" \
  --config configs/paddleocr.yaml --engine paddleocr
```

`configs/paddleocr.yaml` usa português (`pt`), CPU e `allow_download: false`.
Para uma execução totalmente offline, coloque os modelos obtidos por uma ação
explícita do usuário em `data/modelos/paddleocr/` e preencha `det_model_dir`,
`rec_model_dir` e `cls_model_dir`. Para GPU disponível no backend Paddle,
configure `paddleocr.dispositivo: gpu` e instale manualmente a variante
compatível do PaddlePaddle; o programa não instala CUDA/ROCm nem baixa pesos.

O adaptador normaliza a saída PaddleOCR 2.x/3.x para caixas, texto e
confiança. Em CPUs sem AVX2, como a máquina de desenvolvimento RX 580 deste
projeto, ele usa automaticamente `rapidocr_onnxruntime` com modelos PP-OCR
locais empacotados, evitando o `SIGILL` do wheel PaddlePaddle otimizado.
Force esse backend com `OCRHIST_PADDLE_BACKEND=onnx`. Em uma máquina com AVX2,
o backend PaddlePaddle pode ser usado com `paddleocr.backend: paddle`.
Se o pacote, backend ou modelos não estiverem disponíveis, o erro informa a
instalação/configuração necessária e o texto diplomático não é inventado nem
substituído silenciosamente.

O teste da **GUI em navegador headless** é opcional: instale o extra `gui`
(Playwright) e use um Chrome/Chromium local para ativá-lo:

```bash
.venv/bin/python -m pip install -e ".[gui]"
.venv/bin/python -m pytest -m gui
```

Sem o extra ou sem navegador o teste é ignorado; a cobertura da API pelos
testes HTTP segue funcionando normalmente.

## O que o Marco 2 entrega

- `ocrhist processar` agora **executa o OCR**: pré-processa por perfil, reconhece com Tesseract (TSV com confiança e caixas) e exporta TXT/Markdown/JSON auditáveis;
- PDF textual usa extração direta por padrão; `--engine tesseract` força comparação;
- linhas com texto bruto/diplomático separados, caixas e confiança persistidas no banco;
- `ocrhist exportar <ID>` reexporta sem repetir OCR; retomada por página e por documento;
- fallback claro: sem Tesseract, o lote marca a execução como indisponível e continua.

```bash
.venv/bin/ocrhist processar /home/igor/Desktop/OCRENTRADA --perfil automatico
.venv/bin/ocrhist processar jornal_1907.pdf --perfil jornal --engine tesseract --dpi 400
.venv/bin/ocrhist listar --status erro
.venv/bin/ocrhist exportar <ID_DOCUMENTO>
.venv/bin/ocrhist web --host 127.0.0.1 --port 7860
```

## O que o Marco 3 entrega

- classificação de revisão por linha (alta/média/baixa) e CSV `baixa_confianca.csv`;
- exportação TSV, hOCR, PAGE-XML, relatório HTML e overlays numerados em `OCRSAIDA/nome/`;
- **PDF pesquisável**: usa OCRmyPDF quando instalado; fallback local PyMuPDF (sem rede);
- **CER/WER** com contagem de inserções, deleções e substituições:

```bash
ocrhist avaliar --referencia data/treinamento/teste/referencia.txt \
               --hipotese output/OCRSAIDA/documento/documento_diplomatico.txt \
               --normalizar --relatorio avaliacao.json
```

Valores menores de CER/WER significam menos erros; eles **não** são “acurácia” e não há uma precisão fixa prometida.

## O que o Marco 4 entrega

- `ocrhist revisar`, `corrigir`, `marcar` e `selecionar` para fila e seleção ativa;
- todas as correções mantêm texto anterior, corrigido, origem, usuário, data e observação na tabela `correcoes`;
- GUI local permite editar o diplomático e marcar linhas como revisadas, ilegíveis ou para treinamento;
- `ocrhist dataset iniciar/exportar/validar/dividir` para ground truth baseado em linhas;
- splits determinísticos por documento (padrão) ou escrevente, sem vazamento entre treino/validação/teste;
- 76 testes verdes anteriores + testes novos de revisão, dataset e endpoints.

```bash
ocrhist revisar --status alta
ocrhist corrigir ID_DA_LINHA --texto "Illm. Snr. Presidente" --usuario ana
ocrhist marcar ID_DA_LINHA treinamento
ocrhist dataset iniciar cartas_1891 --raiz data/treinamento
ocrhist dataset exportar data/treinamento/cartas_1891/ground_truth
ocrhist dataset validar data/treinamento/cartas_1891/ground_truth
ocrhist dataset dividir data/treinamento/cartas_1891/ground_truth --destino data/treinamento/cartas_1891
```

## O que o Marco 5 entrega

- **Segmentação de manuscritos**: `layout.linhas.segmentar_linhas` usa Kraken blla quando instalado + modelo em `data/modelos/kraken/`; caso contrário, fallback OpenCV por contornos que preserva PAGE-XML e fila de revisão;
- **Kraken HTR CPU-first**: `KrakenEngine` reconhece página/linhas quando modelo local existe; sem Kraken/modelo, `processar --perfil manuscrito --engine kraken` faz fallback para Tesseract com aviso, sem quebrar o lote;
- **Treino/fine-tuning**: `ocrhist treinar kraken DATASET [--modelo-base BASE --epocas 20 --dry-run|--executar]` prepara `ketos train`/`kraken train` em `--device cpu`, validando manifesto; `bash scripts/treinar_kraken.sh` repassa para a CLI;
- **Avaliação sem vazamento**: `ocrhist treinar avaliar MODELO TESTE --relatorio JSON` mede CER/WER no split de teste separado (splits já determinísticos por documento/escrevente);
- **Diagnóstico ampliado**: `diagnosticar` lista modelos `.mlmodel` locais e informa quando Kraken está sem modelo.

```bash
ocrhist processar carta_1891.tif --perfil manuscrito --engine kraken
ocrhist treinar kraken data/treinamento/cartas_1891/ground_truth --dry-run
ocrhist treinar kraken data/treinamento/cartas_1891/ground_truth --modelo-base data/modelos/kraken/base.mlmodel --epocas 30 --executar
ocrhist treinar avaliar data/modelos/kraken/cartas_1891.mlmodel data/treinamento/cartas_1891/teste --relatorio avaliacao_kraken.json
bash scripts/treinar_kraken.sh data/treinamento/cartas_1891/ground_truth --dry-run
```

## O que o Marco 6 entrega

- **Estação de revisão "Arquivo"** (`ocrhist web`): painel com cartões e fila prioritária global, visor de página com camadas e caixas clicáveis, zoom, editor de linha com atalhos de teclado (`↑`/`↓`, `←`/`→`, `Ctrl+Enter`, `1`/`2`/`3`), sugestões LLM separadas e exportação para ground truth — tudo local, sem dependências novas;
- **Revisor LLM local opcional** (`ocrhist sugerir`, desativado por padrão): envia só linhas selecionadas ao Ollama/servidor local, valida JSON via Pydantic, registra em `correcoes` com origem `llm_sugerido` e **nunca altera o diplomático**;
- **Diagnóstico honesto**: `diagnosticar` informa estado do LLM (`DESATIVADO` por padrão) e do Ollama sem falhar.

```bash
ocrhist web --host 127.0.0.1 --port 7860
# ou
bash scripts/executar_web.sh
# → abra http://127.0.0.1:7860 (só local; --expor-rede para expor na rede)
ocrhist sugerir --linha ID_DA_LINHA --usuario ana
ocrhist sugerir --linha ID1 --linha ID2 --confirmar-lote
```

Detalhes em `docs/USO.md` (seções "Estação de revisão local (GUI)" e "Revisor LLM local").

## Motor experimental: Paddle VL (local)

A GUI e a CLI incorporam o motor `paddle_vl`, um adaptador compatível com a
API OpenAI do `llama-server`. Neste host, o servidor configurado é o
**Qwen3-VL-8B-Instruct** em `127.0.0.1:8082`; o rótulo interno permanece
`paddle_vl` porque a integração usa o mesmo fluxo de visão de página, mas não
promete que o modelo seja o PaddleOCR-VL-1.6 original. Não há downloads
automáticos nem envio para a nuvem.

```bash
bash scripts/servidor_qwen3vl.sh --port 8082
ocrhist processar carta_1891.tif --engine paddle_vl
# na GUI: Configuração de conversão → Motor → PaddleOCR-VL (visão)
```

Cada página vira um bloco único **sem confiança por linha** (revisão visual
obrigatória). A GUI exibe endpoint, modelo e disponibilidade, e recusa
servidores que não anunciem um modelo de visão. Para trocar o modelo, ajuste
`paddlevl.base_url`, `paddlevl.model` e `paddlevl.max_lado_px` no YAML.
Detalhes em `docs/USO.md`.

## Motor experimental: olmOCR (local)

Segunda rota VLM: `olmocr`, incorporada à CLI e à GUI. O adaptador preserva a
ordem natural de leitura e solicita saída em Markdown. O servidor visual pode
ser iniciado diretamente pelo botão **Iniciar olmOCR** na GUI. Neste host, o
perfil usa o Qwen3-VL local em `:8082`; o GGUF oficial olmOCR-2-7B pode ser
usado ajustando `configs/olmocr.yaml` e iniciando o script correspondente:

```bash
bash scripts/servidor_olmocr.sh --port 8082
ocrhist processar carta_1891.tif --engine olmocr
```

Os mesmos limites honestos do `paddle_vl` se aplicam: uma página vira um bloco
sem caixas por linha, com confiança nula e revisão humana obrigatória. O
adaptador faz uma passada com `temperature=0` (sem a "ancoragem" do toolkit
oficial). Detalhes em `docs/USO.md`.

## Motor experimental: DeepSeek-OCR-2 (local)

Quarta rota VLM: `deepseek_ocr2`, MoE 3,4B especializado em documentos
(saída Markdown via `<|grounding|>`). O adaptador fala com um servidor
llama-server OpenAI-compatível em `127.0.0.1:8084` (porta própria — o
`:8082` é compartilhado pelos outros VLMs). Este llama.cpp já traz o
suporte (`llama_model_deepseek2ocr`); os pesos são GGUFs comunitários.

Os pesos precisam estar presentes — nada é baixado sozinho:

```bash
hf download sabafallah/DeepSeek-OCR-2-GGUF deepseek-ocr-2-q8_0.gguf mmproj-deepseek-ocr-2-q8_0.gguf --local-dir /mnt/RESERVA2/models/OCR/DeepSeek-OCR-2  # uma vez, explícito
bash scripts/servidor_deepseekocr2.sh --port 8084
ocrhist processar carta_1891.tif --engine deepseek_ocr2 --config configs/deepseekocr2.yaml
# na GUI: Configuração de conversão → Motor → DeepSeek-OCR-2 (documentos/markdown)
```

Valem os mesmos limites honestos dos outros VLMs: página como bloco único,
sem caixas por linha, confiança nula e revisão humana obrigatória.

Notas medidas neste host (set/2026, CPU sem AVX2, quantização comunitária
`sabafallah` q8_0): use o GGUF **q8_0** — o Q4_K_M (MoE) erra letras e entra
em loop; o motor sempre envia **PNG sem perda** (artefatos de JPEG derrubam
o modelo em loop de repetição) com `max_tokens: 2048` (sem teto ele não
emite EOS); e vale só o prompt oficial `<|grounding|>`, sem instruções
extras. Em scan limpo: ~segundos por página; em foto de celular com
artefatos, prefira o Qwen3-VL 8B (lento, porém fiel). Saída degenerada
(loop de repetição, diversidade de 8-gramas < 0,1 em 500+ chars) é
recusada e a página vai para erro em vez de salvar lixo; DRY foi avaliado
e descartado (aborta a transcrição legítima junto).

## Marcos futuros (fora do MVP)

Ajustes de desempenho (paralelismo medido no SQLite), adaptador TrOCR, rota
PaddleOCR clássico (PP-OCR CPU) como alternativa leve ao VLM, e empacotamento final.

## Limitações conhecidas

O OCR em si não baixa modelos; modelos de HTR são baixados apenas em comandos explícitos. PDF pesquisável sem OCRmyPDF usa o fallback local, que insere o texto invisível em caixa ampla por página. Aceleradores AMD/NVIDIA permanecem opcionais por decisão de arquitetura.

## Licença

MIT. Consulte `LICENSE`.
