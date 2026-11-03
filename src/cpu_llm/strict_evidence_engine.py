"""Bounded evidence selection and exact arithmetic; no learned generation."""
from __future__ import annotations

import hashlib
import re
from decimal import Decimal, localcontext

NUMBER = r'[+-]?\d{1,24}(?:\.\d{1,12})?'
UNSAFE = re.compile(r'\b(?:if|unless|when|except|may|might|sometimes|usually|average|approximately|before|after|only|unknown|unverified|unconfirmed|uncertain|suspected|estimated|roughly)\b', re.I)
REF = re.compile(r'\b(?:it|this|that|they|them|their|its)\b', re.I)


def name(value):
    return re.sub(r'^the\s+', '', value.strip(), flags=re.I).casefold()


def value_key(value):
    """Exact scalar equivalence only; original source wording is never converted."""
    units = {'mg': ('mass', '0.001'), 'g': ('mass', '1'), 'mcg': ('mass', '0.000001'),
             'kg': ('mass', '1000'), 'mL': ('volume', '0.001'), 'L': ('volume', '1'),
             'hour': ('time', '60'), 'hours': ('time', '60'), 'minute': ('time', '1'), 'minutes': ('time', '1')}
    match = re.fullmatch(rf'({NUMBER})\s*(mg|g|mcg|kg|mL|L|hours?|minutes?)', value)
    if match:
        kind, scale = units[match[2]]
        with localcontext() as context:
            context.prec = 100
            return kind, Decimal(match[1]) * Decimal(scale)
    return 'literal', value.strip()


def proof(row):
    text = row['chunk_text'].strip()
    start = row['chunk_text'].index(text)
    return dict(document_id=row['document_id'], quote=text, start=start, end=start + len(text),
                chunk_sha256=hashlib.sha256(row['chunk_text'].encode('utf-8')).hexdigest())


def facts_from(rows):
    facts, memberships, rules = [], [], []
    for row in rows:
        text = row['chunk_text'].strip().rstrip('.!')
        # Keep whole chunks atomic; never drop a second sentence or qualifier.
        if not text or re.search(r'(?<!\d)\.|\.(?!\d)|[!?\n]', text):
            continue
        evidence = proof(row)
        text = re.sub(r"\bisn't\b", 'is not', text, flags=re.I)
        universal = re.fullmatch(r'Every (.+?) has (?:a |an )?([a-z][a-z -]{0,60}) of (.+)', text, re.I)
        if universal and not UNSAFE.search(text):
            rules.append(dict(entity=name(universal[1]), attribute=name(universal[2]), value=universal[3], proof=evidence))
            continue
        match = re.fullmatch(r'The ([a-z][a-z -]{0,60}) (?:of|for) (.+?) is (.+)', text, re.I)
        if match:
            attribute, entity, value = match.groups()
        else:
            match = re.fullmatch(r"(.+?)'s ([a-z][a-z -]{0,60}) is (.+)", text, re.I)
            if match:
                entity, attribute, value = match.groups()
            else:
                match = re.fullmatch(r'(.+?) has (?:a |an )?([a-z][a-z -]{0,60}) of (.+)', text, re.I)
                if match:
                    entity, attribute, value = match.groups()
                else:
                    member = re.fullmatch(r'(.+?) is (not )?an? (.+)', text, re.I)
                    if member and not UNSAFE.search(text):
                        memberships.append(dict(entity=name(member[1]), parent=name(member[3]), negative=bool(member[2]), proof=evidence))
                    continue
        facts.append(dict(entity=name(entity), attribute=name(attribute), value=value,
                          negative=bool(re.match(r'not\b', value, re.I)), uncertain=bool(UNSAFE.search(text)), proof=evidence))
    return facts, memberships, rules


def parse(query):
    query = re.sub(r'^(?:please\s+)?', '', query.strip(), flags=re.I)
    from cpu_llm.numeric_comparison import compare_prompt
    comparison = compare_prompt(query)
    if comparison is not None:
        return dict(kind='comparison', comparison=comparison)
    if UNSAFE.search(query) or re.search(r'["“”`]|\b(?:not|or)\b', query, re.I):
        return None
    calc = re.fullmatch(rf'Calculate ({NUMBER})\s*([+*\-])\s*({NUMBER})[.!]?', query, re.I)
    if calc:
        return dict(kind='arithmetic', left=calc[1], op=calc[2], right=calc[3])
    calc = re.fullmatch(rf'Calculate (?:the )?([a-z][a-z -]{{0,60}}) of (.+?) times ({NUMBER})[.!]?', query, re.I)
    if calc:
        return dict(kind='source_calculation', attribute=name(calc[1]), entity=calc[2], multiplier=calc[3])
    overview = re.fullmatch(r'List (?:all )?documented attributes of (.+?)[.!?]?', query, re.I)
    if overview:
        return dict(kind='overview', entity=overview[1])
    match = re.fullmatch(r'What is the ([a-z][a-z -]{0,60}) of (.+?)\?', query, re.I)
    if match:
        return dict(kind='lookup', attribute=name(match[1]), entity=match[2])
    return None


