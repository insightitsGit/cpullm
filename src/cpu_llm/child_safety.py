"""Deterministic child-safety gate (single turn, K-12). On by default; switchable off.

Follows the Retriever Labs construct: one student message, one response, the learner's grade band.

    assess(message, grade)    -> signal (yes / no / need_more_info), severity, category, subcategory, PPRA flags
    check_response(text, a)   -> which principles the response keeps or breaks
    decide(message, text, g)  -> allow / check_in / replace, the delivered text, escalate, and every reason

Safety is a gate, not an average: one hard failure replaces the response with a vetted reply for the category
and grade band, and high severity always sets `escalate` so a person is brought in.

Deterministic means: same input, same decision, every decision traceable to a rule id and config version.
The detector here is a conservative rule layer (`RuleDetector`) behind a small interface, so a trained CPU
classifier can be plugged in through `detector=` without changing the gate. All rules, idioms, PPRA topics,
principle checks and templates live in `data/child_safety.json` (versioned).

Status: unvalidated. Calibrate and validate against the Retriever Labs benchmark (worked keep/break examples,
age-flip subset, reliability targets) before relying on it.

Switches:
    Appliance(child_safety=False)            off for one appliance
    appliance.ask(..., child_safety=False)   off for one question
    CPU_LLM_CHILD_SAFETY=0                   off by environment (default on)
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol, Union

CONFIG_PATH = Path(__file__).parent / "data" / "child_safety.json"
SEVERITY_ORDER = {"none": 0, "low": 1, "need_more_info": 1, "mid": 2, "high": 3}
Grade = Union[int, str, None]


def enabled_by_default() -> bool:
    return os.environ.get("CPU_LLM_CHILD_SAFETY", "1").strip().lower() not in {"0", "false", "off", "no"}


def load_config(path: Optional[Path] = None) -> dict:
    return json.loads(Path(path or CONFIG_PATH).read_text())


# ---------------------------------------------------------------- results


@dataclass
class Assessment:
    signal: str                      # "yes" | "no" | "need_more_info"
    severity: str                    # "none" | "low" | "mid" | "high" | "need_more_info"
    category: Optional[str] = None   # affect | behavior | cognition | disclosure
    subcategory: Optional[str] = None
    rule_ids: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    ppra: list[str] = field(default_factory=list)
    grade_band: Optional[str] = None


@dataclass
class ResponseCheck:
    kept: list[str] = field(default_factory=list)
    broken: list[str] = field(default_factory=list)
    hard_failure: bool = False


@dataclass
class Decision:
    action: str                      # "allow" | "check_in" | "replace" | "off"
    text: str                        # what is delivered
    escalate: bool                   # bring in a person (high severity)
    assessment: Optional[Assessment]
    response: Optional[ResponseCheck]
    reasons: list[str] = field(default_factory=list)
    config_version: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------- detector interface


class Detector(Protocol):
    def assess(self, message: str, grade_band: Optional[str]) -> Assessment: ...


def _norm(text: str) -> str:
    text = (text or "").lower().replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", text)


def _strip_idioms(message: str, idioms: list, normalize) -> str:
    """Remove idioms before and after normalization: some idioms need words the normalizer drops ('lol')."""
    light = _norm(message)
    for idiom in idioms:
        light = idiom.sub(" ", light)
    text = normalize(light)
    for idiom in idioms:
        text = idiom.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


class Normalizer:
    """Lowercase, undo leetspeak inside words, squeeze stretched letters, expand slang and common misspellings."""

    def __init__(self, config: dict):
        spec = config.get("normalize") or {}
        self.slang = [(re.compile(k), v) for k, v in (spec.get("slang") or {}).items()]
        self.leet = spec.get("leet") or {}

    def __call__(self, text: str) -> str:
        t = _norm(text)
        if self.leet:
            def unleet(m: re.Match) -> str:
                word = m.group(0)
                if re.search(r"[a-z]", word) and re.search(r"[0-9@$]", word):
                    return "".join(self.leet.get(ch, ch) for ch in word)
                return word
            t = re.sub(r"[a-z0-9@$]+", unleet, t)
        t = re.sub(r"([a-z])\1{2,}", r"\1\1", t)
        for rx, repl in self.slang:
            t = rx.sub(repl, t)
        return re.sub(r"\s+", " ", t).strip()


class RuleDetector:
    """Conservative, context-aware rules. Idioms are removed first, so 'I could die of embarrassment' is not
    read as risk; ordinary feelings stay low (no intervention); ambiguous distress asks for more information."""

    def __init__(self, config: dict):
        self.normalize = Normalizer(config)
        self.idioms = [re.compile(p) for p in config["idioms"]]
        self.rules = [(r, [re.compile(p) for p in r["patterns"]]) for r in config["rules"]]
        self.ppra = {name: re.compile(p) for name, p in config["ppra"].items()}

    def rule_specs(self, ids: list[str]) -> list[dict]:
        return [r for r, _ in self.rules if r["id"] in ids]

    def assess(self, message: str, grade_band: Optional[str]) -> Assessment:
        text = _strip_idioms(message, self.idioms, self.normalize)
        best: Optional[dict] = None
        best_level = 0
        hits = []
        for rule, patterns in self.rules:
            if any(p.search(text) for p in patterns):
                severity = (rule.get("severity_by_band") or {}).get(grade_band or "", rule["severity"])
                hits.append((rule, severity))
                if SEVERITY_ORDER[severity] > best_level or best is None:
                    best, best_level = dict(rule, severity=severity), SEVERITY_ORDER[severity]
        ppra = [name for name, p in self.ppra.items() if p.search(_norm(message))]
        if best is None:
            return Assessment("no", "none", ppra=ppra, grade_band=grade_band)
        severity = best["severity"]
        signal = "need_more_info" if severity == "need_more_info" else "yes"
        return Assessment(signal, severity, best["category"], best["subcategory"],
                          rule_ids=[r["id"] for r, _ in hits], sources=sorted({r["source"] for r, _ in hits}),
                          ppra=ppra, grade_band=grade_band)


class SemanticDetector:
    """Frozen local sentence encoder (all-mpnet-base-v2, CPU) against a bank of risk and benign example sentences.

    Deterministic: fixed weights, no sampling. A message is flagged at an anchor's severity when its cosine to the
    nearest risk anchor reaches `high` (or `nmi` for a softer check-in) and beats the nearest benign anchor by
    `margin`. It only ever raises severity; the rule layer remains the floor.
    """

    def __init__(self, config: dict):
        spec = config.get("semantic") or {}
        self.spec = spec
        self.normalize = Normalizer(config)
        self.idioms = [re.compile(p) for p in config["idioms"]]
        self._model = None
        self._risk = None
        self._benign = None
        self.available = True

    def _load(self) -> bool:
        if self._model is not None:
            return True
        try:
            import pyarrow  # noqa: F401  # must load before torch; otherwise pyarrow faults on this machine
            import numpy as np
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(os.environ.get("CPU_LLM_SAFETY_ENCODER") or self.spec["model"],
                                              device="cpu")
            enc = lambda texts: np.asarray(self._model.encode(list(texts), normalize_embeddings=True))
            self._enc = enc
            self._risk = enc(a["text"] for a in self.spec["risk"])
            self._benign = enc(self.spec["benign"])
            return True
        except Exception as exc:  # encoder unavailable: the rule layer still runs, and the decision says so
            self.available = False
            self.error = f"{type(exc).__name__}: {exc}"
            return False

    def scores(self, message: str) -> tuple[float, Optional[dict], float]:
        text = _strip_idioms(message, self.idioms, self.normalize)
        if len(text) < 3 or not self._load():
            return 0.0, None, 0.0
        v = self._enc([text])[0]
        risk = self._risk @ v
        benign = self._benign @ v
        i = int(risk.argmax())
        return float(risk[i]), self.spec["risk"][i], float(benign.max())

    def assess(self, message: str, grade_band: Optional[str]) -> Optional[Assessment]:
        if not self.spec.get("enabled", True):
            return None
        sim, anchor, benign = self.scores(message)
        if anchor is None or sim - benign < self.spec["margin"]:
            return None
        if sim >= self.spec["high"]:
            severity = anchor["severity"]
        elif sim >= self.spec["nmi"]:
            severity = "need_more_info"
        else:
            return None
        return Assessment("need_more_info" if severity == "need_more_info" else "yes", severity, anchor["category"],
                          anchor["subcategory"], rule_ids=[f"semantic:{sim:.2f}"],
                          sources=["semantic anchor: " + anchor["text"]], grade_band=grade_band)


class ClassifierDetector:
    """Linear classifier on the frozen encoder's embeddings (trained by tools/safety_train_classifier.py).

    Tiered for proportionate response: P(high) >= `high` gives high; P(high) >= `check_in` gives a gentle check-in.
    Deterministic: the same embedding and the same weights always give the same probabilities.
    """

    def __init__(self, config: dict, semantic: SemanticDetector):
        import numpy as np
        spec = config.get("classifier") or {}
        data = json.loads((Path(__file__).parent / "data" / spec.get("path", "child_safety_clf.json")).read_text())
        self.np = np
        self.semantic = semantic
        self.classes = data["classes"]
        self.W = np.asarray(data["coef"])
        self.b = np.asarray(data["intercept"])
        self.high, self.check_in = spec.get("high", 0.5), spec.get("check_in", 0.25)
        self.trained_on = data.get("trained_on", "")
        self.last_p_high = 0.0

    def probabilities(self, message: str) -> Optional[dict]:
        sem = self.semantic
        text = _strip_idioms(message, sem.idioms, sem.normalize)
        if len(text) < 3 or not sem._load():
            return None
        z = self.W @ sem._enc([text])[0] + self.b
        p = self.np.exp(z - z.max())
        p = p / p.sum()
        return dict(zip(self.classes, (float(x) for x in p)))

    def assess(self, message: str, grade_band: Optional[str]) -> Optional[Assessment]:
        probs = self.probabilities(message)
        if not probs:
            return None
        p_high, p_mid = probs.get("high", 0.0), probs.get("mid", 0.0)
        self.last_p_high = p_high
        _, anchor, _ = self.semantic.scores(message)
        category = (anchor or {}).get("category", "cognition")
        sub = (anchor or {}).get("subcategory", "classifier")
        tag = [f"classifier:high={p_high:.2f},mid={p_mid:.2f}"]
        if p_high >= self.high:
            return Assessment("yes", "high", category, sub, rule_ids=tag, sources=["embedding classifier"],
                              grade_band=grade_band)
        if p_mid >= 0.5 and p_mid > p_high:
            return Assessment("yes", "mid", category, sub, rule_ids=tag, sources=["embedding classifier"],
                              grade_band=grade_band)
        if p_high >= self.check_in or p_high + p_mid >= 0.5:
            return Assessment("need_more_info", "need_more_info", category, sub, rule_ids=tag,
                              sources=["embedding classifier"], grade_band=grade_band)
        return None


class CombinedDetector:
    """Rules (the floor), the semantic anchors and the embedding classifier. The learned layers only raise
    severity. A rule-only hit inside an educational or play framing is lowered to a check-in, never to nothing."""

    def __init__(self, config: dict):
        self.rules = RuleDetector(config)
        self.semantic = SemanticDetector(config) if (config.get("semantic") or {}).get("enabled") else None
        self.classifier = None
        if self.semantic is not None and (config.get("classifier") or {}).get("enabled"):
            try:
                self.classifier = ClassifierDetector(config, self.semantic)
            except FileNotFoundError:
                self.classifier = None
        ctx = config.get("context_downgrade") or {}
        self.educational = re.compile(ctx["educational"]) if ctx.get("educational") else None
        self.play = re.compile(ctx["play"]) if ctx.get("play") else None
        self.accident = re.compile(ctx["accident"]) if ctx.get("accident") else None
        self.corroborate = bool((config.get("classifier") or {}).get("corroborate_high"))
        self.strong_high = float((config.get("classifier") or {}).get("strong_high", 1.01))

    def assess(self, message: str, grade_band: Optional[str]) -> Assessment:
        a = self.rules.assess(message, grade_band)
        sem = self.semantic.assess(message, grade_band) if self.semantic else None
        clf = self.classifier.assess(message, grade_band) if self.classifier else None
        strong = clf is not None and clf.severity == "high" and self.classifier.last_p_high >= self.strong_high
        if self.corroborate and clf is not None and clf.severity == "high" and not strong and a.severity in {"none", "low"} \
                and not (sem is not None and sem.severity in {"high", "mid", "need_more_info"}):
            # Crisis escalation needs a second signal: a classifier-only high becomes a gentle check-in.
            clf.severity, clf.signal = "need_more_info", "need_more_info"
            clf.rule_ids = clf.rule_ids + ["uncorroborated:check-in"]
        framed = _norm(message)
        in_context = any(rx is not None and rx.search(framed) for rx in (self.educational, self.play, self.accident))
        if in_context and sem is not None and sem.severity in {"high", "mid"} and a.severity in {"none", "low"} and not strong:
            # Explicit accident, play or school framing: a semantic-only alarm becomes a check-in, never nothing.
            sem.severity, sem.signal = "need_more_info", "need_more_info"
            sem.rule_ids = sem.rule_ids + ["context:educational-play-accident"]
        learned = [x for x in (sem, clf) if x]
        top = max(learned, key=lambda x: SEVERITY_ORDER[x.severity], default=None)
        if a.severity in {"high", "mid"} and (top is None or top.severity != "high"):
            framed = _norm(message)
            if any(rx is not None and rx.search(framed) for rx in (self.educational, self.play, self.accident)):
                a.severity, a.signal = "need_more_info", "need_more_info"
                a.rule_ids = a.rule_ids + ["context:educational-or-play"]
        # Age-calibrated rules (severity_by_band) set the level for their subcategory; only a very confident
        # classifier (strong_high) can override them, never the semantic anchors alone.
        if top is not None and a.rule_ids and any(r.get("severity_by_band") for r in self.rules.rule_specs(a.rule_ids)) \
                and not (clf is not None and clf.severity == "high" and strong):
            if top.severity == "high" and SEVERITY_ORDER[a.severity] < SEVERITY_ORDER["mid"]:
                # An age rule may soften a learned high, but a supportive reply stays the floor.
                a.severity, a.signal = "mid", "yes"
                a.rule_ids = a.rule_ids + top.rule_ids + ["age-calibrated:floor-mid"]
            return a
        if top is not None and SEVERITY_ORDER[top.severity] > SEVERITY_ORDER[a.severity]:
            top.ppra = a.ppra
            top.rule_ids = a.rule_ids + top.rule_ids
            return top
        return a


# ---------------------------------------------------------------- the gate


class ChildSafetyGate:
    def __init__(self, config: Optional[dict] = None, *, enabled: Optional[bool] = None,
                 detector: Optional[Detector] = None, on_escalate=None, audit_path: Optional[Path] = None):
        self.config = config or load_config()
        self.enabled = self.config.get("enabled", True) if enabled is None else enabled
        self.detector = detector or CombinedDetector(self.config)
        self.checks = {name: dict(spec, rx=re.compile(spec.get("pattern") or spec.get("required")))
                       for name, spec in self.config["response_checks"].items()}
        self._output_patterns = {name: re.compile(p) for name, p in
                                 ((self.config.get("output_filter") or {}).get("patterns") or {}).items()}
        # Escalation hook: called with the audit record whenever a decision escalates (connect alerting here).
        self.on_escalate = on_escalate
        log = audit_path or os.environ.get("CPU_LLM_SAFETY_LOG") or (self.config.get("audit") or {}).get("log_path")
        self.audit_path = Path(log) if log else None

    def conversation(self, session_id: Optional[str] = None) -> "Conversation":
        return Conversation(self, session_id)

    # grade -> band
    def band(self, grade: Grade) -> Optional[str]:
        if grade is None:
            return None
        if isinstance(grade, str):
            g = grade.strip().lower()
            if g in self.config["grade_bands"]:
                return g
            if g in {"k", "kindergarten"}:
                grade = 0
            elif g.isdigit():
                grade = int(g)
            else:
                return None
        for name, (lo, hi) in self.config["grade_bands"].items():
            if lo <= int(grade) <= hi:
                return name
        return None

    def assess(self, message: str, grade: Grade = None) -> Assessment:
        return self.detector.assess(message, self.band(grade))

    def check_response(self, text: str, assessment: Assessment) -> ResponseCheck:
        result = ResponseCheck()
        low = _norm(text)
        for name, spec in self.checks.items():
            applies = spec.get("applies_at")
            if applies and assessment.severity not in applies:
                continue
            if "required" in spec:
                broken = not spec["rx"].search(low)
            else:
                broken = bool(spec["rx"].search(low))
            (result.broken if broken else result.kept).append(name)
            if broken and spec.get("hard"):
                result.hard_failure = True
        return result

    def _template(self, kind: str, assessment: Assessment) -> str:
        t = self.config["templates"]
        band = assessment.grade_band or "default"
        if kind == "high":
            group = t["high"].get(assessment.category or "cognition", t["high"]["cognition"])
        elif kind == "blocked":
            return t["blocked_response"]
        else:
            group = t[kind]
        return group.get(band, group["default"]) if band != "default" else group["default"]

    def decide(self, message: str, response: Optional[str], grade: Grade = None, *,
               enabled: Optional[bool] = None, session_id: Optional[str] = None, audit: bool = True) -> Decision:
        d = self._decide(message, response, grade, enabled=enabled)
        if audit and d.action != "off":
            _audit(self, d, message, session_id)
        return d

    def _decide(self, message: str, response: Optional[str], grade: Grade = None, *,
                enabled: Optional[bool] = None) -> Decision:
        version = self.config.get("version", "")
        on = self.enabled if enabled is None else enabled
        if not on:
            return Decision("off", response or "", False, None, None, ["child safety switched off"], version)
        a = self.assess(message, grade)
        reasons = [f"signal={a.signal} severity={a.severity}" + (f" ({a.category}/{a.subcategory})" if a.category else "")]
        if a.ppra:
            reasons.append("PPRA flags: " + ", ".join(a.ppra))
        if a.severity == "high":
            text = self._template("high", a)
            return Decision("replace", text, True, a, self.check_response(text, a),
                            reasons + ["high severity: vetted reply, escalate to a person"], version)
        if a.severity == "mid" and a.grade_band == "adult" and not any(
                r for r in a.rule_ids if not r.startswith(("semantic:", "classifier:", "uncorroborated", "context:"))):
            # Adults: a mid raised only by the learned layers is not acted on; rule-based mid still is.
            a.severity = "low"
        if a.severity == "mid":
            text = self._template("mid", a)
            return Decision("replace", text, False, a, self.check_response(text, a),
                            reasons + ["mid severity: proportionate supportive reply"], version)
        check = self.check_response(response or "", a)
        if check.hard_failure:
            return Decision("replace", self._template("blocked", a), False, a, check,
                            reasons + [f"response broke: {', '.join(check.broken)}"], version)
        adult = filter_output(self, response or "", grade)
        if adult:
            check.broken.append(f"output_filter:{adult}")
            return Decision("replace", self._template("blocked", a), False, a, check,
                            reasons + [f"K-12 output filter: {adult}"], version)
        if "proportional_response" in check.broken:
            return Decision("replace", self._template("blocked", a), False, a, check,
                            reasons + ["response over-reacts to an ordinary message"], version)
        if a.severity == "need_more_info" and a.grade_band == "adult":
            # Adults (workforce use): no check-ins on ambiguous wording; high and rule-based mid still apply.
            return Decision("allow", response or "", False, a, check, reasons + ["adult: no check-in"], version)
        if a.severity == "need_more_info":
            text = f"{response}\n\n{self._template('check_in', a)}" if response else self._template("check_in", a)
            return Decision("check_in", text, False, a, check, reasons + ["ambiguous: gentle check-in added"], version)
        return Decision("allow", response or "", False, a, check, reasons, version)


# ---------------------------------------------------------------- output filter (K-12)


def filter_output(gate: "ChildSafetyGate", text: str, grade: Grade) -> Optional[str]:
    """The name of the first adult-content category found in `text`, when the learner is K-12, else None."""
    spec = gate.config.get("output_filter") or {}
    if not spec.get("enabled") or not text:
        return None
    band = gate.band(grade)
    if band == "adult" or (band is None and not spec.get("assume_k12_when_grade_unknown", True)):
        return None
    low = _norm(text)
    for name, rx in gate._output_patterns.items():
        if rx.search(low):
            return name
    return None


# ---------------------------------------------------------------- audit log and escalation hook


def _audit(gate: "ChildSafetyGate", decision: "Decision", message: str, session_id: Optional[str]) -> None:
    spec = gate.config.get("audit") or {}
    if decision.action not in set(spec.get("log_actions") or []) and not decision.escalate:
        return
    a = decision.assessment
    record = {"time": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
              "session": session_id, "action": decision.action, "escalate": decision.escalate,
              "severity": a.severity if a else None, "category": a.category if a else None,
              "subcategory": a.subcategory if a else None, "grade_band": a.grade_band if a else None,
              "rules": a.rule_ids if a else [], "reasons": decision.reasons, "config_version": decision.config_version}
    if spec.get("log_message_text", True):
        record["message"] = message
    path = gate.audit_path
    if path is not None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a") as fh:
                fh.write(json.dumps(record) + "\n")
        except OSError:
            pass
    if decision.escalate and gate.on_escalate is not None:
        try:
            gate.on_escalate(record)
        except Exception as exc:  # a failing hook must never block the safe reply
            decision.reasons.append(f"escalation hook failed: {type(exc).__name__}")


# ---------------------------------------------------------------- multi-turn


class Conversation:
    """Per-session tracker: risk that builds over several turns is upgraded, and after a high the session stays
    escalated so later replies keep a person in the loop."""

    def __init__(self, gate: "ChildSafetyGate", session_id: Optional[str] = None):
        spec = gate.config.get("multi_turn") or {}
        self.gate = gate
        self.session_id = session_id
        self.window = int(spec.get("window", 5))
        self.weights = spec.get("weights") or {"low": 1, "need_more_info": 1, "mid": 2}
        self.upgrade_at = int(spec.get("upgrade_to_mid_at", 3))
        self.repeated_mid = bool(spec.get("escalate_on_repeated_mid", True))
        self.persist = int(spec.get("persist_after_high_turns", 3))
        self.history: list[Assessment] = []
        self.escalated = False
        self._since_high: Optional[int] = None

    def decide(self, message: str, response: Optional[str], grade: Grade = None, *,
               enabled: Optional[bool] = None) -> Decision:
        d = self.gate.decide(message, response, grade, enabled=enabled, session_id=self.session_id, audit=False)
        a = d.assessment
        if a is None:
            return d
        recent = self.history[-self.window:]
        score = sum(self.weights.get(x.severity, 0) for x in recent) + self.weights.get(a.severity, 0)
        if a.severity in {"low", "need_more_info"} and score >= self.upgrade_at and any(
                x.severity in {"low", "need_more_info", "mid"} for x in recent):
            a.severity, a.signal = "mid", "yes"
            a.rule_ids = a.rule_ids + [f"multi-turn:score={score}"]
            text = self.gate._template("mid", a)
            d = Decision("replace", text, False, a, self.gate.check_response(text, a),
                         d.reasons + [f"risk built over {len(recent) + 1} turns: supportive reply"], d.config_version)
        if a.severity == "mid" and self.repeated_mid and any(x.severity == "mid" for x in recent):
            d.escalate = True
            d.reasons.append("repeated mid-severity turns: escalate to a person")
        if a.severity in {"mid", "high"} and self.escalated and not d.escalate:
            d.escalate = True
            d.reasons.append("session already escalated: keep the person informed")
        if a.severity == "high" or d.escalate:
            self.escalated = True
            self._since_high = 0
        elif self._since_high is not None:
            self._since_high += 1
            if self._since_high <= self.persist and d.action in {"allow", "check_in"}:
                reminder = self.gate._template("check_in", a)
                d.text = f"{d.text}\n\n{reminder}" if d.text else reminder
                d.action = "check_in"
                d.reasons.append("session escalated earlier: keep a person in the loop")
        self.history.append(a)
        _audit(self.gate, d, message, self.session_id)
        return d
