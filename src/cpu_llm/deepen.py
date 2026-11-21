"""Deepen: examine one hypothesis link by link over an authorized snapshot.

``Deepen: <hypothesis>.``, ``ask(..., deepen=<Frontier hypothesis or text>)`` or ``"deepen": ...`` on
``/v1/ask`` run this route. Frontier searches wide for candidate hypotheses; Deepen takes one and returns:

- evidence for and against each link (A -> B, B -> C, or each side of a pair), with a status per link;
- source predictions that name at least two of its terms;
- experiments or datasets in the sources that already measure one of its terms;
- confounders: other terms the sources say also drive the outcome;
- a test plan: what to vary, measure, block and control, and when the hypothesis fails.

It reuses Frontier's relation graph, related-term matching and encoder bridge check. Every output stays an
``UNVERIFIED_HYPOTHESIS`` with ``promotion: blocked``; nothing is written to the index; strict evidence disables it.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from cpu_llm.cycle_exploration import Budget, StopSearch
from cpu_llm.frontier import (
    CLAIM_STATUS, FrontierLimits, _CAUSAL, _Term, _bridge, _content, _malformed, _similarity, _sign, _tokens,
    build_graph, compose, related, term_key, usable_term,
)

SCHEMA = 'deepen-v1'
STAGES = ['deepen_snapshot', 'deepen_links', 'deepen_evidence', 'deepen_plan']
_COMMAND = re.compile(r'^(?:please\s+)?deepen\s*:\s*(.*?)[\s.!?]*$', re.I | re.S)
_SETUP = re.compile(r'\b(?:we\s+(?:construct|constructed|train|trained|run|ran|measure|measured|evaluate|evaluated|'
                    r'vary|varied|sweep|swept|test|tested|compare|compared|simulate|simulated)|experiments?|datasets?|'
                    r'benchmarks?|ablations?|controlled|synthetic)\b', re.I)
_MAX_ITEMS = 6
_TEXT_FORMS = (
    ('chain', re.compile(r'^(?P<a>.+?) may (?P<verb>increase|reduce|constrain|contribute to|affect|support|undermine) '
                         r'(?P<c>.+?) through (?P<b>.+?)$', re.I)),
    ('convergent', re.compile(r'^(?P<a>.+?) and (?P<b>.+?) may (?P<verb>jointly (?:constrain|drive|support|undermine)|'
                              r'interact in their effect on) (?P<c>.+?)(?:,.*)?$', re.I)),
    ('convergent', re.compile(r'^gains in (?P<c>.+?) from (?P<a>.+?) may be offset by (?P<b>.+?)$', re.I)),
    ('divergent', re.compile(r'^(?P<a>.+?) and (?P<b>.+?) may (?:move together|stand or fall together) because '
                             r'both (?:depend on|rest on) (?P<c>.+?)$', re.I)),
)


def deepen_seed(message, *, forced=False):
    """Return the hypothesis text, ``''`` when missing, or None for another route."""
    text = (message or '').strip()
    match = _COMMAND.fullmatch(text)
    if match:
        return match[1].strip()
    return text.rstrip('.!?').strip() if forced else None


@dataclass(frozen=True)
class HypothesisSpec:
    pattern: str
    a: str
    b: str
    c: str
    via: tuple[str, ...]
    expected: tuple[str | None, ...]
    relation: str | None

    def links(self):
        if self.pattern == 'chain':
            nodes = (self.a, *self.via, self.c)
            return list(zip(nodes, nodes[1:]))
        return [(self.a, self.c), (self.b, self.c)] if self.pattern == 'convergent' else [(self.c, self.a), (self.c, self.b)]


def _term(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 500 or '\x00' in value:
        raise ValueError('Hypothesis terms must be nonempty strings of at most 500 characters.')
    return re.split(r'\s+\(read as\s+', value.strip(), maxsplit=1, flags=re.I)[0]


def _edge_kinds(hypothesis):
    citations = hypothesis.get('citations', [])
    if not isinstance(citations, list) or len(citations) > 1000:
        raise ValueError('Hypothesis citations must be a bounded list of objects.')
    identities = []
    for cite in citations:
        if not isinstance(cite, dict):
            raise ValueError('Each hypothesis citation must be an object.')
        identity = (_term(cite.get('subject')), cite.get('relation'), _term(cite.get('object')))
        if not isinstance(identity[1], str) or identity[1] not in _CAUSAL | {'affects', 'is_a', 'alias_of', 'has'}:
            raise ValueError('Unsupported citation relation.')
        if identity not in identities:
            identities.append(identity)
    return identities


def read_hypothesis(value):
    """Validate used fields, preserve every mediator and the intended direction."""
    if isinstance(value, dict):
        if 'text' in value and not isinstance(value['text'], str):
            raise ValueError('Hypothesis text must be a string.')
        if any(key in value for key in ('pattern', 'anchors', 'via')):
            pattern, anchors = value.get('pattern'), value.get('anchors')
            if not isinstance(pattern, str) or pattern not in {'chain', 'convergent', 'divergent'} or not isinstance(anchors, list):
                raise ValueError('Hypothesis requires a supported pattern and a list of anchors.')
            if len(anchors) != (2 if pattern == 'chain' else 3):
                raise ValueError('Invalid number of hypothesis anchors.')
            anchors = [_term(a) for a in anchors]
            via = value.get('via', [])
            if not isinstance(via, list) or (not 1 <= len(via) <= 2 if pattern == 'chain' else bool(via)):
                raise ValueError('A chain needs one or two intermediary terms; other patterns need none.')
            via = tuple(_term(v) for v in via)
            citations = _edge_kinds(value)
            nodes = (anchors[0], *via, anchors[1]) if pattern == 'chain' else ()
            links = (list(zip(nodes, nodes[1:])) if pattern == 'chain' else
                     [(anchors[0], anchors[2]), (anchors[1], anchors[2])] if pattern == 'convergent' else
                     [(anchors[2], anchors[0]), (anchors[2], anchors[1])])
            # Match by endpoints, never by the order of optional source citations.
            kinds = []
            for source, target in links:
                found = {kind for left, kind, right in citations
                         if related(term_key(left), term_key(source)) and related(term_key(right), term_key(target))}
                if citations and not found:
                    raise ValueError('Citation relations must describe every path link.')
                kinds.append(next(iter(found)) if len(found) == 1 else None)
            relation = value.get('relation')
            if relation is not None and (not isinstance(relation, str) or relation not in {'increases', 'decreases', 'constrains', 'affects',
                    'causes', 'supports', 'undermines', 'jointly_drive', 'jointly_affect', 'jointly_support',
                    'jointly_undermine', 'co_constrain', 'offset', 'contested', 'common_driver', 'common_ground'}):
                raise ValueError('Unsupported hypothesis relation.')
            if pattern == 'chain':
                return HypothesisSpec(pattern, anchors[0], via[0], anchors[1], via,
                                      tuple(kinds), relation)
            return HypothesisSpec(pattern, *anchors, (), tuple(kinds), relation)
        value = value.get('text', '')
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise ValueError('deepen needs a bounded Frontier hypothesis or its text')
    text = value.strip().rstrip('.!?').strip()
    for pattern, form in _TEXT_FORMS:
        match = form.fullmatch(text)
        if match:
            a, c = (_term(match[key]) for key in ('a', 'c'))
            b = match['b'].strip()
            verb = match.groupdict().get('verb')
            relation = {'increase': 'increases', 'reduce': 'decreases', 'constrain': 'constrains',
                        'contribute to': 'causes', 'affect': 'affects', 'support': 'supports',
                        'undermine': 'undermines', 'jointly drive': 'jointly_drive',
                        'jointly constrain': 'co_constrain', 'jointly support': 'jointly_support',
                        'jointly undermine': 'jointly_undermine'}.get(verb.lower() if verb else None)
            via = tuple(_term(v) for v in re.split(r'\s+and\s+then\s+', b, flags=re.I)) if pattern == 'chain' else ()
            if len(via) > 2:
                raise ValueError('Frontier supports at most three path links.')
            count = len(via) + 1 if pattern == 'chain' else 2
            expected = (None,) * count
            if pattern == 'convergent':
                kind = {'jointly_drive': 'increases', 'co_constrain': 'constrains',
                        'jointly_support': 'supports', 'jointly_undermine': 'undermines'}.get(relation)
                expected = (kind, kind)
                if text.lower().startswith('gains in '):
                    expected, relation = ('increases', 'decreases'), 'offset'
            return HypothesisSpec(pattern, a, via[0] if via else _term(b), c, via, expected, relation)
    raise ValueError('Deepen reads hypotheses in the Frontier forms, for example '
                     '"A may constrain C through B." or "A and B may jointly drive C."')


def parse_hypothesis(value):
    """Compatibility view; execution uses read_hypothesis to retain the full path."""
    spec = read_hypothesis(value)
    return spec.pattern, spec.a, spec.b, spec.c, list(spec.expected)


def _cite(edge_or_row, quote=None):
    if quote is None:
        proof = edge_or_row.proofs[0]
        return dict(document_id=proof['document_id'], quote=proof['quote'], start=proof['start'],
                    end=proof['end'], chunk_sha256=proof['chunk_sha256'], relation=edge_or_row.kind,
                    subject=edge_or_row.subject, object=edge_or_row.object, hedged=edge_or_row.hedged)
    chunk = edge_or_row['chunk_text']
    start = chunk.find(quote)
    return dict(document_id=edge_or_row['document_id'], quote=quote, start=start, end=start + len(quote),
                chunk_sha256=hashlib.sha256(chunk.encode()).hexdigest())


def _mentions(stems, term):
    needed = set(_content(_tokens(term)))
    return bool(needed) and needed <= stems


class _Sentences:
    """Sentences of the snapshot with their content stems, built once per run."""

    def __init__(self, rows, budget=None):
        self.budget = budget
        from cpu_llm.answerability import _sentences
        self.items = []
        for row in rows:
            if self.budget: self.budget.check()
            for sentence in _sentences(row['chunk_text']):
                if self.budget: self.budget.check()
                if 20 <= len(sentence) <= 700 and sentence in row['chunk_text']:
                    self.items.append((row, sentence, set(_content(_tokens(sentence)))))

    def with_terms(self, terms, *, at_least, pattern=None):
        found = []
        for row, sentence, stems in self.items:
            if self.budget: self.budget.check()
            if pattern is not None and not pattern.search(sentence):
                continue
            hits = sum(_mentions(stems, term) for term in terms)
            if hits >= at_least:
                found.append((hits, row, sentence))
        found.sort(key=lambda item: -item[0])
        return found


def _direction(kind):
    """Sign of a relation for comparing directions; 'constrains' is capacity-positive (more A allows more B)."""
    return 1 if kind == 'constrains' else _sign(kind) if kind is not None else None


def _link_evidence(graph, sentences, source, target, similar, expected, budget=None):
    """Supporting edges, counter-evidence and co-mentions for one link."""
    s_term, t_term = _Term(term_key(source), source), _Term(term_key(target), target)
    support, counter = [], []
    for edge in graph.edges.values():
        if budget: budget.check()
        if edge.kind not in _CAUSAL:
            continue
        left = _bridge(_Term(edge.subject_key, edge.subject), s_term, similar)
        right = _bridge(_Term(edge.object_key, edge.object), t_term, similar)
        if left is None or right is None:
            continue
        want, have = _direction(expected), _direction(edge.kind)
        opposite = want is not None and have is not None and have == -want
        (counter if opposite else support).append(_cite(edge))
    observed = {item['relation'] for item in support + counter}
    negations = []
    for (subject_key, kind, object_key), proofs in graph.negatives.items():
        if budget: budget.check()
        if related(subject_key, s_term.key) and related(object_key, t_term.key):
            cited = [dict(proof, negated=True, relation=kind) for proof in proofs]
            negations.extend(cited)
            if kind == expected or kind in observed:
                counter.extend(cited)
    co_mentions = [_cite(row, sentence) for _, row, sentence in sentences.with_terms([source, target], at_least=2)]
    signs = {_direction(item['relation']) for item in support} - {None}
    if support and (counter or signs == {1, -1}):
        status = 'contested'
    elif support:
        status = 'supported'
    elif counter:
        status = 'counter_only'
    elif co_mentions:
        status = 'weak'
    else:
        status = 'missing'
    return dict(source=source, target=target, expected_relation=expected, status=status,
                support=support[:_MAX_ITEMS], counter=counter[:_MAX_ITEMS], co_mentions=co_mentions[:3],
                support_count=len(support), counter_count=len(counter), negations=negations[:_MAX_ITEMS],
                observed_relations=sorted(observed))


def _confounders(graph, outcome, exclude, similar, budget=None):
    """Other causes of the outcome stated in the sources."""
    found, seen = [], set()
    o_term = _Term(term_key(outcome), outcome)
    excluded = [term_key(t) for t in exclude]
    for edge in sorted(graph.edges.values(), key=lambda e: (e.subject_key, e.kind)):
        if budget: budget.check()
        if edge.kind not in _CAUSAL or _bridge(_Term(edge.object_key, edge.object), o_term, similar) is None:
            continue
        if any(related(edge.subject_key, key) for key in excluded) or edge.subject_key in seen:
            continue
        if _malformed(edge.subject) or not usable_term(edge.subject) or edge.subject.split()[0].endswith('ing'):
            continue                                   # a fragment or a gerund clause names no quantity to control
        seen.add(edge.subject_key)
        found.append(dict(term=edge.subject, relation=edge.kind, citation=_cite(edge)))
        if len(found) == _MAX_ITEMS:
            break
    return found


def test_plan(pattern, a, b, c, confounders):
    controls = [item['term'] for item in confounders]
    hold = ('Hold ' + ', '.join(controls) + ' fixed or record them as covariates.') if controls else (
        'The sources name no other cause of the outcome; record the main training or measurement settings.')
    if pattern == 'chain':
        return dict(design='mediation', manipulate=[a], measure=[c], mediator=b, controls=controls,
                    steps=[f'Vary {a} across matched settings and measure {c}.', hold,
                           f'Repeat with {b} held fixed or blocked to test whether it carries the effect.'],
                    fails_if=(f'{c} does not change when {a} varies with the controls fixed, or holding {b} fixed '
                              'leaves the effect unchanged.'))
    if pattern == 'convergent':
        return dict(design='2x2 factorial', manipulate=[a, b], measure=[c], mediator=None, controls=controls,
                    steps=[f'Run all four combinations of low and high {a} and {b}; measure {c}.', hold,
                           'Compare the joint effect with the sum of the separate effects.'],
                    fails_if=(f'Neither {a} nor {b} moves {c}, or their joint effect equals the sum of the separate '
                              'effects (no interaction or shifting bottleneck).'))
    return dict(design='common cause', manipulate=[c], measure=[a, b], mediator=None, controls=controls,
                steps=[f'Vary {c} and measure {a} and {b}.', hold,
                       f'Check whether {a} and {b} still co-vary when {c} is held fixed.'],
                fails_if=f'{a} and {b} co-vary just as strongly when {c} is held fixed, or {c} moves neither.')


def _direction_assessment(spec, links, budget):
    requested = spec.relation
    if spec.pattern != 'chain' or requested is None:
        return dict(requested=requested, status='unspecified', observed=[])
    kinds = None
    for link in links:
        budget.check()
        found = set(link['observed_relations'])
        if not found:
            return dict(requested=requested, status='unresolved', observed=[])
        if kinds is None:
            kinds = found
        else:
            combined = set()
            for left in kinds:
                for right in found:
                    step = compose(left, right)
                    combined.add(step[0] if step else 'affects')
            kinds = combined
    want = _direction(requested)
    matches, contrary, unknown = False, False, False
    for kind in kinds or ():
        if kind == requested or requested == 'affects':
            matches = True
        elif want is not None and _direction(kind) is not None:
            matches |= want == _direction(kind)
            contrary |= want == -_direction(kind)
        else:
            unknown = True
    status = ('contested' if matches and contrary else 'contradicted' if contrary and not matches and not unknown
              else 'consistent' if matches and not contrary and not unknown else 'unresolved')
    return dict(requested=requested, status=status, observed=sorted(kinds or ()),
                assumption='Cited effects compose across the same setting; this is not empirical validation.')


def run_deepen(hypothesis, rows, *, limits=None, encode=None, graph=None, similar=None, sentences=None, budget=None):
    """Pure source-bound analysis. Children share the parent's ledger, never reset it."""
    spec = read_hypothesis(hypothesis)
    pattern, a, b, c = spec.pattern, spec.a, spec.b, spec.c
    if budget is None:
        budget = Budget(limits or FrontierLimits())
        budget.counters = dict(rounds=0, candidates=0, edges=0, bytes=0)
    graph_reused = graph is not None
    encoded = None
    links, predictions, setups, confounders = [], [], [], []
    direction = dict(requested=spec.relation, status='unresolved', observed=[])
    stop_reason = None
    verdict = 'incomplete'
    try:
        budget.check()
        if graph is None:
            graph = build_graph(rows, budget)
            similar, encoded = _similarity(encode, list(graph.edges.values()), budget)
        sentences = sentences or _Sentences(rows, budget)
        for index, (source, target) in enumerate(spec.links()):
            budget.check()
            kind = spec.expected[index]
            links.append(_link_evidence(graph, sentences, source, target, similar, kind, budget))
        direction = _direction_assessment(spec, links, budget)
        terms = [a, *spec.via, c] if pattern == 'chain' else [a, b, c]
        predictions = [dict(_cite(row, sentence), qualification='source_prediction')
            for _, row, sentence in sentences.with_terms(terms, at_least=2,
                pattern=re.compile(r'\b(?:predicts?|should|would|might|could|hypothes[ei]s)\b', re.I))][:_MAX_ITEMS]
        outcome_terms = [c] if pattern != 'divergent' else [a, b]
        setups = [dict(_cite(row, sentence), measures=[t for t in terms if _mentions(stems, t)])
            for _, row, sentence in sentences.with_terms(terms, at_least=1, pattern=_SETUP)
            for stems in [set(_content(_tokens(sentence)))]][:_MAX_ITEMS]
        for outcome in outcome_terms:
            confounders += _confounders(graph, outcome, terms, similar, budget)
        confounders = confounders[:_MAX_ITEMS]
        budget.check()
        statuses = [link['status'] for link in links]
        verdict = ('contested' if 'contested' in statuses or 'counter_only' in statuses
                   or direction['status'] in {'contradicted', 'contested'} else
                   'partly_supported' if spec.relation is not None and direction['status'] == 'unresolved'
                   and pattern == 'chain' and any(s == 'supported' for s in statuses) else
                   'all_links_supported' if all(s == 'supported' for s in statuses) else
                   'partly_supported' if any(s == 'supported' for s in statuses) else 'unsupported')
    except StopSearch as exc:
        stop_reason = str(exc)
    incomplete = stop_reason is not None or graph is not None and not graph.complete
    if incomplete:
        verdict = 'incomplete'
    plan = test_plan(pattern, a, b, c, confounders)
    if pattern == 'chain':
        plan['mediators'] = list(spec.via)
        if len(spec.via) > 1:
            plan['mediator'] = None  # use the full ordered mediator list
            plan['steps'][-1] = ('Repeat with each mediator held fixed or blocked in turn ('
                                + ' -> '.join(spec.via) + ') to test every proposed link.')
    return dict(schema=SCHEMA, triggered=True, claim_status=CLAIM_STATUS, promotion='blocked', index_write=False,
                potentially_nondeterministic=True, pattern=pattern, terms=dict(a=a, b=b, c=c),
                path_nodes=[a, *spec.via, c] if pattern == 'chain' else None, links=links,
                expected_relation=spec.relation, direction_check=direction,
                verdict=verdict, predictions=predictions, setups=setups, confounders=confounders,
                test_plan=plan, relation_edges=len(graph.edges) if graph is not None else 0,
                bridge_check='encoder' if similar is not None else 'head_noun', encoded_terms=encoded,
                graph_reused=graph_reused, incomplete=bool(incomplete),
                stop_reason=stop_reason or (graph.stop_reason if graph is not None else None),
                budget_used=dict(budget.counters, seconds=round(budget.clock() - budget.started, 3)))


