"""Bounded cross-chunk design hypotheses with cited premises."""
from itertools import combinations, islice, zip_longest
import hashlib
import re

from cpu_llm.connection_channels import evaluate_connection
from cpu_llm.knowledge_graph import Fact, extract_facts, normalize

NOTE = 'Invention note. Proposals from the invention node are hypotheses. They may contain errors and can vary between runs.'
_BARE_IMAGINE = r'imagine\s+(?!story\b|poem\b|fiction\b|scene\b|world\b)[\w-]+(?=\s*[.?!;]|\s*$)'
INVENTION_START = (
    r'(?:(?:invent|imagine|create|design)\s+(?:a\s+)?'
    r'(?:new\s+(?:concept|design|idea|hypothesis|solution)|something\s+new)\b'
    r'|invention(?=\s*(?:[:.!?;]|$)|\s+(?:for|from|about|using|with|based on)\b)'
    rf'|invent\b|{_BARE_IMAGINE})'
)
_COMMAND = re.compile(rf'^(?:please\s+)?{INVENTION_START}', re.I)
_SEED_PREFIX = re.compile(
    r'^(?:from|about|for|using|with|based on)\s+(?:(?:the\s+)?relationships\s+around\s+|(?:these|the)\s+(?:input\s+)?terms\s*[: ]\s*)?',
    re.I,
)
_EXPLICIT_EDGE = re.compile(r'(?P<subject>[\w -]+?) (?P<verb>uses|stores) (?P<object>[^.!?]+)\.?$', re.I)


def invention_seed(message, *, forced=False):
    """Return None for another route, or an empty string for a missing subject."""
    text = message.strip().rstrip('.!?').strip()
    bare = re.fullmatch(rf'(?:please\s+)?{_BARE_IMAGINE}', text, re.I)
    if bare:
        return text.split()[-1]
    if text.casefold() in {'imagine', 'please imagine'}:
        return ''
    match = _COMMAND.match(text)
    if match:
        return _SEED_PREFIX.sub('', text[match.end():].lstrip(' :')).strip()
    return text if forced else None


def _source_facts(rows):
    from cpu_llm.answerability import _sentences
    from cpu_llm.knowledge_graph import _UNSAFE

    for row in rows:
        doc_id, text = row['document_id'], row['chunk_text']
        yield from extract_facts(doc_id, text)
        for sentence in _sentences(text):
            match = _EXPLICIT_EDGE.fullmatch(sentence)
            if match and not _UNSAFE.search(sentence):
                verb = match['verb'].lower()
                obj = re.split(r'\s+for\s+', match['object'], maxsplit=1, flags=re.I)[0] if verb == 'uses' else match['object']
                yield Fact(match['subject'], verb, obj, doc_id, sentence)


def _proposal(left, right):
    pair = {left.relation: left, right.relation: right}
    if set(pair) == {'uses', 'stores'} and 'metadata' in pair['uses'].sentence.casefold() and 'encrypted' in pair['stores'].object.casefold():
        return (
            f'Prototype storing an encryption-key version in {pair["uses"].object} metadata for {pair["stores"].object}.',
            'This assumes the metadata schema and restore process can be changed.',
            'A key-version field could help select the restore key, with added schema and access-control work.',
            'Restore backups created before and after key rotation and verify that each selects the correct key.',
        )
    return (
        f'Prototype a shared interface between {left.object} and {right.object}.',
        'This assumes both components expose an interface that can be adapted.',
        'A shared interface could reduce coordination work and introduce an additional dependency.',
        'Compare a small integration prototype with the existing workflow and measure failures and manual steps.',
    )


