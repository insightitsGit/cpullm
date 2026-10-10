"""The header libraries import at the versions that are published."""

from pathlib import Path

import numpy as np
import pytest

from cpu_llm.cognition.adapter import poincare_slice
from cpu_llm.stack import chorus_stack, library_versions, load_projection, rules_checker
from vectorprism.tensor_contract import VectorPrismTensorContract


def test_header_libraries_import_at_their_published_versions():
    versions = library_versions()
    assert versions == {
        "vectorprism": "0.1.3",
        "chorusgraph": "1.3.0",
        "prismguard": "0.1.10",
        "prismcognition": "2.1.0",
        "prismrag_patch": "0.2.1",
        "prismresonance": "0.3.0",
        "prismcortex": "0.4.1",
        "prismmanifest": "0.3.4",
        "prismshine": "0.2.2",
        "prismagenticpay": "1.4.1",
    }
    assert rules_checker().__class__.__name__ == "RuntimeChecker"
    assert chorus_stack("tenant_test").__class__.__name__ == "ChorusStack"


def test_hyperbolic_channel_is_the_vectorprism_slice():
    channel = VectorPrismTensorContract.HYPERBOLIC
    assert (channel.start, channel.end) == (640, 768)
    tensor = np.zeros(1024, dtype=np.float32)
    tensor[640] = 0.2
    point = poincare_slice(tensor)
    assert point is not None
    assert point.shape == (128,)
    assert point[0] == pytest.approx(0.2)


def test_projection_refuses_a_missing_checkpoint(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="checkpoint"):
        load_projection(tmp_path / "missing.pt")
