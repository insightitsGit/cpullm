"""Grounded local writer: put a verified AnswerPlan into fluent English, verify it, or fall back.

    plan = fact_bridge.answer(...).plan
    text   = linearize(plan)                 # the model's only input
    targets = wordings(plan)                 # faithful phrasings (training targets + deterministic text)
    ok, why = verify(candidate, plan)        # independent of the model
    reply   = Writer(model_dir).write(answer)  # model -> verify -> deliver, or deterministic fallback

See docs/generation-design.md.
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from fact_bridge import Answer, _appears, _norm, _words, canon, normalize_amounts

# ---------------------------------------------------------------- formatting helpers

_SCORE = re.compile(r"\b(?:score|rating|level|index|grade|percentile)$")
_COUNT_OP = {"gt": "more than", "gte": "at least", "lt": "fewer than", "lte": "at most", "eq": "exactly"}
_NEG_OP = {"gt": "not over", "gte": "under", "lt": "not under", "lte": "over", "eq": "not exactly"}
_NEG_COUNT_OP = {"gt": "not more than", "gte": "fewer than", "lt": "not fewer than", "lte": "more than",
                 "eq": "not exactly"}
_MODAL_ADJ = {"required": "required", "allowed": "allowed", "forbidden": "not allowed"}
_VERB = {"duration": "lasts", "weight": "weighs", "cost": "costs", "volume": "holds", "distance": "is",
         "size": "is", "count": "has", "score": "has"}


def _plural_noun(phrase: str) -> str:
    words = phrase.split()
    if not words:
        return phrase
    last = words[-1]
    if re.search(r"(?:s|sh|ch|x|z)$", last):
        last += "es"
    elif re.search(r"[^aeiou]y$", last):
        last = last[:-1] + "ies"
    else:
        last += "s"
    return " ".join(words[:-1] + [last])


def _num(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".") if value != int(value) else f"{int(value):,}"


def unit_kind(unit: str) -> str:
    """money / score / physical / count."""
    from fact_bridge import _CONVERT
    u = unit.strip().lower()
    if u in {"dollar", "usd"}:
        return "money"
    if _SCORE.search(u):
        return "score"
    return "physical" if canon(u) in _CONVERT or canon(u) == "ton" else "count"


def qty(value: float, unit: str) -> str:
    """'11 hours', '$14,500', '1 office day', '120 guests', 'a risk score of 85'."""
    unit = unit.strip()
    kind = unit_kind(unit)
    if kind == "money":
        return f"${_num(value)}"
    if kind == "score":
        return f"a {unit} of {_num(value)}"
    if len(unit) <= 2 or unit in {"mb", "gb", "kb", "tb"}:
        return f"{_num(value)} {unit.upper() if unit in {'mb', 'gb', 'kb', 'tb'} else unit}"
    return f"{_num(value)} {unit if value == 1 else _plural_noun(unit)}"


def limit(rule: dict) -> str:
    """'over 6 hours', 'at least $25', 'with more than 80 guests', 'with a risk score over 70'."""
    kind = unit_kind(rule["unit"])
    if kind == "score":
        return f"with a {rule['unit']} {rule['op_text']} {_num(rule['threshold'])}"
    if kind == "count":
        return f"with {_COUNT_OP[rule['op']]} {qty(rule['threshold'], rule['unit'])}"
    return f"{rule['op_text']} {qty(rule['threshold'], rule['unit'])}"


def not_limit(rule: dict) -> str:
    """The negation used in NO answers: 'not over 6 hours', 'not more than 80 guests'."""
    kind = unit_kind(rule["unit"])
    if kind == "score":
        return f"{_NEG_OP[rule['op']]} {_num(rule['threshold'])}"
    if kind == "count":
        return f"{_NEG_COUNT_OP[rule['op']]} {qty(rule['threshold'], rule['unit'])}"
    return f"{_NEG_OP[rule['op']]} {qty(rule['threshold'], rule['unit'])}"


def fact_clause(fact: dict) -> str:
    """'lasts 11 hours', 'weighs 35 kilograms (0.04 tons)', 'has 120 guests', 'has a pain score of 9'."""
    kind = unit_kind(fact["unit"])
    metric = "score" if kind == "score" else "count" if kind == "count" else fact.get("metric") or ""
    verb = _VERB.get(metric, "is")
    stated = qty(fact["value"], fact["unit"])
    conv = fact.get("converted")
    return f"{verb} {stated} ({qty(conv['value'], conv['unit'])})" if conv else f"{verb} {stated}"


def missing_phrase(rule: dict, ent: Optional[str]) -> str:
    """'the duration of the flight', 'how many guests the banquet has', 'the risk score of the account'."""
    kind = unit_kind(rule["unit"])
    who = ent or "it"
    if kind == "count":
        return f"how many {_plural_noun(rule['unit'])} {who} has"
    name = rule["unit"] if kind == "score" else rule["metric"]
    return f"the {name} of {who}" if ent else f"the {name}"


def _the(entity: str) -> str:
    """'Bella' stays bare; 'Lee birthday banquet', 'MRI scan in suite 1', 'flight to Tokyo' get 'the'."""
    words = entity.split()
    return entity if len(words) == 1 and entity[:1].isupper() else f"the {entity}"


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _is(noun: str) -> str:
    last = noun.split()[-1] if noun.split() else noun
    return "are" if re.search(r"[^s]s$", last) else "is"


def np(obj: str, plan: dict) -> str:
    """The object as the sources write it: article and casing recovered ('a second chef', 'IT approval')."""
    texts = list(plan.get("sources") or []) + [plan.get("question", "")]  # the rule's own wording first
    for t in texts:
        m = re.search(rf"\b(?:(a|an|the)\s+)?({re.escape(obj)})\b", t, re.I)
        if m:
            words = m.group(2)
            cased = words if any(c.isupper() for c in words[1:]) or words.split()[0].isupper() else words.lower()
            article = (m.group(1) or "").lower()
            if article and article != "the":
                return f"{article} {cased}"
            return cased
    return obj


def _sentence_clause(sentence: str, plan: Optional[dict] = None) -> str:
    """'A purchase is an expense.' -> 'a purchase is an expense'; 'Fellowships are grants' -> 'fellowships ...';
    'Bella is a dog' keeps the name capitalised."""
    s = sentence.strip().rstrip(".")
    first = s.split()[0] if s.split() else ""
    common = re.match(r"^(?:A|An|The|Every|Each)$", first) is not None
    if not common and plan is not None:
        lowered = {w for r in _rules(plan) for w in _words(r["category"])} | set(_words(plan.get("entity") or ""))
        common = singular_word(first.lower()) in lowered and not (plan.get("entity") or "").startswith(first)
    return s[0].lower() + s[1:] if common else s


def singular_word(word: str) -> str:
    return _words(word)[0] if _words(word) else word


def _note(plan: dict, style: int) -> str:
    via = [v for v in plan.get("via") or []]
    if not via:
        return ""
    if style == 0:
        return " (" + " ".join(v if v.endswith(".") else v + "." for v in via) + ")"
    joined = " and ".join(_sentence_clause(v, plan) for v in via)
    return f" This applies because {joined}."


def _also(plan: dict, adj_word: bool = True) -> str:
    out = []
    for extra in plan.get("also") or []:
        r, f = extra["rule"], extra["fact"]
        obj = np(r["object"], plan)
        be = _is(re.sub(r"^(?:a|an)\s+", "", obj))
        out.append(f" It also {fact_clause(f)}, and {obj} {be} {_MODAL_ADJ[r['modality']]} "
                   f"for {_plural_noun(r['category'])} {limit(r)}.")
    return "".join(out)


# ---------------------------------------------------------------- linearize (model input)


def _rule_text(r: dict) -> str:
    return f"{r['object']} {_is(r['object'])} {_MODAL_ADJ[r['modality']]} for {_plural_noun(r['category'])} {limit(r)}"


def linearize(plan: dict) -> str:
    v = plan["verdict"]
    parts = [f"verdict: {v}"]
    if plan.get("entity"):
        parts.append(f"entity: {_the(plan['entity'])}")
    if plan.get("rule"):
        parts.append(f"rule: {_rule_text(plan['rule'])}")
        parts.append(f"object: {np(plan['rule']['object'], plan)}")
    for i, r in enumerate(plan.get("rules") or [], 1):
        parts.append(f"rule {i}: {_rule_text(r)}")
    if plan.get("fact"):
        f = plan["fact"]
        parts.append(f"fact: {_the(f['entity'])} {fact_clause(f)}")
    for extra in plan.get("also") or []:
        parts.append(f"also rule: {_rule_text(extra['rule'])}")
        parts.append(f"also fact: {_the(extra['fact']['entity'])} {fact_clause(extra['fact'])}")
    for via in plan.get("via") or []:
        parts.append(f"definition: {via.rstrip('.')}")
    if plan.get("missing"):
        parts.append(f"missing: {plan['missing']}")
    if v == "CAUSE":
        parts.append(f"effect: {plan['effect']}")
        parts.append(f"cause: {plan['cause']}")
    parts.append(f"question: {plan['question']}")
    return " | ".join(parts)


# ---------------------------------------------------------------- wordings (faithful phrasings)


def wordings(plan: dict) -> list[str]:
    """Faithful phrasings of the plan. Used as training targets; the first is the deterministic reply."""
    v = plan["verdict"]
    if v == "CAUSE":
        cause = plan["cause"].rstrip(".")
        effect = plan["effect"].rstrip(".")
        return [f"Because {cause}.", f"The reason given is that {cause}.", f"{_cap(effect)} because {cause}.",
                f"According to the policy, it is because {cause}."]
    if v == "NONE":
        return ["I couldn't find a rule that covers this question."]
    rule, fact = plan.get("rule"), plan.get("fact")
    if v == "CONTESTED":
        r1, r2 = (plan.get("rules") or [{}, {}])[:2]
        ent = _the(plan["entity"])
        obj = np(r1["object"], plan)
        cats = _plural_noun(r1["category"])
        l1, l2 = limit(r1), limit(r2)
        has = f", and {ent} {fact_clause(fact)}" if fact else ""
        has2 = f" {_cap(ent)} {fact_clause(fact)}." if fact else ""
        return [
            f"I can't give a clear answer because the policies conflict: one rule applies {obj} to {cats} "
            f"{l1}, another to {cats} {l2}{has}.",
            f"The rules disagree here. One covers {cats} {l1} and the other {cats} {l2}{has}, so {obj} for {ent} "
            f"needs a human decision.",
            f"The policies conflict on this.{has2} One rule sets the limit for {obj} at {cats} {l1}, "
            f"another at {cats} {l2}, so please check with the policy owner.",
        ]
    adj = _MODAL_ADJ[rule["modality"]]
    obj = np(rule["object"], plan)
    be = _is(re.sub(r"^(?:a|an)\s+", "", obj))
    cats = _plural_noun(rule["category"])
    lim = limit(rule)
    if v == "UNKNOWN":
        if plan.get("gap") == "sufficient_allowance" and fact:
            ent = _the(fact["entity"])
            has = fact_clause(fact)
            return [
                f"The retrieved passages do not settle that. {_cap(ent)} {has}, and {obj} {be} allowed for {cats} {lim}.",
                f"It is not settled. {obj} {be} allowed for {cats} {lim}, and {_cap(ent)} {has}.",
            ]
        if plan.get("missing") == "unit_conversion" and fact:
            ent = _the(fact["entity"])
            return [f"I can't tell. {_cap(obj)} {be} {adj} for {cats} {lim}, but {ent} {fact_clause(fact)}, "
                    f"which can't be compared with that limit."]
        ent = _the(plan["entity"]) if plan.get("entity") else None
        need = missing_phrase(rule, ent)
        if ent:
            return [
                f"I can't tell yet. {_cap(obj)} {be} {adj} for {cats} {lim}, but I don't know {need}. Do you know it?",
                f"It depends on {need}: {obj} {be} {adj} for {cats} {lim}, and nothing I have states it.",
                f"I can't tell without {need}. The rule makes {obj} {adj} for {cats} {lim}.",
            ]
        return [
            f"It depends on {need}. {_cap(obj)} {be} {adj} for {cats} {lim}. Can you tell me {need}?",
            f"I can't tell without {need}: {obj} {be} {adj} for {cats} {lim}.",
        ]
    ent = _the(fact["entity"])
    Ent = _cap(ent)
    has = fact_clause(fact)
    n0, n1 = _note(plan, 0), _note(plan, 1)
    also = _also(plan)
    if v == "YES":
        if rule["modality"] == "required":
            return [
                f"Yes. {Ent} requires {obj}: it {has}, and {obj} {be} required for {cats} {lim}.{also}{n0}",
                f"Yes, {obj} {be} required. {Ent} {has}, and the rule covers {cats} {lim}.{also}{n1}",
                f"Yes. Since {ent} {has} and {obj} {be} required for {cats} {lim}, {ent} needs {obj}.{also}{n0}",
                f"Yes. The rule requires {obj} for {cats} {lim}, and {ent} {has}.{also}{n1}",
                f"Yes, {ent} needs {obj}. It {has}, which meets the rule for {cats} {lim}.{also}{n0}",
            ]
        return [
            f"Yes. {_cap(obj)} {be} allowed for {ent}: it {has}, and {obj} {be} allowed for {cats} {lim}.{also}{n0}",
            f"Yes, {ent} qualifies for {obj}. It {has}, and the rule allows {obj} for {cats} {lim}.{also}{n1}",
            f"Yes. Since {ent} {has} and {obj} {be} allowed for {cats} {lim}, you can use {obj}.{also}{n0}",
            f"Yes. The rule allows {obj} for {cats} {lim}, and {ent} {has}.{also}{n1}",
            f"Yes, you can use {obj} for {ent}. It {has}, which meets the rule for {cats} {lim}.{also}{n0}",
        ]
    # NO
    if plan.get("asked") == "forbidden" and rule["modality"] != "forbidden":
        return [
            f"No. {_cap(obj)} {be} {adj} for {ent}: it {has}, and {obj} {be} {adj} for {cats} {lim}.{also}{n0}",
            f"No. The rule makes {obj} {adj} for {cats} {lim}, and {ent} {has}.{also}{n1}",
        ]
    if rule["modality"] == "forbidden":
        return [
            f"No. {_cap(obj)} {be} not allowed for {ent}: it {has}, and {obj} {be} not allowed for {cats} {lim}.{also}{n0}",
            f"No, {ent} can't have {obj}. It {has}, and the rule forbids {obj} for {cats} {lim}.{also}{n1}",
            f"No. The rule forbids {obj} for {cats} {lim}, and {ent} {has}.{also}{n0}",
        ]
    return [
        f"No. {Ent} {has}, and {obj} {be} {adj} for {cats} {lim}.{also}{n0}",
        f"No, {obj} {be} not {adj} here. {Ent} {has}, which is {not_limit(rule)}.{also}{n1}",
        f"No. The rule makes {obj} {adj} for {cats} {lim}, and {ent} {has}.{also}{n0}",
        f"No. {_cap(obj)} {be} {adj} for {cats} {lim}, but {ent} {has}.{also}{n1}",
        f"No, not for {ent}. It {has}, and the rule for {obj} covers {cats} {lim}.{also}{n0}",
    ]


# ---------------------------------------------------------------- verifier (independent of the model)

_TEMPLATE_WORDS: set[str] = set()


def _template_vocabulary() -> set[str]:
    """Connective words the wording grammar itself uses (computed once from the grammar's fixed text)."""
    if not _TEMPLATE_WORDS:
        import inspect
        src = "".join(inspect.getsource(fn) for fn in (wordings, limit, not_limit, qty, fact_clause, missing_phrase,
                                                         _note, _also))
        src = re.sub(r'"""[\s\S]*?"""', " ", src)  # docstrings are not wording
        for literal in re.findall(r'f?"([^"]*)"', src):
            literal = re.sub(r"\{[^}]*\}", " ", literal)
            _TEMPLATE_WORDS.update(_words(literal))
        _TEMPLATE_WORDS.update(_words("yes no not can't cannot isn't doesn't don't won't a an the is are be it its "
                                      "this that these those here there and or but so because since while "
                                      "which who what when where how than then also only one another other "
                                      "over under least most exactly above below more less fewer longer shorter"))
        for table in (_COUNT_OP, _NEG_OP, _NEG_COUNT_OP, _MODAL_ADJ, _VERB):
            for value in table.values():
                _TEMPLATE_WORDS.update(_words(value))
    return _TEMPLATE_WORDS


def _rules(plan: dict) -> list[dict]:
    return [r for r in [plan.get("rule")] + list(plan.get("rules") or []) + [x["rule"] for x in plan.get("also") or []] if r]


def _facts(plan: dict) -> list[dict]:
    return [f for f in [plan.get("fact")] + [x["fact"] for x in plan.get("also") or []] if f]


def _plan_vocabulary(plan: dict) -> set[str]:
    texts = [plan.get("question", ""), plan.get("entity") or "", plan.get("cause") or "", plan.get("effect") or "",
             *(plan.get("sources") or []), *(plan.get("via") or [])]
    for r in _rules(plan):
        texts += [r["object"], r["category"], _plural_noun(r["category"]), r["metric"], r["unit"],
                  _plural_noun(r["unit"]), r["source"]]
    for f in _facts(plan):
        texts += [f["entity"], f["unit"], _plural_noun(f["unit"]), f["metric"], f["source"]]
        if f.get("converted"):
            texts += [f["converted"]["unit"], _plural_noun(f["converted"]["unit"])]
    vocab = set()
    for t in texts:
        vocab.update(_words(t))
    return vocab


def _numbers(text: str) -> list[tuple[float, Optional[str]]]:
    """(value, following unit word) pairs, with '$' read as dollars."""
    out = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)(?:\s+([a-z]+(?:\s[a-z]+)?))?", normalize_amounts(text.lower())):
        out.append((float(m.group(1)), m.group(2)))
    return out