def execute_invention(app, message, seed, *, caller=None, as_of=None, strict=False):
    import psycopg
    from cpu_llm.access import source_allowed
    from cpu_llm.pipeline import _caller_for

    context = _caller_for(app, caller)
    allowed = None if context is None else context.allowed_sources

    def result(status, text, invention=None):
        response = dict(message=message, tenant_id=app.tenant_id, answer_status=status, status=status, answer=None,
                        audit_passed=False, answer_evidence=[], reply=dict(text=text, body=text),
                        needs_clarification=status == 'needs_clarification',
                        judgment=dict(outcome=status, complete=status == 'hypotheses'))
        if invention is not None:
            response['invention'] = invention
            response['routing'] = dict(post_stages=['taxonomy_invention'])
        return response

    if app.guard.check(message + '\n' + seed).decision != 'allow' or allowed is not None and not allowed:
        return result('blocked', 'Request blocked.')
    if strict:
        return result('unsupported', 'Strict evidence mode disables invention.')
    receipt = dict(triggered=True, potentially_nondeterministic=True, proposals=[], complete=True,
                   novelty_scope='recognized relationships and endpoint mentions in the authorized snapshot')
    if not seed or len(seed) > 240:
        return result('needs_clarification', 'Name a short subject in your invention request, such as “Create a new concept from Helios.”', receipt)
    try:
        rows, when = app.index.strict_source_rows(allowed, as_of=as_of)
        if len(rows) > 10000 or sum(len(row['chunk_text']) for row in rows) > 8_000_000:
            raise ValueError('snapshot limit')
    except (ValueError, RuntimeError, psycopg.Error):
        receipt['complete'] = False
        return result('partial', 'The invention source snapshot was unavailable or exceeded its limit.', receipt)
    rows = [row for row in rows if source_allowed(row['document_id'], allowed)]
    subjects = {normalize(term) for term in re.split(r',|\s+and\s+', seed, flags=re.I)}
    chunks = {row['document_id']: row['chunk_text'] for row in rows}
    facts = list(dict.fromkeys(fact for fact in _source_facts(rows)
                              if fact.sentence in chunks[fact.document_id]))
    links = [fact for fact in facts if normalize(fact.subject) in subjects]
    taxonomy = {normalize(fact.object) for fact in links if fact.relation == 'is_a'}
    links.extend(fact for fact in facts if normalize(fact.subject) in taxonomy - subjects)
    receipt['taxonomy'] = sorted(taxonomy)
    by_relation = {}
    for fact in links:
        if len(fact.sentence) <= 1000 and len(fact.object) <= 240:
            by_relation.setdefault((normalize(fact.object), fact.relation), []).append(fact)
    # Reserve a premise slot for distinct links before spending slots on duplicates.
    ordered = (fact for batch in zip_longest(*islice(by_relation.values(), 32)) for fact in batch if fact)
    selected = list(islice(ordered, 32))
    receipt.update(as_of=when, complete=len(selected) == len(links))
    links = selected
    groups = {}
    for fact in links:
        groups.setdefault((normalize(fact.object), fact.relation), []).append(fact)
    labels = list(dict.fromkeys(label for fact in links for label in (fact.subject, fact.object) if len(label) <= 240))
    pipeline = getattr(app.index, 'pipeline', None)
    tensors = {}
    if labels and pipeline is not None:
        try:
            tensors = dict(zip(labels, pipeline.encode_texts(labels)))
        except (ValueError, RuntimeError, OSError):
            receipt.update(complete=False, vector_status='unavailable')
    scoring = dict(enabled_channels=getattr(pipeline, 'enabled_channels', None),
                   causal_matrix=getattr(getattr(app.index, 'engine', None), 'causal_matrix', None))

    def channels(fact):
        return evaluate_connection(fact, left_tensor=tensors.get(fact.subject),
                                   right_tensor=tensors.get(fact.object), **scoring)['channels']

    def premise(fact):
        chunk = chunks[fact.document_id]
        start = chunk.index(fact.sentence)
        return dict(subject=fact.subject, relation=fact.relation, object=fact.object,
                    document_id=fact.document_id, quote=fact.sentence, start=start,
                    end=start + len(fact.sentence), chunk_sha256=hashlib.sha256(chunk.encode()).hexdigest(),
                    channels=channels(fact))

    receipt['relationships'] = [premise(fact) for fact in links]
    existing = {frozenset((normalize(f.subject), normalize(f.object))) for f in facts}
    from cpu_llm.answerability import _sentences
    # A source that already discusses both endpoints may contain the proposed
    # relationship in wording the extractor misses. Abstain on those pairs.
    object_patterns = {key: re.compile(r'(?<!\w)' + re.escape(key) + r'(?!\w)', re.I)
                       for key, _ in groups}
    for row in rows:
        for sentence in _sentences(row['chunk_text']):
            mentioned = [key for key, pattern in object_patterns.items() if pattern.search(sentence)]
            existing.update(frozenset(pair) for pair in combinations(mentioned, 2))
    candidates = []
    seen = set()
    for left_group, right_group in combinations(groups.values(), 2):
        left, right = left_group[0], right_group[0]
        pair = frozenset((normalize(left.object), normalize(right.object)))
        if len(pair) != 2 or pair in existing or pair in seen:
            continue
        if left.relation in {'is_a', 'alias_of'} or right.relation in {'is_a', 'alias_of'}:
            continue
        if not any(a.document_id != b.document_id for a in left_group for b in right_group):
            continue
        seen.add(pair)
        scores = channels(Fact(left.object, 'could_coordinate_with', right.object, '', ''))
        proposal, assumptions, tradeoff, test = _proposal(left, right)
        candidates.append(dict(proposal=proposal, assumptions=assumptions, tradeoff=tradeoff, test=test,
            relation='could_coordinate_with', qualification='hypothesis', channels=scores,
            premises=[premise(f) for f in [*left_group, *right_group]]))
    def rank(item):
        scores = [item['channels'][name]['vector_score'] for name in ('dense', 'identity')]
        return tuple(float('-inf') if score is None else score for score in scores)

    candidates.sort(key=rank, reverse=True)
    receipt['proposals'] = candidates[:8]
    receipt['complete'] = receipt['complete'] and len(candidates) <= 8
    lines = []
    for number, item in enumerate(receipt['proposals'], 1):
        lines.extend([f'{number}. Proposed design: {item["proposal"]}', item['assumptions'], item['tradeoff'],
                      'Test: ' + item['test'], 'Cited premises:'])
        lines.extend(f'[{p["document_id"]}] {p["quote"]}' for p in item['premises'])
    if not receipt['complete']:
        lines.append('Candidate coverage is partial. Check the invention receipt for the search and vector status.')
    status = 'partial' if not receipt['complete'] else 'hypotheses' if receipt['proposals'] else 'insufficient_evidence'
    return result(status, '\n'.join(lines) or 'No qualifying cross-chunk proposal was found.', receipt)


def finish_invention_response(result):
    """Append the disclosure outside the selected layout once per response."""
    import html
    from cpu_llm.output_rendering import render_response

    result = render_response(result)
    if not result.get('invention', {}).get('triggered'):
        return result
    rendered = result.get('rendered_response', {})
    suffix = '<p>' + html.escape(NOTE) + '</p>' if rendered.get('media_type') == 'text/html' else '\n\n' + NOTE
    reply = result['reply']
    text = reply['text'] + suffix
    reply.update(text=text, body=text)
    if rendered:
        rendered['text'] = text
    return result
