"""Fine-tuning Kraken a partir de manifest.jsonl — CPU-first, sem download silencioso."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TreinoResultado:
    comando: list[str]
    log_path: Path | None
    modelo_saida: Path
    aviso: str | None


def _validar_estrutura(caminho: Path) -> list[str]:
    base = Path(caminho)
    manifesto = base / "manifest.jsonl" if base.is_dir() else base
    if not manifesto.is_file():
        return [f"manifest.jsonl não encontrado: {manifesto}"]
    # valida rapidamente com dataset.py
    from .dataset import validar_dataset

    return validar_dataset(manifesto)


def preparar_treino(
    dataset: Path | str,
    saida: Path | str | None = None,
    modelo_base: Path | str | None = None,
    epocas: int = 20,
    taxa_aprendizado: float = 0.0001,
    tamanho_lote: int = 8,
    dispositivo: str = "cpu",
    dry_run: bool = False,
) -> TreinoResultado:
    """Monta o comando Kraken (`ketos train`) sem executar rede.

    - Nunca baixa modelo: `modelo_base` deve ser caminho local ou None (treino do zero).
    - `dataset` pode ser pasta ground_truth/ ou manifest.jsonl; splits devem já existir
      em treino/validacao/ ou será usado o manifesto único.
    - `dispositivo` é sempre cpu por padrão; gpu só se explicitamente solicitado.
    """
    base = Path(dataset)
    manifesto = base / "manifest.jsonl" if base.is_dir() else base
    if not manifesto.is_file():
        raise ValueError(f"Dataset não encontrado: {manifesto}")
    erros = _validar_estrutura(base if base.is_dir() else manifesto.parent)
    if erros:
        raise ValueError("Dataset inválido: " + "; ".join(erros[:5]))

    # determina pastas de treino/validação
    if base.is_dir() and (base.parent / "treino" / "manifest.jsonl").is_file():
        treino_manifest = base.parent / "treino" / "manifest.jsonl"
        valid_manifest = base.parent / "validacao" / "manifest.jsonl"
    elif base.is_dir() and (base / "treino" / "manifest.jsonl").is_file():
        treino_manifest = base / "treino" / "manifest.jsonl"
        valid_manifest = base / "validacao" / "manifest.jsonl"
    else:
        treino_manifest = manifesto
        valid_manifest = None

    saida_path = Path(saida) if saida else (Path("data/modelos/kraken") / "modelo_treinado.mlmodel")
    saida_path.parent.mkdir(parents=True, exist_ok=True)

    comando: list[str] = []
    ketos = shutil.which("ketos")
    kraken = shutil.which("kraken")
    if ketos:
        comando = [ketos, "train", str(treino_manifest)]
        if valid_manifest and valid_manifest.is_file():
            comando += ["--valid", str(valid_manifest)]
        comando += ["--output", str(saida_path), "--epochs", str(epocas), "--learning-rate", str(taxa_aprendizado)]
        if dispositivo == "cpu":
            comando += ["--device", "cpu"]
        if modelo_base:
            mb = Path(modelo_base)
            if not mb.is_file():
                raise ValueError(f"Modelo base não encontrado: {mb}")
            comando += ["--load", str(mb)]
        comando += ["--batch-size", str(tamanho_lote)]
    elif kraken:
        # kraken >=5 usa `kraken train`
        comando = [kraken, "train", str(treino_manifest)]
        if valid_manifest and valid_manifest.is_file():
            comando += ["--valid", str(valid_manifest)]
        comando += ["-o", str(saida_path), "--epochs", str(epocas)]
        if modelo_base:
            mb = Path(modelo_base)
            if not mb.is_file():
                raise ValueError(f"Modelo base não encontrado: {mb}")
            comando += ["--load", str(mb)]
    else:
        # dry-run ou host sem kraken: devolve comando descritivo
        comando = [
            "ketos",
            "train",
            str(treino_manifest),
            "--output",
            str(saida_path),
            "--epochs",
            str(epocas),
        ]
        if modelo_base:
            comando += ["--load", str(modelo_base)]

    aviso: str | None = None
    if not ketos and not kraken:
        aviso = (
            "Kraken/ketos não encontrado no PATH; comando apenas preparado (dry-run). "
            "Instale com 'pip install kraken'."
        )

    return TreinoResultado(comando=comando, log_path=None, modelo_saida=saida_path, aviso=aviso)


def executar_treino(resultado: TreinoResultado, dry_run: bool = False) -> TreinoResultado:
    """Executa o comando preparado, registrando log; dry_run apenas valida."""
    if dry_run:
        return resultado
    if not resultado.comando:
        raise ValueError("Comando vazio")
    exe = resultado.comando[0]
    if shutil.which(exe) is None:
        raise FileNotFoundError(f"Executável não encontrado: {exe}. {resultado.aviso or ''}")
    log_path = resultado.modelo_saida.with_suffix(".log")
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"$ {' '.join(resultado.comando)}\n")
        proc = subprocess.run(resultado.comando, stdout=log, stderr=subprocess.STDOUT, check=False, timeout=7200)
        if proc.returncode != 0:
            raise RuntimeError(f"Treino falhou (código {proc.returncode}); veja {log_path}")
    return TreinoResultado(
        comando=resultado.comando,
        log_path=log_path,
        modelo_saida=resultado.modelo_saida,
        aviso=resultado.aviso,
    )


def avaliar_modelo(
    modelo: Path | str,
    teste_manifest: Path | str,
    relatorio: Path | str | None = None,
) -> dict:
    """Avalia modelo Kraken sobre conjunto de teste (CER/WER por linha)."""
    modelo_path = Path(modelo)
    manifesto = Path(teste_manifest)
    if manifesto.is_dir():
        manifesto = manifesto / "manifest.jsonl"
    if not modelo_path.is_file():
        raise ValueError(f"Modelo não encontrado: {modelo_path}")
    if not manifesto.is_file():
        raise ValueError(f"Manifesto de teste não encontrado: {manifesto}")
    # avalia via CER/WER próprios, comparando predição (se kraken disponível) ou apenas registrando estrutura
    from ..avaliacao.comparacao import calcular_cer, calcular_wer

    registros = [
        json.loads(linha)
        for linha in manifesto.read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]
    # sem kraken, retorna métrica vazia mas auditável
    tem_kraken = shutil.which("kraken") is not None or shutil.which("ketos") is not None
    detalhe = {
        "modelo": str(modelo_path),
        "teste": str(manifesto),
        "linhas": len(registros),
        "kraken_disponivel": tem_kraken,
    }
    if not tem_kraken:
        detalhe["aviso"] = "Kraken não instalado; avaliação requer modelo carregado. Métrica não calculada."
        return detalhe
    # quando kraken disponível, tenta predição linha a linha
    try:
        from kraken.lib import models as km  # type: ignore[import-not-found]
        from PIL import Image

        net = km.load_any(str(modelo_path))
        from kraken import rpred  # type: ignore[import-not-found]

        cers: list[float] = []
        wers: list[float] = []
        for reg in registros:
            img_rel = reg.get("imagem", "")
            transc_rel = reg.get("transcricao", "")
            base_dir = manifesto.parent
            img_path = base_dir / img_rel if not Path(img_rel).is_absolute() else Path(img_rel)
            trans_path = base_dir / transc_rel if not Path(transc_rel).is_absolute() else Path(transc_rel)
            if not img_path.is_file() or not trans_path.is_file():
                continue
            ref = trans_path.read_text(encoding="utf-8").strip()
            with Image.open(img_path) as im:
                preds = list(rpred.rpred(net, im))  # type: ignore[attr-defined]
                hyp = str(preds[0].prediction if hasattr(preds[0], "prediction") else preds[0]) if preds else ""
            cer = calcular_cer(ref, hyp)
            wer = calcular_wer(ref, hyp)
            cers.append(cer.valor)
            wers.append(wer.valor)
        detalhe["cer_medio"] = sum(cers) / len(cers) if cers else None
        detalhe["wer_medio"] = sum(wers) / len(wers) if wers else None
        detalhe["linhas_avaliadas"] = len(cers)
    except Exception as exc:  # noqa: BLE001
        detalhe["erro"] = str(exc)
    if relatorio:
        rp = Path(relatorio)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(detalhe, ensure_ascii=False, indent=2), encoding="utf-8")
    return detalhe
