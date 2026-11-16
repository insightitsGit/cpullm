"""Word relations taken from a span's Nammade channel.

The Nammade scan builds these relations from the spans it is reading. Two
content words that share a span are related by that span's channel. ``b``
chooses the logical kind: entailment, contradiction, or orthogonal
independence. ``a`` is the structural weight, ``c`` is the horizon scale, and
``d`` is the zero-free density. A word pair is a polarity bridge when one of
those spans puts it at ``d <= -1`` and another puts it at ``d >= 1``.

Nothing here is written to the category-hop file or the 1024-d tensor.
"""
from __future__ import annotations

from cpu_llm.channels import _content_words
from cpu_llm.nammade.encode import EncodedSpan

_REPLY_CAP = 12
_PAIR_CAP = 128


def relation_kind(polarity: float) -> str:
    """Logical kind of ``b``. Zero is orthogonal independence."""
    if polarity > 0.0:
        return "entails"
    if polarity < 0.0:
        return "contradicts"
    return "orthogonal"


def relations_from_span(span: EncodedSpan, words: set[str] | None = None) -> list[dict]:
    """Pairs in ``span`` whose channel supplies the relation. ``words`` keeps pairs that touch the query."""
    tokens = list(dict.fromkeys(_content_words(span.span_text)))
    if len(tokens) < 2:
        return []
    pairs = [tuple(sorted((left, right))) for index, left in enumerate(tokens) for right in tokens[index + 1 :]]
    pairs = list(dict.fromkeys(pairs))
    if words is not None:
        pairs = [pair for pair in pairs if pair[0] in words or pair[1] in words]
    pairs.sort()
    kind = relation_kind(span.channel.b)
    rows = []
    for left, right in pairs[:_PAIR_CAP]:
        rows.append(
            {
                "left": left,
                "right": right,
                "kind": kind,
                "a": span.channel.a,
                "b": span.channel.b,
                "c": span.channel.c,
                "d": span.channel.d,
                "document_id": span.source_id,
                "span_hash": span.span_hash,
            }
        )
    return rows


def relations_for_query(spans: list[EncodedSpan], words: list[str], *, limit: int = _REPLY_CAP) -> list[dict]:
    """Relations in ``spans`` that touch the query words, with opposite densities marked as a bridge."""
    wanted = {word.casefold() for word in words}
    if not wanted or not spans:
        return []
    touching: list[dict] = []
    for span in spans:
        touching.extend(relations_from_span(span, wanted))
    bridges = _bridge_pairs(touching)
    marked = []
    for row in touching:
        copy = dict(row)
        copy["polarity_bridge"] = (row["left"], row["right"]) in bridges
        marked.append(copy)
    marked.sort(key=lambda row: (
        0 if row["polarity_bridge"] else 1,
        {"contradicts": 0, "entails": 1, "orthogonal": 2}[row["kind"]],
        row["left"],
        row["right"],
        row["document_id"],
    ))
    return marked[:limit]


def _bridge_pairs(rows: list[dict]) -> set[tuple[str, str]]:
    grouped: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        grouped.setdefault((row["left"], row["right"]), []).append(float(row["d"]))
    bridges = set()
    for pair, densities in grouped.items():
        if any(density <= -1.0 for density in densities) and any(density >= 1.0 for density in densities):
            bridges.add(pair)
    return bridges
