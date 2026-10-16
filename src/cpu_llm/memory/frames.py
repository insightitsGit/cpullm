"""Event roles cut from a sentence the realizer can already repeat.

A color, a location, a time, and the participants are slices of that sentence.
A word that is not in the sentence is not stored, and it is not spoken.
"His house" stays a location phrase. It does not become ownership.
"""

from __future__ import annotations

import re
from typing import Any

from cpu_llm.clauses import _first_sentence, proposition_from_chunk
from cpu_llm.comparison import comparison_sides
from cpu_llm.realizer.inflect import surface_tokens

_COLORS = frozenset(
    "black blue brown gray grey green orange pink purple red white yellow".split()
)
_NEGATION = re.compile(r"\b(?:not|never|no|n't)\b", re.IGNORECASE)
_COLOR_NOUN = re.compile(
    r"^(?:a|an|the)\s+(" + "|".join(sorted(_COLORS)) + r")\s+([A-Za-z][A-Za-z'-]*)$",
    re.IGNORECASE,
)
_TRAILING_TIME = re.compile(
    r"(?:\s+)((?:in|on)\s+(?:(?:1[89]|20)\d{2})|yesterday|today|tomorrow|tonight)$",
    re.IGNORECASE,
)
_TRAILING_LOCATION = re.compile(
    r"(?:\s+)((?:in|at|on)\s+(?:his|her|their|the|a|an|my|our|your)\s+[A-Za-z][A-Za-z'-]*)$",
    re.IGNORECASE,
)
_COLOR_QUESTION = re.compile(
    r"\bwhat color was the ([A-Za-z]+)(?: ([A-Za-z]+) ([A-Za-z]+))?(?: in ((?:1[89]|20)\d{2}))?\??$",
    re.IGNORECASE,
)
_WHERE_QUESTION = re.compile(
    r"\bwhere did ([A-Za-z]+) ([A-Za-z]+)(?: the ([A-Za-z]+))?\??$",
    re.IGNORECASE,
)
_WHO_QUESTION = re.compile(r"\bwho ([A-Za-z]+) the ([A-Za-z]+)\??$", re.IGNORECASE)
_BETTER = re.compile(r"\b(?:better|worse|best|worst)\b", re.IGNORECASE)
_TOKEN = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")
_FUNCTION = frozenset("the a an was were is are did that".split())


def frame_trigger(message: str) -> list[str]:
    """Reasons to answer from a stored event frame.

    A comparison, including one that asks which side is better, stays off
    this path. The frame agent does not choose a winner.
    """
    text = message or ""
    if comparison_sides(text) or _BETTER.search(text):
        return []
    if _COLOR_QUESTION.search(text.strip()):
        return ["the prompt asks for a color written in a stored sentence"]
    if _WHERE_QUESTION.search(text.strip()):
        return ["the prompt asks for a location written in a stored sentence"]
    if _WHO_QUESTION.search(text.strip()):
        return ["the prompt asks who a stored sentence names as the agent"]
    return []


def frame_from_chunk(document_id: str, text: str) -> dict[str, Any] | None:
    """The event in the first sentence, or nothing.

    Nothing is stored when the realizer cannot repeat that sentence, or when
    the sentence is negated. A negated sentence is not kept as an affirmative
    event.
    """
    sentence = _first_sentence(text or "")
    if not sentence or _NEGATION.search(sentence):
        return None
    proposition = proposition_from_chunk(document_id, text)
    if proposition is None:
        return None
    body = sentence.rstrip(".!?").strip()
    subject = proposition.subject.raw_text
    if not body.startswith(f"{subject} "):
        return None
    verb, _separator, tail = body[len(subject) + 1 :].partition(" ")
    if not verb or not tail or " " in verb:
        return None
    time_text, tail = _strip_trailing(tail, _TRAILING_TIME)
    location_text, tail = _strip_trailing(tail, _TRAILING_LOCATION)
    color_text, patient_text, agent_text = _roles(proposition.predicate.lemma, subject, tail)
    if patient_text is None:
        return None
    frame: dict[str, Any] = {
        "document_id": document_id,
        "sentence": sentence if sentence.endswith((".", "!", "?")) else f"{sentence}.",
        "proposition_id": proposition.proposition_id,
        "agent": _locate(sentence, agent_text, "agent") if agent_text else None,
        "predicate": _locate(sentence, verb, "predicate"),
        "patient": _locate(sentence, patient_text, "patient"),
        "color": _locate(sentence, color_text, "color") if color_text else None,
        "location": _locate(sentence, location_text, "location") if location_text else None,
        "time": _locate(sentence, time_text, "time") if time_text else None,
    }
    frame["predicate"]["lemma"] = proposition.predicate.lemma
    frame["predicate"]["tense"] = proposition.predicate.tense
    if frame["patient"] is None or frame["predicate"].get("text") != verb:
        return None
    if not _spans_match(sentence, frame):
        return None
    return frame


