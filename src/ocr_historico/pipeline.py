"""Pipeline de OCR em lote, exportação e auditoria (Marcos 2–4)."""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select

from .config import AppConfig
from .database import fabrica_sessoes, inicializar_banco
from .exportacao import (
    agora_iso,
    exportar_baixa_confianca,
    exportar_hocr,
    exportar_json,
    exportar_manifesto,
    exportar_markdown,
    exportar_overlay,
    exportar_pagexml,
    exportar_pdf_pesquisavel,
    exportar_relatorio_html,
    exportar_tsv,
    exportar_txts,
)
from .models import Documento, Execucao, Linha, Pagina
from .posprocessamento.confianca import calcular_confianca, classificar_revisao
from .qualidade.preprocessamento import aplicar_pipeline
from .reconhecimento.base import MotorIndisponivel, RecognitionConfig, RecognitionEngine
from .reconhecimento.factory import criar_engine, resolver_engine

logger = logging.getLogger("ocr_historico")

ProgressoFn = Callable[[str, dict[str, Any]], None]

ESPACOS_DUPLOS = re.compile(r"[ \t]{2,}")

# Motores de visão (página inteira via servidor local, sem caixas por linha):
# usam a imagem original colorida e registram base/modelo na auditoria.
MOTORES_VL = frozenset({"qwen3_vl", "glm_ocr", "olmocr", "deepseek_ocr2"})


def para_diplomatico(bruto: str) -> str:
    """Regra mecânica inequívoca: colapsa espaços duplicados criados pelo OCR.

    Não moderniza ortografia, não expande abreviaturas e não toca em
    pontuação, acentos ou caixa. Quebras de linha são preservadas.
    """
    return "\n".join(ESPACOS_DUPLOS.sub(" ", linha).strip() for linha in bruto.splitlines()).strip()


@dataclass
class ResumoPipeline:
    documentos: int = 0
    paginas_ok: int = 0
    paginas_erro: int = 0
    ids: list[str] = field(default_factory=list)


def _nome_base(nome_original: str) -> str:
    base = Path(nome_original).stem.strip().lower()
    base = re.sub(r"[^a-z0-9._-]+", "_", base).strip("._-")
    return base or "documento"


def _pasta_saida(config: AppConfig, documento: Documento) -> Path:
    pasta = Path(config.saida) / _nome_base(documento.nome_original)
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _dir_pre(config: AppConfig) -> Path:
    base = Path(config.banco).parent / "processamento" / "pre_processadas"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _config_motor(
    dados: AppConfig,
    perfil_nome: str,
    engine_nome: str | None,
    vl_url: str | None = None,
    vl_modelo: str | None = None,
) -> RecognitionConfig:
    rec = dados.reconhecimento
    motor = engine_nome or rec.engine
    if motor == "auto":
        perfil = perfil_nome.lower()
        if "manuscrito" in perfil:
            motor = "kraken"
        elif any(chave in perfil for chave in ("jornal", "layout", "estrutura")):
            motor = "paddleocr"
        else:
            motor = "tesseract"
    # compat: paddle_vl antigo mapeia para qwen3_vl
    if motor == "paddle_vl":
        motor = "qwen3_vl"
    if motor == "qwen3_vl":
        cfg = dados.qwen3vl
        # fallback para paddlevl se config antiga
        if getattr(dados, 'paddlevl', None) and getattr(dados.paddlevl, 'model', None):
            cfg = dados.paddlevl if cfg.model == "Qwen3VL-4B-Instruct" and dados.paddlevl.model else cfg
        return RecognitionConfig(
            engine=motor,
            idioma=rec.idioma,
            oem=rec.oem,
            psm=rec.psm,
            modelo=vl_modelo or cfg.model,
            base_url=vl_url or cfg.base_url,
            timeout_segundos=cfg.timeout_seconds,
            max_lado_px=cfg.max_lado_px,
        )
    if motor == "glm_ocr":
        return RecognitionConfig(
            engine=motor,
            idioma=rec.idioma,
            oem=rec.oem,
            psm=rec.psm,
            modelo=vl_modelo or dados.glmocr.model,
            base_url=vl_url or dados.glmocr.base_url,
            timeout_segundos=dados.glmocr.timeout_seconds,
            max_lado_px=dados.glmocr.max_lado_px,
        )
    if motor == "olmocr":
        return RecognitionConfig(
            engine=motor,
            idioma=rec.idioma,
            oem=rec.oem,
            psm=rec.psm,
            modelo=vl_modelo or dados.olmocr.model,
            base_url=vl_url or dados.olmocr.base_url,
            timeout_segundos=dados.olmocr.timeout_seconds,
            max_lado_px=dados.olmocr.max_lado_px,
        )
    if motor == "deepseek_ocr2":
        return RecognitionConfig(
            engine=motor,
            idioma=rec.idioma,
            oem=rec.oem,
            psm=rec.psm,
            modelo=vl_modelo or dados.deepseekocr2.model,
            base_url=vl_url or dados.deepseekocr2.base_url,
            timeout_segundos=dados.deepseekocr2.timeout_seconds,
            max_lado_px=dados.deepseekocr2.max_lado_px,
        )
    if motor == "paddleocr":
        paddle = dados.paddleocr
        return RecognitionConfig(
            engine=motor,
            idioma=paddle.idioma or rec.idioma,
            oem=rec.oem,
            psm=rec.psm,
            modelo=rec.modelo,
            dispositivo=paddle.dispositivo,
            backend=paddle.backend,
            allow_download=paddle.allow_download,
            det_model_dir=str(paddle.det_model_dir or ""),
            rec_model_dir=str(paddle.rec_model_dir or ""),
            cls_model_dir=str(paddle.cls_model_dir or ""),
            text_detection_model_dir=str(paddle.text_detection_model_dir or ""),
            text_recognition_model_dir=str(paddle.text_recognition_model_dir or ""),
            textline_orientation_model_dir=str(paddle.textline_orientation_model_dir or ""),
            use_angle_cls=paddle.use_angle_cls,
        )
    return RecognitionConfig(
        engine=motor,
        idioma=rec.idioma,
        oem=rec.oem,
        psm=rec.psm,
        modelo=rec.modelo,
    )