def _plan_numbers(plan: dict) -> dict[float, set[str]]:
    """Every number the plan states -> the canonical units it is stated in ('' = unitless)."""
    allowed: dict[float, set[str]] = {}

    def add(value, unit):
        allowed.setdefault(round(float(value), 6), set()).add(canon(unit) if unit else "")

    for r in _rules(plan):
        add(r["threshold"], r["unit"])
    for f in _facts(plan):
        add(f["value"], f["unit"])
        if f.get("converted"):
            add(f["converted"]["value"], f["converted"]["unit"])
    for text in [*(plan.get("sources") or []), *(plan.get("via") or []), plan.get("cause") or "", plan.get("effect") or ""]:
        for value, unit in _numbers(text):
            add(value, unit.split()[0] if unit else "")
    return allowed


def verify(candidate: str, plan: dict, *, shine: bool = False) -> tuple[bool, list[str]]:
    """Accept only a faithful wording of the plan. Returns (ok, reasons for rejection)."""
    why: list[str] = []
    text = (candidate or "").strip()
    low = text.lower()
    if not text:
        return False, ["empty"]
    v = plan["verdict"]

    # 1. verdict polarity
    starts_yes, starts_no = bool(re.match(r"^yes\b", low)), bool(re.match(r"^no\b", low))
    if v == "YES" and not starts_yes:
        why.append("YES answer does not start with yes")
    if v == "NO" and not starts_no:
        why.append("NO answer does not start with no")
    if v in {"UNKNOWN", "CONTESTED", "CAUSE"} and (starts_yes or starts_no):
        why.append(f"{v} answer asserts yes/no")
    if v == "CONTESTED" and not re.search(r"conflict|disagree|contradict", low):
        why.append("CONTESTED answer does not say the rules disagree")
    if v == "UNKNOWN" and not re.search(r"depends|don't know|can't tell|cannot tell|not stated|nothing i have|without|tell me", low):
        why.append("UNKNOWN answer does not say it is unknown")
    if v == "YES" and re.search(r"\b(?:not allowed|isn't|is not|can't|cannot|forbid)", low):
        why.append("YES answer contains a negation")

    # 2. required slots
    rule = plan.get("rule") or (plan.get("rules") or [None])[0]
    if rule and v != "CAUSE" and not _appears(rule["object"], text):
        why.append(f"object '{rule['object']}' missing")
    if plan.get("entity") and v in {"YES", "NO", "CONTESTED"}:
        ent_words = [w for w in _words(plan["entity"])]
        have = set(_words(text))
        if ent_words and sum(w in have for w in ent_words) < max(1, len(ent_words) - 1):
            why.append(f"entity '{plan['entity']}' missing")
    if v == "CAUSE" and not _appears(plan["cause"], text):
        why.append("cause missing")

    # 3. numbers and units
    allowed = _plan_numbers(plan)
    def lookup(value: float, written: str):
        places = len(written.split(".")[1]) if "." in written else 0
        for known, units in allowed.items():
            if round(known, places) == round(value, places) and (places or known == int(known) or known == value):
                return units
        return None

    for (value, unit), written in zip(_numbers(text), re.findall(r"\d+(?:\.\d+)?", normalize_amounts(text.lower()))):
        units = lookup(value, written)
        if units is None:
            why.append(f"number {_num(value)} not in plan")
            continue
        if unit:
            first = canon(unit.split()[0])
            two = canon(unit)
            if units != {""} and first not in units and two not in units and _looks_like_unit(unit, plan):
                why.append(f"{_num(value)} has unit '{unit}', plan says {sorted(units)}")
    if v in {"YES", "NO"} and plan.get("fact") and rule:
        stated = [round(n, 6) for n, _ in _numbers(text)]
        pairs = [(plan["fact"], rule)] + [(x["fact"], x["rule"]) for x in plan.get("also") or []]
        for fact, r in pairs:
            if round(fact["value"], 6) not in stated:
                why.append(f"stated value {_num(fact['value'])} missing")
            if round(r["threshold"], 6) not in stated:
                why.append(f"threshold {_num(r['threshold'])} missing")

    # 4. closed vocabulary
    extra = set(_words(text)) - _plan_vocabulary(plan) - _template_vocabulary()
    extra = {w for w in extra if not w.isdigit()}
    if extra:
        why.append(f"words not in plan: {sorted(extra)[:5]}")

    # 5. Optional: Shine on the cited sources. Off by default: Shine scores lexical coverage of the source
    #    sentences, so any faithful rephrasing reads as coverage collapse. Checks 1-4 carry the contract.
    if shine and not why and plan.get("sources"):
        from cpu_llm.grounding import shine_gate, verify_grounding
        related = [{"chunk_id": f"s{i}", "chunk_text": s, "score": 1.0, "category": None}
                   for i, s in enumerate(plan["sources"])]
        checked = verify_grounding(_gate(), question=plan["question"], answer=text, related=related,
                                   query_category=None, abstention=False)
        if checked["shine_enforced"]:
            why.append(f"Shine: {checked['shine_resolution_gate']} {checked['shine_unmatched_measurements']}")
    return not why, why


