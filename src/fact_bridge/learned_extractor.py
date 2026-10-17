"""Learned extractor for fact_bridge: a small seq2seq model proposes, deterministic checks dispose.

    sentence -> flan-t5 (CPU) -> linear items -> parse -> VERIFY (this file) -> ground() (fact_bridge, in answer())

The model only proposes spans. Everything that decides a YES/NO is re-read from the sentence itself:

  * comparison (over / at least / or more ...)  read from the words around the threshold number
  * modality (required / allowed / forbidden)   read from the sentence's modal words; any negation the lexicon
                                                does not explain, or any exception word (unless, except ...),
                                                vetoes the whole sentence
  * which noun the threshold applies to         the category must sit just before the comparison, with the
                                                object nowhere in between
  * facts                                       the value must be a plain measurement (no over/under/up to),
                                                the unit next to it, the sentence free of modals and negation
  * is-a                                        "<sub>[, <sub> and <sub>] is/are/counts as/... <sup>." exactly

If the model and the sentence disagree on any of these, the item is dropped (a veto), never repaired.
answer() then runs fact_bridge.ground() on what is left, so no word or number outside the source survives.

Usage:
    from fact_bridge import answer
    from fact_bridge.learned_extractor import LearnedExtractor, HybridExtractor
    ex = HybridExtractor(learned=LearnedExtractor("models/extractor-flan-t5-small"))
    answer(question, chunks, extractor=ex)

Wire format (flan-t5's vocabulary has no curly braces, so not JSON): items joined by " ## ", fields by " | ".
    rule | flight | business class | allowed | gt | 6 | hour
    fact | flight from Los Angeles to Tokyo | 11 | hour
    isa | Bella | dog
    cause | knives are sharpened weekly | dull knives cause accidents
    none
"""

from __future__ import annotations

import re
import time
from collections import Counter
from typing import Optional

from fact_bridge import (
    _PREP, Cause, Extraction, Fact, IsA, PatternExtractor, Rule, _words, metric_for, normalize_amounts, singular,
)

PROMPT = "extract: "
ITEM_SEP, FIELD_SEP = " ## ", " | "
OP_NAMES = ("gt", "gte", "lt", "lte", "eq")
MODALITIES = ("required", "allowed", "forbidden")

# ---------------------------------------------------------------- wire format


def _num_text(x: float) -> str:
    return str(int(x)) if float(x) == int(x) else f"{x:g}"


def serialize(ex: Extraction) -> str:
    items = []
    for r in ex.rules:
        items.append(FIELD_SEP.join(["rule", r.category, r.object, r.modality, r.op, _num_text(r.threshold), r.unit]))
    for f in ex.facts:
        items.append(FIELD_SEP.join(["fact", f.entity, _num_text(f.value), f.unit]))
    for i in ex.isa:
        items.append(FIELD_SEP.join(["isa", i.sub, i.sup]))
    for c in ex.causes:
        items.append(FIELD_SEP.join(["cause", c.effect, c.cause]))
    return ITEM_SEP.join(items) if items else "none"


def _fact_category(entity: str) -> str:
    head = re.match(rf"^(.+?) {_PREP} ", entity, re.I)
    return singular(head[1] if head else entity)


def parse(text: str, source: str) -> tuple[Extraction, list[str]]:
    """Wire text -> Extraction (metric and fact category derived the way PatternExtractor derives them)."""
    out, bad = Extraction(), []
    if text.strip().lower() in ("", "none"):
        return out, bad
    for item in text.split("##"):
        f = [p.strip() for p in item.split("|")]
        try:
            kind = f[0].lower()
            if kind == "rule" and len(f) == 7 and f[3] in MODALITIES and f[4] in OP_NAMES and f[1] and f[2]:
                unit = singular(f[6])
                out.rules.append(Rule(category=singular(_strip_det(f[1])), object=_strip_det(f[2]).lower(),
                                      modality=f[3], metric=metric_for(unit), op=f[4], threshold=float(f[5]),
                                      unit=unit, source=source))
            elif kind == "fact" and len(f) == 4 and f[1]:
                unit = singular(f[3])
                entity = _strip_det(f[1])
                out.facts.append(Fact(entity=entity, category=_fact_category(entity), metric=metric_for(unit),
                                      value=float(f[2]), unit=unit, source=source))
            elif kind == "isa" and len(f) == 3 and f[1] and f[2]:
                out.isa.append(IsA(sub=_strip_det(f[1]), sup=_strip_det(f[2]), source=source))
            elif kind == "cause" and len(f) == 3 and f[1] and f[2]:
                out.causes.append(Cause(effect=f[1], cause=f[2], source=source))
            else:
                bad.append(f"unparsable item: {item.strip()!r}")
        except ValueError:
            bad.append(f"bad number: {item.strip()!r}")
    return out, bad


