"""Interface web local: estação de revisão auditável (Marco 6 + GUI).

Usa apenas a biblioteca padrão para HTTP + Pillow (já obrigatória) para
miniaturas/overlays/recortes gerados sob demanda a partir dos caminhos
registrados no banco. O frontend é um app de página única embarcado (HTML +
CSS + JS sem dependências externas, funciona offline). Nenhum arquivo
original é alterado; overlays são gerados em memória. Bind local por padrão.
"""

from __future__ import annotations

import html
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from sqlalchemy import func, or_, select

from ..config import AppConfig
from ..database import fabrica_sessoes, inicializar_banco
from ..models import Correcao, Documento, Linha, Pagina
from ..revisao import corrigir_linha, marcar_linha
from .interface import PAGINA_HTML

HOSTS_LOCAIS = frozenset({"127.0.0.1", "localhost", "::1"})


def _sintese_documento(doc: Documento) -> dict:
    return {
        "id": doc.id,
        "nome": doc.nome_original,
        "tipo": doc.tipo_arquivo,
        "paginas": doc.numero_paginas,
        "status": doc.status,
    }


def _png_bytes(imagem) -> bytes:
    buf = io.BytesIO()
    imagem.save(buf, format="PNG")
    return buf.getvalue()


def _imagem_pagina(pagina: Pagina, tipo: str) -> bytes | None:
    from PIL import Image, ImageDraw, ImageFont

    origem = pagina.imagem_pre_processada or pagina.imagem_original
    if tipo == "original":
        origem = pagina.imagem_original or origem
    if not origem or not Path(origem).is_file():
        return None
    try:
        with Image.open(origem) as base:
            img = base.convert("RGB")
            # limita para web (economia de banda local)
            img.thumbnail((1200, 1600))
            if tipo == "overlay":
                escala_x = img.size[0] / (pagina.largura or img.size[0])
                escala_y = img.size[1] / (pagina.altura or img.size[1])
                desenho = ImageDraw.Draw(img)
                try:
                    fonte = ImageFont.load_default(size=14)
                except TypeError:
                    fonte = ImageFont.load_default()
                for lin in pagina.linhas:
                    x, y = int(lin.x * escala_x), int(lin.y * escala_y)
                    w, h = int(lin.largura * escala_x), int(lin.altura * escala_y)
                    desenho.rectangle((x, y, x + w, y + h), outline=(220, 30, 30), width=2)
                    desenho.text((x + 3, max(0, y - 14)), str(lin.numero), fill=(220, 30, 30), font=fonte)
            return _png_bytes(img)
    except (OSError, ValueError):
        return None


def _recorte_linha(linha: Linha, pagina: Pagina) -> bytes | None:
    from PIL import Image

    # prefere recorte salvo; senão gera a partir da página + bbox
    if linha.imagem_linha and Path(linha.imagem_linha).is_file():
        try:
            with Image.open(linha.imagem_linha) as img:
                img2 = img.convert("RGB")
                img2.thumbnail((800, 200))
                return _png_bytes(img2)
        except (OSError, ValueError):
            pass
    origem = pagina.imagem_pre_processada or pagina.imagem_original
    if not origem or not Path(origem).is_file():
        return None
    try:
        with Image.open(origem) as base:
            foto = base.convert("RGB")
            if linha.largura > 0 and linha.altura > 0:
                x, y, w, h = linha.x, linha.y, linha.largura, linha.altura
                # margem de 4px para não cortar descendentes
                x0, y0 = max(0, x - 4), max(0, y - 4)
                x1, y1 = min(foto.size[0], x + w + 4), min(foto.size[1], y + h + 4)
                foto = foto.crop((x0, y0, x1, y1))
            foto.thumbnail((800, 200))
            return _png_bytes(foto)
    except (OSError, ValueError):
        return None


