# Treinamento HTR

O Marco 4 introduz a preparação auditável do conjunto de linhas. O Marco 5 adiciona o fine-tuning Kraken CPU-first, sem download silencioso.

## 1. Preparar uma coleção

```bash
ocrhist dataset iniciar cartas_1891 --raiz data/treinamento
```

Isso cria:

```text
data/treinamento/cartas_1891/ground_truth/
├── imagens/
├── transcricoes/
├── manifest.jsonl
└── README.md
```

## 2. Marcar linhas

Na revisão, uma linha pode ser marcada para treinamento:

```bash
ocrhist revisar --status alta
ocrhist marcar ID_DA_LINHA treinamento --usuario nome
```

Ou pela interface local, usando **Para treinamento**. O status não altera o texto bruto e fica disponível na trilha de auditoria quando observação for informada.

## 3. Exportar e validar

```bash
ocrhist dataset exportar data/treinamento/cartas_1891/ground_truth
ocrhist dataset validar data/treinamento/cartas_1891/ground_truth
```

A exportação copia a imagem de linha (ou a imagem de página quando ainda não existe recorte) e grava o texto diplomático revisado. Repetições são ignoradas por identificador.

Cada linha do `manifest.jsonl` contém `id`, `imagem`, `transcricao`, `documento`, `pagina`, `escrevente`, `periodo` e `revisado=true`. O validador verifica JSON, referências, transcrição não vazia e revisão confirmada.

## 4. Dividir sem vazamento

```bash
ocrhist dataset dividir data/treinamento/cartas_1891/ground_truth \
  --destino data/treinamento/cartas_1891
# por escrevente, quando os metadados existirem:
ocrhist dataset dividir data/treinamento/cartas_1891/ground_truth \
  --destino data/treinamento/cartas_1891 --grupo escrevente
```

A divisão é determinística e agrupa por documento (padrão) ou escrevente. Linhas do mesmo grupo nunca são distribuídas entre treino/validação/teste. Com poucas coleções, um split pode ficar vazio: adicione coleções antes de treinar.

## 5. Treinar / fine-tuning Kraken (Marco 5)

O treino é **local e CPU-first** (funciona sem GPU; GPU é opcional). Nenhum modelo é baixado silenciosamente: o modelo base deve ser um arquivo local em `data/modelos/kraken/` ou apontado por `--modelo-base`.

```bash
# preparar (dry-run) — apenas valida e mostra o comando
bash scripts/treinar_kraken.sh data/treinamento/cartas_1891/ground_truth --dry-run

# via CLI direta
ocrhist treinar kraken data/treinamento/cartas_1891/ground_truth --dry-run --epocas 20
ocrhist treinar kraken data/treinamento/cartas_1891/ground_truth \
  --modelo-base data/modelos/kraken/base.mlmodel \
  --saida data/modelos/kraken/cartas_1891.mlmodel \
  --epocas 30 --executar

# com splits já existentes (recomendado): usa treino/validacao separados
ocrhist dataset dividir data/treinamento/cartas_1891/ground_truth --destino data/treinamento/cartas_1891
ocrhist treinar kraken data/treinamento/cartas_1891/ground_truth --dry-run
```

O comando preparado é `ketos train` (ou `kraken train` em versões novas), sempre com `--device cpu` quando ketos está presente. O `scripts/treinar_kraken.sh` apenas repassa para a CLI e informa `Kraken não instalado` quando aplicável.

## 6. Avaliar sem vazamento

Nunca avalie no mesmo conjunto usado para treino. Use o split `teste`:

```bash
ocrhist treinar avaliar data/modelos/kraken/cartas_1891.mlmodel \
  data/treinamento/cartas_1891/teste \
  --relatorio output/avaliacao_kraken.json

# ou avaliar qualquer hipótese contra referência (independente de Kraken)
ocrhist avaliar --referencia data/treinamento/teste/referencia.txt \
                --hipotese output/OCRSAIDA/doc/doc_diplomatico.txt --relatorio avaliacao.json
```

Valores de CER/WER são taxas de erro (menor é melhor) e **não são acurácia**. A avaliação Kraken sem o binário instalado retorna aviso auditável sem falhar o processo.

## 7. Segmentação de manuscritos

- Com Kraken + `data/modelos/kraken/blla.mlmodel` (ou `--modelo`), `segmentar_linhas` usa `kraken.blla.segment`.
- Sem Kraken, o fallback OpenCV por projeção/contornos gera `PAGE-XML` e `baixa_confianca.csv` com `metodo=fallback`, penalizando confiança e exigindo revisão humana.
- Para HTR real, coloque um modelo `.mlmodel` em `data/modelos/kraken/` antes de `ocrhist processar carta.tif --perfil manuscrito --engine kraken`.

## Princípios

- O ground truth deve ser produzido por revisão humana visual.
- Texto bruto nunca é substituído pela correção.
- Grafia histórica, abreviaturas, nomes, datas e valores devem ser preservados conforme o padrão diplomático.
- O conjunto de teste é separado e não deve ser usado no treinamento.
- Treino é retomável e CPU-first; GPU permanece opcional.
