"""Event roles cut from a sentence the realizer can already repeat.

Stage 1 accepts one closed clause shape. A role is a capture from that
shape, with offsets into the sentence. A sentence that round-trips but does
not match the shape is not a frame. The joined sentence is not a new
proposition.

Offsets are sentence-relative. ``schema`` is ``stage1-v2``. Ingest stores
that record on the chunk. A query uses the stored record when the schema
matches, and otherwise runs this same extractor.
"""

from __future__ import annotations

import re
from typing import Any

from cpu_llm.clauses import _first_sentence, proposition_from_chunk
from cpu_llm.comparison import comparison_sides
from cpu_llm.realizer.inflect import surface_tokens

SCHEMA = "stage1-v2"
STAGE2 = "stage2-v1"
_UNSETTLED = "The retrieved passages do not settle that."
_COLORS = frozenset(
    "black blue brown gray grey green orange pink purple red white yellow".split()
)
_DET = frozenset("a an the".split())
_NEGATION = re.compile(r"\b(?:not|never|no|n't)\b", re.IGNORECASE)
_YEAR = r"(?:1[89]|20)\d{2}"
_YEAR_PREFIX = rf"(?:[Ii]n (?P<prefix_year>{_YEAR}),\s+)?"
_YEAR_SUFFIX = rf"(?: [Ii]n (?P<suffix_year>{_YEAR}))?"
_COLOR_QUESTION = re.compile(
    rf"^{_YEAR_PREFIX}[Ww]hat color was the (?P<patient>[A-Za-z]+)"
    rf"(?: (?P<agent>[A-Za-z]+) (?P<verb>[A-Za-z]+))?{_YEAR_SUFFIX}\??$"
)
_WHERE_QUESTION = re.compile(
    rf"^{_YEAR_PREFIX}[Ww]here did (?P<agent>[A-Za-z]+) (?P<verb>[A-Za-z]+)"
    rf"(?: the (?P<patient>[A-Za-z]+))?{_YEAR_SUFFIX}\??$"
)
_WHO_QUESTION = re.compile(
    rf"^{_YEAR_PREFIX}[Ww]ho (?P<verb>[A-Za-z]+) the (?P<patient>[A-Za-z]+){_YEAR_SUFFIX}\??$"
)
_NOT_QUESTION = re.compile(r"^[Ww]hat did (?P<agent>[A-Za-z]+) not (?P<verb>[A-Za-z]+)\??$")
_FRAME_LIKE = re.compile(r"\bwhat color\b|\bwhere did\b|\bwho (?:ate|eat|eats|eaten)\b", re.IGNORECASE)
_BETTER = re.compile(r"\b(?:better|worse|best|worst)\b", re.IGNORECASE)
_TOKEN = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")
_FUNCTION = frozenset("the a an".split())
_VISIBLE = frozenset({"answered", "missing", "ambiguous", "conflicting", "unsupported"})


def frame_trigger(message: str) -> list[str]:
    """Reasons to answer from a stored event frame.

    A comparison, including one that asks which side is better, stays off
    this path. A question that looks like a frame question but does not match
    the supported form still enters, so the reply can abstain instead of
    dropping the unmatched words.
    """
    parsed = _parse_question(message)
    if parsed is None:
        return []
    if parsed["status"] == "unsupported":
        return ["the prompt is not a supported event-frame question"]
    return [parsed["reason"]]


