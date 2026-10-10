"""Category labels for the chunks VectorPrism already retrieved.

The category slug is the article id already stored on the chunk, such as
``homarus-gammarus`` from ``wikitext2-homarus-gammarus-p0001``. PrismRAG's
rule table maps those article tokens onto that slug. It does not invent a
subject taxonomy. A query receives a category only when one of those tokens
appears in the prompt.
"""

from __future__ import annotations

import re
from typing import Any

from prismrag_patch import PrismRAG
from prismrag_patch.mapping.rules import RulesStrategy

_PARAGRAPH = re.compile(r"-p\d+$")


def article_slug(document_id: str) -> str:
    slug = document_id
    if slug.startswith("wikitext2-"):
        slug = slug[len("wikitext2-") :]
    return _PARAGRAPH.sub("", slug) or document_id


def mapping_for(chunks: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    categories: list[dict[str, str]] = []
    rules: list[dict[str, str]] = []
    seen_slugs: set[str] = set()
    seen_words: set[str] = set()
    for item in chunks:
        slug = article_slug(str(item["chunk_id"]))
        if slug not in seen_slugs:
            seen_slugs.add(slug)
            categories.append({"slug": slug, "label": slug.replace("-", " ")})
        for token in slug.split("-"):
            word = token.strip().lower()
            if len(word) < 3 or word in seen_words:
                continue
            seen_words.add(word)
            rules.append({"word": word, "category_slug": slug})
    if categories and not rules:
        rules.append({"word": categories[0]["slug"], "category_slug": categories[0]["slug"]})
    return {"categories": categories, "rules": rules}


def label_retrieval(query: str, related: list[dict[str, Any]]) -> dict[str, Any]:
    """Ingest the shortlist with PrismRAG and attach each chunk's category."""
    if not related:
        return {
            "related": [],
            "query_category": None,
            "rag_hits": [],
            "rag_retrieval_mode": "empty",
        }
    mapping = mapping_for(related)
    rag = PrismRAG(mapping=mapping, tenant_id="cpu-llm")
    rag.ingest(
        records=[
            {
                "word": str(item["chunk_id"]),
                "text": str(item["chunk_text"]),
                "category_hint": article_slug(str(item["chunk_id"])),
            }
            for item in related
        ]
    )
    found = rag.search(query, top_k=len(related))
    by_ref = {
        str(hit.get("chunk_ref")): hit.get("category_slug")
        for hit in found.get("hits") or []
    }
    query_category = RulesStrategy(mapping).infer_category_from_text(query)
    labeled: list[dict[str, Any]] = []
    for item in related:
        copy = dict(item)
        copy["category"] = by_ref.get(str(item["chunk_id"])) or article_slug(str(item["chunk_id"]))
        labeled.append(copy)
    hits = []
    for hit in found.get("hits") or []:
        score = hit.get("score")
        hits.append(
            {
                "chunk_ref": str(hit.get("chunk_ref")),
                "category_slug": hit.get("category_slug"),
                "score": None if score is None else float(score),
            }
        )
    return {
        "related": labeled,
        "query_category": query_category,
        "rag_hits": hits,
        "rag_retrieval_mode": found.get("retrieval_mode") or "empty",
    }
