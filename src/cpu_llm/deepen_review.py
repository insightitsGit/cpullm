"""Bounded, source-bound research assessments; never a hypothesis pruning stage."""
from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urlparse

from cpu_llm.frontier import _contains, _content, _tokens, related, term_key

_CONTEXT = {'domain', 'population', 'workload', 'model', 'version', 'regime', 'temperature'}
_QUALIFIER = re.compile(r'\b(?:not all|not every|some|only|unless|except|under|when|if|provided|'
                        r'assuming|may|might|could|for\s+(?:small|large|low|high))\b', re.I)
_VAGUE = re.compile(r'\b(?:substantial boost|different conclusions|sweet spot|large investments|'
                    r'various|something|intra\s*/|inter\s*-)\b', re.I)


def _text(value, name, cap=1000):
    if not isinstance(value, str) or not value.strip() or len(value) > cap or '\x00' in value:
        raise ValueError(f'{name} must be a nonempty string of at most {cap} characters.')
    return value.strip()


def request_options(value):
    """Unwrap a new options envelope without changing old hypothesis-object semantics."""
    options = dict(definitions={}, protocol={}, novelty=False, external_review=False)
    if not isinstance(value, dict) or 'hypothesis' not in value:
        return value, options
    if set(value) - {'hypothesis', *options}:
        raise ValueError('Unknown Deepen research option.')
    for key in ('novelty', 'external_review'):
        if type(value.get(key, False)) is not bool:
            raise ValueError(f'{key} must be a boolean.')
        options[key] = value.get(key, False)
    if options['external_review'] and not options['novelty']:
        raise ValueError('external_review also requires novelty=true.')
    definitions = value.get('definitions', {})
    if not isinstance(definitions, dict) or len(definitions) > 12:
        raise ValueError('definitions must be an object with at most 12 terms.')
    for term, fields in definitions.items():
        _text(term, 'definition term', 500)
        if not isinstance(fields, dict) or set(fields) - {'measurement', 'unit', 'levels', 'feasible', 'type'}:
            raise ValueError('Variable definitions support measurement, unit, levels, feasible and type.')
        clean = {}
        for key, item in fields.items():
            if key == 'type':
                from cpu_llm.variable_types import TYPES
                if item not in TYPES:
                    raise ValueError('type must be one of ' + ', '.join(TYPES) + '.')
                clean[key] = item
            elif key == 'feasible':
                if type(item) is not bool:
                    raise ValueError('feasible must be a boolean.')
                clean[key] = item
            elif key == 'levels':
                if not isinstance(item, list) or not 2 <= len(item) <= 12:
                    raise ValueError('levels needs 2 to 12 distinct labels.')
                clean[key] = [_text(level, 'level', 200) for level in item]
                if len(set(clean[key])) != len(clean[key]):
                    raise ValueError('Intervention levels must be distinct.')
            else:
                clean[key] = _text(item, key)
        normalized = term_key(term)
        if normalized in options['definitions']:
            raise ValueError('Definition terms must be distinct after normalization.')
        options['definitions'][normalized] = clean
    protocol = value.get('protocol', {})
    if not isinstance(protocol, dict) or set(protocol) - {'replicates', 'acceptance_criterion'}:
        raise ValueError('protocol supports replicates and acceptance_criterion.')
    if 'replicates' in protocol:
        n = protocol['replicates']
        if type(n) is not int or not 2 <= n <= 1_000_000:
            raise ValueError('replicates must be an integer from 2 to 1000000.')
        options['protocol']['replicates'] = n
    if 'acceptance_criterion' in protocol:
        options['protocol']['acceptance_criterion'] = _text(protocol['acceptance_criterion'], 'acceptance_criterion')
    return value['hypothesis'], options


def _context(row):
    context = row.get('research_context', {})
    context = context if isinstance(context, dict) else {}
    found = {k: v[:200] for k, v in context.items() if k in _CONTEXT and isinstance(v, str) and v.strip()}
    # Plain-text context labels survive the existing ingestion/SQL snapshot path.
    for match in re.finditer(r'(?im)^\s*(domain|population|workload|model|version|regime|temperature)\s*:\s*([^\n;]{1,200})',
                             row.get('chunk_text', '')):
        found.setdefault(match[1].lower(), match[2].strip())
    return found


