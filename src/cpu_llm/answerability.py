"""Bind a question to sentences that state the relation it asks for.

Retrieval can return a neighbor, and a later audit can confirm that a
sentence matches its stored proposition. Neither of those establishes that
the sentence answers the question. This module handles a declared set of
question shapes. A ranking question, a sum, a rule, and an event-frame
question stay with their own producers.

Nothing here is filled in from outside the sentences the caller supplies.
"""

from __future__ import annotations

import contextvars
import re
from contextlib import contextmanager
from typing import Any

from cpu_llm.ranking import ranking_question

_UNSETTLED = "The retrieved passages do not settle that."
_CHOSEN_CLASS: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "cpu_llm_chosen_class", default=None
)
_NONE = "No passage was retrieved."
_WHAT = re.compile(
    r"^(?P<kind>what|who)\s+(?P<copula>is|are|was|were)\s+(?P<rest>.+?)\s*\??$",
    re.IGNORECASE,
)
_WHICH = re.compile(
    r"^which\s+(?P<head>[a-z][a-z ]{0,40}?)\s+is\s+the\s+(?P<attr>[a-z][a-z ]{0,40}?)\s+of\s+(?P<entity>.+?)\s*\??$",
    re.IGNORECASE,
)
_ATTR_OF = re.compile(
    r"^(?:(?P<head>[a-z][a-z ]{0,40}?)\s+is\s+)?the\s+(?P<attr>[a-z][a-z ]{0,40}?)\s+of\s+(?P<entity>.+)$",
    re.IGNORECASE,
)
_ATTR_POSS = re.compile(
    r"^(?P<entity>.+?)'s\s+(?P<attr>[a-z][a-z ]{0,40})$",
    re.IGNORECASE,
)
_SOURCES = re.compile(
    r"^(?:cite\s+)?sources?\s+for\s+(?P<rest>.+?)\s*\??$",
    re.IGNORECASE,
)
_DOES = re.compile(
    r"^(?P<wh>what|where)\s+does\s+(?P<subject>.+?)\s+(?P<verb>[a-z]+)\s*\??$",
    re.IGNORECASE,
)
_WEIGHT = re.compile(
    r"^how\s+much\s+does\s+(?P<subject>.+?)\s+weigh\s*\??$",
    re.IGNORECASE,
)
_WEIGHT_WORD = re.compile(r"\b(?:weighs?|weight|kilograms?|grams?|pounds?|ounces?)\b", re.IGNORECASE)
_NEGATED = re.compile(r"\b(?:not|never|no|n't)\b", re.IGNORECASE)
_CONDITIONAL = re.compile(r"\bif\b", re.IGNORECASE)
_DETERMINER = re.compile(r"^(?:the|a|an)\s+", re.IGNORECASE)
_ABBREVIATION = re.compile(
    r"\b(?:No|Mr|Mrs|Ms|Dr|St|Jr|Sr|vs|etc|Fig|Prof|Gen|Col|Capt|Lt|Sgt|Mt)\.$|\b[A-Z]\.$"
)


def parse_query(message: str) -> dict[str, str] | None:
    """The supported shape of ``message``, or None when this module does not own it."""
    if ranking_question(message):
        return None
    text = " ".join((message or "").strip().split())
    if not text:
        return None
    activity = re.fullmatch(r'what (?:did|does|do) (.+?) do\s*\??', text, re.I)
    if activity:
        return dict(kind='activity', subject=_subject_phrase(activity[1]), raw=text,
                    tense='past' if re.match(r'what did\b', text, re.I) else 'present')
    does = _DOES.match(text)
    if does:
        subject = _subject_phrase(does.group("subject"))
        verb = does.group("verb").casefold()
        if subject and verb:
            return {
                "kind": "relation",
                "subject": subject,
                "verb": verb,
                "relation": "location" if does.group("wh").casefold() == "where" else "action",
                "raw": text,
            }
    weight = _WEIGHT.match(text)
    if weight:
        subject = _subject_phrase(weight.group("subject"))
        if subject:
            return {"kind": "weight", "subject": subject, "raw": text}
    sources = _SOURCES.match(text)
    if sources:
        subject = _subject_phrase(sources.group("rest"))
        if not subject:
            return None
        return {"kind": "sources", "subject": subject, "raw": text}
    which = _WHICH.match(text)
    if which:
        return {
            "kind": "attribute",
            "attribute": _phrase(which.group("attr")),
            "entity": _phrase(which.group("entity")),
            "tense": "present",
            "raw": text,
        }
    matched = _WHAT.match(text)
    if matched is None:
        return None
    rest = _phrase(matched.group("rest"))
    tense = "past" if matched.group("copula").casefold() in {"was", "were"} else "present"
    if not re.search(r"[A-Za-z]", rest):
        return None
    possessive = _ATTR_POSS.match(rest)
    if possessive:
        return {
            "kind": "attribute",
            "attribute": _phrase(possessive.group("attr")),
            "entity": _phrase(possessive.group("entity")),
            "tense": tense,
            "raw": text,
        }
    attribute = _ATTR_OF.match(rest)
    if attribute:
        return {
            "kind": "attribute",
            "attribute": _phrase(attribute.group("attr")),
            "entity": _phrase(attribute.group("entity")),
            "tense": tense,
            "raw": text,
        }
    return {"kind": "definition", "subject": _subject_phrase(rest), "tense": tense, "raw": text}


