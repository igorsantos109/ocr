#!/usr/bin/env python3
"""v7.3.1 FINAL — PaddleOCR-VL doc_parser (API Python oficial) → SQLite/FTS/JSON.

Requer: paddleocr[doc-parser]>=3.6.0 e llama-server PaddleOCR-VL-1.6 ativo.
A etapa de layout roda local (CPU por padrão); o reconhecimento VLM vai ao
llama-server (RX 580) via backend llama-cpp-server.

Uso real:
  python3 ocr_v73_layout_adapter_FINAL.py documento.pdf --out v73_output \
    --url http://127.0.0.1:8080/v1 --model PaddlePaddle/PaddleOCR-VL-1.6

Reimportar JSONs já produzidos (sem rodar o parser):
  python3 ocr_v73_layout_adapter_FINAL.py documento.pdf --out v73_output --import-only

Na primeira execução o PaddleOCR baixa os modelos de layout (PP-DocLayoutV2 etc.)
da internet; execuções seguintes usam o cache local.
"""
import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 3
DEFAULT_MODEL = "PaddlePaddle/PaddleOCR-VL-1.6"
COMPLEX = {"table", "formula", "chart", "seal", "formula_number"}
NO_TEXT = {"image", "figure", "chart", "seal"}


def db_open(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript("""
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS documents(
      id TEXT PRIMARY KEY, path TEXT NOT NULL, pages INTEGER NOT NULL,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS pages(
      document_id TEXT NOT NULL, page INTEGER NOT NULL, markdown TEXT NOT NULL,
      risk INTEGER NOT NULL, PRIMARY KEY(document_id,page),
      FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS blocks(
      document_id TEXT NOT NULL, page INTEGER NOT NULL, ord INTEGER NOT NULL,
      label TEXT NOT NULL, score REAL NOT NULL,
      x1 REAL NOT NULL, y1 REAL NOT NULL, x2 REAL NOT NULL, y2 REAL NOT NULL,
      content TEXT NOT NULL, risk INTEGER NOT NULL, reasons_json TEXT NOT NULL,
      PRIMARY KEY(document_id,page,ord),
      FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE);
    CREATE VIRTUAL TABLE IF NOT EXISTS blocks_fts USING fts5(
      document_id UNINDEXED, page UNINDEXED, ord UNINDEXED, content,
      tokenize='unicode61 remove_diacritics 2');
    """)
    return con


def check_schema(con: sqlite3.Connection) -> None:
    row = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    if row and int(row[0]) != SCHEMA_VERSION:
        raise RuntimeError(f"schema v{row[0]} incompatível com v{SCHEMA_VERSION}; use outro --out")
    con.execute("INSERT OR REPLACE INTO meta VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
    con.commit()


def sha256(pdf: Path) -> str:
    h = hashlib.sha256()
    with open(pdf, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def rect(coordinate) -> tuple[float, float, float, float]:
    flat = []

    def walk(item):
        for value in item:
            if isinstance(value, (list, tuple)):
                walk(value)
            else:
                flat.append(float(value))

    walk(coordinate)
    if len(flat) < 4 or len(flat) % 2:
        return 0.0, 0.0, 0.0, 0.0
    xs, ys = flat[::2], flat[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def reading_order(boxes: list[dict]) -> list[dict]:
    """Fallback determinístico: elementos largos separam faixas; estreitos por coluna/topo."""
    if not boxes:
        return []
    xmin = min(b["bbox"][0] for b in boxes)
    xmax = max(b["bbox"][2] for b in boxes)
    width = max(1.0, xmax - xmin)
    wide = [b for b in boxes if b["bbox"][2] - b["bbox"][0] >= 0.70 * width]
    narrow = [b for b in boxes if b not in wide]
    anchors = sorted(wide, key=lambda b: b["bbox"][1])
    result, cursor = [], -float("inf")

    def append_band(items):
        cols = sorted(set(round((b["bbox"][0] + b["bbox"][2]) / 100) for b in items))
        for col in cols:
            result.extend(sorted(
                [b for b in items if round((b["bbox"][0] + b["bbox"][2]) / 100) == col],
                key=lambda b: b["bbox"][1]))

    for anchor in anchors:
        append_band([b for b in narrow if cursor <= b["bbox"][1] < anchor["bbox"][1]])
        result.append(anchor)
        cursor = anchor["bbox"][3]
    append_band([b for b in narrow if b["bbox"][1] >= cursor])
    return result


def content_of(box: dict) -> str:
    for key in ("block_content", "content", "text", "markdown"):
        if box.get(key) is not None:
            return str(box[key])
    return ""


def normalize_page(raw: dict, page: int) -> dict:
    res = raw.get("res", raw)
    layout = res.get("layout_det_res", {}) or {}
    boxes = []
    for index, box in enumerate(layout.get("boxes", []) or []):
        boxes.append({
            "source_index": index,
            "label": str(box.get("label", "unknown")),
            "score": float(box.get("score", 0)),
            "bbox": rect(box.get("coordinate", box.get("bbox", []))),
            "content": content_of(box),
        })
    ordered = reading_order(boxes)
    markdown = (res.get("markdown") or res.get("markdown_text")
                or "\n\n".join(b["content"] for b in ordered if b["content"]))
    return {"page": page, "markdown": markdown, "blocks": ordered}


def block_risk(block: dict) -> tuple[int, list[str]]:
    score, reasons = 0, []
    if block["score"] < 0.50:
        score += 40; reasons.append("layout_score_baixo")
    if block["label"] in COMPLEX:
        score += 20; reasons.append("elemento_complexo")
    if not block["content"] and block["label"] not in NO_TEXT:
        score += 35; reasons.append("bloco_sem_conteudo")
    if re.search(r"[?]{2,}", block["content"]):
        score += 30; reasons.append("caracteres_suspeitos")
    return min(score, 100), reasons


def ingest(con: sqlite3.Connection, did: str, data: dict) -> None:
    page = data["page"]
    with con:
        con.execute("DELETE FROM blocks WHERE document_id=? AND page=?", (did, page))
        con.execute("DELETE FROM blocks_fts WHERE document_id=? AND page=?", (did, page))
        risks = []
        for order, block in enumerate(data["blocks"]):
            risk, reasons = block_risk(block)
            risks.append(risk)
            x1, y1, x2, y2 = block["bbox"]
            con.execute("INSERT INTO blocks VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (did, page, order, block["label"], block["score"], x1, y1, x2, y2,
                         block["content"], risk, json.dumps(reasons, ensure_ascii=False)))
            if block["content"]:
                con.execute("INSERT INTO blocks_fts VALUES(?,?,?,?)",
                            (did, page, order, block["content"]))
        con.execute("INSERT OR REPLACE INTO pages VALUES(?,?,?,?)",
                    (did, page, data["markdown"], max(risks, default=0)))


def run_parser(pdf: Path, out: Path, url: str, model: str, device: str) -> None:
    """API Python oficial do PaddleOCR-VL (sem depender de flags da CLI).

    O backend 'llama-cpp-server' aponta o reconhecimento VLM para o llama-server
    local; a análise de layout roda no dispositivo indicado por --device.
    """
    from paddleocr import PaddleOCRVL  # import adiado: --import-only não exige paddleocr
    pipeline = PaddleOCRVL(
        pipeline_version="v1.6",
        vl_rec_backend="llama-cpp-server",
        vl_rec_server_url=url,
        vl_rec_api_model_name=model,
        device=device,
        use_layout_detection=True,
        format_block_content=True,
    )
    json_dir = out / "parser_json"
    json_dir.mkdir(exist_ok=True)
    for res in pipeline.predict(input=str(pdf)):
        res.save_to_json(save_path=str(json_dir))
        res.save_to_markdown(save_path=str(json_dir))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--out", type=Path, default=Path("v73_output"))
    ap.add_argument("--url", default="http://127.0.0.1:8080/v1")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--device", default="cpu",
                    help="dispositivo da análise de layout local; o VLM roda no llama-server")
    ap.add_argument("--import-only", action="store_true")
    args = ap.parse_args()
    if not args.pdf.is_file():
        raise SystemExit(f"PDF não encontrado: {args.pdf}")
    args.out.mkdir(parents=True, exist_ok=True)
    if not args.import_only:
        run_parser(args.pdf, args.out, args.url, args.model, args.device)

    files = sorted(f for f in args.out.rglob("*.json")
                   if not f.name.endswith(".v73.json"))
    if not files:
        raise SystemExit("Nenhum JSON do doc_parser encontrado em --out")
    did = sha256(args.pdf)
    con = db_open(args.out / "ocr_v73.sqlite3")
    check_schema(con)
    con.execute("INSERT OR IGNORE INTO documents(id,path,pages) VALUES(?,?,0)",
                (did, str(args.pdf)))
    con.commit()
    imported = []
    for fallback, file in enumerate(files, 1):
        raw = json.loads(file.read_text(encoding="utf-8"))
        index = raw.get("res", raw).get("page_index")
        page = int(index) + 1 if index is not None else fallback
        data = normalize_page(raw, page)
        ingest(con, did, data)
        atomic(args.out / f"page-{page:05d}.v73.json",
               json.dumps(data, ensure_ascii=False, indent=2))
        imported.append(page)
    con.execute("UPDATE documents SET pages=? WHERE id=?", (len(imported), did))
    con.commit()
    print(f"Importadas {len(imported)} páginas; SQLite/FTS: {args.out / 'ocr_v73.sqlite3'}")


if __name__ == "__main__":
    main()
