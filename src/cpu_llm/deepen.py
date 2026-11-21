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

from cpu_llm.cycle_exploration import Budget, StopSearch
from cpu_llm.frontier import (
    CLAIM_STATUS, FrontierLimits, _CAUSAL, _Term, _bridge, _content, _malformed, _similarity, _sign, _tokens,
    build_graph, related, term_key, usable_term,
)

SCHEMA = 'deepen-v1'
STAGES = ['deepen_snapshot', 'deepen_links', 'deepen_evidence', 'deepen_plan']
_COMMAND = re.compile(r'^(?:please\s+)?deepen\s*:\s*(.*?)[\s.!?]*$', re.I | re.S)
_SETUP = re.compile(r'\b(?:we\s+(?:construct|constructed|train|trained|run|ran|measure|measured|evaluate|evaluated|'
                    r'vary|varied|sweep|swept|test|tested|compare|compared|simulate|simulated)|experiments?|datasets?|'
                    r'benchmarks?|ablations?|controlled|synthetic)\b', re.I)
_MAX_ITEMS = 6
_TEXT_FORMS = (
    ('chain', re.compile(r'^(?P<a>.+?) may (?:increase|reduce|constrain|contribute to|affect|support|undermine) '
                         r'(?P<c>.+?) through (?P<b>.+?)(?: \(read as .+\))?$', re.I)),
    ('convergent', re.compile(r'^(?P<a>.+?) and (?P<b>.+?) may (?:jointly (?:constrain|drive|support|undermine)|'
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


def parse_hypothesis(value):
    """Return (pattern, a, b, c, expected relations) from a Frontier hypothesis dict or its text.

    For a chain, the links are a -> b and b -> c. For a convergent pair, a -> c and b -> c. For a divergent
    pair, c -> a and c -> b.
    """
    if isinstance(value, dict):
        anchors = [a for a in value.get('anchors', []) if isinstance(a, str)]
        pattern = value.get('pattern')
        if pattern == 'chain' and value.get('via') and len(anchors) == 2:
            via = value['via'][0].split(' (read as ')[0]
            kinds = _edge_kinds(value)
            return 'chain', anchors[0], via, anchors[1], kinds
        if pattern in {'convergent', 'divergent'} and len(anchors) == 3:
            return pattern, anchors[0], anchors[1], anchors[2], _edge_kinds(value)
        value = value.get('text', '')
    if not isinstance(value, str) or not value.strip():
        raise ValueError('deepen needs a Frontier hypothesis or its text')
    text = value.strip().rstrip('.!?').strip()
    for pattern, form in _TEXT_FORMS:
        match = form.fullmatch(text)
        if match:
            return pattern, match['a'].strip(), match['b'].strip(), match['c'].strip(), []
    raise ValueError('Deepen reads hypotheses in the Frontier forms, for example '
                     '"A may constrain C through B." or "A and B may jointly drive C."')


def _edge_kinds(hypothesis):
    kinds = []
    for cite in hypothesis.get('citations', []):
        identity = (cite.get('subject'), cite.get('relation'), cite.get('object'))
        if identity not in kinds:
            kinds.append(identity)
    return [kind for _, kind, _ in kinds]


def _links(pattern, a, b, c):
    if pattern == 'chain':
        return [(a, b), (b, c)]
    if pattern == 'convergent':
        return [(a, c), (b, c)]
    return [(c, a), (c, b)]


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

    def __init__(self, rows):
        from cpu_llm.answerability import _sentences
        self.items = []
        for row in rows:
            for sentence in _sentences(row['chunk_text']):
                if 20 <= len(sentence) <= 700 and sentence in row['chunk_text']:
                    self.items.append((row, sentence, set(_content(_tokens(sentence)))))

    def with_terms(self, terms, *, at_least, pattern=None):
        found = []
        for row, sentence, stems in self.items:
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


def _link_evidence(graph, sentences, source, target, similar, expected):
    """Supporting edges, counter-evidence and co-mentions for one link."""
    s_term, t_term = _Term(term_key(source), source), _Term(term_key(target), target)
    support, counter = [], []
    for edge in graph.edges.values():
        if edge.kind not in _CAUSAL:
            continue
        left = _bridge(_Term(edge.subject_key, edge.subject), s_term, similar)
        right = _bridge(_Term(edge.object_key, edge.object), t_term, similar)
        if left is None or right is None:
            continue
        want, have = _direction(expected), _direction(edge.kind)
        opposite = want is not None and have is not None and have == -want
        (counter if opposite else support).append(_cite(edge))
    for subject_key, object_key in graph.negatives:
        if related(subject_key, s_term.key) and related(object_key, t_term.key):
            counter.append(dict(negated=True, subject=subject_key, object=object_key))
    co_mentions = [_cite(row, sentence) for _, row, sentence in sentences.with_terms([source, target], at_least=2)]
    if support and counter:
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
                support_count=len(support), counter_count=len(counter))


def _confounders(graph, outcome, exclude, similar):
    """Other causes of the outcome stated in the sources."""
    found, seen = [], set()
    o_term = _Term(term_key(outcome), outcome)
    excluded = [term_key(t) for t in exclude]
    for edge in sorted(graph.edges.values(), key=lambda e: (e.subject_key, e.kind)):
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


def run_deepen(hypothesis, rows, *, limits=None, encode=None):
    """Pure core: no database, no writes. Returns the ``deepen`` receipt."""
    pattern, a, b, c = parse_hypothesis(hypothesis)[:4]
    expected = parse_hypothesis(hypothesis)[4]
    limits = limits or FrontierLimits()
    budget = Budget(limits)
    budget.counters = dict(rounds=0, candidates=0, edges=0, bytes=0)
    graph = build_graph(rows, budget)
    edges = list(graph.edges.values())
    similar, encoded = _similarity(encode, edges)
    sentences = _Sentences(rows)
    links = []
    for index, (source, target) in enumerate(_links(pattern, a, b, c)):
        kind = expected[index] if index < len(expected) else None
        links.append(_link_evidence(graph, sentences, source, target, similar, kind))
    terms = [a, b, c]
    predictions = [dict(_cite(row, sentence), qualification='source_prediction')
                   for _, row, sentence in sentences.with_terms(terms, at_least=2,
                                                                pattern=re.compile(
                                                                    r'\b(?:predicts?|should|would|might|could|'
                                                                    r'hypothes[ei]s)\b', re.I))][:_MAX_ITEMS]
    outcome_terms = [c] if pattern != 'divergent' else [a, b]
    setups = [dict(_cite(row, sentence), measures=[t for t in terms if _mentions(stems, t)])
              for _, row, sentence in sentences.with_terms(terms, at_least=1, pattern=_SETUP)
              for stems in [set(_content(_tokens(sentence)))]][:_MAX_ITEMS]
    confounders = []
    for outcome in outcome_terms:
        confounders += _confounders(graph, outcome, [a, b, c], similar)
    confounders = confounders[:_MAX_ITEMS]
    statuses = [link['status'] for link in links]
    verdict = ('contested' if 'contested' in statuses or 'counter_only' in statuses else
               'all_links_supported' if all(s == 'supported' for s in statuses) else
               'partly_supported' if any(s == 'supported' for s in statuses) else 'unsupported')
    return dict(schema=SCHEMA, triggered=True, claim_status=CLAIM_STATUS, promotion='blocked', index_write=False,
                potentially_nondeterministic=True, pattern=pattern, terms=dict(a=a, b=b, c=c), links=links,
                verdict=verdict, predictions=predictions, setups=setups, confounders=confounders,
                test_plan=test_plan(pattern, a, b, c, confounders), relation_edges=len(graph.edges),
                bridge_check='encoder' if similar is not None else 'head_noun', encoded_terms=encoded,
                incomplete=not graph.complete, stop_reason=graph.stop_reason,
                budget_used=dict(budget.counters, seconds=round(budget.clock() - budget.started, 3)))


def format_reply(receipt, text):
    plan = receipt['test_plan']
    lines = [f'Deepen: {text}', f'Overall: {receipt["verdict"].replace("_", " ")}. This remains an unverified '
             'hypothesis; the evidence below is what the authorized sources state about each link.']
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

    if app.guard.check(message + '\n' + text).decision != 'allow' or allowed is not None and not allowed:
        return result('blocked', 'Request blocked.')
    if strict:
        return result('unsupported', 'Strict evidence mode disables Deepen.')
    try:
        parse_hypothesis(hypothesis)
    except ValueError as exc:
        return result('needs_clarification', str(exc))
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
    response = result('deepened', format_reply(receipt, text or f'{receipt["terms"]}'), receipt)
    response['answer_evidence'] = [c for link in receipt['links'] for c in link['support']][:100]
    return response


def clarification(app, message, text):
    """A Deepen clarification turn (for example a numbered follow-up with no Frontier answer to refer to)."""
    return dict(message=message, tenant_id=app.tenant_id, status='needs_clarification',
                answer_status='needs_clarification', answer=None, audit_passed=False, answer_evidence=[],
                reply=dict(text=text, body=text), needs_clarification=True,
                judgment=dict(outcome='needs_clarification', complete=False),
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
