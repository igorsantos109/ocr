"""Gerenciador local dos servidores visuais (Qwen3-VL, GLM-OCR, olmOCR).

A GUI pode iniciar/parar somente o processo que ela própria iniciou. Um
servidor já existente é apenas sondado.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


class PaddleVLManager:
    # alias compat
    VisualManager = None  # type: ignore

    def __init__(self, raiz: Path | None = None) -> None:
        self.raiz = raiz or Path(__file__).resolve().parents[3]
        self.scripts = {
            "qwen3_vl": self.raiz / "scripts" / "servidor_qwen3vl_4b.sh",
            "glm_ocr": self.raiz / "scripts" / "servidor_glmocr.sh",
            "olmocr": self.raiz / "scripts" / "servidor_olmocr.sh",
            "deepseek_ocr2": self.raiz / "scripts" / "servidor_deepseekocr2.sh",
            # compat: paddle_vl -> qwen3_vl
            "paddle_vl": self.raiz / "scripts" / "servidor_qwen3vl_4b.sh",
        }
        self.log = self.raiz / "logs" / "paddle-vl.log"
        self.pidfile = self.raiz / "logs" / "paddle-vl.pid"
        self._processo: subprocess.Popen[bytes] | None = None
        self._iniciado_em: float | None = None
        self._lock = threading.RLock()

    @staticmethod
    def _modelos(base_url: str) -> list[str]:
        try:
            with urllib.request.urlopen(base_url.rstrip("/") + "/v1/models", timeout=0.8) as resposta:
                if not 200 <= resposta.status < 300:
                    return []
                dados = json.loads(resposta.read().decode("utf-8"))
        except (OSError, ValueError, urllib.error.URLError):
            return []
        modelos: list[str] = []
        for origem in (dados.get("data"), dados.get("models")):
            if isinstance(origem, list):
                for item in origem:
                    if isinstance(item, dict):
                        valor = item.get("id") or item.get("name") or item.get("model")
                        if isinstance(valor, str) and valor:
                            modelos.append(valor)
        return modelos

    def _online(self, base_url: str) -> tuple[bool, list[str]]:
        base = base_url.rstrip("/")
        modelos = self._modelos(base)
        if modelos:
            return True, modelos
        try:
            with urllib.request.urlopen(base + "/health", timeout=0.8) as resposta:
                return 200 <= resposta.status < 300, []
        except (OSError, urllib.error.URLError):
            return False, []

    def _pidfile_pid(self) -> int | None:
        try:
            pid = int(self.pidfile.read_text(encoding="ascii").strip())
            os.kill(pid, 0)
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().decode("utf-8", "ignore")
            if not any(
                marca in cmdline
                for marca in (
                    "servidor_qwen3vl",
                    "servidor_glmocr",
                    "servidor_olmocr",
                    "servidor_deepseekocr2",
                    "Qwen3VL",
                    "GLM",
                    "olmOCR",
                    "DeepSeek-OCR-2",
                    "deepseek-ocr-2",
                )
            ):
                self.pidfile.unlink(missing_ok=True)
                return None
            return pid
        except (OSError, ValueError):
            self.pidfile.unlink(missing_ok=True)
            return None

    def _processo_vivo(self) -> bool:
        if self._processo is not None and self._processo.poll() is None:
            return True
        return self._pidfile_pid() is not None

    def _pid_gerenciado(self) -> int | None:
        if self._processo is not None and self._processo.poll() is None:
            return self._processo.pid
        return self._pidfile_pid()

    def _configurado(self, config: object, motor: str) -> object:
        # compat paddle_vl -> qwen3vl
        if motor == "paddle_vl":
            motor = "qwen3_vl"
        if motor == "qwen3_vl":
            cfg = getattr(config, "qwen3vl", None)
            # fallback para paddlevl legado
            if cfg is None:
                cfg = getattr(config, "paddlevl", None)
            return cfg
        if motor == "glm_ocr":
            return getattr(config, "glmocr", None)
        if motor == "deepseek_ocr2":
            return getattr(config, "deepseekocr2", None)
        if motor == "olmocr":
            return getattr(config, "olmocr", None)
        return getattr(config, "qwen3vl", None)

    def _script_for(self, config: object, motor: str) -> Path:
        if motor == "paddle_vl":
            motor = "qwen3_vl"
        if motor == "glm_ocr":
            return self.scripts["glm_ocr"]
        if motor == "deepseek_ocr2":
            return self.scripts["deepseek_ocr2"]
        if motor == "olmocr":
            cfg = self._configurado(config, motor)
            modelo = str(getattr(cfg, "model", "")).lower()
            if "olmocr" in modelo:
                return self.scripts["olmocr"]
            return self.scripts["qwen3_vl"]
        return self.scripts["qwen3_vl"]

    def status(self, config: object, motor: str = "qwen3_vl") -> dict[str, object]:
        if motor == "paddle_vl":
            motor = "qwen3_vl"
        cfg = self._configurado(config, motor)
        base_url = str(getattr(cfg, "base_url", "http://127.0.0.1:8082"))
        modelo = str(getattr(cfg, "model", "Qwen3VL-4B-Instruct"))
        online, modelos = self._online(base_url)
        with self._lock:
            gerenciado = self._processo_vivo()
            pid = self._pid_gerenciado() if gerenciado else None
            if self._processo is not None and self._processo.poll() is not None:
                self._processo = None
                self._iniciado_em = None
            segundos = round(time.monotonic() - self._iniciado_em) if gerenciado and self._iniciado_em else None
        anunciado_vl = any(any(p in item.lower() for p in ("vl", "vision", "qwen", "glm", "ocr")) for item in modelos)
        url = urlparse(base_url)
        local = url.hostname in {"127.0.0.1", "localhost", "::1"}
        script = self._script_for(config, motor)
        if online and modelos and not anunciado_vl:
            mensagem = "Servidor respondeu, mas não anunciou um modelo visual."
        elif online:
            mensagem = f"Servidor visual pronto para {motor}."
        elif gerenciado and segundos is not None and segundos >= 120:
            mensagem = (
                f"O modelo não respondeu após {segundos // 60} min; consulte o log "
                "e pare o processo antes de tentar novamente."
            )
        elif gerenciado:
            mensagem = "Servidor iniciado; aguardando o carregamento do modelo."
        else:
            mensagem = "Servidor visual desligado."
        return {
            "online": online,
            "gerenciado": gerenciado,
            "iniciando": bool(gerenciado and not online and (segundos is None or segundos < 120)),
            "carregando": bool(gerenciado and not online),
            "segundos_desde_inicio": segundos,
            "motor": motor,
            "modelo": modelo,
            "modelos": modelos,
            "endpoint": base_url,
            "pid": pid,
            "local": local,
            "pode_iniciar": bool(local and script.is_file()),
            "modelo_visual": anunciado_vl or not modelos,
            "mensagem": mensagem,
            "log": str(self.log),
        }

    def iniciar(self, config: object, motor: str = "qwen3_vl", gpu: bool = False) -> dict[str, object]:
        if motor == "paddle_vl":
            motor = "qwen3_vl"
        with self._lock:
            atual = self.status(config, motor)
            if atual["online"] or atual["gerenciado"]:
                return atual
            if not atual["local"]:
                raise ValueError("Por segurança, a GUI só pode iniciar um servidor VLM local.")
            script = self._script_for(config, motor)
            if not script.is_file():
                raise FileNotFoundError(f"script do servidor não encontrado: {script}")
            cfg = self._configurado(config, motor)
            base_url = str(getattr(cfg, "base_url", "http://127.0.0.1:8082"))
            porta = urlparse(base_url).port or 8082
            self.log.parent.mkdir(parents=True, exist_ok=True)
            modo = "--gpu" if gpu else "--cpu"
            with self.log.open("ab") as saida:
                self._processo = subprocess.Popen(
                    ["bash", str(script), "--port", str(porta), modo],
                    cwd=self.raiz,
                    stdin=subprocess.DEVNULL,
                    stdout=saida,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            self.pidfile.write_text(str(self._processo.pid), encoding="ascii")
            self._iniciado_em = time.monotonic()
            return self.status(config, motor)

    def parar(self, config: object, motor: str = "qwen3_vl") -> dict[str, object]:
        if motor == "paddle_vl":
            motor = "qwen3_vl"
        with self._lock:
            processo = self._processo
            pid = self._pid_gerenciado()
            if pid is None:
                self._processo = None
                self._iniciado_em = None
                self.pidfile.unlink(missing_ok=True)
                return self.status(config, motor)
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                if processo is not None:
                    processo.wait(timeout=3)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            finally:
                self._processo = None
                self._iniciado_em = None
                self.pidfile.unlink(missing_ok=True)
            return self.status(config, motor)


GERENCIADOR = PaddleVLManager()
VisualManager = PaddleVLManager