def tasks_from(query):
    if len(query) > 32000:
        return None
    from cpu_llm.numeric_comparison import compare_prompt
    if compare_prompt(query) is not None:
        return [dict(kind='comparison', comparison=compare_prompt(query), query=query)]
    fields = re.fullmatch(r'What are the ([a-z ,\-]+) of (.+?)\?', query.strip(), re.I)
    if fields:
        attributes = re.split(r',\s*(?:and\s+)?|\s+and\s+', fields[1], flags=re.I)
        queries = [f'What is the {a.strip()} of {fields[2]}?' for a in attributes]
    else:
        queries = re.split(r'(?<=\?)\s+(?:and\s+)?|\n+|;\s*', query.strip(), flags=re.I)
    if not 1 <= len(queries) <= 8:
        return None
    result, entities = [], set()
    for query in queries:
        task = parse(query)
        if task is None:
            result.append(dict(kind='unsupported', query=query))
            continue
        task['query'] = query
        if 'entity' in task:
            entity = task['entity']
            if REF.fullmatch(entity.strip()):
                if len(entities) != 1:
                    task['kind'] = 'unsupported'
                else:
                    task['reference_binding'] = dict(original=entity, replacement=next(iter(entities)))
                    task['entity'] = next(iter(entities))
            elif (REF.search(entity) or re.search(r'\b(?:and|or|not)\b|[?;\n]', entity, re.I)
                  or not re.fullmatch(r'[\w -]{1,100}', entity)):
                task['kind'] = 'unsupported'
            else:
                entities.add(entity)
        result.append(task)
    return result


def lookup(task, facts, memberships, rules):
    entity, attribute = name(task['entity']), task['attribute']
    candidates = [(f, [f['proof']]) for f in facts if f['entity'] == entity and f['attribute'] == attribute]
    for member in memberships:
        if member['entity'] != entity:
            continue
        for rule in rules:
            if rule['entity'] == member['parent'] and rule['attribute'] == attribute:
                negatives = [m for m in memberships if m['entity'] == entity and m['parent'] == member['parent'] and m['negative']]
                candidates.append((dict(rule, negative=member['negative'] or bool(negatives), uncertain=False),
                                   [member['proof'], rule['proof']] + [m['proof'] for m in negatives]))
    evidence = []
    for _, proofs in candidates:
        for p in proofs:
            if p not in evidence:
                evidence.append(p)
    if not candidates:
        return 'insufficient_evidence', [], None
    if any(f['uncertain'] for f, _ in candidates):
        return 'insufficient_evidence', evidence, None
    if any(f['negative'] for f, _ in candidates) or len({value_key(f['value']) for f, _ in candidates}) > 1:
        return 'conflicting', evidence, None
    return 'evidence_quote', evidence, candidates[0][0]['value']


def calculate(task, source_value=None):
    unit = ''
    if source_value is not None:
        match = re.fullmatch(rf'({NUMBER})\s*(mg|g|mcg|kg|mL|L|hours?|minutes?)', source_value)
        if not match:
            return None
        left, right, op, unit = match[1], task['multiplier'], '*', match[2]
    else:
        left, right, op = task['left'], task['right'], task['op']
    with localcontext() as context:
        context.prec = 100
        a, b = Decimal(left), Decimal(right)
        value = a + b if op == '+' else a - b if op == '-' else a * b
    return dict(operation=op, operands=[left, right], value=format(value, 'f'), unit=unit,
                display=format(value, 'f') + (' ' + unit if unit else ''), clinical_validation=False)