def _strip_det(text: str) -> str:
    return re.sub(r"^(?:(?:a|an|the|any|every|each|all|our|my|your)\s+)+", "", text.strip(), flags=re.I).strip()


# ---------------------------------------------------------------- deterministic readers

_NUMBER_WORDS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
                 "sixteen seventeen eighteen nineteen twenty").split()
_NUMBER_WORDS = {w: i for i, w in enumerate(_NUMBER_WORDS)} | {"thirty": 30, "forty": 40, "fifty": 50, "hundred": 100}
_ARTICLES = {"a", "an", "the"}


def tokens(text: str, commas: bool = False, articles: bool = False) -> list[str]:
    """Lower-case tokens with amounts normalized ('$1,500' -> '1500 dollars') and number words as digits."""
    text = normalize_amounts(text).lower().replace("’", "'")
    out = []
    for t in re.findall(r"\d+(?:\.\d+)?|[a-z]+(?:'[a-z]+)?" + ("|," if commas else ""), text):
        out.append(str(_NUMBER_WORDS[t]) if t in _NUMBER_WORDS else t)
    return [t for t in out if articles or t not in _ARTICLES]


def _is_num(t: str) -> bool:
    return re.fullmatch(r"\d+(?:\.\d+)?", t) is not None


def _same(a: str, b: str) -> bool:
    return a == b or singular(a) == singular(b)


def find_spans(phrase: str, toks: list[str]) -> list[tuple[int, int]]:
    """All contiguous occurrences of `phrase` in `toks` (articles ignored, singular/plural-insensitive)."""
    p = tokens(phrase)
    if not p:
        return []
    return [(i, i + len(p)) for i in range(len(toks) - len(p) + 1)
            if all(_same(p[k], toks[i + k]) for k in range(len(p)))]


def _phrases(spec: dict[str, list[str]]) -> list[tuple[list[str], str]]:
    return sorted(((p.split(), k) for k, ps in spec.items() for p in ps), key=lambda x: -len(x[0]))


PREFIX_OPS = _phrases({
    "gt": ["over", "more than", "longer than", "greater than", "exceeding", "exceeds", "exceed", "exceeded",
           "above", "heavier than", "larger than", "bigger than", "higher than", "older than", "taller than",
           "wider than", "louder than", "warmer than", "hotter than", "farther than", "further than", "in excess of", "beyond", "upwards of", "pricier than"],
    "gte": ["at least", "no less than", "not less than", "no fewer than", "not fewer than", "no shorter than",
            "minimum of", "not under", "not below"],
    "lt": ["under", "below", "less than", "fewer than", "shorter than", "lighter than", "smaller than",
           "lower than", "younger than", "cheaper than", "quieter than", "colder than", "cooler than"],
    "lte": ["at most", "up to", "no more than", "not more than", "no longer than", "not longer than",
            "not exceeding", "maximum of", "not over", "not above", "no heavier than", "no greater than"],
    "eq": ["exactly"],
})
POSTFIX_OPS = _phrases({
    "gte": ["or more", "or longer", "or greater", "or above", "or over", "or higher", "or heavier", "or older",
            "and up", "and above", "and over", "or larger", "or bigger"],
    "lte": ["or less", "or fewer", "or under", "or below", "or shorter", "or younger", "or lighter", "or lower",
            "or smaller"],
})
APPROX = {"about", "around", "roughly", "approximately", "nearly", "some", "almost", "just"}


def _match_ending(toks, end, table):
    """Longest lexicon phrase ending at index end-1 -> (op, start)."""
    for words, op in table:
        s = end - len(words)
        if s >= 0 and toks[s:end] == words:
            return op, s
    return None, None