def exportar_documento(config: AppConfig, doc_id: str) -> Path:
    """Exporta todos os produtos de um documento sem repetir o OCR."""
    engine = inicializar_banco(config.banco)
    original_pdf: str | None = None
    nome_original = ""
    sha256_doc = ""
    perfil_doc = ""
    status_doc = ""
    blocos: list[dict[str, Any]] = []
    with fabrica_sessoes(engine)() as sessao:
        documento = sessao.get(Documento, doc_id)
        if documento is None:
            raise ValueError(f"Documento não encontrado: {doc_id}")
        original_pdf = documento.caminho_original if documento.tipo_arquivo == "pdf" else None
        nome_original = documento.nome_original
        sha256_doc = documento.sha256
        perfil_doc = documento.perfil
        status_doc = documento.status
        paginas = sessao.scalars(select(Pagina).where(Pagina.documento_id == doc_id).order_by(Pagina.numero)).all()
        for pagina in paginas:
            linhas = sessao.scalars(select(Linha).where(Linha.pagina_id == pagina.id).order_by(Linha.numero)).all()
            itens = [
                {
                    "numero": item.numero,
                    "x": item.x,
                    "y": item.y,
                    "largura": item.largura,
                    "altura": item.altura,
                    "texto_bruto": item.texto_bruto,
                    "texto_diplomatico": item.texto_diplomatico,
                    "confianca": item.confianca,
                }
                for item in linhas
            ]
            blocos.append({"pagina": pagina, "itens": itens})
        execucao = sessao.scalars(
            select(Execucao).where(Execucao.documento_id == doc_id).order_by(Execucao.inicio.desc())
        ).first()
        execucao_info = {
            "motores": [execucao.motor] if execucao else [],
            "modelo": (execucao.versao_modelo if execucao else None),
            "configuracao": dict(documento.configuracao_json or {}),
        }
    pasta = Path(config.saida) / _nome_base(nome_original)
    pasta.mkdir(parents=True, exist_ok=True)
    base = _nome_base(nome_original)
    bruto = "\n\n".join("\n".join(i["texto_bruto"] for i in b["itens"]) for b in blocos)
    diploteco = "\n\n".join("\n".join(i["texto_diplomatico"] for i in b["itens"]) for b in blocos)
    exportar_txts(pasta, base, [bruto], [diploteco])
    exportar_markdown(pasta, base, nome_original, [diploteco])
    paginas_data = [
        {
            "numero": b["pagina"].numero,
            "qualidade": {
                "largura": b["pagina"].largura,
                "altura": b["pagina"].altura,
                "dpi": b["pagina"].dpi,
                "nitidez": b["pagina"].nitidez,
                "contraste": b["pagina"].contraste,
            },
            "texto_bruto": "\n".join(i["texto_bruto"] for i in b["itens"]),
            "texto_diplomatico": "\n".join(i["texto_diplomatico"] for i in b["itens"]),
            "imagem_original": b["pagina"].imagem_original,
            "imagem_pre_processada": b["pagina"].imagem_pre_processada,
            "linhas": [
                {
                    "numero": i["numero"],
                    "x": i["x"],
                    "y": i["y"],
                    "largura": i["largura"],
                    "altura": i["altura"],
                    "texto": i["texto_diplomatico"],
                    "confianca": i["confianca"],
                    "prioridade": classificar_revisao(
                        i["confianca"], config.confianca.limiar_alta, config.confianca.limiar_revisao
                    ).prioridade,
                }
                for i in b["itens"]
            ],
        }
        for b in blocos
    ]
    exportar_json(
        pasta,
        base,
        documento={
            "nome_original": nome_original,
            "sha256": sha256_doc,
            "perfil": perfil_doc,
            "processado_em": agora_iso(),
        },
        execucao=execucao_info,
        paginas=paginas_data,
    )
    exportar_tsv(pasta, base, paginas_data)
    exportar_hocr(pasta, base, paginas_data)
    exportar_pagexml(pasta, base, paginas_data)
    exportar_overlay(pasta, paginas_data)
    exportar_baixa_confianca(pasta, base, paginas_data, config.confianca.limiar_revisao)
    exportar_relatorio_html(pasta, base, nome_original, paginas_data, status_doc, config.confianca.limiar_revisao)
    exportar_manifesto(
        pasta,
        documento={
            "id": doc_id,
            "nome_original": nome_original,
            "sha256": sha256_doc,
            "perfil": perfil_doc,
            "status": status_doc,
            "caminho_original": original_pdf,
        },
        paginas=paginas_data,
        preservacao=dict(dict(documento.configuracao_json or {}).get("preservacao") or {}),
        qualidade={"paginas": [p.get("qualidade", {}) for p in paginas_data]},
    )
    try:
        exportar_pdf_pesquisavel(pasta, base, original_pdf or "", paginas_data)
    except Exception as erro:
        logger.warning("PDF pesquisável não gerado para %s: %s", nome_original, erro)
    return pasta


