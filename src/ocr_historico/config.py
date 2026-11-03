"""Configuração YAML validada com Pydantic, sem efeitos de rede."""

from __future__ import annotations

import os
import re
from importlib import resources as _resources
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PreprocessamentoConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    grayscale: bool = True
    deskew: bool = True
    clahe: bool = False
    denoise: str = "leve"
    remover_fundo: bool = False
    upscale: float = Field(default=1.0, ge=0.1, le=4.0)
    binarizacao: bool = False


class ReconhecimentoConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    engine: str = "tesseract"
    idioma: str = "por"
    oem: int = Field(default=1, ge=0, le=3)
    psm: int = Field(default=3, ge=3, le=13)
    modelo: str = "best"
    timeout_segundos: int = Field(default=300, gt=0, le=3600)


class ConfiancaConfig(BaseModel):
    limiar_alta: float = Field(default=0.70, ge=0, le=1)
    limiar_revisao: float = Field(default=0.82, ge=0, le=1)

    @field_validator("limiar_revisao")
    @classmethod
    def limiar_maior_que_alta(cls, value: float, info):
        alta = info.data.get("limiar_alta", 0.70)
        if value <= alta:
            raise ValueError("limiar_revisao deve ser maior que limiar_alta")
        return value


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    enabled: bool = False
    provider: str = "ollama"
    model: str = "qwen2.5:7b-instruct"
    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: int = Field(default=120, gt=0)
    mode: str = "suggest_only"


class Qwen3VLConfig(BaseModel):
    """Servidor VLM local Qwen3-VL 4B (llama-server, OpenAI-compatível).

    Padrão: Qwen3-VL-4B em :8082 (scripts/servidor_qwen3vl_4b.sh).
    Se o GGUF 4B não estiver presente, o script faz fallback para o
    Qwen3VL-8B já existente em /mnt/RESERVA2/models/OCR/.
    """

    model_config = ConfigDict(extra="allow")
    base_url: str = "http://127.0.0.1:8082"
    model: str = "Qwen3VL-4B-Instruct"
    timeout_seconds: int = Field(default=300, gt=0)
    max_lado_px: int = Field(default=1024, ge=512, le=4096)


class GLMOCRConfig(BaseModel):
    """Servidor VLM local GLM-OCR (llama-server, OpenAI-compatível).

    Padrão: GLM-OCR em :8082 (scripts/servidor_glmocr.sh).
    Ajustado para documentos com alta precisão em tabelas e layout.
    Se o GGUF oficial não estiver presente, usa Qwen3-VL como fallback
    compartilhado (mesma porta 8082).
    """

    model_config = ConfigDict(extra="allow")
    base_url: str = "http://127.0.0.1:8082"
    model: str = "GLM-OCR"
    timeout_seconds: int = Field(default=300, gt=0)
    max_lado_px: int = Field(default=1024, ge=512, le=4096)


class OlmOCRConfig(BaseModel):
    """Servidor VLM local do olmOCR (llama-server, OpenAI-compatível).

    Padrão: Qwen3-VL-8B em :8082 (scripts/servidor_qwen3vl.sh) — o GGUF
    olmOCR-2-7B não está presente neste host. Para o olmOCR original,
    baixe GGUF + mmproj e ajuste model.
    """

    model_config = ConfigDict(extra="allow")
    base_url: str = "http://127.0.0.1:8082"
    model: str = "Qwen3VL-8B-Instruct"
    timeout_seconds: int = Field(default=300, gt=0)
    max_lado_px: int = Field(default=1024, ge=512, le=4096)


class DeepSeekOCR2Config(BaseModel):
    """Servidor VLM local DeepSeek-OCR-2 (llama-server, OpenAI-compatível).

    Padrão: DeepSeek-OCR-2 (GGUF Q4_K_M + mmproj) em :8084
    (scripts/servidor_deepseekocr2.sh). MoE 3,4B especializado em
    documentos; porta própria porque o :8082 é compartilhado pelos
    outros VLMs.
    """

    model_config = ConfigDict(extra="allow")
    base_url: str = "http://127.0.0.1:8084"
    model: str = "DeepSeek-OCR-2"
    timeout_seconds: int = Field(default=600, gt=0)
    max_lado_px: int = Field(default=1540, ge=512, le=4096)


class PaddleOCRConfig(BaseModel):
    """PaddleOCR clássico local; modelos só baixam com ``allow_download`` explícito."""

    model_config = ConfigDict(extra="allow")
    idioma: str = "pt"
    dispositivo: str = "cpu"
    backend: str = "auto"
    use_angle_cls: bool = True
    allow_download: bool = False
    det_model_dir: Path | None = None
    rec_model_dir: Path | None = None
    cls_model_dir: Path | None = None
    text_detection_model_dir: Path | None = None
    text_recognition_model_dir: Path | None = None
    textline_orientation_model_dir: Path | None = None


class PreservacaoConfig(BaseModel):
    """Política opcional para manter uma cópia verificável dos originais."""

    model_config = ConfigDict(extra="allow")
    modo: str = Field(default="none", pattern="^(none|copy|content_addressed)$")
    raiz: Path | None = None
    manter_caminho_relativo: bool = True
    verificar_hash: bool = True
    sobrescrever: bool = False