def read_op(toks: list[str], i: int) -> tuple[Optional[str], int, bool]:
    """Comparison attached to the number at toks[i] -> (op, start index of the comparison, ambiguous)."""
    pre, start = _match_ending(toks, i, PREFIX_OPS)
    post = None
    for j in range(i + 1, min(len(toks), i + 5)):
        for words, op in POSTFIX_OPS:
            if toks[j:j + len(words)] == words:
                post = op
                break
        if post or _is_num(toks[j]):
            break
    window = toks[max(0, i - 4):i]
    ambiguous = (pre is not None and post is not None) or "between" in window or "from" in window[-2:]
    return pre or post, (start if pre else i), ambiguous


MODAL = _phrases({
    "forbidden": ["not allowed", "not permitted", "not available", "not eligible", "not approved", "may not",
                  "must not", "cannot", "can't", "can not", "prohibited", "forbidden", "banned", "ineligible",
                  "never allowed", "never permitted", "is barred", "are barred", "disallowed", "not entitled"],
    "required": ["required", "must", "mandatory", "needed", "necessary", "need", "needs", "require", "requires",
                 "shall", "have to", "has to", "obligatory", "compulsory"],
    "allowed": ["allowed", "permitted", "may", "can", "available", "approved", "eligible", "qualify", "qualifies",
                "entitled", "get to", "gets to"],
})
NEGATION = {"not", "no", "never", "without", "nobody", "none", "neither", "nor", "don't", "doesn't", "isn't",
            "aren't", "won't", "shouldn't", "didn't", "optional", "exempt", "waived"}
EXCEPTION = {"unless", "except", "excluding", "excepting", "besides", "otherwise", "although", "however",
             "only if", "provided that", "as long as", "subject to approval"}
OP_WORDS = {w for table in (PREFIX_OPS, POSTFIX_OPS) for words, _ in table for w in words}


def read_modality(toks: list[str]) -> tuple[set[str], list[str]]:
    """Modal classes found in the sentence, and any negation the lexicon (modal or comparison) does not explain."""
    used = [False] * len(toks)
    found = set()
    for table in (MODAL, PREFIX_OPS, POSTFIX_OPS):
        i = 0
        while i < len(toks):
            for words, kind in table:
                if toks[i:i + len(words)] == words and not any(used[i:i + len(words)]):
                    if table is MODAL:
                        found.add(kind)
                    for k in range(i, i + len(words)):
                        used[k] = True
                    i += len(words) - 1
                    break
            i += 1
    stray = [t for t, u in zip(toks, used) if not u and (t in NEGATION or t.endswith("n't"))]
    return found, stray


def _exception(toks: list[str]) -> Optional[str]:
    joined = " ".join(toks)
    for w in EXCEPTION:
        if re.search(rf"\b{re.escape(w)}\b", joined):
            return w
    return None


# ---------------------------------------------------------------- verifier


def verify_rule(r: Rule, toks: list[str]) -> Optional[str]:
    if exc := _exception(toks):
        return f"exception word '{exc}'"
    found, stray = read_modality(toks)
    if stray:
        return f"unexplained negation '{stray[0]}'"
    if found != {r.modality}:
        return f"modality {r.modality} but sentence reads {sorted(found) or 'none'}"
    n = _num_text(r.threshold)
    occurrences = [i for i, t in enumerate(toks) if _is_num(t) and abs(float(t) - r.threshold) < 1e-9]
    if not occurrences:
        return f"threshold {n} not in sentence"
    reads = [read_op(toks, i) for i in occurrences]
    if any(amb for _, _, amb in reads):
        return "range or ambiguous comparison"
    ops = {op for op, _, _ in reads if op}
    if ops != {r.op}:
        return f"op {r.op} but sentence reads {sorted(ops) or 'none'} at {n}"
    i, (op, op_start, _) = next((i, rd) for i, rd in zip(occurrences, reads) if rd[0] == r.op)
    # unit: right after the number (possibly after one approximator), or a metric phrase just before the comparison
    unit_spans = find_spans(r.unit, toks)
    if not any(s in (i + 1, i + 2) or (op_start - 4 <= s and e <= op_start) for s, e in unit_spans):
        return f"unit '{r.unit}' not attached to {n}"
    # the category must be the noun the comparison hangs off: ends within 5 tokens before it, object not between
    cat_spans = [(s, e) for s, e in find_spans(r.category, toks) if e <= op_start and op_start - e <= 5]
    if not cat_spans:
        return f"category '{r.category}' not just before the comparison"
    cat_end = max(e for _, e in cat_spans)
    obj_spans = find_spans(r.object, toks)
    if not obj_spans:
        return f"object '{r.object}' not a contiguous phrase"
    if any(cat_end <= s < op_start for s, _ in obj_spans):
        return "object sits between category and comparison (roles swapped?)"
    if all(s <= i < e or (s < cat_end and e > cat_end - len(tokens(r.category))) for s, e in obj_spans):
        return "object overlaps the condition or the category"
    return None