def resolve_frames(message: str, frames: list[dict[str, Any]]) -> dict[str, Any]:
    """A sentence built from matching frames, or a gap.

    The spoken sentence may contain only words from the source sentence, plus
    a closed list of function words. Two colors for the same question produce
    no color.
    """
    if not frame_trigger(message):
        return _empty("This question is not answered from an event frame.")
    kind, wanted = _parse(message)
    if kind is None:
        return _empty("This question is not answered from an event frame.")
    matched = [frame for frame in frames if _matches(frame, wanted)]
    if not matched:
        return _empty("No stored sentence states that.")
    if kind == "color":
        return _color_answer(matched)
    if kind == "location":
        return _location_answer(matched)
    return _agent_answer(matched)


def _roles(lemma: str, subject: str, tail: str) -> tuple[str | None, str | None, str | None]:
    if lemma == "be" and tail.casefold() in _COLORS:
        return tail, _head(subject), None
    found = _COLOR_NOUN.match(tail)
    if found:
        return found.group(1), found.group(2), subject
    head = _head(tail)
    if head is None:
        return None, None, subject
    return None, head, subject


def _head(phrase: str) -> str | None:
    tokens = _TOKEN.findall(phrase)
    content = [token for token in tokens if token.casefold() not in _FUNCTION]
    if not content:
        return None
    return content[-1]


def _strip_trailing(text: str, pattern: re.Pattern[str]) -> tuple[str | None, str]:
    found = pattern.search(text)
    if found is None:
        return None, text
    return found.group(1), text[: found.start()].rstrip()


def _locate(sentence: str, phrase: str | None, role: str) -> dict[str, Any] | None:
    if not phrase:
        return None
    start = sentence.find(phrase)
    if start < 0:
        return None
    end = start + len(phrase)
    if sentence[start:end] != phrase:
        return None
    return {"role": role, "text": phrase, "start": start, "end": end}


def _spans_match(sentence: str, frame: dict[str, Any]) -> bool:
    for key in ("agent", "predicate", "patient", "color", "location", "time"):
        span = frame.get(key)
        if span is None:
            continue
        if sentence[span["start"] : span["end"]] != span["text"]:
            return False
    return True


def _parse(message: str) -> tuple[str | None, dict[str, str]]:
    text = (message or "").strip()
    color = _COLOR_QUESTION.search(text)
    if color:
        wanted = {"patient": color.group(1)}
        if color.group(2) and color.group(3):
            wanted["agent"] = color.group(2)
            wanted["verb"] = color.group(3)
        if color.group(4):
            wanted["year"] = color.group(4)
        return "color", wanted
    where = _WHERE_QUESTION.search(text)
    if where:
        wanted = {"agent": where.group(1), "verb": where.group(2)}
        if where.group(3):
            wanted["patient"] = where.group(3)
        return "location", wanted
    who = _WHO_QUESTION.search(text)
    if who:
        return "agent", {"verb": who.group(1), "patient": who.group(2)}
    return None, {}


def _matches(frame: dict[str, Any], wanted: dict[str, str]) -> bool:
    if "patient" in wanted and not _text_is(frame.get("patient"), wanted["patient"]):
        return False
    if "agent" in wanted and not _text_is(frame.get("agent"), wanted["agent"]):
        return False
    if "verb" in wanted and not _verb_is(frame, wanted["verb"]):
        return False
    year = wanted.get("year")
    if year is None:
        found = None
    else:
        found = year
    if found is None:
        return True
    time_span = frame.get("time")
    return bool(time_span) and found in str(time_span.get("text") or "")


