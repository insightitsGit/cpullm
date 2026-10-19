"""Legal clauses for the records a turn already holds.

Each record yields at most one derivation. The grammar does not invent a
second construction, and it does not take a word from a different record.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import replace

from cpu_llm.clauses import _first_sentence, proposition_from_chunk
from cpu_llm.ir.schema import EIRProposition, EdgeType
from cpu_llm.memory.frames import frame_from_chunk, resolve_frames
from cpu_llm.realizer.evidence_schema import Action, Bundle, Derivation, Plan, Record, Span
from cpu_llm.realizer.inflect import forms
from cpu_llm.realizer.surface import SemanticSurfaceRealizer, _ordered_ids

_REALIZER = SemanticSurfaceRealizer()
_WORD = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")
_FRAME_ALLOWED = {
    "past_color": ("patient", "agent", "predicate", "color"),
    "past_location": ("agent", "predicate", "patient", "location"),
    "past_agent": ("agent", "predicate", "patient"),
}
_FRAME_REQUIRED = {
    "past_color": ("patient", "predicate", "color"),
    "past_location": ("agent", "predicate", "patient", "location"),
    "past_agent": ("agent", "predicate", "patient"),
}


def bundle_from_chunks(
    chunks: list[tuple[str, str]],
    *,
    attributes: dict[str, dict] | None = None,
    math_result: dict | None = None,
    causal_edges: list | None = None,
) -> Bundle:
    """One record per authorized object on the shortlist."""
    attributes = attributes or {}
    records: list[Record] = []
    for document_id, text in chunks:
        records.extend(_chunk_records(document_id, text, attributes.get(document_id) or {}))
    math = _math_record(math_result or {})
    if math is not None:
        records.append(math)
    passages = tuple(text for _document_id, text in chunks if text.strip())
    return Bundle(
        records=tuple(records),
        causal_edges=tuple(_causal_pairs(causal_edges or [])),
        passages=passages,
    )


def plan_for(bundle: Bundle, question: str, *, account: bool = False) -> Plan:
    """Choose which records the question licenses. Scores are not consulted."""
    frame_plan = _frame_plan(bundle, question)
    if account:
        return _account_plan(bundle, question, frame_plan)
    if frame_plan is not None:
        return frame_plan
    if _math_licensed(question, bundle):
        return _ids_plan(bundle, question, "question", [item.record_id for item in bundle.records if item.kind == "math"])
    return _ids_plan(
        bundle,
        question,
        "question",
        _proposition_ids(bundle),
        empty="No verified epistemic evidence available.",
    )


def attach_ranking(bundle: Bundle, plan: Plan, question: str, spoken: str) -> tuple[Bundle, Plan, Derivation] | None:
    """License the ranking clause. The ranker is not asked to invent one.

    A stored sentence that names the order is copied. Otherwise the grammar
    emits the fixed sentence that says the passages do not state a ranking.
    """
    from cpu_llm.ranking import ranking_notice

    texts = list(bundle.passages) or [
        record.source for record in bundle.records if record.kind in {"proposition", "quote", "frame"} and record.source
    ]
    notice = ranking_notice(question, texts, spoken=spoken)
    if notice is None:
        return None
    record_id = "ranking-turn"
    if notice["status"] == "stated" and notice["sentences"] and notice["text"] == " ".join(notice["sentences"]):
        record, derivation = _copied_ranking(record_id, notice["sentences"])
    else:
        record, derivation = _grammar_ranking(record_id, f"Ranking: {notice['text']}")
    if derivation is None:
        return None
    return (
        replace(bundle, records=bundle.records + (record,)),
        replace(plan, record_ids=plan.record_ids + (record_id,)),
        derivation,
    )


def derivations_for(bundle: Bundle, plan: Plan) -> list[list[Derivation]]:
    """One group per licensed record. A group is empty when that record cannot speak."""
    if plan.status != "answered":
        return []
    groups: list[list[Derivation]] = []
    previous_proposition = ""
    for record_id in plan.record_ids:
        record = bundle.record(record_id)
        if record is None:
            continue
        built = _derivation(bundle, plan, record, previous_proposition)
        if record.kind == "proposition" and record.proposition is not None:
            previous_proposition = record.proposition.proposition_id
        if built is not None:
            groups.append([built])
    return groups


def _chunk_records(document_id: str, text: str, attributes: dict) -> list[Record]:
    found: list[Record] = []
    proposition = _proposition(document_id, text, attributes)
    frame = _frame(document_id, text, attributes)
    if proposition is not None:
        record_id = f"prop-{document_id}"
        source = _first_sentence(text) or text.strip()
        spans = _proposition_spans(record_id, source, proposition)
        if spans is not None:
            found.append(
                Record(
                    record_id=record_id,
                    kind="proposition",
                    document_id=document_id,
                    source=source,
                    spans=spans,
                    proposition=proposition,
                    lemma=proposition.predicate.lemma,
                    tense=proposition.predicate.tense,
                )
            )
    elif frame is None:
        quote = _quote_record(document_id, text)
        if quote is not None:
            found.append(quote)
    if frame is not None:
        found.append(_frame_record(document_id, frame))
    hands = _hand_words(attributes.get("relation_hands"))
    if hands:
        found.append(_word_edge_record(document_id, hands))
    for category in _categories(attributes.get("taxonomy_tags")):
        found.append(_tag_record(document_id, category))
    return found


def _proposition(document_id: str, text: str, attributes: dict) -> EIRProposition | None:
    raw = attributes.get("proposition")
    if isinstance(raw, EIRProposition):
        return raw
    if isinstance(raw, dict):
        return EIRProposition.model_validate(raw)
    return proposition_from_chunk(document_id, text)


def _frame(document_id: str, text: str, attributes: dict) -> dict | None:
    raw = attributes.get("event_frame")
    if isinstance(raw, dict) and raw.get("schema") == "stage1-v2":
        return raw
    return frame_from_chunk(document_id, text)


def _proposition_spans(record_id: str, source: str, proposition: EIRProposition) -> tuple[Span, ...] | None:
    subject = proposition.subject.raw_text
    obj = proposition.object_target.raw_text if proposition.object_target is not None else ""
    subject_at = _locate(source, subject, 0)
    if subject_at is None or not obj:
        return None
    object_at = _locate(source, obj, subject_at[1])
    if object_at is None:
        return None
    verb_at = _verb_at(source, proposition.predicate.lemma, subject_at[1], object_at[0])
    if verb_at is None:
        return None
    return (
        _span(record_id, "subject", source, subject_at),
        _span(record_id, "predicate", source, verb_at),
        _span(record_id, "object", source, object_at),
    )


def _verb_at(source: str, lemma: str, start: int, end: int) -> tuple[int, int] | None:
    window = source[start:end]
    for form in forms(lemma).values():
        found = _locate(window, form, 0)
        if found is not None:
            return start + found[0], start + found[1]
    return None


def _quote_record(document_id: str, text: str) -> Record | None:
    sentence = _first_sentence(text).strip()
    if not sentence:
        return None
    record_id = f"quote-{document_id}"
    span = Span(f"{record_id}:sentence:0:{len(sentence)}", record_id, "sentence", sentence, 0, len(sentence))
    return Record(record_id, "quote", document_id, sentence, (span,))


def _frame_record(document_id: str, frame: dict) -> Record:
    record_id = f"frame-{document_id}"
    source = str(frame.get("sentence") or "")
    spans = []
    for role in ("agent", "predicate", "patient", "color", "location", "time", "subject", "object"):
        raw = frame.get(role)
        if not isinstance(raw, dict) or "text" not in raw:
            continue
        start = int(raw["start"])
        end = int(raw["end"])
        spans.append(Span(f"{record_id}:{role}:{start}:{end}", record_id, role, str(raw["text"]), start, end))
    predicate = frame.get("predicate") or {}
    return Record(
        record_id=record_id,
        kind="frame",
        document_id=document_id,
        source=source,
        spans=tuple(spans),
        frame=frame,
        lemma=str(predicate.get("lemma") or ""),
        tense=str(predicate.get("tense") or ""),
    )


def _word_edge_record(document_id: str, words: list[str]) -> Record:
    sentence = "These words share a stored word-edge: " + ", ".join(words) + "."
    record_id = f"hands-{document_id}"
    spans = []
    cursor = sentence.index(": ") + 2
    for word in words:
        found = _locate(sentence, word, cursor)
        if found is None:
            continue
        spans.append(_span(record_id, "hand", sentence, found))
        cursor = found[1]
    return Record(record_id, "word_edge", document_id, sentence, tuple(spans))


def _tag_record(document_id: str, category: str) -> Record:
    sentence = f"Stored tag: {category}."
    record_id = f"tag-{document_id}-{category}"
    found = _locate(sentence, category, 0)
    spans = () if found is None else (_span(record_id, "category", sentence, found),)
    return Record(record_id, "tag", document_id, sentence, spans)


def _math_record(result: dict) -> Record | None:
    if result.get("ok") is not True:
        return None
    expression = str(result.get("expression") or "")
    value = str(result.get("value") or "")
    text = str(result.get("text") or "")
    expected = f"{expression} = {value}."
    if not expression or not value or text != expected:
        return None
    record_id = "math-result"
    span = Span(f"{record_id}:calculation:0:{len(text)}", record_id, "calculation", text, 0, len(text))
    return Record(record_id, "math", "", text, (span,))


def _hand_words(raw: object) -> list[str]:
    if not isinstance(raw, dict):
        return []
    words: list[str] = []
    for hand in sorted(raw, key=lambda item: str(item)):
        values = raw[hand]
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            continue
        for word in values:
            text = str(word).strip()
            if text and text not in words and _WORD.fullmatch(text):
                words.append(text)
    return words


def _categories(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    found: list[str] = []
    for item in raw:
        category = item.get("category") if isinstance(item, dict) else getattr(item, "category", None)
        text = str(category or "").strip()
        if text and text not in found and "\n" not in text:
            found.append(text)
    return sorted(found)


def _frame_plan(bundle: Bundle, question: str) -> Plan | None:
    frames = [item.frame for item in bundle.records if item.kind == "frame" and item.frame]
    resolved = resolve_frames(question, frames)
    if resolved.get("status") == "ignored":
        return None
    status = str(resolved.get("status") or "missing")
    if status != "answered":
        return Plan(
            plan_id=_plan_id("frame", question, ()),
            mode="frame",
            question=question,
            record_ids=(),
            required_roles=(),
            forbidden_roles=("ownership", "cause", "comparison"),
            tense="PAST",
            status=status,
            non_answer=str(resolved.get("text") or ""),
            frame_kind=str(resolved.get("kind") or ""),
        )
    document_id = str((resolved.get("derivation") or {}).get("document_id") or "")
    transformation = str((resolved.get("derivation") or {}).get("transformation") or "")
    record = next(
        (item for item in bundle.records if item.kind == "frame" and item.document_id == document_id),
        None,
    )
    if record is None or transformation not in _FRAME_ALLOWED:
        return Plan(
            plan_id=_plan_id("frame", question, ()),
            mode="frame",
            question=question,
            record_ids=(),
            required_roles=(),
            forbidden_roles=("ownership", "cause", "comparison"),
            tense="PAST",
            status="unsupported",
            non_answer="That question is not in the supported event-frame form.",
            frame_kind="",
        )
    return Plan(
        plan_id=_plan_id("frame", question, (record.record_id,)),
        mode="frame",
        question=question,
        record_ids=(record.record_id,),
        required_roles=_FRAME_REQUIRED[transformation],
        forbidden_roles=("ownership", "cause", "comparison", "time")
        if transformation == "past_color"
        else ("ownership", "cause", "comparison"),
        tense="PAST",
        status="answered",
        non_answer="",
        frame_kind=transformation,
    )


def _account_plan(bundle: Bundle, question: str, frame_plan: Plan | None) -> Plan:
    ids = list(_proposition_ids(bundle))
    ids.extend(item.record_id for item in bundle.records if item.kind == "quote")
    if frame_plan is not None and frame_plan.status == "answered":
        ids.extend(frame_plan.record_ids)
    ids.extend(item.record_id for item in bundle.records if item.kind in {"math", "word_edge", "tag"})
    non_answer = ""
    if frame_plan is not None and frame_plan.status != "answered":
        non_answer = frame_plan.non_answer
    if ids:
        status = "answered"
    elif frame_plan is not None:
        status = frame_plan.status
    else:
        status = "missing"
        non_answer = non_answer or "No verified epistemic evidence available."
    return Plan(
        plan_id=_plan_id("account", question, tuple(ids)),
        mode="account",
        question=question,
        record_ids=tuple(ids),
        required_roles=(),
        forbidden_roles=("ownership", "cause", "comparison"),
        tense="",
        status=status,
        non_answer=non_answer,
    )


def _ids_plan(bundle: Bundle, question: str, mode: str, record_ids: list[str], empty: str = "") -> Plan:
    if not record_ids:
        return Plan(
            plan_id=_plan_id(mode, question, ()),
            mode=mode,
            question=question,
            record_ids=(),
            required_roles=(),
            forbidden_roles=(),
            tense="",
            status="missing",
            non_answer=empty or "No verified epistemic evidence available.",
        )
    return Plan(
        plan_id=_plan_id(mode, question, tuple(record_ids)),
        mode=mode,
        question=question,
        record_ids=tuple(record_ids),
        required_roles=(),
        forbidden_roles=(),
        tense="",
        status="answered",
        non_answer="",
    )


def _math_licensed(question: str, bundle: Bundle) -> bool:
    if not any(item.kind == "math" for item in bundle.records):
        return False
    from cpu_llm.classifier import math_trigger

    return bool(math_trigger(question))


def _proposition_ids(bundle: Bundle) -> list[str]:
    records = [item for item in bundle.records if item.kind == "proposition" and item.proposition is not None]
    if not records:
        return []
    propositions = [item.proposition for item in records if item.proposition is not None]
    order = _ordered_ids(propositions, [])
    by_proposition = {item.proposition.proposition_id: item.record_id for item in records if item.proposition}
    return [by_proposition[item] for item in order if item in by_proposition]


def _derivation(bundle: Bundle, plan: Plan, record: Record, previous_proposition: str) -> Derivation | None:
    if record.kind == "proposition":
        return _proposition_derivation(bundle, record, previous_proposition)
    if record.kind == "quote":
        return _copy_all(record, "source_quote", "sentence")
    if record.kind == "math":
        return _copy_all(record, "math_result", "calculation")
    if record.kind == "word_edge":
        return _marked_copies(record, "word_edge", "These words share a stored word-edge: ", ", ", ".")
    if record.kind == "tag":
        return _marked_copies(record, "stored_tag", "Stored tag: ", "", ".")
    if record.kind == "frame":
        return _frame_derivation(record, plan.frame_kind)
    return None


def _proposition_derivation(bundle: Bundle, record: Record, previous_proposition: str) -> Derivation | None:
    proposition = record.proposition
    if proposition is None:
        return None
    clause, _delivered = _REALIZER.synthesize([proposition], [])
    by_role = {span.role: span for span in record.spans}
    pieces = [by_role[role] for role in ("subject", "predicate", "object") if role in by_role]
    actions = _bind_clause("proposition_clause", clause, pieces)
    if actions is None:
        return None
    causal = proposition.proposition_id and (previous_proposition, proposition.proposition_id) in bundle.causal_edges
    if causal:
        actions = (actions[0], Action("EMIT_GRAMMAR", "proposition_clause", surface="Consequently, ")) + actions[1:]
    return _finish(
        record,
        "proposition_clause",
        actions,
        allowed=("subject", "predicate", "object"),
        required=("subject", "predicate", "object"),
    )


def _frame_derivation(record: Record, transformation: str) -> Derivation | None:
    if transformation not in _FRAME_ALLOWED or record.frame is None:
        return None
    resolved = resolve_frames(_question_for(transformation, record.frame), [record.frame])
    sentence = str(resolved.get("text") or "")
    if resolved.get("status") != "answered" or resolved.get("verified") is not True:
        return None
    by_role = {span.role: span for span in record.spans}
    order = {
        "past_color": ("patient", "agent", "predicate", "color") if by_role.get("agent") else ("patient", "predicate", "color"),
        "past_location": ("agent", "predicate", "patient", "location"),
        "past_agent": ("agent", "predicate", "patient"),
    }[transformation]
    if any(role not in by_role for role in order):
        return None
    pieces = [by_role[role] for role in order]
    actions = _bind_clause(transformation, sentence, pieces)
    if actions is None:
        return None
    required = _FRAME_REQUIRED[transformation]
    if by_role.get("agent") and transformation == "past_color":
        required = ("patient", "agent", "predicate", "color")
    return _finish(record, transformation, actions, allowed=_FRAME_ALLOWED[transformation], required=required)


def _question_for(transformation: str, frame: dict) -> str:
    patient = str((frame.get("patient") or {}).get("text") or "")
    agent = str((frame.get("agent") or {}).get("text") or "")
    verb = str((frame.get("predicate") or {}).get("text") or "")
    if transformation == "past_location":
        return f"Where did {agent} {verb}?"
    if transformation == "past_agent":
        return f"Who {verb} the {patient}?"
    if agent and " " not in agent:
        return f"What color was the {patient} {agent} {verb}?"
    return f"What color was the {patient}?"


def _copied_ranking(record_id: str, sentences: list[str]) -> tuple[Record, Derivation | None]:
    body = " ".join(sentences)
    source = f"Ranking: {body}"
    spans: list[Span] = []
    cursor = len("Ranking: ")
    for sentence in sentences:
        found = source.find(sentence, cursor)
        if found < 0:
            return Record(record_id, "ranking", "", source, ()), None
        spans.append(_span(record_id, "ranking", source, (found, found + len(sentence))))
        cursor = found + len(sentence)
    record = Record(record_id, "ranking", "", source, tuple(spans))
    actions = _bind_clause("stored_ranking", source, spans)
    if actions is None:
        return record, None
    return record, _finish(record, "stored_ranking", actions, allowed=("ranking",), required=("ranking",))


def _grammar_ranking(record_id: str, sentence: str) -> tuple[Record, Derivation]:
    record = Record(record_id, "ranking", "", sentence, ())
    actions = (
        Action("CHOOSE_CONSTRUCTION", "ranking_gap"),
        Action("EMIT_GRAMMAR", "ranking_gap", surface=sentence),
        Action("STOP", "ranking_gap"),
    )
    return record, _finish(record, "ranking_gap", actions, allowed=(), required=())


def _copy_all(record: Record, construction_id: str, role: str) -> Derivation | None:
    span = next((item for item in record.spans if item.role == role), None)
    if span is None:
        return None
    actions = (
        Action("CHOOSE_CONSTRUCTION", construction_id),
        Action("COPY", construction_id, span.span_id, span.text, role),
        Action("STOP", construction_id),
    )
    return _finish(record, construction_id, actions, allowed=(role,), required=(role,))


def _marked_copies(record: Record, construction_id: str, prefix: str, separator: str, suffix: str) -> Derivation | None:
    if not record.spans:
        return None
    actions = [Action("CHOOSE_CONSTRUCTION", construction_id), Action("EMIT_GRAMMAR", construction_id, surface=prefix)]
    for index, span in enumerate(record.spans):
        if index and separator:
            actions.append(Action("EMIT_GRAMMAR", construction_id, surface=separator))
        actions.append(Action("COPY", construction_id, span.span_id, span.text, span.role))
    actions.append(Action("EMIT_GRAMMAR", construction_id, surface=suffix))
    actions.append(Action("STOP", construction_id))
    if replay_text(tuple(actions)) != record.source:
        return None
    roles = tuple(dict.fromkeys(span.role for span in record.spans))
    return _finish(record, construction_id, tuple(actions), allowed=roles, required=roles)


def _bind_clause(construction_id: str, sentence: str, pieces: list[Span]) -> tuple[Action, ...] | None:
    actions: list[Action] = [Action("CHOOSE_CONSTRUCTION", construction_id)]
    cursor = 0
    for span in pieces:
        found = sentence.find(span.text, cursor)
        if found < 0:
            return None
        if found > cursor:
            actions.append(Action("EMIT_GRAMMAR", construction_id, surface=sentence[cursor:found]))
        actions.append(Action("COPY", construction_id, span.span_id, span.text, span.role))
        cursor = found + len(span.text)
    if cursor < len(sentence):
        actions.append(Action("EMIT_GRAMMAR", construction_id, surface=sentence[cursor:]))
    actions.append(Action("STOP", construction_id))
    if replay_text(tuple(actions)) != sentence:
        return None
    return tuple(actions)


def _finish(
    record: Record,
    construction_id: str,
    actions: tuple[Action, ...],
    *,
    allowed: tuple[str, ...],
    required: tuple[str, ...],
) -> Derivation:
    return Derivation(
        derivation_id=f"{construction_id}:{record.record_id}",
        construction_id=construction_id,
        record_id=record.record_id,
        actions=actions,
        allowed_roles=allowed,
        required_roles=required,
    )


def _span(record_id: str, role: str, source: str, bounds: tuple[int, int]) -> Span:
    start, end = bounds
    return Span(f"{record_id}:{role}:{start}:{end}", record_id, role, source[start:end], start, end)


def _locate(source: str, text: str, start: int) -> tuple[int, int] | None:
    if not text:
        return None
    found = source.find(text, start)
    if found < 0:
        return None
    return found, found + len(text)


def _plan_id(mode: str, question: str, record_ids: tuple[str, ...]) -> str:
    raw = "\n".join((mode, question, *record_ids))
    return "p-" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def _causal_pairs(edges: list) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for edge in edges:
        edge_type = getattr(edge, "edge_type", None)
        if edge_type is None and isinstance(edge, dict):
            edge_type = edge.get("edge_type")
        if edge_type not in {EdgeType.CAUSAL_RELATION, EdgeType.CAUSAL_RELATION.value, "CAUSAL_RELATION"}:
            continue
        source = getattr(edge, "source_id", None)
        target = getattr(edge, "target_id", None)
        if isinstance(edge, dict):
            source = edge.get("source_id")
            target = edge.get("target_id")
        if source and target:
            pairs.append((str(source), str(target)))
    return pairs


def replay_text(actions: tuple[Action, ...]) -> str:
    from cpu_llm.realizer.evidence_schema import replay

    return replay(actions)
