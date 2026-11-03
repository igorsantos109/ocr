# Instalação

Consulte o [README](../README.md) para o caminho rápido. O instalador é idempotente, cria `.venv` somente se necessário, instala o pacote editável e executa `ocrhist diagnosticar`. Ele não instala dependências de sistema sem ação explícita nem baixa modelos.

Para reproduzir manualmente:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/ocrhist setup
.venv/bin/ocrhist diagnosticar
```

Dependências opcionais serão documentadas junto aos marcos que as utilizarem.