def frame_from_chunk(document_id: str, text: str) -> dict[str, Any] | None:
    """The event in the first sentence, or nothing.

    Round-trip is required. It is not enough. The sentence also has to be a
    name or a simple noun phrase, one verb, and a direct object of a
    determiner, an optional color, and one noun. A location and a time may
    follow. Negation, a condition, a nested object, and an extra attachment
    produce no frame.
    """
    sentence = _first_sentence(text or "")
    if not sentence:
        return None
    if not sentence.endswith((".", "!", "?")):
        sentence = f"{sentence}."
    if _NEGATION.search(sentence) or re.search(r"\sif\s", sentence, re.IGNORECASE):
        return _stage2_frame(document_id, sentence)
    proposition = proposition_from_chunk(document_id, text)
    if proposition is None:
        return None
    if not sentence.endswith((".", "!", "?")):
        sentence = f"{sentence}."
    subject = proposition.subject.raw_text
    if not sentence.startswith(subject) or sentence[len(subject) : len(subject) + 1] not in {" ", ""}:
        return None
    tokens = list(_TOKEN.finditer(sentence))
    if not tokens:
        return None
    subject_tokens = [token for token in tokens if token.end() <= len(subject)]
    rest = [token for token in tokens if token.start() > len(subject)]
    if not rest:
        return None
    verb = rest[0]
    parsed = _parse_clause(proposition.predicate.lemma, subject, subject_tokens, verb, rest[1:])
    if parsed is None:
        return None
    frame = {
        "schema": SCHEMA,
        "document_id": document_id,
        "sentence": sentence,
        "offset_base": "sentence",
        "proposition_id": proposition.proposition_id,
        "subject": _span("subject", subject, 0),
        "object": parsed["object"],
        "agent": parsed["agent"],
        "predicate": parsed["predicate"],
        "patient": parsed["patient"],
        "color": parsed["color"],
        "location": parsed["location"],
        "time": parsed["time"],
    }
    frame["predicate"]["lemma"] = proposition.predicate.lemma
    frame["predicate"]["tense"] = proposition.predicate.tense
    if not _bindings_ok(frame):
        return None
    return frame


def stated_role(frames: list[dict[str, Any]], role: str, entity: str = "") -> str:
    """A role span from a frame already in ``frames``.

    The list is the sentences retrieval returned. A role that is not on one
    of those frames is the existing missing sentence for that role. This does
    not search another node and does not add a relation.
    """
    wanted = entity.casefold()
    for frame in frames:
        if not frame or frame.get("schema") not in {SCHEMA, STAGE2}:
            continue
        if wanted and not any(_text_is(frame.get(key), entity) for key in ("agent", "patient", "subject")):
            continue
        span = frame.get(role)
        if isinstance(span, dict) and span.get("text"):
            return str(span["text"])
    if role == "color":
        return "No stored sentence states that color in the past."
    if role == "location":
        return "No stored sentence states that location."
    if role == "agent":
        return "No stored sentence names who did that."
    return "No stored sentence states that role."


def _stage2_frame(document_id: str, sentence: str) -> dict[str, Any] | None:
    """Negation or a condition, as spans of the stored sentence.

    The affirmative stage-1 sentence stays on schema ``stage1-v2``. A negated
    span is not rewritten as a permission. A condition stays attached to the
    sentence that states it.
    """
    condition = None
    core = sentence
    marker = re.search(r"\sif\s", sentence, re.IGNORECASE)
    if marker:
        core = sentence[: marker.start()].rstrip()
        if not core.endswith("."):
            core = f"{core}."
        condition = {
            "role": "condition",
            "text": sentence[marker.start() + 1 :].rstrip(".!?"),
            "start": marker.start() + 1,
            "end": len(sentence.rstrip(".!?")),
        }
    if not _NEGATION.search(core):
        inner = frame_from_chunk(document_id, core)
        if inner is None or condition is None:
            return None
        inner["schema"] = STAGE2
        inner["polarity"] = "AFFIRMATIVE"
        inner["condition"] = condition
        inner["sentence"] = sentence
        return inner
    parsed = _negative_clause(core)
    if parsed is None:
        return None
    frame = {
        "schema": STAGE2,
        "document_id": document_id,
        "sentence": sentence,
        "offset_base": "sentence",
        "polarity": "NEGATIVE",
        "condition": condition,
        "proposition_id": None,
        **parsed,
    }
    if not _bindings_ok(frame):
        return None
    return frame


