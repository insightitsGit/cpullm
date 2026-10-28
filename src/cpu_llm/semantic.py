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

# These are declared equivalents for a bounded relation, not corpus synonyms.
POSSESSION_VERBS = r'(?:have|contain|include|possess)'
POSSESSION_SOURCE_VERBS = r'(?:has|have|contains?|includes?|possess(?:es)?)'
ATTRIBUTE_VALUES = {
    'shape': frozenset('round square circular triangular rectangular oval spherical cylindrical flat'.split()),
    'material': frozenset('wood metal glass plastic steel iron brass copper oak pine clay slate maple birch cedar ash'.split()),
}

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
    return _ROLE.search(sentence) is not None or named_identity(sentence)


def named_identity(sentence: str) -> bool:
    """A bounded proper-name equality, distinct from an action or adjective."""
    if re.search(r'\b(?:is|are|was|were)\s+(?:also\s+)?(?:called|known as|named)\s+\S', sentence, re.I):
        return True
    found = re.search(r'\b(?:is|are|was|were)\s+([A-Z][A-Za-z\'-]+(?:\s+[A-Za-z][A-Za-z\'-]+){1,3})[.!?]?$', sentence)
    if not found:
        return False
    words = found[1].split()
    excluded = {'in', 'on', 'at', 'from', 'with', 'for', 'and', 'or', 'not', 'very', 'ready', 'known', 'found'}
    return not any(word.casefold() in excluded or word.casefold() in COLOR_VOCABULARY for word in words)


def request_contract(message: str, intent=None) -> AnswerRequest | None:
    """One adapter boundary for channel and legacy factual request parsers."""
    from cpu_llm.prompt_intent import route_prompt
    requested = ((intent if intent is not None else route_prompt(message)).get('requested') or {})
    if requested:
        return compile_request(requested)
    from cpu_llm.answerability import parse_query
    parsed = parse_query(message)
    if not parsed:
        return None
    relation = {'definition': 'is_a', 'activity': 'activity', 'weight': 'weight'}.get(parsed['kind'])
    if parsed['kind'] == 'attribute':
        relation = 'attribute:' + parsed['attribute'].casefold()
    elif parsed['kind'] == 'relation':
        relation = parsed.get('relation', 'action') + ':' + parsed['verb']
    elif parsed['kind'] == 'sources':
        relation = 'sources'
    return compile_request(dict(entity=parsed.get('subject') or parsed.get('entity') or '',
                                relation=relation or parsed['kind'], direction='subject'))


def effects_equivalent(left: str, right: str) -> bool:
    """Allow one declared verb-form change; keep subject and other roles exact."""
    from cpu_llm.realizer.inflect import surface_tokens
    def tokens(text):
        return [word for word in _name(text).split() if word not in {'is', 'are', 'was', 'were', 'be'}]
    a, b = tokens(left), tokens(right)
    if len(a) != len(b):
        return False
    differences = [i for i, pair in enumerate(zip(a, b)) if pair[0] != pair[1]]
    if not differences:
        return True
    if len(differences) != 1 or differences[0] == 0:
        return False
    i = differences[0]
    for base, value in ((a[i], b[i]), (b[i], a[i])):
        forms = surface_tokens(base)
        if len(base) >= 3 and base[-1] not in 'aeiouwxy' and base[-2] in 'aeiou':
            forms.add(base + base[-1] + 'ed')
        if value in forms:
            return True
    return False


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
