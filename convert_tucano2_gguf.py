#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conversor Tucano2 (Metaspace ▁ + byte-fallback) -> GGUF qwen2 (bytes_to_unicode).

Problema: o convert_hf_to_gguf.py atual (transformers 5.x / TokenizersBackend)
lê o vocabulário "como está" do tokenizer.json: peças "<0xNN>" (byte fallback)
viram tokens literais de texto e "▁" (Metaspace) fica cru dentro de tokens
NORMAL. O llama.cpp espera, para pre=qwen2/model=gpt2, a codificação
bytes_to_unicode (GPT-2): byte 0x0A -> 'Ċ', byte 0x20 -> 'Ġ', etc.

Este script sobrescreve set_vocab do Qwen3Model com uma implementação que
converte cada peça do tokenizer.json para essa codificação:
  ▁ (U+2581) -> byte 0x20 (espaço) -> char bytes_to_unicode
  <0xNN>     -> byte NN            -> char bytes_to_unicode
  demais     -> bytes UTF-8        -> char bytes_to_unicode por byte

Uso (igual ao convert_hf_to_gguf.py):
  python convert_tucano2_gguf.py <dir-do-modelo> --outtype f16 --outfile X.gguf
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LLAMA_CPP = "/home/igor/llama.cpp"
sys.path.insert(0, LLAMA_CPP)

import convert_hf_to_gguf  # noqa: E402
import gguf  # noqa: E402
from conversion import qwen  # noqa: E402
from gguf import TokenType  # noqa: E402


def _bytes_to_unicode() -> dict[int, str]:
    bs = (
        list(range(ord("!"), ord("~") + 1))
        + list(range(ord("¡"), ord("¬") + 1))
        + list(range(ord("®"), ord("ÿ") + 1))
    )
    cs = bs[:]
    n = 0
    for b in range(2 ** 8):
        if b not in bs:
            bs.append(b)
            cs.append(2 ** 8 + n)
            n += 1
    return {b: chr(c) for b, c in zip(bs, cs)}


_B2C = _bytes_to_unicode()
_BYTE_PIECE_RE = re.compile(r"<0x([0-9A-Fa-f]{2})>")


def _piece_to_bytes(piece: str) -> list[int]:
    """Converte uma peça do tokenizer.json em bytes crus."""
    if _BYTE_PIECE_RE.fullmatch(piece):
        return [int(piece[3:5], 16)]
    raw: list[int] = []
    for ch in piece:
        if ch == "\u2581":          # Metaspace marker == espaco
            raw.append(0x20)
        else:
            raw.extend(ch.encode("utf-8"))
    return raw


def _piece_to_token_text(piece: str) -> str:
    return "".join(_B2C[b] for b in _piece_to_bytes(piece))


def _merge_to_str(pair) -> str:
    if isinstance(pair, str):           # "a b"
        a, b = pair.split(" ", 1)
    else:                               # ["a", "b"]
        a, b = pair
    return f"{_piece_to_token_text(a)} {_piece_to_token_text(b)}"


