"""Measured comparison for the resonance-tag prototype.

Run from the repository root::

    python tests/resonance_eval.py

Exit 0 when spreading precision is at least 0.88 and recall is at least 0.89
on ``tests/resonance_corpus.py``. The figures are computed from the store.
They are not copied from the design note.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

from cpu_llm.resonance_groups import ResonanceTags


def _corpus():
    path = Path(__file__).with_name("resonance_corpus.py")
    spec = importlib.util.spec_from_file_location("resonance_corpus", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CORPUS = _corpus()


def build_store(path: Path) -> ResonanceTags:
    store = ResonanceTags(path)
    store.add_chunks([(row["doc_id"], row["text"]) for row in CORPUS.SENTENCES])
    return store


def _rates(result: dict, gold: list[str]) -> tuple[float, float]:
    got = {unit["doc_id"] for unit in result["units"]}
    wanted = set(gold)
    precision = len(got & wanted) / len(got) if got else 0.0
    recall = len(got & wanted) / len(wanted) if wanted else 0.0
    return precision, recall


def measure(path: Path) -> dict[str, tuple[float, float]]:
    """Macro precision and recall for the lexical, cluster, and spreading paths."""
    store = build_store(path)
    methods = {
        "lexical": store.lexical,
        "cluster": store.recall,
        "spread": store.recall_spread,
    }
    scores: dict[str, tuple[float, float]] = {}
    details: dict[str, list[tuple[str, float, float]]] = {}
    for name, method in methods.items():
        precision_sum = 0.0
        recall_sum = 0.0
        rows = []
        for query in CORPUS.QUERIES:
            precision, recall = _rates(method(query["text"]), CORPUS.gold_ids(query))
            precision_sum += precision
            recall_sum += recall
            rows.append((query["text"], precision, recall))
        count = len(CORPUS.QUERIES)
        scores[name] = (precision_sum / count, recall_sum / count)
        details[name] = rows
    scores["details"] = details  # type: ignore[assignment]
    return scores


def spreading_scores(path: Path) -> tuple[float, float]:
    precision, recall = measure(path)["spread"]
    return precision, recall


def _format(metrics: dict) -> str:
    lines = ["method      precision  recall"]
    for name in ("lexical", "cluster", "spread"):
        precision, recall = metrics[name]
        lines.append(f"{name:<10}  {precision:9.2f}  {recall:6.2f}")
    lines.append("spread queries:")
    for text, precision, recall in metrics["details"]["spread"]:
        lines.append(f"  {precision:.2f}  {recall:.2f}  {text}")
    return "\n".join(lines)


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        metrics = measure(Path(directory) / "resonance_tags.db")
    print(_format(metrics))
    precision, recall = metrics["spread"]
    if precision >= 0.88 and recall >= 0.89:
        return 0
    print(f"spread gate failed: precision {precision:.4f}, recall {recall:.4f}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