def assess_composition(spec, links, rows, direction, budget):
    by_id = {row['document_id']: row for row in rows}
    qualifications, bridges, scopes = [], [], []
    for index, link in enumerate(links):
        for proof in link['support'] + link['counter']:
            budget.check()
            context = _context(by_id.get(proof['document_id'], {}))
            if context:
                scopes.append(dict(link=index, context=context, citation=proof))
            if _QUALIFIER.search(proof['quote']) or proof.get('hedged'):
                qualifications.append(dict(link=index, citation=proof,
                    instruction='Retain this full qualified statement; do not treat it as universal.'))
            for endpoint, requested in (('subject', link['source']), ('object', link['target'])):
                actual = proof.get(endpoint)
                if actual and term_key(actual) != term_key(requested):
                    contained = _contains(term_key(actual), term_key(requested))
                    bridges.append(dict(link=index, requested=requested, source_term=actual, citation=proof,
                        status='requires_review', kind='modifier' if contained else 'meaning',
                        reason=('Changed endpoint modifiers; check the direction and scope they imply.' if contained
                                else 'Different terms joined by similarity; similarity is not identity.')))
    scope_differences = []
    for field in sorted(_CONTEXT):
        budget.check()
        values = sorted({s['context'][field] for s in scopes if field in s['context']})
        if len(values) > 1:
            scope_differences.append(dict(field=field, values=values,
                reason='Different source settings; establish transferability before combining effects.'))
    status = ('incompatible_direction' if direction['status'] in {'contradicted', 'contested'} else
              'insufficient_evidence' if len(links) != len(spec.links()) or any(
                  l['status'] in {'missing', 'weak', 'counter_only'} for l in links) else
              'requires_review' if bridges or scope_differences or qualifications or any(
                  l['status'] in {'contested', 'bridge_mismatch'} for l in links) else 'conditional')
    return dict(status=status, bridges=bridges, qualifications=qualifications,
                source_contexts=scopes, scope_differences=scope_differences,
                context_coverage='explicit_context_available' if scopes else 'not_recorded',
                interaction=dict(status='untested' if spec.pattern == 'convergent' else 'not_applicable',
                    reason='Individual effects do not establish a joint interaction.'),
                assumptions=['Source terms denote compatible quantities and settings.',
                             'Composed source relationships are not causal identification.'],
                scientific_validity='not_established')


def classify_controls(items, spec, graph, budget):
    """A cause of the outcome alone is a candidate control, not a confounder."""
    exposures = ([spec.a] if spec.pattern in {'chain', 'direct'} else [spec.a, spec.b] if spec.pattern == 'convergent'
                 else [spec.c])
    for item in items:
        item.update(role='outcome_predictor', recommended_action='Review before adjustment; not an established confounder.')
        causes_exposure, downstream = [], []
        for edge in graph.edges.values():
            budget.check()
            if edge.kind not in {'causes', 'increases', 'decreases', 'constrains', 'supports', 'undermines'}:
                continue
            if term_key(item['term']) == edge.subject_key and any(
                    term_key(e) == edge.object_key for e in exposures):
                causes_exposure += edge.proofs[:1]
            if edge.object_key == term_key(item['term']) and any(
                    term_key(e) == edge.subject_key for e in exposures):
                downstream += edge.proofs[:1]
        item['exposure_evidence'] = causes_exposure
        item['downstream_evidence'] = downstream
        if downstream:
            item.update(role='possible_downstream_variable', recommended_action='Do not adjust automatically; may block a mechanism or introduce bias.')
        elif causes_exposure:
            item.update(role='candidate_shared_cause', recommended_action='Check timing and causal assumptions before treating as a confounder.')


def measurement_hints(spec, sentences):
    from cpu_llm.deepen import _cite
    marker = re.compile(r'\b(?:measur\w*|defined as|operational\w*|tokens?\s*(?:/|per)\s*s(?:econd)?|'
                        r'watts?|joules?|milliseconds?|percent)\b', re.I)
    terms = [t for t in dict.fromkeys([spec.a, *spec.via, spec.b, spec.c]) if t]
    return {term_key(t): [dict(_cite(row, sentence), qualification='measurement_hint_not_validated_definition')
                         for _, row, sentence in sentences.with_terms([t], at_least=1, pattern=marker)[:3]]
            for t in terms}


