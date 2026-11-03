# Formatos de saída

O Marco 3 gera os produtos abaixo por documento em `OCRSAIDA/nome_do_documento/`:

| Arquivo | Conteúdo |
|---|---|
| `*_bruto.txt` | Texto direto do motor, sem correção semântica. |
| `*_diplomatico.txt` | Texto derivado com apenas regras mecânicas inequívocas. |
| `*.md` | Texto estruturado por página. |
| `*.json` | Auditoria completa: hash, perfil, execução, qualidade, linhas, caixas e confiança. |
| `*.tsv` | Página, linha, bounding box, confiança e texto, compatível com análise tabular. |
| `*.hocr` | HTML hOCR com `ocr_page`, `ocr_line`, `bbox` e `x_wconf`. |
| `*_page.xml` | PAGE-XML com `Page`, `TextRegion`, `TextLine`, `Coords` e `Unicode`. |
| `*_relatorio.html` | Relatório navegável com status e linhas destacadas para revisão. |
| `baixa_confianca.csv` | Linhas abaixo do limiar de revisão (`pagina`, `linha`, `confianca`, `prioridade`, `texto`). |
| `overlays/pagina_NNNN.png` | Imagens com caixas vermelhas numeradas para inspeção visual. |
| `*_pesquisavel.pdf` | OCRmyPDF se instalado; caso contrário, PDF local PyMuPDF com camada invisível. |

## Confiança e revisão

A prioridade inicial é:

- **alta:** confiança `< 0,70`, confiança ausente ou falha de segmentação;
- **média:** `0,70 ≤ confiança < 0,82`;
- **baixa:** confiança `≥ 0,82`.

A confiança do motor é o sinal principal. Nitidez, contraste, caracteres anormais e divergência reduzem o valor, mas dicionários não provam correção histórica.

## PDF pesquisável

A ordem é `ocrmypdf` local quando instalado; depois fallback PyMuPDF. O fallback nunca substitui o PDF original e não faz upload nem chamadas externas. Se nenhuma página tiver uma imagem derivada, o relatório continua sendo produzido e o PDF é registrado como indisponível.

## CER/WER

`ocrhist avaliar` calcula distância de Levenshtein entre caracteres (CER) e palavras (WER), informando inserções, deleções, substituições e distância total. CER/WER são **taxas de erro**, não acurácia; normalização é opcional e o modo padrão preserva acentos, pontuação e grafia histórica.
