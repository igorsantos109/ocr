# Solução de problemas

- **Python antigo:** use Python 3.11 ou superior e recrie `.venv`.
- **Tesseract indisponível:** instale `tesseract-ocr` e `tesseract-ocr-por`; o diagnóstico continua funcionando sem ele.
- **Diretórios Desktop ausentes:** use `ocrhist setup --criar-diretorios --sim` somente se desejar criá-los.
- **Banco não pode ser criado:** verifique permissão do diretório indicado por `banco` no YAML.
- **Kraken/OCRmyPDF/Ollama indisponíveis:** são opcionais e não bloqueiam o processamento básico. Sem OCRmyPDF, o projeto tenta o fallback local PyMuPDF.
- **Fila de revisão vazia:** `revisar` mostra linhas com `exige_revisao=true`. Use `ocrhist selecionar` para seleção ativa e marque linhas corrigidas com `treinamento` para exportá-las.
- **Dataset inválido:** execute `ocrhist dataset validar`; confira caminhos relativos no `manifest.jsonl`, `revisado=true` e transcrições não vazias.
- **Split com conjunto vazio:** com poucos documentos/escreventes isso pode ser esperado. Adicione grupos antes do treinamento; linhas do mesmo grupo nunca são espalhadas artificialmente.