def verify_fact(f: Fact, toks: list[str]) -> Optional[str]:
    if exc := _exception(toks):
        return f"exception word '{exc}'"
    found, stray = read_modality(toks)
    if found:
        return "modal sentence is a rule, not a fact"
    if stray:
        return f"unexplained negation '{stray[0]}'"
    if toks and toks[0] in ("if", "when", "whenever", "once", "should", "for"):
        return "conditional sentence"
    occurrences = [i for i, t in enumerate(toks) if _is_num(t) and abs(float(t) - f.value) < 1e-9]
    if not occurrences:
        return f"value {_num_text(f.value)} not in sentence"
    ent_spans = find_spans(f.entity, toks)
    if not ent_spans or not any(t not in ("it", "they", "this", "that", "these", "those") for t in tokens(f.entity)):
        return f"entity '{f.entity}' not a contiguous phrase"
    unit_spans = find_spans(f.unit, toks)
    for i in occurrences:
        op, _, amb = read_op(toks, i)
        if op or amb or (i > 0 and toks[i - 1] in ("within", "per", "every", "each")):
            continue
        after = any(s == i + 1 for s, _ in unit_spans)
        before = any(e == i or (e == i - 1 and toks[i - 1] in ("of", "is", "at", "was")) for _, e in unit_spans)
        if not (after or before):
            continue
        if any(s <= i < e for s, e in ent_spans):
            continue
        if not any(e <= i for _, e in ent_spans):
            continue
        return None
    return f"no plain '{_num_text(f.value)} {f.unit}' measurement after the entity"


_COPULAS = [["is", "considered"], ["are", "considered"], ["is", "classified", "as"], ["are", "classified", "as"],
            ["counts", "as"], ["count", "as"], ["qualifies", "as"], ["qualify", "as"], ["is", "regarded", "as"],
            ["are", "regarded", "as"], ["is"], ["are"]]
_PREPS = {"with", "in", "at", "on", "for", "from", "by", "to", "of", "into", "near", "during", "every", "each"}
_SUP_LEAD = [["kind", "of"], ["type", "of"], ["form", "of"], ["sort", "of"], ["also"]]


def verify_isa(link: IsA, toks: list[str]) -> Optional[str]:
    if any(_is_num(t) for t in toks):
        return "is-a sentence with a number"
    if _exception(toks):
        return "exception word"
    for k, t in enumerate(toks):
        cop = next((c for c in _COPULAS if toks[k:k + len(c)] == c), None)
        if cop:
            break
    else:
        return "no copula"
    found, stray = read_modality(toks[:k] + toks[k + len(cop):])
    if found or stray:
        return "modal or negated is-a sentence"
    left, right = [t for t in toks[:k] if t not in _ARTICLES], toks[k + len(cop):]
    while left and left[0] in ("every", "each", "all", "any"):
        left = left[1:]
    has_article = bool(right) and right[0] in _ARTICLES
    right = [t for t in right if t not in _ARTICLES]
    for lead in _SUP_LEAD:
        if right[:len(lead)] == lead:
            right = [t for t in right[len(lead):] if t not in _ARTICLES]
    if not right or len(right) > 4 or any(t in _PREPS or t == "," for t in right):
        return "right side is not a short noun phrase"
    if not has_article and (len(right) > 3 or right[0].endswith(("ed", "ly")) or right[-1].endswith(("ed", "ly"))):
        return "right side is not a short noun phrase"
    sup = tokens(link.sup)
    if len(sup) != len(right) or not all(_same(a, b) for a, b in zip(sup, right)):
        return f"sup '{link.sup}' is not the whole right side"
    members, cur = [], []
    for t in left:
        if t in ("and", "or", ","):
            members.append(cur)
            cur = []
        else:
            cur.append(t)
    members.append(cur)
    sub = tokens(link.sub)
    if not any(len(m) == len(sub) and all(_same(a, b) for a, b in zip(sub, m)) for m in members):
        return f"sub '{link.sub}' is not one of the defined things"
    if [singular(t) for t in sub] == [singular(t) for t in sup]:
        return "sub equals sup"
    return None


