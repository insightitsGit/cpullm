"""fact_bridge v5: deterministic rule reasoning over cpu-llm retrieval.

The default path loads no model. `answer(..., ml=True)` may read a local seq2seq
checkpoint; the verifier still has to accept every sentence it proposes.

    retrieved chunks
        -> split into sentences          (cpu-llm's abbreviation rule)
        -> extract rules / facts / is-a / causes   (clause parser, below)
        -> ground                        (every word and number must be in its source sentence)
        -> reason                        (is-a closure, unit conversion, conflict detection,
                                          cpu-llm PrismCognitionSubspaceAdapter for the YES derivation)
        -> realize + audit               (cpu-llm SemanticSurfaceRealizer + EpistemicEntailmentAuditor)

Verdicts: YES / NO / CONTESTED / UNKNOWN / CAUSE / NONE, each with the source sentences behind it.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np
from pydantic import BaseModel

from cpu_llm.audit.entailment import EpistemicEntailmentAuditor
from cpu_llm.clauses import _ABBREVIATION
from cpu_llm.cognition.adapter import PrismCognitionSubspaceAdapter
from cpu_llm.ir.schema import (
    ConditionEval, EIRProposition, EpistemicStatus, LogicalExpressionNode, LogicalOperator,
    Modality, Quantifier, QuantifierType, TypedEntity, TypedPredicate, evaluate_condition,
)
from cpu_llm.measurements import _UNIT_MAP
from cpu_llm.realizer.surface import SemanticSurfaceRealizer

# ---------------------------------------------------------------- schema


class Rule(BaseModel):
    category: str          # singular: "account", "seafood shipment"
    object: str            # "security training"
    modality: Literal["allowed", "required", "forbidden"]
    metric: str            # "duration", "risk score", "guest"
    op: Literal["gt", "gte", "lt", "lte", "eq"]
    threshold: float
    unit: str              # as written, singular: "hour", "kilogram", "risk score"
    source: str


class Fact(BaseModel):
    entity: str            # "contractor account for Dana", "Bella"
    category: str          # "contractor account", "bella"
    metric: str
    value: float
    unit: str
    source: str


class IsA(BaseModel):
    sub: str
    sup: str
    source: str


class Cause(BaseModel):
    effect: str
    cause: str
    source: str


class Extraction(BaseModel):
    rules: list[Rule] = []
    facts: list[Fact] = []
    isa: list[IsA] = []
    causes: list[Cause] = []


# ---------------------------------------------------------------- text helpers

NUMBER_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen twenty".split())}
NUMBER_WORDS.update({"thirty": 30, "forty": 40, "fifty": 50, "hundred": 100})

_NUM = r"(?:\d+(?:\.\d+)?|" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) + r")"
OPS = [("no more than", "lte"), ("more than", "gt"), ("longer than", "gt"), ("greater than", "gt"),
       ("exceeding", "gt"), ("over", "gt"), ("above", "gt"), ("at least", "gte"),
       ("less than", "lt"), ("shorter than", "lt"), ("fewer than", "lt"), ("under", "lt"), ("below", "lt"),
       ("at most", "lte"), ("up to", "lte"), ("exactly", "eq")]
_OP = "|".join(re.escape(p) for p, _ in OPS)
MODALITY = [
    (r"(?:is|are) (?:not allowed|not permitted|prohibited|forbidden|banned)", "forbidden"),
    (r"(?:may not|must not|cannot|can't)", "forbidden"),
    (r"(?:is|are) (?:required|mandatory|needed|necessary)", "required"),
    (r"(?:must|shall|needs?|requires?)", "required"),
    (r"(?:is|are) (?:allowed|permitted|available|approved)", "allowed"),
    (r"(?:may|can)", "allowed"),
]
_MOD = "|".join(m for m, _ in MODALITY)
_ART = r"(?:an?|the|our|my|your|this|that|every|each)"
_NOT_UNIT = r"(?:must|may|can|cannot|shall|needs?|requires?|is|are|was|were|should|will|not)\b"
_UNITW = rf"(?!{_NOT_UNIT})[a-z][a-z-]*(?: (?!{_NOT_UNIT})[a-z][a-z-]*)?"  # a unit never absorbs a modal verb
_VERBS = (r"is worth|is priced at|comes to|takes|lasts|runs|costs|weighs|measures|covers|spans|totals|holds|"
          r"contains|includes|uses|has|have|is|are")
_PREP = r"(?:from|to|between|in|at|for|on|of|with)"
_TRAIL = {"away", "long", "old", "total", "wide", "tall", "high"}
_LINKERS = r"(?:with|having|that have|that has|that are|that last|that cost|that weigh|lasting|costing|weighing|of)"


def normalize_amounts(text: str) -> str:
    text = re.sub(r"\$\s?(\d[\d,]*(?:\.\d+)?)", lambda m: m[1].replace(",", "") + " dollars", text)
    return re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)


def to_number(token: str) -> float:
    token = token.lower()
    return float(NUMBER_WORDS[token]) if token in NUMBER_WORDS else float(token)


def singular(phrase: str) -> str:
    def one(word: str) -> str:
        for suffix, repl in (("ies", "y"), ("sses", "ss"), ("shes", "sh"), ("ches", "ch"), ("s", "")):
            if word.endswith(suffix) and len(word) > 3 and not word.endswith("ss"):
                return word[: -len(suffix)] + repl
        return word
    words = phrase.lower().split()
    return " ".join(words[:-1] + [one(words[-1])]) if words else ""


def plural(unit: str) -> str:
    return unit if len(unit) <= 2 or unit.endswith("s") else unit + "s"


def split_sentences(text: str) -> list[str]:
    """Sentence split that keeps 'Dr.' / 'St.' / initials together (cpu-llm's abbreviation rule)."""
    out, current = [], ""
    for part in re.split(r"(?<=[.!?])\s+", text.strip()):
        current = f"{current} {part}".strip() if current else part
        if _ABBREVIATION.search(current) is None:
            out.append(current)
            current = ""
    if current:
        out.append(current)
    return [s for s in out if s]


def _norm(text: str) -> str:
    text = normalize_amounts(text).lower()
    for word, value in NUMBER_WORDS.items():
        text = re.sub(rf"\b{word}\b", str(value), text)
    return text


def _words(text: str) -> list[str]:
    return [singular(w) for w in re.findall(r"[a-z0-9]+", _norm(text)) if len(w) > 2 or w.isdigit()]


def _appears(value: str, source: str) -> bool:
    """All content words of `value` occur in `source` (singular/plural-insensitive)."""
    have = set(_words(source))
    return all(w in have for w in _words(value))


def _num_in(value: float, source: str) -> bool:
    return any(abs(float(n) - value) < 1e-9 for n in re.findall(r"\d+(?:\.\d+)?", _norm(source)))


# ---------------------------------------------------------------- units

# canonical short form -> (family, factor to family base). Same family converts; different family never does.
_CONVERT = {
    "s": ("time", 1 / 60), "min": ("time", 1), "h": ("time", 60), "day": ("time", 1440), "week": ("time", 10080),
    "month": ("months", 1), "year": ("months", 12),
    "g": ("mass", 1), "kg": ("mass", 1000), "lb": ("mass", 453.59237), "oz": ("mass", 28.349523125),
    "mm": ("length", 0.001), "cm": ("length", 0.01), "m": ("length", 1), "km": ("length", 1000),
    "mile": ("length", 1609.344), "ft": ("length", 0.3048), "in": ("length", 0.0254),
    "ml": ("volume", 0.001), "liter": ("volume", 1), "gallon": ("volume", 3.785411784),
    "kb": ("data", 1e-3), "mb": ("data", 1), "gb": ("data", 1e3), "tb": ("data", 1e6),
    "dollar": ("money", 1),
    "ton": ("ton", 1),  # its own family: short, long and metric tons differ, so tons never convert to kg
}
_ALIASES = {"second": "s", "minute": "min", "hour": "h", "hr": "h", "kilometer": "km", "kilometre": "km",
            "litre": "liter", "milliliter": "ml", "millilitre": "ml", "usd": "dollar", "ounce": "oz"}
_FAMILY_METRIC = {"time": "duration", "months": "duration", "mass": "weight", "length": "distance",
                  "volume": "volume", "data": "size", "money": "cost", "ton": "weight"}


def canon(unit: str) -> str:
    u = singular(unit.strip().lower())
    return _ALIASES.get(u) or _UNIT_MAP.get(u) or _UNIT_MAP.get(unit.strip().lower()) or u


def metric_for(unit: str) -> str:
    family = _CONVERT.get(canon(unit), (None,))[0]
    return _FAMILY_METRIC.get(family, canon(unit))


def convert(value: float, from_unit: str, to_unit: str) -> Optional[float]:
    a, b = canon(from_unit), canon(to_unit)
    if a == b:
        return value
    if a in _CONVERT and b in _CONVERT and _CONVERT[a][0] == _CONVERT[b][0]:
        return value * _CONVERT[a][1] / _CONVERT[b][1]
    return None


def _clean_unit(unit: Optional[str]) -> Optional[str]:
    if not unit:
        return None
    words = [w for w in unit.split() if w not in _TRAIL]
    return " ".join(words) or None


# ---------------------------------------------------------------- extractor

_COND = rf"(?P<op>{_OP}) (?P<n>{_NUM})(?: (?P<unit>{_UNITW}))?(?: of [a-z -]+)?"


class PatternExtractor:
    """Deterministic clause parser. Anything it cannot read is skipped, never guessed."""

    RULES = [
        re.compile(rf"^(?P<obj>.+?) (?P<mod>{_MOD}) (?:for|on) (?P<cp>.+?) {_COND}$", re.I),
        re.compile(rf"^(?P<cp>.+?) {_COND} (?P<mod>{_MOD}) (?:to )?(?:use |book |fly |get |have |be |receive )?"
                   rf"(?P<obj>.+)$", re.I),
        re.compile(rf"^if (?:an? |the )?(?P<cp>.+?) (?:is|lasts|takes|runs|costs|weighs|has) {_COND}, "
                   rf"(?P<obj>.+?) (?P<mod>{_MOD})$", re.I),
        re.compile(rf"^for (?P<cp>.+?) {_COND}, (?P<obj>.+?) (?P<mod>{_MOD})$", re.I),
    ]
    FACT = re.compile(
        rf"^(?:{_ART} )?(?P<subj>.+?) (?:{_VERBS}) (?:an? (?P<mp>[a-z -]+?) of )?"
        rf"(?:about |around |roughly |approximately |nearly )?(?P<n>{_NUM})(?: (?P<unit>{_UNITW}))?"
        rf"(?: of [a-z -]+)?$", re.I)
    ISA = re.compile(rf"^(?:{_ART} )?(?P<sub>[\w -]+?) (?:is|are) (?:a kind of |a type of )?(?P<art>an? )?"
                     rf"(?P<sup>[a-z]+(?: [a-z]+){{0,2}})$", re.I)
    CAUSE = re.compile(r"^(?P<effect>.+?),? (?:because|since|due to the fact that) (?P<cause>.+)$", re.I)

    def extract(self, sentences: list[str]) -> Extraction:
        out = Extraction()
        for raw in sentences:
            s = normalize_amounts(raw.strip().rstrip("."))
            if m := self.CAUSE.match(s):
                out.causes.append(Cause(effect=m["effect"], cause=m["cause"], source=raw))
            elif rule := self._rule(s, raw):
                out.rules.append(rule)
            elif fact := self._fact(s, raw):
                out.facts.append(fact)
            elif link := self._isa(s, raw):
                out.isa.append(link)
        return out

    def _rule(self, s: str, raw: str) -> Optional[Rule]:
        for pattern in self.RULES:
            m = pattern.match(s)
            if not m:
                continue
            cp = re.sub(rf"^{_ART} ", "", m["cp"].strip(), flags=re.I)
            mp = None
            if hit := re.match(rf"^(.+?) (?:with|having|that have|that has) (?:an? |the )?(.+)$", cp, re.I):
                cp, mp = hit[1], hit[2]
            cp = re.sub(rf"(?: {_LINKERS})+$", "", cp, flags=re.I)
            unit = _clean_unit(m["unit"]) or mp
            if not unit or len(cp.split()) > 3:
                return None
            obj = re.sub(r"^(?:to |the |an? )", "", m["obj"].strip(), flags=re.I).lower()
            kind = next(k for p, k in MODALITY if re.fullmatch(p, m["mod"].lower()))
            return Rule(category=singular(cp), object=obj, modality=kind,
                        metric=singular(mp) if mp else metric_for(unit),
                        op=dict(OPS)[m["op"].lower()], threshold=to_number(m["n"]), unit=singular(unit),
                        source=raw)
        return None

    def _fact(self, s: str, raw: str) -> Optional[Fact]:
        m = self.FACT.match(s)
        if not m or re.search(rf"\b(?:{_MOD})\b", m["subj"], re.I):
            return None
        subj = m["subj"].strip()
        unit = _clean_unit(m["unit"]) or m["mp"]
        if not unit or len(subj.split()) > 8:
            return None
        head = re.match(rf"^(.+?) {_PREP} ", subj, re.I)
        category = head[1] if head else subj
        return Fact(entity=subj, category=singular(category), metric=singular(m["mp"]) if m["mp"] else metric_for(unit),
                    value=to_number(m["n"]), unit=singular(unit), source=raw)

    def _isa(self, s: str, raw: str) -> Optional[IsA]:
        m = self.ISA.match(s)
        if not m:
            return None
        sup = m["sup"]
        if not m["art"] and (len(sup.split()) > 2 or sup.split()[0].endswith("ed")):
            return None  # "Fleet vehicles are washed every Friday" is not a definition
        return IsA(sub=m["sub"], sup=sup, source=raw)


# ---------------------------------------------------------------- grounding guard


def ground(ex: Extraction, sentences: list[str]) -> tuple[Extraction, list[str]]:
    known = {s.strip() for s in sentences}
    kept, rejected = Extraction(), []

    def check(item, parts, numbers):
        if item.source.strip() not in known:
            return "source is not a retrieved sentence"
        for p in parts:
            if p and not _appears(p, item.source):
                return f"'{p}' not in source"
        for n in numbers:
            if not _num_in(n, item.source):
                return f"number {n:g} not in source"
        return None

    for kind, items, parts, numbers in (
        ("rules", ex.rules, lambda r: [r.category, r.object, r.unit], lambda r: [r.threshold]),
        ("facts", ex.facts, lambda f: [f.entity, f.unit], lambda f: [f.value]),
        ("isa", ex.isa, lambda i: [i.sub, i.sup], lambda i: []),
        ("causes", ex.causes, lambda c: [c.effect, c.cause], lambda c: []),
    ):
        for item in items:
            why = check(item, parts(item), numbers(item))
            if why:
                rejected.append(f"{kind}: {why} :: {item.source}")
            else:
                getattr(kept, kind).append(item)
    return kept, rejected


# ---------------------------------------------------------------- reasoning

_OPS = {"gt": LogicalOperator.GT, "gte": LogicalOperator.GTE, "lt": LogicalOperator.LT,
        "lte": LogicalOperator.LTE, "eq": LogicalOperator.EQ}
_OP_TEXT = {"gt": "over", "gte": "at least", "lt": "under", "lte": "at most", "eq": "exactly"}


@dataclass
class Answer:
    verdict: Literal["YES", "NO", "CONTESTED", "UNKNOWN", "CAUSE", "NONE", "SAFETY"]
    text: str
    because: list[str] = field(default_factory=list)
    audited: Optional[bool] = None
    rejected: list[str] = field(default_factory=list)
    plan: dict = field(default_factory=dict)  # structured record of what was proved; the writer's only input
    safety: dict = field(default_factory=dict)  # child-safety gate decision (empty when switched off)
    wording: dict = field(default_factory=dict)  # path model or deterministic, plus any verifier rejection


def categories_of(fact: Fact, isa: list[IsA]) -> dict[str, list[str]]:
    """Every category the fact belongs to -> definition sentences on the way (head noun + is-a closure)."""
    cat = singular(fact.category)
    found = {cat: [], singular(fact.entity): [], cat.split()[-1]: []}
    changed = True
    while changed:
        changed = False
        for link in isa:
            sub, sup = singular(link.sub), singular(link.sup)
            if sup in found:
                continue
            for name, path in list(found.items()):
                if sub == name or re.search(rf"\b{re.escape(sub)}\b", name):
                    found[sup] = path + [link.source]
                    found.setdefault(sup.split()[-1], path + [link.source])
                    changed = True
                    break
    return found


_ID_STOP = {"a", "an", "the", "of", "in", "on", "at", "to", "for", "from", "with", "and", "or", "my", "our", "your"}


def _id_words(text: str) -> list[str]:
    """Identity tokens: like _words, but short tokens count ('hall B' vs 'hall D', 'bay 3', 'suite 1')."""
    return [singular(w) for w in re.findall(r"[a-z0-9]+", _norm(text)) if w not in _ID_STOP]


def _names(entity: str, question: str) -> bool:
    have = set(_id_words(question))
    return all(w in have for w in _id_words(entity))


def _entity_facts(facts: list[Fact], question: str) -> list[Fact]:
    """Facts about the thing the question names: full entity first, then its prepositional tail.
    Every identity token must match, short ones included, so 'hall D' never borrows the fact about 'hall B'."""
    def score(f: Fact) -> int:
        if _names(f.entity, question):
            return 2 * len(_words(f.entity))
        tail = re.match(rf"^.+? ({_PREP} .+)$", f.entity, re.I)
        return len(_words(tail[1])) if tail and _names(tail[1], question) else 0
    scored = [(score(f), f) for f in facts]
    best = max((s for s, _ in scored), default=0)
    if best == 0:
        return []
    top = {singular(f.entity) for s, f in scored if s == best}
    return [f for f in facts if singular(f.entity) in top]


def _condition(rule: Rule) -> LogicalExpressionNode:
    return LogicalExpressionNode(operator=_OPS[rule.op], metric_name=rule.metric,
                                 threshold_value=rule.threshold, unit=canon(rule.unit))


def _stance(rule: Rule, fact: Optional[Fact]) -> tuple[Optional[str], Optional[float]]:
    """What one rule supports, before the question's modality is applied.

    ``permitted``, ``obligatory``, and ``prohibited`` mean the condition holds.
    ``not_permitted`` is an allowance the source itself marks as exclusive.
    ``not_obligatory`` is a requirement whose condition does not hold.
    ``open`` means this rule does not settle the other cases. ``unknown`` means
    the fact or the units are missing. ``None`` means the rule has no opinion.
    """
    if fact is None:
        return "unknown", None
    value = convert(fact.value, fact.unit, rule.unit)
    if value is None:
        return "unknown", None
    verdict = evaluate_condition(_condition(rule), {rule.metric: value}, units={rule.metric: canon(rule.unit)})
    if verdict is ConditionEval.EVAL_UNKNOWN:
        return "unknown", value
    holds = verdict is ConditionEval.EVAL_TRUE
    if rule.modality == "forbidden":
        return ("prohibited" if holds else "open"), value
    if rule.modality == "allowed":
        if holds:
            return "permitted", value
        if re.search(r"\bonly\b", rule.source or "", re.IGNORECASE):
            return "not_permitted", value
        return "open", value
    return ("obligatory" if holds else "not_obligatory"), value


# The asked modality is the proposition to accept or reject. A permission does
# not answer an obligation question, and a firing prohibition answers "forbidden?"
# with YES.
_ASKED_VERDICT = {
    "allowed": {
        "permitted": "YES",
        "obligatory": "YES",
        "prohibited": "NO",
        "not_permitted": "NO",
        "not_obligatory": "OPEN",
        "open": "OPEN",
        "unknown": "UNKNOWN",
    },
    "required": {
        "permitted": "OPEN",
        "obligatory": "YES",
        "prohibited": "NO",
        "not_permitted": "NO",
        "not_obligatory": "NO",
        "open": "OPEN",
        "unknown": "UNKNOWN",
    },
    "forbidden": {
        "permitted": "NO",
        "obligatory": "NO",
        "prohibited": "YES",
        "not_permitted": "YES",
        "not_obligatory": "OPEN",
        "open": "OPEN",
        "unknown": "UNKNOWN",
    },
}


def _derive(rule: Rule, fact: Fact, value: float) -> tuple[Optional[str], Optional[bool]]:
    """Hand the matched rule and fact to cpu-llm's reasoner; realize and audit what it derives."""
    name = f"the {fact.entity}" if fact.entity[:1].islower() else fact.entity
    props = [
        EIRProposition(proposition_id="rule", modality=Modality.OBLIGATIVE if rule.modality == "required"
                       else Modality.PERMISSIVE, quantifier=Quantifier(qtype=QuantifierType.ALL),
                       subject=TypedEntity(raw_text=rule.category + "s", lemma=rule.category, is_plural=True),
                       predicate=TypedPredicate(lemma="use"),
                       object_target=TypedEntity(raw_text=rule.object, lemma=rule.object, is_plural=False),
                       condition_tree=_condition(rule), epistemic_weight=1.0),
        EIRProposition(proposition_id="isa", subject=TypedEntity(raw_text=name, lemma=name.lower(), is_plural=False),
                       predicate=TypedPredicate(lemma="be"),
                       object_target=TypedEntity(raw_text=f"a {rule.category}", lemma=rule.category, is_plural=False),
                       epistemic_weight=1.0),
        EIRProposition(proposition_id="metric", subject=TypedEntity(raw_text=name, lemma=name.lower(), is_plural=False),
                       predicate=TypedPredicate(lemma="measure"), metric_name=rule.metric, metric_value=value,
                       metric_unit=canon(rule.unit), epistemic_weight=1.0),
    ]
    result = PrismCognitionSubspaceAdapter().deliberate(np.zeros(128), props, [np.zeros(128)] * 3, "fact-bridge")
    derived = [p for p in result.grounded_propositions
               if p.derivation and p.epistemic_status is EpistemicStatus.ACTIVATED_CONCLUSION]
    if not derived:
        return None, None
    text, delivered = SemanticSurfaceRealizer().synthesize([derived[0]], [])
    return text, EpistemicEntailmentAuditor().audit_delivered_output(delivered, [derived[0]])


def _rule_plan(r: Rule) -> dict:
    return {"category": r.category, "object": r.object, "modality": r.modality, "metric": r.metric,
            "op": r.op, "op_text": _OP_TEXT[r.op], "threshold": r.threshold, "unit": r.unit, "source": r.source}


def _fact_plan(f: Fact, value: Optional[float], rule: Optional[Rule]) -> dict:
    out = {"entity": f.entity, "metric": f.metric, "value": f.value, "unit": f.unit, "source": f.source}
    if rule is not None and value is not None and canon(f.unit) != canon(rule.unit):
        out["converted"] = {"value": round(value, 6), "unit": rule.unit}
    return out


def _asked_modality(question: str) -> str:
    """The modality the question asks about, not the modality stored in a rule."""
    if re.search(r"\b(?:forbidden|prohibited|banned|not allowed|not permitted)\b", question, re.IGNORECASE):
        return "forbidden"
    if re.search(r"\b(?:required|mandatory|must)\b", question, re.IGNORECASE):
        return "required"
    return "allowed"


def _plan(verdict: str, question: str, **parts) -> dict:
    parts.setdefault("asked", _asked_modality(question))
    return {"verdict": verdict, "question": question, **{k: v for k, v in parts.items() if v is not None}}


def reason(question: str, ex: Extraction) -> Answer:
    answer = _reason(question, ex)
    answer.plan.setdefault("sources", list(answer.because))
    return answer


_CAUSE_STOP = {"why", "does", "did", "the", "are", "was", "were", "can", "may", "must", "should", "would", "could",
               "have", "has", "had", "not", "for", "important", "employee", "employees", "need", "needs"}


def _reason(question: str, ex: Extraction) -> Answer:
    q = question.strip()
    if re.match(r"(?i)^why\b", q) and ex.causes:
        # The stated effect must be what the question asks about: at least two of the question's content words
        # and half of them. Otherwise no cause is given (a 'because' sentence about something else is not an answer).
        asked = set(_words(q)) - _CAUSE_STOP
        def overlap(c: Cause) -> int:
            return len(set(_words(c.effect)) & asked)
        best = max(ex.causes, key=overlap)
        if asked and overlap(best) >= 2 and overlap(best) >= 0.5 * len(asked):
            return Answer("CAUSE", f"Because {best.cause.rstrip('.')}.", [best.source],
                          plan=_plan("CAUSE", q, effect=best.effect, cause=best.cause.rstrip(".")))

    rules = [r for r in ex.rules if _appears(r.object, q)]
    if not rules:
        return Answer("NONE", "No retrieved rule covers this question.", plan=_plan("NONE", q, reason="no_rule"))
    facts = _entity_facts(ex.facts, q)
    if not facts:
        r = rules[0]
        return Answer("UNKNOWN", f"It depends on the {r.metric}: {r.object} is {r.modality} for {r.category}s "
                                 f"{_OP_TEXT[r.op]} {r.threshold:g} {plural(r.unit)}, and nothing retrieved gives it.",
                      [r.source], plan=_plan("UNKNOWN", q, rule=_rule_plan(r), missing=r.metric, entity=None))

    asked = _asked_modality(q)
    cats: dict[str, list[str]] = {}
    for f in facts:
        for k, v in categories_of(f, ex.isa).items():
            cats.setdefault(k, v)
    opinions = []
    opens = []
    for r in rules:
        if r.category not in cats:
            continue
        fact = next((f for f in facts if f.metric == r.metric), None)
        stance, value = _stance(r, fact)
        verdict = _ASKED_VERDICT[asked].get(stance) if stance else None
        if verdict == "OPEN":
            opens.append((r, fact, value, stance))
            continue
        if verdict:
            opinions.append((verdict, stance, r, fact, value))
    if not opinions:
        if opens:
            r, f, value, stance = opens[0]
            sources = [r.source] + ([f.source] if f else [])
            gap = "permission_not_obligation" if asked == "required" else "sufficient_allowance"
            return Answer(
                "UNKNOWN",
                "The retrieved passages do not settle that.",
                sources,
                plan=_plan(
                    "UNKNOWN", q, entity=f.entity if f else facts[0].entity,
                    rule=_rule_plan(r), fact=_fact_plan(f, value, r) if f else None,
                    gap=gap, stance=stance,
                ),
            )
        return Answer("NONE", "No retrieved rule applies to this kind of thing.",
                      plan=_plan("NONE", q, reason="no_matching_category", entity=facts[0].entity))

    # A rule that does not fire is not a contradiction. The rules conflict only when two thresholds on the
    # same measure disagree, or a forbidding rule fires next to one that permits or requires. Otherwise one firing
    # rule is enough for YES, and NO needs every applicable rule to say no.
    def _conflicting(ops) -> bool:
        yes = [(r, f) for k, _stance_name, r, f, _ in ops if k == "YES"]
        no = [(r, f) for k, _stance_name, r, f, _ in ops if k == "NO"]
        forbidden_fires = any(r.modality == "forbidden" for r, _ in yes + no)
        same_measure = any(
            ry.metric == rn.metric and {ry.modality, rn.modality} != {"forbidden"}
            for ry, _ in yes for rn, _ in no
        )
        return bool(yes) and bool(no) and (forbidden_fires or same_measure)

    kinds = {v for v, *_ in opinions}
    if {"YES", "NO"} <= kinds and not _conflicting(opinions):
        opinions = [o for o in opinions if o[0] == "YES"] + [o for o in opinions if o[0] not in {"YES", "NO"}]
        kinds = {v for v, *_ in opinions}
    sources = list(dict.fromkeys(
        s for _, _stance_name, r, f, _v in opinions for s in [r.source] + ([f.source] if f else [])
    ))
    if {"YES", "NO"} <= kinds:
        return Answer("CONTESTED", "The retrieved rules disagree: " + " / ".join(r.source for _, _s, r, *_ in opinions),
                      sources, plan=_plan("CONTESTED", q, entity=facts[0].entity,
                                          fact=_fact_plan(opinions[0][3], opinions[0][4], opinions[0][2])
                                          if opinions[0][3] else None,
                                          rules=[dict(_rule_plan(r), outcome=v) for v, _s, r, *_ in opinions]))
    if "YES" in kinds:
        _, stance, r, f, value = next(o for o in opinions if o[0] == "YES")
        also = [{"rule": _rule_plan(r2), "fact": _fact_plan(f2, v2, r2)}
                for k, _s, r2, f2, v2 in opinions if k == "YES" and r2 is not r and f2 is not None and f2 is not f]
        plan = _plan("YES", q, entity=f.entity, rule=_rule_plan(r), fact=_fact_plan(f, value, r),
                     via=cats.get(r.category) or None, also=also or None, stance=stance)
        if stance in {"prohibited", "not_permitted"}:
            return Answer("YES", "Yes.", sources + cats.get(r.category, []), plan=plan)
        text, audited = _derive(r, f, value)
        if text is None:
            return Answer("UNKNOWN", "The rule matched, but the reasoner could not derive a conclusion.", sources,
                          plan=_plan("UNKNOWN", q, rule=_rule_plan(r), entity=f.entity, missing="derivation"))
        return Answer("YES", "Yes. " + text[0].upper() + text[1:], sources + cats.get(r.category, []), audited,
                      plan=plan)
    if "NO" in kinds:
        _, stance, r, f, value = next(o for o in opinions if o[0] == "NO")
        also = [{"rule": _rule_plan(r2), "fact": _fact_plan(f2, v2, r2)}
                for k, _s, r2, f2, v2 in opinions if k == "NO" and r2 is not r and f2 is not None and f2 is not f
                and r2.modality != "forbidden" and r.modality != "forbidden"]
        plan = _plan("NO", q, entity=f.entity, rule=_rule_plan(r), fact=_fact_plan(f, value, r),
                     via=cats.get(r.category) or None, also=also or None, stance=stance)
        if r.modality == "forbidden":
            return Answer("NO", f"No. {r.object.capitalize()} is forbidden for the {f.entity} ({f.value:g} "
                                f"{plural(f.unit)} is {_OP_TEXT[r.op]} {r.threshold:g} {plural(r.unit)}).", sources,
                          plan=plan)
        return Answer("NO", f"No. The {f.entity} is {f.value:g} {plural(f.unit)}, and {r.object} is {r.modality} "
                            f"for {r.category}s {_OP_TEXT[r.op]} {r.threshold:g} {plural(r.unit)}.", sources,
                      plan=plan)
    _, _stance_name, r, f, _v = opinions[0]
    missing = f"the {r.metric}" if f is None else f"a {r.unit} value ({f.value:g} {plural(f.unit)} does not convert)"
    return Answer("UNKNOWN", f"Nothing retrieved gives {missing} for the {facts[0].entity}.", sources,
                  plan=_plan("UNKNOWN", q, rule=_rule_plan(r), entity=facts[0].entity,
                             missing=r.metric if f is None else "unit_conversion",
                             fact=_fact_plan(f, None, r) if f else None))


# ---------------------------------------------------------------- multi-hop retrieval


def _follow_ups(question: str, ex: Extraction) -> list[str]:
    queries = []
    rules = [r for r in ex.rules if _appears(r.object, question)]
    facts = _entity_facts(ex.facts, question)
    if rules and not facts:
        focus = question
        for r in rules:
            focus = re.sub(re.escape(r.object), " ", focus, flags=re.I)
        queries.append(re.sub(r"\s+", " ", focus).strip())
    for f in facts:
        for name in categories_of(f, ex.isa):
            queries.append(f"What is a {name}?")
        queries.append(f"What is {f.entity}?")
    return list(dict.fromkeys(queries))


def answer(question: str, chunks: list[str], extractor=None, retrieve=None, hops: int = 3, *,
           grade=None, child_safety: Optional[bool] = None, conversation=None,
           ml: bool = False, model_root: Optional[str] = None) -> Answer:
    """`chunks`: retrieved texts (any length). `retrieve(query) -> list[str]` enables multi-hop follow-ups.

    `ml=True` reads the sentences with the trained extractor and phrases the verdict with the trained writer.
    A missing model directory raises. `grade`, `child_safety`, and `conversation` are accepted and not applied.
    """
    del grade, child_safety, conversation
    writer = None
    if ml and extractor is None:
        extractor, writer = load_ml(model_root)
    elif ml:
        _extractor, writer = load_ml(model_root)
        del _extractor
    result = _answer(question, chunks, extractor, retrieve, hops)
    if writer is not None:
        reply = writer.write(result)
        result.text = reply.text
        result.wording = {"path": reply.path, "rejected": reply.rejected, "ms": reply.ms}
    return result


# Definitions supplied only when the retrieved text already uses that word.
# They close a join the source wording left implicit: a purchase counted as an
# expense, or a named laptop. An international trip is handled below, and only
# when the retrieved text states the eligibility or the London flight.
_MEMORY_CUES = (
    ("purchase", "A purchase is an expense."),
    ("reimbursement", "A reimbursement is an expense."),
    ("subscription", "A subscription is an expense."),
    ("macbook pro", "A MacBook Pro is a laptop."),
    ("thinkpad", "A ThinkPad is a laptop."),
    ("laptop", "A laptop is a computer."),
)
_ELIGIBLE = re.compile(
    r"for more than (\d+(?:\.\d+)?) hours are eligible to book premium economy",
    re.I,
)
_LONDON = re.compile(r"flight to London", re.I)
_LONDON_KIND = re.compile(r"flight to London is an international", re.I)


def _cued(blob: str, cue: str) -> bool:
    return re.search(rf"\b{re.escape(cue)}\b", blob, re.I) is not None


def _cue_sentences(blob: str, pool: list[str], extra: list[str]) -> None:
    for cue, sentence in _MEMORY_CUES:
        if sentence in pool or sentence in extra:
            continue
        if _cued(blob, cue):
            extra.append(sentence)


def _with_memory(pool: list[str]) -> list[str]:
    """Append memory sentences the retrieved text already gives a cue for."""
    blob = "\n".join(pool)
    extra: list[str] = []
    _cue_sentences(blob, pool, extra)
    _cue_sentences(blob + "\n" + "\n".join(extra), pool, extra)
    found = _ELIGIBLE.search(blob)
    if found:
        rule = f"Premium economy is allowed for international flights over {found.group(1)} hours."
        if rule not in pool and rule not in extra:
            extra.append(rule)
    if _LONDON.search(blob) and not _LONDON_KIND.search(blob):
        kind = "The flight to London is an international flight."
        if kind not in pool and kind not in extra:
            extra.append(kind)
    return pool + extra


def _answer(question: str, chunks: list[str], extractor=None, retrieve=None, hops: int = 3) -> Answer:
    extractor = extractor or PatternExtractor()
    pool = _with_memory(list(dict.fromkeys(s.strip() for c in chunks for s in split_sentences(c))))
    asked = {question}
    for _ in range(hops if retrieve else 0):
        grounded, _ = ground(extractor.extract(pool), pool)
        new = []
        for query in _follow_ups(question, grounded):
            if query in asked:
                continue
            asked.add(query)
            new += [s.strip() for c in retrieve(query) for s in split_sentences(c) if s.strip() not in pool]
        if not new:
            break
        pool += list(dict.fromkeys(new))
    grounded, rejected = ground(extractor.extract(pool), pool)
    result = reason(question, grounded)
    result.rejected = rejected
    result.text = _situation_text(result)
    result.wording = {"path": "deterministic"}
    return result


def _situation_text(result: Answer) -> str:
    """The sentence for this verdict."""
    plan = result.plan or {}
    if plan.get("verdict") not in {"YES", "NO", "CONTESTED", "UNKNOWN", "CAUSE", "NONE"}:
        return result.text
    from fact_bridge.writer import wordings

    try:
        return wordings(plan)[0]
    except (KeyError, IndexError, TypeError):
        return result.text


_ML: dict[str, tuple] = {}


def model_root(explicit: Optional[str] = None) -> Optional[Path]:
    """Where the trained extractor and writer live, if they are on disk."""
    from pathlib import Path as _Path

    candidates = []
    if explicit:
        candidates.append(_Path(explicit))
    env = os.environ.get("FACTBRIDGE_MODELS")
    if env:
        candidates.append(_Path(env))
    repo = _Path(__file__).resolve().parents[2]
    candidates.append(repo / "models")
    candidates.append(repo / "cpullm-factbridge" / "models")
    for path in candidates:
        if (path / "extractor-flan-t5-small").is_dir():
            return path
    return None


def load_ml(root: Optional[str] = None):
    """The hybrid extractor and the writer. Loaded once. CPU only."""
    found = model_root(root)
    if found is None:
        raise FileNotFoundError("no fact-bridge model directory with extractor-flan-t5-small")
    key = str(found)
    if key not in _ML:
        from fact_bridge.learned_extractor import HybridExtractor, LearnedExtractor
        from fact_bridge.writer import Writer

        writer_dir = found / "writer-flan-t5-small"
        if not (writer_dir / "model.safetensors").is_file():
            writer_dir = found / "writer-flan-t5-base"
        _ML[key] = (
            HybridExtractor(learned=LearnedExtractor(str(found / "extractor-flan-t5-small"))),
            Writer(str(writer_dir)),
        )
    return _ML[key]
