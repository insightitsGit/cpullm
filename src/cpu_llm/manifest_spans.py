"""PrismManifest span grammar over retrieved chunk text.

SpanIdGrammarMask is the grammar this stack added. It allows only span ids
that were cut from the retrieved evidence. A number in the delivered sentence
must match one of those spans. This does not rewrite the sentence.
"""

from __future__ import annotations

import re
from decimal import Decimal

from prismmanifest.canonicalize import canonicalize_number, to_micro_units
from prismmanifest.ingest.evidence import EvidenceIndex
from prismmanifest.spans.grammar import SpanIdGrammarMask

_NUMBER = re.compile(r"(?<![\w.])\(?[$€£¥]?\d[\d,]*(?:\.\d+)?\)?")


def numeric_tokens(text: str) -> list[str]:
    found: list[str] = []
    for match in _NUMBER.finditer(text):
        token = match.group(0)
        try:
            canonicalize_number(token)
        except ValueError:
            continue
        found.append(token)
    return found


def build_span_grammar(chunks: list[dict[str, str]]) -> tuple[EvidenceIndex, SpanIdGrammarMask]:
    """One evidence span per numeric token in the retrieved chunks."""
    corpus = "\n".join(chunk["chunk_text"] for chunk in chunks)
    index = EvidenceIndex(doc_id="cpu-llm", raw_corpus=corpus)
    span_id = 1
    for chunk in chunks:
        text = chunk["chunk_text"]
        base = corpus.find(text)
        if base < 0:
            base = 0
        for match in _NUMBER.finditer(text):
            token = match.group(0)
            try:
                span = EvidenceIndex.make_span(
                    span_id=span_id,
                    doc_id=chunk["chunk_id"],
                    page=1,
                    char_start=base + match.start(),
                    char_end=base + match.end(),
                    raw_text=token,
                    ocr_confidence=1.0,
                    engine="vectorprism",
                    line_item=chunk["chunk_id"],
                )
            except (ValueError, OverflowError):
                continue
            index.add(span)
            span_id += 1
    return index, SpanIdGrammarMask(index)


def answer_numbers_allowed(answer: str, index: EvidenceIndex, mask: SpanIdGrammarMask) -> bool:
    """Every number in the sentence must be an allowed evidence span."""
    allowed = {
        span.canonical_micro
        for span in index.spans
        if mask.allows(span.span_id)
    }
    for token in numeric_tokens(answer):
        if to_micro_units(canonicalize_number(token)) not in allowed:
            return False
    return True


def canonical_values(index: EvidenceIndex) -> list[str]:
    values: list[str] = []
    for span in index.spans:
        text = format(Decimal(span.canonical_micro) / Decimal(1_000_000), "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        values.append(text)
    return values
