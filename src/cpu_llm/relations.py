"""Second- and third-hand word relations for creation, training, and sleep.

PrismRAG connects words that share a category and expands a search two hops.
It does not label those hops, and it stops before a third hand. This module
walks the same undirected edges one hand at a time, through three hands.

A paragraph's content words are the seeds. The first hand is the words that
share an edge with a seed. The second hand is the next ring. The third hand
is the ring after that. Words that occur in too many paragraphs are not
bridges, so a common word does not tie unrelated articles together.

The hands are written into the tail of the relational channel, 32 values
whose length is 0.05. The dense core and the rest of the relational channel
stay as VectorPrism stored them. A large integer in that channel is what
pulled unrelated paragraphs into why-questions, so this write stays small.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
from prismrag_patch.store.types import GraphEdge
from vectorprism.tensor_contract import PSMTensorContract

from cpu_llm.channels import _best_sentence, _content_words

_RELATION = PSMTensorContract.RELATIONAL
_TAIL = 32
_TAIL_NORM = 0.05
_MAX_DEGREE = 8
_MAX_DF = 12
_HANDS = 3
_HAND_LIMIT = 8
_SCALE = {1: 1.0, 2: 0.5, 3: 0.25}


def relation_hands(
    edges: list[GraphEdge],
    seeds: list[str],
    *,
    hands: int = _HANDS,
    limit: int = _HAND_LIMIT,
) -> dict[int, list[str]]:
    """Words reached at each hand.

    Hand 1 shares an edge with a seed. Hand 2 is one edge further. Hand 3 is
    the edge after that. Seeds are not listed again. The order is alphabetical
    and each hand stops at ``limit`` words.
    """
    adjacent: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        adjacent[edge.from_word].add(edge.to_word)
        adjacent[edge.to_word].add(edge.from_word)
    seen = set(seeds)
    frontier = set(seeds)
    found = {hand: [] for hand in range(1, hands + 1)}
    for hand in range(1, hands + 1):
        nxt: set[str] = set()
        for node in frontier:
            nxt.update(adjacent.get(node, ()))
        nxt -= seen
        chosen = sorted(nxt)[:limit]
        found[hand] = chosen
        seen.update(chosen)
        frontier = set(chosen)
        if not frontier:
            break
    return found


def edges_from_passages(
    chunks: list[tuple[str, str]],
    *,
    base_counts: dict[str, int] | None = None,
    max_degree: int = _MAX_DEGREE,
    max_df: int = _MAX_DF,
) -> list[GraphEdge]:
    """Rule edges between words that share a paragraph.

    A word that appears in more than ``max_df`` paragraphs is not a bridge.
    Each word keeps at most ``max_degree`` partners, the rarer ones first.
    """
    counts: dict[str, int] = defaultdict(int)
    passages: list[list[str]] = []
    for _document_id, text in chunks:
        words = list(dict.fromkeys(_content_words(text)))
        passages.append(words)
        for word in words:
            counts[word] += 1
    if base_counts:
        for word, value in base_counts.items():
            counts[word] = max(counts[word], int(value))
    candidates: dict[str, set[str]] = defaultdict(set)
    for words in passages:
        usable = [word for word in words if counts[word] <= max_df]
        for left, right in combinations(usable, 2):
            candidates[left].add(right)
            candidates[right].add(left)
    ranked: list[tuple[int, str, str]] = []
    for word, partners in candidates.items():
        for other in partners:
            if word < other:
                ranked.append((max(counts[word], counts[other]), word, other))
    ranked.sort()
    degree: dict[str, int] = defaultdict(int)
    edges: list[GraphEdge] = []
    for _rarity, left, right in ranked:
        if degree[left] >= max_degree or degree[right] >= max_degree:
            continue
        edges.append(GraphEdge(left, right, "rule", 1.0))
        degree[left] += 1
        degree[right] += 1
    return edges


def hands_for_text(edges: list[GraphEdge], text: str) -> dict[int, list[str]]:
    words = _content_words(text)
    if not words or not edges:
        return {1: [], 2: [], 3: []}
    return relation_hands(edges, words)


def apply_relation_signature(tensor: np.ndarray, hands: dict[int, list[str]]) -> np.ndarray:
    """Copy ``tensor`` and write the hand signature into the relational tail.

    An empty hand list leaves the tensor unchanged. The dense core is not
    written. The first part of the relational channel is not written.
    """
    vector = np.asarray(tensor, dtype=np.float32).reshape(-1).copy()
    if vector.shape != (PSMTensorContract.TOTAL_DIM,):
        raise ValueError(f"expected a 1024-d tensor, got {vector.shape}")
    packed = _signature(hands)
    if packed is None:
        return vector
    start = _RELATION.end - _TAIL
    vector[start : _RELATION.end] = packed
    return vector


def load_edges(path: Path) -> list[GraphEdge]:
    if not path.exists():
        return []
    loaded = json.loads(path.read_text(encoding="utf-8"))
    rows = loaded.get("edges") if isinstance(loaded, dict) else None
    if not isinstance(rows, list):
        return []
    edges: list[GraphEdge] = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 2:
            continue
        edges.append(GraphEdge(str(row[0]), str(row[1]), "rule", 1.0))
    return edges


def save_edges(path: Path, edges: list[GraphEdge]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted((edge.from_word, edge.to_word) for edge in edges)
    path.write_text(json.dumps({"edges": rows}), encoding="utf-8")


def add_edges(path: Path, pairs: list[tuple[str, str]]) -> int:
    """Store endpoint pairs from a sheet without dropping the edges already there."""
    current = {(edge.from_word, edge.to_word) for edge in load_edges(path)}
    added = 0
    for left, right in pairs:
        left = left.strip().casefold()
        right = right.strip().casefold()
        if not left or not right or left == right:
            continue
        key = tuple(sorted((left, right)))
        if key in current:
            continue
        current.add(key)
        added += 1
    save_edges(path, [GraphEdge(left, right, "rule", 1.0) for left, right in sorted(current)])
    return added


def merge_passage_edges(
    path: Path,
    chunks: list[tuple[str, str]],
    word_tags: dict[str, dict[str, list[str]]] | None = None,
) -> list[GraphEdge]:
    """Add edges from ``chunks`` without dropping edges already stored."""
    current = {(edge.from_word, edge.to_word) for edge in load_edges(path)}
    degree: dict[str, int] = defaultdict(int)
    for left, right in current:
        degree[left] += 1
        degree[right] += 1
    for edge in edges_from_passages(chunks, base_counts=_document_counts(word_tags)):
        key = tuple(sorted((edge.from_word, edge.to_word)))
        if key in current:
            continue
        if degree[key[0]] >= _MAX_DEGREE or degree[key[1]] >= _MAX_DEGREE:
            continue
        current.add(key)
        degree[key[0]] += 1
        degree[key[1]] += 1
    edges = [GraphEdge(left, right, "rule", 1.0) for left, right in sorted(current)]
    save_edges(path, edges)
    return edges


def sign_and_store(db: Any, rows: list[tuple[str, str, np.ndarray]], edges: list[GraphEdge]) -> int:
    """Write the hand signature for each row that has a relation.

    ``rows`` are ``(document_id, text, tensor)``. The tensor VectorPrism
    stored is copied. Only the relational tail changes.
    """
    from cpu_llm.word_taxonomy import write_stamped_tensor

    written = 0
    for document_id, text, tensor in rows:
        hands = hands_for_text(edges, text)
        if not any(hands.values()):
            continue
        signed = apply_relation_signature(tensor, hands)
        write_stamped_tensor(db, document_id, text, signed)
        written += 1
    return written


def creation_relations(
    edges: list[GraphEdge],
    word_tags: dict[str, dict[str, list[str]]],
    message: str,
    exclude: set[str],
    *,
    per_hand: int = 4,
) -> tuple[dict[int, list[str]], list[tuple[int, str, str]]]:
    """Second- and third-hand paragraphs for a creative prompt.

    The result is the hand lists and ``(hand, document_id, word)`` rows.
    Document ids already in ``exclude`` are left out. Each hand returns at
    most ``per_hand`` paragraphs.
    """
    seeds = _content_words(message)
    hands = relation_hands(edges, seeds) if seeds and edges else {1: [], 2: [], 3: []}
    chosen: list[tuple[int, str, str]] = []
    seen = set(exclude)
    for hand in (2, 3):
        count = 0
        for word in hands.get(hand, []):
            by_slug = word_tags.get(word) or {}
            for document_ids in by_slug.values():
                for document_id in document_ids:
                    if document_id in seen:
                        continue
                    chosen.append((hand, document_id, word))
                    seen.add(document_id)
                    count += 1
                    if count >= per_hand:
                        break
                if count >= per_hand:
                    break
            if count >= per_hand:
                break
    return hands, chosen


def relation_sentences(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stored sentences for the related paragraphs creation loaded."""
    found: list[dict[str, Any]] = []
    for row in rows:
        sentence = _best_sentence(str(row.get("chunk_text") or ""), str(row.get("word") or ""))
        if not sentence:
            continue
        found.append(
            {
                "hand": int(row["relation_hand"]),
                "document_id": str(row["document_id"]),
                "word": str(row.get("word") or ""),
                "sentence": sentence,
            }
        )
    return found


def _document_counts(word_tags: dict[str, dict[str, list[str]]] | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for word, by_slug in (word_tags or {}).items():
        counts[str(word)] = sum(len(document_ids) for document_ids in by_slug.values())
    return counts


def _signature(hands: dict[int, list[str]]) -> np.ndarray | None:
    packed = np.zeros(_TAIL, dtype=np.float64)
    used = False
    for hand, words in hands.items():
        scale = _SCALE.get(int(hand))
        if scale is None:
            continue
        for word in words:
            digest = hashlib.sha256(f"{hand}:{word}".encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % _TAIL
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            packed[index] += sign * scale
            used = True
    if not used:
        return None
    norm = float(np.linalg.norm(packed))
    if norm == 0.0:
        return None
    return (packed / norm * _TAIL_NORM).astype(np.float32)