def format_reply(receipt, text):
    plan = receipt['test_plan']
    lines = [f'Deepen: {text}', f'Overall: {receipt["verdict"].replace("_", " ")}. This remains an unverified '
             'hypothesis; the evidence below is what the authorized sources state about each link.']
    if receipt['direction_check']['requested'] is not None:
        lines.append('End-to-end direction: ' + receipt['direction_check']['status'] + '.')
    for link in receipt['links']:
        lines.append(f'\nLink {link["source"]} -> {link["target"]}: {link["status"].replace("_", " ")} '
                     f'({link["support_count"]} supporting, {link["counter_count"]} contrary).')
        lines.extend(f'  + [{c["document_id"]}] {c["quote"]}' for c in link['support'][:3])
        lines.extend(f'  - [{c["document_id"]}] {c["quote"]}' for c in link['counter'][:3] if 'quote' in c)
        if not link['support'] and link['co_mentions']:
            lines.extend(f'  ~ [{c["document_id"]}] {c["quote"]}' for c in link['co_mentions'][:2])
    if receipt['predictions']:
        lines.append('\nSource predictions naming two or more of its terms:')
        lines.extend(f'  [{p["document_id"]}] {p["quote"]}' for p in receipt['predictions'][:4])
    if receipt['setups']:
        lines.append('\nExisting setups that measure one of its terms:')
        lines.extend(f'  [{s["document_id"]}] {s["quote"]}' for s in receipt['setups'][:4])
    if receipt['confounders']:
        lines.append('\nOther causes of the outcome in the sources (control these):')
        lines.extend(f'  {item["term"]} [{item["citation"]["document_id"]}]' for item in receipt['confounders'])
    lines.append(f'\nTest plan ({plan["design"]}):')
    lines.extend(f'  {number}. {step}' for number, step in enumerate(plan['steps'], 1))
    lines.append(f'  Fails if: {plan["fails_if"]}')
    if receipt['incomplete']:
        lines.append(f'\nEvidence search incomplete: {receipt["stop_reason"]}.')
    return '\n'.join(lines)


