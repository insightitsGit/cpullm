"""Training tags a word with its article and writes one relation number."""

from pathlib import Path

import numpy as np
import pytest
from prismresonance import PrismResonance
from vectorprism.tensor_contract import PSMTensorContract

from cpu_llm.word_taxonomy import (
    bind_word_taxonomy,
    category_number,
    recall_document_ids,
    slug_fits,
    stamp_relation,
    tag_id,
)


def _tensor(seed: float) -> np.ndarray:
    vector = np.zeros(1024, dtype=np.float32)
    dense = PSMTensorContract.DENSE_CORE
    vector[dense.start : dense.end] = seed
    vector[dense.start] = 1.0
    return vector


def test_one_article_shares_one_relation_number():
    assert category_number("papa-stour") == category_number("papa-stour")
    assert category_number("papa-stour") != category_number("meridian-mississippi")
    stamped = stamp_relation(_tensor(0.2), category_number("papa-stour"))
    other = stamp_relation(_tensor(0.8), category_number("papa-stour"))
    relation = PSMTensorContract.RELATIONAL.start
    dense = PSMTensorContract.DENSE_CORE
    assert stamped[relation] == other[relation]
    assert stamped[dense.start] == 1.0


def test_slug_fit_accepts_the_longer_article_id():
    assert slug_fits(["meridian"], "meridian-mississippi") is True
    assert slug_fits(["papa-stour"], "papa-stour") is True
    assert slug_fits(["european"], "homarus-gammarus") is False


def test_sleep_tags_the_word_and_recall_returns_its_paragraph(tmp_path: Path):
    onnx = Path(".chorusgraph") / "cpu-llm" / "resonance_1024.onnx"
    if not onnx.exists():
        pytest.skip("resonance graph has not been compiled")
    resonance = PrismResonance.create(
        embedding_dim=1024,
        onnx_path=onnx,
        state_path=tmp_path / "resonance_state.db",
        coherence_threshold=-1.0,
        load_state=False,
    )
    peat = "wikitext2-papa-stour-p0007"
    lead = "wikitext2-papa-stour-p0001"
    chunks = [
        (lead, "Papa Stour is one of the Shetland Islands in Scotland."),
        (peat, "There is no peat because the volcanic rocks do not hold it."),
    ]
    bound = bind_word_taxonomy(
        resonance,
        chunks,
        [_tensor(0.2), _tensor(0.4)],
        tags_path=tmp_path / "word_tags.json",
    )
    assert bound["tensors"][0][PSMTensorContract.RELATIONAL.start] == bound["tensors"][1][PSMTensorContract.RELATIONAL.start]
    partners = [partner for partner, _count in resonance.most_related(tag_id("papa-stour", "peat"), n=5)]
    assert peat in partners
    recalled = recall_document_ids(
        resonance,
        bound["index"],
        "Why is there no peat on Papa Stour?",
    )
    assert peat in recalled
    assert "homarus-gammarus" not in " ".join(recalled)
