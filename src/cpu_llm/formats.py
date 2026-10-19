"""Output formats for a request that asks for a document.

The catalog is the list of formats this system will produce. A request names
one of them and a topic. The spoken text then follows that format's fields.
A field that names a person or a date is filled only when a retrieved passage
states that role. The body is the retrieved sentences about the topic. A
missing topic or a missing format stays a question, and the catalog is the
answer to that question.

PrismCortex keeps each format as one graph node and does not store an
embedding for it. The node is a short record: name, aliases, a field bitmask,
a body code, and whether the layout cites sources. Retrieval skips it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

MISSING = "Not stated in the retrieved passages."

_STOP = frozenset(
    """
    a an the of to and or in on for with from by as is are was were be been being
    this that these those it its their his her they them you your we our not no nor
    but if then than into over after before about above below such only also just
    when where what which who whom how why can may known other during between across
    per via using used have has had does did done there here most more less very
    much many few please
    """.split()
)

_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)
_DATE_VALUE = (
    rf"(?:{_MONTHS})\s+\d{{1,2}}(?:,\s+\d{{4}})?"
    rf"|\d{{1,2}}\s+(?:{_MONTHS})(?:\s+\d{{4}})?"
    rf"|\d{{4}}-\d{{2}}-\d{{2}}"
)
_DATE = re.compile(rf"\b(?:dated|the date is|date is)\s+({_DATE_VALUE})\b", re.IGNORECASE)
_ROLE = {
    "to": re.compile(r"\b(?:addressed to|recipient is|written to)\s+([^.]{1,80})", re.IGNORECASE),
    "from": re.compile(r"\b(?:sender is|signed by|sent by|written by)\s+([^.]{1,80})", re.IGNORECASE),
    "attendees": re.compile(r"\b(?:attendees are|attendees were|present were)\s+([^.]{1,80})", re.IGNORECASE),
}
_ROLE["byline"] = _ROLE["from"]
_FIELD_LABEL = {
    "to": "To",
    "from": "From",
    "date": "Date",
    "subject": "Subject",
    "title": "Title",
    "attendees": "Attendees",
    "byline": "By",
}
_GAP_NAME = {
    "to": "recipient",
    "from": "sender",
    "date": "date",
    "attendees": "attendees",
    "byline": "byline",
}
_FIELD_ORDER = ("to", "from", "date", "subject", "title", "attendees", "byline")
_FIELD_BIT = {name: 1 << index for index, name in enumerate(_FIELD_ORDER)}
_BODY_CODE = {
    "paragraphs": "p",
    "numbered": "n",
    "checklist": "c",
    "faq": "q",
    "findings": "f",
    "recorded": "r",
    "bullets": "b",
}
_CODE_BODY = {code: name for name, code in _BODY_CODE.items()}
_VERB = re.compile(
    r"\b(?P<verb>write|draft|compose|create|prepare|produce|send|make)\b"
    r"(?:\s+me)?(?:\s+(?:an?|the))?\s+(?P<head>.+)$",
    re.IGNORECASE,
)
_GENERIC = re.compile(r"^(?:something|anything)(?:\s+(?P<rest>.*))?$", re.IGNORECASE)
_INNER_TOPIC = re.compile(r"\b(?:about|regarding|concerning|titled)\s+(.+)$", re.IGNORECASE)
_LEAD_TOPIC = re.compile(r"^(?:about|on|of|for)\s+(.+)$", re.IGNORECASE)
_RECIPIENT_ONLY = re.compile(r"to\s+\S+(?:\s+\S+){0,4}", re.IGNORECASE)
_TOPIC_CUE = re.compile(
    r"\b(?:about|regarding|concerning|titled|on|of|for)\s+(.+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OutputFormat:
    """One stored way to lay out a document."""

    id: str
    name: str
    aliases: tuple[str, ...]
    fields: tuple[str, ...]
    body: str
    sources: bool = False


OUTPUT_FORMATS: tuple[OutputFormat, ...] = (
    OutputFormat("email", "Email", ("e-mail", "emails", "email"), ("to", "from", "date", "subject"), "paragraphs"),
    OutputFormat("letter", "Letter", ("cover letter", "letters", "letter"), ("date", "to", "from", "subject"), "paragraphs"),
    OutputFormat("memo", "Memo", ("memorandum", "memos", "memo"), ("to", "from", "date", "subject"), "paragraphs"),
    OutputFormat(
        "document",
        "Document",
        ("documentation", "documents", "document", "doc"),
        ("title",),
        "numbered",
    ),
    OutputFormat("report", "Report", ("reports", "report"), ("title",), "findings", sources=True),
    OutputFormat("agenda", "Agenda", ("meeting agenda", "agenda"), ("title", "date"), "numbered"),
    OutputFormat(
        "minutes",
        "Minutes",
        ("meeting minutes", "meeting notes", "minutes"),
        ("title", "attendees", "date"),
        "recorded",
    ),
    OutputFormat("notice", "Notice", ("announcement", "bulletin", "notice"), ("title", "date"), "paragraphs"),
    OutputFormat(
        "checklist",
        "Checklist",
        ("check list", "to-do list", "todo list", "checklist"),
        ("title",),
        "checklist",
    ),
    OutputFormat("faq", "FAQ", ("faqs", "faq"), ("title",), "faq"),
    OutputFormat("outline", "Outline", ("outline",), ("title",), "numbered"),
    OutputFormat(
        "status",
        "Status update",
        ("status update", "status report", "status"),
        ("subject", "date"),
        "bullets",
    ),
    OutputFormat("proposal", "Proposal", ("proposals", "proposal"), ("title", "to"), "bullets"),
    OutputFormat("briefing", "Briefing", ("executive brief", "briefing", "brief"), ("subject",), "bullets"),
    OutputFormat("essay", "Essay", ("essays", "essay"), ("title",), "paragraphs", sources=True),
    OutputFormat("article", "Article", ("articles", "article"), ("title", "byline"), "paragraphs", sources=True),
    OutputFormat("blog", "Blog post", ("blog article", "blog post", "blog"), ("title",), "paragraphs"),
    OutputFormat("press", "Press release", ("press release", "news release"), ("title", "date"), "paragraphs"),
    OutputFormat("abstract", "Abstract", ("abstracts", "abstract"), ("title",), "paragraphs"),
    OutputFormat(
        "paper",
        "Paper",
        ("research paper", "white paper", "papers", "paper"),
        ("title",),
        "findings",
        sources=True,
    ),
    OutputFormat("case", "Case study", ("case study",), ("title",), "findings", sources=True),
    OutputFormat("newsletter", "Newsletter", ("newsletters", "newsletter"), ("title", "date"), "paragraphs"),
    OutputFormat("speech", "Speech", ("speeches", "speech", "talk"), ("title",), "paragraphs"),
    OutputFormat("biography", "Biography", ("biographies", "biography", "bio"), ("title",), "paragraphs"),
    OutputFormat("review", "Review", ("reviews", "review"), ("title",), "paragraphs"),
    OutputFormat(
        "tutorial",
        "Tutorial",
        ("how-to guide", "how to guide", "how-to", "how to", "tutorial", "guide"),
        ("title",),
        "numbered",
    ),
    OutputFormat(
        "procedure",
        "Procedure",
        ("standard operating procedure", "runbook", "procedure", "sop"),
        ("title",),
        "numbered",
    ),
    OutputFormat("decision", "Decision record", ("decision record", "decision"), ("title",), "bullets", sources=True),
    OutputFormat("incident", "Incident report", ("incident report",), ("title", "date"), "findings", sources=True),
    OutputFormat(
        "invitation",
        "Invitation",
        ("meeting invitation", "meeting invite", "invitation", "invite"),
        ("to", "date", "subject"),
        "paragraphs",
    ),
    OutputFormat("post", "Post", ("linkedin post", "social post", "post"), ("title",), "bullets"),
)


def output_format_ids() -> tuple[str, ...]:
    """Every format id, in catalog order."""
    return tuple(item.id for item in _ACTIVE)


def catalog_text() -> str:
    """The format list, with the fields each format follows."""
    lines = ["Output formats:"]
    for item in _ACTIVE:
        fields = ", ".join(_FIELD_LABEL[field] for field in item.fields)
        lines.append(f"- {item.id}: {fields}, body")
    return "\n".join(lines)


def draft_trigger(message: str) -> list[str]:
    """Reasons this turn is a document order. Empty for an ordinary question."""
    order = parse_order(message)
    if order is None:
        return []
    reasons: list[str] = []
    if order.format_id is None:
        reasons.append("the prompt asks for a document and does not name an output format")
    else:
        reasons.append(f"the prompt asks for {_asks_for(order.format_id)}")
    if not order.topic:
        reasons.append("the prompt does not name a topic")
    return reasons


@dataclass(frozen=True)
class DraftOrder:
    """A document order parsed from the request. The format may still be unnamed."""

    format_id: Optional[str]
    topic: str


def parse_order(message: str) -> Optional[DraftOrder]:
    """The format and topic, or nothing when this is not a document order."""
    match = _VERB.search(message or "")
    if match is None:
        return None
    head = match.group("head").strip(" .?!")
    if not head:
        return None
    chosen = _format_at_start(head)
    if chosen is None:
        chosen = _format_at_end(head)
    if chosen is not None:
        return DraftOrder(chosen[0].id, _topic_from_rest(chosen[1]))
    generic = _GENERIC.match(head)
    if generic is not None:
        return DraftOrder(None, _topic_from_rest(generic.group("rest") or ""))
    if _LEAD_TOPIC.match(head):
        return DraftOrder(None, _topic_from_rest(head))
    return None


def render_draft(
    message: str,
    rows: list[dict[str, Any]],
    order: Optional[DraftOrder] = None,
) -> Optional[dict[str, Any]]:
    """The formatted document, or nothing when the request is not a document order."""
    if order is None:
        order = parse_order(message)
    if order is None:
        return None
    if order.format_id is None or not order.topic:
        return {
            "format": order.format_id,
            "topic": order.topic,
            "text": _incomplete(order),
            "missing": [],
            "sources": [],
            "formats": list(output_format_ids()),
        }
    fmt = _by_id(order.format_id)
    sentences, sources = _sentences_about(rows, order.topic)
    values, missing = _values(fmt, order.topic, rows)
    text = _render(fmt, order.topic, values, sentences, sources, missing)
    return {
        "format": fmt.id,
        "topic": order.topic,
        "text": text,
        "missing": missing,
        "sources": sources,
        "formats": list(output_format_ids()),
    }


def _incomplete(order: DraftOrder) -> str:
    if order.format_id is None and order.topic:
        lead = f"This request does not name an output format. The topic is {order.topic}."
        closing = "Name one of these formats."
    elif order.format_id is None:
        lead = "This request does not name an output format or a topic."
        closing = "Name one format and a topic."
    else:
        name = _asks_for(order.format_id)
        lead = f"This request asks for {name} and does not name a topic."
        closing = f"Name a topic to fill the {order.format_id}."
    return f"{lead}\n{catalog_text()}\n{closing}"


def _asks_for(format_id: str) -> str:
    name = _by_id(format_id).name.casefold()
    article = "an" if name[0] in "aeiou" else "a"
    return f"{article} {name}"


def _render(
    fmt: OutputFormat,
    topic: str,
    values: dict[str, str],
    sentences: list[str],
    sources: list[str],
    missing: list[str],
) -> str:
    lines = [fmt.name]
    lines.extend(f"{_FIELD_LABEL[field]}: {values[field]}" for field in fmt.fields)
    lines.append("")
    lines.extend(_body_lines(fmt, topic, sentences))
    if fmt.sources and sources:
        lines.extend(["", "Sources:", *[f"- {item}" for item in sources]])
    if missing:
        names = ", ".join(_GAP_NAME[field] for field in missing)
        lines.extend(["", f"Not stated in the retrieved passages: {names}."])
    return "\n".join(lines).strip()


def _body_lines(fmt: OutputFormat, topic: str, sentences: list[str]) -> list[str]:
    if not sentences:
        return [f"The retrieved passages do not state anything about {topic}."]
    if fmt.body == "numbered":
        return [f"{index}. {sentence}" for index, sentence in enumerate(sentences, start=1)]
    if fmt.body == "checklist":
        return [f"- [ ] {sentence}" for sentence in sentences]
    if fmt.body == "faq":
        lines = [f"Q: {topic}"]
        lines.extend(f"A: {sentence}" for sentence in sentences)
        return lines
    if fmt.body == "findings":
        return ["Findings:", *[f"- {sentence}" for sentence in sentences]]
    if fmt.body == "recorded":
        return ["Recorded:", *[f"- {sentence}" for sentence in sentences]]
    if fmt.body == "bullets":
        return [f"- {sentence}" for sentence in sentences]
    return sentences


def _values(fmt: OutputFormat, topic: str, rows: list[dict[str, Any]]) -> tuple[dict[str, str], list[str]]:
    stated = _stated(rows)
    values: dict[str, str] = {}
    missing: list[str] = []
    for field in fmt.fields:
        if field in {"subject", "title"}:
            values[field] = topic
            continue
        value = stated.get(field)
        if value is None:
            values[field] = MISSING
            missing.append(field)
        else:
            values[field] = value
    return values, missing


def _stated(rows: list[dict[str, Any]]) -> dict[str, str]:
    found: dict[str, list[str]] = {field: [] for field in _ROLE}
    found["date"] = []
    for sentence in _all_sentences(rows):
        for field, pattern in _ROLE.items():
            match = pattern.search(sentence)
            if match is None:
                continue
            value = _role_value(match.group(1))
            if value and value.casefold() not in {item.casefold() for item in found[field]}:
                found[field].append(value)
        date_match = _DATE.search(sentence)
        if date_match is not None:
            value = date_match.group(1).strip()
            if value.casefold() not in {item.casefold() for item in found["date"]}:
                found["date"].append(value)
    stated: dict[str, str] = {}
    for field, values in found.items():
        if len(values) == 1:
            stated[field] = values[0]
        elif len(values) > 1:
            stated[field] = _conflict(field)
    return stated


def _conflict(field: str) -> str:
    if field == "to":
        return "The retrieved passages name more than one recipient."
    if field in {"from", "byline"}:
        return "The retrieved passages name more than one byline." if field == "byline" else "The retrieved passages name more than one sender."
    if field == "attendees":
        return "The retrieved passages name more than one attendee list."
    return "The retrieved passages name more than one date."


def _role_value(raw: str) -> str:
    value = " ".join(raw.strip(" .,:;").split())
    words = value.split()
    if not words or len(words) > 12:
        return ""
    return value


def _sentences_about(rows: list[dict[str, Any]], topic: str) -> tuple[list[str], list[str]]:
    wanted = _words(topic)
    sentences: list[str] = []
    sources: list[str] = []
    seen: set[str] = set()
    for row in rows:
        text = str(row.get("chunk_text") or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        source = str(row.get("chunk_id") or row.get("document_id") or "").strip()
        used = False
        for sentence in _split_sentences(text):
            if wanted & _words(sentence) and sentence not in sentences:
                sentences.append(sentence)
                used = True
        if used and source and source not in sources:
            sources.append(source)
    return sentences, sources


def _all_sentences(rows: list[dict[str, Any]]) -> list[str]:
    sentences: list[str] = []
    seen: set[str] = set()
    for row in rows:
        text = str(row.get("chunk_text") or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        for sentence in _split_sentences(text):
            if sentence not in sentences:
                sentences.append(sentence)
    return sentences


def _topic_from_rest(rest: str) -> str:
    text = (rest or "").strip(" .?!")
    inner = _INNER_TOPIC.search(text)
    if inner is not None:
        text = inner.group(1).strip()
    else:
        lead = _LEAD_TOPIC.match(text)
        if lead is not None:
            text = lead.group(1).strip()
        elif _RECIPIENT_ONLY.fullmatch(text):
            return ""
    text = text.strip(" .?!")
    if not _words(text):
        return ""
    return text


def _words(text: str) -> set[str]:
    words: set[str] = set()
    for token in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text or ""):
        for part in token.split("-"):
            key = part.casefold()
            if len(part) >= 3 and key not in _STOP:
                words.add(key)
    return words


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    merged: list[str] = []
    for part in parts:
        if merged and re.search(r"\b[A-Z]\.$", merged[-1]):
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return [part.strip() for part in merged if part.strip()]


def _format_at_start(head: str) -> Optional[tuple[OutputFormat, str]]:
    match = _START.match(head)
    if match is None:
        return None
    return _by_alias(match.group("alias")), match.group("rest") or ""


def _format_at_end(head: str) -> Optional[tuple[OutputFormat, str]]:
    match = _END.match(head)
    if match is None:
        return None
    rest = match.group("rest") or ""
    if not rest.strip():
        return None
    return _by_alias(match.group("alias")), rest


def _by_alias(alias: str) -> OutputFormat:
    return _ALIASES[alias.casefold()]


def _by_id(format_id: str) -> OutputFormat:
    return _IDS[format_id]


def _compile_aliases(
    formats: tuple[OutputFormat, ...],
) -> tuple[dict[str, OutputFormat], re.Pattern[str], re.Pattern[str]]:
    table: dict[str, OutputFormat] = {}
    aliases: list[str] = []
    for item in formats:
        for alias in item.aliases:
            table[alias.casefold()] = item
            aliases.append(alias)
    aliases.sort(key=len, reverse=True)
    body = "|".join(re.escape(alias) for alias in aliases)
    start = re.compile(rf"(?P<alias>{body})(?:\s+(?P<rest>.*))?$", re.IGNORECASE)
    end = re.compile(rf"(?P<rest>.*?)\s+(?P<alias>{body})$", re.IGNORECASE)
    return table, start, end


def bind_formats(formats: tuple[OutputFormat, ...] | None = None) -> None:
    """Use these formats for parsing. None restores the shipped catalog."""
    global _ACTIVE, _ALIASES, _START, _END, _IDS, _ALIAS_SPAN
    _ACTIVE = OUTPUT_FORMATS if formats is None else formats
    _ALIASES, _START, _END = _compile_aliases(_ACTIVE)
    _IDS = {item.id: item for item in _ACTIVE}
    aliases = sorted({alias for item in _ACTIVE for alias in item.aliases}, key=len, reverse=True)
    body = "|".join(re.escape(alias) for alias in aliases)
    _ALIAS_SPAN = re.compile(rf"\b(?:{body})\b", re.IGNORECASE)


def mentioned_format(message: str) -> tuple[OutputFormat, str] | None:
    """The longest format name in the message, and the topic named beside it."""
    matches = list(_ALIAS_SPAN.finditer(message or ""))
    if not matches:
        return None
    best = max(matches, key=lambda item: (len(item.group(0)), -item.start()))
    rest = f"{(message or '')[: best.start()]} {(message or '')[best.end() :]}"
    return _by_alias(best.group(0)), _cued_topic(rest)


def cued_topic(message: str) -> str:
    """The phrase after the last about, on, or for. Empty when no cue is there."""
    return _cued_topic(message or "")


def _cued_topic(text: str) -> str:
    found = list(_TOPIC_CUE.finditer(text))
    if not found:
        return ""
    topic = found[-1].group(1).strip(" .?!")
    if not _words(topic):
        return ""
    return topic


def remember_output_formats(store: Any) -> int:
    """Write any catalog format the graph does not already store. Returns how many were written."""
    from prismcortex.models import DeltaOp, Node, Operation, StateDelta

    existing = {node.id: node for node in store.all_nodes() if getattr(node, "kind", "") == "output_format"}
    ops = []
    for index, fmt in enumerate(OUTPUT_FORMATS):
        attributes = _record(fmt, index)
        current = existing.get(f"output-format:{fmt.id}")
        if current is not None and not current.embedding and _same_record(current.attributes, attributes):
            continue
        ops.append(
            DeltaOp(
                operation=Operation.ASSIMILATE,
                node=Node(
                    id=f"output-format:{fmt.id}",
                    label=f"output-format:{fmt.id}",
                    kind="output_format",
                    embedding=None,
                    attributes=attributes,
                ),
                reason="output format",
            )
        )
    if not ops:
        return 0
    store.apply(StateDelta(ops=ops))
    return len(ops)


def output_formats_from(store: Any) -> tuple[OutputFormat, ...]:
    """Formats stored in the graph, in catalog order."""
    decoded: list[tuple[int, OutputFormat]] = []
    for node in store.all_nodes():
        if getattr(node, "kind", "") != "output_format":
            continue
        fmt = _decode(dict(node.attributes))
        if fmt is not None:
            decoded.append((int(node.attributes.get("n", 10_000)), fmt))
    decoded.sort(key=lambda item: (item[0], item[1].id))
    return tuple(item[1] for item in decoded)


def install_output_formats(store: Any) -> tuple[OutputFormat, ...]:
    """Store the catalog, then parse from the graph copy."""
    remember_output_formats(store)
    loaded = output_formats_from(store)
    bind_formats(loaded or None)
    return _ACTIVE


def _record(fmt: OutputFormat, index: int) -> dict[str, Any]:
    return {
        "id": fmt.id,
        "name": fmt.name,
        "aliases": "|".join(fmt.aliases),
        "fields": sum(_FIELD_BIT[field] for field in fmt.fields),
        "body": _BODY_CODE[fmt.body],
        "sources": 1 if fmt.sources else 0,
        "n": index,
    }


def _same_record(stored: dict[str, Any], wanted: dict[str, Any]) -> bool:
    for key, value in wanted.items():
        current = stored.get(key)
        if key in {"fields", "sources", "n"}:
            if current is None or int(current) != int(value):
                return False
        elif current != value:
            return False
    return True


def _decode(attributes: dict[str, Any]) -> Optional[OutputFormat]:
    format_id = str(attributes.get("id") or "").strip()
    name = str(attributes.get("name") or "").strip()
    body = _CODE_BODY.get(str(attributes.get("body") or ""))
    if not format_id or not name or body is None:
        return None
    try:
        bits = int(attributes.get("fields") or 0)
    except (TypeError, ValueError):
        return None
    fields = tuple(field for field in _FIELD_ORDER if bits & _FIELD_BIT[field])
    if any(field not in _FIELD_LABEL for field in fields):
        return None
    aliases = tuple(part for part in str(attributes.get("aliases") or "").split("|") if part)
    if not aliases:
        return None
    return OutputFormat(format_id, name, aliases, fields, body, sources=bool(int(attributes.get("sources") or 0)))


_ACTIVE: tuple[OutputFormat, ...] = OUTPUT_FORMATS
_ALIASES, _START, _END = _compile_aliases(_ACTIVE)
_IDS = {item.id: item for item in _ACTIVE}
_ALIAS_SPAN = re.compile(r"$^")
bind_formats(OUTPUT_FORMATS)
