"""Criação e validação de dataset de linhas no formato manifest.jsonl."""

from __future__ import annotations

import json
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select

from ..database import fabrica_sessoes, inicializar_banco
from ..models import Documento, Linha, Pagina


@dataclass(frozen=True)
class ResultadoDataset:
    caminho: Path
    adicionadas: int
    ignoradas: int


def iniciar_dataset(nome: str, raiz: Path | str) -> Path:
    """Cria estrutura ground_truth/ de uma coleção sem sobrescrever arquivos."""
    nome_sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    nome_limpo = "".join(c for c in nome_sem_acento.strip() if c.isalnum() or c in "_- ").strip().replace(" ", "_")
    if not nome_limpo:
        raise ValueError("nome da coleção não pode ser vazio")
    base = Path(raiz) / nome_limpo / "ground_truth"
    for subpasta in ("imagens", "transcricoes"):
        (base / subpasta).mkdir(parents=True, exist_ok=True)
    manifesto = base / "manifest.jsonl"
    if not manifesto.exists():
        manifesto.write_text("", encoding="utf-8")
    readme = base / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Ground truth\n\nDataset por linhas. Não misture documentos entre treino, validação e teste.\n",
            encoding="utf-8",
        )
    return base


def exportar_linhas_revisadas(
    banco: Path | str,
    destino: Path | str,
    apenas_status: tuple[str, ...] = ("treinamento",),
) -> ResultadoDataset:
    """Copia imagem/texto de linhas marcadas e acrescenta registros idempotentes."""
    base = Path(destino)
    base.mkdir(parents=True, exist_ok=True)
    imagens = base / "imagens"
    transcricoes = base / "transcricoes"
    imagens.mkdir(exist_ok=True)
    transcricoes.mkdir(exist_ok=True)
    manifesto = base / "manifest.jsonl"
    existentes: set[str] = set()
    if manifesto.exists():
        for linha in manifesto.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                try:
                    existentes.add(str(json.loads(linha)["id"]))
                except (json.JSONDecodeError, KeyError):
                    continue
    engine = inicializar_banco(banco)
    adicionadas = 0
    ignoradas = 0
    with fabrica_sessoes(engine)() as sessao:
        consulta = (
            select(Linha, Pagina, Documento)
            .join(Pagina, Linha.pagina_id == Pagina.id)
            .join(Documento, Pagina.documento_id == Documento.id)
            .where(Linha.status_revisao.in_(apenas_status))
            .order_by(Documento.nome_original, Pagina.numero, Linha.numero)
        )
        registros = sessao.execute(consulta).all()
    with manifesto.open("a", encoding="utf-8") as arquivo_manifesto:
        for linha, pagina, documento in registros:
            identificador = f"{Path(documento.nome_original).stem}_p{pagina.numero:03d}_l{linha.numero:03d}"
            if identificador in existentes:
                ignoradas += 1
                continue
            origem = linha.imagem_linha or pagina.imagem_pre_processada or pagina.imagem_original
            if not origem or not Path(origem).is_file() or not linha.texto_diplomatico.strip():
                ignoradas += 1
                continue
            nome_imagem = f"{identificador}{Path(origem).suffix.lower() or '.png'}"
            destino_imagem = imagens / nome_imagem
            shutil.copy2(origem, destino_imagem)
            destino_texto = transcricoes / f"{identificador}.gt.txt"
            destino_texto.write_text(linha.texto_diplomatico, encoding="utf-8")
            manifesto_record: dict[str, Any] = {
                "id": identificador,
                "imagem": f"imagens/{nome_imagem}",
                "transcricao": f"transcricoes/{identificador}.gt.txt",
                "documento": Path(documento.nome_original).stem,
                "pagina": pagina.numero,
                "escrevente": "desconhecido",
                "periodo": "desconhecido",
                "revisado": True,
            }
            arquivo_manifesto.write(json.dumps(manifesto_record, ensure_ascii=False) + "\n")
            adicionadas += 1
    return ResultadoDataset(base, adicionadas, ignoradas)


def validar_dataset(caminho: Path | str) -> list[str]:
    """Valida referências, JSONL e transcrições; retorna erros, sem corrigir nada."""
    base = Path(caminho)
    manifesto = base / "manifest.jsonl" if base.is_dir() else base
    if not manifesto.is_file():
        return [f"manifest.jsonl não encontrado: {manifesto}"]
    erros: list[str] = []
    ids: set[str] = set()
    for numero, linha in enumerate(manifesto.read_text(encoding="utf-8").splitlines(), start=1):
        if not linha.strip():
            continue
        try:
            registro = json.loads(linha)
        except json.JSONDecodeError as erro:
            erros.append(f"linha {numero}: JSON/schema inválido ({erro})")
            continue
        if not isinstance(registro, dict):
            erros.append(f"linha {numero}: o registro deve ser um objeto JSON")
            continue
        identificador = str(registro.get("id") or "")
        if not identificador:
            erros.append(f"linha {numero}: campo id ausente")
            continue
        imagem_rel = registro.get("imagem")
        transcricao_rel = registro.get("transcricao")
        if not isinstance(imagem_rel, str):
            erros.append(f"linha {numero}: campo imagem ausente")
            imagem = manifesto.parent / "<imagem-ausente>"
        else:
            imagem = manifesto.parent / imagem_rel
        if not isinstance(transcricao_rel, str):
            erros.append(f"linha {numero}: campo transcricao ausente")
            transcricao = manifesto.parent / "<transcricao-ausente>"
        else:
            transcricao = manifesto.parent / transcricao_rel
        if identificador in ids:
            erros.append(f"linha {numero}: id duplicado {identificador}")
        ids.add(identificador)
        if not imagem.is_file():
            erros.append(f"linha {numero}: imagem não encontrada {imagem}")
        if not transcricao.is_file():
            erros.append(f"linha {numero}: transcrição não encontrada {transcricao}")
        elif not transcricao.read_text(encoding="utf-8").strip():
            erros.append(f"linha {numero}: transcrição vazia {transcricao}")
        if registro.get("revisado") is not True:
            erros.append(f"linha {numero}: registro precisa estar revisado=true")
    return erros