_FORWARD = [["due", "to", "fact", "that"], ["because", "of"], ["because"], ["since"], ["due", "to"], ["owing", "to"], ["as", "result", "of"],
            ["thanks", "to"]]
_BACKWARD = [["so", "that"], ["so"], ["therefore"], ["which", "is", "why"]]


def verify_cause(c: Cause, toks: list[str]) -> Optional[str]:
    eff, cau = find_spans(c.effect, toks), find_spans(c.cause, toks)
    if not eff or not cau:
        return "effect or cause is not a contiguous phrase"
    for (es, ee) in eff:
        for (cs, ce) in cau:
            gap = toks[ee:cs] if ee <= cs else None
            if gap is not None and any(gap == w for w in _FORWARD):
                return None                                    # effect BECAUSE cause
            if cs > 0 and ce <= es and any(toks[:cs] == w for w in _FORWARD):
                return None                                    # Because cause, effect
            if ce <= es and any(toks[ce:es] == w for w in _BACKWARD if w != ["so", "that"]):
                return None                                    # cause, so effect
    return "no causal connective between effect and cause"


def verify(ex: Extraction, sentence: str) -> tuple[Extraction, list[str]]:
    toks = tokens(sentence.strip().rstrip("."))
    with_commas = tokens(sentence.strip().rstrip("."), commas=True, articles=True)
    kept, vetoed = Extraction(), []
    for kind, items, check in (("rules", ex.rules, verify_rule), ("facts", ex.facts, verify_fact),
                               ("isa", ex.isa, verify_isa), ("causes", ex.causes, verify_cause)):
        for item in items:
            why = check(item, with_commas if kind == "isa" else toks)
            if why:
                vetoed.append(f"{kind}: {why}")
            else:
                getattr(kept, kind).append(item)
    return kept, vetoed


def drop_indistinguishable(ex: Extraction) -> tuple[Extraction, list[str]]:
    """fact_bridge matches a question to facts by content words longer than two letters, so 'rack in hall B' and
    'rack in hall D' are the same entity to it, and the first fact would answer for both. Drop every fact whose
    entity collides that way with a differently written entity measuring the same metric."""
    groups: dict[tuple, set[str]] = {}
    for f in ex.facts:
        groups.setdefault((f.metric, frozenset(_words(f.entity))), set()).add(" ".join(tokens(f.entity)))
    bad = {k for k, names in groups.items() if len(names) > 1}
    if not bad:
        return ex, []
    keep = [f for f in ex.facts if (f.metric, frozenset(_words(f.entity))) not in bad]
    dropped = [f"facts: entity '{f.entity}' indistinguishable from another :: {f.source}" for f in ex.facts
               if (f.metric, frozenset(_words(f.entity))) in bad]
    return ex.model_copy(update={"facts": keep}), dropped


# ---------------------------------------------------------------- extractors