@contextmanager
def chosen_class(value: str | None):
    """The class the user already picked, visible to assessment during this turn."""
    token = _CHOSEN_CLASS.set(value or None)
    try:
        yield
    finally:
        _CHOSEN_CLASS.reset(token)


def chosen_class_label() -> str | None:
    """The class selected earlier in this turn, if the user already picked one."""
    label = _CHOSEN_CLASS.get()
    return label.strip() if isinstance(label, str) and label.strip() else None


def _constrain_channel_class(message: str, chunks: list[Any], channel_answer: dict[str, Any]) -> dict[str, Any] | None:
    """Keep a selected class, or ask when two classes are still open.

    ``None`` means the channel answer can stand. A chosen class that is not in
    the rows is insufficient. It is not a license to quote the other class.
    """
    requested = (channel_answer.get("prompt_intent") or {}).get("requested") or {}
    if requested.get("relation") != "is_a":
        return None
    rows = [_row(chunk, index) for index, chunk in enumerate(chunks)]
    rows = [row for row in rows if row["text"]]
    subject = str(requested.get("entity") or "")
    chosen = chosen_class_label()
    if chosen:
        sentence = _class_sentence(subject, chosen, rows)
        if sentence is None:
            return {
                **channel_answer,
                "answer_status": "insufficient_evidence",
                "reason": "chosen_class_missing",
                "text": _UNSETTLED,
                "answer_evidence": [],
            }
        return {
            **channel_answer,
            "answer_status": "answered",
            "reason": "chosen_class",
            "text": sentence["span"],
            "answer_evidence": [sentence],
        }
    # A taxonomic definition of this entity, including a sentence under one of
    # its names, is the definition. A species sentence about something else
    # does not close a real choice between this entity's classes.
    if _relevant_species_definition(subject, rows):
        return None
    classes = _unlinked_classes(subject, rows)
    if len(classes) < 2:
        return None
    from cpu_llm.clarification import _sense_text

    senses = [{"words": label.split()} for label in classes]
    return {
        **channel_answer,
        "answer_status": "needs_clarification",
        "reason": "unlinked_classes",
        "classes": list(classes),
        "text": _sense_text(senses),
        "answer_evidence": [],
    }


