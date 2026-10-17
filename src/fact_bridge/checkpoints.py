"""Load a local seq2seq checkpoint. Torch stays unimported until this is called."""

from __future__ import annotations

import json
from pathlib import Path


def load_seq2seq(model_dir: str):
    """Tokenizer and model for a checkpoint saved by Transformers 5.

    Two compatibility repairs, both checked against the files:

    * Those checkpoints store T5's extra ids as a list. Transformers 4 expects a
      mapping. The ids already live in the sentencepiece model, so an empty
      mapping loads the same vocabulary.
    * The saved output layer is not tied to the input embeddings. Transformers 4
      ties them on load and the trained head is discarded. When the two tensors
      differ, the saved head is put back.
    """
    import pyarrow  # noqa: F401  # must load before torch; otherwise pyarrow faults on this machine
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    path = Path(model_dir)
    config_path = path / "tokenizer_config.json"
    kwargs = {}
    if config_path.is_file():
        extra = json.loads(config_path.read_text(encoding="utf-8")).get("extra_special_tokens")
        if isinstance(extra, list):
            kwargs["extra_special_tokens"] = {}
    tokenizer = AutoTokenizer.from_pretrained(model_dir, **kwargs)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_dir)
    _restore_untied_head(model, path, torch)
    return tokenizer, model


def _restore_untied_head(model, path: Path, torch) -> None:
    weight_file = path / "model.safetensors"
    if not weight_file.is_file() or not hasattr(model, "lm_head"):
        return
    from safetensors import safe_open

    with safe_open(weight_file, framework="pt") as handle:
        if "lm_head.weight" not in handle.keys() or "shared.weight" not in handle.keys():
            return
        head = handle.get_tensor("lm_head.weight")
        shared = handle.get_tensor("shared.weight")
    if torch.equal(head, shared):
        return
    model.config.tie_word_embeddings = False
    model.lm_head.weight = torch.nn.Parameter(head.clone())
