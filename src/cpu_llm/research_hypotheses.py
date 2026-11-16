"""Extract candidate predictions and turn them into proposed research tests."""
import re

from cpu_llm.answerability import _sentences
from cpu_llm.channels import _content_words
from cpu_llm.nammade.encode import span_hash

_PREDICTION = re.compile(r"\b(?:predicts?|should|would|might|could|hypothes[ei]s)\b", re.I)
_NON_TOPIC = {"test", "research", "hypothesis", "hypotheses", "predict", "prediction"}


def hypothesis_options(query, rows, *, limit=3):
    """Return source-attributed predictions with a proposed check for each."""
    topic = set(_content_words(query)) - _NON_TOPIC
    if not topic:
        return []
    ranked = []
    seen = set()
    for row in rows:
        chunk = row["chunk_text"]
        for sentence in _sentences(chunk):
            overlap = topic.intersection(_content_words(sentence))
            if (not overlap or not 20 <= len(sentence) <= 700 or sentence in seen
                    or sentence not in chunk or not _PREDICTION.search(sentence)):
                continue
            seen.add(sentence)
            ranked.append((len(overlap), dict(
                document_id=row["document_id"],
                prediction=sentence,
                span_hash=span_hash(sentence),
                qualification="hypothesis",
                test=("Define a measurable outcome for this prediction and compare it with an "
                      "independent observation and a baseline under the same conditions."),
            )))
    ranked.sort(key=lambda entry: -entry[0])
    return [option for _, option in ranked[:limit]]