def processar_documentos(
    config: AppConfig,
    engine_nome: str | None = None,
    forcar: bool = False,
    retry_failed: bool = False,
    somente_ids: list[str] | None = None,
    vl_url: str | None = None,
    vl_modelo: str | None = None,
    progresso: ProgressoFn | None = None,
    cancelado: Callable[[], bool] | None = None,
) -> ResumoPipeline:
    """Executa OCR das páginas pendentes, com retomada e exportação por documento."""
    resumo = ResumoPipeline()
    engine_bd = inicializar_banco(config.banco)
    with fabrica_sessoes(engine_bd)() as sessao:
        consulta = select(Documento).order_by(Documento.criado_em)
        if somente_ids:
            consulta = consulta.where(Documento.id.in_(somente_ids))
        documentos = list(sessao.scalars(consulta))
        ids = [d.id for d in documentos]
        nomes = {d.id: d.nome_original for d in documentos}
    total = len(ids)
    for indice, doc_id in enumerate(ids, start=1):
        if cancelado is not None and cancelado():
            if progresso:
                progresso("cancelado", {"indice": indice, "total": total})
            break
        if progresso:
            progresso(
                "inicio_doc",
                {"id": doc_id, "nome": nomes.get(doc_id, doc_id), "indice": indice, "total": total},
            )
        _processar_um(
            config,
            doc_id,
            engine_nome,
            forcar,
            retry_failed,
            resumo,
            vl_url=vl_url,
            vl_modelo=vl_modelo,
            progresso=progresso,
            cancelado=cancelado,
        )
        if progresso:
            progresso("fim_doc", {"id": doc_id, "indice": indice, "total": total})
    return resumo


