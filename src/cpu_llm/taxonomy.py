"""Lexical tags attached to a chunk while it is ingested.

The category is the article slug already in the document id. PrismRAG records
that word-to-article rule. PrismResonance registers the same term on the dense
core, which is VectorPrism's trained channel, [16:384]. The graph node keeps
the tags beside any stored proposition.

Terms are the content words of the chunk. A fixed window of the first eight
tokens would drop a word that sits later in the paragraph.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict
from prismresonance import FrequencyFamily
from vectorprism.tensor_contract import PSMTensorContract

from cpu_llm.catalog import article_slug
from cpu_llm.channels import _content_words
from cpu_llm.word_taxonomy import tag_id

_DENSE = PSMTensorContract.DENSE_CORE


class LexicalTaxonomyTag(BaseModel):
    model_config = ConfigDict(frozen=True)
    term: str
    category: str
    resonance_key: str
    channel_index: int = _DENSE.start


class IngestTaxonomyIndexer:
    """Build category tags for one chunk and register their wave markers."""

    def __init__(self, resonance: Any, rag: Any | None = None) -> None:
        self.resonance = resonance
        self.rag = rag

    def resolve_category(self, doc_id: str) -> str:
        resolver = getattr(self.rag, "resolve_category", None)
        if callable(resolver):
            found = resolver(doc_id)
            if found:
                return str(found)
        return article_slug(doc_id)

    def build_chunk_tags(
        self,
        doc_id: str,
        text: str,
        tensor_1024d: np.ndarray,
    ) -> list[LexicalTaxonomyTag]:
        category = self.resolve_category(doc_id)
        tags: list[LexicalTaxonomyTag] = []
        seen: set[str] = set()
        for term in _content_words(text):
            if term in seen:
                continue
            seen.add(term)
            tag = LexicalTaxonomyTag(
                term=term,
                category=category,
                resonance_key=f"{category}:{term}",
                channel_index=_DENSE.start,
            )
            tags.append(tag)
            self._register_wave_tag(tag, doc_id, tensor_1024d)
        return tags

    def _register_wave_tag(
        self,
        tag: LexicalTaxonomyTag,
        doc_id: str,
        tensor_1024d: np.ndarray,
    ) -> None:
        from cpu_llm.pipeline import resonance_amplitude

        amplitude = resonance_amplitude(tensor_1024d)
        if amplitude.shape != (PSMTensorContract.TOTAL_DIM,):
            raise ValueError("wave tag amplitude must stay on the 1024-d layout")
        dense = amplitude[_DENSE.start : _DENSE.end]
        if float(np.linalg.norm(dense)) == 0.0:
            raise ValueError("wave tag requires the dense core")
        for marker in (tag.resonance_key, tag_id(tag.category, tag.term)):
            self.resonance.ingest(
                marker,
                amplitude,
                frequency=FrequencyFamily.NEUTRAL,
                group_id=tag.category,
            )
            self.resonance.record_co_activation(marker, doc_id)