def _negative_clause(sentence: str) -> dict[str, Any] | None:
    colors = "|".join(sorted(_COLORS))
    found = re.fullmatch(
        rf"(?P<agent>[A-Z][A-Za-z]+) did not (?P<verb>[A-Za-z]+) "
        rf"(?P<det>a|an|the)(?: (?P<color>{colors}))? (?P<patient>[A-Za-z]+)"
        rf"(?P<rest>.*)\.",
        sentence,
    )
    if found is None:
        return None
    agent = found.group("agent")
    verb = found.group("verb")
    patient = found.group("patient")
    color = found.group("color")
    object_text = found.group("det")
    if color:
        object_text = f"{object_text} {color}"
    object_text = f"{object_text} {patient}"
    object_at = sentence.find(object_text)
    if object_at < 0:
        return None
    rest = found.group("rest") or ""
    location = None
    if rest.strip():
        location_at = sentence.find(rest.strip())
        if location_at < 0:
            return None
        location = {"role": "location", "text": rest.strip(), "start": location_at, "end": location_at + len(rest.strip())}
    return {
        "subject": _span("subject", agent, 0),
        "agent": _span("agent", agent, 0),
        "predicate": {
            "role": "predicate",
            "text": verb,
            "lemma": verb,
            "tense": "PAST",
            "start": sentence.find(f" {verb} ") + 1,
            "end": sentence.find(f" {verb} ") + 1 + len(verb),
        },
        "patient": {
            "role": "patient",
            "text": patient,
            "start": object_at + object_text.rfind(patient),
            "end": object_at + object_text.rfind(patient) + len(patient),
        },
        "color": None
        if color is None
        else {
            "role": "color",
            "text": color,
            "start": sentence.find(color, object_at),
            "end": sentence.find(color, object_at) + len(color),
        },
        "object": {"role": "object", "text": object_text, "start": object_at, "end": object_at + len(object_text)},
        "location": location,
        "time": None,
    }


def _stage2_hold(frames: list[dict[str, Any]], wanted: dict[str, Any]) -> dict[str, Any] | None:
    """A positive question against a negative span or an unmet condition."""
    matched = [frame for frame in frames if frame and frame.get("schema") == STAGE2 and _stage2_same(frame, wanted)]
    if not matched:
        return None
    blocked = [
        frame
        for frame in matched
        if frame.get("polarity") == "NEGATIVE" or frame.get("condition")
    ]
    if not blocked:
        return None
    result = _outcome("missing", _UNSETTLED, "the stored span does not grant the asked polarity")
    result["evidence"] = [frame["document_id"] for frame in blocked]
    return result


def _stage2_same(frame: dict[str, Any], wanted: dict[str, Any]) -> bool:
    if wanted.get("patient") and not _text_is(frame.get("patient"), wanted["patient"]):
        return False
    if wanted.get("agent") and not _text_is(frame.get("agent"), wanted["agent"]):
        return False
    return True


def _negated_answer(frames: list[dict[str, Any]], wanted: dict[str, Any]) -> dict[str, Any]:
    matched = [
        frame
        for frame in frames
        if frame
        and frame.get("schema") == STAGE2
        and frame.get("polarity") == "NEGATIVE"
        and _text_is(frame.get("agent"), wanted.get("agent"))
        and _text_is(frame.get("predicate"), wanted.get("verb"))
    ]
    if not matched:
        text = _missing_text("negated", wanted)
        return _outcome("missing", text, text)
    frame = matched[0]
    sentence = str(frame.get("sentence") or "")
    result = _outcome("answered", sentence, "")
    result.update(
        {
            "ok": True,
            "kind": "negated",
            "value": (frame.get("patient") or {}).get("text") or "",
            "verified": True,
            "abstained": False,
            "evidence": [frame["document_id"]],
        }
    )
    return result


