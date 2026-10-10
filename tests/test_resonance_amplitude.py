"""The resonance amplitude is the dense channel, not the packed header."""

import numpy as np

from cpu_llm.pipeline import TENSOR_DIM, resonance_amplitude
from vectorprism.tensor_contract import PSMTensorContract


def test_timestamp_bits_do_not_enter_the_interference_score():
    dense = PSMTensorContract.DENSE_CORE
    query = np.zeros(TENSOR_DIM, dtype=np.float32)
    chunk = np.zeros(TENSOR_DIM, dtype=np.float32)
    direction = np.linspace(0.1, 1.0, dense.length, dtype=np.float64)
    direction /= np.linalg.norm(direction)
    query[dense.start : dense.end] = direction
    chunk[dense.start : dense.end] = direction
    query[3] = np.float32(1.22089e26)
    chunk[3] = np.float32(1.22087e26)
    chunk[512:640] = 3.0

    query_amplitude = resonance_amplitude(query)
    chunk_amplitude = resonance_amplitude(chunk)
    assert np.all(query_amplitude[:16] == 0.0)
    assert np.all(query_amplitude[384:] == 0.0)
    score = float(query_amplitude.astype(np.float64) @ chunk_amplitude.astype(np.float64))
    assert np.isfinite(score)
    assert score == np.float32(1.0) or abs(score - 1.0) < 1e-5
