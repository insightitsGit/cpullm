"""Taxonomy of the words stored in a source, built at training time.

PrismRAG records each content word under the article it was written in.
PrismResonance keeps a tag for that word in the article's group, and
co-activates the tag with every paragraph that contains the word.

The article slug is the category. A query word recalls the tag, and the tag
names the paragraphs. The graph node holds those tags. Offline consolidation
writes related terms onto the node. It does not rewrite the stored tensor.
No edge is invented from a sentence that does not contain the word.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from prismrag_patch import PrismRAG
from prismresonance import FrequencyFamily, PrismResonance
from vectorprism.tensor_contract import PSMTensorContract

from cpu_llm.catalog import article_slug, title_slugs
from cpu_llm.channels import _content_words

TAG_PREFIX = "tag:"
_RELATION = PSMTensorContract.RELATIONAL
_MAX_RECALL = 12


def tag_id(slug: str, word: str) -> str:
    return f"{TAG_PREFIX}{slug}:{word}"


def category_number(slug: str) -> int:
    """Stable integer stored in the relational slice for one article.

    Float32 represents every integer in this range exactly, so two paragraphs
    of the same article compare equal.
    """
    digest = hashlib.sha256(slug.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % 1_000_000 + 1


def stamp_relation(tensor: np.ndarray, number: int) -> np.ndarray:
    """Write ``number`` into the first relational component. The dense core stays."""
    stamped = np.asarray(tensor, dtype=np.float32).reshape(-1).copy()
    if stamped.shape != (PSMTensorContract.TOTAL_DIM,):
        raise ValueError(f"expected a 1024-d tensor, got {stamped.shape}")
    stamped[_RELATION.start] = np.float32(number)
    return stamped


def word_index(chunks: list[tuple[str, str]]) -> dict[str, dict[str, list[str]]]:
    """word -> article slug -> document ids that contain the word."""
    index: dict[str, dict[str, list[str]]] = {}
    for document_id, text in chunks:
        slug = article_slug(document_id)
        for word in _content_words(text):
            by_slug = index.setdefault(word, {})
            ids = by_slug.setdefault(slug, [])
            if document_id not in ids:
                ids.append(document_id)
    return index


def merge_word_index(
    path: Path,
    incoming: dict[str, dict[str, list[str]]],
) -> dict[str, dict[str, list[str]]]:
    current = load_word_index(path)
    for word, by_slug in incoming.items():
        stored = current.setdefault(word, {})
        for slug, document_ids in by_slug.items():
            have = stored.setdefault(slug, [])
            for document_id in document_ids:
                if document_id not in have:
                    have.append(document_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current), encoding="utf-8")
    return current


def _matches_document_prefix(document_id: str, prefix: str) -> bool:
    from cpu_llm.source_ids import matches_prefix

    return matches_prefix(document_id, prefix)


def drop_document_prefix(index: dict[str, dict[str, list[str]]], prefix: str) -> int:
    """Remove document ids that belong to ``prefix``. Empty words are dropped."""
    removed = 0
    for word in list(index):
        by_slug = index.get(word)
        if not isinstance(by_slug, dict):
            continue
        for slug in list(by_slug):
            ids = by_slug.get(slug)
            if not isinstance(ids, list):
                continue
            kept = [
                document_id
                for document_id in ids
                if not _matches_document_prefix(str(document_id), prefix)
            ]
            removed += len(ids) - len(kept)
            if kept:
                by_slug[slug] = kept
            else:
                del by_slug[slug]
        if not by_slug:
            del index[word]
    return removed


def load_word_index(path: Path) -> dict[str, dict[str, list[str]]]:
    if not path.exists():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return {}
    return loaded


def slug_fits(named: list[str], slug: str) -> bool:
    for name in named:
        if name == slug or slug.startswith(name + "-") or name.startswith(slug + "-"):
            return True
    return False


def recall_document_ids(
    resonance: PrismResonance,
    word_tags: dict[str, dict[str, list[str]]],
    message: str,
    *,
    limit: int = _MAX_RECALL,
    skip_words: set[str] | None = None,
    allowed_slugs: set[str] | None = None,
) -> list[str]:
    """Paragraphs the query words were tagged with during training.

    A named article limits the tags to that article. The rarest matching word
    is called first, through the resonance tag. Words already written in the
    shortlist are skipped, and a paragraph is kept only when its article is
    already in that shortlist.
    """
    named = title_slugs(message)
    ranked: list[tuple[int, str, str]] = []
    for word in _content_words(message):
        if skip_words and word in skip_words:
            continue
        by_slug = word_tags.get(word) or {}
        slugs = [
            slug
            for slug in by_slug
            if (not named or slug_fits(named, slug)) and (allowed_slugs is None or slug in allowed_slugs)
        ]
        total = sum(len(by_slug[slug]) for slug in slugs)
        if total:
            ranked.append((total, word, slugs[0] if len(slugs) == 1 else ""))
    ranked.sort()
    found: list[str] = []
    for _total, word, only_slug in ranked:
        by_slug = word_tags[word]
        slugs = [only_slug] if only_slug else [
            slug
            for slug in by_slug
            if (not named or slug_fits(named, slug)) and (allowed_slugs is None or slug in allowed_slugs)
        ]
        for slug in slugs:
            ordered = _recalled_documents(resonance, slug, word, limit)
            if not ordered:
                ordered = list(by_slug.get(slug) or [])
            for document_id in ordered:
                if document_id not in found:
                    found.append(document_id)
                if len(found) >= limit:
                    return found
    return found


def _recalled_documents(resonance: PrismResonance, slug: str, word: str, limit: int) -> list[str]:
    """Document ids co-activated with this word.

    New tags use ``{category}:{term}``. Tags written before that key still
    answer as ``tag:{category}:{term}``.
    """
    spec = f"{slug}:{word}"
    ordered: list[str] = []
    for candidate in (spec, tag_id(slug, word)):
        for partner, _count in resonance.most_related(candidate, n=limit):
            if partner == spec or partner == tag_id(slug, word) or partner.startswith(TAG_PREFIX):
                continue
            if partner not in ordered:
                ordered.append(partner)
    return ordered


def taxonomize_words(index: dict[str, dict[str, list[str]]], tenant_id: str = "cpu-llm") -> PrismRAG:
    """Register every stored word under its article with PrismRAG."""
    categories: list[dict[str, str]] = []
    rules: list[dict[str, str]] = []
    seen_slugs: set[str] = set()
    seen_rules: set[tuple[str, str]] = set()
    for word, by_slug in index.items():
        for slug in by_slug:
            if slug not in seen_slugs:
                seen_slugs.add(slug)
                categories.append({"slug": slug, "label": slug.replace("-", " ")})
            key = (word, slug)
            if key in seen_rules:
                continue
            seen_rules.add(key)
            rules.append({"word": word, "category_slug": slug})
    if categories and not rules:
        rules.append({"word": categories[0]["slug"], "category_slug": categories[0]["slug"]})
    rag = PrismRAG(
        mapping={"categories": categories or [{"slug": "untagged", "label": "untagged"}], "rules": rules or [{"word": "untagged", "category_slug": "untagged"}]},
        tenant_id=tenant_id,
    )
    records = [
        {"word": word, "text": word, "category_hint": slug}
        for word, by_slug in index.items()
        for slug in by_slug
    ]
    if records:
        rag.ingest(records=records)
    return rag


def bind_word_taxonomy(
    resonance: PrismResonance,
    chunks: list[tuple[str, str]],
    tensors: list[np.ndarray],
    *,
    tags_path: Path,
    amplitudes: list[np.ndarray] | None = None,
    tenant_id: str = "cpu-llm",
) -> dict[str, Any]:
    """Tag every content word and checkpoint the resonance ledger.

    ``amplitudes`` are the 1024-d resonance vectors. When omitted, the stored
    tensor's dense core is used. The returned tensors carry the article's
    category number in memory. Callers that persist rows keep the tensor
    VectorPrism stored.
    """
    from cpu_llm.pipeline import resonance_amplitude

    incoming = word_index(chunks)
    merged = merge_word_index(tags_path, incoming)
    rag = taxonomize_words(incoming, tenant_id)
    seen_tags: set[str] = set()
    stamped: list[np.ndarray] = []
    for (document_id, text), tensor in zip(chunks, tensors):
        slug = article_slug(document_id)
        number = category_number(slug)
        vector = stamp_relation(tensor, number)
        stamped.append(vector)
        amplitude = (
            amplitudes[len(stamped) - 1]
            if amplitudes is not None
            else resonance_amplitude(vector)
        )
        resonance.ingest(
            document_id,
            amplitude,
            frequency=FrequencyFamily.NEUTRAL,
            group_id=slug,
        )
        for word in _content_words(text):
            tag = tag_id(slug, word)
            if tag not in seen_tags:
                resonance.ingest(
                    tag,
                    amplitude,
                    frequency=FrequencyFamily.NEUTRAL,
                    group_id=slug,
                )
                seen_tags.add(tag)
            resonance.record_co_activation(tag, document_id)
    if chunks:
        resonance.sleep()
    return {
        "words": len(incoming),
        "tags": len(seen_tags),
        "categories": len({article_slug(document_id) for document_id, _text in chunks}),
        "index": merged,
        "prismrag_tenant": rag.tenant_id,
        "tensors": stamped,
    }


def write_stamped_tensor(db, document_id: str, text: str, tensor: np.ndarray) -> None:
    """Replace one stored tensor with ``tensor``."""
    vector = np.asarray(tensor, dtype=np.float32).reshape(-1)
    unpacked = PSMTensorContract.unpack_header(vector)
    db.upsert(
        document_id,
        text,
        vector,
        {
            "epistemic_truth": float(unpacked["epistemic_truth"]),
            "anchor_dist": float(unpacked["anchor_distance"]),
            "valid_timestamp": int(unpacked["timestamp"]),
            "model_version": int(unpacked["model_version"]),
        },
    )


def main() -> None:
    """Tag the stored WikiText rows. The stored tensors are left as they are."""
    import os

    import psycopg
    from pgvector.psycopg import register_vector

    from cpu_llm.pipeline import TENSOR_DIM
    from cpu_llm.retrieval import LOCAL_PG_DSN

    dsn = os.environ.get("VECTORPRISM_PG_DSN") or LOCAL_PG_DSN
    cache = Path(".chorusgraph") / "cpu-llm"
    resonance = PrismResonance.create(
        embedding_dim=TENSOR_DIM,
        onnx_path=cache / "resonance_1024.onnx",
        state_path=cache / "resonance_state.db",
        coherence_threshold=-1.0,
        load_state=True,
    )
    conn = psycopg.connect(dsn, autocommit=True)
    register_vector(conn)
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT document_id, chunk_text, tensor_1024d
            FROM psm_document_embeddings
            WHERE document_id LIKE 'wikitext2%'
            ORDER BY document_id
            """
        )
        rows = cursor.fetchall()
    chunks = [(row[0], row[1]) for row in rows]
    tensors = [np.asarray(row[2], dtype=np.float32).reshape(-1) for row in rows]
    bound = bind_word_taxonomy(
        resonance,
        chunks,
        tensors,
        tags_path=cache / "word_tags.json",
    )
    print(
        f"tagged {bound['tags']} words across {bound['categories']} articles, {len(chunks)} paragraphs"
    )


if __name__ == "__main__":
    main()
