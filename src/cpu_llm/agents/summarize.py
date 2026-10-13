"""Keep the sentences PrismCognition has already judged most important.

Deliberation decays a claim that is in modal tension and refuses a summary
when the evidence contradicts itself. Surviving claims are ordered by that
weight, then by how close their tensor sits to the deliberation target.
The target is the query blended with the evidence, which is the adapter's
own vector. No separate importance score is invented, and a sentence that
does not round-trip is not spoken.
"""

from __future__ import annotations

import re

import numpy as np

from cpu_llm.channels import _content_words
from cpu_llm.cognition.adapter import DeliberationResult
from cpu_llm.ir.schema import EIRProposition, EpistemicStatus

SUMMARY_KEEP = 3
LIST_KEEP = 8
_CAUSE = re.compile(r"\b(?:because|due to|caused|therefore)\b", re.IGNORECASE)
_NOT_TOPIC = frozenset(
    """
    summarize summarise summary briefly short important points main tldr
    explain why cause list enumerate cite citation citations sources source
    imagine imagined imagination creative creatively deep search compare comparison
    versus different difference
    """.split()
)


def topic_words(message: str) -> list[str]:
    """Content words that name a subject, with the request words removed."""
    return [word for word in _content_words(message) if word not in _NOT_TOPIC]


def rank_by_cognition(
    result: DeliberationResult,
    tensors_by_id: dict[str, np.ndarray],
) -> list[EIRProposition]:
    """Highest epistemic weight first, then closest to the deliberation target.

    A contradiction abstains. The synthetic conflict sentence is not a stored
    claim and is not returned.
    """
    if result.abstention_triggered or result.ruin_distance >= 1.0:
        return []
    target = np.asarray(result.target_vector, dtype=np.float64).reshape(-1)
    ranked: list[tuple[float, float, int, EIRProposition]] = []
    for index, proposition in enumerate(result.grounded_propositions):
        if proposition.epistemic_status is EpistemicStatus.UNRESOLVED_CONTRADICTION:
            continue
        ranked.append(
            (
                float(proposition.epistemic_weight),
                _alignment(target, tensors_by_id.get(proposition.proposition_id)),
                index,
                proposition,
            )
        )
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [item[3] for item in ranked]


def cause_first(ranked: list[EIRProposition], texts: dict[str, str]) -> list[EIRProposition]:
    """Stored sentences that state a cause, in cognition order."""
    return [
        proposition
        for proposition in ranked
        if _CAUSE.search(texts.get(proposition.proposition_id, ""))
    ]


def _alignment(target: np.ndarray, tensor: np.ndarray | None) -> float:
    if tensor is None:
        return -1.0
    right = np.asarray(tensor, dtype=np.float64).reshape(-1)
    if right.shape != target.shape:
        return -1.0
    denom = float(np.linalg.norm(target) * np.linalg.norm(right))
    if denom == 0.0:
        return -1.0
    return float(np.dot(target, right) / denom)
