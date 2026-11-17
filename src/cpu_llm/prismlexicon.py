"""Opt-in, deterministic vocabulary adaptation at the reply boundary."""
from dataclasses import dataclass
from functools import wraps
import re

VERSION = "prismlexicon-contextual-v1"
LEVELS = frozenset(("A1", "A2", "B1", "B2", "C1", "C2", "auto", "off"))
_MAX_CHARS = 16_000
_MAX_CHANGES = 16
_CONTROL = re.compile(
    r"(?:\n|[?!.]\s+)(?:please )?use (?:CEFR (A1|A2|B1|B2|C1|C2) English"
    r"|(simple|advanced) English)\.?\s*$", re.I
)
_PROTECTED = re.compile(
    r'```[\s\S]*?```|`[^`]*`|"[^"]*"|“[^”]*”|‘[^’]*’|'
    r"(?<!\w)'[^'\n]*'(?!\w)|https?://[^\s]+|\[[^\]\n]+\](?:\([^\n)]*\))?"
    r"|(?m:^\s*(?:>|From |Sources:|Cited premises:)[^\n]*)"
)


@dataclass(frozen=True)
class Rule:
    sense: str
    target_sense: str
    pos: str
    gloss: str
    pattern: re.Pattern
    replacement: str


# Level policies below select a direction. These entries have no independently
# measured CEFR labels. Context and inflection are part of each approval.
_RULES = (
    Rule("bright.luminous", "strong.luminous", "adjective", "giving off strong light",
         re.compile(r"\b(?P<word>bright)(?= lights?(?:[.,;!?]|$| (?:appeared|shone|flashed)\b))"), "strong"),
    Rule("bright.intelligent", "clever.intelligent", "adjective", "quick to learn",
         re.compile(r"\b(?P<word>bright)(?= (?:student|students|child|children)\b)"), "clever"),
    Rule("reside.geographic", "live.geographic", "verb", "live in a place",
         re.compile(r"\b(?P<word>reside[sd]?)(?= in [A-Z][a-z]+\b)"), "live"),
    Rule("prior_to.temporal", "before.temporal", "preposition", "earlier than",
         re.compile(r"\b(?P<word>prior to)\b"), "before"),
)


def normalize_level(level):
    if not isinstance(level, str):
        raise ValueError("target_level must be off, auto, or A1 through C2")
    level = level.lower() if level.lower() in {"auto", "off"} else level.upper()
    if level not in LEVELS:
        raise ValueError("target_level must be off, auto, or A1 through C2")
    return level


def adapt_output(answer, target_level, *, protected_spans=()):
    level = normalize_level(target_level)
    receipt = dict(text=answer, requested_level=level, lexicon_version=VERSION,
                   applied_changes=[], abstentions=[], integrity_passed=True)
    if level in {"off", "B2", "C1", "C2"}:
        receipt["abstentions"].append("no_approved_rules_for_level" if level != "off" else "disabled")
        return receipt
    if len(answer) > _MAX_CHARS:
        receipt["abstentions"].append("character_budget")
        return receipt
    if answer.count("```") % 2 or answer.count("`") % 2 or answer.count('"') % 2 or answer.count("“") != answer.count("”"):
        receipt["abstentions"].append("unbalanced_protected_delimiter")
        return receipt
    locked = [match.span() for match in _PROTECTED.finditer(answer)]
    for start, end in protected_spans:
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(answer):
            receipt.update(integrity_passed=False, abstentions=["invalid_protected_span"])
            return receipt
        locked.append((start, end))
    candidates = []
    for rule in _RULES:
        for match in rule.pattern.finditer(answer):
            start, end = match.span("word")
            if any(start < right and end > left for left, right in locked):
                continue
            original = match["word"]
            replacement = rule.replacement
            if rule.sense == "reside.geographic":
                replacement += original[len("reside"):]
            candidates.append((start, end, original, replacement, rule))
    candidates.sort(key=lambda entry: (entry[0], entry[4].sense))
    parts = []
    cursor = shift = 0
    for start, end, original, replacement, rule in candidates[:_MAX_CHANGES]:
        if start < cursor:
            receipt.update(integrity_passed=False, applied_changes=[], abstentions=["overlapping_rules"])
            return receipt
        parts.extend((answer[cursor:start], replacement))
        receipt["applied_changes"].append(dict(
            input_span=[start, end], output_span=[start + shift, start + shift + len(replacement)],
            source_sense_id=rule.sense, target_sense_id=rule.target_sense,
            original=original, replacement=replacement, pos=rule.pos, cefr_level="unknown",
            source=VERSION, confidence="context_rule", checks=["approved_surface_form", "outside_protected_spans"],
            reason="reviewed_context_and_surface_form",
        ))
        cursor = end
        shift += len(replacement) - (end - start)
    parts.append(answer[cursor:])
    adapted = "".join(parts)
    for start, end in locked:
        offset = sum(
            len(change["replacement"]) - len(change["original"])
            for change in receipt["applied_changes"] if change["input_span"][1] <= start
        )
        if adapted[start + offset:end + offset] != answer[start:end]:
            receipt.update(integrity_passed=False, applied_changes=[], abstentions=["protected_span_changed"])
            return receipt
    receipt["text"] = adapted
    if len(candidates) > _MAX_CHANGES:
        receipt["abstentions"].append("change_budget")
    if not candidates:
        receipt["abstentions"].append("no_safe_contextual_match")
    return receipt


def lexical_delivery(ask):
    """Adapt the display copy once after the authorized answer is finalized."""
    @wraps(ask)
    def deliver(self, message, *args, **kwargs):
        level = kwargs.get("target_level")
        enabled = getattr(self, "prismlexicon", False)
        if level is not None:
            level = normalize_level(level)
        if (enabled and level is None and isinstance(message, str)
                and not any(mark in message for mark in ('`', '"', '“', '”'))
                and (control := _CONTROL.search(message))):
            level = normalize_level(control[1]) if control[1] else {"simple": "A2", "advanced": "C1"}[control[2].lower()]
            # Preserve the question terminator when the instruction follows it.
            end = control.start() + int(message[control.start()] in "?!." )
            message = message[:end].rstrip()
        response = ask(self, message, *args, **kwargs)
        if not enabled or level in {None, "off"}:
            return response
        reply = response.get("reply") or {}
        text = reply.get("text")
        if not isinstance(text, str):
            return response
        status = response.get("answer_status", reply.get("answer_status"))
        if (status != "answered" or response.get("rendered_response") or response.get("task_results")
                or response.get("invention") or response.get("nammade")
                or any(response.get(flag) for flag in ("math", "finance", "draft", "document", "style", "stylistic"))
                or kwargs.get("strict_evidence") or getattr(self, "strict_evidence", False)):
            response["prismlexicon"] = dict(requested_level=level, lexicon_version=VERSION,
                applied_changes=[], abstentions=["protected_response"], integrity_passed=True)
            return response
        spans = []
        for item in [*(response.get("answer_evidence") or []), *(response.get("supporting_evidence") or []),
                     *(reply.get("answer_evidence") or []), *(reply.get("supporting_evidence") or [])]:
            quote = item.get("span") or item.get("quote")
            if isinstance(quote, str) and quote:
                spans.extend(match.span() for match in re.finditer(re.escape(quote), text))
        receipt = adapt_output(text, level, protected_spans=spans)
        adapted = receipt.pop("text")
        response["prismlexicon"] = receipt
        if adapted != text:
            response["reply"] = dict(reply, text=adapted, original_text=text)
        return response
    return deliver