def _text_is(span: dict[str, Any] | None, word: str) -> bool:
    return bool(span) and str(span.get("text") or "").casefold() == word.casefold()


def _verb_is(frame: dict[str, Any], word: str) -> bool:
    predicate = frame.get("predicate") or {}
    if str(predicate.get("text") or "").casefold() == word.casefold():
        return True
    lemma = str(predicate.get("lemma") or "")
    return bool(lemma) and word.casefold() in surface_tokens(lemma)


def _color_answer(frames: list[dict[str, Any]]) -> dict[str, Any]:
    colored = [frame for frame in frames if frame.get("color")]
    if not colored:
        return _empty("No stored sentence states that color.")
    values = {str(frame["color"]["text"]).casefold() for frame in colored}
    if len(values) > 1:
        return {
            "ok": False,
            "kind": "color",
            "text": "Two stored sentences state different colors.",
            "value": "",
            "evidence": [frame["document_id"] for frame in colored],
            "contradictions": [frame["document_id"] for frame in colored],
            "gaps": ["the stored colors disagree"],
            "abstained": True,
        }
    frame = colored[0]
    noun = frame["patient"]["text"]
    agent = (frame.get("agent") or {}).get("text")
    verb = frame["predicate"]["text"]
    color = frame["color"]["text"]
    if agent:
        sentence = f"The {noun} {agent} {verb} was {color}."
    else:
        sentence = f"The {noun} was {color}."
    if not _grounded(sentence, frame["sentence"]):
        return _empty("The color sentence used a word the source does not contain.")
    return _spoken("color", sentence, color, frame)


def _location_answer(frames: list[dict[str, Any]]) -> dict[str, Any]:
    located = [frame for frame in frames if frame.get("location") and frame.get("agent")]
    if not located:
        return _empty("No stored sentence states that location.")
    places = {str(frame["location"]["text"]).casefold() for frame in located}
    if len(places) > 1:
        return {
            "ok": False,
            "kind": "location",
            "text": "Two stored sentences state different locations.",
            "value": "",
            "evidence": [frame["document_id"] for frame in located],
            "contradictions": [frame["document_id"] for frame in located],
            "gaps": ["the stored locations disagree"],
            "abstained": True,
        }
    frame = located[0]
    sentence = f"{frame['agent']['text']} {frame['predicate']['text']} the {frame['patient']['text']} {frame['location']['text']}."
    if not _grounded(sentence, frame["sentence"]):
        return _empty("The location sentence used a word the source does not contain.")
    return _spoken("location", sentence, frame["location"]["text"], frame)


def _agent_answer(frames: list[dict[str, Any]]) -> dict[str, Any]:
    named = [frame for frame in frames if frame.get("agent")]
    if not named:
        return _empty("No stored sentence names who did that.")
    agents = {str(frame["agent"]["text"]).casefold() for frame in named}
    if len(agents) > 1:
        return {
            "ok": False,
            "kind": "agent",
            "text": "Two stored sentences name different people.",
            "value": "",
            "evidence": [frame["document_id"] for frame in named],
            "contradictions": [frame["document_id"] for frame in named],
            "gaps": ["the stored agents disagree"],
            "abstained": True,
        }
    frame = named[0]
    sentence = f"{frame['agent']['text']} {frame['predicate']['text']} the {frame['patient']['text']}."
    if not _grounded(sentence, frame["sentence"]):
        return _empty("The agent sentence used a word the source does not contain.")
    return _spoken("agent", sentence, frame["agent"]["text"], frame)


def _grounded(sentence: str, source: str) -> bool:
    source_tokens = {token.casefold() for token in _TOKEN.findall(source)}
    for token in _TOKEN.findall(sentence):
        lowered = token.casefold()
        if lowered in _FUNCTION:
            continue
        if lowered not in source_tokens:
            return False
    return True


def _spoken(kind: str, sentence: str, value: str, frame: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "kind": kind,
        "text": sentence,
        "value": value,
        "evidence": [frame["document_id"]],
        "contradictions": [],
        "gaps": [],
        "abstained": False,
    }


def _empty(gap: str) -> dict[str, Any]:
    return {
        "ok": False,
        "kind": "",
        "text": "",
        "value": "",
        "evidence": [],
        "contradictions": [],
        "gaps": [gap],
        "abstained": False,
    }

