"""Real entry points of the libraries named in the specification header.

Importing this module loads those packages. It does not call a language-model
API. An untrained VectorPrism projection is refused: its causal matrix is a
learned parameter and a random initialization is not a measurement.
"""

from __future__ import annotations

from pathlib import Path


def library_versions() -> dict[str, str]:
    import chorusgraph
    import prismagenticpay
    import prismcognition
    import prismcortex
    import prismguard
    import prismmanifest
    import prismrag_patch
    import prismresonance
    import prismshine
    import vectorprism

    return {
        "vectorprism": vectorprism.__version__,
        "chorusgraph": chorusgraph.__version__,
        "prismguard": prismguard.__version__,
        "prismcognition": prismcognition.__version__,
        "prismrag_patch": prismrag_patch.__version__,
        "prismresonance": prismresonance.__version__,
        "prismcortex": prismcortex.__version__,
        "prismmanifest": prismmanifest.__version__,
        "prismshine": prismshine.__version__,
        "prismagenticpay": prismagenticpay.__version__,
    }


def rules_checker():
    """PrismGuard structural checker. This does not load the ONNX classifier."""
    from prismguard.runtime.factory import create_checker_rules_only

    return create_checker_rules_only()


def chorus_stack(tenant_id: str):
    from chorusgraph import ChorusStack

    return ChorusStack(tenant_id=tenant_id)


def load_projection(checkpoint: Path):
    """Load a trained VectorPrism projection. The file must be a state dict."""
    path = Path(checkpoint)
    if not path.is_file():
        raise FileNotFoundError(
            f"VectorPrism checkpoint not found at {path}. "
            "An untrained MultiTaskProjectionAdapter is not used."
        )
    import torch
    from vectorprism import VectorPrismProjectionAdapter

    model = VectorPrismProjectionAdapter()
    state = torch.load(path, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    return model
