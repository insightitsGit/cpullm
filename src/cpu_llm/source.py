"""WikiText-2 validation paragraphs, as published.

VectorPrism does not split text. This module reads the downloaded source and
emits one chunk per paragraph. It keeps every paragraph. It does not keep
only the lead, and it does not drop articles.
"""

from __future__ import annotations

import re
from pathlib import Path

_MARKERS = (
    (" @-@ ", "-"),
    (" @.@ ", "."),
    (" @,@ ", ","),
)
_CONTRACTIONS = ("s", "re", "ve", "ll", "d", "m")
_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?])")
_OPEN_PAREN = re.compile(r"\(\s+")
_CLOSE_PAREN = re.compile(r"\s+\)")
_TITLE = re.compile(r"^= (?!=).+ =$")


def validation_path() -> Path:
    return _split_path("validation.parquet")


def test_path() -> Path:
    return _split_path("test.parquet")


def _split_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "wikitext-2-raw-v1" / name


def detokenize(text: str) -> str:
    for marker, replacement in _MARKERS:
        text = text.replace(marker, replacement)
    text = text.replace(" n't", "n't")
    for ending in _CONTRACTIONS:
        text = text.replace(f" '{ending}", f"'{ending}")
    text = _BEFORE_PUNCT.sub(r"\1", text)
    text = _OPEN_PAREN.sub("(", text)
    text = _CLOSE_PAREN.sub(")", text)
    return " ".join(text.split())


def validation_chunks(path: Path | None = None) -> list[tuple[str, str, str]]:
    """Return (document_id, title, paragraph) for every validation paragraph."""
    return wikitext_chunks(path or validation_path(), prefix="wikitext2")


def test_chunks(path: Path | None = None) -> list[tuple[str, str, str]]:
    """Return (document_id, title, paragraph) for every test-split paragraph.

    Ids use the prefix ``wikitext2test-``. A later validation replace deletes
    ``wikitext2-%`` and must not remove this split.
    """
    return wikitext_chunks(path or test_path(), prefix="wikitext2test")


def wikitext_chunks(path: Path, *, prefix: str) -> list[tuple[str, str, str]]:
    """Return (document_id, title, paragraph) for every paragraph in ``path``."""
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    lines = [row.strip() for row in table.column("text").to_pylist()]
    chunks: list[tuple[str, str, str]] = []
    title: str | None = None
    paragraph_number = 0
    for line in lines:
        if _TITLE.match(line):
            title = detokenize(line.strip("= ").strip())
            paragraph_number = 0
            continue
        if title is None or not line or line.startswith("="):
            continue
        paragraph_number += 1
        chunks.append((_document_id(prefix, title, paragraph_number), title, detokenize(line)))
    return chunks


def _document_id(prefix: str, title: str, paragraph_number: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")
    return f"{prefix}-{slug[:72]}-p{paragraph_number:04d}"