def operationalize(plan, spec, options, composition, hints=None):
    variables, missing = [], []
    roles = [('intervention', t) for t in plan['manipulate']] + [('outcome', t) for t in plan['measure']]
    roles += [('stratifier', t) for t in plan.get('strata', [])]
    roles += [('mediator', t) for t in (spec.via if spec.pattern == 'chain' and plan['design'] != 'resolve_first' else ())]
    typed = {term_key(spec.c): (plan.get('variable_types') or {}).get('c')}
    for role, term in roles:
        definition = options['definitions'].get(term_key(term), {})
        requirements = []
        if role == 'intervention':
            if not definition.get('levels'):
                requirements.append('intervention levels')
            if definition.get('feasible') is not True:
                requirements.append('feasible intervention or justified observational design')
        else:
            if not definition.get('measurement'):
                requirements.append('measurement procedure')
            if not definition.get('unit'):
                requirements.append('unit or explicit categorical scale')
            if role == 'stratifier' and not definition.get('levels'):
                requirements.append('levels or strata to compare')
            if role == 'outcome' and typed.get(term_key(term)) not in (None, 'outcome_metric') \
                    and not definition.get('measurement'):
                requirements.append('a measurable outcome (this term is not a metric)')
        if _VAGUE.search(term):
            requirements.append('precise replacement for vague variable')
        variables.append(dict(term=term, role=role, definition=definition, missing=requirements,
                              source_hints=(hints or {}).get(term_key(term), []),
                              provenance='user_supplied_assumption' if definition else 'not_defined'))
        missing.extend(dict(kind='variable', term=term, requirement=r) for r in requirements)
    for key in ('replicates', 'acceptance_criterion'):
        if key not in options['protocol']:
            missing.append(dict(kind='protocol', requirement=key))
    if composition['status'] != 'conditional':
        missing.append(dict(kind='composition', requirement='Resolve semantic, scope or evidence concerns.'))
    plan.update(variables=variables, protocol=options['protocol'], missing_requirements=missing,
                readiness='needs_input' if missing else 'specified_for_review', executed=False,
                control_policy='Candidate controls require causal review; do not adjust automatically.',
                statistical_validity='not_established')
    if spec.pattern == 'convergent':
        plan['interaction_test'] = dict(contrast='Y11 - Y10 - Y01 + Y00',
            assumptions='Additive outcome scale, matched conditions and defined interventions.',
            interpretation='A zero interaction contrast challenges compounding, not the individual effects.')


def novelty_review(spec, sentences, options, budget, reviewer=None):
    result = dict(requested=options['novelty'], kb_status='not_requested', matches=[],
                  external_status='not_requested', external_matches=[], prior_art_status='not_checked',
                  scientific_novelty='not_established')
    if not options['novelty']:
        return result
    terms = [t for t in dict.fromkeys([spec.a, *spec.via, spec.b, spec.c]) if t]
    # Co-mention is deliberately not labeled a prior demonstration of the relationship.
    from cpu_llm.deepen import _cite
    result['matches'] = [dict(_cite(row, sentence), qualification='potential_overlap_not_equivalence')
                         for _, row, sentence in sentences.with_terms(terms, at_least=len(terms))[:6]]
    result['kb_status'] = 'potential_overlap' if result['matches'] else 'no_overlap_found_in_snapshot'
    if not options['external_review']:
        return result
    if reviewer is None:
        result.update(external_status='not_configured', prior_art_status='not_configured')
        return result
    budget.check()
    remaining = budget.limits.max_seconds - (budget.clock() - budget.started)
    try:
        records = reviewer(query=' ; '.join(terms), max_results=6, timeout_seconds=remaining)
        budget.check()
        if not isinstance(records, list) or len(records) > 6:
            raise ValueError('Reviewer must return at most six records.')
        clean = []
        for record in records:
            budget.check()
            if not isinstance(record, dict):
                raise ValueError('Invalid literature record.')
            title = _text(record.get('title'), 'title', 500)
            url = _text(record.get('url'), 'url', 2000)
            parsed = urlparse(url)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Literature references require HTTPS URLs without credentials.')
            excerpt = _text(record.get('excerpt'), 'excerpt', 3000)
            stems = set(_content(_tokens(title + ' ' + excerpt)))
            named = [t for t in terms if set(_content(_tokens(t))) and set(_content(_tokens(t))) <= stems]
            clean.append(dict(title=title, url=url, excerpt=excerpt, terms_named=named,
                              qualification='external_overlap_candidate_not_kb_evidence'))
        result.update(external_status='reviewed_candidates', external_matches=clean,
                      prior_art_status='potential_prior_art' if any(len(c['terms_named']) >= 2 for c in clean)
                      else 'none_found')
    except Exception as exc:
        from cpu_llm.cycle_exploration import StopSearch
        if isinstance(exc, StopSearch):
            raise
        result.update(external_status='unavailable_or_invalid', prior_art_status='unavailable')
    return result