class LearnedExtractor:
    """flan-t5 proposals, verified per sentence. CPU inference; outputs cached per sentence."""

    def __init__(self, model_dir: str, device: str = "cpu", beams: int = 1, batch: int = 16, max_new_tokens: int = 128):
        import torch
        from fact_bridge.checkpoints import load_seq2seq
        self.torch = torch
        self.tok, self.model = load_seq2seq(model_dir)
        self.model = self.model.to(device).eval()
        self.device, self.beams, self.batch, self.max_new = device, beams, batch, max_new_tokens
        self.cache: dict[str, tuple[Extraction, list[str], str]] = {}
        self.stats = {"sentences": 0, "seconds": 0.0, "proposed": 0, "vetoed": 0, "veto_reasons": Counter()}

    def generate(self, sentences: list[str]) -> list[str]:
        outs = []
        for k in range(0, len(sentences), self.batch):
            part = sentences[k:k + self.batch]
            enc = self.tok([PROMPT + normalize_amounts(s.strip()) for s in part], return_tensors="pt",
                           padding=True, truncation=True, max_length=192).to(self.device)
            with self.torch.no_grad():
                ids = self.model.generate(**enc, max_new_tokens=self.max_new, num_beams=self.beams, do_sample=False)
            outs += self.tok.batch_decode(ids, skip_special_tokens=True)
        return outs

    def _fill(self, sentences: list[str]) -> None:
        todo = list(dict.fromkeys(s.strip() for s in sentences if s.strip() not in self.cache))
        if not todo:
            return
        t0 = time.time()
        raw = self.generate(todo)
        self.stats["seconds"] += time.time() - t0
        self.stats["sentences"] += len(todo)
        for s, text in zip(todo, raw):
            proposed, bad = parse(text, s)
            kept, vetoed = proposed, list(bad)
            n = sum(len(getattr(proposed, k)) for k in ("rules", "facts", "isa", "causes")) + len(bad)
            self.stats["proposed"] += n
            self.stats["vetoed"] += len(vetoed)
            for v in vetoed:
                self.stats["veto_reasons"][re.sub(r"'[^']*'|\d+(?:\.\d+)?", "_", v)] += 1
            self.cache[s] = (kept, vetoed, text)

    def extract(self, sentences: list[str]) -> Extraction:
        self._fill(sentences)
        out = Extraction()
        for s in sentences:
            kept = self.cache[s.strip()][0]
            for kind in ("rules", "facts", "isa", "causes"):
                # keep the caller's exact sentence as source so ground() recognizes it
                getattr(out, kind).extend(i.model_copy(update={"source": s}) for i in getattr(kept, kind))
        out, dropped = drop_indistinguishable(out)
        self.stats["collisions"] = self.stats.get("collisions", 0) + len(dropped)
        return out

    def explain(self, sentence: str) -> dict:
        self._fill([sentence])
        kept, vetoed, raw = self.cache[sentence.strip()]
        return {"raw": raw, "kept": kept, "vetoed": vetoed}


class HybridExtractor:
    """Union of PatternExtractor and the learned extractor, conflicts resolved toward the regex.

    * every regex item is kept (removing one rule of a conflicting pair would turn CONTESTED into a confident
      answer), except facts dropped by the entity-collision guard, which only ever removes facts
    * a learned rule is added unless a regex rule from the same sentence names the same category and object
      (a duplicate, or a disagreement, which the regex wins)
    * a learned fact is added unless a regex fact from the same sentence has the same entity and metric
    * learned is-a links are added when new; a learned cause only for a sentence the regex read no cause from
    """

    def __init__(self, learned: LearnedExtractor, pattern: Optional[PatternExtractor] = None):
        self.learned = learned
        self.pattern = pattern or PatternExtractor()

    def extract(self, sentences: list[str]) -> Extraction:
        regex = self.pattern.extract(sentences)
        learned = self.learned.extract(sentences)
        out = regex.model_copy(deep=True)
        rkey = {(r.source, singular(r.category), r.object.lower()) for r in regex.rules}
        out.rules += [r for r in learned.rules if (r.source, r.category, r.object) not in rkey]
        fkey = {(f.source, " ".join(tokens(f.entity)), f.metric) for f in regex.facts}
        out.facts += [f for f in learned.facts if (f.source, " ".join(tokens(f.entity)), f.metric) not in fkey]
        ikey = {(i.source, singular(i.sub).lower(), singular(i.sup).lower()) for i in regex.isa}
        out.isa += [i for i in learned.isa if (i.source, singular(i.sub).lower(), singular(i.sup).lower()) not in ikey]
        have = {c.source for c in regex.causes}
        out.causes += [c for c in learned.causes if c.source not in have]
        out, _ = drop_indistinguishable(out)
        return out
