"""Model01 sentence generator.

The prompt is the task. The stored sentences and propositions are the words.
"""

from cpu_llm.model01.corpus import load_pairs, prepare
from cpu_llm.model01.generator import MODEL_ID, MODEL_NAME, apply_model01, generate
from cpu_llm.model01.train import train

__all__ = ["MODEL_ID", "MODEL_NAME", "apply_model01", "generate", "load_pairs", "prepare", "train"]
