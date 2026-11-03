"""Diagnóstico local, sem instalar ou baixar componentes."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import AppConfig
from .database import inicializar_banco


@dataclass(frozen=True)
class ItemDiagnostico:
    nome: str
    estado: str
    detalhe: str


def _comando_versao(comando: str, argumentos: list[str] | None = None) -> str | None:
    executavel = shutil.which(comando)
    if not executavel:
        return None
    try:
        resultado = subprocess.run(
            [executavel, *(argumentos or ["--version"])],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except OSError:
        return None
    texto = (resultado.stdout or resultado.stderr).strip().splitlines()
    return texto[0] if resultado.returncode == 0 and texto else None


def _diagnosticar_vlm(
    nome: str,
    base_url: str,
    modelo: str,
    gguf_candidatos: list[Path],
    script: str,
    binario: str = "llama-server",
    dica_modelo: str | None = None,
) -> ItemDiagnostico:
    base = base_url.rstrip("/")
    tem_binario = shutil.which(binario) is not None
    tem_modelo = any(p.is_file() or p.is_dir() for p in gguf_candidatos)
    servidor_ok = False
    servidos: list[str] = []
    try:
        req = urllib.request.Request(base + "/v1/models", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status < 500:
                servidor_ok = True
                try:
                    dados = json.loads(resp.read().decode("utf-8"))
                    for origem in (dados.get("models"), dados.get("data")):
                        if isinstance(origem, list):
                            for item in origem:
                                if isinstance(item, dict) and isinstance(item.get("id"), str):
                                    servidos.append(item["id"])
                except Exception:  # noqa: BLE001
                    pass
    except Exception:  # noqa: BLE001
        pass
    if not servidor_ok:
        try:
            req = urllib.request.Request(base + "/health", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                servidor_ok = resp.status < 500
        except Exception:  # noqa: BLE001
            servidor_ok = False
    if servidor_ok:
        baixo = " ".join(servidos).lower()
        parece_vl = modelo in servidos or any(p in baixo for p in ("qwen", "glm", "deepseek", "vl-", "olmocr"))
        if parece_vl or not servidos:
            return ItemDiagnostico(nome, "OK", f"servidor ativo em {base} ({modelo})")
        return ItemDiagnostico(
            nome, "AVISO",
            f"servidor em {base} serve {servidos[0]!r}, sem visão/VL — suba {nome} p/ transcrever",
        )
    if not tem_binario and not tem_modelo:
        return ItemDiagnostico(nome, "INDISPONÍVEL", f"{binario} e pesos ausentes; lote continua com tesseract/kraken")
    pendencias = []
    if not tem_binario:
        pendencias.append(f"instale o {binario}")
    if not tem_modelo:
        pendencias.append(dica_modelo or f"baixe o GGUF (ver {script})")
    if tem_binario and tem_modelo:
        pendencias.append(f"suba com 'bash {script}' ({base})")
    return ItemDiagnostico(nome, "AVISO", "; ".join(pendencias))


def _diagnosticar_qwen3vl(config: AppConfig) -> ItemDiagnostico:
    return _diagnosticar_vlm(
        "Qwen3-VL 4B", config.qwen3vl.base_url, config.qwen3vl.model,
        [Path("/mnt/RESERVA2/models/OCR/Qwen3VL-4B-Instruct-Q4_K_M.gguf"),
         Path("/mnt/RESERVA2/models/OCR/Qwen3VL-4B-Instruct-Q8_0.gguf"),
         Path("/mnt/RESERVA2/models/OCR/Qwen3VL-8B-Instruct-Q4_K_M.gguf")],
        "scripts/servidor_qwen3vl_4b.sh",
    )


def _diagnosticar_glmocr(config: AppConfig) -> ItemDiagnostico:
    return _diagnosticar_vlm(
        "GLM-OCR", config.glmocr.base_url, config.glmocr.model,
        [Path("/mnt/RESERVA2/models/OCR/GLM-OCR/GLM-OCR-Q4_K_M.gguf"),
         Path("/mnt/RESERVA2/models/OCR/Qwen3VL-8B-Instruct-Q4_K_M.gguf")],
        "scripts/servidor_glmocr.sh",
    )


def _diagnosticar_olmoc(config: AppConfig) -> ItemDiagnostico:
    """Estado do olmOCR: binário, GGUF local e servidor — sem baixar nada."""
    return _diagnosticar_vlm(
        "olmOCR", config.olmocr.base_url, config.olmocr.model,
        [Path("/mnt/RESERVA2/models/OCR/olmOCR-2-7B/olmOCR-2-7B-Q4_K_M.gguf"),
         Path("/mnt/RESERVA2/models/OCR/Qwen3VL-8B-Instruct-Q4_K_M.gguf")],
        "scripts/servidor_olmocr.sh",
    )


def _diagnosticar_deepseekocr2(config: AppConfig) -> ItemDiagnostico:
    """Estado do DeepSeek-OCR-2: llama-server, GGUF local e servidor — sem baixar nada."""
    return _diagnosticar_vlm(
        "DeepSeek-OCR-2",
        config.deepseekocr2.base_url,
        config.deepseekocr2.model,
        [
            Path("/mnt/RESERVA2/models/OCR/DeepSeek-OCR-2/deepseek-ocr-2-Q4_K_M.gguf"),
            Path("/mnt/RESERVA2/models/OCR/DeepSeek-OCR-2/mmproj-deepseek-ocr-2-q8_0.gguf"),
        ],
        "scripts/servidor_deepseekocr2.sh",
        dica_modelo=(
            "baixe os GGUFs uma vez (hf download sabafallah/DeepSeek-OCR-2-GGUF "
            "deepseek-ocr-2-Q4_K_M.gguf mmproj-deepseek-ocr-2-q8_0.gguf "
            "--local-dir /mnt/RESERVA2/models/OCR/DeepSeek-OCR-2)"
        ),
    )


def diagnostico_para_json(itens: list[ItemDiagnostico]) -> list[dict[str, str]]:
    """Converte o diagnóstico para uma estrutura serializável."""
    return [asdict(item) for item in itens]


def coletar_diagnostico(config: AppConfig, raiz_projeto: Path) -> list[ItemDiagnostico]:
    itens = [ItemDiagnostico("Python", "OK", sys.version.split()[0])]
    venv = sys.prefix != sys.base_prefix
    itens.append(ItemDiagnostico("Ambiente virtual", "OK" if venv else "AVISO", "ativo" if venv else "não ativo"))

    tess = _comando_versao("tesseract")
    itens.append(ItemDiagnostico("Tesseract", "OK" if tess else "INDISPONÍVEL", tess or "não encontrado no PATH"))
    idiomas = ""
    if tess:
        try:
            saida = subprocess.run(
                ["tesseract", "--list-langs"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            idiomas = saida.stdout
        except OSError:
            idiomas = ""
    por_instalado = "por" in idiomas.split()
    itens.append(
        ItemDiagnostico(
            "Idioma por",
            "OK" if por_instalado else "AVISO",
            "instalado" if por_instalado else "não localizado",
        )
    )
    best = raiz_projeto / "data" / "modelos" / "tesseract" / "por.traineddata"
    best_instalado = best.is_file()
    itens.append(
        ItemDiagnostico(
            "Idioma por_best",
            "OK" if best_instalado else "AVISO",
            "localizado" if best_instalado else "não localizado",
        )
    )

    poppler = shutil.which("pdftoppm") is not None
    itens.append(
        ItemDiagnostico(
            "Poppler",
            "OK" if poppler else "AVISO",
            "pdftoppm disponível" if poppler else "não localizado",
        )
    )
    for nome, modulo, mensagem in [
        ("PyMuPDF", "fitz", "renderização de PDF disponível"),
        ("OpenCV", "cv2", "processamento de imagem disponível"),
        ("Kraken", "kraken", "recurso manuscrito avançado habilitado"),
        ("OCRmyPDF", "ocrmypdf", "PDF pesquisável disponível"),
        ("Ollama", "ollama", "cliente local disponível"),
    ]:
        existe = importlib.util.find_spec(modulo) is not None
        estado = "OK" if existe else "INDISPONÍVEL"
        detalhe = (
            mensagem
            if existe
            else {
                "Kraken": "recurso manuscrito avançado não habilitado",
                "OCRmyPDF": "PDF pesquisável usará fallback futuro",
                "Ollama": "revisão LLM desabilitada",
            }.get(nome, "não instalado")
        )
        if nome == "Kraken":
            kraken_dir = raiz_projeto / "data" / "modelos" / "kraken"
            modelos = sorted(kraken_dir.glob("*.mlmodel")) if kraken_dir.is_dir() else []
            htr = [p for p in modelos if not p.stem.lower().startswith(("blla", "segmentation"))]
            blla = [p for p in modelos if p not in htr]
            if existe and htr:
                detalhe = f"{mensagem} — modelos HTR: {', '.join(p.name for p in htr[:3])}"
            elif existe and blla:
                detalhe = (
                    f"{mensagem} — segmentação blla ativa "
                    f"({', '.join(p.name for p in blla[:3])}), sem modelo HTR "
                    "(treine com 'ocrhist treinar kraken'); manuscrito usa fallback"
                )
            elif existe:
                detalhe = f"{mensagem} — nenhum .mlmodel em data/modelos/kraken/ (treine com 'ocrhist treinar kraken')"
            elif modelos:
                detalhe = f"não instalado, mas há modelos locais: {', '.join(p.name for p in modelos[:3])}"
        if nome == "Ollama":
            if not config.llm.enabled:
                estado = "INDISPONÍVEL"
                detalhe = f"revisão LLM desabilitada (llm.enabled=false; modelo {config.llm.model})"
            elif existe:
                detalhe = f"{mensagem} — modelo {config.llm.model} em {config.llm.base_url} (suggest_only)"
            else:
                detalhe = (
                    f"configurado ({config.llm.model} em {config.llm.base_url}, suggest_only), "
                    "mas pacote/cliente não detectado — o revisor usa HTTP stdlib e segue funcional"
                )
                estado = "AVISO"
        itens.append(ItemDiagnostico(nome, estado, detalhe))
    paddle_existe = importlib.util.find_spec("paddleocr") is not None
    rapid_existe = importlib.util.find_spec("rapidocr_onnxruntime") is not None
    paddle_backend = importlib.util.find_spec("paddle") is not None
    cpuinfo = Path("/proc/cpuinfo")
    try:
        tem_avx2 = "avx2" in cpuinfo.read_text(encoding="utf-8").lower() if cpuinfo.is_file() else False
    except OSError:
        tem_avx2 = False
    if paddle_existe and paddle_backend and (tem_avx2 or not rapid_existe):
        paddle_detalhe = "PaddleOCR clássico + PaddlePaddle detectados; use configs/paddleocr.yaml"
        paddle_estado = "OK"
    elif paddle_existe and rapid_existe:
        paddle_detalhe = "PaddleOCR detectado; backend RapidOCR/ONNX será usado neste CPU sem AVX2"
        paddle_estado = "OK"
    else:
        paddle_detalhe = "instale 'pip install -e .[paddle]'"
        paddle_estado = "INDISPONÍVEL"
    itens.append(ItemDiagnostico("PaddleOCR", paddle_estado, paddle_detalhe))
    itens.append(_diagnosticar_qwen3vl(config))
    itens.append(_diagnosticar_glmocr(config))
    itens.append(_diagnosticar_olmoc(config))
    itens.append(_diagnosticar_deepseekocr2(config))
    estado_llm = "INFO" if config.llm.enabled else "DESATIVADO"
    detalhe_llm = f"modo {config.llm.mode}; nunca altera o diplomático"
    itens.append(ItemDiagnostico("LLM", estado_llm, detalhe_llm))
    itens.append(ItemDiagnostico("GPU", "OPCIONAL", "RX 580 via Vulkan; use --gpu na GUI ou nos scripts"))
    itens.append(ItemDiagnostico("Entrada padrão", "INFO", str(config.entrada)))
    itens.append(ItemDiagnostico("Saída padrão", "INFO", str(config.saida)))
    try:
        inicializar_banco(config.banco)
        itens.append(ItemDiagnostico("Banco SQLite", "OK", str(config.banco)))
    except OSError as erro:
        itens.append(ItemDiagnostico("Banco SQLite", "ERRO", str(erro)))
    return itens