def assess(message: str, chunks: list[Any], *, intent=None) -> dict[str, Any] | None:
    """Whether the supplied sentences state the asked relation.

    ``None`` means the question is outside this contract. ``answered`` means
    the sentences state one value. It does not mean a later audit ran, and it
    does not mean the source is true.
    """
    from cpu_llm.prompt_intent import select_channel_answer
    channel_answer = select_channel_answer(message, chunks, intent=intent)
    if channel_answer is not None:
        # "What kind" is settled by the selector. Apply the selected class
        # before that answer is returned, or the first stored class is spoken.
        constrained = _constrain_channel_class(message, chunks, channel_answer)
        if constrained is not None:
            return constrained
        return channel_answer
    plan = parse_query(message)
    if plan is None:
        return None
    rows = [_row(chunk, index) for index, chunk in enumerate(chunks)]
    rows = [row for row in rows if row["text"]]
    retrieved = [{"document_id": row["document_id"], "span": row["text"]} for row in rows]
    base = {
        "query": plan["raw"],
        "kind": plan["kind"],
        "retrieved_candidates": retrieved,
        "answer_evidence": [],
        "verification_scope": "query",
    }
    if not rows:
        return {
            **base,
            "answer_status": "insufficient_evidence",
            "reason": "none_retrieved",
            "text": _NONE,
        }
    if plan["kind"] == "attribute":
        return {**base, **_attribute_decision(plan, rows)}
    if plan["kind"] in {"relation", "weight"}:
        bindings = _relation_bindings(plan, rows)
        if not bindings:
            return {
                **base,
                "answer_status": "insufficient_evidence",
                "reason": "no_binding",
                "text": _UNSETTLED,
            }
        sentences = _unique([item["span"] for item in bindings])
        return {
            **base,
            "answer_status": "answered",
            "reason": "relation_stated",
            "text": " ".join(sentences),
            "answer_evidence": bindings,
        }
    if plan["kind"] == "definition":
        classes = _unlinked_classes(plan.get("subject") or "", rows)
        chosen = _CHOSEN_CLASS.get()
        if chosen:
            # The selected meaning stays selected. Another class that happens
            # to be in the shortlist is not a substitute for it.
            sentence = _class_sentence(plan.get("subject") or "", chosen, rows)
            if sentence is not None:
                return {
                    **base,
                    "answer_status": "answered",
                    "reason": "chosen_class",
                    "text": sentence["span"],
                    "answer_evidence": [sentence],
                }
            return {
                **base,
                "answer_status": "insufficient_evidence",
                "reason": "chosen_class_missing",
                "text": _UNSETTLED,
            }
        if len(classes) >= 2:
            from cpu_llm.clarification import _sense_text

            senses = [{"words": label.split()} for label in classes]
            return {
                **base,
                "answer_status": "needs_clarification",
                "reason": "unlinked_classes",
                "classes": list(classes),
                "text": _sense_text(senses),
            }
    bindings = _subject_bindings(plan, rows)
    if not bindings:
        return {
            **base,
            "answer_status": "insufficient_evidence",
            "reason": "no_binding",
            "text": _UNSETTLED,
        }
    sentences = _unique([item["span"] for item in bindings])
    return {
        **base,
        "answer_status": "answered",
        "reason": "subject_stated",
        "text": " ".join(sentences),
        "answer_evidence": bindings,
    }


