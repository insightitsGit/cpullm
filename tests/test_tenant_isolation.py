"""Two live tenants, and a labelled retrieval run with no pass bar.

The isolation check needs Postgres. A token stored for one tenant must be
absent from the other tenant's reply, preface, draft, and the rest of the
result. The measurement records hit-rate@5 and spoken attribution. It does
not assert a threshold.
"""

import json
import platform
import subprocess

from cpu_llm.pipeline import Appliance
from cpu_llm.retrieval_eval import measure

TOKEN_A = "ALPHATOKENZXQ"
TOKEN_B = "BETATOKENQWZ"

LAB = (
    ("lab-p0001", "The velnax beetle lives in the red marsh.", "Where does the velnax beetle live?"),
    ("lab-p0002", "The brindle kite winters on the chalk cliff.", "Where does the brindle kite winter?"),
    ("lab-p0003", "The cinder owl hunts above the dry canal.", "Where does the cinder owl hunt?"),
    ("lab-p0004", "The marigold moth rests under the iron bridge.", "Where does the marigold moth rest?"),
)


def test_tenant_a_text_does_not_appear_in_tenant_b():
    alpha = Appliance(namespace="tenant_alpha")
    beta = Appliance(namespace="tenant_beta")
    try:
        alpha.upsert("alpha-p0001", f"The private fact is {TOKEN_A}.")
        beta.upsert("beta-p0001", f"The private fact is {TOKEN_B}.")
        left = alpha.ask(f"What is the private fact {TOKEN_A}?")
        right = beta.ask(f"What is the private fact {TOKEN_B}?")
        left_body = json.dumps(left)
        right_body = json.dumps(right)
        assert TOKEN_A in left_body
        assert TOKEN_B in right_body
        assert TOKEN_B not in left_body
        assert TOKEN_A not in right_body
        assert all(item["document_id"].startswith("alpha-") for item in left["passages"])
        assert all(item["document_id"].startswith("beta-") for item in right["passages"])
    finally:
        alpha.close()
        beta.close()


def test_labelled_retrieval_is_recorded_without_a_threshold(capsys):
    lab = Appliance(namespace="retrieval_lab")
    cases = []
    try:
        for document_id, sentence, question in LAB:
            lab.upsert(document_id, sentence)
        for document_id, sentence, question in LAB:
            hits = lab.index.search(question, top_k=5)
            retrieved = [str(hit["document_id"]) for hit in hits]
            result = lab.ask(question)
            spoken = _spoken_document(result, sentence)
            cases.append(
                {
                    "question": question,
                    "relevant_ids": [document_id],
                    "retrieved_ids": retrieved,
                    "spoken_document_id": spoken,
                }
            )
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
        record = measure(
            cases,
            commit=commit,
            machine=platform.node() or platform.platform(),
            command="python -m pytest tests/test_tenant_isolation.py::test_labelled_retrieval_is_recorded_without_a_threshold --tb=short",
        )
        print(json.dumps({"record": record, "cases": cases}, indent=2))
        assert record["cases"] == 4
        assert record["commit"] == commit
        assert "threshold" not in record
        assert 0.0 <= record["hit_rate_at_5"] <= 1.0
        assert 0.0 <= record["spoken_attribution"] <= 1.0
    finally:
        lab.close()


def _spoken_document(result: dict, sentence: str) -> str:
    """The document id whose stored sentence was spoken, or nothing."""
    spoken = str((result.get("reply") or {}).get("text") or result.get("answer") or "")
    if sentence not in spoken:
        return ""
    for item in list(result.get("passages") or []) + list(result.get("related") or []):
        if sentence in str(item.get("chunk_text") or ""):
            return str(item.get("document_id") or item.get("chunk_id") or "")
    return ""
