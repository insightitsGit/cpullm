"""Request, proof, and answer decision for the migrated relation families.

Parsers still propose candidates. This module is the owner of quantifier
scope, which source sentences may license a conclusion, and the proof that
the public evidence list must repeat. It does not search and it does not
keep a second store.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re

REQUEST_SCHEMA = "answer-request-v1"
DECISION_SCHEMA = "answer-decision-v1"

# Bare "X is Y" is a color only when Y is in this vocabulary. An explicit
# "has color" / "the color of X is Y" construction may name a value outside it.
COLOR_VOCABULARY = frozenset(
    """
    black blue brown gray grey green orange pink purple red white yellow
    amber copper crimson slate olive silver cream linen rose ink rust charcoal
    gold bronze violet teal navy maroon beige ivory tan scarlet azure cobalt
    magenta cyan turquoise indigo
    """.split()
)

_AGGREGATE = re.compile(r"^(?:some|most|many|several|few|average)\b", re.IGNORECASE)
_UNIVERSAL = re.compile(r"^(?:every|all)\b", re.IGNORECASE)
_COPULA = r"(?:is|are|was|were)"
_ROLE = re.compile(rf"\b{_COPULA}\s+(?:a|an|the)\s+(?!found\b)(?!best\b)\S", re.IGNORECASE)
_PLACE = re.compile(rf"\b{_COPULA}\s+found\b", re.IGNORECASE)
_BARE_COLOR = re.compile(
    rf"\b{_COPULA}\s+(?:" + "|".join(sorted(COLOR_VOCABULARY, key=len, reverse=True)) + r")\b[.!?]?\s*$",
    re.IGNORECASE,
)


def _name(text: str) -> str:
    from cpu_llm.prompt_intent import _name as normalize

    return normalize(text)


@dataclass(frozen=True)
class AnswerRequest:
    """What one task asked, separate from the sentences that might answer it."""

    entity: str
    relation: str
    direction: str
    quantifier_scope: str
    schema: str = REQUEST_SCHEMA
    polarity: str = "affirmative"
    object_constraint: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ProofSpan:
    document_id: str
    span: str
    role: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AnswerDecision:
    """The conclusion and the proof the renderer is allowed to show."""

    request: AnswerRequest
    outcome: str
    reason: str
    text: str
    proof: tuple[ProofSpan, ...]
    schema: str = DECISION_SCHEMA

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["proof"] = [step.as_dict() for step in self.proof]
        payload["request"] = self.request.as_dict()
        return payload


def quantifier_scope(entity: str) -> str:
    """Individual, universal, or a group aggregate. These do not inherit each other."""
    name = _name(entity)
    if _AGGREGATE.match(name):
        return "aggregate"
    if _UNIVERSAL.match(name):
        return "universal"
    return "individual"


def indefinite_subject(text: str) -> bool:
    """A some/average sentence is about a group, not one named entity."""
    return bool(_AGGREGATE.match(_name(text)))


def compile_request(requested: dict) -> AnswerRequest:
    """The channel parser's candidate, with quantifier scope made explicit."""
    entity = str(requested.get("entity") or "")
    constraint = requested.get("object")
    return AnswerRequest(
        entity=entity,
        relation=str(requested.get("relation") or ""),
        direction=str(requested.get("direction") or "subject"),
        quantifier_scope=quantifier_scope(entity),
        object_constraint=str(constraint) if constraint else None,
    )


def scope_allows(scope: str, entity: str, subject: str) -> bool:
    """Whether this assertion's subject may license the request.

    An individual does not inherit some or an average. An explicit aggregate
    question keeps only that aggregate's own sentence.
    """
    from cpu_llm.prompt_intent import _equivalent

    if scope == "aggregate":
        return indefinite_subject(subject) and _equivalent(entity, subject)
    if indefinite_subject(subject):
        return False
    return True


def discharges_type(sentence: str) -> bool:
    """A type or role copula. A place, a ranking, or a bare color does not."""
    if _PLACE.search(sentence) or _BARE_COLOR.search(sentence):
        return False
    return _ROLE.search(sentence) is not None


def blocks_type(sentence: str) -> bool:
    """A copula that must not be used when the question asks what something is."""
    return bool(_PLACE.search(sentence) or _BARE_COLOR.search(sentence))


def decide(
    request: AnswerRequest,
    *,
    outcome: str,
    reason: str,
    text: str,
    proof: list[ProofSpan],
) -> AnswerDecision:
    return AnswerDecision(
        request=request,
        outcome=outcome,
        reason=reason,
        text=text,
        proof=tuple(proof),
    )


def proof_from_facts(facts: list, *, role: str = "premise") -> list[ProofSpan]:
    spans: list[ProofSpan] = []
    seen: set[tuple[str, str]] = set()
    for fact in facts:
        key = (str(fact.document_id), str(fact.sentence))
        if key in seen:
            continue
        seen.add(key)
        spans.append(ProofSpan(document_id=key[0], span=key[1], role=role))
    return spans


def assemble_proof(identity: list, conclusions: list) -> list[ProofSpan]:
    """The identity edges that bind the asked name, then the stated relation.

    A conclusion about a canonical name does not by itself justify an answer
    to an alias. The alias premise has to be in this proof, not only in a
    side list.
    """
    spans = proof_from_facts(identity, role="identity")
    seen = {(span.document_id, span.span, span.role) for span in spans}
    for span in proof_from_facts(conclusions):
        key = (span.document_id, span.span, span.role)
        if key in seen:
            continue
        seen.add(key)
        spans.append(span)
    return spans
