"""Adaptador PaddleOCR clássico (PP-OCR), lazy e sem downloads implícitos."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from .base import LinhaRec, MotorIndisponivel, MotorPagina, RecognitionConfig, ResultadoPagina

MENSAGEM_INSTALACAO = (
    "PaddleOCR clássico indisponível. Instalação explícita (sem download de modelos): "
    "'pip install paddleocr' (extra .[paddle]) e defina configs/paddleocr.yaml. "
    "Os modelos só são baixados com allow_download=true explícito. "
    "O lote continua com os motores disponíveis."
)


class PaddleOCREngine(MotorPagina):
    """Reconhece páginas com PaddleOCR local, gerando caixas e confiança.

    A API do pacote varia entre as versões 2.x e 3.x; o adaptador normaliza
    para o contrato ``LinhaRec``/``ResultadoPagina``. Nenhum modelo é baixado
    automaticamente: os parâmetros só baixam via ``allow_download=true``.
    """

    name = "paddleocr"
    _instancia: object | None = None
    _chave: str | None = None

    def available(self) -> bool:
        return bool(
            importlib.util.find_spec("paddleocr") is not None
            or importlib.util.find_spec("rapidocr_onnxruntime") is not None
        )

    def _carregar(self, config: RecognitionConfig) -> object:
        if not self.available():
            raise MotorIndisponivel(MENSAGEM_INSTALACAO)
        backend = os.environ.get("OCRHIST_PADDLE_BACKEND", config.backend)
        if backend == "onnx":
            return self._carregar_onnx()
        # Este host expõe AVX, mas não AVX2. O wheel PaddlePaddle atual
        # aborta com SIGILL nesse caso; RapidOCR/ONNX é o backend seguro.
        if backend == "auto" and not self._cpu_has_avx2() and importlib.util.find_spec("rapidocr_onnxruntime"):
            return self._carregar_onnx()
        if importlib.util.find_spec("paddle") is None and importlib.util.find_spec("rapidocr_onnxruntime"):
            return self._carregar_onnx()
        # Modelos padrão do paddleocr só baixam com allow_download explícito.
        if not config.allow_download and not any(
            (
                config.det_model_dir,
                config.rec_model_dir,
                config.cls_model_dir,
                config.text_detection_model_dir,
                config.text_recognition_model_dir,
                config.textline_orientation_model_dir,
            )
        ):
            raise MotorIndisponivel(
                "PaddleOCR sem modelos locais e allow_download=false. "
                "Defina det_model_dir/rec_model_dir (ou allow_download=true explícito) em configs/paddleocr.yaml."
            )
        chave = self._chave_instancia(config)
        if self._instancia is not None and self._chave == chave:
            return self._instancia
        import paddleocr  # type: ignore[import-not-found]

        try:
            instancia = paddleocr.PaddleOCR(**self._parametros_paddle(config))
        except TypeError:
            instancia = paddleocr.PaddleOCR(
                use_angle_cls=config.use_angle_cls if hasattr(config, "use_angle_cls") else True,
                lang=self._idioma_paddle(config.idioma),
                show_log=False,
            )
        self._instancia = instancia
        self._chave = chave
        return instancia

    @staticmethod
    def _cpu_has_avx2() -> bool:
        try:
            return "avx2" in Path("/proc/cpuinfo").read_text(encoding="utf-8").lower()
        except OSError:
            return False

    def _carregar_onnx(self) -> object:
        if self._instancia is None or self._chave != "rapidocr-onnx":
            try:
                from rapidocr_onnxruntime import RapidOCR
            except ImportError as erro:
                raise MotorIndisponivel(
                    "Backend ONNX do PaddleOCR indisponível; instale rapidocr_onnxruntime."
                ) from erro
            self._instancia = RapidOCR()
            self._chave = "rapidocr-onnx"
        return self._instancia

    def _chave_instancia(self, config: RecognitionConfig) -> str:
        exts = (
            config.det_model_dir,
            config.rec_model_dir,
            config.cls_model_dir,
            config.dispositivo,
            config.idioma,
        )
        return "|".join(exts)

    def _parametros_paddle(self, config: RecognitionConfig) -> dict[str, object]:
        params: dict[str, object] = {
            "lang": self._idioma_paddle(config.idioma),
            "show_log": False,
            "use_angle_cls": config.use_angle_cls if hasattr(config, "use_angle_cls") else True,
        }
        if config.dispositivo == "gpu":
            params["device"] = "gpu"
        # Modelos locais explícitos; sem eles o paddleocr usa os padrões pós-instalação.
        if config.det_model_dir:
            params["det_model_dir"] = config.det_model_dir
        if config.rec_model_dir:
            params["rec_model_dir"] = config.rec_model_dir
        if config.cls_model_dir:
            params["cls_model_dir"] = config.cls_model_dir
        if config.text_detection_model_dir:
            params["text_detection_model_dir"] = config.text_detection_model_dir
        if config.text_recognition_model_dir:
            params["text_recognition_model_dir"] = config.text_recognition_model_dir
        if config.textline_orientation_model_dir:
            params["textline_orientation_model_dir"] = config.textline_orientation_model_dir
        return params

    @staticmethod
    def _idioma_paddle(idioma: str) -> str:
        mapeamento = {
            "por": "pt",
            "pt": "pt",
            "eng": "en",
            "en": "en",
            "fra": "fr",
            "spa": "es",
            "lat": "latin",
            "deu": "german",
        }
        return mapeamento.get(idioma, "pt")

    def recognize_page(
        self, image_path: Path | str, config: RecognitionConfig, numero_pagina: int = 1
    ) -> ResultadoPagina:
        if not self.available():
            raise MotorIndisponivel(MENSAGEM_INSTALACAO)
        caminho = Path(image_path)
        if not caminho.is_file():
            raise MotorIndisponivel(f"Imagem não encontrada para PaddleOCR: {caminho}")
        instancia = self._carregar(config)
        if self._chave == "rapidocr-onnx":
            try:
                chamada_onnx = instancia
                saida, _tempo = chamada_onnx(str(caminho))  # type: ignore[operator]
            except Exception as erro:  # noqa: BLE001
                raise MotorIndisponivel(f"Falha no backend ONNX do PaddleOCR: {erro}") from erro
            linhas = self._extrair_linhas(saida, numero_pagina)
            return self._resultado(linhas)
        chamada_ocr = getattr(instancia, "ocr", None) or getattr(instancia, "predict", None)
        if chamada_ocr is None:
            raise MotorIndisponivel(
                "API PaddleOCR não reconhecida nesta versão; atualize o adaptador."
            )
        try:
            saida = chamada_ocr(str(caminho), cls=True)
        except TypeError:
            chamada_2 = getattr(instancia, "predict", None)
            if chamada_2 is None:
                raise MotorIndisponivel(
                    "API PaddleOCR não reconhecida nesta versão; atualize o adaptador."
                ) from None
            saida = chamada_2(str(caminho))
        linhas = self._extrair_linhas(saida, numero_pagina)
        return self._resultado(linhas)

    def _resultado(self, linhas: list[LinhaRec]) -> ResultadoPagina:
        if not linhas:
            return ResultadoPagina(
                texto_bruto="", linhas=(), confianca_media=None,
                motor=self.name, aviso="PaddleOCR não detectou texto nesta página.",
            )
        bruto = "\n".join(linha.texto for linha in linhas)
        confiancas = [linha.confianca for linha in linhas if linha.confianca is not None]
        media = sum(confiancas) / len(confiancas) if confiancas else None
        return ResultadoPagina(texto_bruto=bruto, linhas=tuple(linhas), confianca_media=media, motor=self.name)

    def _extrair_linhas(self, saida: object, numero_pagina: int) -> list[LinhaRec]:
        """Normaliza saída PaddleOCR 2.x/3.x para linhas com caixa e confiança."""
        linhas: list[LinhaRec] = []
        avulsos: list[object] = []

        if hasattr(saida, "json"):
            try:
                dados = saida.json
                if callable(dados):
                    dados = dados()
                if isinstance(dados, str):
                    import json

                    dados = json.loads(dados)
                if isinstance(dados, dict):
                    saida = dados
            except (TypeError, ValueError):
                pass
        if hasattr(saida, "to_dict"):
            try:
                convertido = saida.to_dict()
                if isinstance(convertido, dict):
                    saida = convertido
            except (TypeError, ValueError):
                pass

        def coletar(valor: object) -> None:
            if self._parece_rapidocr(valor):
                avulsos.append(valor)
                return
            if isinstance(valor, dict):
                avulsos.append(valor)
                return
            if not isinstance(valor, (list, tuple)):
                return
            # Formato PaddleOCR 2.x: [polygon, (texto, confiança)].
            if len(valor) >= 2 and self._parece_poligono(valor[0]) and self._parece_texto_score(valor[1]):
                avulsos.append(valor)
                return
            for parte in valor:
                coletar(parte)

        coletar(saida)
        for avulso in avulsos:
            caixa: object = None
            texto = ""
            conf: float | None = None
            if isinstance(avulso, dict):
                caixa = avulso.get("box") or avulso.get("polygon") or avulso.get("points") or avulso.get("bbox")
                texto = str(avulso.get("text") or avulso.get("rec_text") or "")
                conf_raw = avulso.get("score") or avulso.get("confidence") or avulso.get("rec_score")
                if conf_raw is not None:
                    try:
                        conf = float(conf_raw)
                    except (TypeError, ValueError):
                        conf = None
            elif isinstance(avulso, (list, tuple)) and len(avulso) >= 2:
                caixa = avulso[0]
                valor_texto = avulso[1]
                if isinstance(valor_texto, (list, tuple)) and valor_texto:
                    texto = str(valor_texto[0] or "")
                    if len(valor_texto) > 1 and valor_texto[1] is not None:
                        try:
                            conf = float(valor_texto[1])
                        except (TypeError, ValueError):
                            conf = None
                else:
                    texto = str(valor_texto or "")
                if len(avulso) >= 3 and avulso[2] is not None:
                    try:
                        conf = float(avulso[2])
                    except (TypeError, ValueError):
                        conf = None
            if not texto:
                continue
            x, y, w, h = self._caixa_para_bbox(caixa)
            linhas.append(
                LinhaRec(numero=len(linhas) + 1, x=x, y=y, largura=w, altura=h, texto=texto.strip(), confianca=conf)
            )
        return linhas

    @staticmethod
    def _parece_rapidocr(valor: object) -> bool:
        return isinstance(valor, (list, tuple)) and len(valor) >= 3 and isinstance(valor[1], str)

    @staticmethod
    def _parece_poligono(valor: object) -> bool:
        return isinstance(valor, (list, tuple)) and len(valor) >= 4 and all(
            isinstance(ponto, (list, tuple)) and len(ponto) >= 2 for ponto in valor[:4]
        )

    @staticmethod
    def _parece_texto_score(valor: object) -> bool:
        return isinstance(valor, (list, tuple)) and len(valor) >= 2 and isinstance(valor[0], str)

    @staticmethod
    def _caixa_para_bbox(caixa: object) -> tuple[int, int, int, int]:
        pontos = caixa
        if isinstance(caixa, dict):
            pontos = caixa.get("points") or caixa.get("box")
        if not isinstance(pontos, (list, tuple)) or len(pontos) < 4:
            return 0, 0, 0, 0
        xs: list[int] = []
        ys: list[int] = []
        for ponto in pontos[:4]:
            if not isinstance(ponto, (list, tuple)) or len(ponto) < 2:
                return 0, 0, 0, 0
            try:
                xs.append(int(float(ponto[0])))
                ys.append(int(float(ponto[1])))
            except (TypeError, ValueError):
                return 0, 0, 0, 0
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        return x0, y0, max(0, x1 - x0), max(0, y1 - y0)

    def versions(self) -> dict[str, str]:
        if not self.available():
            return {"paddleocr": "ausente"}
        try:
            from importlib.metadata import version

            return {"paddleocr": version("paddleocr")}
        except Exception:  # noqa: BLE001
            return {"paddleocr": "desconhecida"}