class InventarioConfig(BaseModel):
    """Opções de varredura; o hash é calculado por padrão."""

    model_config = ConfigDict(extra="allow")
    calcular_hash: bool = True
    seguir_links: bool = False


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    perfil: str = "automatico"
    render_dpi: int = Field(default=300, ge=72, le=1200)
    entrada: Path = Path.home() / "Área de trabalho" / "OCRENTRADA"
    saida: Path = Path.home() / "Área de trabalho" / "OCRSAIDA"
    banco: Path = Path("data/ocr_historico.sqlite3")
    idiomas: list[str] = Field(default_factory=lambda: ["por"])
    workers: int = Field(default=1, ge=1, le=64)
    output_type_pdf: str = "pdf"
    salvar_imagens: bool = True
    ocrmypdf: dict[str, Any] = Field(default_factory=dict)
    inventario: InventarioConfig = Field(default_factory=InventarioConfig)
    preservacao: PreservacaoConfig = Field(default_factory=PreservacaoConfig)
    reconhecimento: ReconhecimentoConfig = Field(default_factory=ReconhecimentoConfig)
    preprocessamento: PreprocessamentoConfig = Field(default_factory=PreprocessamentoConfig)
    confianca: ConfiancaConfig = Field(default_factory=ConfiancaConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    qwen3vl: Qwen3VLConfig = Field(default_factory=Qwen3VLConfig)
    glmocr: GLMOCRConfig = Field(default_factory=GLMOCRConfig)
    olmocr: OlmOCRConfig = Field(default_factory=OlmOCRConfig)
    deepseekocr2: DeepSeekOCR2Config = Field(default_factory=DeepSeekOCR2Config)
    paddleocr: PaddleOCRConfig = Field(default_factory=PaddleOCRConfig)
    # compat: mantém leitura de YAMLs antigos com `paddlevl`
    paddlevl: Qwen3VLConfig | None = None

    @field_validator("entrada", "saida", "banco", mode="before")
    @classmethod
    def _expande_home(cls, valor: Any) -> Any:
        if isinstance(valor, str) and valor.startswith("~"):
            return Path(valor).expanduser()
        return valor


_VAR_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}")


def _resolver_variaveis_ambiente(texto: str) -> str:
    """Substitui ``${VAR:default}`` e ``${VAR}`` por valores de ambiente.

    Variáveis não definidas sem valor padrão ficam inalteradas, permitindo que
    o Pydantic reporte o erro de validação apropriado.
    """

    def _substituir(match: re.Match[str]) -> str:
        nome = match.group(1)
        padrao = match.group(2)
        if nome in os.environ:
            return os.environ[nome]
        if padrao is not None:
            return padrao
        return match.group(0)

    return _VAR_ENV_RE.sub(_substituir, texto)


def carregar_config(caminho: Path | str) -> AppConfig:
    caminho = Path(caminho)
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {caminho}")
    try:
        with caminho.open("r", encoding="utf-8") as arquivo:
            bruto = arquivo.read()
    except OSError as erro:
        raise ValueError(f"Não foi possível ler {caminho}: {erro}") from erro
    try:
        dados: Any = yaml.safe_load(_resolver_variaveis_ambiente(bruto)) or {}
    except yaml.YAMLError as erro:
        raise ValueError(f"YAML inválido em {caminho}: {erro}") from erro
    if not isinstance(dados, dict):
        raise ValueError("A configuração YAML deve conter um objeto no nível superior")
    # compat: migra paddlevl -> qwen3vl se necessário
    if "paddlevl" in dados and "qwen3vl" not in dados:
        dados["qwen3vl"] = dados["paddlevl"]
    return AppConfig.model_validate(dados)


def config_padrao_embutida() -> AppConfig:
    return AppConfig()


_PAQUETE_CONFIGS = "ocr_historico.configs"


def raiz_projeto() -> Path:
    """Retorna a raiz do repositório (dois níveis acima deste módulo)."""
    return Path(__file__).resolve().parents[2]


def _caminho_configs_pacote(nome: str = "default.yaml") -> Path | None:
    """Localiza um YAML de configuração empacotado via ``importlib.resources``.

    Funciona quando o projeto está instalado (wheel ou ``pip install -e``) e o
    diretório ``configs/`` foi incluído como package data. Retorna ``None`` se
    não houver recurso empacotado (execução direta do código-fonte sem
    instalação), deixando o chamador decidir o fallback.
    """
    try:
        _resources.files(_PAQUETE_CONFIGS).joinpath(nome)
        return Path(_resources.files(_PAQUETE_CONFIGS).joinpath(nome))
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return None


def caminho_config_padrao() -> Path:
    """Resolve o arquivo de configuração padrão.

    Ordem de resolução:
    1. recurso empacotado ``ocr_historico/configs/default.yaml`` (instalação
       normal ou editável com package data);
    2. ``<raiz_projeto>/configs/default.yaml`` (código-fonte);
    3. arquivo padrão ``~/.config/ocr-historico/default.yaml`` (usuário, sem
       falhar se ainda não existir).
    """
    empacotado = _caminho_configs_pacote("default.yaml")
    if empacotado is not None:
        return empacotado
    fonte = raiz_projeto() / "configs" / "default.yaml"
    if fonte.is_file():
        return fonte
    return Path.home() / ".config" / "ocr-historico" / "default.yaml"