def _processar_um(
    config: AppConfig,
    doc_id: str,
    engine_nome: str | None,
    forcar: bool,
    retry_failed: bool,
    resumo: ResumoPipeline,
    vl_url: str | None = None,
    vl_modelo: str | None = None,
    progresso: ProgressoFn | None = None,
    cancelado: Callable[[], bool] | None = None,
) -> None:
    engine_bd = inicializar_banco(config.banco)
    with fabrica_sessoes(engine_bd)() as sessao:
        documento = sessao.get(Documento, doc_id)
        if documento is None:
            return
        if documento.status == "concluido" and not forcar:
            logger.info("Pulado (já concluído): %s", documento.nome_original)
            return
        if documento.status == "erro" and not (retry_failed or forcar):
            logger.info("Pulado (com erro; use --retry-failed): %s", documento.nome_original)
            return
        cfg_motor = _config_motor(config, documento.perfil, engine_nome, vl_url=vl_url, vl_modelo=vl_modelo)
        if (
            engine_nome is None
            and documento.tipo_arquivo == "pdf"
            and bool((documento.configuracao_json or {}).get("camada_textual"))
        ):
            cfg_motor = RecognitionConfig(
                engine="pdf_texto",
                idioma=cfg_motor.idioma,
                oem=cfg_motor.oem,
                psm=cfg_motor.psm,
                modelo=cfg_motor.modelo,
            )
            logger.info("PDF textual: usando extração direta; use --engine tesseract para comparação visual.")
        motor: RecognitionEngine = criar_engine(cfg_motor.engine)
        fallback_aviso: str | None = None
        verifica_cfg = getattr(motor, "available_com_config", None)
        pedido_ok = verifica_cfg(cfg_motor) if callable(verifica_cfg) else motor.available()
        if not pedido_ok:
            try:
                efetivo, aviso = resolver_engine(cfg_motor.engine)
            except ValueError as erro:
                logger.warning("%s", erro)
                efetivo, aviso = cfg_motor.engine, str(erro)
            if efetivo != cfg_motor.engine:
                fallback_aviso = aviso or f"Motor {cfg_motor.engine} indisponível; usando {efetivo}."
                logger.warning(fallback_aviso)
                cfg_motor = _config_motor(config, documento.perfil, efetivo, vl_url=vl_url, vl_modelo=vl_modelo)
                motor = criar_engine(cfg_motor.engine)
        if not motor.available() and cfg_motor.engine == "kraken":
            from .reconhecimento.tesseract_engine import TesseractEngine as _Tess

            tess = _Tess()
            if tess.available():
                fallback_aviso = (
                    f"Kraken indisponível; usando tesseract como fallback para {documento.nome_original}. "
                    "Para HTR real, instale kraken e um modelo .mlmodel."
                )
                logger.warning(fallback_aviso)
                motor = tess  # type: ignore[assignment]
                cfg_motor = RecognitionConfig(
                    engine="tesseract",
                    idioma=cfg_motor.idioma,
                    oem=cfg_motor.oem,
                    psm=cfg_motor.psm,
                    modelo=cfg_motor.modelo,
                )
            else:
                logger.warning(
                    "Kraken e Tesseract indisponíveis; páginas serão marcadas "
                    "como erro com mensagem acionável."
                )
        execucao = Execucao(
            id=uuid.uuid4().hex,
            documento_id=doc_id,
            motor=cfg_motor.engine,
            versao_modelo=f"{cfg_motor.idioma}_{config.reconhecimento.modelo}",
            etapa="ocr",
            status="iniciada",
            parametros_json={
                "idioma": cfg_motor.idioma,
                "oem": cfg_motor.oem,
                "psm": cfg_motor.psm,
                "render_dpi": config.render_dpi,
                "fallback_aviso": fallback_aviso,
                "vl_base_url": cfg_motor.base_url or None,
                "vl_modelo": cfg_motor.modelo if cfg_motor.engine in MOTORES_VL else None,
            },
        )
        sessao.add(execucao)
        sessao.commit()
        paginas = sessao.scalars(select(Pagina).where(Pagina.documento_id == doc_id).order_by(Pagina.numero)).all()
        ids_paginas = [p.id for p in paginas]
        verifica = getattr(motor, "available_com_config", None)
        disponivel = verifica(cfg_motor) if callable(verifica) else motor.available()
        if not disponivel:
            execucao.status = "erro"
            execucao.erro = f"Motor {cfg_motor.engine} indisponível neste host."
            sessao.commit()
    pre_base = _dir_pre(config)
    ok = 0
    erros = 0
    n_pag = len(ids_paginas)
    for i, pag_id in enumerate(ids_paginas, start=1):
        if cancelado is not None and cancelado():
            break
        if progresso:
            progresso("inicio_pagina", {"pagina": i, "paginas": n_pag, "id": pag_id, "motor": cfg_motor.engine})
        if _processar_pagina(config, pag_id, cfg_motor, motor, pre_base, forcar):
            ok += 1
            if progresso:
                progresso("fim_pagina", {"pagina": i, "paginas": n_pag, "ok": True, "motor": cfg_motor.engine})
        else:
            erros += 1
            if progresso:
                progresso("fim_pagina", {"pagina": i, "paginas": n_pag, "ok": False, "motor": cfg_motor.engine})
    with fabrica_sessoes(engine_bd)() as sessao:
        documento = sessao.get(Documento, doc_id)
        execucao_fim = sessao.scalars(
            select(Execucao).where(Execucao.documento_id == doc_id).order_by(Execucao.inicio.desc())
        ).first()
        if documento is None:
            return
        if ok and not erros:
            documento.status = "concluido"
        elif ok:
            documento.status = "parcial"
        else:
            documento.status = "erro"
            documento.erro = f"Nenhuma página reconhecida ({ok} ok, {erros} erros)."
        if execucao_fim is not None:
            from .models import agora

            execucao_fim.fim = agora()
            execucao_fim.status = "concluida" if ok else "erro"
        sessao.commit()
        try:
            exportar_documento(config, doc_id)
        except Exception as erro:
            logger.exception("Falha ao exportar %s: %s", documento.nome_original, erro)
    resumo.documentos += 1
    resumo.paginas_ok += ok
    resumo.paginas_erro += erros
    resumo.ids.append(doc_id)