def eligible_hits(message: str, hits: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Hits that state the asked relation.

    ``None`` leaves the caller on its previous selection. An empty list means
    this question was recognized and none of the hits state it.
    """
    plan = parse_query(message)
    if plan is None:
        return None
    kept: list[dict[str, Any]] = []
    for hit in hits:
        text = str(hit.get("chunk_text") or hit.get("text") or "")
        if _text_binds(plan, text):
            kept.append(hit)
    return kept


def supporting_ids(message: str, hits: list[dict[str, Any]]) -> list[str] | None:
    """Document ids that state the asked subject or relation, in retrieval order.

    ``None`` means this module does not own the question. An empty list means
    it does, and none of the hits support it.
    """
    chosen = eligible_hits(message, hits)
    if chosen is None:
        return None
    ids: list[str] = []
    for hit in chosen:
        document_id = str(hit.get("document_id") or hit.get("chunk_id") or "")
        if document_id and document_id not in ids:
            ids.append(document_id)
    return ids


def supported_answer(message: str, answer: str) -> str | None:
    """The part of an audited answer that stays on the asked subject.

    A pronoun sentence stays only while the previous kept sentence is still
    about that subject. A sentence about something else is left out.
    """
    plan = parse_query(message)
    if plan is None:
        return None
    kept: list[str] = []
    armed = False
    for sentence in _sentences(answer or ""):
        if _text_binds(plan, sentence):
            kept.append(sentence)
            armed = True
            continue
        if armed and re.match(r"^(?:it|they|he|she|this|that)\b", sentence, re.IGNORECASE):
            kept.append(sentence)
            continue
        armed = False
    if not kept:
        return None
    return " ".join(kept)


def _attribute_decision(plan: dict[str, str], rows: list[dict[str, str]]) -> dict[str, Any]:
    found: list[dict[str, str]] = []
    for row in rows:
        for sentence in _sentences(row["text"]):
            value = _attribute_value(plan, sentence)
            if value is None:
                continue
            found.append({"document_id": row["document_id"], "span": sentence, "value": value})
    if not found:
        return {
            "answer_status": "insufficient_evidence",
            "reason": "no_binding",
            "text": _UNSETTLED,
        }
    by_value: dict[str, list[dict[str, str]]] = {}
    for item in found:
        by_value.setdefault(item["value"].casefold(), []).append(item)
    if len(by_value) > 1:
        spans = _unique([item["span"] for item in found])
        spans = sorted(spans, key=str.casefold)
        quoted = " ".join(f'"{span}"' for span in spans)
        return {
            "answer_status": "conflicting",
            "reason": "distinct_values",
            "text": f"{_UNSETTLED} Stored sentences conflict: {quoted}",
            "answer_evidence": [
                {"document_id": item["document_id"], "span": item["span"]}
                for item in sorted(found, key=lambda item: item["span"].casefold())
            ],
        }
    evidence = [{"document_id": item["document_id"], "span": item["span"]} for item in found]
    return {
        "answer_status": "answered",
        "reason": "relation_stated",
        "text": found[0]["span"],
        "answer_evidence": evidence,
    }


def _relevant_species_definition(subject: str, rows: list[dict[str, str]]) -> bool:
    """True when a species sentence is about the asked entity, not a neighbor.

    Identity includes an explicit alias. An unrelated "species of" row in the
    same shortlist is not this entity's taxonomy.
    """
    from cpu_llm.knowledge_graph import extract_facts
    from cpu_llm.prompt_intent import _alias_paths, _entity_key

    facts = []
    for row in rows:
        facts.extend(extract_facts(row["document_id"], row["text"]))
    names = set(_alias_paths(subject, facts))
    for fact in facts:
        if fact.relation != "is_a" or "is a species of" not in fact.sentence.casefold():
            continue
        if _entity_key(fact.subject) in names:
            return True
    return False


def _class_sentence(subject: str, label: str | None, rows: list[dict[str, str]]) -> dict[str, str] | None:
    if not label:
        return None
    from cpu_llm.knowledge_graph import extract_facts
    from cpu_llm.prompt_intent import _entity_key

    want_subject, want_object = _entity_key(subject), _entity_key(label)
    for row in rows:
        for fact in extract_facts(row["document_id"], row["text"]):
            if fact.relation != "is_a":
                continue
            if _entity_key(fact.subject) == want_subject and _entity_key(fact.object) == want_object:
                return {"document_id": row["document_id"], "span": fact.sentence}
    return None


def _unlinked_classes(subject: str, rows: list[dict[str, str]]) -> list[str]:
    """Class names stored for ``subject`` that no source is_a edge links.

    One class is a definition. Two classes with no source saying one is the
    other are a choice, not a license to quote only the first.
    """
    from cpu_llm.knowledge_graph import extract_facts
    from cpu_llm.prompt_intent import _entity_key

    key = _entity_key(subject)
    labels: list[str] = []
    keys: list[str] = []
    links: set[tuple[str, str]] = set()
    for row in rows:
        for fact in extract_facts(row["document_id"], row["text"]):
            if fact.relation != "is_a":
                continue
            subject_key, object_key = _entity_key(fact.subject), _entity_key(fact.object)
            links.add((subject_key, object_key))
            if subject_key != key or object_key in keys:
                continue
            keys.append(object_key)
            labels.append(fact.object.strip())
    if len(keys) < 2:
        return []
    shown: list[str] = []
    for index, left in enumerate(keys):
        for right_index, right in enumerate(keys[index + 1:], start=index + 1):
            if (left, right) in links or (right, left) in links:
                continue
            if labels[index] not in shown:
                shown.append(labels[index])
            if labels[right_index] not in shown:
                shown.append(labels[right_index])
    return shown


def _subject_bindings(plan: dict[str, str], rows: list[dict[str, str]]) -> list[dict[str, str]]:
    subject = plan.get("subject") or ""
    bindings: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        for sentence in _sentences(row["text"]):
            if not _subject_sentence(subject, sentence):
                continue
            if plan['kind'] == 'activity' and not _activity_sentence(subject, sentence, tense=plan['tense']):
                continue
            key = (row["document_id"], sentence)
            if key in seen:
                continue
            seen.add(key)
            bindings.append({"document_id": row["document_id"], "span": sentence})
    if plan["kind"] == "definition":
        definitions = [item for item in bindings if _definition_sentence(plan, item["span"])]
        # "What is X?" and "What was X?" take one type or role copula.
        # A place or a bare color does not count, and neither does every
        # other sentence that happens to name the subject.
        kinds = [item for item in definitions if _kind_sentence(item["span"])]
        plain = [item for item in kinds if "," not in item["span"]]
        if plain:
            return plain[:1]
        if kinds:
            return kinds[:1]
        # A definition is a positive obligation. Neither mentioning the
        # subject nor an arbitrary copula licenses a type/role answer.
        # Keep unfamiliar forms unsupported by evidence rather than falling
        # back to all of the subject's events or attributes.
        return []
    return bindings


def _activity_sentence(subject: str, sentence: str, *, tense: str) -> bool:
    """A bounded affirmative main-clause action, quoted without role inference."""
    prefix = rf'^(?:(?:the|a|an)\s+)?{re.escape(_subject_phrase(subject))}\s+'
    tail = re.sub(prefix, '', sentence, count=1, flags=re.I)
    if tail == sentence or re.search(r"\b(?:not|never|no|if|unless|may|might|could|would|should)\b|n't", tail, re.I):
        return False
    verb = re.match(r'([A-Za-z]+)\s+\S', tail)
    if not verb:
        return False
    word = verb[1].casefold()
    if word in {'is', 'are', 'was', 'were', 'has', 'have', 'had', 'known'}:
        return False
    if tense == 'past':
        return word.endswith('ed') or word in {'ate', 'made', 'built', 'taught', 'wrote', 'ran', 'sang', 'went', 'bought', 'sold', 'took', 'gave'}
    return word.endswith('s')


def _relation_bindings(plan: dict[str, str], rows: list[dict[str, str]]) -> list[dict[str, str]]:
    bindings: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        for sentence in _sentences(row["text"]):
            if not _relation_sentence(plan, sentence):
                continue
            key = (row["document_id"], sentence)
            if key in seen:
                continue
            seen.add(key)
            bindings.append({"document_id": row["document_id"], "span": sentence})
    return bindings


def _relation_sentence(plan: dict[str, str], sentence: str) -> bool:
    """The asked predicate belongs to this subject in the main clause.

    A verb inside "that nests" or "watches a heron eat" is another clause's
    predicate. It does not answer the question about the outer subject.
    """
    subject = plan.get("subject") or ""
    if not _subject_sentence(subject, sentence):
        return False
    if plan["kind"] == "weight":
        return _direct_weight(subject, sentence)
    if plan.get("relation") == "location" and plan.get("verb") == "live":
        # A named species' definition may state its range without "lives in".
        # Require the explicit subject/alias and a geographic range clause.
        if _definition_sentence({"subject": subject}, sentence) and re.search(
            r"\b(?:species|animal|bird|mammal|fish|lobster)\b.*\bfrom\s+", sentence, re.IGNORECASE
        ):
            return True
    forms = _verb_forms(plan.get("verb") or "")
    if not forms:
        return False
    return _direct_predicate(subject, sentence, forms, location=plan.get("relation") == "location")


_PREDICATE_ADVERB = r"(?:always|often|usually|also|still)\s+"


def _direct_predicate(subject: str, sentence: str, forms: set[str], *, location: bool) -> bool:
    phrase = _subject_phrase(subject)
    if not phrase or not forms:
        return False
    verb = "|".join(re.escape(form) for form in sorted(forms))
    tail = (r"\s+(?:in|on|at|under|above|below|near|inside|outside|within|beside|behind|beneath|over|across)\b"
            if location else r"\b")
    pattern = (
        rf"^(?:(?:the|a|an)\s+)?{re.escape(phrase)}\s+(?:{_PREDICATE_ADVERB})?(?:{verb}){tail}"
    )
    return re.match(pattern, " ".join(sentence.split()), re.IGNORECASE) is not None


def _direct_weight(subject: str, sentence: str) -> bool:
    phrase = _subject_phrase(subject)
    if not phrase:
        return False
    folded = " ".join(sentence.split())
    patterns = (
        rf"^(?:(?:the|a|an)\s+)?{re.escape(phrase)}\s+(?:{_PREDICATE_ADVERB})?(?:weighs|weighed)\b",
        rf"^(?:(?:the|a|an)\s+)?{re.escape(phrase)}'s\s+weight\s+is\b",
        rf"^the\s+weight\s+of\s+(?:(?:the|a|an)\s+)?{re.escape(phrase)}\s+is\b",
    )
    return any(re.match(pattern, folded, re.IGNORECASE) for pattern in patterns)


def _verb_forms(verb: str) -> set[str]:
    from cpu_llm.realizer.inflect import surface_tokens

    lemma = verb.casefold()
    if lemma.endswith("s") and not lemma.endswith("ss") and lemma[:-1]:
        lemma = lemma[:-1]
    return surface_tokens(lemma) | {verb.casefold()}


def _text_binds(plan: dict[str, str], text: str) -> bool:
    if plan['kind'] == 'activity':
        return any(_activity_sentence(plan['subject'], sentence, tense=plan['tense']) for sentence in _sentences(text))
    if plan["kind"] == "attribute":
        return any(_attribute_value(plan, sentence) is not None for sentence in _sentences(text))
    if plan["kind"] in {"relation", "weight"}:
        return any(_relation_sentence(plan, sentence) for sentence in _sentences(text))
    subject = plan.get("subject") or ""
    return any(_subject_sentence(subject, sentence) for sentence in _sentences(text))


def _attribute_value(plan: dict[str, str], sentence: str) -> str | None:
    if _NEGATED.search(sentence) or _CONDITIONAL.search(sentence):
        return None
    attribute = re.escape(plan["attribute"].casefold())
    entity = re.escape(plan["entity"].casefold())
    copula = "was" if plan.get("tense") == "past" else "is"
    folded = " ".join(sentence.split())
    patterns = (
        rf"\bthe {attribute} of {entity} {copula} (?P<value>[^.?!]+)",
        rf"\b{entity}'s {attribute} {copula} (?P<value>[^.?!]+)",
        rf"^(?P<value>.+?) {copula} the {attribute} of {entity}[.?!]?$",
    )
    for pattern in patterns:
        matched = re.search(pattern, folded, re.IGNORECASE)
        if matched is None:
            continue
        value = matched.group("value").strip(" .")
        if value:
            return value
    return None


def _subject_sentence(subject: str, sentence: str) -> bool:
    phrase = _subject_phrase(subject)
    if not phrase or _NEGATED.search(sentence) or _CONDITIONAL.search(sentence):
        return False
    if not _complete_phrase(sentence, phrase):
        return False
    folded = sentence.casefold()
    known = re.search(r"\bknown as\b", folded)
    if known and _complete_phrase(sentence[known.start() :], phrase):
        return True
    if re.search(rf"\b(?:is|are)\s+(?:(?:the|a|an)\s+)?{re.escape(phrase)}[.!?]?$", sentence, re.IGNORECASE):
        return True
    return re.match(rf"^(?:(?:the|a|an)\s+)?{re.escape(phrase)}\b", folded, re.IGNORECASE) is not None


def _kind_sentence(sentence: str) -> bool:
    """A taxonomic "is a" sentence, not a place or a one-word predicate."""
    from cpu_llm.semantic import discharges_type

    return discharges_type(sentence)


def _definition_sentence(plan: dict[str, str], sentence: str) -> bool:
    phrase = re.escape(_subject_phrase(plan.get("subject") or ""))
    copula = r"(?:was|were)" if plan.get("tense") == "past" else r"(?:is|are)"
    return bool(re.match(
        rf"^(?:(?:the|a|an)\s+)?{phrase}(?:,\s*[^,]+,)?\s+{copula}\b", sentence, re.IGNORECASE
    ) or re.search(r"\bknown as\b", sentence, re.IGNORECASE)
        or re.search(rf"\b{copula}\s+(?:(?:the|a|an)\s+)?{phrase}[.!?]?$", sentence, re.IGNORECASE))


def _complete_phrase(text: str, phrase: str) -> bool:
    matched = re.search(rf"\b{re.escape(phrase)}\b", text, re.IGNORECASE)
    if matched is None:
        return False
    nxt = re.match(r"\s+([A-Za-z][A-Za-z'-]*)", text[matched.end() :])
    return not (nxt is not None and nxt.group(1)[:1].isupper())


def _row(chunk: Any, index: int) -> dict[str, str]:
    if isinstance(chunk, str):
        return {"document_id": f"chunk-{index}", "text": chunk.strip()}
    text = str(chunk.get("text") or chunk.get("chunk_text") or "").strip()
    document_id = str(chunk.get("document_id") or chunk.get("chunk_id") or f"chunk-{index}")
    return {"document_id": document_id, "text": text}


def _phrase(text: str) -> str:
    return " ".join((text or "").strip().strip(" ?.!").split())


def _subject_phrase(text: str) -> str:
    return _DETERMINER.sub("", _phrase(text)).strip()


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences: list[str] = []
    buffer = ""
    for part in parts:
        buffer = f"{buffer} {part}".strip() if buffer else part
        if _ABBREVIATION.search(buffer) is None:
            sentences.append(buffer)
            buffer = ""
    if buffer:
        sentences.append(buffer)
    return [sentence for sentence in sentences if sentence]