def resolve_frames(message: str, frames: list[dict[str, Any]]) -> dict[str, Any]:
    """A verified sentence, or a visible non-answer.

    ``status`` is ``answered``, ``missing``, ``ambiguous``, ``conflicting``,
    or ``unsupported``. ``verified`` is true only for a sentence whose role
    bindings and tense transformation were checked. ``ok`` follows ``verified``.
    """
    parsed = _parse_question(message)
    if parsed is None:
        return _outcome("ignored", "", "This question is not answered from an event frame.")
    if parsed["status"] == "unsupported":
        return _outcome("unsupported", "That question is not in the supported event-frame form.", parsed["gap"])
    kind = parsed["kind"]
    if kind == "negated":
        return _negated_answer(frames, parsed)
    held = _stage2_hold(frames, parsed)
    if held is not None:
        return held
    matched = [frame for frame in frames if frame and _matches(frame, parsed)]
    if not matched:
        return _outcome("missing", _missing_text(kind, parsed), _missing_text(kind, parsed))
    if kind == "color":
        return _color_answer(matched, parsed)
    if kind == "location":
        return _location_answer(matched, parsed)
    return _agent_answer(matched, parsed)


def frame_reply_text(state: dict[str, Any]) -> str:
    """The frame sentence that may be spoken, or nothing.

    A Shine rejection, an audit block, or a grammar block wins. An answered
    frame is spoken only when ``verified`` is true. A missing, conflicting,
    ambiguous, or unsupported frame is spoken as that non-answer.
    """
    if state.get("delivery_blocked") or state.get("shine_enforced") or state.get("shine_ok") is False:
        return ""
    if state.get("frame") is not True:
        return ""
    result = state.get("frame_result") or {}
    status = str(result.get("status") or "")
    text = str(result.get("text") or "").strip()
    if status not in _VISIBLE or not text:
        return ""
    if status == "answered" and result.get("verified") is not True:
        return ""
    return text


def _parse_clause(lemma, subject, subject_tokens, verb, tail):
    if lemma == "be":
        if not _simple_noun_phrase(subject_tokens):
            return None
        patient = subject_tokens[-1]
        color, index = _one(_COLORS, tail, 0, "color")
        if color is None:
            return None
        location, index = _location(tail, index)
        time_span, index = _time(tail, index)
        if index != len(tail):
            return None
        return {
            "agent": None,
            "predicate": _from_match(verb, "predicate"),
            "patient": _from_match(patient, "patient"),
            "color": color,
            "location": location,
            "time": time_span,
            "object": color,
        }
    agent = _span("agent", subject, 0)
    object_span, patient, color, index = _object(tail)
    if object_span is None or patient is None:
        return None
    location, index = _location(tail, index)
    time_span, index = _time(tail, index)
    if index != len(tail):
        return None
    return {
        "agent": agent,
        "predicate": _from_match(verb, "predicate"),
        "patient": patient,
        "color": color,
        "location": location,
        "time": time_span,
        "object": object_span,
    }


def _simple_noun_phrase(tokens: list[re.Match[str]]) -> bool:
    words = [token.group(0).casefold() for token in tokens]
    if len(words) == 1:
        return words[0] not in _DET
    return len(words) == 2 and words[0] in _DET and words[1] not in _DET


def _object(tokens: list[re.Match[str]]):
    if len(tokens) < 2 or tokens[0].group(0).casefold() not in _DET:
        return None, None, None, 0
    if len(tokens) >= 3 and tokens[1].group(0).casefold() in _COLORS and tokens[2].group(0).casefold() not in _DET:
        color = _from_match(tokens[1], "color")
        patient = _from_match(tokens[2], "patient")
        return _cover(tokens[0], tokens[2], "object"), patient, color, 3
    if tokens[1].group(0).casefold() in _DET or tokens[1].group(0).casefold() in _COLORS:
        return None, None, None, 0
    patient = _from_match(tokens[1], "patient")
    return _cover(tokens[0], tokens[1], "object"), patient, None, 2


