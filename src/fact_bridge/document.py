"""Ask questions about an ingested document, with honest fallbacks.

    from cpu_llm.pipeline import Appliance
    from fact_bridge.document import ask_document

    with Appliance(namespace="hud-handbook") as app:
        app.ingest("handbook.pdf")
        r = ask_document(app, "Can I be excused for 5 workdays for National Guard duty?", grade="adult", session_id="u1")
        r.kind, r.verdict, r.text, r.citations

Order of answering (the first that applies wins):
  1. semantic memory: a supported who / where / color question is the joined event-frame sentence.
  2. fact_bridge over the retrieved chunks: YES / NO / CONTESTED / UNKNOWN / CAUSE. The trained extractor
     and writer run when the regex reader finds no rule and a checkpoint is on disk.
  3. scenario check: a number in the question ("5 workdays", "90 minutes") against a limit sentence in the
     document ("a maximum of 3 workdays", "more than 1 hour may not be scheduled"), only for question and rule
     shapes that map unambiguously to yes or no.
  4. extractive answer: the sentence that best covers the question's distinctive terms (IDF over this
     namespace's chunks), with its list items when it introduces a list.
  5. otherwise "I couldn't find this in the document", with the closest sections. An unrelated passage is never
     presented as the answer.
Follow-up questions ("what if...", "and after 15 years?") are resolved with the previous question of the session.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from cpu_llm.answering import situation_from_chunks
from fact_bridge import canon, convert, split_sentences, to_number

_STOP = set("""a an the of to in on at for from by with and or but if then than as is are was were be been being am do does
did can could may might must shall should will would i me my we our you your he she it its they them their this that these
those there here what which who whom whose when where why how much many any some each every all no not yes so up out about
into over under again more most other such only own same very just also get got have has had having employee employees
someone somebody one ones per""".split())
_QWORDS = {"what", "which", "who", "when", "where", "why", "how", "can", "could", "may", "is", "are", "do", "does", "will"}
_FOLLOW = re.compile(r"^(?:and |but |so |also )|^what (?:if|about)\b|\b(?:it|that|this|those|them|they)\b[?.]?\s*$|"
                     r"\bfor that\b|\bthe same\b|^(?:after|before|during) ", re.I)
_NUMBER_WORDS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())}
_NUM = r"(\d+(?:\.\d+)?|" + "|".join(_NUMBER_WORDS) + r")"
_UNIT = r"(minutes?|hours?|days?|workdays?|calendar days?|weeks?|months?|years?|pay periods?)"


@dataclass
class DocAnswer:
    kind: str                        # "safety" | "verdict" | "scenario" | "quote" | "unknown"
    text: str
    verdict: Optional[str] = None    # YES / NO / CONTESTED / CAUSE / SAFETY / None
    citations: list[str] = field(default_factory=list)
    coverage: float = 0.0
    query: str = ""
    safety: dict = field(default_factory=dict)


# ---------------------------------------------------------------- vocabulary statistics per namespace


def _terms(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", text.lower()):
        if w in _STOP or (len(w) < 3 and not w.isdigit()):
            continue
        out.append(w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w)
    return out


class _Stats:
    def __init__(self, chunks: list[str]):
        self.n = max(1, len(chunks))
        self.df = Counter(t for c in chunks for t in set(_terms(c)))

    def idf(self, term: str) -> float:
        return math.log((self.n + 1) / (self.df.get(term, 0) + 0.5))


def _stats(app) -> _Stats:
    """Term statistics over this namespace's chunks, rebuilt when the number of stored chunks changes."""
    db = getattr(app.index, "db", None)
    conn = getattr(db, "conn", None)
    if conn is None:
        return _Stats([])
    try:
        count = conn.execute("SELECT count(*) FROM psm_document_embeddings").fetchone()[0]
        cached = getattr(app, "_doc_stats", None)
        if cached is not None and getattr(app, "_doc_stats_count", None) == count:
            return cached
        chunks = [r[0] for r in conn.execute("SELECT chunk_text FROM psm_document_embeddings").fetchall()]
    except Exception:
        return _Stats([])
    app._doc_stats, app._doc_stats_count = _Stats(chunks), count
    return app._doc_stats


def _reset_stats(app) -> None:
    app._doc_stats = None


# ---------------------------------------------------------------- follow-ups


def _resolve_followup(app, session_id: Optional[str], question: str) -> str:
    memory = getattr(app, "_doc_sessions", None)
    if memory is None:
        memory = app._doc_sessions = {}
    previous = memory.get(session_id) if session_id else None
    content = [t for t in _terms(question)]
    resolved = question
    if previous and (_FOLLOW.search(question.strip()) or len(content) <= 2):
        keep = [t for t in _terms(previous) if t not in content][:8]
        resolved = f"{question} ({' '.join(keep)})"
    if session_id:
        memory[session_id] = resolved
    return resolved


