"""Bounded source-grounded deduction with replayable proof steps.

Rules are application-owned. Source text supplies predicates, never executable
rules. Structured temporal/statistical/explanatory analyses use separate receipts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from copy import deepcopy
import hashlib
import json
import re

from cpu_llm.answerability import _sentences

SCHEMA = "grounded-inference-v1"
RULES = {
    "bigger_than.transitive.v1": "bigger_than(x,y) & bigger_than(y,z) -> bigger_than(x,z)",
    "membership.possession.v1": "member_of(x,c) & every_member_has(c,y) -> has(x,y)",
}
# Only these application-owned compositions are legal.
_BINARY_RULES = {
    "bigger_than.transitive.v1": ("bigger_than", "bigger_than", "bigger_than"),
    "membership.possession.v1": ("member_of", "every_member_has", "has"),
    "taxonomy.membership.v1": ("member_of", "subclass_of", "member_of"),
    "taxonomy.transitive.v1": ("subclass_of", "subclass_of", "subclass_of"),
    "physical_part.transitive.v1": ("physical_part_of", "physical_part_of", "physical_part_of"),
    "physical_part.location.v1": ("physical_part_of", "located_in", "located_in"),
    "membership.requirement.v1": ("member_of", "every_member_requires", "requires"),
}
for _rule, (_left, _right, _out) in _BINARY_RULES.items():
    RULES.setdefault(_rule, f"{_left}(x,y) & {_right}(y,z) -> {_out}(x,z)")
RULES["physical_part.inverse.v1"] = "physical_part_of(x,y) -> physically_contains(y,x)"
_RELATIONS = {"bigger_than", "has", "member_of", "subclass_of", "physical_part_of",
              "physically_contains", "located_in", "requires"}
_ASYMMETRIC = {'bigger_than', 'physical_part_of'}
_FAMILIES = ({"bigger_than"}, {"member_of", "subclass_of", "every_member_has", "has",
             "every_member_requires", "requires"},
             {"physical_part_of", "physically_contains", "located_in"})


def _family(relation):
    return next(family for family in _FAMILIES if relation in family)


def _applications(left, right=None):
    a, relation, b, negative = _triple(left)
    if negative:
        return []
    if right is None:
        return [("physical_part.inverse.v1", (b, "physically_contains", a, False))] if relation == "physical_part_of" else []
    c, other, d, neg = _triple(right)
    if neg or b != c:
        return []
    return [(rule, (a, out, d, False)) for rule, (r, o, out) in _BINARY_RULES.items()
            if relation == r and other == o]

_ENTITY = r"[A-Za-z][A-Za-z0-9 '’-]{0,99}?"
_COMMAND = re.compile(r"^(?:please\s+)?infer whether\s+(.+?)\s*[.?]?$", re.I)
_UNSAFE_ENTITY = re.compile(r"\b(?:and|or|in|at|during|with|without|from|on|under|over|after|before|while|because|but)\b|,", re.I)
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
            raise ValueError("Unsupported inference relation.")
        for label in ("subject", "object"):
            value = getattr(self, label)
            if not isinstance(value, str) or not re.fullmatch(_ENTITY, value):
                raise ValueError("Inference entities must be explicit names.")
            object.__setattr__(self, label, name(value))
            if not getattr(self, label):
                raise ValueError("Inference entities cannot be empty.")
            if _UNSAFE_ENTITY.search(value):
                raise ValueError("Inference requires atomic entity names without trailing clauses.")
            if _QUALIFIED.search(value) or re.match(r"^(?:every|all|no)\b", value, re.I):
                raise ValueError("Inference requires individual entities.")
        for field, ceiling in (("max_hops", 10), ("max_predicates", 256), ("max_states", 1024),
                               ("max_operations", 100_000)):
            value = getattr(self, field)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError(f"{field} must be an integer from 1 to {ceiling}.")


def request_from(message, option=None):
    from cpu_llm.evidence_analysis import analysis_request
    analysis = analysis_request(message, option)
    if analysis is not None:
        return analysis
    if option is not None:
        if not isinstance(option, dict):
            raise ValueError("inference must be a request object.")
        fields = dict(option)
        if fields.pop("mode", "deductive") != "deductive":
            raise ValueError("Unsupported inference mode.")
        try:
            return InferenceRequest(**fields)
        except TypeError as exc:
            raise ValueError("Inference request contains missing or unsupported fields.") from exc
    from cpu_llm.classifier import inference_prompt
    original = message
    message = inference_prompt(message)
    natural = not _COMMAND.fullmatch(original.strip())
    match = _COMMAND.fullmatch(message.strip())
    if not match:
        return None
    body = match[1].rstrip(".?")
    for relation, pattern in (
        ("bigger_than", rf"(?P<s>{_ENTITY}) is bigger than (?P<o>{_ENTITY})"),
        ("has", rf"(?P<s>{_ENTITY}) has (?P<o>{_ENTITY})"),
        ("member_of", rf"(?P<s>{_ENTITY}) is a member of (?P<o>{_ENTITY})"),
        ("subclass_of", rf"(?P<s>{_ENTITY}) is a subclass of (?P<o>{_ENTITY})"),
        ("physical_part_of", rf"(?P<s>{_ENTITY}) is a physical part of (?P<o>{_ENTITY})"),
        ("located_in", rf"(?P<s>{_ENTITY}) is located in (?P<o>{_ENTITY})"),
        ("requires", rf"(?P<s>{_ENTITY}) requires (?P<o>{_ENTITY})"),
        ("physically_contains", rf"(?P<s>{_ENTITY}) physically contains (?P<o>{_ENTITY})"),
    ):
        if parsed := re.fullmatch(pattern, body, re.I):
            try:
                return InferenceRequest(parsed["s"], relation, parsed["o"])
            except ValueError:
                if natural:
                    return None
                raise
    if natural:
        return None
    raise ValueError("Use Infer whether followed by a supported explicit relationship.")


def attach_inference(response, query, rows, *, snapshot=None, scope=None):
    """Share bounded rule proofs with research without promoting hypotheses."""
    prepared = PreparedInference(rows, snapshot=snapshot, scope=scope)
    candidates = []
    capped = False
    for family in _FAMILIES:
        probe = InferenceRequest('probe', sorted(family & _RELATIONS)[0], 'target')
        _, closure, truncated, _ = prepared.closure(probe)
        capped = capped or truncated
        for step in closure.values():
            subject, relation, obj, negative = step['conclusion']
            if step['rule'] == 'SOURCE' or negative or relation not in _RELATIONS:
                continue
            if not any(re.search(r'(?<!\w)' + re.escape(entity) + r'(?!\w)', query, re.I)
                       for entity in (subject, obj)):
                continue
            candidates.append((subject, relation, obj))
    targets = sorted(set(candidates))
    receipts = [prepared.deduce(InferenceRequest(*target)) for target in targets[:8]]
    response['research_inference'] = dict(triggered=True, mode='deductive', receipts=receipts,
        complete=not capped and len(targets) <= 8,
        outcome='partial' if capped or len(targets) > 8 else 'checked' if receipts else 'no_applicable_rule',
        hypothesis_promotion=False)
    response.setdefault('research_methods', {})['inference'] = {
        'outcome': response['research_inference']['outcome'], 'proof_count': len(receipts)}
    stages = response.setdefault('routing', {}).setdefault('post_stages', [])
    if 'inference' not in stages:
        stages.append('inference')
    lines = []
    for receipt in receipts:
        request = receipt['request']
        conclusion = f"{request['subject']} {request['relation']} {request['object']}"
        lines.append(f"{conclusion}: {receipt['verdict']}")
    if lines:
        text = response['reply']['text'] + '\n\nRule inference (source-grounded; hypotheses remain unverified):\n' + '\n'.join(lines)
        response['reply'].update(text=text, body=text)
    return response


def _extracted(rows):
    """Exact anchored clauses only. Negation remains part of the predicate."""
    found = []
    for row in sorted(rows, key=lambda item: item["document_id"]):
        chunk = row["chunk_text"]
        chunk_hash = hashlib.sha256(chunk.encode("utf8")).hexdigest()
        cursor = 0
        for sentence in _sentences(chunk):
            start = chunk.find(sentence, cursor)
            if start < 0:
                # The shared sentence splitter may normalize abbreviation/newline
                # whitespace. Such text cannot be used as an exact proof span.
                continue
            cursor = start + len(sentence)
            if _QUALIFIED.search(sentence) or sentence.startswith(('"', "'", "“", ">", "`", "#")):
                continue
            text = sentence.rstrip(".!?")
            for relation, pattern in (
                ("bigger_than", rf"(?P<s>{_ENTITY}) is (?P<neg>not )?bigger than (?P<o>{_ENTITY})"),
                ("every_member_has", rf"every (?P<s>{_ENTITY}) has (?P<o>{_ENTITY})"),
                ("has", rf"(?P<s>{_ENTITY}) (?P<neg>does not )?ha(?:s|ve) (?P<o>{_ENTITY})"),
                ("subclass_of", rf"every (?P<s>{_ENTITY}) is an? (?P<o>{_ENTITY})"),
                ("subclass_of", rf"(?P<s>{_ENTITY}) is (?P<neg>not )?a subclass of (?P<o>{_ENTITY})"),
                ("every_member_requires", rf"every (?P<s>{_ENTITY}) requires (?P<o>{_ENTITY})"),
                ("requires", rf"(?P<s>{_ENTITY}) (?P<neg>does not )?require(?:s)? (?P<o>{_ENTITY})"),
                ("physical_part_of", rf"(?P<s>{_ENTITY}) is (?P<neg>not )?a physical part of (?P<o>{_ENTITY})"),
                ("located_in", rf"(?P<s>{_ENTITY}) is (?P<neg>not )?located in (?P<o>{_ENTITY})"),
                ("physically_contains", rf"(?P<s>{_ENTITY}) (?P<neg>does not )?physically contain(?:s)? (?P<o>{_ENTITY})"),
                ("member_of", rf"(?P<s>{_ENTITY}) is (?P<neg>not )?a member of (?P<o>{_ENTITY})"),
                ("member_of", rf"(?P<s>{_ENTITY}) is (?P<neg>not )?an? (?P<o>{_ENTITY})"),
            ):
                match = re.fullmatch(pattern, text, re.I)
                if match:
                    if any(_UNSAFE_ENTITY.search(match[key]) for key in ("s", "o")):
                        continue
                    found.append(dict(
                        subject=name(match["s"]), relation=relation, object=name(match["o"]),
                        negative=bool(match.groupdict().get("neg")),
                        source=dict(document_id=row["document_id"], span=sentence, start=start,
                                    end=start + len(sentence), chunk_sha256=chunk_hash,
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
            applications = [(rule, conclusion, [left]) for rule, conclusion in _applications(left)]
            for right in values:
                operations += 1
                if operations > request.max_operations:
                    return steps, by_predicate, True
                applications.extend((rule, conclusion, [left, right])
                                    for rule, conclusion in _applications(left, right))
            for rule, conclusion, parents in applications:
                depth = max(parent['depth'] for parent in parents) + 1
                if depth <= request.max_hops:
                    additions.append(_new_step(conclusion, rule, [p['id'] for p in parents], None, depth))
        changed = False
        for step in sorted(additions, key=lambda item: (item["depth"], item["id"])):
            changed = add(step) or changed
        if capped or not changed:
            break
    return steps, by_predicate, capped


def verify_proof(proof, rows, request, *, _facts=None):
    """Replay every leaf and application, including semantic source binding."""
    allowed_facts = {_new_step(
        (f["subject"], f["relation"], f["object"], f["negative"]), "SOURCE", [], f["source"], 0
    )["id"] for f in (_extracted(rows) if _facts is None else _facts)}
    verified = {}
    for step in sorted(proof, key=lambda item: (item["depth"], item["id"])):
        if step["id"] != digest({key: value for key, value in step.items() if key != "id"}):
            return False
        if step["rule"] == "SOURCE":
            if step["id"] not in allowed_facts:
                return False
        else:
            inputs = step['inputs']
            if len(inputs) not in (1, 2) or not all(key in verified for key in inputs):
                return False
            parents = [verified[key] for key in inputs]
            applications = _applications(*parents)
            if (step['rule'], _triple(step)) not in applications:
                return False
            if step['depth'] != max(parent['depth'] for parent in parents) + 1:
                return False
            if step['depth'] > request.max_hops or step['source'] is not None:
                return False
        if step["id"] in verified:
            return False
        verified[step["id"]] = step
    return True


class PreparedInference:
    """Request-local snapshot; no state is shared between callers or requests."""

    def __init__(self, rows, *, snapshot=None, scope=None):
        from cpu_llm.access import source_allowed
        self.scope = sorted(scope) if scope is not None else None
        self.snapshot = deepcopy(snapshot)
        self.rows = [dict(document_id=row['document_id'], chunk_text=row['chunk_text'],
                          source_version=deepcopy(row.get('source_version')))
                     for row in rows if source_allowed(row['document_id'], self.scope)]
        if len({row['document_id'] for row in self.rows}) != len(self.rows):
            raise ValueError('Inference requires one active version of each chunk ID.')
        self.facts = _extracted(self.rows)
        self.input_digest = digest(sorted(
            (dict(document_id=row['document_id'], hash=hashlib.sha256(row['chunk_text'].encode('utf8')).hexdigest(),
                  source_version=row.get('source_version')) for row in self.rows), key=canonical))
        self._closures = {}

    def closure(self, request):
        family = _family(request.relation)
        key = (tuple(sorted(family)), request.max_hops, request.max_predicates,
               request.max_states, request.max_operations)
        if key not in self._closures:
            facts = [f for f in self.facts if f['relation'] in family]
            steps, predicates, capped = _closure(request, facts[:request.max_predicates])
            self._closures[key] = (steps, predicates, capped or len(facts) > request.max_predicates, len(facts))
        return self._closures[key]

    def deduce(self, request):
        return _deduce_prepared(self, request)


def deduce(rows, request, *, snapshot=None, scope=None):
    return PreparedInference(rows, snapshot=snapshot, scope=scope).deduce(request)


def _deduce_prepared(prepared, request):
    rows, snapshot, scope = prepared.rows, prepared.snapshot, prepared.scope
    steps, predicates, cap, fact_count = prepared.closure(request)
    target = request.subject, request.relation, request.object, False
    goals = [predicates[key] for key in (target, (*target[:3], True)) if key in predicates]
    if request.relation in _ASYMMETRIC:
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
        if r in _ASYMMETRIC and not negative and (reverse := predicates.get((o, r, s, False))):
            collect(reverse["id"])
            conflict = True
    proof = sorted((steps[key] for key in needed), key=lambda step: (step["depth"], step["id"]))
    verdict = "BUDGET_EXHAUSTED" if cap else (
        "CONFLICT" if conflict else "ENTAILED_BY_RULES" if target in predicates else
        "CONTRADICTED_BY_RULES" if (*target[:3], True) in predicates else "INSUFFICIENT_SUPPORT"
    )
    if not verify_proof(proof, rows, request, _facts=prepared.facts):
        raise ValueError("Inference proof failed independent replay.")
    receipt = dict(schema=SCHEMA, mode="deductive", request=asdict(request),
                   scope=scope, snapshot=snapshot, rules=RULES, verdict=verdict,
                   proof=proof, conclusion=list(target) if verdict == "ENTAILED_BY_RULES" else None,
                   predicate_count=fact_count, visited_states=len(steps),
                   completion="resource_cap" if cap else "bounded_closure",
                   proof_verified=True)
    receipt["input_digest"] = prepared.input_digest
    receipt["audit_hash"] = digest(receipt)
    # Returning a proof must not expose cached steps or the global registry to mutation.
    return deepcopy(receipt)


def verify_receipt(receipt, rows):
    """Recompute the requested result and digest from the authorized snapshot."""
    try:
        if receipt.get('schema') == 'structured-inference-v1':
            from cpu_llm.evidence_analysis import EvidenceAnalysisRequest, analyze
            return analyze(rows, EvidenceAnalysisRequest(**receipt['request']),
                           snapshot=receipt['snapshot'], scope=receipt['scope']) == receipt
        request = InferenceRequest(**receipt["request"])
        expected = deduce(rows, request, snapshot=receipt["snapshot"], scope=receipt["scope"])
        return expected == receipt
    except (KeyError, TypeError, ValueError):
        return False


def inference_response(message, tenant_id, status, text):
    """Consistent envelope for inference errors and ordinary service replies."""
    return dict(message=message, tenant_id=tenant_id, status=status, answer_status=status,
                answer=None, answer_evidence=[], supporting_evidence=[], audit_passed=False,
                needs_clarification=status == 'needs_clarification',
                routing=dict(post_stages=['inference'], execution_owner='inference_service'),
                reply=dict(text=text, body=text, answer_status=status, answer_evidence=[]))


def augment_retrieved_inference(response, message, *, as_of=None, scope=None):
    """Attach useful proofs from retrieved rows without replacing normal answers.

    No database access, no snapshot loading, and no implicit assertion that the
    retrieved subset is the complete knowledge base.
    """
    if (response.get('guard_decision') not in (None, 'allow') or response.get('delivery_blocked')
            or response.get('shine_enforced') or response.get('shine_ok') is False
            or response.get('grammar_ok') is False or response.get('__partial__')
            or response.get('__node_error__') or response.get('task_results')
            or response.get('answer_status') in {'blocked', 'refused', 'external_unverified'}):
        return response
    request = request_from(message)
    if not isinstance(request, InferenceRequest):
        return response
    selected = {}
    for row in [*(response.get('passages') or []), *(response.get('related') or [])]:
        identifier = row.get('document_id') or row.get('chunk_id')
        text = row.get('chunk_text')
        if identifier and isinstance(text, str):
            if identifier in selected and selected[identifier]['chunk_text'] != text:
                return response  # Conflicting active versions cannot form one proof.
            selected[identifier] = dict(document_id=identifier, chunk_text=text,
                                        source_version=row.get('source_version'))
    if not selected:
        return response
    receipt = deduce(list(selected.values()), request, snapshot=as_of, scope=scope)
    if receipt['verdict'] not in {'ENTAILED_BY_RULES', 'CONFLICT', 'CONTRADICTED_BY_RULES'}:
        return response
    response['inference'] = receipt
    response['inference_evidence_scope'] = 'retrieved_subset'
    response.setdefault('routing', {}).setdefault('post_stages', []).append('inference')
    return response


def execute_inference(app, message, request, *, caller=None, as_of=None, strict=False):
    from cpu_llm.invention import _snapshot
    from cpu_llm.pipeline import _caller_for

    context = _caller_for(app, caller)
    allowed = None if context is None else context.allowed_sources
    result = inference_response(message, app.tenant_id, 'pending', '')

    def finish(status, text):
        result.update(status=status, answer_status=status,
                      reply=dict(text=text, body=text, answer_status=status,
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
    from cpu_llm.evidence_analysis import EvidenceAnalysisRequest, analyze
    if isinstance(request, EvidenceAnalysisRequest):
        receipt = analyze(rows, request, snapshot=when, scope=allowed)
        result['inference'] = receipt
        result['answer_evidence'] = receipt['evidence']
        result['judgment'] = dict(outcome=receipt['verdict'], verification='structured_source_analysis')
        statuses = {'CALCULATED': 'calculated', 'ESTIMATED': 'statistical_estimate', 'HYPOTHESES': 'hypotheses'}
        status = statuses.get(receipt['verdict'], 'insufficient_evidence')
        body = canonical({key: value for key, value in receipt.items()
                          if key not in {'evidence', 'audit_hash'}})
        if request.mode == 'abductive':
            body += '\nAbduction note: these explanations are unverified hypotheses and may be wrong.'
        elif request.mode == 'inductive':
            body += '\nStatistical note: this estimate depends on sampling and independence assumptions.'
        return finish(status, body)
    receipt = deduce(rows, request, snapshot=when, scope=sorted(allowed) if allowed is not None else None)
    result["inference"] = receipt
    result["judgment"] = dict(outcome=receipt["verdict"], verification="replayed_rule_proof")
    for step in receipt["proof"]:
        if step["source"] and step["source"] not in result["answer_evidence"]:
            result["answer_evidence"].append(step["source"])
    if receipt["verdict"] == "ENTAILED_BY_RULES":
        relation = {"bigger_than": "is bigger than", "member_of": "is a member of",
                    "subclass_of": "is a subclass of", "physical_part_of": "is a physical part of",
                    "located_in": "is located in"}.get(request.relation, request.relation.replace("_", " "))
        text = f"Derived from the cited records and registered rules: {request.subject} {relation} {request.object}."
        status = "derived_inference"
    elif receipt["verdict"] == "CONFLICT":
        text, status = "The records conflict on the requested inference or one of its premises.", "conflicting"
    elif receipt['verdict'] == 'CONTRADICTED_BY_RULES':
        text, status = 'The cited records explicitly contradict the requested relationship.', 'contradicted'
    elif receipt["verdict"] == "BUDGET_EXHAUSTED":
        text, status = "Inference stopped at its resource limit. The requested conclusion is unresolved.", "partial"
    else:
        text, status = "The authorized records do not establish the requested relationship within the hop limit.", "insufficient_evidence"
    text += "".join(f'\n[{item["document_id"]}] {item["span"]}' for item in result["answer_evidence"])
    return finish(status, text)