def _location(tokens, index):
    if index + 2 >= len(tokens):
        return None, index
    preposition, determiner, noun = tokens[index], tokens[index + 1], tokens[index + 2]
    if preposition.group(0).casefold() not in {"in", "at", "on"}:
        return None, index
    if determiner.group(0).casefold() not in {"his", "her", "their", "the", "a", "an", "my", "our", "your"}:
        return None, index
    return _cover(preposition, noun, "location"), index + 3


def _time(tokens, index):
    if index >= len(tokens):
        return None, index
    word = tokens[index].group(0).casefold()
    if word in {"yesterday", "today", "tomorrow", "tonight"}:
        return _from_match(tokens[index], "time"), index + 1
    if index + 1 < len(tokens) and word in {"in", "on"} and re.fullmatch(_YEAR, tokens[index + 1].group(0)):
        return _cover(tokens[index], tokens[index + 1], "time"), index + 2
    return None, index


def _one(allowed: frozenset[str], tokens, index: int, role: str):
    if index >= len(tokens) or tokens[index].group(0).casefold() not in allowed:
        return None, index
    return _from_match(tokens[index], role), index + 1


def _from_match(token: re.Match[str], role: str) -> dict[str, Any]:
    return {"role": role, "text": token.group(0), "start": token.start(), "end": token.end()}


def _cover(start: re.Match[str], end: re.Match[str], role: str) -> dict[str, Any]:
    return {"role": role, "text": start.string[start.start() : end.end()], "start": start.start(), "end": end.end()}


def _span(role: str, text: str, start: int) -> dict[str, Any]:
    return {"role": role, "text": text, "start": start, "end": start + len(text)}


def _bindings_ok(frame: dict[str, Any]) -> bool:
    sentence = frame["sentence"]
    subject = frame["subject"]
    obj = frame["object"]
    if sentence[subject["start"] : subject["end"]] != subject["text"]:
        return False
    if sentence[obj["start"] : obj["end"]] != obj["text"]:
        return False
    patient = frame.get("patient")
    color = frame.get("color")
    agent = frame.get("agent")
    if patient is None or sentence[patient["start"] : patient["end"]] != patient["text"]:
        return False
    if color is not None:
        if sentence[color["start"] : color["end"]] != color["text"]:
            return False
        if not _inside(color, obj):
            return False
    if agent is None:
        return _inside(patient, subject)
    if sentence[agent["start"] : agent["end"]] != agent["text"]:
        return False
    if agent["start"] != subject["start"] or agent["end"] != subject["end"]:
        return False
    return _inside(patient, obj)


def _inside(inner: dict[str, Any], outer: dict[str, Any]) -> bool:
    return outer["start"] <= inner["start"] and inner["end"] <= outer["end"]


def _parse_question(message: str) -> dict[str, Any] | None:
    text = (message or "").strip()
    if not text or comparison_sides(text) or _BETTER.search(text):
        return None
    negated = _NOT_QUESTION.fullmatch(text)
    if negated is not None:
        return {
            "status": "supported",
            "kind": "negated",
            "reason": "the prompt asks for a negated span written in a stored sentence",
            "patient": None,
            "agent": negated.group("agent"),
            "verb": negated.group("verb"),
            "year": None,
            "tense": "PAST",
            "negative": True,
            "gap": "",
        }
    for kind, pattern, reason in (
        ("color", _COLOR_QUESTION, "the prompt asks for a color written in a stored sentence"),
        ("location", _WHERE_QUESTION, "the prompt asks for a location written in a stored sentence"),
        ("agent", _WHO_QUESTION, "the prompt asks who a stored sentence names as the agent"),
    ):
        found = pattern.fullmatch(text)
        if found is None:
            continue
        prefix = found.groupdict().get("prefix_year")
        suffix = found.groupdict().get("suffix_year")
        if prefix and suffix and prefix != suffix:
            return {"status": "unsupported", "gap": "the question names two years"}
        year = prefix or suffix
        tense = "PAST"
        return {
            "status": "supported",
            "kind": kind,
            "reason": reason,
            "patient": found.groupdict().get("patient"),
            "agent": found.groupdict().get("agent"),
            "verb": found.groupdict().get("verb"),
            "year": year,
            "tense": tense,
            "gap": "",
        }
    if _FRAME_LIKE.search(text):
        return {"status": "unsupported", "gap": "the question is outside the supported event-frame form"}
    return None