def answer(appliance, message, *, caller=None, as_of=None):
    from cpu_llm.pipeline import _caller_for
    from cpu_llm.access import source_allowed
    from cpu_llm.strict_evidence import requested
    context = _caller_for(appliance, caller)
    allowed = None if context is None else context.allowed_sources
    result = dict(message=message, original_message=message, tenant_id=appliance.tenant_id,
        request_id=None if context is None else context.request_id, answer=None, answer_status='unsupported',
        answer_evidence=[], audit_passed=False, evidence_policy=dict(version='strict-evidence-v3', enabled=True,
            allowed_sources=None if allowed is None else sorted(allowed), learned_generation=False,
            clinical_validation=False, source_truth_verified=False,
            conflict_detection='recognized literal and possessive/has/for forms; exact scalar unit equivalence',
            disabled_nodes=['fact_bridge', 'realizer', 'stylistic', 'reference_resolution', 'specialists'],
            stateless=True, scan_complete=False), reply=dict(text='Unsupported strict request; use explicit named attribute questions.'))
    result['guard_decision'] = appliance.guard.check(message).decision
    if result['guard_decision'] != 'allow':
        result.update(answer_status='blocked', reply=dict(text='Request blocked.'))
        return result
    tasks = tasks_from(requested(message, True)[1])
    if not tasks or all(t['kind'] == 'unsupported' for t in tasks):
        return result
    rows = []
    if any(t['kind'] not in {'arithmetic', 'comparison', 'unsupported'} for t in tasks):
        try:
            rows, when = appliance.index.strict_source_rows(allowed, as_of=as_of)
            if sum(len(row['chunk_text']) for row in rows) > 8_000_000:
                raise ValueError('strict scan text limit')
        except (ValueError, RuntimeError):
            result.update(answer_status='insufficient_evidence', reply=dict(text='Evidence scan unavailable or exceeds the strict scan limit; no answer selected.'))
            return result
        if any(not source_allowed(row['document_id'], allowed) for row in rows):
            raise RuntimeError('strict source scope violation')
        result['evidence_policy'].update(scan_complete=True, as_of=when, scanned_chunks=len(rows))
    facts, memberships, rules = facts_from(rows)
    expanded = []
    for task in tasks:
        if task['kind'] == 'overview':
            attributes = sorted({f['attribute'] for f in facts if f['entity'] == name(task['entity'])})
            if len(attributes) > 32:
                task = dict(task, kind='unsupported')
            elif attributes:
                expanded.extend(dict(task, kind='lookup', attribute=a) for a in attributes)
                continue
        expanded.append(task)
    outputs = []
    for task in expanded:
        evidence, calculation = [], None
        if task['kind'] == 'comparison':
            status, calculation = 'derived_calculation', task['comparison']
        elif task['kind'] == 'arithmetic':
            status, calculation = 'derived_calculation', calculate(task)
        elif task['kind'] in {'lookup', 'source_calculation'}:
            status, evidence, value = lookup(task, facts, memberships, rules)
            if task['kind'] == 'source_calculation' and status == 'evidence_quote':
                calculation = calculate(task, value)
                status = 'derived_calculation' if calculation else 'unsupported'
        else:
            status = 'insufficient_evidence' if task['kind'] == 'overview' else 'unsupported'
        if status == 'evidence_quote':
            text = 'Source quotations (not clinically validated):\n' + '\n'.join(f"[{p['document_id']}] {p['quote']}" for p in evidence)
        elif status == 'derived_calculation':
            text = calculation['text'] if calculation['operation'] == 'greater_than' else 'Exact arithmetic: ' + calculation['display'] + '. Arithmetic only; not treatment advice.'
        else:
            text = {'conflicting': 'Source evidence conflicts; no answer selected.',
                    'insufficient_evidence': 'No unambiguous supported evidence; no answer selected.'}.get(status, 'Unsupported strict request; no answer selected.')
        outputs.append(dict(query=task['query'], status=status, request=task,
            result=dict(answer_status=status, answer_evidence=evidence, calculation=calculation, reply=dict(text=text))))
        for p in evidence:
            if p not in result['answer_evidence']:
                result['answer_evidence'].append(p)
    statuses = [t['status'] for t in outputs]
    success = {'evidence_quote', 'derived_calculation'}
    status = statuses[0] if len(set(statuses)) == 1 else ('completed' if all(s in success for s in statuses) else 'partial' if any(s in success for s in statuses) else 'conflicting' if 'conflicting' in statuses else 'insufficient_evidence')
    result.update(answer_status=status, task_results=outputs,
                  reply=dict(text='\n\n'.join(t['result']['reply']['text'] for t in outputs)))
    if len(outputs) == 1 and outputs[0]['result']['calculation']:
        result['calculation'] = outputs[0]['result']['calculation']
    return result
