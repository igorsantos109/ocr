"""Serviço de ingestão: registra documentos e páginas, com retomada."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image
from sqlalchemy import select

from ..config import AppConfig
from ..database import fabrica_sessoes, inicializar_banco
from ..models import Documento, Pagina
from .arquivos import ArquivoDescoberto, descobrir_arquivos
from .hash import calcular_sha256
from .imagens import info_imagem
from .inventario import inventariar_entrada
from .pdf import dimensoes_pdf_px, info_pdf, renderizar_pagina
from .preservacao import preservar_original

logger = logging.getLogger("ocr_historico")

STATUS_PRONTO_OCR = "aguardando_ocr"


@dataclass
class ResumoIngestao:
    total: int = 0
    novos: int = 0
    pulados: int = 0
    erros: int = 0
    inventariados: int = 0
    ignorados: int = 0
    manifesto: Path | None = None
    documentos: list[str] = field(default_factory=list)


def _dir_renderizadas(config: AppConfig) -> Path:
    base = Path(config.banco).parent / "processamento" / "renderizadas"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _deve_pular(status: str, forcar: bool, retry_failed: bool) -> bool:
    if forcar:
        return False
    if status == "erro":
        return not retry_failed
    return status in {"concluido", STATUS_PRONTO_OCR, "processando"}


def ingerir_entrada(
    entrada: Path | str,
    config: AppConfig,
    perfil: str | None = None,
    forcar: bool = False,
    retry_failed: bool = False,
) -> ResumoIngestao:
    """Descobre, calcula SHA-256 e registra documentos e páginas.

    Um erro em um arquivo nunca aborta o lote: o documento é marcado com
    `erro` e o processamento segue para o próximo. Arquivos idênticos
    (mesmo SHA-256) já registrados são pulados, exceto com `forcar` ou,
    para falhas, com `retry_failed`.
    """
    perfil_usado = perfil or config.perfil
    resumo = ResumoIngestao()
    inicializar_banco(config.banco)
    render_base = _dir_renderizadas(config)

    inventario = inventariar_entrada(
        entrada,
        calcular_hash=config.inventario.calcular_hash,
        seguir_links=config.inventario.seguir_links,
    )
    resumo.inventariados = len(inventario.suportados)
    resumo.ignorados = len(inventario.ignorados)
    manifesto_dir = Path(config.banco).parent / "inventarios"
    manifesto_dir.mkdir(parents=True, exist_ok=True)
    resumo.manifesto = manifesto_dir / "inventario.json"
    resumo.manifesto.write_text(json.dumps(inventario.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        arquivos = descobrir_arquivos(entrada)
    except FileNotFoundError as erro:
        logger.error("Entrada não encontrada: %s", erro)
        raise
    resumo.total = len(arquivos)

    for item in arquivos:
        try:
            _ingerir_um(item, config, perfil_usado, forcar, retry_failed, render_base, resumo)
        except Exception as erro:  # erro isolado por arquivo, nunca aborta o lote
            logger.exception("Falha ao ingerir %s: %s", item.caminho, erro)
            resumo.erros += 1
            _marcar_erro(config, item, str(erro))
    return resumo


def _ingerir_um(
    item: ArquivoDescoberto,
    config: AppConfig,
    perfil: str,
    forcar: bool,
    retry_failed: bool,
    render_base: Path,
    resumo: ResumoIngestao,
) -> None:
    sha = calcular_sha256(item.caminho)
    preservado = None
    if config.preservacao.modo != "none":
        raiz_preservacao = config.preservacao.raiz or (Path(config.saida) / "_originais")
        item_inventario = next(
            (item_i for item_i in inventariar_entrada(item.caminho).itens if item_i.suportado),
            None,
        )
        if item_inventario is not None:
            preservado = preservar_original(
                item_inventario,
                raiz_preservacao,
                sha,
                modo=config.preservacao.modo,
                sobrescrever=config.preservacao.sobrescrever,
                verificar_hash=config.preservacao.verificar_hash,
            )
    engine = inicializar_banco(config.banco)
    with fabrica_sessoes(engine)() as sessao:
        existente = sessao.scalar(select(Documento).where(Documento.sha256 == sha))
        if existente is not None and _deve_pular(existente.status, forcar, retry_failed):
            logger.info("Pulado (já registrado, status=%s): %s", existente.status, item.nome)
            resumo.pulados += 1
            resumo.documentos.append(existente.id)
            return
        doc_id = existente.id if existente is not None else uuid.uuid4().hex
        if existente is not None:
            for pagina in list(existente.paginas):
                sessao.delete(pagina)
            sessao.flush()

        parametros: dict[str, Any] = {
            "render_dpi": config.render_dpi,
            "perfil": perfil,
            "inventario": {
                "caminho_relativo": item.caminho.relative_to(Path(config.entrada)).as_posix()
                if Path(config.entrada).is_dir() and Path(item.caminho).is_relative_to(Path(config.entrada))
                else item.nome,
                "tamanho_bytes": item.caminho.stat().st_size,
                "sha256": sha,
            },
            "preservacao": {
                "modo": config.preservacao.modo,
                "destino": preservado.destino if preservado else None,
                "verificado": preservado.verificado if preservado else False,
            },
        }
        if item.tipo_arquivo == "pdf":
            paginas_info = _paginas_pdf(item.caminho, doc_id, config, parametros, render_base)
            numero_paginas = len(paginas_info)
        else:
            info = info_imagem(item.caminho)
            numero_paginas = info.quadros
            imagens = [str(item.caminho)]
            # O Pillow lê apenas o primeiro quadro por padrão. Materializar TIFF
            # multipágina torna cada página independente, reproduzível e auditável.
            if numero_paginas > 1:
                quadros_dir = render_base / doc_id
                quadros_dir.mkdir(parents=True, exist_ok=True)
                with Image.open(item.caminho) as tiff:
                    imagens = []
                    for indice in range(numero_paginas):
                        tiff.seek(indice)
                        quadro = tiff.convert("RGB")
                        destino_quadro = quadros_dir / f"p{indice + 1:04d}.png"
                        quadro.save(destino_quadro, format="PNG")
                        imagens.append(str(destino_quadro))
            paginas_info = [
                {
                    "numero": n,
                    "imagem_original": imagens[n - 1],
                    "largura": info.largura,
                    "altura": info.altura,
                    "dpi": info.dpi,
                    "nitidez": info.nitidez,
                    "contraste": info.contraste,
                }
                for n in range(1, numero_paginas + 1)
            ]
            if info.resolucao_baixa:
                logger.info("Aviso de resolução baixa (revisão priorizada): %s", item.nome)

        if existente is None:
            documento = Documento(
                id=doc_id,
                caminho_original=str(item.caminho),
                nome_original=item.nome,
                sha256=sha,
                tipo_arquivo=item.tipo_arquivo,
                perfil=perfil,
                numero_paginas=numero_paginas,
                status=STATUS_PRONTO_OCR,
                configuracao_json=parametros,
            )
            sessao.add(documento)
        else:
            existente.caminho_original = str(item.caminho)
            existente.nome_original = item.nome
            existente.tipo_arquivo = item.tipo_arquivo
            existente.perfil = perfil
            existente.numero_paginas = numero_paginas
            existente.status = STATUS_PRONTO_OCR
            existente.erro = None
            existente.configuracao_json = parametros
            documento = existente

        for ordem, info_pag in enumerate(paginas_info, start=1):
            sessao.add(
                Pagina(
                    id=uuid.uuid4().hex,
                    documento=documento,
                    numero=info_pag["numero"],
                    imagem_original=info_pag.get("imagem_original"),
                    imagem_pre_processada=None,
                    largura=info_pag.get("largura"),
                    altura=info_pag.get("altura"),
                    dpi=info_pag.get("dpi"),
                    ordem_processamento=ordem,
                    status="pendente",
                )
            )
        sessao.commit()
        logger.info("Ingerido: %s (%d página(s))", item.nome, numero_paginas)
        resumo.novos += 1
        resumo.documentos.append(documento.id)


def _paginas_pdf(
    caminho: Path,
    doc_id: str,
    config: AppConfig,
    parametros: dict[str, Any],
    render_base: Path,
) -> list[dict[str, Any]]:
    info = info_pdf(caminho)
    parametros["camada_textual"] = info.tem_texto
    if info.tem_texto:
        logger.info("PDF com camada textual utilizável: %s", caminho.name)
    dimensoes = dimensoes_pdf_px(caminho, config.render_dpi)
    destino_dir = render_base / doc_id
    paginas: list[dict[str, Any]] = []
    for numero, (largura, altura) in enumerate(dimensoes, start=1):
        saida = destino_dir / f"p{numero:04d}.png"
        renderizar_pagina(caminho, numero, config.render_dpi, saida)
        paginas.append(
            {
                "numero": numero,
                "imagem_original": str(saida),
                "largura": largura,
                "altura": altura,
                "dpi": config.render_dpi,
            }
        )
    return paginas


def _marcar_erro(config: AppConfig, item: ArquivoDescoberto, mensagem: str) -> None:
    try:
        engine = inicializar_banco(config.banco)
        with fabrica_sessoes(engine)() as sessao:
            sha = calcular_sha256(item.caminho)
            existente = sessao.scalar(select(Documento).where(Documento.sha256 == sha))
            if existente is None:
                sessao.add(
                    Documento(
                        id=uuid.uuid4().hex,
                        caminho_original=str(item.caminho),
                        nome_original=item.nome,
                        sha256=sha,
                        tipo_arquivo=item.tipo_arquivo,
                        perfil=config.perfil,
                        numero_paginas=0,
                        status="erro",
                        configuracao_json={},
                        erro=mensagem[:2000],
                    )
                )
            else:
                existente.status = "erro"
                existente.erro = mensagem[:2000]
            sessao.commit()
    except Exception:
        logger.exception("Não foi possível registrar o erro de %s", item.caminho)