def _matches(frame: dict[str, Any], wanted: dict[str, Any]) -> bool:
    if frame.get("schema") != SCHEMA:
        return False
    if wanted.get("patient") and not _text_is(frame.get("patient"), wanted["patient"]):
        return False
    if wanted.get("agent") and not _text_is(frame.get("agent"), wanted["agent"]):
        return False
    if wanted.get("verb") and not _verb_is(frame, wanted["verb"], wanted["tense"]):
        return False
    if frame.get("predicate", {}).get("tense") != wanted["tense"]:
        return False
    year = wanted.get("year")
    if not year:
        return True
    time_span = frame.get("time")
    return bool(time_span) and str(year) in str(time_span.get("text") or "")


def _text_is(span: dict[str, Any] | None, word: str | None) -> bool:
    return bool(word) and bool(span) and str(span.get("text") or "").casefold() == word.casefold()


def _verb_is(frame: dict[str, Any], word: str, tense: str) -> bool:
    predicate = frame.get("predicate") or {}
    if predicate.get("tense") != tense:
        return False
    if str(predicate.get("text") or "").casefold() == word.casefold():
        return True
    lemma = str(predicate.get("lemma") or "")
    return bool(lemma) and word.casefold() in surface_tokens(lemma)


def _color_answer(frames: list[dict[str, Any]], wanted: dict[str, Any]) -> dict[str, Any]:
    colored = [frame for frame in frames if frame.get("color")]
    if not colored:
        text = _missing_text("color", wanted)
        return _outcome("missing", text, text)
    values = {str(frame["color"]["text"]).casefold() for frame in colored}
    if len(values) > 1:
        return _conflict("color", "Two stored sentences state different colors.", colored, "the stored colors disagree")
    frame = colored[0]
    sentence = _color_sentence(frame)
    if sentence is None or not _transformation_ok(frame, sentence, "color"):
        return _outcome("unsupported", "That color sentence is not a supported transformation.", "transformation")
    return _answered("color", sentence, frame["color"]["text"], frame, "past_color")


def _color_sentence(frame: dict[str, Any]) -> str | None:
    patient = frame["patient"]["text"]
    color = frame["color"]["text"]
    agent = (frame.get("agent") or {}).get("text")
    verb = frame["predicate"]["text"]
    if frame["predicate"]["tense"] != "PAST":
        return None
    if not agent:
        return f"The {patient} {verb} {color}."
    if " " in agent:
        return None
    return f"The {patient} {agent} {verb} was {color}."


def _location_answer(frames: list[dict[str, Any]], wanted: dict[str, Any]) -> dict[str, Any]:
    located = [frame for frame in frames if frame.get("location") and frame.get("agent")]
    if not located:
        text = _missing_text("location", wanted)
        return _outcome("missing", text, text)
    places = {str(frame["location"]["text"]).casefold() for frame in located}
    if len(places) > 1:
        return _conflict("location", "Two stored sentences state different locations.", located, "the stored locations disagree")
    frame = located[0]
    sentence = f"{frame['agent']['text']} {frame['predicate']['text']} the {frame['patient']['text']} {frame['location']['text']}."
    if not _transformation_ok(frame, sentence, "location"):
        return _outcome("unsupported", "That location sentence is not a supported transformation.", "transformation")
    return _answered("location", sentence, frame["location"]["text"], frame, "past_location")


