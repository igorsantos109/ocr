# Imagem mínima e CPU-first para o OCR Histórico BR.
# Docker é OPCIONAL: o fluxo nativo continua sendo o principal.
# Build rootless-friendly: o usuário final roda com seu próprio UID/GID.
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# Dependências do sistema: Tesseract + idioma por, Poppler, OCRmyPDF e tools.
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr \
      tesseract-ocr-por \
      poppler-utils \
      ocrmypdf \
      ghostscript \
      qpdf \
      unpaper \
      && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala o projeto (leitura e escrita de entrada/saída ficam nos volumes).
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY configs ./configs
COPY scripts ./scripts
RUN pip install --no-cache-dir .

# Diretórios de trabalho padrão (montáveis via docker-compose).
RUN mkdir -p /dados/entrada /dados/saida /dados/banco /dados/modelos && \
    chmod -R ugo+rwX /dados

# Usuário não-root para execução rootless.
RUN useradd --create-home --uid 10001 ocr && \
    chown -R ocr:ocr /app /dados
USER ocr

ENV OCRHIST_ENTRADA=/dados/entrada \
    OCRHIST_SAIDA=/dados/saida \
    OCRHIST_BANCO=/dados/banco/ocr_historico.sqlite3

ENTRYPOINT ["ocrhist"]
CMD ["doctor"]