# ---------------------------------------------------------------- scenario check

_LIMIT_PATTERNS = [
    # allowed up to N: "may be excused for a maximum of 3 workdays", "up to 40 hours", "may not exceed 32 hours"
    ("allow_max", re.compile(rf"\b(?:a maximum of|up to|not (?:to )?exceed|not in excess of|no more than|may not exceed|"
                             rf"not exceeding|for a period not in excess of)\s+{_NUM}\s+{_UNIT}", re.I)),
    # required above N: "in excess of 3 consecutive workdays must ... be supported by"
    ("require_over", re.compile(rf"\b(?:in excess of|more than|over|exceeding)\s+{_NUM}\s+(?:consecutive\s+)?{_UNIT}\b"
                                rf"[^.]*\bmust\b", re.I)),
    # forbidden above N: "breaks ... of more than 1 hour may not be scheduled"
    ("forbid_over", re.compile(rf"\b(?:more than|in excess of|over)\s+{_NUM}\s+{_UNIT}\b[^.]*\b(?:may not|must not|cannot|"
                               rf"shall not)\b", re.I)),
    # forbidden below N: "may not be advanced if ... lasts less than 2 consecutive days"
    ("forbid_under", re.compile(rf"\b(?:may not|must not|cannot)\b[^.]*\bless than\s+{_NUM}\s+(?:consecutive\s+)?{_UNIT}", re.I)),
]
_ASK_PERMIT = re.compile(r"^\s*(?:can|may|am i allowed|is it ok|could)\b|\bbe (?:excused|scheduled|granted|advanced)\b", re.I)
_ASK_REQUIRE = re.compile(r"\b(?:do i need|do i have to|is (?:a|an)?\s*\w+ (?:needed|required)|must i|need (?:a|an)\b|required)\b", re.I)


def _unit_norm(unit: str) -> str:
    u = unit.lower().replace("calendar ", "").replace("work", "")
    u = u.rstrip("s")
    return {"minute": "minute", "hour": "hour", "day": "day", "week": "week", "month": "month", "year": "year",
            "pay period": "pay period"}.get(u, u)


def _question_quantity(question: str) -> Optional[tuple[float, str]]:
    m = re.search(rf"\b{_NUM}\s+(?:consecutive\s+)?{_UNIT}\b", question, re.I)
    if not m:
        return None
    return to_number(m.group(1)), _unit_norm(m.group(2))


def _same_measure(q_value: float, q_unit: str, r_unit: str) -> Optional[float]:
    if q_unit == r_unit:
        return q_value
    names = {"minute": "minute", "hour": "hour", "day": "day", "week": "week", "month": "month", "year": "year"}
    if q_unit in names and r_unit in names:
        return convert(q_value, q_unit, r_unit)
    return None


def _scenario(question: str, sentences: list[tuple[str, float]]) -> Optional[DocAnswer]:
    qty = _question_quantity(question)
    if qty is None:
        return None
    q_value, q_unit = qty
    permit = bool(_ASK_PERMIT.search(question))
    require = bool(_ASK_REQUIRE.search(question)) and not permit
    if not (permit or require):
        return None
    for sentence, coverage in sentences:
        if coverage < 0.5:
            continue
        for kind, rx in _LIMIT_PATTERNS:
            m = rx.search(sentence)
            if not m:
                continue
            limit, r_unit = to_number(m.group(1)), _unit_norm(m.group(2))
            value = _same_measure(q_value, q_unit, r_unit)
            if value is None:
                continue
            shown = f"{q_value:g} {q_unit}{'s' if q_value != 1 else ''}"
            lim = f"{limit:g} {r_unit}{'s' if limit != 1 else ''}"
            if kind == "allow_max" and permit:
                ok = value <= limit
                text = (f"Yes. The handbook allows up to {lim}, and you asked about {shown}." if ok else
                        f"No. The handbook allows up to {lim}, and you asked about {shown}.")
            elif kind == "require_over" and require:
                ok = value > limit
                text = (f"Yes. It is required for more than {lim}, and you asked about {shown}." if ok else
                        f"No, not ordinarily. It is required only for more than {lim}, and you asked about {shown}.")
            elif kind == "forbid_over" and permit:
                ok = value <= limit
                text = (f"Yes. Only more than {lim} is not allowed, and you asked about {shown}." if ok else
                        f"No. More than {lim} is not allowed, and you asked about {shown}.")
            elif kind == "forbid_under" and permit:
                ok = value >= limit
                text = (f"Yes, that is not ruled out: the limit applies below {lim}, and you asked about {shown}." if ok else
                        f"No. It is not allowed for less than {lim}, and you asked about {shown}.")
            else:
                continue
            return DocAnswer("scenario", text, "YES" if ok else "NO", [sentence], coverage)
    return None


