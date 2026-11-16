"""Deterministic bridge from Nammade comparisons to one relational candidate.

The node reads bounds and regime marks that are written in the compared
passages. A candidate may use only an observable and a regime variable from
those passages and the active domain ontology. The claim stays an unverified
hypothesis and is not written back to the source index.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

_NUM = r"(?P<value>\d+(?:\.\d+)?)"
_MODEL_CLASS = re.compile(
    r"\b(?:velocity|temperature|halo[- ]mass)[- ]dependent\b"
    r"|\bdependent on (?:the )?(?:relative velocity|velocity|temperature|halo mass)\b"
    r"|\bas a function of (?:the )?(?:relative velocity|velocity|temperature|halo mass)\b",
    re.IGNORECASE,
)
_BOUND_PATTERNS = (
    (0, "upper", True, rf"upper bound of\s+{_NUM}"),
    (1, "upper", True, rf"less than or equal to\s+{_NUM}"),
    (2, "upper", True, rf"at most\s+{_NUM}"),
    (3, "lower", True, rf"greater than or equal to\s+{_NUM}"),
    (4, "lower", True, rf"at least\s+{_NUM}"),
    (5, "lower", True, rf"no less than\s+{_NUM}"),
    (6, "upper", True, rf"{_NUM}\s*(?:≲|≤|<=)"),
    (7, "lower", True, rf"{_NUM}\s*(?:≳|≥|>=)"),
    (8, "upper", True, rf"(?:≲|≤|<=)\s*{_NUM}"),
    (9, "lower", True, rf"(?:≳|≥|>=)\s*{_NUM}"),
    (10, "upper", False, rf"\bless than\s+{_NUM}"),
    (11, "lower", False, rf"\bgreater than\s+{_NUM}"),
    (12, "lower", False, rf"\bmore than\s+{_NUM}"),
    (13, "lower", False, rf"\babove\s+{_NUM}"),
    (14, "upper", False, rf"\bbelow\s+{_NUM}"),
    (15, "upper", False, rf"\bunder\s+{_NUM}"),
    (16, "upper", False, rf"<\s*{_NUM}"),
    (17, "lower", False, rf">\s*{_NUM}"),
)


@dataclass(frozen=True)
class ObservableSpec:
    name: str
    surfaces: tuple[str, ...]
    units: tuple[str, ...]


@dataclass(frozen=True)
class RegimeSpec:
    name: str
    surfaces: tuple[str, ...]
    labels: tuple[tuple[str, str], ...]
    qualitative: tuple[tuple[str, str], ...]
    values: tuple[str, ...]


@dataclass(frozen=True)
class DomainSpec:
    name: str
    activation: tuple[str, ...]
    observables: tuple[ObservableSpec, ...]
    regimes: tuple[RegimeSpec, ...]


@dataclass(frozen=True)
class Constraint:
    observable: str
    kind: Literal["lower", "upper", "point"]
    value: float
    inclusive: bool
    unit: str
    source_id: str
    sentence: str
    regime: str
    labels: tuple[str, ...]
    qualitative: str | None
    regime_value: float | None


# Regime order is part of the ontology: a dwarf halo is the low-velocity side
# of a cluster merger. The node may use that order only when both labels are
# present in the compared passages.
SIDM = DomainSpec(
    name="self_interacting_dark_matter",
    activation=(r"self[- ]interacting dark matter", r"\bsidm\b"),
    observables=(
        ObservableSpec(
            name="cross_section_per_mass",
            surfaces=(
                r"σ\s*/\s*m",
                r"sigma\s*/\s*m",
                r"cross[- ]section per (?:unit )?mass",
                r"square centimeters per gram",
                r"cm\s*(?:\^2|²)\s*/\s*g",
            ),
            units=(
                r"cm\s*(?:\^2|²)\s*/\s*g",
                r"cm2/g",
                r"square centimeters per gram",
            ),
        ),
    ),
    regimes=(
        RegimeSpec(
            name="relative_velocity",
            surfaces=(r"relative velocity", r"\bv\s*="),
            labels=(
                ("dwarf", r"\bdwarf(?:[- ]galax(?:y|ies))?\b"),
                ("cluster", r"\bbullet cluster\b|\bcluster merger\b"),
            ),
            qualitative=(
                ("low", r"\blow relative velocity\b"),
                ("high", r"\bhigh relative velocity\b"),
            ),
            values=(
                r"relative velocity of\s+(?P<value>\d+(?:\.\d+)?)\s*km/s",
                r"\bv\s*=\s*(?P<value>\d+(?:\.\d+)?)\s*km/s",
            ),
        ),
    ),
)
ONTOLOGY = (SIDM,)


class RelationalBridge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor_chunk_ids: list[str] = Field(..., min_length=2, max_length=2)
    shared_observable: str
    regime_a_constraint: str
    regime_b_constraint: str
    mediating_variable: str
    proposed_relation: Literal[
        "inverse_monotonic",
        "direct_monotonic",
        "threshold_piecewise",
        "regime_conditional",
    ]
    claim_status: Literal["UNVERIFIED_HYPOTHESIS"] = "UNVERIFIED_HYPOTHESIS"


class AbductiveBridgeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["BRIDGED", "NO_GAP", "INSUFFICIENT_EVIDENCE"]
    candidate: Optional[RelationalBridge] = None
    abstention_reason: Optional[str] = None
    contradiction_source_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def status_matches_candidate(self) -> "AbductiveBridgeResult":
        if self.status == "BRIDGED" and self.candidate is None:
            raise ValueError("BRIDGED requires a candidate")
        if self.status != "BRIDGED" and self.candidate is not None:
            raise ValueError("Only BRIDGED carries a candidate")
        if self.status == "INSUFFICIENT_EVIDENCE" and not self.abstention_reason:
            raise ValueError("INSUFFICIENT_EVIDENCE requires an abstention reason")
        return self


def _passages(comparisons: list[dict]) -> list[tuple[str, str]]:
    passages = []
    for item in comparisons[:32]:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id") or "").strip()
        text = str(item.get("span_text") or "").strip()
        if source_id and text:
            passages.append((source_id, text))
    return passages


def _active_domains(query: str, passages: list[tuple[str, str]]) -> tuple[DomainSpec, ...]:
    blob = "\n".join((query, *(text for _, text in passages)))
    return tuple(domain for domain in ONTOLOGY if any(re.search(pattern, blob, re.I) for pattern in domain.activation))


def _sentences(text: str) -> list[str]:
    from cpu_llm.answerability import _sentences as split_sentences

    return split_sentences(text)


def _first_bound(sentence: str) -> tuple[str, bool, float] | None:
    found = []
    for priority, kind, inclusive, pattern in _BOUND_PATTERNS:
        match = re.search(pattern, sentence, re.IGNORECASE)
        if match:
            found.append((match.start(), priority, kind, inclusive, float(match.group("value"))))
    if not found:
        return None
    _, _, kind, inclusive, value = min(found)
    return kind, inclusive, value


def _unit(sentence: str, observable: ObservableSpec) -> str | None:
    for pattern in observable.units:
        if re.search(pattern, sentence, re.IGNORECASE):
            return "cm^2/g" if observable.name == "cross_section_per_mass" else pattern
    return None


def _regime_mark(text: str, regime: RegimeSpec) -> tuple[tuple[str, ...], str | None, float | None]:
    labels = tuple(name for name, pattern in regime.labels if re.search(pattern, text, re.IGNORECASE))
    qualitative = [name for name, pattern in regime.qualitative if re.search(pattern, text, re.IGNORECASE)]
    value = None
    for pattern in regime.values:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = float(match.group("value"))
            break
    return labels, (qualitative[0] if len(qualitative) == 1 else None), value


def _regime_present(text: str, regime: RegimeSpec) -> bool:
    labels, qualitative, value = _regime_mark(text, regime)
    if labels or qualitative is not None or value is not None:
        return True
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in regime.surfaces)


def names_mediating_model(query: str) -> bool:
    """True when the prompt already names the model class that would be bridged."""
    return _MODEL_CLASS.search(query or "") is not None


def _links_regimes(text: str, domain: DomainSpec) -> bool:
    for observable in domain.observables:
        if not any(re.search(pattern, text, re.IGNORECASE) for pattern in observable.surfaces):
            continue
        for regime in domain.regimes:
            labels, _qualitative, _value = _regime_mark(text, regime)
            qualitative_hits = [name for name, pattern in regime.qualitative if re.search(pattern, text, re.IGNORECASE)]
            if len(labels) >= 2 or len(qualitative_hits) >= 2:
                return True
    return False


def extract_constraints(query: str, comparisons: list[dict]) -> list[Constraint]:
    """Bounds whose observable, unit, and regime marks are written in each passage."""
    passages = _passages(comparisons)
    constraints: list[Constraint] = []
    for domain in _active_domains(query, passages):
        for source_id, text in passages:
            for regime in domain.regimes:
                labels, qualitative, regime_value = _regime_mark(text, regime)
                for observable in domain.observables:
                    for sentence in _sentences(text):
                        if not any(re.search(pattern, sentence, re.IGNORECASE) for pattern in observable.surfaces):
                            continue
                        bound = _first_bound(sentence)
                        unit = _unit(sentence, observable)
                        if bound is None or unit is None:
                            continue
                        kind, inclusive, value = bound
                        constraints.append(Constraint(
                            observable=observable.name,
                            kind=kind,
                            value=value,
                            inclusive=inclusive,
                            unit=unit,
                            source_id=source_id,
                            sentence=sentence,
                            regime=regime.name,
                            labels=labels,
                            qualitative=qualitative,
                            regime_value=regime_value,
                        ))
                        break
    return constraints


def _interval(constraint: Constraint) -> tuple[float, bool, float, bool]:
    if constraint.kind == "lower":
        return constraint.value, not constraint.inclusive, math.inf, False
    if constraint.kind == "upper":
        return -math.inf, False, constraint.value, not constraint.inclusive
    return constraint.value, False, constraint.value, False


def _includes(bound: tuple[float, bool, float, bool], point: float) -> bool:
    low, low_open, high, high_open = bound
    above_low = point > low or (point == low and not low_open)
    below_high = point < high or (point == high and not high_open)
    return above_low and below_high


def intervals_disjoint(left: Constraint, right: Constraint) -> bool:
    """True when a single constant value cannot satisfy both bounds."""
    if left.unit != right.unit:
        return False
    a = _interval(left)
    b = _interval(right)
    low = max(a[0], b[0])
    high = min(a[2], b[2])
    if low < high:
        return False
    if low > high:
        return True
    return not (_includes(a, low) and _includes(b, low))


def _same_number(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return False
    return abs(left - right) <= 1e-6 * max(1.0, abs(left), abs(right))


def _rank(constraint: Constraint, regime: RegimeSpec) -> tuple[str, float] | None:
    if constraint.regime != regime.name:
        return None
    if constraint.regime_value is not None:
        return ("number", constraint.regime_value)
    if constraint.qualitative is not None:
        order = [name for name, _pattern in regime.qualitative]
        return ("qualitative", float(order.index(constraint.qualitative)))
    if len(constraint.labels) == 1:
        order = [name for name, _pattern in regime.labels]
        return ("label", float(order.index(constraint.labels[0])))
    return None


def _differentiates(left: Constraint, right: Constraint, regime: RegimeSpec) -> bool:
    if left.regime != regime.name or right.regime != regime.name:
        return False
    if _same_number(left.regime_value, right.regime_value):
        return False
    if left.regime_value is not None and right.regime_value is not None:
        return True
    left_rank = _rank(left, regime)
    right_rank = _rank(right, regime)
    if left_rank is None or right_rank is None or left_rank[0] != right_rank[0]:
        return False
    return left_rank[1] != right_rank[1]


def _allowed_symbols(domain: DomainSpec, left: str, right: str) -> set[str]:
    allowed = set()
    for observable in domain.observables:
        if any(re.search(pattern, text, re.IGNORECASE) for text in (left, right) for pattern in observable.surfaces):
            allowed.add(observable.name)
    for regime in domain.regimes:
        if _regime_present(left, regime) or _regime_present(right, regime):
            allowed.add(regime.name)
    return allowed


def _relation(low: Constraint, high: Constraint, text: str) -> str:
    if re.search(r"\bthreshold\b", text, re.IGNORECASE):
        return "threshold_piecewise"
    if low.kind == "lower" and high.kind == "upper":
        return "inverse_monotonic"
    if low.kind == "upper" and high.kind == "lower":
        return "direct_monotonic"
    if low.kind == "point" and high.kind == "point" and low.value != high.value:
        return "inverse_monotonic" if low.value > high.value else "direct_monotonic"
    return "regime_conditional"


def _contradicts(relation: str, low: Constraint, high: Constraint, other: Constraint, regime: RegimeSpec) -> bool:
    rank = _rank(other, regime)
    low_rank = _rank(low, regime)
    high_rank = _rank(high, regime)
    if rank is None or low_rank is None or high_rank is None or rank[0] != high_rank[0]:
        return False
    if relation == "inverse_monotonic" and rank[1] >= high_rank[1] and other.kind == "lower" and high.kind == "upper" and other.value >= high.value:
        return True
    if relation == "inverse_monotonic" and rank[1] <= low_rank[1] and other.kind == "upper" and low.kind == "lower" and other.value <= low.value:
        return True
    if relation == "direct_monotonic" and rank[1] >= high_rank[1] and other.kind == "upper" and high.kind == "lower" and other.value <= high.value:
        return True
    return False


def _insufficient(reason: str) -> AbductiveBridgeResult:
    return AbductiveBridgeResult(status="INSUFFICIENT_EVIDENCE", candidate=None, abstention_reason=reason)


def _no_gap(reason: str) -> AbductiveBridgeResult:
    return AbductiveBridgeResult(status="NO_GAP", candidate=None, abstention_reason=reason)


class AbductiveBridgeNode:
    """Compile one relational candidate from ranked Nammade comparisons, or abstain."""

    def execute(self, query: str, comparisons: list[dict]) -> AbductiveBridgeResult:
        comparisons = comparisons if isinstance(comparisons, list) else []
        passages = _passages(comparisons)
        if names_mediating_model(query or ""):
            return _no_gap("The prompt already names the mediating model.")
        domains = _active_domains(query or "", passages)
        if any(_links_regimes(text, domain) for _source, text in passages for domain in domains):
            return _no_gap("A compared passage already links both regimes.")
        constraints = extract_constraints(query or "", comparisons)
        saw_tension = False
        for domain in domains:
            regimes = {regime.name: regime for regime in domain.regimes}
            for index, left in enumerate(constraints):
                for right in constraints[index + 1:]:
                    if left.source_id == right.source_id or left.observable != right.observable:
                        continue
                    if not intervals_disjoint(left, right):
                        continue
                    regime = regimes.get(left.regime)
                    if regime is None or not _differentiates(left, right, regime):
                        saw_tension = True
                        continue
                    left_rank = _rank(left, regime)
                    right_rank = _rank(right, regime)
                    if left_rank is None or right_rank is None:
                        saw_tension = True
                        continue
                    low, high = (left, right) if left_rank <= right_rank else (right, left)
                    texts = dict(passages)
                    allowed = _allowed_symbols(domain, texts[low.source_id], texts[high.source_id])
                    if low.observable not in allowed or regime.name not in allowed:
                        saw_tension = True
                        continue
                    relation = _relation(low, high, "\n".join(texts.values()))
                    conflicts = [
                        item.source_id for item in constraints
                        if item.source_id not in {low.source_id, high.source_id}
                        and item.observable == low.observable
                        and _contradicts(relation, low, high, item, regime)
                    ]
                    return AbductiveBridgeResult(
                        status="BRIDGED",
                        candidate=RelationalBridge(
                            anchor_chunk_ids=[low.source_id, high.source_id],
                            shared_observable=low.observable,
                            regime_a_constraint=low.sentence,
                            regime_b_constraint=high.sentence,
                            mediating_variable=regime.name,
                            proposed_relation=relation,
                        ),
                        contradiction_source_ids=list(dict.fromkeys(conflicts)),
                    )
        if saw_tension:
            return _insufficient(
                "The same observable has incompatible bounds, and no regime variable in the "
                "chunk schemas or the active ontology takes different values."
            )
        return _no_gap("The diagnostic comparisons do not show incompatible bounds.")