def _processar_pagina(
    config: AppConfig,
    pagina_id: str,
    cfg_motor: RecognitionConfig,
    motor: RecognitionEngine,
    pre_base: Path,
    forcar: bool,
) -> bool:
    engine_bd = inicializar_banco(config.banco)
    with fabrica_sessoes(engine_bd)() as sessao:
        pagina = sessao.get(Pagina, pagina_id)
        if pagina is None:
            return False
        if pagina.status == "concluida" and not forcar:
            return True
        origem = pagina.imagem_original
        numero = pagina.numero
    try:
        if not origem:
            raise MotorIndisponivel("Página sem imagem de origem registrada.")
        destino = pre_base / pagina_id / f"p{numero:04d}.png"
        auditoria_pre: dict[str, Any] = {}
        if motor.name == "pdf_texto":
            from .models import Documento as Doc

            with fabrica_sessoes(engine_bd)() as sessao:
                pagina_ref = sessao.get(Pagina, pagina_id)
                doc_ref = sessao.get(Doc, pagina_ref.documento_id) if pagina_ref else None
                original_pdf = doc_ref.caminho_original if doc_ref else None
            resultado = motor.recognize_page(original_pdf or "", cfg_motor, numero)
        elif motor.name in MOTORES_VL:
            # VLM trabalha melhor com a imagem colorida original (manchas e tinta
            # se distinguem em cor); o pré-processamento em cinza é pulado.
            logger.info("%s: enviando imagem original colorida ao servidor local.", motor.name)
            resultado = motor.recognize_page(origem, cfg_motor, numero)
        else:
            auditoria_pre = aplicar_pipeline(origem, destino, config.preprocessamento)
            resultado = motor.recognize_page(destino, cfg_motor, numero)
        with fabrica_sessoes(engine_bd)() as sessao:
            pagina = sessao.get(Pagina, pagina_id)
            if pagina is None:
                return False
            for antiga in list(pagina.linhas):
                sessao.delete(antiga)
            sessao.flush()
            for rec in resultado.linhas:
                confianca = calcular_confianca(
                    rec.confianca,
                    pagina.nitidez,
                    pagina.contraste,
                    rec.texto,
                    bool(resultado.divergencias),
                )
                avaliacao = classificar_revisao(
                    confianca,
                    config.confianca.limiar_alta,
                    config.confianca.limiar_revisao,
                )
                sessao.add(
                    Linha(
                        id=uuid.uuid4().hex,
                        pagina_id=pagina_id,
                        numero=rec.numero,
                        x=rec.x,
                        y=rec.y,
                        largura=rec.largura,
                        altura=rec.altura,
                        texto_bruto=rec.texto,
                        texto_diplomatico=para_diplomatico(rec.texto),
                        confianca=confianca,
                        exige_revisao=avaliacao.exige_revisao,
                        status_revisao=avaliacao.prioridade,
                    )
                )
            pagina.imagem_pre_processada = str(destino) if motor.name != "pdf_texto" and destino.is_file() else None
            pagina.preprocessamento_json = auditoria_pre or None
            metricas = (auditoria_pre or {}).get("metricas_depois") or (auditoria_pre or {}).get("metricas_antes")
            if metricas:
                pagina.qualidade_json = metricas
                pagina.qualidade_score = metricas.get("score")
                pagina.qualidade_flags = metricas.get("flags")
                if metricas.get("flags"):
                    pagina.classificacao = "problemática"
            pagina.status = "concluida"
            sessao.commit()
        return True
    except Exception as erro:
        logger.exception("Falha na página %s: %s", pagina_id, erro)
        with fabrica_sessoes(engine_bd)() as sessao:
            pagina = sessao.get(Pagina, pagina_id)
            if pagina is not None:
                pagina.status = "erro"
                sessao.commit()
        return False