def execute_deepen(app, message, hypothesis, *, caller=None, as_of=None, strict=False):
    import psycopg
    from cpu_llm.invention import _snapshot
    from cpu_llm.pipeline import _caller_for

    context = _caller_for(app, caller)
    allowed = None if context is None else context.allowed_sources
    text = hypothesis.get('text', '') if isinstance(hypothesis, dict) else (hypothesis or '')

    def result(status, body, receipt=None):
        response = dict(message=message, tenant_id=app.tenant_id, status=status, answer_status=status, answer=None,
                        audit_passed=False, answer_evidence=[], reply=dict(text=body, body=body),
                        needs_clarification=status == 'needs_clarification',
                        judgment=dict(outcome=status, complete=status == 'deepened'),
                        routing=dict(schema='flag-routing-contract-v1', executed_nodes=[],
                                     post_stages=list(STAGES) if receipt else ['deepen_snapshot']))
        if receipt is not None:
            response['deepen'] = receipt
        return response

    if app.guard.check(message).decision != 'allow' or allowed is not None and not allowed:
        return result('blocked', 'Request blocked.')
    if strict:
        return result('unsupported', 'Strict evidence mode disables Deepen.')
    try:
        spec = read_hypothesis(hypothesis)
    except ValueError as exc:
        return result('needs_clarification', str(exc))
    if app.guard.check(message + '\n' + ' '.join([spec.a, *spec.via, spec.b, spec.c])).decision != 'allow':
        return result('blocked', 'Request blocked.')
    try:
        rows, when = _snapshot(app, allowed, as_of)
    except (ValueError, RuntimeError, psycopg.Error):
        return result('partial', 'The Deepen source snapshot was unavailable or exceeded its limit.')
    pipeline = getattr(app.index, 'pipeline', None)
    try:
        receipt = run_deepen(hypothesis, rows, encode=getattr(pipeline, 'encode_texts', None))
    except StopSearch as exc:
        return result('partial', f'The Deepen evidence search stopped: {exc}.')
    receipt['snapshot'] = dict(as_of=when, chunk_count=len(rows))
    response = result('partial' if receipt['incomplete'] else 'deepened', format_reply(receipt, text or f'{receipt["terms"]}'), receipt)
    response['answer_evidence'] = [c for link in receipt['links'] for c in link['support']][:100]
    return response


def clarification(app, message, text, *, status='needs_clarification'):
    """A Deepen clarification turn (for example a numbered follow-up with no Frontier answer to refer to)."""
    return dict(message=message, tenant_id=app.tenant_id, status=status,
                answer_status=status, answer=None, audit_passed=False, answer_evidence=[],
                reply=dict(text=text, body=text), needs_clarification=status == 'needs_clarification',
                judgment=dict(outcome=status, complete=False),
                routing=dict(schema='flag-routing-contract-v1', executed_nodes=[], post_stages=['deepen_snapshot']))


def finish_deepen_response(result):
    """Render the selected layout, then append the standard invention note once."""
    import html
    from cpu_llm.invention import NOTE
    from cpu_llm.output_rendering import render_response

    result = render_response(result)
    if 'deepen' not in result:
        return result
    rendered = result.get('rendered_response', {})
    suffix = '<p>' + html.escape(NOTE) + '</p>' if rendered.get('media_type') == 'text/html' else '\n\n' + NOTE
    text = result['reply']['text'] + suffix
    result['reply'].update(text=text, body=text)
    if rendered:
        rendered['text'] = text
    return result
