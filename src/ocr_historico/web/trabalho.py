"""Fila de OCR em segundo plano para a GUI (thread única, estado consultável)."""

from __future__ import annotations

import threading
from collections import deque
from typing import Any

from ..config import AppConfig

_MAX_LOG = 80


class FilaTrabalho:
    """Uma tarefa por vez: a GUI consulta `snapshot()` sem bloquear o OCR."""

    def __init__(self) -> None:
        self._trava = threading.Lock()
        self._evento_cancelar = threading.Event()
        self._fio: threading.Thread | None = None
        self._estado = "ocioso"
        self._mensagem = "Nenhum trabalho em andamento."
        self._percentual = 0
        self._documento: str | None = None
        self._documento_id: str | None = None
        self._pagina = 0
        self._paginas = 0
        self._indice = 0
        self._total = 0
        self._motor = ""
        self._log: deque[str] = deque(maxlen=_MAX_LOG)
        self._resumo: dict[str, int] = {"paginas_ok": 0, "paginas_erro": 0, "documentos": 0}

    def snapshot(self) -> dict[str, Any]:
        with self._trava:
            return {
                "estado": self._estado,
                "mensagem": self._mensagem,
                "percentual": self._percentual,
                "documento": self._documento,
                "documento_id": self._documento_id,
                "pagina": self._pagina,
                "paginas": self._paginas,
                "indice": self._indice,
                "total": self._total,
                "motor": self._motor,
                "log": list(self._log),
                "resumo": dict(self._resumo),
            }

    def ocupado(self) -> bool:
        with self._trava:
            return self._estado == "rodando"

    def pedir_cancelamento(self) -> None:
        self._evento_cancelar.set()
        self._anotar("Cancelamento pedido — aguardando o fim da página atual.")

    def iniciar(
        self,
        config: AppConfig,
        ids: list[str] | None,
        engine: str | None,
        forcar: bool,
        retry_failed: bool,
    ) -> dict[str, Any]:
        with self._trava:
            if self._estado == "rodando":
                raise RuntimeError("Já há um OCR em andamento.")
            self._estado = "rodando"
            self._mensagem = "Iniciando OCR…"
            self._percentual = 0
            self._documento = None
            self._documento_id = None
            self._pagina = 0
            self._paginas = 0
            self._indice = 0
            self._total = len(ids or [])
            self._motor = engine or ""
            self._resumo = {"paginas_ok": 0, "paginas_erro": 0, "documentos": 0}
            self._log.clear()
            self._evento_cancelar.clear()
        self._anotar("Fila iniciada.")
        self._fio = threading.Thread(
            target=self._executar,
            args=(config, ids, engine, forcar, retry_failed),
            daemon=True,
            name="ocr-gui-trabalho",
        )
        self._fio.start()
        return self.snapshot()

    def _anotar(self, texto: str) -> None:
        with self._trava:
            self._log.append(texto)
            self._mensagem = texto

    def _progresso(self, evento: str, dados: dict[str, Any]) -> None:
        with self._trava:
            if evento == "inicio_doc":
                self._documento = str(dados.get("nome") or "")
                self._documento_id = str(dados.get("id") or "")
                self._indice = int(dados.get("indice") or 0)
                self._total = int(dados.get("total") or self._total)
                self._pagina = 0
                self._mensagem = f"Documento {self._indice}/{self._total}: {self._documento}"
                self._log.append(self._mensagem)
            elif evento == "inicio_pagina":
                self._pagina = int(dados.get("pagina") or 0)
                self._paginas = int(dados.get("paginas") or 0)
                self._motor = str(dados.get("motor") or self._motor)
                self._mensagem = f"Reconhecendo p.{self._pagina}/{self._paginas} ({self._motor})"
                self._log.append(self._mensagem)
            elif evento == "fim_pagina":
                ok = bool(dados.get("ok"))
                self._log.append(f"Página {dados.get('pagina')}: {'ok' if ok else 'erro'}")
            elif evento == "fim_doc":
                self._log.append("Documento concluído.")
            elif evento == "cancelado":
                self._mensagem = "Cancelado."
                self._log.append(self._mensagem)
            total = max(self._total, 1)
            paginas = max(self._paginas, 1)
            frac_doc = (max(self._indice, 1) - 1) / total
            frac_pag = self._pagina / paginas / total
            self._percentual = min(99, int(round((frac_doc + frac_pag) * 100)))

    def _executar(
        self,
        config: AppConfig,
        ids: list[str] | None,
        engine: str | None,
        forcar: bool,
        retry_failed: bool,
    ) -> None:
        from ..pipeline import processar_documentos

        try:
            resumo = processar_documentos(
                config,
                engine_nome=engine,
                forcar=forcar,
                retry_failed=retry_failed,
                somente_ids=ids,
                progresso=self._progresso,
                cancelado=self._evento_cancelar.is_set,
            )
            with self._trava:
                self._resumo = {
                    "paginas_ok": resumo.paginas_ok,
                    "paginas_erro": resumo.paginas_erro,
                    "documentos": resumo.documentos,
                }
                if self._evento_cancelar.is_set():
                    self._estado = "cancelado"
                    self._mensagem = "OCR cancelado."
                    self._percentual = self._percentual
                else:
                    self._estado = "concluido"
                    self._mensagem = (
                        f"OCR concluído: {resumo.documentos} doc(s), "
                        f"{resumo.paginas_ok} pág. ok, {resumo.paginas_erro} com erro."
                    )
                    self._percentual = 100
                self._log.append(self._mensagem)
        except Exception as erro:  # noqa: BLE001 - a GUI precisa da mensagem
            with self._trava:
                self._estado = "erro"
                self._mensagem = f"Falha no OCR: {erro}"
                self._log.append(self._mensagem)


FILA = FilaTrabalho()
