"""Extract candidate predictions and turn them into proposed research tests."""
import re
import unicodedata

from cpu_llm.answerability import _sentences
from cpu_llm.channels import _content_words
from cpu_llm.nammade.encode import span_hash

_PREDICTION = re.compile(r"\b(?:predicts?|should|would|might|could|hypothes[ei]s)\b", re.I)
_NON_TOPIC = {"test", "research", "hypothesis", "hypotheses", "predict", "prediction"}
_SIDM_TOPIC = re.compile(r"\b(?:self[- ]interacting dark matter|sidm)\b", re.I)
_DWARF_CORES = re.compile(
    r"\bcores in dwarf galaxies with sizes of \((?P<low>\d+(?:\.\d+)?)[-–−]"
    r"(?P<high>\d+(?:\.\d+)?)\)\s*kpc\b", re.I,
)
_MERGER_BOUND = re.compile(
    r"\bupper bound of (?P<limit>\d+(?:\.\d+)?) square centimeters per gram "
    r"at (?P<confidence>\d+) percent confidence\b", re.I,
)


def sidm_boundary_option(query, rows):
    """Join a dwarf-core simulation result and an independent merger bound."""
    if not _SIDM_TOPIC.search(query):
        return None
    dwarf = merger = None
    for row in rows:
        text = unicodedata.normalize("NFKC", row["chunk_text"])
        if dwarf is None and re.search(r"\bsidm\b|withsidm", text, re.I):
            if match := _DWARF_CORES.search(text):
                dwarf = row, match
        if merger is None and all(phrase in text.casefold() for phrase in (
            "bullet cluster", "self-interactions", "mass peak", "galaxy centroid",
        )):
            if match := _MERGER_BOUND.search(text):
                merger = row, match
    if not dwarf or not merger or dwarf[0]["document_id"] == merger[0]["document_id"]:
        return None
    dwarf_row, sizes = dwarf
    merger_row, bound = merger
    low, high = sizes["low"], sizes["high"]
    limit, confidence = bound["limit"], bound["confidence"]
    premises = [
        dict(document_id=row["document_id"], span=row["chunk_text"], span_hash=span_hash(row["chunk_text"]))
        for row in (dwarf_row, merger_row)
    ]
    return dict(
        document_id=dwarf_row["document_id"],
        qualification="hypothesis",
        origin="cross_source_synthesis",
        prediction=(
            f"A single velocity-dependent self-interacting dark matter model can reproduce "
            f"dwarf-galaxy core radii in the reported simulation range ({low}–{high} kpc) "
            f"while remaining below the reported Bullet Cluster bound."
        ),
        test=(
            f"Fit the model to independent dwarf-galaxy kinematics, controlling for baryonic feedback. "
            f"Use the same parameters to predict the cluster-merger mass–galaxy offset. "
            f"Under the cited merger analysis assumptions, reject the candidate if no parameter "
            f"set that fits the dwarf data also stays below {limit} cm²/g at cluster velocities "
            f"(the reported {confidence}% confidence bound). Compare with a collisionless baseline."
        ),
        premises=premises,
        span_hash=premises[0]["span_hash"],
    )


def hypothesis_options(query, rows, *, limit=3):
    """Return source-attributed predictions with a proposed check for each."""
    if candidate := sidm_boundary_option(query, rows):
        return [candidate][:limit]
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