class Manipulador(BaseHTTPRequestHandler):
    banco: Path = Path("data/ocr_historico.sqlite3")
    config_llm: dict = {"enabled": False, "model": ""}
    config_app: AppConfig | None = None

    def log_message(self, formato: str, *args: object) -> None:
        pass

    def _responder(self, codigo: int, corpo: bytes, tipo: str) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, codigo: int, dados: object) -> None:
        self._responder(codigo, json.dumps(dados, ensure_ascii=False).encode("utf-8"), "application/json")

    def do_GET(self) -> None:  # noqa: N802 - assinatura exigida pela stdlib
        rota = urlparse(self.path)
        if rota.path == "/":
            self._responder(200, PAGINA_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if rota.path == "/api/documentos":
            self._listar_documentos(parse_qs(rota.query))
            return
        if rota.path == "/api/documento":
            self._detalhar_documento(parse_qs(rota.query))
            return
        if rota.path == "/api/revisao":
            self._listar_revisao(parse_qs(rota.query))
            return
        if rota.path == "/api/resumo":
            self._resumo()
            return
        if rota.path == "/api/pagina":
            self._detalhar_pagina(parse_qs(rota.query))
            return
        if rota.path == "/api/linha":
            self._detalhar_linha(parse_qs(rota.query))
            return
        if rota.path == "/api/linha/imagem":
            self._imagem_linha(parse_qs(rota.query))
            return
        if rota.path == "/api/pagina/imagem":
            self._imagem_pagina(parse_qs(rota.query))
            return
        if rota.path == "/api/llm-estado":
            self._json(
                200, {"enabled": bool(self.config_llm.get("enabled")), "model": self.config_llm.get("model", "")}
            )
            return
        if rota.path == "/api/motores":
            self._motores()
            return
        if rota.path == "/api/paddle-vl":
            self._paddle_vl_status(parse_qs(rota.query))
            return
        if rota.path == "/api/trabalho":
            from .trabalho import FILA

            self._json(200, FILA.snapshot())
            return
        if rota.path == "/api/produtos":
            self._listar_produtos(parse_qs(rota.query))
            return
        if rota.path == "/api/download":
            self._baixar_produto(parse_qs(rota.query))
            return
        self._json(404, {"erro": "rota desconhecida"})

    def do_POST(self) -> None:  # noqa: N802 - assinatura exigida pela stdlib
        rota = urlparse(self.path)
        tamanho = int(self.headers.get("Content-Length", "0"))
        if rota.path == "/api/upload":
            self._upload(tamanho)
            return
        try:
            dados = json.loads(self.rfile.read(tamanho) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"erro": "JSON inválido"})
            return
        try:
            if rota.path == "/api/corrigir":
                corrigir_linha(
                    self.banco,
                    str(dados["linha_id"]),
                    str(dados["texto"]),
                    origem="humana",
                    usuario=str(dados.get("usuario") or "web"),
                    observacao=dados.get("observacao"),
                )
                self._json(200, {"ok": True})
                return
            if rota.path == "/api/marcar":
                marcar_linha(
                    self.banco,
                    str(dados["linha_id"]),
                    str(dados["status"]),
                    usuario=str(dados.get("usuario") or "web"),
                    observacao=dados.get("observacao"),
                )
                self._json(200, {"ok": True})
                return
            if rota.path == "/api/sugerir":
                self._sugerir(dados)
                return
            if rota.path == "/api/exportar-dataset":
                self._exportar_dataset(dados)
                return
            if rota.path == "/api/processar":
                self._enfileirar(dados)
                return
            if rota.path == "/api/paddle-vl/iniciar":
                self._paddle_vl_iniciar(dados)
                return
            if rota.path == "/api/paddle-vl/parar":
                self._paddle_vl_parar(dados)
                return
            if rota.path == "/api/cancelar":
                from .trabalho import FILA

                FILA.pedir_cancelamento()
                self._json(200, {"ok": True, **FILA.snapshot()})
                return
            self._json(404, {"erro": "rota desconhecida"})
        except (KeyError, TypeError, ValueError) as erro:
            self._json(400, {"erro": str(erro)})

    def _sessao(self):
        engine = inicializar_banco(self.banco)
        return fabrica_sessoes(engine)()

    def _motor_vl(self, dados: dict | None) -> str:
        motor = (dados or {}).get("motor") if isinstance(dados, dict) else None
        return str(motor) if motor in {"qwen3_vl", "glm_ocr", "olmocr", "deepseek_ocr2", "paddle_vl"} else "qwen3_vl"

    def _paddle_vl_status(self, qs: dict[str, list[str]] | None = None) -> None:
        if self.config_app is None:
            self._json(500, {"erro": "configuração do servidor indisponível"})
            return
        from .paddle_vl import GERENCIADOR

        motor = self._motor_vl({"motor": (qs or {}).get("motor", [""])[0]})
        if motor == "paddle_vl":
            motor = "qwen3_vl"
        self._json(200, GERENCIADOR.status(self.config_app, motor))

    def _paddle_vl_iniciar(self, dados: dict | None = None) -> None:
        if self.config_app is None:
            self._json(500, {"erro": "configuração do servidor indisponível"})
            return
        from .paddle_vl import GERENCIADOR

        motor = self._motor_vl(dados)
        if motor == "paddle_vl":
            motor = "qwen3_vl"
        gpu = bool((dados or {}).get("gpu"))
        try:
            self._json(200, GERENCIADOR.iniciar(self.config_app, motor, gpu=gpu))
        except (OSError, ValueError) as erro:
            self._json(400, {"erro": str(erro)})

    def _paddle_vl_parar(self, dados: dict | None = None) -> None:
        if self.config_app is None:
            self._json(500, {"erro": "configuração do servidor indisponível"})
            return
        from .paddle_vl import GERENCIADOR

        motor = self._motor_vl(dados)
        self._json(200, GERENCIADOR.parar(self.config_app, motor))

    def _motores(self) -> None:
        from ..reconhecimento.factory import listar_motores, resolver_engine

        try:
            efetivo, aviso = resolver_engine("auto")
        except ValueError as erro:
            efetivo, aviso = "", str(erro)
        self._json(200, {"motores": listar_motores(self.config_app), "recomendado": efetivo, "aviso": aviso})

    def _enfileirar(self, dados: dict) -> None:
        from .trabalho import FILA

        if self.config_app is None:
            self._json(500, {"erro": "configuração do servidor indisponível"})
            return
        ids_brutos = dados.get("ids") or []
        ids = [str(i) for i in ids_brutos] if isinstance(ids_brutos, list) else []
        motor = str(dados.get("engine") or "").strip() or None
        try:
            snap = FILA.iniciar(
                self.config_app,
                ids=ids or None,
                engine=motor,
                forcar=bool(dados.get("forcar")),
                retry_failed=bool(dados.get("retry_failed", True)),
            )
        except RuntimeError as erro:
            self._json(409, {"erro": str(erro)})
            return
        self._json(200, {"ok": True, "trabalho": snap})

    def _pasta_produtos(self, doc: Documento) -> Path | None:
        if self.config_app is None:
            return None
        from ..pipeline import _nome_base

        pasta = Path(self.config_app.saida) / _nome_base(doc.nome_original)
        return pasta if pasta.is_dir() else None

    def _listar_produtos(self, qs: dict[str, list[str]]) -> None:
        doc_id = (qs.get("id") or [""])[0]
        if not doc_id:
            self._json(400, {"erro": "parâmetro id é obrigatório"})
            return
        with self._sessao() as sessao:
            doc = sessao.get(Documento, doc_id)
            if doc is None:
                self._json(404, {"erro": "documento não encontrado"})
                return
            pasta = self._pasta_produtos(doc)
            arquivos: list[dict[str, object]] = []
            if pasta is not None:
                for item in sorted(pasta.iterdir()):
                    if item.is_file():
                        arquivos.append({"nome": item.name, "bytes": item.stat().st_size})
            self._json(200, {"id": doc.id, "pasta": str(pasta) if pasta else None, "arquivos": arquivos})

    def _baixar_produto(self, qs: dict[str, list[str]]) -> None:
        doc_id = (qs.get("id") or [""])[0]
        nome = (qs.get("arquivo") or [""])[0]
        if not doc_id or not nome:
            self._json(400, {"erro": "id e arquivo são obrigatórios"})
            return
        if Path(nome).name != nome or "/" in nome or "\\" in nome or nome in {".", ".."}:
            self._json(400, {"erro": "nome de arquivo inválido"})
            return
        with self._sessao() as sessao:
            doc = sessao.get(Documento, doc_id)
            if doc is None:
                self._json(404, {"erro": "documento não encontrado"})
                return
            pasta = self._pasta_produtos(doc)
        if pasta is None:
            self._json(404, {"erro": "nenhum produto exportado ainda"})
            return
        alvo = (pasta / nome).resolve()
        try:
            alvo.relative_to(pasta.resolve())
        except ValueError:
            self._json(400, {"erro": "caminho fora da pasta de produtos"})
            return
        if not alvo.is_file():
            self._json(404, {"erro": "arquivo não encontrado"})
            return
        dados = alvo.read_bytes()
        tipo = "application/octet-stream"
        if alvo.suffix.lower() == ".pdf":
            tipo = "application/pdf"
        elif alvo.suffix.lower() in {".txt", ".md", ".csv", ".tsv", ".xml", ".html", ".json"}:
            tipo = "text/plain; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Content-Disposition", f'attachment; filename="{alvo.name}"')
        self.end_headers()
        self.wfile.write(dados)

    def _upload(self, tamanho: int) -> None:
        from ..ingestao import ingerir_entrada
        from ..ingestao.arquivos import tipo_por_extensao
        from .upload import (
            MAX_ARQUIVO_BYTES,
            MAX_TOTAL_BYTES,
            PacoteMultipart,
            destino_upload,
            extrair_boundary,
            nome_seguro,
            parse_multipart,
        )

        config = self.config_app
        if config is None:
            self._json(500, {"erro": "configuração do servidor indisponível"})
            return
        if tamanho <= 0:
            self._json(400, {"erro": "corpo vazio; envie multipart/form-data"})
            return
        if tamanho > MAX_TOTAL_BYTES:
            self.close_connection = True
            self._json(413, {"erro": f"envio excede o limite de {MAX_TOTAL_BYTES // 1024 // 1024}MB"})
            return
        try:
            boundary = extrair_boundary(self.headers.get("Content-Type", ""))
            pacote: PacoteMultipart = parse_multipart(self.rfile.read(tamanho), boundary)
        except ValueError as erro:
            self._json(400, {"erro": f"multipart inválido: {erro}"})
            return
        if not pacote.arquivos:
            self._json(400, {"erro": "nenhum arquivo no envio"})
            return
        destino_dir = Path(config.entrada) / "upload_web"
        try:
            destino_dir.mkdir(parents=True, exist_ok=True)
        except OSError as erro:
            self._json(
                500,
                {"erro": f"pasta de entrada inacessível ({destino_dir}): {erro}. Ajuste 'entrada' no YAML."},
            )
            return
        arquivos: list[dict[str, object]] = []
        for recebido in pacote.arquivos:
            try:
                seguro = nome_seguro(recebido.nome)
            except ValueError as erro:
                arquivos.append({"nome": recebido.nome, "status": "erro", "motivo": str(erro)})
                continue
            if len(recebido.dados) == 0:
                arquivos.append({"nome": seguro, "status": "erro", "motivo": "arquivo vazio"})
                continue
            if len(recebido.dados) > MAX_ARQUIVO_BYTES:
                arquivos.append({"nome": seguro, "status": "erro", "motivo": "excede 50MB por arquivo"})
                continue
            if tipo_por_extensao(Path(seguro).suffix) is None:
                arquivos.append({"nome": seguro, "status": "erro", "motivo": "tipo não suportado"})
                continue
            alvo = destino_upload(destino_dir, seguro, recebido.dados)
            try:
                with open(alvo, "xb") as fh:
                    fh.write(recebido.dados)
            except FileExistsError:
                try:
                    if alvo.read_bytes() != recebido.dados:
                        # corrida: mesmo nome, conteúdo distinto → novo sufixo
                        alvo = destino_upload(destino_dir, f"{alvo.stem}_dup{alvo.suffix}", recebido.dados)
                        with open(alvo, "xb") as fh:
                            fh.write(recebido.dados)
                except OSError as erro:
                    arquivos.append({"nome": seguro, "status": "erro", "motivo": f"falha de escrita: {erro}"})
                    continue
            except OSError as erro:
                arquivos.append({"nome": seguro, "status": "erro", "motivo": f"falha de escrita: {erro}"})
                continue
            arquivos.append({"nome": alvo.name, "status": "ok", "bytes": len(recebido.dados)})
        try:
            resumo = ingerir_entrada(destino_dir, config)
        except OSError as erro:
            self._json(500, {"erro": f"falha ao registrar upload: {erro}"})
            return
        resposta: dict[str, object] = {
            "ok": True,
            "arquivos": arquivos,
            "novos": resumo.novos,
            "pulados": resumo.pulados,
            "erros": resumo.erros,
            "ids": resumo.documentos,
        }
        if pacote.campos.get("processar", "").strip().lower() in {"1", "true", "sim"} and resumo.documentos:
            from .trabalho import FILA

            motor = pacote.campos.get("engine", "").strip() or None
            try:
                resposta["trabalho"] = FILA.iniciar(
                    config,
                    ids=list(resumo.documentos),
                    engine=motor,
                    forcar=False,
                    retry_failed=True,
                )
            except RuntimeError as erro:
                resposta["processar_erro"] = str(erro)
        self._json(200, resposta)

    def _listar_documentos(self, qs: dict[str, list[str]]) -> None:
        with self._sessao() as sessao:
            consulta = select(Documento).order_by(Documento.criado_em)
            status = (qs.get("status") or [""])[0]
            busca = (qs.get("busca") or [""])[0].strip()
            if status:
                consulta = consulta.where(Documento.status == status)
            if busca:
                consulta = consulta.where(
                    or_(
                        Documento.nome_original.contains(busca),
                        Documento.caminho_original.contains(busca),
                    )
                )
            documentos = list(sessao.scalars(consulta))
            total = sessao.scalar(select(func.count(Documento.id))) or 0
        self._json(200, {"total": total, "documentos": [_sintese_documento(d) for d in documentos]})

    def _listar_revisao(self, qs: dict[str, list[str]]) -> None:
        from ..revisao import listar_fila

        try:
            status = (qs.get("status") or [""])[0] or None
            itens = listar_fila(self.banco, status=status, limite=int((qs.get("limite") or ["100"])[0] or 100))
            documento = (qs.get("documento") or [""])[0]
            if documento:
                itens = [item for item in itens if item.documento_id == documento]
            texto_q = (qs.get("q") or [""])[0].strip().lower()
            if texto_q:
                itens = [i for i in itens if texto_q in (i.texto_diplomatico or "").lower()]
            if (qs.get("baixa") or [""])[0] in {"1", "true", "sim"}:
                itens = [i for i in itens if (i.confianca is None or i.confianca < 0.82)]
            self._json(
                200,
                {
                    "linhas": [
                        {
                            "id": item.linha_id,
                            "numero": item.numero,
                            "pagina": item.pagina,
                            "documento_id": item.documento_id,
                            "documento": item.documento,
                            "confianca": item.confianca,
                            "texto": item.texto_diplomatico,
                            "texto_bruto": item.texto_bruto,
                            "normalizado": item.texto_normalizado,
                            "status": item.status,
                        }
                        for item in itens
                    ]
                },
            )
        except ValueError as erro:
            self._json(400, {"erro": str(erro)})

    def _resumo(self) -> None:
        """Agregados para o painel inicial: documentos, fila e atividade."""
        with self._sessao() as sessao:
            total_docs = sessao.scalar(select(func.count(Documento.id))) or 0
            por_status = dict(
                sessao.execute(select(Documento.status, func.count(Documento.id)).group_by(Documento.status)).all()
            )
            total_linhas = sessao.scalar(select(func.count(Linha.id))) or 0
            fila = (
                sessao.scalar(select(func.count(Linha.id)).where(Linha.exige_revisao.is_(True))) or 0
            )
            baixa = (
                sessao.scalar(
                    select(func.count(Linha.id)).where(
                        Linha.exige_revisao.is_(True), or_(Linha.confianca.is_(None), Linha.confianca < 0.82)
                    )
                )
                or 0
            )
            revisadas = (
                sessao.scalar(select(func.count(Linha.id)).where(Linha.status_revisao == "revisada")) or 0
            )
            correcoes = sessao.scalar(select(func.count(Correcao.id))) or 0
        self._json(
            200,
            {
                "documentos": {"total": total_docs, "por_status": por_status},
                "linhas": {"total": total_linhas, "fila": fila, "baixa_confianca": baixa, "revisadas": revisadas},
                "correcoes": correcoes,
            },
        )

    def _detalhar_pagina(self, qs: dict[str, list[str]]) -> None:
        """Página + linhas com caixas e estado de revisão (base do visor clicável)."""
        pid = (qs.get("id") or [""])[0]
        if not pid:
            self._json(400, {"erro": "parâmetro id é obrigatório"})
            return
        with self._sessao() as sessao:
            pagina = sessao.get(Pagina, pid)
            if pagina is None:
                self._json(404, {"erro": "página não encontrada"})
                return
            linhas = (
                sessao.scalars(select(Linha).where(Linha.pagina_id == pid).order_by(Linha.numero)).all()
            )
            self._json(
                200,
                {
                    "id": pagina.id,
                    "numero": pagina.numero,
                    "status": pagina.status,
                    "largura": pagina.largura,
                    "altura": pagina.altura,
                    "linhas": [
                        {
                            "id": lin.id,
                            "numero": lin.numero,
                            "x": lin.x,
                            "y": lin.y,
                            "largura": lin.largura,
                            "altura": lin.altura,
                            "confianca": lin.confianca,
                            "status": lin.status_revisao,
                            "exige_revisao": bool(lin.exige_revisao),
                            "texto": lin.texto_diplomatico,
                        }
                        for lin in linhas
                    ],
                },
            )

    def _detalhar_linha(self, qs: dict[str, list[str]]) -> None:
        lid = (qs.get("id") or [""])[0]
        if not lid:
            self._json(400, {"erro": "parâmetro id é obrigatório"})
            return
        with self._sessao() as sessao:
            linha = sessao.get(Linha, lid)
            if linha is None:
                self._json(404, {"erro": "linha não encontrada"})
                return
            sugestoes = sessao.scalars(
                select(Correcao)
                .where(Correcao.linha_id == lid, Correcao.origem == "llm_sugerido")
                .order_by(Correcao.criado_em.desc())
            ).all()
            historico = sessao.scalars(
                select(Correcao).where(Correcao.linha_id == lid).order_by(Correcao.criado_em.desc()).limit(20)
            ).all()
            self._json(
                200,
                {
                    "id": linha.id,
                    "texto_bruto": linha.texto_bruto,
                    "texto_diplomatico": linha.texto_diplomatico,
                    "texto_normalizado": linha.texto_normalizado,
                    "confianca": linha.confianca,
                    "status": linha.status_revisao,
                    "sugestoes": [
                        {"texto": s.texto_corrigido, "data": s.criado_em.isoformat() if s.criado_em else None}
                        for s in sugestoes
                    ],
                    "historico": [
                        {
                            "anterior": c.texto_anterior,
                            "corrigido": c.texto_corrigido,
                            "origem": c.origem,
                            "usuario": c.usuario,
                            "data": c.criado_em.isoformat() if c.criado_em else None,
                        }
                        for c in historico
                    ],
                },
            )

    def _imagem_linha(self, qs: dict[str, list[str]]) -> None:
        lid = (qs.get("id") or [""])[0]
        if not lid:
            self._json(400, {"erro": "parâmetro id é obrigatório"})
            return
        with self._sessao() as sessao:
            linha = sessao.get(Linha, lid)
            if linha is None:
                self._json(404, {"erro": "linha não encontrada"})
                return
            pagina = sessao.get(Pagina, linha.pagina_id)
            dados_img = _recorte_linha(linha, pagina) if pagina else None
        if dados_img is None:
            self._json(404, {"erro": "imagem da linha indisponível"})
            return
        self._responder(200, dados_img, "image/png")

    def _imagem_pagina(self, qs: dict[str, list[str]]) -> None:
        pid = (qs.get("id") or [""])[0]
        tipo = (qs.get("tipo") or ["overlay"])[0]
        if not pid:
            self._json(400, {"erro": "parâmetro id é obrigatório"})
            return
        if tipo not in {"original", "pre", "overlay"}:
            self._json(400, {"erro": "tipo deve ser original, pre ou overlay"})
            return
        with self._sessao() as sessao:
            pagina = sessao.get(Pagina, pid)
            if pagina is None:
                self._json(404, {"erro": "página não encontrada"})
                return
            dados_img = _imagem_pagina(pagina, tipo)
        if dados_img is None:
            self._json(404, {"erro": "imagem da página indisponível"})
            return
        self._responder(200, dados_img, "image/png")

    def _sugerir(self, dados: dict) -> None:
        if not self.config_llm.get("enabled"):
            self._json(400, {"erro": "LLM desabilitado (llm.enabled=false). Ative em configs/llm_local.yaml."})
            return
        from ..posprocessamento.llm_revisor import sugerir_linhas

        lid = str(dados.get("linha_id") or "")
        if not lid:
            self._json(400, {"erro": "linha_id é obrigatório"})
            return
        try:
            res = sugerir_linhas(
                self.banco,
                [lid],
                base_url=str(self.config_llm.get("base_url") or "http://127.0.0.1:11434"),
                model=str(self.config_llm.get("model") or "qwen2.5:7b-instruct"),
                timeout_seconds=int(self.config_llm.get("timeout") or 120),
                usuario=str(dados.get("usuario") or "web"),
            )[0]
        except Exception as exc:  # noqa: BLE001
            self._json(502, {"erro": f"Falha ao consultar LLM local: {exc}"})
            return
        if res.sugestao is None:
            self._json(502, {"erro": res.erro or "LLM não retornou sugestão válida"})
            return
        self._json(
            200,
            {
                "ok": True,
                "sugestao": res.sugestao.sugestao,
                "tipo": res.sugestao.tipo,
                "justificativa": res.sugestao.justificativa_curta,
                "confianca": res.sugestao.confianca,
            },
        )

    def _exportar_dataset(self, dados: dict) -> None:
        from ..treinamento.dataset import exportar_linhas_revisadas, iniciar_dataset

        colecao = str(dados.get("colecao") or "revisao_web").strip() or "revisao_web"
        try:
            base = iniciar_dataset(colecao, Path("data/treinamento"))
            resultado = exportar_linhas_revisadas(self.banco, base)
        except (OSError, ValueError) as exc:
            self._json(400, {"erro": str(exc)})
            return
        self._json(
            200,
            {"ok": True, "colecao": colecao, "adicionadas": resultado.adicionadas, "ignoradas": resultado.ignoradas},
        )

    def _detalhar_documento(self, qs: dict[str, list[str]]) -> None:
        doc_id = (qs.get("id") or [""])[0]
        if not doc_id:
            self._json(400, {"erro": "parâmetro id é obrigatório"})
            return
        with self._sessao() as sessao:
            doc = sessao.scalar(select(Documento).where(Documento.id == doc_id))
            if doc is None:
                self._json(404, {"erro": "documento não encontrado"})
                return
            paginas = sessao.scalars(select(Pagina).where(Pagina.documento_id == doc.id).order_by(Pagina.numero)).all()
            resposta = {
                "id": doc.id,
                "nome": html.escape(doc.nome_original),
                "tipo": doc.tipo_arquivo,
                "status": doc.status,
                "sha256": doc.sha256,
                "erro": doc.erro,
                "paginas": [
                    {"id": p.id, "numero": p.numero, "status": p.status, "largura": p.largura, "altura": p.altura}
                    for p in paginas
                ],
            }
        self._json(200, resposta)


def servir(config: AppConfig, host: str = "127.0.0.1", porta: int = 7860, expor_rede: bool = False) -> None:
    """Inicia o painel local. Escuta 0.0.0.0 somente com `expor_rede=True`."""
    if host not in HOSTS_LOCAIS and not expor_rede:
        raise ValueError(f"Host {host!r} não é local; use --expor-rede para expor na rede explicitamente.")
    Manipulador.banco = Path(config.banco)
    Manipulador.config_app = config
    Manipulador.config_llm = {
        "enabled": bool(config.llm.enabled),
        "model": config.llm.model,
        "base_url": config.llm.base_url,
        "timeout": config.llm.timeout_seconds,
    }
    servidor = ThreadingHTTPServer((host, porta), Manipulador)
    print(f"Painel local em http://{host}:{porta} (Ctrl+C para encerrar)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        from .paddle_vl import GERENCIADOR

        if Manipulador.config_app is not None:
            GERENCIADOR.parar(Manipulador.config_app)
        servidor.server_close()