# ---------------------------------------------------------------- extractive selection


def _ranked_sentences(question: str, chunks: list[str], stats: _Stats) -> list[tuple[str, float]]:
    q_terms = list(dict.fromkeys(_terms(question)))
    if not q_terms:
        return []
    weights = {t: stats.idf(t) for t in q_terms}
    total = sum(weights.values()) or 1.0
    scored: dict[str, float] = {}
    for rank, chunk in enumerate(chunks):
        pieces = split_sentences(chunk)
        for i, sentence in enumerate(pieces):
            s_terms = set(_terms(sentence))
            cov = sum(w for t, w in weights.items() if t in s_terms) / total
            text = sentence
            if sentence.rstrip().endswith(":") and i + 1 < len(pieces):
                text = " ".join(pieces[i:i + 1 + min(10, len(pieces) - i - 1)])
                cov = max(cov, sum(w for t, w in weights.items() if t in set(_terms(text))) / total)
            score = cov - 0.01 * rank
            if score > scored.get(text, -1):
                scored[text] = score
    return sorted(((t, s) for t, s in scored.items()), key=lambda x: -x[1])


def _sections(chunks: list[str]) -> list[str]:
    out = []
    for c in chunks:
        m = re.match(r"^\s*(\d{1,2}[-.]\d{1,3})\.?\s+([A-Z][A-Z ,/()-]{3,60})", c)
        if m and m.group(0).strip() not in out:
            out.append(f"{m.group(1)} {m.group(2).strip().title()}")
    return out[:3]


# ---------------------------------------------------------------- entry point


def ask_document(app, question: str, *, grade=None, session_id: Optional[str] = None,
                 child_safety: Optional[bool] = None, k: int = 10, min_coverage: float = 0.55,
                 extractor=None) -> DocAnswer:
    """Answer `question` from the documents in `app`'s namespace. See the module docstring for the order."""
    first = app.ask(question, grade=grade, session_id=session_id, child_safety=child_safety)
    safety = first.get("child_safety") or {}
    frame = first.get("frame_result") or {}
    if first.get("frame") and frame.get("status") in {"answered", "missing", "ambiguous", "conflicting", "unsupported"}:
        spoken = ((first.get("reply") or {}).get("text") or frame.get("text") or "").strip()
        if spoken and not (frame.get("status") == "answered" and not first.get("frame_verified")):
            return DocAnswer("memory", spoken, str(frame.get("status")), list(frame.get("evidence") or []),
                             safety=safety)
    query = _resolve_followup(app, session_id, question)
    hits = app.index.search(query, top_k=k)
    chunks = list(dict.fromkeys([h.get("chunk_text") or "" for h in hits] +
                                [c["chunk_text"] for c in first.get("related") or []]))
    chunks = [c for c in chunks if c.strip()]
    stats = _stats(app)

    def fetch(q: str) -> list[str]:
        return [h.get("chunk_text") or "" for h in app.index.search(q, top_k=5)]

    found = situation_from_chunks(query, chunks, extractor=extractor, retrieve=fetch)
    if found is not None:
        out = DocAnswer("verdict", found["text"], found["verdict"], list(found["because"]), 1.0, query, safety)
        return _post(app, question, out, grade, safety)
    ranked = _ranked_sentences(query, chunks, stats)
    # 3. scenario check
    scen = _scenario(question, ranked[:12])
    if scen is not None:
        scen.query, scen.safety = query, safety
        return _post(app, question, scen, grade, safety)
    # 4. extractive answer, or 5. honest unknown
    if ranked and ranked[0][1] >= min_coverage:
        best, cov = ranked[0]
        return _post(app, question, DocAnswer("quote", best, None, [best], round(cov, 3), query, safety), grade, safety)
    near = _sections(chunks)
    text = "I couldn't find this in the document."
    if near:
        text += " The closest sections are: " + "; ".join(near) + "."
    return _post(app, question, DocAnswer("unknown", text, None, [], round(ranked[0][1], 3) if ranked else 0.0,
                                          query, safety), grade, safety)


def _post(app, question: str, out: DocAnswer, grade, safety: dict) -> DocAnswer:
    """Response-side safety checks on the final text (principles, K-12 output filter), and the session's check-in."""
    gate = app.child_safety
    if safety.get("action") == "off" or not gate.enabled:
        return out
    decision = gate.decide(question, out.text, grade, enabled=True, audit=False)
    if decision.action == "replace":
        return DocAnswer("safety", decision.text, "SAFETY", out.citations, out.coverage, out.query, decision.as_dict())
    if safety.get("action") == "check_in" and "check in" not in out.text:
        out.text = f"{out.text}\n\n{gate._template('check_in', decision.assessment)}" if decision.assessment else out.text
    return out