def research_actions(composition, plan, novelty):
    actions = []
    if composition.get('bridges') or composition.get('scope_differences'):
        actions.append(dict(id='bridge_review', kind='semantic', instruction='Resolve the listed endpoint meanings and source-setting differences.'))
    if composition.get('qualifications'):
        actions.append(dict(id='qualification_review', kind='scope', instruction='Restrict the proposal to the cited conditions and quantifiers.'))
    for item in plan['missing_requirements']:
        identity = json.dumps(item, sort_keys=True)
        actions.append(dict(id=hashlib.sha256(identity.encode()).hexdigest()[:16], **item,
                            instruction=f"Supply {item['requirement'].rstrip('.')}" + (f" for {item['term']}." if 'term' in item else '.')))
    if novelty['scientific_novelty'] == 'not_established':
        actions.append(dict(id='novelty_review', kind='novelty', instruction='Compare this exact proposal with current literature; inspect overlap candidates and document coverage.'))
    actions.append(dict(id='execute_reviewed_plan', kind='execution',
        instruction='After resolving requirements, execute the reviewed protocol and supply measurements; this node has not run an experiment.'))
    return actions


def fingerprint(rows):
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps([row['document_id'], row['chunk_text'], _context(row)], sort_keys=True).encode())
    return digest.hexdigest()


LEAD_STATUSES = ('testable', 'needs_semantic_resolution', 'contested_tension', 'coverage_gap',
                 'insufficient_evidence', 'needs_review', 'incomplete')


def lead_status(verdict, composition, links, incomplete):
    """One status a consumer can act on; it travels with the receipt so a summary cannot drop it."""
    if incomplete or verdict == 'incomplete':
        return 'incomplete'
    if verdict == 'bridge_mismatch':
        return 'needs_semantic_resolution'
    if verdict == 'contested' or composition.get('status') == 'incompatible_direction':
        return 'contested_tension'
    if any(link.get('coverage', {}).get('gap') for link in links):
        return 'coverage_gap'
    if verdict in {'unsupported', 'partly_supported'}:
        return 'insufficient_evidence'
    if any(bridge.get('kind') == 'meaning' for bridge in composition.get('bridges', [])):
        return 'needs_semantic_resolution'
    if verdict == 'all_links_supported' and composition.get('status') == 'conditional':
        return 'testable'
    return 'needs_review'


def quarantine(plan, status, composition, links):
    """Replace the experiment with what must be resolved first; keep the design that was withheld."""
    steps = []
    if status == 'needs_semantic_resolution':
        seen = set()
        for bridge in composition.get('bridges', []):
            if bridge.get('kind') != 'meaning':
                continue
            pair = (bridge['source_term'], bridge['requested'])
            if pair in seen:
                continue
            seen.add(pair)
            steps.append(f'Confirm whether "{pair[0]}" [{bridge["citation"]["document_id"]}] denotes the same '
                         f'quantity as "{pair[1]}".')
        for link in links:
            if link['status'] == 'bridge_mismatch':
                for item in link['counter'][:2]:
                    steps.append(f'The contrary source [{item["document_id"]}] uses different terms; check whether '
                                 f'it bears on {link["source"]} -> {link["target"]}: {item["quote"]}')
        steps = steps[:6] + ['If the meanings differ, restate the hypothesis in the sources\' own terms and run '
                             'Deepen again.']
    else:
        for link in links:
            if link['status'] != 'contested' and not link['counter']:
                continue
            genuine = [c for c in link['counter'] + link['support'] if c.get('endpoint_match') != 'bridged']
            by_relation = {}
            for item in genuine:
                by_relation.setdefault(item['relation'], item)
            if len(by_relation) > 1 or link['counter']:
                for item in list(by_relation.values())[:3]:
                    steps.append(f'Weigh the contrary evidence on {link["source"]} -> {link["target"]} '
                                 f'({item["relation"]}) [{item["document_id"]}]: {item["quote"]}')
        if not steps:
            steps.append('The cited effects compose to the opposite of the stated direction; inspect each link\'s '
                         'quotes for the step that reverses it.')
        steps = steps[:6] + ['State the conditions under which each source holds; the hypothesis may survive only '
                             'in a restricted regime.', 'Restate it for that regime and run Deepen again.']
    return dict(design='resolve_first', blocked_design=plan['design'], manipulate=[], measure=[], mediator=None,
                controls=plan['controls'], steps=steps, fails_if=None,
                reason=('meaning differences between linked sources' if status == 'needs_semantic_resolution'
                        else 'contrary evidence or contradicted direction'))