def _read_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def set_vocab_metaspace_qwen2(self) -> None:
    """Qwen3Model.set_vocab: tokenizer Metaspace(▁) + byte-fallback -> qwen2."""
    dir_model = self.dir_model

    try:
        tokenizer_json = _read_json(dir_model / "tokenizer.json")
    except FileNotFoundError:
        # não é o formato alvo; cai no comportamento padrão
        return qwen.Qwen3Model.set_vocab_ORIGINAL(self)

    model = tokenizer_json.get("model") or {}
    vocab = model.get("vocab") or {}
    merges = model.get("merges") or []
    added_tokens = tokenizer_json.get("added_tokens") or []

    tokenizer_config = _read_json(dir_model / "tokenizer_config.json")
    added_decoder = tokenizer_config.get("added_tokens_decoder", {})
    vocab_size = int(self.hparams["vocab_size"])

    tokens: list[str] = [""] * vocab_size
    toktypes: list[int] = [int(TokenType.UNUSED)] * vocab_size

    # 1) peças do BPE base (byte-fallback e Metaspace incluidas)
    byte_piece_ids: set[int] = set()
    for piece, tid in vocab.items():
        tid = int(tid)
        if tid >= vocab_size:
            continue
        tokens[tid] = _piece_to_token_text(piece)
        toktypes[tid] = int(TokenType.NORMAL)
        if _BYTE_PIECE_RE.fullmatch(piece):
            byte_piece_ids.add(tid)

    # 2) tokens adicionados (especiais) — texto literal, flags do added_tokens
    for item in added_tokens:
        tid = int(item["id"])
        if tid >= vocab_size:
            continue
        content = item["content"]
        special = bool(item.get("special", False))
        tokens[tid] = content
        toktypes[tid] = int(TokenType.CONTROL if special else TokenType.USER_DEFINED)

    # 3) added_tokens_decoder pode trazer flags mais corretas
    for tid_s, data in added_decoder.items():
        tid = int(tid_s)
        if tid >= vocab_size:
            continue
        if data.get("special") or self.does_token_look_special(data["content"]):
            toktypes[tid] = int(TokenType.CONTROL)
        else:
            toktypes[tid] = int(TokenType.USER_DEFINED)
        tokens[tid] = data["content"]

    # 4) texto duplicado não é permitido no GGUF BPE (assert id_to_token ==
    #    token_to_id). As peças de byte-fallback colidem com lexemas vivos
    #    ('<0x20>' vs '▁', '<0x21>' vs '!'...), e o HF só usa o byte-fallback
    #    para bytes SEM lexema (ex.: <0x0A> newline). Regra: demover a peça
    #    byte-fallback colidente para UNUSED e manter o lexema.
    seen: dict[str, int] = {}
    for tid in range(vocab_size):
        text = tokens[tid]
        if text == "":
            continue
        if text in seen:
            other = seen[text]
            # demote o byte-fallback (id menor), mantém o lexema
            demote = tid if tid in byte_piece_ids else other
            keep = other if demote == tid else tid
            assert demote in byte_piece_ids, f"colisão sem byte-fallback: {text!r}"
            tokens[demote] = f"[PAD{demote}]"
            toktypes[demote] = int(TokenType.UNUSED)
            seen[text] = keep
        else:
            seen[text] = tid

    painted = sum(1 for i, t in enumerate(tokens) if t != "")
    if painted != vocab_size:
        raise RuntimeError(
            f"vocab incompleto: {painted}/{vocab_size} tokens preenchidos"
        )
    if any(not t for t in tokens):
        raise RuntimeError("há tokens vazios no vocabulário")

    self.gguf_writer.add_tokenizer_model("gpt2")
    self.gguf_writer.add_tokenizer_pre("qwen2")
    self.gguf_writer.add_token_list(tokens)
    self.gguf_writer.add_token_types(toktypes)

    # 5) merges: originais (transformados) + sintéticos byte-nível.
    #    O BPE do Tucano2 é char-level (Metaspace): peças como 'á' são átomos
    #    sem merges-pai. No encoding gpt2 do llama.cpp, 'á' vira 2 chars
    #    ('Ã' + '¡'), e sem merge 'Ã ¡' o tokenizer sempre separa em 2 tokens.
    #    Reconstruímos o caminho byte-BPE: para cada peça de k>=2 chars,
    #    adicionamos os merges de prefixo (c1..cj, cj+1..ck) — eles só disparam
    #    quando nenhum merge treinado se aplica, restaurando a tokenização
    #    de 1 token por peça (idêntica ao HF).
    gguf_merges: list[str] = [_merge_to_str(m) for m in merges]
    merge_set: set[str] = set(gguf_merges)

    def _add_merge(a: str, b: str):
        key = f"{a} {b}"
        if key not in merge_set:
            merge_set.add(key)
            gguf_merges.append(key)

    for tid in range(vocab_size):
        text = tokens[tid]
        if toktypes[tid] != int(TokenType.NORMAL):
            continue
        chars = list(text)
        if len(chars) < 2 or text.startswith("[PAD"):
            continue
        # split 1..k-1 at EVERY position (chain normaliza do fim p/ o início:
        # (c1..c{k-1}, ck) primeiro, depois seus prefixos na ordem de tamanho)
        for j in range(len(chars) - 1, 0, -1):
            _add_merge("".join(chars[:j]), "".join(chars[j:]))

    self.gguf_writer.add_token_merges(gguf_merges)

    special_vocab = gguf.SpecialVocab(dir_model, load_merges=False)
    special_vocab.merges = []
    special_vocab.add_to_gguf(self.gguf_writer)


# guarda o original e instala o override
qwen.Qwen3Model.set_vocab_ORIGINAL = qwen.Qwen3Model.set_vocab
qwen.Qwen3Model.set_vocab = set_vocab_metaspace_qwen2


if __name__ == "__main__":
    convert_hf_to_gguf.main()