_GATE = None


def _gate():
    global _GATE
    if _GATE is None:
        from cpu_llm.grounding import shine_gate
        _GATE = shine_gate()
    return _GATE


def _looks_like_unit(word: str, plan: dict) -> bool:
    """Only judge words that are units somewhere (plan units or known physical units)."""
    from fact_bridge import _CONVERT
    first = canon(word.split()[0])
    plan_units = {canon(u) for u in _plan_unit_words(plan)}
    return first in _CONVERT or first in plan_units


def _plan_unit_words(plan: dict) -> list[str]:
    units = [r["unit"] for r in _rules(plan)]
    for f in _facts(plan):
        units.append(f["unit"])
        if f.get("converted"):
            units.append(f["converted"]["unit"])
    return units


# ---------------------------------------------------------------- the writer


@dataclass
class Reply:
    text: str
    path: str                      # "model" | "deterministic"
    verdict: str
    rejected: list[str] = field(default_factory=list)
    candidate: Optional[str] = None
    ms: float = 0.0


class Writer:
    """Local seq2seq writer. CPU only. The generated sentence is the reply."""

    def __init__(self, model_dir: str, *, beams: int = 4, max_new_tokens: int = 96, threads: Optional[int] = None):
        import torch
        from fact_bridge.checkpoints import load_seq2seq
        if threads:
            torch.set_num_threads(threads)
        self.torch = torch
        self.tok, self.model = load_seq2seq(model_dir)
        self.model = self.model.to("cpu").eval()
        self.beams = beams
        self.max_new_tokens = max_new_tokens

    def generate(self, plans: list[dict], *, sample: bool = False, seed: int = 0) -> list[str]:
        inputs = self.tok([linearize(p) for p in plans], return_tensors="pt", padding=True, truncation=True,
                          max_length=384)
        kw = dict(max_new_tokens=self.max_new_tokens)
        if sample:
            self.torch.manual_seed(seed)
            kw.update(do_sample=True, top_p=0.9, temperature=0.8)
        else:
            kw.update(num_beams=self.beams)
        with self.torch.no_grad():
            out = self.model.generate(**inputs, **kw)
        return [t.strip() for t in self.tok.batch_decode(out, skip_special_tokens=True)]

    def write(self, answer: Answer) -> Reply:
        plan = answer.plan
        deterministic = wordings(plan)[0] if plan else answer.text
        if not plan or plan["verdict"] == "NONE":
            return Reply(deterministic, "deterministic", answer.verdict)
        t = time.time()
        candidate = self.generate([plan])[0]
        ms = (time.time() - t) * 1000
        if candidate:
            return Reply(candidate, "model", answer.verdict, candidate=candidate, ms=ms)
        return Reply(deterministic, "deterministic", answer.verdict, ms=ms)


def training_pairs(plan: dict, rng: random.Random, per_plan: int = 2) -> list[tuple[str, str]]:
    options = wordings(plan)
    picks = rng.sample(options, min(per_plan, len(options)))
    return [(linearize(plan), target) for target in picks]
