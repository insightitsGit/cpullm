"""Assign a Nammade channel from an explicit span record or from span text.

An explicit ``Nammade span:`` record keeps the stored ``a, b, c, d``. Any other
authorized chunk uses one fixed 3×6 projection of lexical markers. That
projection is a deterministic reading of the text. It is not a physical
measurement and it does not verify the Nammade treatise.

Feature order is causal, mathematical, contradiction, entailment, local, universal.
Density bands follow the Verified Edition ingestion rules:

- ``nammade frontier`` or ``open wave`` → -10
- an explicit invariant statement → +10
- ``prediction`` or ``falsifiable`` → -5
- hypothesis or hedge language → -1
- measured or experimental language → +4
- any other stored source statement → +1

A query is an open probe, so its density is -1. Its spatial state uses the
same projection of the query text.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

import numpy as np

from cpu_llm.nammade.channel import NammadeChannelEncoder
from cpu_llm.nammade.types import NammadeChannel4D

_PREFIX = re.compile(r"^nammade span:\s*", re.IGNORECASE)
_CAUSAL = re.compile(r"\b(?:because|due to|caused|therefore)\b", re.IGNORECASE)
_MATH = re.compile(r"\b(?:invariant|equation|law|theorem)\b|=", re.IGNORECASE)
_CONTRADICTION = re.compile(r"\b(?:not|never|contradict(?:s|ed|ion)?|unless|opposite)\b", re.IGNORECASE)
_ENTAILMENT = re.compile(r"\b(?:implies|entails|therefore|equals)\b", re.IGNORECASE)
_LOCAL = re.compile(r"\b(?:this|local)\b|\d", re.IGNORECASE)
_UNIVERSAL = re.compile(r"\b(?:all|every|universal|always|invariant)\b", re.IGNORECASE)
_FRONTIER = re.compile(r"\b(?:nammade frontier|open wave)\b", re.IGNORECASE)
_INVARIANT = re.compile(r"\b(?:is an invariant|structural invariant|matter invariant)\b", re.IGNORECASE)
_PREDICTION = re.compile(r"\b(?:prediction|falsifiable)\b", re.IGNORECASE)
_HYPOTHESIS = re.compile(r"\b(?:hypothesis|hypotheses|might|could|propose|proposed)\b", re.IGNORECASE)
_MEASURED = re.compile(r"\b(?:measured|experiment(?:al)?|observed)\b", re.IGNORECASE)
_DOMAIN = re.compile(r"[A-Z][A-Z0-9_]{0,31}")

LEXICAL_PROJECTION = np.array(
    [
        [0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, -1.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0, -1.0, 1.0],
    ],
    dtype=np.float32,
)


@dataclass(frozen=True)
class EncodedSpan:
    source_id: str
    span_text: str
    span_hash: str
    channel: NammadeChannel4D
    explicit: bool
    is_invariant: bool
    domain_mask: tuple[str, ...]


def lexical_features(text: str) -> np.ndarray:
    return np.array(
        [
            1.0 if _CAUSAL.search(text) else 0.0,
            1.0 if _MATH.search(text) else 0.0,
            1.0 if _CONTRADICTION.search(text) else 0.0,
            1.0 if _ENTAILMENT.search(text) else 0.0,
            1.0 if _LOCAL.search(text) else 0.0,
            1.0 if _UNIVERSAL.search(text) else 0.0,
        ],
        dtype=np.float32,
    )


def source_density(text: str) -> float:
    if _FRONTIER.search(text):
        return -10.0
    if _INVARIANT.search(text):
        return 10.0
    if _PREDICTION.search(text):
        return -5.0
    if _HYPOTHESIS.search(text):
        return -1.0
    if _MEASURED.search(text):
        return 4.0
    return 1.0


def encode_state(text: str, raw_density: float) -> NammadeChannel4D:
    return NammadeChannelEncoder.encode_from_relational(
        lexical_features(text),
        LEXICAL_PROJECTION,
        raw_density,
    )


def encode_query(text: str) -> NammadeChannel4D:
    return encode_state(text, -1.0)


def span_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _domain_mask(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) and _DOMAIN.fullmatch(item) for item in value):
        raise ValueError("domain_mask must be a list of domain tokens")
    return tuple(value)


def parse_explicit_span(document_id: str, chunk: str) -> EncodedSpan:
    """Parse a chunk that begins with ``Nammade span:`` and one JSON object."""
    body = _PREFIX.sub("", chunk.strip(), count=1)
    try:
        payload, end = json.JSONDecoder().raw_decode(body)
    except json.JSONDecodeError as exc:
        raise ValueError("explicit Nammade span is not a JSON object") from exc
    if not isinstance(payload, dict):
        raise ValueError("explicit Nammade span is not a JSON object")
    remainder = body[end:].strip()
    text = payload.get("text", remainder)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("explicit Nammade span has no proposition text")
    if "text" in payload and remainder:
        raise ValueError("explicit Nammade span repeats its proposition text")
    invariant = payload.get("is_invariant", False)
    if not isinstance(invariant, bool):
        raise ValueError("is_invariant must be a boolean")
    channel = NammadeChannel4D(payload["a"], payload["b"], payload["c"], payload["d"])
    proposition = text.strip()
    return EncodedSpan(
        source_id=document_id,
        span_text=proposition,
        span_hash=span_hash(proposition),
        channel=channel,
        explicit=True,
        is_invariant=invariant,
        domain_mask=_domain_mask(payload.get("domain_mask")),
    )


def encode_chunk(document_id: str, chunk: str) -> EncodedSpan:
    text = chunk.strip()
    if _PREFIX.match(text):
        return parse_explicit_span(document_id, text)
    proposition = text
    return EncodedSpan(
        source_id=document_id,
        span_text=proposition,
        span_hash=span_hash(proposition),
        channel=encode_state(proposition, source_density(proposition)),
        explicit=False,
        is_invariant=bool(_INVARIANT.search(proposition)),
        domain_mask=(),
    )