def _agent_answer(frames: list[dict[str, Any]], wanted: dict[str, Any]) -> dict[str, Any]:
    named = [frame for frame in frames if frame.get("agent")]
    if not named:
        text = _missing_text("agent", wanted)
        return _outcome("missing", text, text)
    agents = {str(frame["agent"]["text"]).casefold() for frame in named}
    if len(agents) > 1:
        return _conflict("agent", "Two stored sentences name different people.", named, "the stored agents disagree")
    frame = named[0]
    sentence = f"{frame['agent']['text']} {frame['predicate']['text']} the {frame['patient']['text']}."
    if not _transformation_ok(frame, sentence, "agent"):
        return _outcome("unsupported", "That agent sentence is not a supported transformation.", "transformation")
    return _answered("agent", sentence, frame["agent"]["text"], frame, "past_agent")


def _transformation_ok(frame: dict[str, Any], sentence: str, kind: str) -> bool:
    if frame["predicate"]["tense"] != "PAST":
        return False
    if not _bindings_ok(frame):
        return False
    allowed = set(_FUNCTION)
    allowed.add(frame["predicate"]["text"].casefold())
    allowed.add(frame["patient"]["text"].casefold())
    if kind == "color":
        allowed.add(frame["color"]["text"].casefold())
        if frame.get("agent"):
            if " " in frame["agent"]["text"]:
                return False
            allowed.add("was")
            allowed.update(token.casefold() for token in _TOKEN.findall(frame["agent"]["text"]))
    elif kind == "location":
        allowed.update(token.casefold() for token in _TOKEN.findall(frame["agent"]["text"]))
        allowed.update(token.casefold() for token in _TOKEN.findall(frame["location"]["text"]))
    else:
        allowed.update(token.casefold() for token in _TOKEN.findall(frame["agent"]["text"]))
    for token in _TOKEN.findall(sentence):
        if token.casefold() not in allowed:
            return False
    source = {token.casefold() for token in _TOKEN.findall(frame["sentence"])}
    for token in _TOKEN.findall(sentence):
        lowered = token.casefold()
        if lowered in _FUNCTION or lowered == "was":
            continue
        if lowered not in source:
            return False
    return True


def _missing_text(kind: str, wanted: dict[str, Any]) -> str:
    year = wanted.get("year")
    if kind == "color" and year:
        return f"No stored sentence states that color in {year}."
    if kind == "color" and wanted.get("tense") == "PAST":
        return "No stored sentence states that color in the past."
    if kind == "location":
        return "No stored sentence states that location."
    if kind == "agent":
        return "No stored sentence names who did that."
    if kind == "negated":
        return "No stored sentence states that."
    return "No stored sentence states that."


def _answered(kind: str, sentence: str, value: str, frame: dict[str, Any], transformation: str) -> dict[str, Any]:
    result = _outcome("answered", sentence, "")
    result.update(
        {
            "ok": True,
            "kind": kind,
            "value": value,
            "verified": True,
            "abstained": False,
            "evidence": [frame["document_id"]],
            "derivation": {
                "document_id": frame["document_id"],
                "proposition_id": frame["proposition_id"],
                "sentence": frame["sentence"],
                "offset_base": "sentence",
                "tense": frame["predicate"]["tense"],
                "transformation": transformation,
                "roles": {
                    key: frame.get(key)
                    for key in ("agent", "predicate", "patient", "color", "location", "time")
                },
            },
        }
    )
    return result


def _conflict(kind: str, text: str, frames: list[dict[str, Any]], gap: str) -> dict[str, Any]:
    result = _outcome("conflicting", text, gap)
    result["kind"] = kind
    result["evidence"] = [frame["document_id"] for frame in frames]
    result["contradictions"] = [frame["document_id"] for frame in frames]
    return result


def _outcome(status: str, text: str, gap: str) -> dict[str, Any]:
    abstained = status in {"missing", "ambiguous", "conflicting", "unsupported"}
    return {
        "ok": False,
        "status": status,
        "kind": "",
        "text": text,
        "value": "",
        "verified": False,
        "evidence": [],
        "contradictions": [],
        "gaps": [gap] if gap else [],
        "abstained": abstained,
        "derivation": None,
    }
