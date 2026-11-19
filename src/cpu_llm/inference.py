"""Bounded source-grounded deduction with replayable proof steps.

Rules are application-owned. Source text supplies predicates, never executable
rules. This first release supports strict ordering and universal possession.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re

from cpu_llm.answerability import _sentences

SCHEMA = "grounded-inference-v1"
RULES = {
    "bigger_than.transitive.v1": "bigger_than(x,y) & bigger_than(y,z) -> bigger_than(x,z)",
    "membership.possession.v1": "member_of(x,c) & every_member_has(c,y) -> has(x,y)",
}
_RELATIONS = {"bigger_than", "has"}
_ENTITY = r"[A-Za-z][A-Za-z0-9 '’-]{0,99}"
_COMMAND = re.compile(r"^(?:please\s+)?infer whether\s+(.+?)\s*[.?]?$", re.I)
_QUALIFIED = re.compile(r"\b(?:if|unless|may|might|could|would|should|allegedly|some|average|most|never)\b", re.I)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf8")).hexdigest()


def name(value):
    return re.sub(r"^(?:the|an?|every)\s+", "", " ".join(value.casefold().split())).strip()


@dataclass(frozen=True)
class InferenceRequest:
    subject: str
    relation: str
    object: str
    max_hops: int = 4
    max_predicates: int = 256
    max_states: int = 1024
    max_operations: int = 100_000

    def __post_init__(self):
        if self.relation not in _RELATIONS:
            raise ValueError("Inference supports bigger_than and has.")
        for label in ("subject", "object"):
            value = getattr(self, label)
            if not isinstance(value, str) or not re.fullmatch(_ENTITY, value):
                raise ValueError("Inference entities must be explicit names.")
            object.__setattr__(self, label, name(value))
            if not getattr(self, label):
                raise ValueError("Inference entities cannot be empty.")
            if _QUALIFIED.search(value) or re.match(r"^(?:every|all|no)\b", value, re.I):
                raise ValueError("Inference requires individual entities.")
        for field, ceiling in (("max_hops", 10), ("max_predicates", 256), ("max_states", 1024),
                               ("max_operations", 100_000)):
            value = getattr(self, field)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError(f"{field} must be an integer from 1 to {ceiling}.")


def request_from(message, option=None):
    if option is not None:
        if not isinstance(option, dict):
            raise ValueError("inference must be a request object.")
        fields = dict(option)
        if fields.pop("mode", "deductive") != "deductive":
            raise ValueError("Only deductive inference is implemented.")
        try:
            return InferenceRequest(**fields)
        except TypeError as exc:
            raise ValueError("Inference request contains missing or unsupported fields.") from exc
    match = _COMMAND.fullmatch(message.strip())
    if not match:
        return None
    body = match[1].rstrip(".?")
    for relation, pattern in (
        ("bigger_than", rf"(?P<s>{_ENTITY}) is bigger than (?P<o>{_ENTITY})"),
        ("has", rf"(?P<s>{_ENTITY}) has (?P<o>{_ENTITY})"),
    ):
        if parsed := re.fullmatch(pattern, body, re.I):
            return InferenceRequest(parsed["s"], relation, parsed["o"])
    raise ValueError("Use 'Infer whether X is bigger than Y' or 'Infer whether X has Y'.")


def _extracted(rows):
    """Exact anchored clauses only. Negation remains part of the predicate."""
    found = []
    for row in sorted(rows, key=lambda item: item["document_id"]):
        chunk = row["chunk_text"]
        cursor = 0
        for sentence in _sentences(chunk):
            start = chunk.find(sentence, cursor)
            if start < 0:
                raise ValueError("Source sentence is missing from its chunk.")
            cursor = start + len(sentence)
            if _QUALIFIED.search(sentence) or sentence.startswith(('"', "'", "“", ">", "`", "#")):
                continue
            text = sentence.rstrip(".!?")
            for relation, pattern in (
                ("bigger_than", rf"(?P<s>{_ENTITY}) is (?P<neg>not )?bigger than (?P<o>{_ENTITY})"),
                ("every_member_has", rf"every (?P<s>{_ENTITY}) has (?P<o>{_ENTITY})"),
                ("has", rf"(?P<s>{_ENTITY}) (?P<neg>does not )?ha(?:s|ve) (?P<o>{_ENTITY})"),
                ("member_of", rf"(?P<s>{_ENTITY}) is (?P<neg>not )?an? (?P<o>{_ENTITY})"),
            ):
                match = re.fullmatch(pattern, text, re.I)
                if match:
                    found.append(dict(
                        subject=name(match["s"]), relation=relation, object=name(match["o"]),
                        negative=bool(match.groupdict().get("neg")),
                        source=dict(document_id=row["document_id"], span=sentence, start=start,
                                    end=start + len(sentence), chunk_sha256=hashlib.sha256(chunk.encode("utf8")).hexdigest(),
                                    source_version=row.get("source_version")),
                    ))
                    break
    return sorted(found, key=canonical)


def _triple(step):
    return tuple(step["conclusion"])


def _new_step(conclusion, rule, inputs, source, depth):
    payload = dict(conclusion=list(conclusion), rule=rule, inputs=inputs, source=source, depth=depth)
    return dict(id=digest(payload), **payload)


def _closure(request, facts):
    steps = {}
    by_predicate = {}
    capped = False
    operations = 0

    def add(step):
        nonlocal capped
        key = _triple(step)
        if key in by_predicate:
            return False
        if len(steps) >= request.max_states:
            capped = True
            return False
        steps[step["id"]] = step
        by_predicate[key] = step
        return True

    for fact in facts:
        add(_new_step(
            (fact["subject"], fact["relation"], fact["object"], fact["negative"]),
            "SOURCE", [], fact["source"], 0,
        ))
    for _ in range(request.max_hops):
        additions = []
        values = sorted(by_predicate.values(), key=lambda item: (item["depth"], item["id"]))
        for left in values:
            a, relation, b, negative = _triple(left)
            if negative:
                continue
            for right in values:
                operations += 1
                if operations > request.max_operations:
                    return steps, by_predicate, True
                c, other, d, neg = _triple(right)
                if neg:
                    continue
                rule = None
                if relation == other == "bigger_than" and b == c:
                    rule = "bigger_than.transitive.v1"
                if relation == "member_of" and other == "every_member_has" and b == c:
                    rule = "membership.possession.v1"
                if rule:
                    depth = max(left["depth"], right["depth"]) + 1
                    if depth <= request.max_hops:
                        additions.append(_new_step(
                            (a, "has" if relation == "member_of" else relation, d, False),
                            rule, [left["id"], right["id"]], None, depth,
                        ))
        changed = False
        for step in sorted(additions, key=lambda item: (item["depth"], item["id"])):
            changed = add(step) or changed
        if capped or not changed:
            break
    return steps, by_predicate, capped


def verify_proof(proof, rows, request):
    """Replay every leaf and application, including semantic source binding."""
    allowed_facts = {_new_step(
        (f["subject"], f["relation"], f["object"], f["negative"]), "SOURCE", [], f["source"], 0
    )["id"] for f in _extracted(rows)}
    verified = {}
    for step in sorted(proof, key=lambda item: (item["depth"], item["id"])):
        if step["id"] != digest({key: value for key, value in step.items() if key != "id"}):
            return False
        if step["rule"] == "SOURCE":
            if step["id"] not in allowed_facts:
                return False
        else:
            if len(step["inputs"]) != 2 or not all(key in verified for key in step["inputs"]):
                return False
            left, right = (verified[key] for key in step["inputs"])
            a, relation, b, neg = _triple(left)
            c, other, d, negative = _triple(right)
            if neg or negative or b != c or step["depth"] != max(left["depth"], right["depth"]) + 1:
                return False
            if step["depth"] > request.max_hops:
                return False
            if step["rule"] == "bigger_than.transitive.v1":
                expected = (a, "bigger_than", d, False)
                if relation != "bigger_than" or other != relation:
                    return False
            elif step["rule"] == "membership.possession.v1":
                expected = (a, "has", d, False)
                if relation != "member_of" or other != "every_member_has":
                    return False
            else:
                return False
            if _triple(step) != expected or step["source"] is not None:
                return False
        if step["id"] in verified:
            return False
        verified[step["id"]] = step
    return True


def deduce(rows, request, *, snapshot=None, scope=None):
    if len({row["document_id"] for row in rows}) != len(rows):
        raise ValueError("Inference requires one active version of each chunk ID.")
    if scope is not None:
        from cpu_llm.access import source_allowed

        rows = [row for row in rows if source_allowed(row["document_id"], scope)]
    facts = _extracted(rows)
    relevant = {"bigger_than"} if request.relation == "bigger_than" else {"has", "member_of", "every_member_has"}
    facts = [fact for fact in facts if fact["relation"] in relevant]
    cap = len(facts) > request.max_predicates
    steps, predicates, state_cap = _closure(request, facts[:request.max_predicates])
    target = request.subject, request.relation, request.object, False
    goals = [predicates[key] for key in (target, (*target[:3], True)) if key in predicates]
    if request.relation == "bigger_than":
        reverse = request.object, request.relation, request.subject, False
        if reverse in predicates:
            goals.append(predicates[reverse])
    needed = set()

    def collect(identifier):
        if identifier in needed:
            return
        needed.add(identifier)
        for parent in steps[identifier]["inputs"]:
            collect(parent)

    for goal in goals:
        collect(goal["id"])
    proof = sorted((steps[key] for key in needed), key=lambda step: (step["depth"], step["id"]))
    conflict = False
    # Check premises in the selected proof and the conclusion, not unrelated facts.
    for step in list(proof):
        s, r, o, negative = _triple(step)
        opposite = predicates.get((s, r, o, not negative))
        if opposite:
            collect(opposite["id"])
            conflict = True
        if r == "bigger_than" and not negative and (reverse := predicates.get((o, r, s, False))):
            collect(reverse["id"])
            conflict = True
    proof = sorted((steps[key] for key in needed), key=lambda step: (step["depth"], step["id"]))
    verdict = "BUDGET_EXHAUSTED" if cap or state_cap else (
        "CONFLICT" if conflict else "ENTAILED_BY_RULES" if target in predicates else "INSUFFICIENT_SUPPORT"
    )
    if not verify_proof(proof, rows, request):
        raise ValueError("Inference proof failed independent replay.")
    receipt = dict(schema=SCHEMA, mode="deductive", request=asdict(request),
                   scope=scope, snapshot=snapshot, rules=RULES, verdict=verdict,
                   proof=proof, conclusion=list(target) if verdict == "ENTAILED_BY_RULES" else None,
                   predicate_count=len(facts), visited_states=len(steps),
                   completion="resource_cap" if cap or state_cap else "bounded_closure",
                   proof_verified=True)
    receipt["input_digest"] = digest(sorted(
        (dict(document_id=row["document_id"], hash=hashlib.sha256(row["chunk_text"].encode("utf8")).hexdigest(),
              source_version=row.get("source_version")) for row in rows), key=canonical
    ))
    receipt["audit_hash"] = digest(receipt)
    return receipt


def verify_receipt(receipt, rows):
    """Recompute the requested result and digest from the authorized snapshot."""
    try:
        request = InferenceRequest(**receipt["request"])
        expected = deduce(rows, request, snapshot=receipt["snapshot"], scope=receipt["scope"])
        return expected == receipt
    except (KeyError, TypeError, ValueError):
        return False


def execute_inference(app, message, request, *, caller=None, as_of=None, strict=False):
    from cpu_llm.invention import _snapshot
    from cpu_llm.pipeline import _caller_for

    context = _caller_for(app, caller)
    allowed = None if context is None else context.allowed_sources
    result = dict(message=message, tenant_id=app.tenant_id, answer=None,
                  answer_evidence=[], supporting_evidence=[], audit_passed=False,
                  needs_clarification=False, routing=dict(post_stages=["inference"]))

    def finish(status, text):
        result.update(status=status, answer_status=status,
                      reply=dict(text=text, answer_status=status,
                                 answer_evidence=result["answer_evidence"]))
        return result

    if app.guard.check(message).decision != "allow" or allowed is not None and not allowed:
        return finish("blocked", "Request blocked.")
    if strict:
        return finish("unsupported", "Rule inference requires standard evidence mode.")
    import psycopg

    try:
        rows, when = _snapshot(app, allowed, as_of)
    except (ValueError, RuntimeError, psycopg.Error):
        return finish("partial", "The authorized inference snapshot is unavailable or exceeds its limit.")
    receipt = deduce(rows, request, snapshot=when, scope=sorted(allowed) if allowed is not None else None)
    result["inference"] = receipt
    result["judgment"] = dict(outcome=receipt["verdict"], verification="replayed_rule_proof")
    for step in receipt["proof"]:
        if step["source"] and step["source"] not in result["answer_evidence"]:
            result["answer_evidence"].append(step["source"])
    if receipt["verdict"] == "ENTAILED_BY_RULES":
        relation = "is bigger than" if request.relation == "bigger_than" else "has"
        text = f"Derived from the cited records and registered rules: {request.subject} {relation} {request.object}."
        status = "derived_inference"
    elif receipt["verdict"] == "CONFLICT":
        text, status = "The records conflict on the requested inference or one of its premises.", "conflicting"
    elif receipt["verdict"] == "BUDGET_EXHAUSTED":
        text, status = "Inference stopped at its resource limit. The requested conclusion is unresolved.", "partial"
    else:
        text, status = "The authorized records do not establish the requested relationship within the hop limit.", "insufficient_evidence"
    text += "".join(f'\n[{item["document_id"]}] {item["span"]}' for item in result["answer_evidence"])
    return finish(status, text)


def graph_inference(state):
    """Graph adapter. Explicit requests use the same source-bound service."""
    if state.get("guard_decision") != "allow":
        return {}
    request = state.get("inference_request")
    if request is None:
        return {}
    if not isinstance(request, InferenceRequest):
        raise ValueError("Graph inference requires a validated request.")
    from cpu_llm.access import keep_allowed

    return {"inference": deduce(keep_allowed(state.get("passages") or [], state.get("allowed_sources")), request,
                               snapshot=state.get("as_of"),
                               scope=sorted(state["allowed_sources"]) if state.get("allowed_sources") is not None else None)}
